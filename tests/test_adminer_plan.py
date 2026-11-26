import ast,unittest
from pathlib import Path
from urllib.parse import urlsplit
from prototypes.control2.adminer_model import (URL,IPV6_URL,LISTEN,APACHE,browser_request,loopback_peer,release_gate)
from prototypes.control2.model import SimulatedBackend
ROOT=Path(__file__).resolve().parents[1]
class AdminerPlanTests(unittest.TestCase):
    def test_exact_ipv4_ipv6_listeners(self):
        self.assertEqual(LISTEN.splitlines(),['Listen 127.0.0.1:8081','Listen [::1]:8081'])
        for bad in ['0.0.0.0','[::]:','Listen 80']:self.assertNotIn(bad,LISTEN)
    def test_connection_model_denies_external_and_malformed(self):
        for peer in ['192.168.1.10','203.0.113.1','2001:db8::1','0.0.0.0','::','localhost','127.0.0.1, 203.0.113.1','not an IP']:
            self.assertFalse(loopback_peer(peer))
        self.assertTrue(loopback_peer('127.0.0.1'));self.assertTrue(loopback_peer('::1'))
    def test_native_adminer_directory_not_http_exposed(self):
        self.assertIn('<Directory "/usr/share/adminer">',APACHE)
        self.assertIn('Require all denied',APACHE)
        self.assertNotIn('Require all granted',APACHE)
        self.assertIn('AllowOverride None',APACHE)
    def test_wrapper_alias_and_acl_defense(self):
        self.assertIn('Alias "/devlite-adminer" "/usr/share/devlite-os/adminer/index.php"',APACHE)
        self.assertGreaterEqual(APACHE.count('Require ip 127.0.0.1 ::1'),1)
        self.assertIn('Require env devlite_adminer_host_ok',APACHE)
        self.assertIn('Options -Indexes',APACHE)
    def test_default_urls_no_credentials_or_query(self):
        for url in [URL,IPV6_URL]:
            p=urlsplit(url);self.assertEqual(p.scheme,'http');self.assertIsNone(p.username);self.assertIsNone(p.password)
            self.assertFalse(p.query);self.assertFalse(p.fragment);self.assertEqual(p.path,'/devlite-adminer')
    def test_open_requires_both_services(self):
        for apache,mariadb in [(False,True),(True,False),(False,False)]:
            with self.assertRaises(ValueError):browser_request(apache,mariadb)
        self.assertEqual(browser_request(True,True),URL)
    def test_truthy_state_string_does_not_bypass_precondition(self):
        with self.assertRaises(ValueError):browser_request('failed','active')
    def test_open_check_does_not_start_services(self):
        b=SimulatedBackend();before=b.all_status()
        with self.assertRaises(ValueError):browser_request(b.status('apache').state=='active',b.status('mariadb').state=='active')
        self.assertEqual(b.all_status(),before)
    def test_signed_metadata_is_not_artifact_integrity(self):
        self.assertFalse(release_gate(True,False,True,True))
    def test_security_review_and_runtime_are_mandatory(self):
        self.assertFalse(release_gate(True,True,False,True))
        self.assertFalse(release_gate(True,True,True,False))
        self.assertTrue(release_gate(True,True,True,True))
    def test_unknown_values_fail_closed(self):
        self.assertFalse(release_gate(True,True,'approved',True))
        self.assertFalse(release_gate(True,True,None,True))
    def test_gui_database_button_never_launches_or_mutates_real_services(self):
        tree=ast.parse((ROOT/'prototypes/control2/app.py').read_text())
        method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='databases')
        code=ast.unparse(method)
        for forbidden in ['operate(', 'pkexec','subprocess','webbrowser','launch_default_for_uri']:self.assertNotIn(forbidden,code)
        self.assertIn('browser_request',code)
    def test_model_has_no_execution_or_database_imports(self):
        tree=ast.parse((ROOT/'prototypes/control2/adminer_model.py').read_text())
        imports=[n.name for x in ast.walk(tree) if isinstance(x,ast.Import) for n in x.names]
        self.assertEqual(imports,['ipaddress'])

    def test_actual_packaged_alias_and_etc_tree_are_denied(self):
        self.assertIn('<Directory "/etc/adminer">',APACHE)
        self.assertIn('<LocationMatch "^/adminer(?:/|$)">',APACHE)
        self.assertNotIn('Require all granted',APACHE)
