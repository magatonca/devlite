"""Orquestrador sem privilégios; operações root são sempre manuais e confirmadas."""
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path
from .build import preflight, detect, EXPECTED
from .runtime import BuildError, Runner, owned_directory
from .structure import digest, region_digest, compare_boot_metadata, pvd_metadata
from .validation import inventory, iso_metadata, normalized_bios, verify_manifest
from .minimal_root import EPOCH, HASHES, guard_workspace

BASELINE_HASH = '2e3a6eecf59d535a4825ff41655c542f6ef2017ccce9a9672891ace2672f2bc7'


def update_grub(text):
    arguments = 'locale=pt_BR.UTF-8 keyboard-configuration/layoutcode=br keyboard-configuration/modelcode=abnt2'
    count = 0
    lines = []
    for line in text.splitlines(keepends=True):
        if re.match(r'^\s*linux\s+/casper/vmlinuz(?:\s|$)', line):
            if 'locale=' in line or 'keyboard-configuration/' in line:
                raise BuildError('GRUB já tem configuração regional; revisar duplicação')
            line = line.replace('/casper/vmlinuz', '/casper/vmlinuz ' + arguments, 1)
            count += 1
        lines.append(line)
    if not count:
        raise BuildError('Nenhuma entrada Casper no GRUB')
    return ''.join(lines), count



def prepare(root):
    from .minimal_config import prepare_configuration
    source = preflight(root)
    if shutil.disk_usage(root).free < 40 * 1024**3:
        raise BuildError('Preparação requer pelo menos 40 GiB livres')
    workspace = owned_directory(root / 'work', 'phase4b1-')
    (workspace / 'logs').mkdir()
    runner = Runner(workspace / 'logs', EPOCH)
    runner.run('authenticate-source', [sys.executable, str(root / 'scripts/validar-iso.py')])
    for name, target in (('/casper', 'original-casper'), ('/boot/grub', 'original-grub'), ('/md5sum.txt', 'original-md5sum.txt')):
        runner.xorriso('extract-' + target, '-osirrox', 'on', '-indev', source, '-extract', name, workspace / target)
    prepare_configuration(root, workspace)
    print('Preparado para confirmação dos três comandos root:', workspace)
    return workspace


def make_md5(original, mapped, provenance):
    entries = {}
    for line in original.splitlines():
        checksum, name = line.split(maxsplit=1)
        name = name.lstrip('* ').removeprefix('./')
        if name == 'casper/SHA256SUMS.gpg':
            continue
        if name in ('md5sum.txt', 'boot.catalog', 'boot/grub/i386-pc/eltorito.img'):
            raise BuildError('Manifest original contém arquivo regenerável inesperado')
        entries[name] = checksum
    for name, file in {**mapped, **provenance}.items():
        if name == 'md5sum.txt':
            continue
        with file.open('rb') as stream:
            entries[name] = hashlib.file_digest(stream, 'md5').hexdigest()
    return ''.join(value + '  ./' + name + '\n' for name, value in sorted(entries.items()))


def compare_iso_trees(before, after, source_tree, result_tree, changed, added, removed):
    if set(after) != (set(before) - set(removed)) | set(added):
        raise BuildError('Árvore ISO tem adições/remoções fora da allowlist')
    for name in before.keys() & after.keys():
        if name in changed or before[name] == after[name]:
            continue
        if name == 'boot.catalog':
            continue
        if name == 'boot/grub/i386-pc/eltorito.img' and normalized_bios(source_tree / name) == normalized_bios(result_tree / name):
            continue
        raise BuildError('Arquivo ISO alterado sem autorização: ' + name)


