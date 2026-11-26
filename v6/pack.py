"""Manual v6 worker. It runs as PID 1 of the job namespace."""
import ctypes
import hashlib
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
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
from v5.execution import LIMITS, STACKS as V4_STACKS
from v5.image import confined, finalize
from v5.layers import invalidate_browser_cache, layer_absence, visible_absence
from v6.acquire_curl import VERSION, selected_records, verified_index
from v6.payload import apply
from v6.storage import ROOT, SOURCE, GIB, require_space, stage_budgets

STATE = Path('/var/lib/devlite-v6')
SOURCE_SHA = '2fd9d0e625990bc37b4606354d5dd048f6c369ba63f00256f914a9d168fd9912'
STACKS = {target: (*names, f'{names[-1].removesuffix(".squashfs")}.v5.squashfs')
          for target, names in V4_STACKS.items()}

# Dotted filenames declare the inherited casper layer chain.
LEAVES = {target: stack[-1].removesuffix(".squashfs") + ".v6.squashfs"
          for target, stack in STACKS.items()}


def write_json(path, data):
    with path.open('x') as stream:
        json.dump(data, stream, indent=2, sort_keys=True)
        stream.write('\n')


def verify_context():
    if os.geteuid() != 0 or os.getpid() != 1:
        raise ValueError('Executor requires root as PID 1 of the private namespace')
    group = Path('/proc/self/cgroup').read_text()
    if not re.search(r'/devlite-v6-pack\.service$', group, re.M):
        raise ValueError('Executor requires the dedicated systemd service')
    real_group = group.strip().split('::', 1)[1]
    cgroup_limits(Path('/sys/fs/cgroup') / real_group.lstrip('/'), LIMITS)
    if 'NoNewPrivs:\t1' not in Path('/proc/self/status').read_text():
        raise ValueError('NoNewPrivileges is required')
    info = STATE.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        raise ValueError('Unsafe state directory')
    if STATE.stat().st_dev != ROOT.stat().st_dev:
        raise ValueError('Pack and ISO must share the monitored filesystem')
    if ctypes.CDLL(None, use_errno=True).prctl(4, 0, 0, 0, 0):
        raise OSError('Cannot protect the supervisor')
    os.umask(0o077)


class Mounts:
    def __init__(self, job, runner):
        self.job = job
        self.runner = runner
        self.paths = []

    def mount(self, label, args, path):
        if not path.is_relative_to(self.job) or not path.is_dir() or path.resolve() != path:
            raise ValueError(f'Unapproved mount target: {path}')
        require_space(self.job, 512 * 1024**2)
        self.runner.run(label, ['/usr/bin/mount', *args, str(path)])
        self.paths.append(path)

    def unmount(self, path):
        if not self.paths or self.paths[-1] != path:
            raise ValueError('Mount cleanup order violated')
        self.runner.run('umount-' + path.name, ['/usr/bin/umount', '--', str(path)])
        self.paths.pop()

    def cleanup(self):
        errors = []
        for path in reversed(self.paths):
            try:
                subprocess.run(['/usr/bin/umount', '--', str(path)], check=True, timeout=30)
            except (subprocess.SubprocessError, OSError) as error:
                errors.append(f'{path}: {error}')
        return errors


def copy_curl(runtime):
    records = selected_records(verified_index())
    archive_dir = ROOT / 'work/v6-curl-noble-security'
    (runtime / 'debs').mkdir()
    (runtime / 'debs').chmod(0o755)
    for fields in records.values():
        name = Path(fields['Filename']).name
        source = archive_dir / name
        if source.resolve() != source:
            raise ValueError('Unexpected archive symlink')
        with source.open('rb') as stream:
            size = int(fields['Size'])
            content = stream.read(size + 1)
        if len(content) != size or hashlib.sha256(content).hexdigest() != fields['SHA256']:
            raise ValueError('Archive no longer matches signed Ubuntu index')
        destination = runtime / 'debs' / name
        destination.write_bytes(content)
        destination.chmod(0o644)
    return [{'package': name, 'version': VERSION, 'architecture': 'amd64',
             'filename': fields['Filename']} for name, fields in sorted(records.items())]


