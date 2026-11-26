import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from v7 import admin_bootstrap as bootstrap, pack


class SnapshotTest(unittest.TestCase):
    def setUp(self):
        workspace = tempfile.TemporaryDirectory()
        self.addCleanup(workspace.cleanup)
        self.snapshot = Path(workspace.name) / 'snapshot'
        self.code = self.snapshot / 'code'
        self.module = self.code / 'v7/pack.py'
        self.module.parent.mkdir(parents=True)
        self.module.write_text('VALUE = 42\n')
        self.raw = json.dumps({'v7/pack.py': bootstrap.file_digest(self.module)}).encode()
        manifest = self.snapshot / bootstrap.MANIFEST
        manifest.write_bytes(self.raw)
        for path in [self.snapshot, *self.snapshot.rglob('*')]:
            path.chmod(0o555 if path.is_dir() else 0o444)
        self.addCleanup(self.unlock)
        self.expected = bootstrap.fingerprint(self.raw)

    def unlock(self):
        for path in [self.snapshot, *self.snapshot.rglob('*')]:
            if path.is_dir() and not path.is_symlink():
                path.chmod(0o755)

    def verify(self, expected=None):
        return bootstrap.verify_snapshot(self.snapshot, expected or self.expected, uid=os.getuid())

    def test_valid_snapshot_loads_in_isolated_python(self):
        bootstrap_path = Path(bootstrap.__file__)
        with tempfile.TemporaryDirectory() as directory:
            rogue = Path(directory)
            (rogue / 'v7').mkdir()
            (rogue / 'v7/missing.py').write_text('raise SystemExit("unapproved module executed")\n')
            program = """
import runpy, sys
from pathlib import Path
anchor = runpy.run_path(sys.argv[1])
code, entries = anchor['verify_snapshot'](Path(sys.argv[2]), sys.argv[3], uid=int(sys.argv[4]))
assert sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode
sys.meta_path.insert(0, anchor['SnapshotImports'](code, entries))
sys.path.append(str(code))
from v7 import pack
assert pack.VALUE == 42
# Even a later addition to the search path cannot extend the project namespaces.
sys.path.append(sys.argv[5])
try:
    import v7.missing
except ModuleNotFoundError as error:
    assert 'Unapproved worker import' in str(error)
else:
    raise AssertionError('unapproved module imported')
"""
            subprocess.run(['/usr/bin/python3', '-ISB', '-c', program, str(bootstrap_path),
                            str(self.snapshot), self.expected, str(os.getuid()), str(rogue)],
                           cwd=rogue, env={**os.environ, 'PYTHONPATH': str(rogue)}, check=True)

    def test_changed_code_is_rejected(self):
        self.module.chmod(0o644)
        self.module.write_text('VALUE = 0\n')
        self.module.chmod(0o444)
        with self.assertRaisesRegex(ValueError, 'Unapproved worker file'):
            self.verify()

    def test_fingerprint_and_writable_files_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            self.verify('0' * 64)
        self.module.chmod(0o664)
        with self.assertRaisesRegex(ValueError, 'Untrusted administrative path'):
            self.verify()

    def test_symlink_and_hardlink_are_rejected(self):
        self.module.parent.chmod(0o755)
        sibling = self.module.parent / 'copy'
        self.module.rename(sibling)
        self.module.symlink_to(sibling)
        self.module.parent.chmod(0o555)
        with self.assertRaisesRegex(ValueError, 'Untrusted administrative path'):
            self.verify()
        self.module.parent.chmod(0o755)
        self.module.unlink()
        os.link(sibling, self.module)
        self.module.parent.chmod(0o555)
        with self.assertRaisesRegex(ValueError, 'Untrusted administrative path'):
            self.verify()

    def test_extra_bytecode_and_unsafe_paths_are_rejected(self):
        self.module.parent.chmod(0o755)
        extra = self.module.with_suffix('.pyc')
        extra.write_bytes(b'compiled')
        extra.chmod(0o444)
        self.module.parent.chmod(0o555)
        with self.assertRaisesRegex(ValueError, 'Unapproved worker file'):
            self.verify()
        for name in ('v7/../outside.py', '/home/magaton/evil.py', 'v7/lib.so'):
            with self.assertRaisesRegex(ValueError, 'Unexpected worker path'):
                bootstrap.path_name(name)


class CleanupTest(unittest.TestCase):
    def test_cleanup_failure_quarantines_pack_before_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            job = Path(directory)
            pending = job / 'publication.pending'
            pending.mkdir(mode=0o700)
            report = {'status': 'quarantined'}
            with patch.object(pack, 'cleanup_barrier', return_value=['loop still active']):
                with self.assertRaisesRegex(ValueError, 'quarantined'):
                    pack.finish_pack(job, report, Mock())
            self.assertFalse((job / 'published').exists())
            self.assertFalse((pending / 'pack.json').exists())
            audit = json.loads((job / 'audit.json').read_text())
            self.assertEqual(audit['status'], 'quarantined')
            self.assertEqual(audit['cleanup_errors'], ['loop still active'])
