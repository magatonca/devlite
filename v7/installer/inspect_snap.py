"""Inspect a DevLite installer Snap without mounting or running its contents."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory

import yaml


def command(*args):
    return subprocess.check_output(args, timeout=180, text=True)


def inspect(snap):
    def read(path):
        return command('unsquashfs', '-cat', str(snap), path)

    meta = yaml.safe_load(read('meta/snap.yaml'))
    if (meta.get('name'), meta.get('base'), meta.get('confinement')) != (
            'devlite-installer', 'core22', 'classic'):
        raise ValueError('Unexpected Snap identity, base or confinement')
    if meta.get('architectures') != ['amd64']:
        raise ValueError('Expected amd64')
    apps = meta['apps']
    frontend = apps['devlite-installer']
    backend = apps['subiquity-server']
    if (frontend.get('command') != 'bin/ubuntu_bootstrap'
            or frontend.get('command-chain') != ['bin/launcher']
            or backend.get('command') != 'bin/subiquity-server'
            or backend.get('daemon') != 'simple'
            or backend.get('restart-condition') != 'always'):
        raise ValueError('Unexpected installer or backend entry points')

    lines = command('unsquashfs', '-ll', str(snap)).splitlines()
    paths = {}
    for line in lines:
        fields = line.split(maxsplit=5)
        if len(fields) == 6 and fields[5].startswith('squashfs-root/'):
            paths[fields[5].removeprefix('squashfs-root/').split(' -> ', 1)[0]] = fields[:2]
    for path, executable in {
        'bin/ubuntu_bootstrap': True,
        'bin/launcher': True,
        'bin/subiquity-server': True,
        'bin/lib/libapp.so': False,
        'bin/subiquity/subiquity/cmd/server.py': False,
        'meta/snap.yaml': False,
        'snap/manifest.yaml': False,
    }.items():
        mode, owner = paths.get(path, ('', ''))
        if not mode.startswith('-') or owner != 'root/root' or mode[5] == 'w' or mode[8] == 'w':
            raise ValueError(f'Missing or untrusted file: {path}')
        if executable and mode[3] != 'x':
            raise ValueError(f'Missing executable bit: {path}')
    if not any(re.fullmatch(r'lib/python[^/]+/site-packages/curtin/__init__\.py', name)
               for name in paths):
        raise ValueError('Curtin package missing')
    manifest = yaml.safe_load(read('snap/manifest.yaml'))
    if not isinstance(manifest, dict) or not manifest.get('parts', {}).get('curtin'):
        raise ValueError('Missing Snapcraft build provenance for Curtin')
    dependencies = {}
    with TemporaryDirectory(prefix='devlite-snap-elf-') as temporary:
        extracted = Path(temporary) / 'elf'
        for name in sorted(paths):
            if (name != 'bin/ubuntu_bootstrap' and
                    not (name.startswith('bin/lib/') and name.endswith('.so'))):
                continue
            with extracted.open('wb') as stream:
                subprocess.run(['unsquashfs', '-cat', str(snap), name],
                               stdout=stream, check=True, timeout=120)
            info = command('readelf', '-dW', str(extracted))
            dependencies[name] = re.findall(r'Shared library: \[([^\]]+)\]', info)
    with snap.open('rb') as stream:
        fingerprint = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'name': meta['name'], 'version': meta['version'], 'sha256': fingerprint,
            'bytes': snap.stat().st_size, 'files': len(paths),
            'native_dependencies': dependencies, 'snapcraft_manifest': manifest}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snap', type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.snap), indent=2, default=str))
