import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import xml.etree.ElementTree as ET

from v7 import vscode
from v7.desktop import ICON, apply
from v7.firefox import FINGERPRINT, primary_fingerprints
from v7.storage import GIB, budgets


class SecurityTests(unittest.TestCase):
    def test_apparmor_override_only_in_live_and_keeps_non_casper_guard(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            icon = root / ICON
            icon.parent.mkdir(parents=True)
            icon.write_text('<svg/>')
            path = 'etc/systemd/system/apparmor.service.d/30-devlite-casper.conf'
            self.assertNotIn(path, apply(root))
            self.assertIn(path, apply(root, live=True))
            conditions = [line for line in (root / path).read_text().splitlines()
                          if line.startswith('Condition')]
            self.assertEqual(conditions, ['ConditionPathExists=', 'ConditionSecurity=apparmor',
                                          'ConditionPathExists=!/run/live/overlay/work'])

    def test_vscode_client_invokes_exact_helper_and_checks_result(self):
        process = SimpleNamespace(returncode=0)
        with patch.object(vscode.subprocess, 'run', return_value=process) as run, patch.object(
                vscode, 'installed', return_value=True):
            vscode.install()
            self.assertEqual(run.call_args.args[0], ['/usr/bin/pkexec', vscode.HELPER])
        with patch.object(vscode.subprocess, 'run', return_value=process), patch.object(
                vscode, 'installed', return_value=False):
            with self.assertRaisesRegex(RuntimeError, 'não foi confirmada'):
                vscode.install()
        policy = Path('v7/overlay/usr/share/polkit-1/actions/org.devlite.v7.vscode.policy')
        action = ET.parse(policy).find('action')
        self.assertEqual(action.findtext('annotate'), vscode.HELPER)
        self.assertEqual(action.findtext('defaults/allow_active'), 'auth_admin')
        self.assertEqual(action.findtext('defaults/allow_inactive'), 'no')

    def test_budgets_account_for_simultaneously_retained_outputs(self):
        result = budgets(4 * GIB)
        self.assertEqual(result['frontend'], 16 * GIB)
        self.assertEqual(result['snap'], 10 * GIB)
        self.assertEqual(result['iso'], 25 * GIB)

    def test_mozilla_primary_fingerprint_ignores_subkeys(self):
        output = f'pub::::::::::\nfpr:::::::::{FINGERPRINT}:\nsub::::::::::\nfpr:::::::::OTHER:\n'
        self.assertEqual(primary_fingerprints(output), [FINGERPRINT])

    def test_firefox_defaults_preserve_unrelated_applications(self):
        from v7.browser import DESKTOP, render_mime

        inherited = ('[Default Applications]\ntext/html=epiphany.desktop;\n'
                     'application/xhtml+xml=epiphany.desktop;\n'
                     'x-scheme-handler/http=epiphany.desktop;\n'
                     'x-scheme-handler/https=epiphany.desktop;\n'
                     'application/pdf=atril.desktop;\n')
        expected = inherited.replace('epiphany.desktop', DESKTOP)
        self.assertEqual(render_mime(inherited), expected)
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            render_mime(inherited + 'text/html=unknown.desktop;\n')

    def test_epiphany_offline_removal_refuses_shared_dependencies(self):
        from v7.browser import remove_epiphany
        from unittest.mock import Mock

        proposed = 'Purg epiphany-browser [46.5]\nPurg epiphany-browser-data [46.5]\n'
        run = Mock(return_value=proposed)
        remove_epiphany(run)
        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args.args[0][-3:],
                         ['purge', 'epiphany-browser', 'epiphany-browser-data'])
        for call in run.call_args_list:
            command = call.args[0]
            self.assertIn('--no-download', command)
            self.assertEqual(command[1:3], ['-o', 'DPkg::Use-Pty=0'])
        run = Mock(return_value=proposed + 'Purg libwebkitgtk [1.0]\n')
        with self.assertRaisesRegex(ValueError, 'outside'):
            remove_epiphany(run)
        self.assertEqual(run.call_count, 1)
