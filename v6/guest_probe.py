"""Exercise guest checks on a disposable copy of an interrupted Base overlay."""
import json
import re
import stat
import subprocess
import tempfile
from pathlib import Path

from pipeline.devlite.customize.isolation_validation import loop_backings
from pipeline.devlite.minimal_root import EPOCH
from pipeline.devlite.runtime import Runner
from v6.pack import (SOURCE_SHA, STACKS, STATE, Mounts, install_guest,
                     prepare_upper_root, protect_namespace, verify_context, write_json)
from v6.storage import GIB, require_space


def trusted(path, kind):
    if path.resolve() != path:
        raise ValueError(f'Symlink in probe input: {path}')
    info = path.lstat()
    if not kind(info.st_mode) or (info.st_uid, info.st_gid) != (0, 0) or info.st_mode & 0o022:
        raise ValueError(f'Untrusted probe input: {path}')
    return info


def probe_inputs(attempt):
    if not re.fullmatch(r'pack-[a-z0-9_]{8}', attempt):
        raise ValueError('Expected a pack ID directly below the v6 state directory')
    previous = STATE / attempt
    upper = previous / 'base/upper'
    for directory in (previous, upper.parent, upper):
        trusted(directory, stat.S_ISDIR)
    receipt = previous / 'audit.json'
    trusted(receipt, stat.S_ISREG)
    audit = json.loads(receipt.read_text())
    if (audit.get('status') != 'quarantined' or audit.get('cleanup_errors') != []
            or audit.get('source_sha256') != SOURCE_SHA
            or not audit.get('error', '').startswith('Guest failed (')):
        raise ValueError('Expected an interrupted guest with a clean audit receipt')
    images = [previous / name for name in STACKS['base']]
    for image in images:
        trusted(image, stat.S_ISREG)
    if any(isinstance(backing, str) and backing.startswith(str(previous) + '/')
           for backing in loop_backings().values()):
        raise ValueError('An earlier pack loop device is still attached')
    return upper, images


def probe(attempt):
    verify_context()
    previous_upper, images = probe_inputs(attempt)
    previous_mode = stat.S_IMODE(previous_upper.stat().st_mode)
    size = int(subprocess.check_output(
        ['/usr/bin/du', '-sx', '-B1', str(previous_upper)], text=True).split()[0])
    require_space(STATE, size + GIB)
    job = Path(tempfile.mkdtemp(prefix='probe-', dir=STATE))
    (job / 'logs').mkdir()
    runner = Runner(job / 'logs', EPOCH)
    runner.env['PATH'] = '/usr/sbin:/usr/bin:/sbin:/bin'
    mounts = Mounts(job, runner)
    report = {'attempt': attempt, 'status': 'failed', 'previous_upper_mode': oct(previous_mode)}
    print(f'Guest probe: {job}; interrupted upper mode: {previous_mode:04o}', flush=True)
    try:
        protect_namespace(runner)
        lowers = []
        for image in images:
            lower = job / ('lower-' + image.name)
            lower.mkdir()
            mounts.mount('probe-layer', ['-t', 'squashfs', '-o', 'loop,ro,nodev,nosuid', str(image)], lower)
            lowers.append(str(lower))
        lowerdirs = ':'.join(reversed(lowers))
        reference, root, upper, work = (job / name for name in ('reference', 'root', 'upper', 'work'))
        for directory in (reference, root, work):
            directory.mkdir()
        mounts.mount('probe-reference', ['-t', 'overlay', '-o',
                     'ro,nodev,nosuid,lowerdir=' + lowerdirs, 'overlay'], reference)
        runner.run('copy-interrupted-upper', ['/usr/bin/cp', '-a', '--', str(previous_upper), str(upper)])
        prepare_upper_root(reference, upper)
        options = (f'nodev,nosuid,lowerdir={lowerdirs},upperdir={upper},workdir={work},'
                   'index=off,metacopy=off,redirect_dir=off,xino=off')
        mounts.mount('probe-cow', ['-t', 'overlay', '-o', options, 'overlay'], root)
        report['corrected_root_mode'] = oct(stat.S_IMODE(root.stat().st_mode))
        if report['corrected_root_mode'] != '0o755':
            raise ValueError('Probe root permissions differ from the reference')
        print(runner.run('probe-mandb-path', ['/usr/bin/namei', '-l',
                         str(root / 'usr/lib/man-db/libmandb-2.12.0.so')]), flush=True)
        install_guest(root, job, mounts, job, validate_only=True)
        while mounts.paths:
            mounts.unmount(mounts.paths[-1])
        if any(isinstance(backing, str) and backing.startswith(str(STATE / attempt) + '/')
               for backing in loop_backings().values()):
            raise ValueError('Probe loop devices remain attached')
        report['status'] = 'guest_checks_passed'
    except BaseException as error:
        report['error'] = str(error)
        raise
    finally:
        report['cleanup_errors'] = mounts.cleanup()
        if report['cleanup_errors']:
            report['status'] = 'failed'
        write_json(job / 'audit.json', report)
        log = job / 'guest.log'
        if log.exists():
            print(log.read_text(), flush=True)
        print(json.dumps(report), flush=True)
