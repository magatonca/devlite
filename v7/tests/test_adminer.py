import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from v7 import adminer, adminer_action, desktop


class AdminerIntegrationTest(unittest.TestCase):
    def test_verified_payload_and_guest_commands(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'etc/apache2/conf-enabled').mkdir(parents=True)
            run = Mock()
            previous_umask = os.umask(0o077)
            try:
                adminer.apply(root, dict.fromkeys(adminer.REQUIRED), run)
            finally:
                os.umask(previous_umask)
            payload = root / 'usr/share/devlite-os/adminer'
            self.assertEqual(payload.stat().st_mode & 0o777, 0o755)
            self.assertEqual((payload / 'empty').stat().st_mode & 0o777, 0o755)
            config = root / 'etc/apache2/conf-enabled/devlite-adminer.conf'
            self.assertEqual(str(config.readlink()), '../conf-available/devlite-adminer.conf')
            self.assertIn('Listen 127.0.0.1:8081\nListen [::1]:8081', config.read_text())
            self.assertIn('SetHandler application/x-httpd-php', config.read_text())
            self.assertEqual(run.call_count, 4)
            run.assert_called_with(['/usr/sbin/apache2ctl', 'configtest'])

    def test_offline_services_do_not_launch_browser(self):
        run = Mock(side_effect=[SimpleNamespace(returncode=3), SimpleNamespace(returncode=3)])
        launch = Mock()
        self.assertIn('Apache, MariaDB', adminer_action.open_adminer(run, launch))
        launch.assert_not_called()
        self.assertTrue(all(call.args[0][1] == 'is-active' for call in run.call_args_list))

    def test_active_services_launch_fixed_firefox_endpoint(self):
        run = Mock(return_value=SimpleNamespace(returncode=0))
        launch = Mock()
        adminer_action.open_adminer(run, launch)
        launch.assert_called_once_with(['/snap/bin/firefox', adminer_action.URL], start_new_session=True)

    def test_devcontrol_overlay_compiles(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            app = root / 'usr/lib/devlite/devcontrol/app.py'
            app.parent.mkdir(parents=True)
            app.write_text(Path('v6/devcontrol/app.py').read_text())
            desktop.apply_devcontrol(root)
            text = app.read_text()
            compile(text, str(app), 'exec')
            self.assertEqual(text.count('Gerenciar banco de dados'), 1)
