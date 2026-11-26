import os
import shutil
import stat
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from v6 import payload


class PolkitPayloadTests(unittest.TestCase):
    def test_checkout_umask_cannot_make_privileged_guest_files_writable(self):
        for target in ('base', 'live'):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as directory:
                temp = Path(directory).resolve()
                overlay = temp / 'source'
                shutil.copytree(payload.OVERLAY, overlay, symlinks=True)
                (overlay / payload.POLICY).chmod(0o664)
                (overlay / payload.HELPER).chmod(0o775)
                guest = temp / 'guest'
                guest.mkdir(mode=0o700)
                real_lstat = Path.lstat

                def root_owned(path):
                    # Exercise the production root check without sudo. Only UID is
                    # simulated; modes and symlinks come from the real filesystem.
                    info = real_lstat(path)
                    return SimpleNamespace(st_mode=info.st_mode, st_uid=0)

                with patch.object(payload, 'OVERLAY', overlay), patch.object(
                        payload.os, 'geteuid', return_value=0), patch.object(Path, 'lstat', root_owned):
                    payload.apply(guest, target)
                policy = guest / payload.POLICY
                helper = guest / payload.HELPER
                for path, mode in ((policy, 0o644), (helper, 0o755)):
                    info = path.lstat()
                    self.assertTrue(stat.S_ISREG(info.st_mode))
                    self.assertEqual(stat.S_IMODE(info.st_mode), mode)
                action = ET.parse(policy).find('action')
                self.assertEqual(action.attrib['id'], 'org.devlite.v6.services.manage')
                self.assertEqual(action.findtext('annotate'), '/' + payload.HELPER)
                self.assertEqual(action.findtext('defaults/allow_any'), 'no')
                self.assertEqual(action.findtext('defaults/allow_inactive'), 'no')
                self.assertEqual(action.findtext('defaults/allow_active'), 'auth_admin')
                self.assertEqual(stat.S_IMODE((overlay / payload.POLICY).stat().st_mode), 0o664)
                self.assertEqual(stat.S_IMODE((overlay / payload.HELPER).stat().st_mode), 0o775)

    def test_rejects_symlink_policy_source_and_destination(self):
        for endpoint in ('source', 'guest'):
            with self.subTest(endpoint=endpoint), tempfile.TemporaryDirectory() as directory:
                temp = Path(directory).resolve()
                overlay = temp / 'source'
                shutil.copytree(payload.OVERLAY, overlay, symlinks=True)
                guest = temp / 'guest'
                guest.mkdir()
                outside = temp / 'outside'
                outside.write_text('unchanged')
                policy = (overlay if endpoint == 'source' else guest) / payload.POLICY
                if endpoint == 'source':
                    policy.unlink()
                else:
                    policy.parent.mkdir(parents=True)
                policy.symlink_to(outside)
                with patch.object(payload, 'OVERLAY', overlay), self.assertRaisesRegex(
                        ValueError, 'Unexpected overlay symlink|Unexpected target'):
                    payload.apply(guest, 'base')
                self.assertEqual(outside.read_text(), 'unchanged')

    def test_privileged_ancestor_remains_protected(self):
        with tempfile.TemporaryDirectory() as directory:
            guest = Path(directory).resolve()
            parent = (guest / payload.POLICY).parent
            parent.mkdir(parents=True)
            for path in parent.parents:
                if path == guest:
                    break
                path.chmod(0o755)
            parent.chmod(0o775)
            real_lstat = Path.lstat

            def root_owned(path):
                info = real_lstat(path)
                return SimpleNamespace(st_mode=info.st_mode, st_uid=0)

            with patch.object(payload.os, 'geteuid', return_value=0), patch.object(
                    Path, 'lstat', root_owned), self.assertRaisesRegex(
                        ValueError, 'Untrusted DevControl path: .*polkit-1/actions$'):
                payload.apply(guest, 'base')
            self.assertEqual(os.stat(parent).st_mode & 0o777, 0o775)