def install_guest(root, job, mounts, stage, *, validate_only=False):
    start = len(mounts.paths)
    for name in ('run', 'tmp', 'var/tmp', 'dev', 'sys'):
        path = confined(root, name)
        options = 'nosuid,noexec,mode=0755,size=128m'
        if name != 'dev':
            options += ',nodev'
        mounts.mount('guest-' + name.replace('/', '-'), ['-t', 'tmpfs', '-o', options, 'tmpfs'], path)
        if name in ('tmp', 'var/tmp'):
            path.chmod(0o1777)
    for name, minor in (('null', 3), ('zero', 5), ('random', 8), ('urandom', 9)):
        device = root / 'dev' / name
        os.mknod(device, stat.S_IFCHR | 0o666, os.makedev(1, minor))
        device.chmod(0o666)
    for name, fd in (('fd', 'fd'), ('stdin', 'fd/0'), ('stdout', 'fd/1'), ('stderr', 'fd/2')):
        (root / 'dev' / name).symlink_to('/proc/self/' + fd)
    mounts.mount('guest-proc', ['-t', 'proc', '-o', 'ro,nosuid,nodev,noexec', 'proc'], root / 'proc')
    runtime = root / 'run/devlite-v6'
    runtime.mkdir(mode=0o755)
    runtime.chmod(0o755)
    locked = [] if validate_only else copy_curl(runtime)
    if not validate_only:
        write_json(runtime / 'request.json', locked)
    shutil.copyfile(ROOT / 'v6/guest.py', runtime / 'guest.py')
    reused = (ROOT / 'pipeline/devlite/customize/guest_runner.py').read_text()
    (runtime / 'guest_runner.py').write_text(reused.replace('/run/devlite/apt.conf', '/run/devlite-v6/apt.conf'))
    from v5.worker import APT_CONF
    (runtime / 'apt.conf').write_text(APT_CONF.replace('/run/devlite-v5/', '/run/devlite-v6/'))
    for name in ('empty', 'lists'):
        (runtime / name).mkdir()
    (runtime / 'empty.conf').touch()
    (root / 'run/sshd').mkdir()
    (root / 'run/apache2').mkdir()
    (root / 'run/lock').mkdir(mode=0o1777)
    mounts.runner.run('guest-inputs-ro', ['/usr/bin/mount', '--bind', str(runtime), str(runtime)])
    mounts.paths.append(runtime)
    mounts.runner.run('guest-inputs-remount', ['/usr/bin/mount', '-o', 'remount,bind,ro,nosuid,nodev,noexec', str(runtime)])

    def enter():
        os.chroot(root)
        os.chdir('/')
        restrict_caps()

    command = ['/usr/bin/python3', '-I', '-B', '-c',
               'import runpy,sys; sys.path.insert(0,"/run/devlite-v6"); '
               'runpy.run_path("/run/devlite-v6/guest.py",run_name="__main__")']
    if validate_only:
        command.append('--validate-only')
    with service_guard(root), (stage / 'guest.log').open('x') as log:
        with subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log,
                              stderr=subprocess.STDOUT, start_new_session=True,
                              env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LC_ALL': 'C'},
                              preexec_fn=enter) as child:
            try:
                for _ in range(1200):
                    try:
                        status = child.wait(timeout=1)
                        if status:
                            raise RuntimeError(f'Guest failed ({status}); see {stage}/guest.log')
                        break
                    except subprocess.TimeoutExpired:
                        require_space(job, 512 * 1024**2)
                else:
                    raise TimeoutError('Guest exceeded its execution deadline')
            finally:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
    for path in reversed(mounts.paths[start:]):
        mounts.unmount(path)
    return locked


def layer_hashes(runner):
    if digest(SOURCE) != SOURCE_SHA:
        raise ValueError('Pinned ISO v5 changed')
    path = runner.logs.parent / 'source-checksums'
    runner.xorriso('source-checksums', '-osirrox', 'on', '-indev', SOURCE,
                   '-extract', '/casper/SHA256SUMS', path)
    if digest(path) != '41f9164789bf236ed3f7adb06bcf8a2d21b422ecad4b76fdcca9b1a5359888a6':
        raise ValueError('Pinned checksum manifest changed')
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


