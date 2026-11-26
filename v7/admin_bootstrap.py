"""Administrative trust anchor. Install and review this standalone file separately."""
import hashlib
import importlib.machinery
import io
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tarfile
import tempfile

ADMIN = Path('/etc/devlite-v7')
ROOTS = {'pipeline', 'v5', 'v6', 'v7', 'config'}
SOURCE_SIZE = 3654746112
SOURCE_SHA = '3d8cc3de5747f69be2b569ab91320f9d783ec4c0107ccd09064f70ba0cf0f09d'
CAP = 64 * 1024**2
RESERVE = 10 * 1024**3
MANIFEST = 'manifest.json'
HEX = re.compile(r'[0-9a-f]{64}')


def checked(path, *, directory=False, immutable=False, uid=0):
    info = path.lstat()
    kind = stat.S_ISDIR if directory else stat.S_ISREG
    mask = 0o7222 if immutable else 0o7022
    if (not kind(info.st_mode) or info.st_uid != uid or info.st_mode & mask
            or (not directory and info.st_nlink != 1)):
        raise ValueError(f'Untrusted administrative path: {path}')
    return info


def administrative_root():
    for path in (Path('/'), Path('/etc'), ADMIN):
        checked(path, directory=True)
    checked(ADMIN / 'bootstrap.py', immutable=True)
    checked(ADMIN / 'worker', directory=True)


def path_name(name):
    parts = name.split('/')
    if (len(parts) < 2 or parts[0] not in ROOTS or any(
            not re.fullmatch(r'[A-Za-z0-9_.-]+', part) or part in ('.', '..', '__pycache__')
            for part in parts)
            or Path(name).suffix in ('.pyc', '.pyo', '.so', '.pth', '.zip')):
        raise ValueError(f'Unexpected worker path: {name}')
    return name


def fingerprint(data):
    return hashlib.sha256(data).hexdigest()


def file_digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def manifest_data(raw, expected):
    if not HEX.fullmatch(expected) or fingerprint(raw) != expected:
        raise ValueError('Worker manifest fingerprint mismatch')
    entries = json.loads(raw)
    if not isinstance(entries, dict) or 'v7/pack.py' not in entries:
        raise ValueError('Invalid worker manifest')
    for name, digest in entries.items():
        path_name(name)
        if not isinstance(digest, str) or not HEX.fullmatch(digest):
            raise ValueError('Invalid worker file digest')
    return entries


def verify_snapshot(directory, expected, uid=0):
    checked(directory, directory=True, immutable=True, uid=uid)
    path = directory / MANIFEST
    if checked(path, immutable=True, uid=uid).st_size > CAP:
        raise ValueError('Manifest exceeds staging limit')
    entries = manifest_data(path.read_bytes(), expected)
    code = directory / 'code'
    checked(code, directory=True, immutable=True, uid=uid)
    if {p.name for p in directory.iterdir()} != {MANIFEST, 'code'}:
        raise ValueError('Unexpected worker snapshot entries')
    actual = set()
    for path in code.rglob('*'):
        relative = path.relative_to(code).as_posix()
        if path.is_dir() and not path.is_symlink():
            if not any(name.startswith(relative + '/') for name in entries):
                raise ValueError(f'Unapproved worker directory: {relative}')
            checked(path, directory=True, immutable=True, uid=uid)
            continue
        checked(path, immutable=True, uid=uid)
        if relative not in entries or file_digest(path) != entries[relative]:
            raise ValueError(f'Unapproved worker file: {relative}')
        actual.add(relative)
    if actual != entries.keys():
        raise ValueError('Worker manifest does not match the snapshot tree')
    return code, entries


class SnapshotImports:
    def __init__(self, code, entries):
        self.code = code
        self.entries = entries

    def find_spec(self, fullname, path=None, target=None):
        if fullname.partition('.')[0] not in ROOTS:
            return None
        spec = importlib.machinery.PathFinder.find_spec(
            fullname, [str(self.code)] if path is None else path)
        if spec is not None:
            if spec.origin is not None:
                origin = Path(spec.origin)
                if (origin.is_relative_to(self.code) and origin.suffix == '.py'
                        and origin.relative_to(self.code).as_posix() in self.entries):
                    return spec
            elif spec.submodule_search_locations and all(
                    Path(item).is_relative_to(self.code) for item in spec.submodule_search_locations):
                return spec
        raise ModuleNotFoundError(f'Unapproved worker import: {fullname}', name=fullname)


def source_iso():
    source = ADMIN / 'source-v6.iso'
    if (checked(source, immutable=True).st_size != SOURCE_SIZE
            or file_digest(source) != SOURCE_SHA):
        raise ValueError('Administrative ISO v6 does not match the approved bytes')
    return source


def approved_snapshot():
    administrative_root()
    receipt = ADMIN / 'release.json'
    checked(receipt)
    expected = json.loads(receipt.read_text()).get('worker_sha256', '')
    if not isinstance(expected, str) or not HEX.fullmatch(expected):
        raise ValueError('Invalid administrative worker fingerprint')
    code, entries = verify_snapshot(ADMIN / 'worker' / expected, expected)
    return expected, code, entries


