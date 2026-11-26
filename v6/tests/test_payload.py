import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from v6.devcontrol.metrics import DevControlCollector
from v6.devcontrol.services import ACTIONS, catalog
from v6.payload import APACHE_LINK, DEVCONTROL, ROOT, apply


class PayloadTests(unittest.TestCase):
    def test_base_and_live_payloads(self):
        for target in ('base', 'live'):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as directory:
                guest = Path(directory).resolve()
                written = apply(guest, target)
                self.assertTrue((guest / APACHE_LINK).is_file())
                self.assertIn(f'{DEVCONTROL}/collector.py', written)
                self.assertEqual(sum(name.endswith('slide_pt_BR.html') for name in written),
                                 4 if target == 'live' else 0)
                self.assertIn('ServerName localhost', (guest / APACHE_LINK).read_text())
                policy = guest / 'usr/share/polkit-1/actions/org.devlite.v6.services.policy'
                action = ET.parse(policy).find('action')
                self.assertEqual(action.findtext('defaults/allow_active'), 'auth_admin')
                self.assertEqual(action.findtext('defaults/allow_any'), 'no')
                self.assertEqual(action.findtext('annotate'), '/usr/libexec/devlite-services-v6')

    def test_cpu_delta_excludes_guest_time(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'proc').mkdir()
            stat = root / 'proc/stat'
            stat.write_text('cpu 10 0 20 60 10 0 0 0 5 0\n')
            collector = DevControlCollector(root)
            self.assertEqual(collector.cpu_usage(), 'Coletando amostra')
            stat.write_text('cpu 20 0 20 70 10 0 0 0 10 0\n')
            self.assertEqual(collector.cpu_usage(), '50%')

    def test_services_keep_fixed_ids_and_actions(self):
        rows = catalog(ROOT / 'v6/overlay')
        self.assertTrue({'docker', 'docker-socket', 'containerd', 'ssh-socket'} <=
                        {row['id'] for row in rows})
        self.assertNotIn('shell', ACTIONS)


if __name__ == '__main__':
    unittest.main()
