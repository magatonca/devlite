"""Aceitação estática da ISO final; exige workspace real concluído, não usa VM."""
import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class ResultImageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace = Path(os.environ['DEVLITE_MINIMAL_WORKSPACE'])
        cls.report = json.loads((cls.workspace / 'customization-report.json').read_text())
        if cls.report['status'] != 'validado_estruturalmente':
            raise AssertionError('Construção não foi promovida')
        cls.casper = cls.workspace / 'result-iso-tree/casper'
        cls.source = cls.workspace / 'original-casper'
        cls.payloads = json.loads((cls.workspace / 'configuration.json').read_text())

    def read(self, image, member):
        return subprocess.run(['unsquashfs', '-processors', '1', '-data-queue', '64', '-frag-queue', '64', '-cat', str(image), member], capture_output=True, check=True).stdout

    def content_hash(self, image, member):
        with tempfile.TemporaryFile(dir=self.workspace) as errors:
            process = subprocess.Popen(['unsquashfs', '-processors', '1', '-data-queue', '64', '-frag-queue', '64', '-cat', str(image), member], stdout=subprocess.PIPE, stderr=errors)
            try:
                digest = hashlib.file_digest(process.stdout, 'sha256').hexdigest()
            finally:
                process.stdout.close()
                code = process.wait()
            self.assertEqual(code, 0)
        return digest

    def test_language_keyboard_and_timezone_in_installed_source(self):
        image = self.casper / 'minimal.squashfs'
        self.assertIn(b'LANG=pt_BR.UTF-8', self.read(image, 'etc/locale.conf'))
        self.assertIn(b'LANGUAGE=pt_BR:pt', self.read(image, 'etc/locale.conf'))
        self.assertIn(b'XKBMODEL="abnt2"', self.read(image, 'etc/default/keyboard'))
        self.assertIn(b'XKBLAYOUT="br"', self.read(image, 'etc/default/keyboard'))
        self.assertEqual(self.read(image, 'etc/timezone'), b'America/Sao_Paulo\n')
        for name, target in (('etc/default/locale', '../locale.conf'),
                             ('etc/os-release', '../usr/lib/os-release'),
                             ('etc/localtime', '../usr/share/zoneinfo/America/Sao_Paulo')):
            listing = subprocess.run(['unsquashfs', '-lln', str(image), name], capture_output=True, check=True, text=True).stdout
            self.assertIn('-> ' + target, listing)

    def test_identity_and_ubuntu_compatibility(self):
        image = self.casper / 'minimal.squashfs'
        identity = self.read(image, 'usr/lib/os-release').decode()
        self.assertIn('NAME="DevLite OS"', identity)
        self.assertIn('ID=ubuntu\n', identity)
        self.assertIn('UBUNTU_CODENAME=noble', identity)
        self.assertIn(b'DevLite OS', self.read(image, 'etc/devlite-release'))

    def test_compiled_locale_and_all_configuration_payloads(self):
        image = self.casper / 'minimal.squashfs'
        regular = {name: value for name, value in self.payloads.items() if value['kind'] == 'file'}
        self.assertTrue(any(name.startswith('usr/lib/locale/pt_BR.utf8/') for name in regular))
        for name, value in regular.items():
            with self.subTest(path=name):
                self.assertEqual(self.content_hash(image, name), value['sha256'])

    def test_package_state_is_unchanged_in_both_layers(self):
        for name in ('minimal.squashfs', 'minimal.live.squashfs'):
            for member in ('var/lib/dpkg/status',):
                with self.subTest(layer=name, member=member):
                    self.assertEqual(self.content_hash(self.source / name, member), self.content_hash(self.casper / name, member))

    def test_original_desktop_bootstrap_snap_is_preserved(self):
        member = 'var/lib/snapd/snaps/ubuntu-desktop-bootstrap_572.snap'
        name = 'minimal.live.squashfs'
        self.assertEqual(self.content_hash(self.source / name, member), self.content_hash(self.casper / name, member))


if __name__ == '__main__':
    unittest.main()