def assemble(root, workspace):
    guard_workspace(workspace)
    source = preflight(root)
    if not (workspace / 'root-pack-ok.json').is_file():
        raise BuildError('As etapas privilegiadas ainda não concluíram a validação')
    logs = owned_directory(workspace, 'assembly-logs-')
    runner = Runner(logs, EPOCH)
    report = {'status': 'montando', 'workspace': str(workspace), 'uid': os.getuid(),
              'packages_installed': False, 'mounts': False, 'chroot': False,
              'boot': 'não testado', 'installation': 'não testada', 'post_install_persistence': 'não testada'}
    report_file = workspace / 'customization-report.json'
    try:
        verified = {name: json.loads((workspace / (folder + '.verified.json')).read_text()) for name, folder in
                    (('minimal.squashfs', 'base-root'), ('minimal.live.squashfs', 'live-root'))}
        generated = owned_directory(workspace, 'iso-updates-')
        mapped = {}
        for name, result in verified.items():
            file = workspace / 'rebuilt-casper' / name
            if digest(file) != result['sha256']:
                raise BuildError('SquashFS mudou após validação root')
            mapped['casper/' + name] = file
        sizes = {name: result['uncompressed_allocated_bytes'] for name, result in verified.items()}
        texts = {'casper/minimal.size': str(sizes['minimal.squashfs']) + '\n',
                 'casper/minimal.live.size': str(sizes['minimal.live.squashfs']) + '\n',
                 'casper/filesystem.size': str(sum(sizes.values())) + '\n'}
        catalog = (workspace / 'original-casper/install-sources.yaml').read_text()
        catalog, count = re.subn(r'^  size: [0-9]+$', '  size: ' + str(sizes['minimal.squashfs']), catalog, flags=re.M)
        if count != 1 or 'path: minimal.squashfs' not in catalog or 'type: fsimage-layered' not in catalog:
            raise BuildError('Catálogo do instalador não reconhecido')
        texts['casper/install-sources.yaml'] = catalog
        texts['casper/SHA256SUMS'] = ''.join(verified[name]['sha256'] + ' *' + name + '\n' for name in sorted(verified))
        grub_entries = 0
        for file in sorted((workspace / 'original-grub').glob('*.cfg')):
            original = file.read_text()
            if re.search(r'^\s*linux\s+/casper/vmlinuz', original, re.M):
                modified, count = update_grub(original)
                grub_entries += count
                texts['boot/grub/' + file.name] = modified
        if grub_entries < 4:
            raise BuildError('Esperadas entradas normal e safe graphics em GRUB e loopback')
        notice = {'edition': 'DevLite OS 1.0 experimental — configuração mínima', 'upstream_iso_sha256': EXPECTED,
                  'packages_changed': False, 'signature': 'checksums personalizados não assinados; assinatura Ubuntu original arquivada como proveniência',
                  'boot_installation': 'não testados', 'source_date_epoch': EPOCH}
        texts['casper/devlite-customization.json'] = json.dumps(notice, ensure_ascii=False, indent=2) + '\n'
        for name, value in texts.items():
            file = generated / name; file.parent.mkdir(parents=True, exist_ok=True); file.write_text(value)
            mapped[name] = file
        provenance = {'casper/devlite-provenance/original-SHA256SUMS': workspace / 'original-casper/SHA256SUMS',
                      'casper/devlite-provenance/original-SHA256SUMS.gpg': workspace / 'original-casper/SHA256SUMS.gpg'}
        md5 = generated / 'md5sum.txt'
        md5.write_text(make_md5((workspace / 'original-md5sum.txt').read_text(), mapped, provenance))
        mapped['md5sum.txt'] = md5
        for file in mapped.values():
            # Apenas arquivos novos próprios podem ter timestamp ajustado.
            if file.is_relative_to(generated):
                os.utime(file, (EPOCH, EPOCH))
        output_dir = owned_directory(root / 'artifacts', 'phase4b1-')
        candidate = output_dir / 'devlite-os-1.0-basic-experimental.iso.partial'
        original_boot = detect(runner, source, 'source')
        commands = ['-indev', str(source), '-outdev', str(candidate), '-overwrite', 'on',
                    '-mkdir', '/casper/devlite-provenance', '--',
                    '-mv', '/casper/SHA256SUMS.gpg', '/casper/devlite-provenance/original-SHA256SUMS.gpg', '--']
        for name, file in {**mapped, **provenance}.items():
            commands += ['-map', str(file), '/' + name, '-chown', '0', '/' + name, '--', '-chgrp', '0', '/' + name, '--',
                         '-chmod', '0444', '/' + name, '--', '-alter_date', 'm', '=' + str(EPOCH), '/' + name, '--']
        commands += ['-chown', '0', '/casper/devlite-provenance', '--', '-chgrp', '0', '/casper/devlite-provenance', '--',
                     '-chmod', '0755', '/casper/devlite-provenance', '--', '-alter_date', 'm', '=' + str(EPOCH), '/casper/devlite-provenance', '--',
                     '-assess_indev_features', 'replay', '-boot_image', 'any', 'replay',
                     '-volid', 'DevLite OS 1.0 Experimental', '-volume_date', 'uuid', pvd_metadata(source)['timestamp'], '-end']
        runner.xorriso('assemble-customized-iso', *commands)
        result_boot = detect(runner, candidate, 'result')
        compare_boot_metadata(source, candidate, original_boot, result_boot)
        if result_boot['timestamp'] != original_boot['timestamp'] or result_boot['volume_id'] != 'DevLite OS 1.0 Experimental':
            raise BuildError('UUID/data de volume ou rótulo experimental incorreto')
        if region_digest(source, original_boot['efi_offset'], original_boot['efi_bytes']) != region_digest(candidate, result_boot['efi_offset'], result_boot['efi_bytes']):
            raise BuildError('EFI anexada mudou')
        source_tree = workspace / 'source-iso-tree'; result_tree = workspace / 'result-iso-tree'
        for image, target, label in ((source, source_tree, 'source'), (candidate, result_tree, 'result')):
            runner.xorriso(label + '-extract-tree', '-osirrox', 'on', '-indev', image, '-extract', '/', target)
        print('Comparação de todos os arquivos ISO...', flush=True)
        before, after = inventory(source_tree), inventory(result_tree)
        added = set(provenance) | {'casper/devlite-provenance', 'casper/devlite-customization.json'}
        changed = set(mapped)
        compare_iso_trees(before, after, source_tree, result_tree, changed, added, {'casper/SHA256SUMS.gpg'})
        for name, file in {**mapped, **provenance}.items():
            if digest(result_tree / name) != digest(file):
                raise BuildError('Payload mapeado divergiu: ' + name)
        old_meta = iso_metadata(runner.xorriso('source-metadata', '-indev', source, '-find', '/', '-exec', 'lsdl', '--'))
        new_meta = iso_metadata(runner.xorriso('result-metadata', '-indev', candidate, '-find', '/', '-exec', 'lsdl', '--'))
        for name in old_meta.keys() & new_meta.keys():
            if name.lstrip('/') not in changed | added | {'boot.catalog'} and old_meta[name] != new_meta[name]:
                raise BuildError('Metadados ISO inesperados: ' + name)
        for name in set(mapped) | set(provenance):
            values = new_meta['/' + name]
            if values[2:4] != ['0', '0'] or values[0] != '-r--r--r--':
                raise BuildError('Permissões/ownership de payload ISO incorretos')
        report['md5_entries'] = verify_manifest(result_tree, Path('md5sum.txt'), 'md5')
        report['layer_sha256_entries'] = verify_manifest(result_tree, Path('casper/SHA256SUMS'), 'sha256')
        runner.run('verify-upstream-provenance', ['gpgv', '--homedir', str(root / 'sources/verification'),
                   '--keyring', str(root / 'sources/verification/trustedkeys.gpg'),
                   str(result_tree / 'casper/devlite-provenance/original-SHA256SUMS.gpg'),
                   str(result_tree / 'casper/devlite-provenance/original-SHA256SUMS')])
        report['sha256'] = digest(candidate)
        if digest(source) != EXPECTED:
            raise BuildError('A ISO original mudou')
        baseline = Path(json.loads((root / 'docs/evidencias/reconstrucao-experimental.json').read_text())['saida'])
        if baseline.resolve().parent.parent != (root / 'artifacts').resolve() or digest(baseline) != BASELINE_HASH:
            raise BuildError('A reconstrução 3B não confere')
        final = output_dir / 'devlite-os-1.0-basic-experimental.iso'
        if final.exists():
            raise BuildError('Não sobrescrever saída')
        candidate.rename(final)
        report.update(status='validado_estruturalmente', iso=str(final), bytes=final.stat().st_size,
                      layers=verified, original_preserved=True, baseline_3b_preserved=True,
                      free_after=shutil.disk_usage(root).free, grub_entries_updated=grub_entries,
                      unsigned_customized_checksums=True)
        (output_dir / 'SHA256SUMS').write_text(report['sha256'] + '  ' + final.name + '\n')
        (output_dir / 'customization-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print('ISO PERSONALIZADA:', final, flush=True)
    except BaseException as error:
        report.update(status='falhou', error=str(error))
        raise
    finally:
        report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    return report
