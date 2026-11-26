"""Replay the v5 hybrid boot layout and attach the two verified v6 layers."""
import json
import os
import re
import stat
import sys
from pathlib import Path

from pipeline.devlite.build import detect
from pipeline.devlite.minimal_build import compare_iso_trees, make_md5
from pipeline.devlite.minimal_root import EPOCH
from pipeline.devlite.release_layers import delta_manifest, manifests
from pipeline.devlite.runtime import Runner, owned_directory
from pipeline.devlite.structure import compare_boot_metadata, digest, region_digest
from pipeline.devlite.validation import inventory, iso_metadata, verify_manifest
from v5.assemble import package_versions
from v6.pack import LEAVES, SOURCE_SHA, STACKS, STATE, write_json
from v6.storage import ROOT, SOURCE, require_space, stage_budgets

FILENAME = 'devlite-os-1.0-v6-amd64.iso'
VOLUME = 'DevLite OS 1.0 v6'


def open_pack(path):
    if (path.parent != STATE or not re.fullmatch(r'pack-[a-z0-9_]{8}', path.name)
            or path.resolve() != path):
        raise ValueError('Unapproved pack directory')

    for directory in (STATE, path, path / 'published'):
        info = directory.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError('Untrusted pack directory')
    published = path / 'published'

    def sealed(name):
        item = published / name
        info = item.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o222:
            raise ValueError(f'Untrusted pack file: {name}')
        return item

    report = json.loads(sealed('pack.json').read_text())
    if (report.get('status') != 'v6_layers_verified' or report.get('cleanup_errors') != []
            or report.get('host_critical_files_unchanged') is not True
            or report.get('source_sha256') != SOURCE_SHA or report.get('targets', {}).keys() != LEAVES.keys()):
        raise ValueError('Preflight pack receipt rejected')
    result = {}
    for target, name in LEAVES.items():
        entry = report['targets'][target]
        image, manifest = sealed(name), sealed(target + '.manifest')
        if (entry['image'] != name or entry['composition_verified'] is not True
                or type(entry['allocated_bytes']) is not int or entry['allocated_bytes'] <= 0
                or image.stat().st_size != entry['bytes'] or digest(image) != entry['sha256']
                or digest(manifest) != entry['manifest_sha256']):
            raise ValueError('Pack result no longer matches its receipt')
        result[target] = (image, manifest, entry)
    return result


def render_catalog(text, added_bytes):
    path = f'  path: {STACKS["base"][-1]}'
    updated, count = re.subn(r'^  size: ([0-9]+)$',
                             lambda match: f'  size: {int(match[1]) + added_bytes}', text, flags=re.M)
    if count != 1 or updated.splitlines().count(path) != 1:
        raise ValueError('Unexpected installation source')
    updated = updated.replace(path + '\n', f'  path: {LEAVES["base"]}\n')
    translations = {
        'description': 'Instalação mínima do DevLite OS 1.0.',
        'name': 'DevLite OS 1.0',
    }
    for field, translation in translations.items():
        pattern = rf'(?m)^  {field}:\n    en: [^\n]+\n'
        updated, count = re.subn(pattern, lambda match: (
            match[0] + f'    pt_BR: "{translation}"\n'
        ), updated)
        if count != 1:
            raise ValueError(f'Unexpected translated source field: {field}')
    return updated


def render_grub(text):
    lines = []
    for line in text.splitlines(keepends=True):
        if re.match(r'^\s*linux\s+/casper/vmlinuz(?:\s|$)', line):
            tokens = re.findall(r'(?<!\S)layerfs-path=(\S+)', line)
            if tokens != [STACKS['live'][-1]]:
                raise ValueError('Unexpected inherited Live layer')
            line = line.replace('layerfs-path=' + tokens[0], 'layerfs-path=' + LEAVES['live'])
        lines.append(line)
    return ''.join(lines)


def updates(original, files):
    casper = original / 'casper'
    documents = {
        'install-sources.yaml': render_catalog((casper / 'install-sources.yaml').read_text(),
                                               files['base'][2]['allocated_bytes']),
        'filesystem.size': str(int((casper / 'filesystem.size').read_text()) +
                               files['live'][2]['allocated_bytes']) + '\n',
    }
    old_base = (casper / 'devlite-base.manifest.full').read_text()
    old_live = (casper / 'filesystem.manifest').read_text()
    full = manifests(*(package_versions(files[t][1].read_text()) for t in ('base', 'live')), old_live)
    for target, old, key in (('base', old_base, 'devlite-base.manifest.full'),
                             ('live', old_live, 'filesystem.manifest')):
        name = LEAVES[target].removesuffix('.squashfs')
        documents[name + '.size'] = str(files[target][2]['allocated_bytes']) + '\n'
        documents[name + '.manifest'] = delta_manifest(old, full[key], STACKS[target][-1], name)
        documents[key] = full[key]
    checksums = (casper / 'SHA256SUMS').read_text()
    documents['SHA256SUMS'] = checksums.rstrip('\n') + '\n' + ''.join(
        f'{files[target][2]["sha256"]} *{name}\n' for target, name in LEAVES.items())
    documents = {'casper/' + name: text for name, text in documents.items()}
    for path in sorted((original / 'boot/grub').glob('*.cfg')):
        text = path.read_text()
        updated = render_grub(text)
        if updated != text:
            documents[path.relative_to(original).as_posix()] = updated
    if sum(name.startswith('boot/grub/') for name in documents) < 2:
        raise ValueError('Expected BIOS and UEFI GRUB paths')
    documents['casper/devlite-v6.json'] = json.dumps({
        'status': 'CANDIDATA DE HOMOLOGAÇÃO', 'distribution_approved': False,
        'source_v5_sha256': SOURCE_SHA, 'hyper_v_validation': 'pending',
    }, ensure_ascii=False) + '\n'
    return documents


