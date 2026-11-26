import hashlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from v7 import admin_bootstrap


class PreflightTest(unittest.TestCase):
    def test_administrative_iso_integrity_and_permissions(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source-v6.iso'
            source.write_bytes(b'iso')
            source.chmod(0o444)
            good = hashlib.sha256(b'iso').hexdigest()
            def checked(path, **kwargs):
                return real_checked(path, uid=os.getuid(), **kwargs)
            real_checked = admin_bootstrap.checked
            with patch.object(admin_bootstrap, 'ADMIN', root), \
                    patch.object(admin_bootstrap, 'SOURCE_SIZE', 3), \
                    patch.object(admin_bootstrap, 'SOURCE_SHA', good), \
                    patch.object(admin_bootstrap, 'checked', side_effect=checked):
                self.assertEqual(admin_bootstrap.source_iso(), source)
                source.chmod(0o644)
                with self.assertRaisesRegex(ValueError, 'Untrusted'):
                    admin_bootstrap.source_iso()
                source.write_bytes(b'bad')
                source.chmod(0o444)
                with self.assertRaisesRegex(ValueError, 'approved bytes'):
                    admin_bootstrap.source_iso()
                original = source.with_name('original.iso')
                source.rename(original)
                source.symlink_to(original)
                with self.assertRaisesRegex(ValueError, 'Untrusted'):
                    admin_bootstrap.source_iso()
