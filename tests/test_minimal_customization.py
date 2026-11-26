"""Segurança do patch mínimo; testes executados sem root e sem instalações."""
import copy
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline.devlite.runtime import BuildError
from pipeline.devlite import minimal_root as module
from pipeline.devlite.minimal_build import update_grub, make_md5, compare_iso_trees
from pipeline.devlite.minimal_config import replace_field

ROOT = Path(__file__).resolve().parents[1]


class MinimalTests(unittest.TestCase):
    def temp(self):
        return tempfile.TemporaryDirectory(dir=ROOT / 'work')

    def test_root_main_requires_explicit_privileged_execution(self):
        with patch.object(module.os, 'geteuid', return_value=1000):
            with self.assertRaises(BuildError):
                module.main(ROOT / 'work/unknown', 'extract')

    def test_allowed_configuration_excludes_packages_and_host_accounts(self):
        self.assertTrue(module.allowed_configuration('etc/locale.conf'))
        self.assertTrue(module.allowed_configuration('usr/lib/locale/pt_BR.utf8/LC_TIME'))
        for name in ('etc/passwd', 'var/lib/dpkg/status', '../etc/locale.conf', 'usr/lib/locale/pt_BR.utf8/../../passwd'):
            self.assertFalse(module.allowed_configuration(name))

    def test_member_refuses_symlink_ancestors(self):
        with self.temp() as folder:
            root = Path(folder)
            (root / 'etc').symlink_to('/etc')
            with self.assertRaises(BuildError):
                module.member(root, 'etc/locale.conf')
            with self.assertRaises(BuildError):
                module.member(root, '../outside')

    def test_snapshot_covers_xattrs_hardlinks_and_symlinks(self):
        with self.temp() as folder:
            root = Path(folder)
            file = root / 'a'; file.write_bytes(b'fixture')
            os.setxattr(file, 'user.devlite', b'xattr')
            os.link(file, root / 'b'); (root / 'link').symlink_to('a')
            result = module.snapshot(root)
            self.assertEqual(result['a']['hardlinks'], ['a', 'b'])
            self.assertIn('user.devlite', result['a']['xattrs'])
            self.assertEqual(result['link']['target'], 'a')

    def test_diff_rejects_package_or_metadata_change(self):
        before = {'var/lib/dpkg/status': {'sha256': 'a'}, 'etc/locale.conf': {'sha256': 'b'}}
        after = copy.deepcopy(before); after['var/lib/dpkg/status']['sha256'] = 'changed'
        with self.assertRaises(BuildError):
            module.check_diff(before, after, {'etc/locale.conf'})
        after = {'etc/locale.conf': {'sha256': 'b'}}
        with self.assertRaises(BuildError):
            module.check_diff(before, after, {'etc/locale.conf'})

    def test_live_reconciliation_detects_exact_and_opaque_mask(self):
        self.assertTrue(module.is_masked('etc/locale.conf', {'etc/locale.conf': {}}))
        self.assertTrue(module.is_masked('etc/locale.conf', {'etc': {'xattrs': {'trusted.overlay.opaque': 'eQ=='}}}))
        self.assertFalse(module.is_masked('etc/locale.conf', {'var/lib/dpkg/status': {}}))

    def test_live_non_directory_ancestor_requires_review(self):
        with self.assertRaises(BuildError):
            module.is_masked('etc/locale.conf', {'etc': {'type': 'char', 'xattrs': {}}})

    def test_grub_preserves_safe_graphics_and_iso_scan(self):
        original = 'linux /casper/vmlinuz nomodeset iso-scan/filename=${iso_path} --- quiet splash\n'
        rendered, count = update_grub(original)
        self.assertEqual(count, 1)
        self.assertIn('nomodeset iso-scan/filename=${iso_path}', rendered)
        self.assertIn('locale=pt_BR.UTF-8', rendered)
        self.assertIn('keyboard-configuration/modelcode=abnt2', rendered)
        with self.assertRaises(BuildError):
            update_grub(rendered)

    def test_identity_keeps_ubuntu_id_and_noble_codename(self):
        original = 'NAME="Ubuntu"\nID=ubuntu\nUBUNTU_CODENAME=noble\n'
        rendered = replace_field(original, 'NAME', 'DevLite OS')
        self.assertIn('NAME="DevLite OS"', rendered)
        self.assertIn('ID=ubuntu\nUBUNTU_CODENAME=noble', rendered)

    def test_outer_iso_cannot_change_installer_outside_allowlist(self):
        before = {'casper/initrd': {'sha256': 'trusted'}}
        after = {'casper/initrd': {'sha256': 'changed'}}
        with self.assertRaises(BuildError):
            compare_iso_trees(before, after, Path('.'), Path('.'), set(), set(), set())

    def test_md5_moves_stale_signature_and_covers_updated_payload(self):
        with self.temp() as folder:
            file = Path(folder) / 'new'; file.write_bytes(b'updated')
            original = '0' * 32 + '  ./casper/SHA256SUMS.gpg\n' + '1' * 32 + '  ./casper/SHA256SUMS\n'
            result = make_md5(original, {'casper/SHA256SUMS': file}, {'casper/devlite-provenance/original-SHA256SUMS.gpg': file})
            self.assertNotIn('  ./casper/SHA256SUMS.gpg\n', result)
            self.assertIn(hashlib.md5(b'updated').hexdigest(), result)
            self.assertIn('devlite-provenance/original-SHA256SUMS.gpg', result)

    def test_allocated_usage_does_not_double_count_hardlinks(self):
        with self.temp() as folder:
            root = Path(folder)
            file = root / 'a'; file.write_bytes(b'x' * 8192)
            os.link(file, root / 'b')
            self.assertEqual(module.allocated_usage(root), (root.stat().st_blocks + file.stat().st_blocks) * 512)

    def test_payload_symlink_or_tampering_is_rejected(self):
        with self.temp() as folder:
            root = Path(folder)
            (root / 'configuration/etc').mkdir(parents=True)
            file = root / 'configuration/etc/locale.conf'; file.write_bytes(b'original')
            manifest = {'etc/locale.conf': {'kind': 'file', 'sha256': hashlib.sha256(b'original').hexdigest()}}
            (root / 'configuration.json').write_text(json.dumps(manifest))
            self.assertEqual(module.load_payloads(root), manifest)
            file.write_bytes(b'changed')
            with self.assertRaises(BuildError):
                module.load_payloads(root)


if __name__ == '__main__':
    unittest.main()
