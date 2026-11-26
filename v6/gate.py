"""Validate the full suite and any later scoped DevControl changes."""
import contextlib
import hashlib
import json
import stat
import subprocess
import sys
import unittest
from pathlib import Path

from v6.storage import ROOT

VALIDATION = ROOT / 'work/v6-validation'
RECEIPT = VALIDATION / 'installer-visual-suite.json'
DEVCONTROL = VALIDATION / 'devcontrol-suite.json'
BASELINE = VALIDATION / 'devcontrol-baseline.json'
XFCE = VALIDATION / 'xfce-suite.json'
XFCE_BASELINE = VALIDATION / 'xfce-baseline.json'
POLKIT = VALIDATION / 'polkit-fix-suite.json'
POLKIT_BASELINE = VALIDATION / 'polkit-fix-baseline.json'
GUEST = VALIDATION / 'guest-fix-suite.json'
GUEST_BASELINE = VALIDATION / 'guest-fix-baseline.json'
SSH = VALIDATION / 'ssh-fix-suite.json'
SSH_BASELINE = VALIDATION / 'ssh-fix-baseline.json'
SSH_AFFECTED = frozenset(('v6/gate.py', 'v6/guest.py', 'v6/tests/test_guest_isolation.py'))
GUEST_AFFECTED = frozenset((
    'v6/gate.py', 'v6/build-manual.sh', 'v6/guest.py', 'v6/pack.py',
    'v6/guest_probe.py', 'v6/tests/test_guest_isolation.py',
))
POLKIT_AFFECTED = frozenset((
    'v6/gate.py',
    'v6/payload.py',
    'v6/tests/test_polkit_payload.py',
))
XFCE_AFFECTED = frozenset((
    'v6/gate.py',
    'v6/overlay/etc/xdg/xfce4/whiskermenu/defaults.rc',
    'v6/overlay/etc/xdg/xdg-xubuntu/xfce4/whiskermenu/defaults.rc',
    'v6/tests/test_xfce_identity.py',
))
AFFECTED = (
    'v6/devcontrol/app.py',
    'v6/devcontrol/metrics.py',
    'v6/devcontrol/services.py',
    'v6/gate.py',
    'v6/overlay/usr/libexec/devlite-services-v6',
    'v6/overlay/usr/share/applications/devcontrol.desktop',
    'v6/overlay/usr/share/applications/devlite-control.desktop',
    'v6/payload.py',
    'v6/tests/test_devcontrol3.py',
)


def files():
    records = {}
    for name in ('v6', 'v5', 'pipeline', 'config/v6', 'tests'):
        for path in (ROOT / name).rglob('*'):
            if '__pycache__' in path.parts:
                continue
            if path.is_symlink():
                value = str(path.readlink())
            elif path.is_file():
                with path.open('rb') as stream:
                    value = hashlib.file_digest(stream, 'sha256').hexdigest()
            else:
                continue
            records[str(path.relative_to(ROOT))] = [path.lstat().st_mode, value]
    return records


def fingerprint(records):
    result = hashlib.sha256()
    for path in sorted(records, key=Path):
        mode, value = records[path]
        result.update(path.encode() + b'\0')
        result.update(mode.to_bytes(4, 'big'))
        result.update(value.encode() if stat.S_ISLNK(mode) else bytes.fromhex(value))
        result.update(b'\0')
    return result.hexdigest()


def identity():
    return fingerprint(files())


def approved(path):
    data = json.loads(path.read_text())
    if (data['successful'] is not True or data['failed'] or data['errors']
            or data['skipped'] or data['project_check']):
        raise ValueError(f'Unsuccessful test receipt: {path.name}')
    return data


def devcontrol_scope(current):
    baseline = json.loads(BASELINE.read_text())
    previous = baseline['files']
    digest = approved(RECEIPT)['source_sha256']
    if fingerprint(previous) != digest or baseline['source_sha256'] != digest:
        raise ValueError('DevControl baseline differs from the approved full suite')
    changed = {p for p in current.keys() | previous.keys() if current.get(p) != previous.get(p)}
    if not changed <= set(AFFECTED):
        raise ValueError(f'Files outside the tested scope changed: {sorted(changed - set(AFFECTED))}')
    return digest


def verify_devcontrol(current):
    baseline = devcontrol_scope(current)
    scoped = approved(DEVCONTROL)
    if scoped['source_sha256'] != fingerprint(current) or scoped['baseline_sha256'] != baseline:
        raise ValueError('DevControl test receipt is stale or incomplete')


def xfce_scope(current):
    baseline = json.loads(XFCE_BASELINE.read_text())
    previous = baseline['files']
    verify_devcontrol(previous)
    digest = fingerprint(previous)
    if digest != baseline['source_sha256']:
        raise ValueError('XFCE baseline differs from the approved DevControl scope')
    changed = {p for p in current.keys() | previous.keys() if current.get(p) != previous.get(p)}
    if not changed <= XFCE_AFFECTED:
        raise ValueError(f'Files outside the XFCE scope changed: {sorted(changed - XFCE_AFFECTED)}')
    return digest


def verify_xfce(current):
    baseline = xfce_scope(current)
    scoped = approved(XFCE)
    if scoped['source_sha256'] != fingerprint(current) or scoped['baseline_sha256'] != baseline:
        raise ValueError('XFCE test receipt is stale or incomplete')


