import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from v6.assemble import open_pack, render_catalog, render_grub
from v6.pack import LEAVES, Mounts, ROOT, STACKS


class BuildTests(unittest.TestCase):
    def test_layer_names_extend_casper_prefixes(self):
        for target, name in LEAVES.items():
            self.assertEqual(name, STACKS[target][-1].replace('.squashfs', '.v6.squashfs'))

    def test_catalog_and_grub_use_the_new_leaves(self):
        source = ('- default: true\n  id: xubuntu-desktop-minimal\n'
                  '  description:\n    en: Minimal.\n'
                  '  name:\n    en: DevLite OS 1.0\n'
                  f'  path: {STACKS["base"][-1]}\n  size: 10\n')
        catalog = render_catalog(source, 7)
        self.assertIn(f'  path: {LEAVES["base"]}\n  size: 17\n', catalog)
        self.assertIn('  id: xubuntu-desktop-minimal\n', catalog)
        self.assertIn('pt_BR: "Instalação mínima do DevLite OS 1.0."', catalog)
        self.assertIn('pt_BR: "DevLite OS 1.0"', catalog)
        opt = f'linux /casper/vmlinuz username=devlite layerfs-path={STACKS["live"][-1]} quiet\n'
        self.assertEqual(render_grub(opt), opt.replace(STACKS['live'][-1], LEAVES['live']))
        with self.assertRaises(ValueError):
            render_grub('linux /casper/vmlinuz quiet\n')

    def test_mount_scope_and_cleanup_order(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            job = base / 'job'
            first = job / 'first'
            second = job / 'second'
            first.mkdir(parents=True)
            second.mkdir()
            symlink = job / 'outside'
            symlink.symlink_to(base)
            runner = Mock()
            mounts = Mounts(job, runner)
            for path in (base, symlink):
                with self.assertRaises(ValueError):
                    mounts.mount('escape', [], path)
            runner.run.assert_not_called()
            for path in (first, second):
                mounts.mount('tmpfs', ['-t', 'tmpfs', 'tmpfs'], path)
            with self.assertRaises(ValueError):
                mounts.unmount(first)
            mounts.unmount(second)
            mounts.unmount(first)
            self.assertEqual(mounts.paths, [])

    def test_assembler_rejects_workspace_path_as_receipt(self):
        with self.assertRaisesRegex(ValueError, 'Unapproved'):
            open_pack(ROOT / 'work/pack-fakefake')
