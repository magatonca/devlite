"""Manual v7 worker. It runs as PID 1 of the job namespace."""
from contextlib import contextmanager
import ctypes
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import tempfile
from pathlib import Path

from pipeline.devlite.customize.executor_worker import restrict_caps, service_guard
from pipeline.devlite.customize.installation import installed
from pipeline.devlite.customize.isolation_validation import cgroup_limits, critical_files, loop_backings
from pipeline.devlite.minimal_root import EPOCH, snapshot
from pipeline.devlite.release_layers import full_manifest, materialize, recipe
from pipeline.devlite.release_pack import compress_args
from pipeline.devlite.release_resume import absent_xattrs, checked_snapshot
from pipeline.devlite.runtime import Runner
from pipeline.devlite.structure import digest
from v5.execution import LIMITS
from v5.image import confined, finalize
from v5.layers import layer_absence, visible_absence
from v6.pack import LEAVES as V6_LEAVES, STACKS as V6_STACKS
from v6.pack import Mounts, prepare_upper_root, protect_namespace, write_json
from v6.storage import GIB, require_space
from v7 import layers, live_installer, release_gate, seed
from v7.admin_bootstrap import ADMIN, SOURCE_SHA
from v7.storage import budgets

SOURCE = ADMIN / 'source-v6.iso'

STATE = Path('/var/lib/devlite-v7')
STACKS = {target: (*stack, V6_LEAVES[target]) for target, stack in V6_STACKS.items()}
LEAVES = {target: stack[-1].removesuffix('.squashfs') + '.v7.squashfs'
          for target, stack in STACKS.items()}


def verify_context():
    if os.geteuid() != 0 or os.getpid() != 1:
        raise ValueError('Executor requires root as PID 1 of the private namespace')
    group = Path('/proc/self/cgroup').read_text()
    if not re.search(r'/devlite-v7-pack\.service$', group, re.M):
        raise ValueError('Executor requires the dedicated systemd service')
    real_group = group.strip().split('::', 1)[1]
    cgroup_limits(Path('/sys/fs/cgroup') / real_group.lstrip('/'), LIMITS)
    if 'NoNewPrivs:\t1' not in Path('/proc/self/status').read_text():
        raise ValueError('NoNewPrivileges is required')
    info = STATE.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        raise ValueError('Unsafe state directory')
    if STATE.stat().st_dev != SOURCE.stat().st_dev:
        raise ValueError('Pack and ISO must share the monitored filesystem')
    if ctypes.CDLL(None, use_errno=True).prctl(4, 0, 0, 0, 0):
        raise OSError('Cannot protect the supervisor')
    os.umask(0o077)


def layer_hashes(runner):
    path = runner.logs.parent / 'source-checksums'
    runner.xorriso('source-checksums', '-osirrox', 'on', '-indev', SOURCE,
                   '-extract', '/casper/SHA256SUMS', path)
    hashes = {}
    for line in path.read_text().splitlines():
        checksum, name = line.split()
        name = name.removeprefix('*')
        if name in hashes or not re.fullmatch('[a-f0-9]{64}', checksum):
            raise ValueError('Invalid inherited layer manifest')
        hashes[name] = checksum
    if hashes.keys() != {name for stack in STACKS.values() for name in stack}:
        raise ValueError('Unexpected inherited layer layout')
    return hashes


@contextmanager
def guest_devices(mounts, root):
    start = len(mounts.paths)
    try:
        for name in ('run', 'tmp', 'var/tmp', 'dev', 'sys'):
            options = 'nosuid,noexec,mode=0755,size=128m'
            if name != 'dev':
                options += ',nodev'
            path = confined(root, name)
            mounts.mount('guest-' + name, ['-t', 'tmpfs', '-o', options, 'tmpfs'], path)
            if name in ('tmp', 'var/tmp'):
                path.chmod(0o1777)
        for name, minor in (('null', 3), ('zero', 5), ('random', 8), ('urandom', 9)):
            path = root / 'dev' / name
            os.mknod(path, stat.S_IFCHR | 0o666, os.makedev(1, minor))
            path.chmod(0o666)
        mounts.mount('guest-proc', ['-t', 'proc', '-o', 'ro,nosuid,nodev,noexec', 'proc'],
                     root / 'proc')
        lock_link = confined(root, 'var/lock')
        # Do not resolve an absolute guest symlink in the host filesystem.
        if not lock_link.is_symlink() or os.readlink(lock_link) not in ('/run/lock', '../run/lock'):
            raise ValueError('Expected guest /var/lock to point to /run/lock')
        for name, mode in (('lock', 0o1777), ('apache2', 0o755)):
            directory = root / 'run' / name
            directory.mkdir()
            os.chown(directory, 0, 0)
            directory.chmod(mode)
        yield
    finally:
        while len(mounts.paths) > start:
            mounts.unmount(mounts.paths[-1])