def polkit_scope(current):
    baseline = json.loads(POLKIT_BASELINE.read_text())
    previous = baseline['files']
    verify_xfce(previous)
    digest = fingerprint(previous)
    if digest != baseline['source_sha256']:
        raise ValueError('Polkit baseline differs from the approved XFCE scope')
    changed = {p for p in current.keys() | previous.keys() if current.get(p) != previous.get(p)}
    if not changed <= POLKIT_AFFECTED:
        raise ValueError(f'Files outside the Polkit fix changed: {sorted(changed - POLKIT_AFFECTED)}')
    return digest


def verify_polkit(current):
    baseline = polkit_scope(current)
    scoped = approved(POLKIT)
    if scoped['source_sha256'] != fingerprint(current) or scoped['baseline_sha256'] != baseline:
        raise ValueError('Polkit test receipt is stale or incomplete')


def guest_scope(current):
    baseline = json.loads(GUEST_BASELINE.read_text())
    previous = baseline['files']
    verify_polkit(previous)
    digest = fingerprint(previous)
    if digest != baseline['source_sha256']:
        raise ValueError('Guest baseline differs from the approved Polkit scope')
    changed = {p for p in current.keys() | previous.keys() if current.get(p) != previous.get(p)}
    if not changed <= GUEST_AFFECTED:
        raise ValueError(f'Files outside the guest fix changed: {sorted(changed - GUEST_AFFECTED)}')
    return digest


def verify_guest(current):
    baseline = guest_scope(current)
    scoped = approved(GUEST)
    if scoped['source_sha256'] != fingerprint(current) or scoped['baseline_sha256'] != baseline:
        raise ValueError('Guest test receipt is stale or incomplete')


def ssh_scope(current):
    baseline = json.loads(SSH_BASELINE.read_text())
    previous = baseline['files']
    verify_guest(previous)
    digest = fingerprint(previous)
    if digest != baseline['source_sha256']:
        raise ValueError('SSH baseline differs from the approved guest scope')
    changed = {p for p in current.keys() | previous.keys() if current.get(p) != previous.get(p)}
    if not changed <= SSH_AFFECTED:
        raise ValueError(f'Files outside the SSH fix changed: {sorted(changed - SSH_AFFECTED)}')
    return digest


def verify():
    current = files()
    active = fingerprint(current)
    if approved(RECEIPT)['source_sha256'] == active:
        return
    if approved(DEVCONTROL)['source_sha256'] == active:
        verify_devcontrol(current)
        return
    if approved(XFCE)['source_sha256'] == active:
        verify_xfce(current)
        return
    if approved(POLKIT)['source_sha256'] == active:
        verify_polkit(current)
        return
    if approved(GUEST)['source_sha256'] == active:
        verify_guest(current)
        return
    baseline = ssh_scope(current)
    scoped = approved(SSH)
    if scoped['source_sha256'] != active or scoped['baseline_sha256'] != baseline:
        raise ValueError('SSH test receipt is stale or incomplete')



def test(scope=None):
    current = files()
    before = fingerprint(current)
    loader = unittest.TestLoader()
    baseline = None
    if scope == 'devcontrol':
        baseline = devcontrol_scope(current)
        output = DEVCONTROL
        patterns = ('test_payload.py', 'test_devcontrol3.py')
    elif scope == 'xfce':
        baseline = xfce_scope(current)
        output = XFCE
        patterns = ('test_xfce_identity.py',)
    elif scope == 'polkit':
        baseline = polkit_scope(current)
        output = POLKIT
        patterns = ('test_polkit_payload.py', 'test_payload.py', 'test_devcontrol3.py', 'test_xfce_identity.py')
    elif scope == 'guest':
        baseline = guest_scope(current)
        output = GUEST
        patterns = ('test_guest_isolation.py', 'test_build.py')
    elif scope == 'ssh':
        baseline = ssh_scope(current)
        output = SSH
        patterns = ('test_guest_isolation.py',)
    else:
        output = RECEIPT
    if scope:
        suites = [loader.discover(str(ROOT / 'v6/tests'), pattern=pattern) for pattern in patterns]
    else:
        suites = [loader.discover(str(ROOT / relative)) for relative in ('tests', 'v5/tests', 'v6/tests')]
    log = output.with_suffix('.log')
    with log.open('x') as stream, contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.TestSuite(suites))
    checker = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/verificar-projeto.py')],
                             cwd=ROOT, check=False).returncode
    report = {'executed': result.testsRun, 'failed': len(result.failures), 'errors': len(result.errors),
              'skipped': len(result.skipped), 'source_sha256': before, 'project_check': checker}
    if baseline is not None:
        report['baseline_sha256'] = baseline
    report['successful'] = result.wasSuccessful() and not result.skipped and checker == 0 and before == identity()
    with output.open('x') as stream:
        json.dump(report, stream, indent=2)
    print(report)
    return 0 if report['successful'] else 1


if __name__ == '__main__':
    if sys.argv[1:] == ['test']:
        raise SystemExit(test())
    if sys.argv[1:] == ['test-devcontrol']:
        raise SystemExit(test('devcontrol'))
    if sys.argv[1:] == ['test-xfce']:
        raise SystemExit(test('xfce'))
    if sys.argv[1:] == ['test-polkit']:
        raise SystemExit(test('polkit'))
    if sys.argv[1:] == ['test-guest']:
        raise SystemExit(test('guest'))
    if sys.argv[1:] == ['test-ssh']:
        raise SystemExit(test('ssh'))
    if sys.argv[1:] == ['verify']:
        verify()
    else:
        raise SystemExit('Expected test, test-devcontrol, test-xfce, test-polkit, test-guest, test-ssh or verify')
