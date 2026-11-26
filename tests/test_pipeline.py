"""Ensaios sem ISO grande, sem privilégios e sem comandos de build reais."""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.devlite.build import rebuild_args, preflight
from pipeline.devlite.runtime import BuildError, Runner, owned_directory
from pipeline.devlite.structure import parse_boot, region_digest, compare_boot_metadata
from pipeline.devlite.validation import compare_trees, inventory, verify_manifest, iso_metadata

BOOT = """El Torito boot img :   1  BIOS  y   none  0x0000  0x00      4         801
El Torito boot img :   2  UEFI  y   none  0x0000  0x00  10160     1556628
El Torito img path :   1  /boot/grub/i386-pc/eltorito.img
System area summary: MBR protective-msdos-label grub2-mbr cyl-align-off GPT
GPT type GUID      :   2  28732ac11ff8d211ba4b00a0c93ec93b
GPT start and size :   2  6226512  10160
"""


class PipelineTests(unittest.TestCase):
    def test_boot_efi_must_match_gpt(self):
        self.assertEqual(parse_boot(BOOT)['efi_bytes'], 5201920)
        for value in (BOOT.replace('6226512', '6226500'), BOOT.replace('UEFI', 'BIOS'), BOOT.replace('grub2-mbr', 'unknown')):
            with self.assertRaises(BuildError):
                parse_boot(value)

    def test_input_output_never_same_or_existing(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'source.iso'
            source.touch()
            with self.assertRaises(BuildError):
                rebuild_args(source, source, '2026090808365000')
            args = rebuild_args(source, Path(folder) / 'new.iso', '2026090808365000')
            self.assertIn('replay', args)
            self.assertNotIn('-dev', args)

    def test_workspace_refuses_symlink_and_keeps_marker(self):
        with tempfile.TemporaryDirectory() as folder:
            parent = Path(folder)
            work = owned_directory(parent, 'test-')
            self.assertEqual(json.loads((work / '.devlite-workspace.json').read_text())['path'], str(work.resolve()))
            link = parent / 'alias'
            link.symlink_to(work, target_is_directory=True)
            with self.assertRaises(BuildError):
                owned_directory(link, 'test-')
            self.assertTrue(work.exists())

    def test_runner_failure_retains_logs(self):
        with tempfile.TemporaryDirectory() as folder:
            runner = Runner(Path(folder), 1)
            with self.assertRaises(BuildError):
                runner.run('failure', [sys.executable, '-c', 'raise SystemExit(7)'])
            self.assertTrue(list(Path(folder).glob('*.stderr')))

    def test_manifest_tampering_and_traversal_rejected(self):
        import hashlib
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'data').write_bytes(b'good')
            manifest = root / 'sums'
            manifest.write_text(hashlib.sha256(b'good').hexdigest() + ' *data\n')
            self.assertEqual(verify_manifest(root, Path('sums'), 'sha256'), 1)
            (root / 'data').write_bytes(b'bad')
            with self.assertRaises(BuildError):
                verify_manifest(root, Path('sums'), 'sha256')
            manifest.write_text('0' * 64 + ' *../outside\n')
            with self.assertRaises(BuildError):
                verify_manifest(root, Path('sums'), 'sha256')

    def test_changes_outside_boot_tables_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            parent = Path(folder)
            left, right = parent / 'left', parent / 'right'
            left.mkdir(); right.mkdir()
            for tree in (left, right):
                (tree / 'boot.img').write_bytes(b'x' * 3000)
                (tree / 'minimal.squashfs').write_bytes(b'unchanged')
            before = inventory(left)
            content = bytearray((right / 'boot.img').read_bytes())
            content[8:64] = bytes(56)
            (right / 'boot.img').write_bytes(content)
            self.assertEqual(compare_trees(before, inventory(right), left, right, '/boot.img'), ['boot.img'])
            content[100] = 0
            (right / 'boot.img').write_bytes(content)
            with self.assertRaises(BuildError):
                compare_trees(before, inventory(right), left, right, '/boot.img')

    def test_metadata_preserves_iso_uid_gid(self):
        parsed = iso_metadata("-r--r--r-- 1 0 0 123 Sep 8 08:35 '/a file'\nnoise")
        self.assertEqual(parsed['/a file'][2:4], ['0', '0'])
        with self.assertRaises(BuildError):
            iso_metadata('no metadata')

    def test_optional_version_exit_does_not_weaken_other_commands(self):
        with tempfile.TemporaryDirectory() as folder:
            runner = Runner(Path(folder), 1)
            self.assertEqual(runner.run('version', [sys.executable, '-c', 'raise SystemExit(1)'], allowed=(0, 1)), '')
            with self.assertRaises(BuildError):
                runner.run('operation', [sys.executable, '-c', 'raise SystemExit(1)'])

    def test_changed_squashfs_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            parent = Path(folder)
            left, right = parent / 'left', parent / 'right'
            left.mkdir(); right.mkdir()
            (left / 'minimal.squashfs').write_bytes(b'original')
            (right / 'minimal.squashfs').write_bytes(b'changed')
            with self.assertRaises(BuildError):
                compare_trees(inventory(left), inventory(right), left, right, '/boot.img')

    def test_region_out_of_bounds_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            image = Path(folder) / 'image'
            image.write_bytes(b'1234')
            with self.assertRaises(BuildError):
                region_digest(image, 2, 8)

    def test_authentication_failure_preserves_workspace_without_build(self):
        from pipeline.devlite.build import build
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'work').mkdir()
            (root / 'artifacts').mkdir()
            source = root / 'original.iso'
            source.write_bytes(b'fixture')
            def command(runner, label, args, allowed=(0,)):
                if label == 'authenticate-source':
                    raise BuildError('GPG inválido na amostra')
                return 'unsquashfs version 4.6.1'
            with patch('pipeline.devlite.build.preflight', return_value=source), patch('pipeline.devlite.build.pvd_metadata', return_value={'timestamp': '2026090808365000'}), patch.object(Runner, 'run', command):
                with self.assertRaises(BuildError):
                    build(root)
            workspaces = list((root / 'work').glob('phase3b-*'))
            self.assertEqual(len(workspaces), 1)
            report = json.loads((workspaces[0] / 'report.json').read_text())
            self.assertEqual(report['status'], 'falhou')
            self.assertFalse(list((root / 'artifacts').iterdir()))
            self.assertEqual(source.read_bytes(), b'fixture')

    def test_reproduction_rejects_report_outside_artifacts(self):
        from pipeline.devlite.build import reproduce
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'artifacts').mkdir()
            outside = root / 'external.json'
            outside.write_text('{}')
            with patch('pipeline.devlite.build.preflight', return_value=root / 'source.iso'):
                with self.assertRaises(BuildError):
                    reproduce(root, outside)
            self.assertEqual(outside.read_text(), '{}')

    def test_mbr_code_and_load_size_must_be_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            source, result = Path(folder) / 'source', Path(folder) / 'result'
            block = bytes(510) + b'\x55\xaa'
            source.write_bytes(block); result.write_bytes(block)
            metadata = parse_boot(BOOT)
            compare_boot_metadata(source, result, metadata, metadata)
            result.write_bytes(b'x' + block[1:])
            with self.assertRaises(BuildError):
                compare_boot_metadata(source, result, metadata, metadata)

    def test_preflight_rejects_root(self):
        with patch('pipeline.devlite.build.pwd.getpwuid') as user:
            user.return_value.pw_name = 'root'
            with self.assertRaises(BuildError):
                preflight(ROOT)


if __name__ == '__main__':
    unittest.main()
