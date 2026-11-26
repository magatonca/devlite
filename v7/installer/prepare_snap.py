"""Prepare a distinct DevLite Snapcraft project from pinned release inputs."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

import yaml

from pipeline.devlite.structure import digest
from v6.storage import GIB, ROOT, require_space

INPUTS = json.loads(Path(__file__).with_name('inputs.json').read_text())
NAME = INPUTS['candidate_name']


def extract(official, path):
    return subprocess.check_output(['/usr/bin/unsquashfs', '-cat', official, path], timeout=60)


def recipe(official):
    config = yaml.safe_load(extract(official, 'snap/snapcraft.yaml'))
    if config['name'] != INPUTS['official_reference']['name'] or config['base'] != 'core22':
        raise ValueError('Unexpected installer recipe')
    # Snapcraft versions differ in the classic runtime environment they emit.
    # Preserve the official search path for libraries loaded at runtime by GLVND/GTK.
    official_meta = yaml.safe_load(extract(official, 'meta/snap.yaml'))
    config['environment'] = {**config.get('environment', {}), **official_meta['environment']}
    config['name'] = NAME
    config['title'] = 'Instalador DevLite OS'
    config['summary'] = 'Instalador DevLite OS 1.0'
    config['description'] = 'Frontend DevLite baseado no Ubuntu Desktop Bootstrap, com Subiquity e Curtin.'
    config.pop('adopt-info')
    config['version'] = '1.0-v7'
    config['architectures'] = [{'build-on': 'amd64'}]
    config['apps'][NAME] = config['apps'].pop(INPUTS['official_reference']['name'])
    config['apps'][NAME]['desktop'] = f'usr/share/applications/{NAME}.desktop'
    parts = config['parts']
    parts.pop('flutter-git')
    parts.pop('version')
    if parts['curtin']['source-commit'] != INPUTS['curtin_commit']:
        raise ValueError('Unexpected Curtin revision')
    bootstrap = parts['ubuntu-bootstrap']
    bootstrap.pop('after')
    bootstrap['source'] = 'payload'
    bootstrap.pop('source-type')
    if bootstrap.pop('source-commit') != INPUTS['source_commit']:
        raise ValueError('Unexpected frontend upstream revision')
    bootstrap['override-build'] = '''set -eu
mkdir -p "$CRAFT_PART_INSTALL/bin"
cp -a bundle/. "$CRAFT_PART_INSTALL/bin/"
cp -a subiquity "$CRAFT_PART_INSTALL/bin/"
'''
    launcher = parts['launcher']
    launcher.pop('source-type')
    launcher['override-build'] = launcher['override-build'].replace(
        'ubuntu-desktop-bootstrap.desktop', f'{NAME}.desktop')
    return config


def prepare(official, bundle, subiquity, output):
    if digest(official) != INPUTS['official_reference']['sha256']:
        raise ValueError('Unexpected official reference digest')
    if subprocess.check_output(['git', '-C', subiquity, 'rev-parse', 'HEAD'],
                               text=True).strip() != INPUTS['subiquity_commit']:
        raise ValueError('Unexpected Subiquity revision')
    if subprocess.check_output(['git', '-C', subiquity, 'status', '--porcelain'], text=True):
        raise ValueError('Subiquity checkout has local changes')
    for item in bundle.rglob('*'):
        if item.is_symlink() or not (item.is_file() or item.is_dir()):
            raise ValueError(f'Unexpected frontend bundle entry: {item}')
    if not (bundle / 'ubuntu_bootstrap').is_file() or not (bundle / 'lib/libapp.so').is_file():
        raise ValueError('Incomplete Flutter bundle')
    require_space(output.parent, 2 * GIB)
    output.mkdir(mode=0o700)
    shutil.copytree(bundle, output / 'payload/bundle')
    shutil.copytree(subiquity, output / 'payload/subiquity', ignore=shutil.ignore_patterns('.git'),
                    symlinks=True)
    local = output / 'snap/local'
    local.mkdir(parents=True)
    config = recipe(official)
    (output / 'snap/snapcraft.yaml').write_text(yaml.safe_dump(config, sort_keys=False))
    for name in ('launcher', 'subiquity-server'):
        target = local / name
        payload = extract(official, f'bin/{name}')
        if name == 'launcher':
            command = b'sudo systemctl start udisks2-inhibit.service\n'
            if payload.count(command) != 1:
                raise ValueError('Unexpected canonical automount launcher')
            payload = payload.replace(command, command.rstrip() + b' || exit "$?"\n')
        target.write_bytes(payload)
        target.chmod(0o755)
    desktop = extract(official, 'usr/share/applications/ubuntu-desktop-bootstrap.desktop').decode()
    desktop = desktop.replace('Name=Install RELEASE', 'Name=Instalar DevLite OS 1.0')
    desktop = desktop.replace('Exec=ubuntu-desktop-bootstrap', f'Exec={NAME}')
    desktop = desktop.replace('Icon=ubiquity', 'Icon=${SNAP}/meta/gui/icon.svg\nNoDisplay=true')
    gui = output / 'snap/gui'
    gui.mkdir()
    shutil.copyfile(ROOT / 'assets/branding/devlite.svg', gui / 'icon.svg')
    (local / f'{NAME}.desktop').write_text(desktop)
    hooks = local / 'postinst.d'
    hooks.mkdir()
    listing = subprocess.check_output(['/usr/bin/unsquashfs', '-ls', official,
                                      'etc/subiquity/postinst.d'], text=True, timeout=60)
    prefix = 'squashfs-root/etc/subiquity/postinst.d/'
    for line in listing.splitlines():
        if line.startswith(prefix):
            name = line.removeprefix(prefix)
            if not name or name in ('.', '..') or '/' in name:
                raise ValueError(f'Unexpected post-install hook entry: {name}')
            (hooks / name).write_bytes(extract(official, f'etc/subiquity/postinst.d/{name}'))
            (hooks / name).chmod(0o755)
    (output / 'SHA256SUMS').write_text(''.join(
        f'{digest(p)}  {p.relative_to(output)}\n'
        for p in sorted(output.rglob('*')) if p.is_file() and not p.is_symlink()))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('official', 'bundle', 'subiquity', 'output'):
        parser.add_argument(name, type=Path)
    parser.add_argument('--core-lib', required=True, type=Path)
    parser.add_argument('--official-lib', required=True, type=Path)
    args = parser.parse_args()
    subprocess.run([sys.executable, Path(__file__).with_name('check-bundle.py'),
                    args.bundle, args.core_lib, args.official_lib], check=True, timeout=300)
    prepare(args.official, args.bundle, args.subiquity, args.output)