def protect_namespace(runner):
    runner.run('private-propagation', ['/usr/bin/mount', '--make-rprivate', '/'])
    for name in ('/proc/sys', '/proc/sysrq-trigger'):
        runner.run('protect-proc', ['/usr/bin/mount', '--bind', name, name])
        runner.run('protect-proc-ro', ['/usr/bin/mount', '-o', 'remount,bind,ro', name])


def prepare_upper_root(reference, upper):
    """Mirror the inherited root directory, while the enclosing job is private."""
    info = reference.lstat()
    mode = stat.S_IMODE(info.st_mode)
    if not stat.S_ISDIR(info.st_mode) or (info.st_uid, info.st_gid) != (0, 0) or mode != 0o755:
        raise ValueError(f'Unexpected inherited root directory: {reference}')
    upper.chmod(mode)


def pack():
    verify_context()
    require_space(STATE, sum(stage_budgets(SOURCE.stat().st_size).values()))
    job = Path(tempfile.mkdtemp(prefix='pack-', dir=STATE))
    print(f'Job: {job}', flush=True)
    (job / 'logs').mkdir()
    runner = Runner(job / 'logs', EPOCH)
    runner.env['PATH'] = '/usr/sbin:/usr/bin:/sbin:/bin'
    runner.env.pop('SOURCE_DATE_EPOCH', None)
    mounts = Mounts(job, runner)
    report = {'status': 'quarantined', 'source_sha256': SOURCE_SHA, 'targets': {}}
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
            apply(root, target)
            invalidate_browser_cache(root)
            locked = install_guest(root, job, mounts, stage)
            policy = finalize(root)
            current = installed((root / 'var/lib/dpkg/status').read_text())
            if current != {**before_packages, **{item['package']: item['version'] for item in locked}}:
                raise ValueError('Unexpected installed package changes')
            if list((root / 'etc/ssh').glob('ssh_host_*_key')):
                raise ValueError('Factory SSH private keys remain')
            after = snapshot(root, xattr_absence=visible_absence(stack, records, (stage / 'upper',)))
            changes = recipe(baseline, after)
            protected = ('var/lib/snapd/snaps/', 'var/lib/snapd/seed/')
            if any(name.startswith(protected) for name in (*changes['put'], *changes['whiteouts'])):
                raise ValueError('Signed installer payload changed')
            logical = sum(item.get('size', 0) for item in changes['put'].values())
            if logical > GIB:
                raise ValueError('Incremental delta exceeds one GiB')
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
        if any(isinstance(backing, str) and backing.startswith(str(job) + '/')
               for backing in loop_backings().values()):
            raise ValueError('Job loop devices remain attached')
        if critical_files() != host:
            raise ValueError('Host critical state changed')
        require_space(job, GIB)
        published = job / 'published'
        published.mkdir(mode=0o755)
        published.chmod(0o755)
        for target, item in report['targets'].items():
            for filename in (item['image'], 'packages.manifest'):
                destination = published / (target + '.manifest' if filename == 'packages.manifest' else filename)
                shutil.copyfile(job / target / filename, destination)
                destination.chmod(0o444)
        report['host_critical_files_unchanged'] = True
        report['status'] = 'v6_layers_verified'
        report['cleanup_errors'] = []
        receipt = published / 'pack.json'
        write_json(receipt, report)
        receipt.chmod(0o444)
        job.chmod(0o711)
        print(f'Pack verificado: {published}', flush=True)
    except BaseException as error:
        report['error'] = str(error)
        raise
    finally:
        errors = mounts.cleanup()
        if errors:
            report['status'] = 'quarantined'
        report['cleanup_errors'] = errors
        write_json(job / 'audit.json', report)


if __name__ == '__main__':
    if sys.argv[1:] == ['--execute-authorized']:
        pack()
    elif len(sys.argv) == 3 and sys.argv[1] == '--validate-guest':
        from v6.guest_probe import probe
        probe(sys.argv[2])
    else:
        raise SystemExit('Use the documented manual systemd command.')
