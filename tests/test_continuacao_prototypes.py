import hashlib,json,unittest,xml.etree.ElementTree as ET
from pathlib import Path
from prototypes.control2 import adminer_model as a
from prototypes.control2.model import SimulatedBackend,OperationError
R=Path(__file__).resolve().parents[1]
class ContinuacaoTests(unittest.TestCase):
    def test_adminer_vendor_binding(self):
        m=json.loads((R/'prototypes/adminer/manifest.json').read_text())
        self.assertEqual(hashlib.sha256((R/m['vendor_source']).read_bytes()).hexdigest(),m['sha256'])
        self.assertIn(m['sha256'],(R/'prototypes/adminer/index.php').read_text())
    def test_dedicated_vhost(self):
        self.assertEqual(a.APACHE,(R/'prototypes/adminer/apache.conf').read_text())
        self.assertIn('<VirtualHost 127.0.0.1:8081 [::1]:8081>',a.APACHE)
        self.assertIn('http://127.0.0.1:8081/',a.URL)
        self.assertNotIn('Listen 80',a.APACHE)
        self.assertIn('Require all denied',a.APACHE)
    def test_modern_payload_hashes_and_xml(self):
        base=R/'prototypes/devlite-modern'
        m=json.loads((base/'manifest.json').read_text());self.assertFalse(m['applied'])
        self.assertEqual(len(m['files']),7)
        for name,digest in m['files'].items():
            f=base/'payload'/name
            self.assertEqual(hashlib.sha256(f.read_bytes()).hexdigest(),digest)
            if f.suffix=='.xml':ET.fromstring(f.read_text())
    def test_bounded_simulated_logs(self):
        b=SimulatedBackend()
        for _ in range(80):b.operate('apache','start')
        self.assertEqual(len(b.logs('apache').splitlines()),50)
    def test_boot_and_runtime_independent(self):
        b=SimulatedBackend();b.operate('mariadb','enable')
        self.assertEqual(b.status('mariadb').state,'inactive')
        b.operate('mariadb','start');b.operate('mariadb','disable',confirmed=True)
        self.assertEqual(b.status('mariadb').state,'active')
        self.assertFalse(b.status('mariadb').autostart)
    def test_failure_preserves_state(self):
        b=SimulatedBackend();before=b.all_status();b.next_error='Autorização negada'
        with self.assertRaises(OperationError):b.operate('apache','restart',confirmed=True)
        self.assertEqual(before,b.all_status())