def stage_snapshot(expected):
    administrative_root()
    if not HEX.fullmatch(expected):
        raise ValueError('Invalid expected fingerprint')
    parent = ADMIN / 'worker'
    final = parent / expected
    if final.exists() or final.is_symlink():
        raise ValueError('Snapshot already exists')
    if shutil.disk_usage(parent).free < RESERVE + CAP:
        raise ValueError('Insufficient storage for administrative snapshot')
    temporary = Path(tempfile.mkdtemp(prefix='.staging-', dir=parent))
    code = temporary / 'code'
    code.mkdir()
    limit = CAP + 2 * 1024**2
    archive_bytes = sys.stdin.buffer.read(limit + 1)
    if len(archive_bytes) > limit:
        raise ValueError('Worker archive exceeds input limit')
    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode='r:') as archive:
        member = archive.next()
        if member is None or member.name != MANIFEST or not member.isfile() or member.size > CAP:
            raise ValueError('Expected a bounded manifest as first archive member')
        raw = archive.extractfile(member).read()
        entries = manifest_data(raw, expected)
        (temporary / MANIFEST).write_bytes(raw)
        total = len(raw)
        seen = set()
        while member := archive.next():
            name = path_name(member.name)
            total += member.size
            if not member.isfile() or total > CAP or name not in entries or name in seen:
                raise ValueError(f'Unapproved archive member: {name}')
            target = code / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                shutil.copyfileobj(archive.extractfile(member), stream)
            seen.add(name)
    for path in temporary.rglob('*'):
        path.chmod(0o555 if path.is_dir() else 0o444)
    temporary.chmod(0o555)
    verify_snapshot(temporary, expected)
    os.rename(temporary, final)
    print(final)


def stage_source():
    administrative_root()
    final = ADMIN / 'source-v6.iso'
    if final.exists() or final.is_symlink():
        raise ValueError('Administrative ISO already exists')
    if shutil.disk_usage(ADMIN).free < RESERVE + SOURCE_SIZE:
        raise ValueError('Insufficient storage for administrative ISO')
    fd, name = tempfile.mkstemp(prefix='.source-', dir=ADMIN)
    path = Path(name)
    remaining = SOURCE_SIZE
    hash_value = hashlib.sha256()
    with os.fdopen(fd, 'wb') as stream:
        while remaining:
            block = sys.stdin.buffer.read(min(1024**2, remaining))
            if not block:
                break
            remaining -= len(block)
            hash_value.update(block)
            stream.write(block)
    if remaining or sys.stdin.buffer.read(1) or hash_value.hexdigest() != SOURCE_SHA:
        raise ValueError(f'Administrative ISO rejected, private staging retained at {path}')
    path.chmod(0o444)
    os.link(path, final)
    path.unlink()
    print(final)


def bundle(repo, output):
    # This path is only for producing a reviewable archive as the ordinary user.
    if os.geteuid() == 0:
        raise ValueError('Prepare review bundles without privileges')
    files = {}
    for folder in sorted(ROOTS):
        for path in sorted((repo / folder).rglob('*')):
            relative = path.relative_to(repo).as_posix()
            if '__pycache__' in path.parts or 'tests' in path.relative_to(repo).parts:
                continue
            if relative == 'v6/overlay/etc/apache2/conf-enabled/devlite-servername.conf' and path.is_symlink():
                # Historical link is unused in v7. Reject a different target.
                if os.readlink(path) != '../conf-available/devlite-servername.conf':
                    raise ValueError('Unexpected historical Apache symlink')
                continue
            if path.is_symlink() or (not path.is_file() and not path.is_dir()):
                raise ValueError(f'Unexpected review input: {path}')
            if path.is_file():
                files[path_name(relative)] = path.read_bytes()
    raw = json.dumps({name: fingerprint(data) for name, data in files.items()},
                     sort_keys=True, separators=(',', ':')).encode()
    if len(raw) + sum(map(len, files.values())) > CAP:
        raise ValueError('Worker archive exceeds staging limit')
    with tarfile.open(output, 'x', format=tarfile.USTAR_FORMAT) as archive:
        for name, data in [(MANIFEST, raw), *files.items()]:
            member = tarfile.TarInfo(name)
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
    print(fingerprint(raw))


def main():
    args = sys.argv[1:]
    if len(args) == 3 and args[0] == '--bundle':
        bundle(Path(args[1]).resolve(), args[2])
        return
    if not (sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode):
        raise ValueError('Use system Python with -ISB')
    if args == ['--check']:
        expected, _, _ = approved_snapshot()
        source_iso()
        print(expected)
        return
    if os.geteuid() != 0 or Path(__file__) != ADMIN / 'bootstrap.py':
        raise ValueError('Administrative staging requires the installed root-owned bootstrap')
    if len(args) == 2 and args[0] == '--stage':
        stage_snapshot(args[1])
    elif args == ['--stage-source']:
        stage_source()
    elif args == ['--execute-authorized']:
        if os.getpid() != 1:
            raise ValueError('Worker must be PID 1 of its private namespace')
        expected, code, entries = approved_snapshot()
        source_iso()
        sys.meta_path.insert(0, SnapshotImports(code, entries))
        sys.path.extend(['/usr/lib/python3/dist-packages', str(code)])
        from v7 import pack
        pack.pack(expected)
    else:
        raise ValueError('Invalid administrative action')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, tarfile.TarError) as error:
        raise SystemExit(str(error)) from None