def guest(runner, root, args):
    def enter():
        os.chroot(root)
        os.chdir('/')
        restrict_caps()

    # The guest has private runtime mounts and no host sockets.
    with tempfile.TemporaryFile() as output:
        with subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=output,
                              stderr=subprocess.STDOUT, start_new_session=True,
                              env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LC_ALL': 'C',
                                   'DEBIAN_FRONTEND': 'noninteractive', 'HOME': '/root',
                                   'SYSTEMD_OFFLINE': '1', 'NEEDRESTART_MODE': 'l'},
                              preexec_fn=enter) as process:
            try:
                for _ in range(180):
                    try:
                        status = process.wait(timeout=1)
                        break
                    except subprocess.TimeoutExpired:
                        require_space(root, 512 * 1024**2)
                else:
                    raise TimeoutError('Guest command exceeded its deadline')
            finally:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        output.seek(0)
        text = output.read().decode(errors='replace')
    with (runner.logs / 'guest.log').open('a') as log:
        log.write(repr(args) + '\n' + text)
    if status:
        raise ValueError(f'Guest command failed ({status}): {args[0]}')
    return text


def apply_guest(mounts, root, target, directory, installer, mode):
    if target not in STACKS or root != mounts.job / target / 'root':
        raise ValueError('Unapproved guest root')
    with guest_devices(mounts, root), service_guard(root):
        def run(args):
            return guest(mounts.runner, root, args)

        if target == 'live':
            live_installer.reset(root, run)
        layers.apply(root, target, directory, run,
                     installer=installer if target == 'live' else None,
                     local=mode == 'local' and target == 'live')
        run(['/usr/bin/apt-get', '-o', 'DPkg::Use-Pty=0', '-s', 'check'])
        if run(['/usr/bin/dpkg', '--audit']).strip():
            raise ValueError('Incomplete package database')


def cleanup_barrier(mounts, job):
    errors = mounts.cleanup()
    prefix = str(job) + '/'
    for line in Path('/proc/self/mountinfo').read_text().splitlines():
        target = line.split()[4]
        if target == str(job) or target.startswith(prefix):
            errors.append(f'Job mount remains: {target}')
    for device, backing in loop_backings().items():
        if not isinstance(backing, str) or backing.startswith(prefix):
            errors.append(f'Loop device not cleared or unverifiable: {device}')
    return errors


def finish_pack(job, report, mounts):
    try:
        errors = cleanup_barrier(mounts, job)
    except Exception as error:
        errors = [f'Cleanup could not be verified: {error}']
    report['cleanup_errors'] = errors
    if errors or 'error' in report:
        write_json(job / 'audit.json', report)
        if errors:
            raise ValueError('Pack quarantined due to cleanup failure')
        return

    pending = job / 'publication.pending'
    report['status'] = 'v7_layers_verified'
    write_json(pending / 'pack.json', report)
    (pending / 'pack.json').chmod(0o444)
    write_json(job / 'audit.json', report)
    pending.chmod(0o755)
    published = job / 'published'
    pending.rename(published)
    job.chmod(0o711)
    print(f'Pack verificado: {published}', flush=True)