def assemble(pack):
    if os.geteuid() == 0:
        raise ValueError('Run assembly as magaton')
    files = open_pack(pack)
    budget = stage_budgets(SOURCE.stat().st_size)
    require_space(ROOT, budget['assemble'] + budget['verify'])
    if digest(SOURCE) != SOURCE_SHA:
        raise ValueError('Pinned v5 ISO changed')
    job = owned_directory(ROOT / 'work', 'v6-iso-')
    (job / 'logs').mkdir()
    runner = Runner(job / 'logs', EPOCH)
    original = job / 'source-tree'
    runner.xorriso('reference', '-osirrox', 'on', '-indev', SOURCE, '-extract', '/', original)
    before = inventory(original)
    mapped = {'casper/' + name: files[target][0] for target, name in LEAVES.items()}

    def add_text(name, text):
        path = job / 'updates' / name
        path.parent.mkdir(exist_ok=True, parents=True)
        path.write_text(text)
        mapped[name] = path

    for name, document in updates(original, files).items():
        add_text(name, document)
    add_text('md5sum.txt', make_md5((original / 'md5sum.txt').read_text(), mapped, {}))
    output = owned_directory(ROOT / 'artifacts', 'devlite-v6-')
    partial = output / (FILENAME + '.partial')
    source_boot = detect(runner, SOURCE, 'source')
    args = ['-indev', str(SOURCE), '-outdev', str(partial), '-overwrite', 'on']
    for name, path in sorted(mapped.items()):
        entry = '/' + name
        args += ['-map', str(path), entry, '-chown', '0', entry, '--', '-chgrp', '0', entry,
                 '--', '-chmod', '0444', entry, '--', '-alter_date', 'm', '=' + str(EPOCH), entry, '--']
    args += ['-assess_indev_features', 'replay', '-boot_image', 'any', 'replay', '-volid', VOLUME,
             '-volume_date', 'uuid', source_boot['timestamp'], '-end']
    require_space(ROOT, SOURCE.stat().st_size + budget['verify'])
    runner.xorriso('assemble', *args)
    boot = detect(runner, partial, 'candidate')
    compare_boot_metadata(SOURCE, partial, source_boot, boot)
    if boot['volume_id'] != VOLUME or boot['timestamp'] != source_boot['timestamp']:
        raise ValueError('Unexpected volume metadata')
    if region_digest(SOURCE, source_boot['efi_offset'], source_boot['efi_bytes']) != region_digest(
            partial, boot['efi_offset'], boot['efi_bytes']):
        raise ValueError('EFI payload changed')
    require_space(ROOT, budget['verify'])
    result = job / 'result-tree'
    runner.xorriso('verify-extract', '-osirrox', 'on', '-indev', partial, '-extract', '/', result)
    compare_iso_trees(before, inventory(result), original, result, set(mapped) & set(before),
                      set(mapped) - set(before), set())
    old_meta = iso_metadata(runner.xorriso('source-metadata', '-indev', SOURCE, '-find', '/', '-exec', 'lsdl', '--'))
    new_meta = iso_metadata(runner.xorriso('candidate-metadata', '-indev', partial, '-find', '/', '-exec', 'lsdl', '--'))
    for name, value in old_meta.items():
        if name.lstrip('/') not in set(mapped) | {'boot.catalog'} and new_meta.get(name) != value:
            raise ValueError(f'Inherited metadata changed: {name}')
    for name, path in mapped.items():
        fields = new_meta['/' + name]
        if fields[0] != '-r--r--r--' or fields[2:4] != ['0', '0'] or digest(result / name) != digest(path):
            raise ValueError(f'Mapped file differs: {name}')
    md5 = verify_manifest(result, Path('md5sum.txt'), 'md5')
    sha = verify_manifest(result, Path('casper/SHA256SUMS'), 'sha256')
    if sha != len({*STACKS['base'], *STACKS['live'], *LEAVES.values()}):
        raise ValueError('Unexpected layer count')
    free = require_space(ROOT, 0)
    final = output / FILENAME
    fingerprint = digest(partial)
    write_json(output / 'validation.json', {
        'status': 'CANDIDATA DE HOMOLOGAÇÃO', 'distribution_approved': False,
        'iso': str(final), 'sha256': fingerprint, 'bytes': partial.stat().st_size,
        'iso_boot': boot, 'md5_entries': md5, 'layer_checksums': sha,
        'free_bytes': free, 'verification_workspace': str(job), 'pack': str(pack),
    })
    with (output / 'SHA256SUMS').open('x') as checksums:
        checksums.write(f'{fingerprint}  {FILENAME}\n')
    os.link(partial, final)
    partial.unlink()
    print(final)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Provide the verified pack directory')
    assemble(Path(sys.argv[1]))
