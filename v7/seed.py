"""Validate v7 release seeds with snapd before allowing image assembly."""
import argparse
import hashlib
from pathlib import Path
import re
import subprocess

import yaml

FIREFOX_ID = '3wdHCAVyZEmYsCMFDE9qt92UV8rC8Wdk'
BROWSER = {'firefox', 'core26', 'bare', 'gnome-core26', 'mesa-2604', 'gtk-common-themes', 'snapd'}


LOCAL_SHA256 = '1a63e51a94b2ca522b03f98e56624a232f9f7c4b24fcc182a585185ef4b11c89'
LOCAL_NAME = 'devlite-installer'
LOCAL_ENTRY = {'name': LOCAL_NAME, 'file': LOCAL_NAME + '.snap',
               'classic': True, 'unasserted': True}


def read_seed(directory, installer=None, *, local=False):
    if local and installer != LOCAL_NAME:
        raise ValueError("Local mode requires the DevLite Live installer")
    if directory.resolve() != directory or not directory.is_dir():
        raise ValueError('Seed path must be an absolute real directory')
    settings = directory / 'seed.yaml'
    for item in directory.rglob('*'):
        if item.is_symlink() or not (item.is_file() or item.is_dir()):
            raise ValueError(f'Unexpected seed path: {item}')
    data = yaml.safe_load(settings.read_text())
    entries = {}
    for snap in data['snaps']:
        name = snap['name']
        if local and name == LOCAL_NAME:
            if name in entries or snap != LOCAL_ENTRY:
                raise ValueError('Unexpected local installer seed entry')
            with (directory / 'snaps' / LOCAL_ENTRY['file']).open('rb') as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != LOCAL_SHA256:
                    raise ValueError('Local installer SHA-256 mismatch')
            entries[name] = snap
            continue
        if name in entries or not snap.get('snap-id') or snap.get('devmode') or snap.get('unasserted'):
            raise ValueError(f'Duplicate or unasserted snap: {name}')
        filename = snap['file']
        if not re.fullmatch(re.escape(name) + r'_[0-9]+\.snap', filename):
            raise ValueError(f'Expected an asserted numeric revision: {filename}')
        if not (directory / 'snaps' / filename).is_file():
            raise ValueError(f'Missing snap: {filename}')
        entries[name] = snap
    expected = BROWSER if not installer else BROWSER | {'core22', installer}
    if set(entries) != expected:
        raise ValueError(f'Unexpected snap set: {sorted(set(entries) ^ expected)}')
    if {item.name for item in (directory / 'snaps').iterdir()} != {
            item['file'] for item in entries.values()}:
        raise ValueError('Unexpected files in seed snaps directory')
    if any(snap.get('classic') for name, snap in entries.items() if name != installer):
        raise ValueError('Expected official confined seed snaps')
    if entries['firefox']['snap-id'] != FIREFOX_ID or entries['firefox'].get('classic'):
        raise ValueError('Expected the official confined Firefox snap')
    if installer and installer == 'ubuntu-desktop-bootstrap':
        raise ValueError('The official installer is a recovery reference, not the v7 candidate')
    return settings, entries


def validate(directory, installer=None, *, local=False):
    settings, _ = read_seed(directory, installer, local=local)
    subprocess.run(['/usr/bin/snap', 'debug', 'validate-seed', str(settings)],
                   check=True, timeout=180)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('seed', type=Path)
    parser.add_argument('--installer', help='Snap Store name approved for the v7 frontend')
    parser.add_argument('--local', action='store_true')
    args = parser.parse_args()
    validate(args.seed, args.installer, local=args.local)
