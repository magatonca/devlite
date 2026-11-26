"""Admission checks for administrator-staged v7 release inputs."""
import json
from pathlib import Path
import stat

from pipeline.devlite.structure import digest
from v7 import seed

INPUTS = Path('/etc/devlite-v7')
INSTALLER = 'devlite-installer'
LOCAL_CHECKS = {'abi', 'worker_review', 'automated_tests'}
LOCAL_ACK = {'purpose': 'personal-homologation-candidate',
             'distribution_approved': False, 'runtime_validation': 'pending'}
REQUIRED_CHECKS = {'abi', 'backend_socket', 'backend_authorization', 'backend_lifecycle',
                   'curtin', 'automount', 'worker_review', 'automated_tests'}


def trusted(path):
    info = path.lstat()
    if info.st_uid != 0 or info.st_mode & 0o7022 or not (
            stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
        raise ValueError(f'Untrusted release input: {path}')
    if stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
        raise ValueError(f'Hard-linked release input: {path}')


def inputs(worker_sha256):
    if not INPUTS.exists():
        raise ValueError(f'Provisionamento administrativo ausente em {INPUTS}; consulte docs/v7/instalador-local.md')
    trusted(INPUTS)
    receipt = INPUTS / 'release.json'
    trusted(receipt)
    record = json.loads(receipt.read_text())
    mode = record.get('installer_mode', 'store')
    if mode not in ('local', 'store'):
        raise ValueError('Unknown installer approval mode')
    local = mode == 'local'
    if local and (set(record) != {'installer_mode', 'installer_sha256', 'authorization',
                                 'validated', 'worker_sha256'}
                  or record.get('authorization') != LOCAL_ACK
                  or record.get('installer_sha256') != seed.LOCAL_SHA256):
        raise ValueError('Invalid local candidate authorization')
    if set(record.get('validated', {})) != (LOCAL_CHECKS if local else REQUIRED_CHECKS) or any(
            value is not True for value in record['validated'].values()):
        raise ValueError('Incomplete installer and worker validation receipt')
    if record.get('worker_sha256') != worker_sha256:
        raise ValueError('Worker source does not match the reviewed release')
    base, live = INPUTS / 'base-seed', INPUTS / 'live-seed'
    for directory in (base, live):
        trusted(directory)
        for path in directory.rglob('*'):
            trusted(path)
    seed.validate(base)
    seed.validate(live, INSTALLER, local=local)
    if not local:
        _, entries = seed.read_seed(live, INSTALLER)
        entry = entries[INSTALLER]
        if (entry['snap-id'] != record.get('installer_snap_id')
                or entry.get('classic') is not True
                or digest(live / 'snaps' / entry['file']) != record.get('installer_sha256')):
            raise ValueError('Installer does not match the approved revision or confinement')
    return base, live, INSTALLER, mode


if __name__ == '__main__':
    raise SystemExit('Use the administrative bootstrap or the unprivileged preflight.')
