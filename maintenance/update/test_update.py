from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from maintenance.update import updater
from maintenance.update.build import ROOT, build


class UpdateTests(unittest.TestCase):
    def test_download_reports_progress_for_all_assets(self):
        def fetch(_url, _limit, progress):
            progress(0.5)
            return b'fixture'

        with tempfile.TemporaryDirectory() as directory:
            reports = []
            folder = Path(directory)
            with patch.object(updater, 'fetch', side_effect=fetch):
                updater.download('v1.0.2', folder, lambda rate, message: reports.append((rate, message)))
            self.assertEqual(len(list(folder.iterdir())), 3)
            self.assertEqual(sorted(rate for rate, _ in reports), [rate for rate, _ in reports])
            self.assertEqual(reports[0][0], 0)
            self.assertEqual(reports[-1][0], 1)

    def test_latest_allows_skipping_intermediate_releases(self):
        import json

        release = {
            'tag_name': 'v1.0.8', 'draft': False, 'prerelease': False, 'body': 'Cumulativa',
            'assets': [{'name': name} for name in
                       ('devlite-update_1.0.8_amd64.deb', 'SHA256SUMS', 'SHA256SUMS.sig')],
        }
        with (patch.object(updater, 'fetch', return_value=json.dumps(release).encode()) as request,
              patch.object(updater, 'installed', return_value='1.0.1')):
            self.assertEqual(updater.latest(), ('v1.0.8', 'Cumulativa'))
            request.assert_called_once()

    def test_validate_versions(self):
        self.assertEqual(updater.package_name('v1.0.1'), 'devlite-update_1.0.1_amd64.deb')
        for tag in ('../v1.0.1', 'v01.0.1', 'v1.0.1-rc1', 'v1.0.1\n'):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                updater.version(tag)

    def test_redirect_rejects_non_release_hosts(self):
        handler = updater.ReleaseRedirect()
        req = updater.urllib.request.Request(updater.RELEASE)
        for url in ('http://github.com/example', 'https://github.com.attacker.invalid/x',
                    'https://github.com@localhost/x'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                handler.redirect_request(req, None, 302, 'Found', {}, url)

    def test_reject_insecure_keyring(self):
        with tempfile.TemporaryDirectory(prefix='devlite-') as folder:
            key = Path(folder) / 'keys.gpg'
            key.touch(mode=0o666)
            key.chmod(0o666)
            with self.assertRaisesRegex(ValueError, 'chaveiro'):
                updater.verify('v1.0.1', key.parent, key)

    def test_restore_selects_previous_success_and_revalidates(self):
        with tempfile.TemporaryDirectory(prefix='du-') as folder:
            state = Path(folder)
            releases = state / 'releases'
            releases.mkdir(mode=0o700)
            for tag in ('v1.0.1', 'v1.0.2', 'v1.0.3'):
                release = releases / tag
                release.mkdir(mode=0o700)
                if tag != 'v1.0.2':
                    (release / 'installed').touch()
            dpkg_package = releases / 'v1.0.1' / 'devlite-update_1.0.1_amd64.deb'
            real_lstat = Path.lstat

            def root_owned(path):
                info = real_lstat(path)
                return SimpleNamespace(st_uid=0, st_mode=info.st_mode)

            state.chmod(0o700)
            with (patch.object(updater, 'STATE', state),
                  patch.object(updater.os, 'geteuid', return_value=0),
                  patch.object(updater.os, 'umask'),
                  patch.object(Path, 'lstat', root_owned),
                  patch.object(updater, 'installed', return_value='1.0.3'),
                  patch.object(updater, 'newer', side_effect=lambda a, b: a > b),
                  patch.object(updater, 'verify', side_effect=[dpkg_package, Path('/previous.deb')]) as verify,
                  patch.object(updater, 'install_verified') as install):
                updater.privileged('restore')
                self.assertEqual(verify.call_args_list[0].args, ('v1.0.1', dpkg_package.parent))
                install.assert_called_once_with(dpkg_package, '1.0.1', Path('/previous.deb'), '1.0.3',
                                                downgrade=True, progress=None)
                self.assertIn('recuperação v1.0.1 · concluída', updater.history())

    def test_dependency_plan_rejects_changes_before_calling_dpkg(self):
        with (patch.object(updater.subprocess, 'check_output', return_value='Inst another-package (2)'),
              patch.object(updater.subprocess, 'run') as run):
            with self.assertRaisesRegex(ValueError, 'Dependências'):
                updater.install_verified(Path('/new.deb'), '1.0.2', Path('/old.deb'), '1.0.1')
            run.assert_not_called()

    def test_install_failure_restores_configured_previous_version(self):
        with (patch.object(updater.subprocess, 'check_output', return_value='Inst devlite-update [1.0.1] (1.0.2)'),
              patch.object(updater.subprocess, 'run', side_effect=[subprocess.CalledProcessError(1, 'dpkg'), None]) as run,
              patch.object(updater, 'package_state', side_effect=[('half-configured', '1.0.2'), ('installed', '1.0.1')])):
            with self.assertRaisesRegex(ValueError, 'versão 1.0.1 foi restaurada'):
                updater.install_verified(Path('/new.deb'), '1.0.2', Path('/old.deb'), '1.0.1')
            self.assertEqual(run.call_args_list[1].args[0][-1], '/old.deb')

    def test_package_manifest_signature_and_tamper_detection(self):
        tag = 'v' + (ROOT / 'VERSION').read_text().strip()
        with tempfile.TemporaryDirectory(prefix='du-', dir='/tmp') as folder:
            root = Path(folder)
            out = root / 'release'
            package = out / updater.package_name(tag)
            home = root / 'g'
            home.mkdir(mode=0o700)
            gpg = ['/usr/bin/gpg', '--homedir', str(home), '--batch']
            try:
                subprocess.run([*gpg, '--pinentry-mode', 'loopback', '--passphrase', '',
                                '--quick-generate-key', 'DevLite Fixture <fixture@invalid>',
                                'ed25519', 'sign', '1d'], check=True, capture_output=True, timeout=25)
                key = root / 'test.gpg'
                key.write_bytes(subprocess.check_output([*gpg, '--export'], timeout=10))
                key.chmod(0o644)
                build(out, key)
                build(root / 'repeat', key)
                self.assertEqual((out / 'SHA256SUMS').read_bytes(),
                                 (root / 'repeat' / 'SHA256SUMS').read_bytes())
                extracted = root / 'extracted'
                subprocess.run(['/usr/bin/dpkg-deb', '-x', str(package), str(extracted)], check=True)
                self.assertEqual((extracted / 'usr/share/keyrings/devlite-update.gpg').read_bytes(),
                                 key.read_bytes())
                secret = root / 'secret.gpg'
                secret.write_bytes(subprocess.check_output([*gpg, '--export-secret-keys'], timeout=10))
                with self.assertRaisesRegex(ValueError, 'chave pública'):
                    build(root / 'reject', secret)
                subprocess.run([*gpg, '--output', str(out / 'SHA256SUMS.sig'), '--detach-sign',
                                str(out / 'SHA256SUMS')], check=True, timeout=10)
                real_lstat = Path.lstat

                def lstat(path):
                    info = real_lstat(path)
                    if path == key:
                        return SimpleNamespace(st_uid=0, st_mode=info.st_mode)
                    return info

                with patch.object(Path, 'lstat', lstat):
                    self.assertEqual(updater.verify(tag, out, key), package)
                    with package.open('ab') as stream:
                        stream.write(b'modificado')
                    with self.assertRaisesRegex(ValueError, 'SHA-256 divergente'):
                        updater.verify(tag, out, key)
                    with (out / 'SHA256SUMS').open('a') as stream:
                        stream.write('modificado')
                    with self.assertRaises(subprocess.CalledProcessError):
                        updater.verify(tag, out, key)
            finally:
                subprocess.run(['/usr/bin/gpgconf', '--homedir', str(home), '--kill', 'gpg-agent'],
                               check=False, capture_output=True, timeout=10)