def pack(worker_sha256):
    if Path(__file__).resolve().parents[1] != ADMIN / 'worker' / worker_sha256 / 'code':
        raise ValueError('Worker is outside the approved administrative snapshot')
    verify_context()
    base_seed, live_seed, installer, mode = release_gate.inputs(worker_sha256)
    require_space(STATE, budgets(SOURCE.stat().st_size)['iso'])
    job = Path(tempfile.mkdtemp(prefix='pack-', dir=STATE))
    print(f'Job: {job}', flush=True)
    (job / 'logs').mkdir()
    runner = Runner(job / 'logs', EPOCH)
    runner.env['PATH'] = '/usr/sbin:/usr/bin:/sbin:/bin'
    runner.env.pop('SOURCE_DATE_EPOCH', None)
    mounts = Mounts(job, runner)
    report = {'status': 'quarantined', 'source_sha256': SOURCE_SHA, 'installer_mode': mode, 'worker_sha256': worker_sha256, 'targets': {}}
    if mode == 'local':
        report['installer_sha256'] = seed.LOCAL_SHA256
    host = critical_files()
    try:
        protect_namespace(runner)
        hashes = layer_hashes(runner)
        lowers, records = {}, {}
        for name, expected in sorted(hashes.items()):
            require_space(job, SOURCE.stat().st_size)
            image = job / name
            runner.xorriso('extract-layer', '-osirrox', 'on', '-indev', SOURCE,
                           '-extract', '/casper/' + name, image)
            if digest(image) != expected:
                raise ValueError(f'Source layer changed: {name}')
            lower = job / ('lower-' + name)
            lower.mkdir()
            mounts.mount('mount-layer', ['-t', 'squashfs', '-o', 'loop,ro,nodev,nosuid', str(image)], lower)
            lowers[name] = lower
            records[name] = layer_absence(image, lower)

        for target, stack in STACKS.items():
            stage = job / target
            stage.mkdir()
            for name in ('before', 'root', 'upper', 'work', 'verify', 'composed'):
                (stage / name).mkdir()
            root, before_root = stage / 'root', stage / 'before'
            lowerdirs = ':'.join(str(lowers[name]) for name in reversed(stack))
            readonly = 'ro,nodev,nosuid,lowerdir=' + lowerdirs
            mounts.mount('reference-' + target, ['-t', 'overlay', '-o', readonly, 'overlay'], before_root)
            prepare_upper_root(before_root, stage / 'upper')
            options = (f'nodev,nosuid,lowerdir={lowerdirs},upperdir={stage / "upper"},'
                       f'workdir={stage / "work"},index=off,metacopy=off,redirect_dir=off,xino=off')
            mounts.mount('cow-' + target, ['-t', 'overlay', '-o', options, 'overlay'], root)
            if stat.S_IMODE(root.stat().st_mode) != stat.S_IMODE(before_root.stat().st_mode):
                raise ValueError('Overlay root permissions differ from the reference')
            baseline = snapshot(before_root, xattr_absence=visible_absence(stack, records))
            before_packages = installed((before_root / 'var/lib/dpkg/status').read_text())
            directory = base_seed if target == 'base' else live_seed
            apply_guest(mounts, root, target, directory, installer, mode)
            policy = finalize(root)
            current = installed((root / 'var/lib/dpkg/status').read_text())
            if current != {key: val for key, val in before_packages.items() if key not in layers.REMOVED}:
                raise ValueError('Unexpected installed package changes')
            if list((root / 'etc/ssh').glob('ssh_host_*_key')):
                raise ValueError('Factory SSH private keys remain')
            after = snapshot(root, xattr_absence=visible_absence(stack, records, (stage / 'upper',)))
            changes = recipe(baseline, after)
            snap_prefix = 'var/lib/snapd/snaps/'
            inherited = {'ubuntu-desktop-bootstrap_572.snap', 'core22_2437.snap', 'snapd_27738.snap'}
            if any(name.startswith(snap_prefix) for name in changes['put']):
                raise ValueError('Unexpected installed Snap payload outside the seed')
            for name in changes['whiteouts']:
                if name.startswith(snap_prefix) and (
                        target != 'live' or name.removeprefix(snap_prefix) not in inherited):
                    raise ValueError('Unexpected removed installed Snap payload')
            logical = sum(item.get('size', 0) for item in changes['put'].values())
            if logical > 2 * GIB:
                raise ValueError('Incremental delta exceeds two GiB')
            require_space(job, 3 * logical + GIB)
            write_json(stage / 'recipe.json', changes)
            delta = stage / 'delta'
            expected = materialize(root, delta, changes, EPOCH)
            image = stage / LEAVES[target]
            runner.run('compress-' + target, compress_args(delta, image, expected['.']))
            leaf = stage / 'verify'
            mounts.mount('verify-leaf', ['-t', 'squashfs', '-o', 'loop,ro,nodev,nosuid', str(image)], leaf)
            checked_snapshot(leaf, expected, target, absent_xattrs(image, expected))
            composed = stage / 'composed'
            mounts.mount('verify-composed', ['-t', 'overlay', '-o',
                         f'ro,nodev,nosuid,lowerdir={leaf}:{lowerdirs}', 'overlay'], composed)
            missing, names = layer_absence(image, leaf)
            absent = (set(visible_absence(stack, records)) - names) | missing
            checked_snapshot(composed, after, target + '-composition', frozenset(absent))
            for path in (composed, leaf, root, before_root):
                mounts.unmount(path)
            manifest = stage / 'packages.manifest'
            manifest.write_text(full_manifest(current))
            allocated = int(runner.run('delta-size', ['/usr/bin/du', '-sx', '-B1', str(delta)]).split()[0])
            report['targets'][target] = {
                'image': image.name, 'sha256': digest(image), 'bytes': image.stat().st_size,
                'manifest_sha256': digest(manifest), 'allocated_bytes': allocated,
                'composition_verified': True, 'offline_service_policy': policy,
            }
            del baseline, after, expected, changes

        while mounts.paths:
            mounts.unmount(mounts.paths[-1])
        if critical_files() != host:
            raise ValueError('Host critical state changed')
        require_space(job, GIB)
        pending = job / 'publication.pending'
        pending.mkdir(mode=0o700)
        for target, item in report['targets'].items():
            for filename in (item['image'], 'packages.manifest'):
                destination = pending / (target + '.manifest' if filename == 'packages.manifest' else filename)
                shutil.copyfile(job / target / filename, destination)
                destination.chmod(0o444)
        report['host_critical_files_unchanged'] = True
    except BaseException as error:
        report['error'] = str(error)
        raise
    finally:
        finish_pack(job, report, mounts)


if __name__ == '__main__':
    raise SystemExit('Use the installed administrative bootstrap.')
