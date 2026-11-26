import ast,unittest,xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from prototypes.control2.model import (SimulatedBackend,OperationError,SERVICES,LABELS,
    normalize_state,requires_confirmation,admin_argv)
ROOT=Path(__file__).resolve().parents[1]

class Control2PrototypeTests(unittest.TestCase):
    def test_exact_service_allowlist(self):
        self.assertEqual(SERVICES,{'apache':'apache2.service','mariadb':'mariadb.service','docker':'docker.service'})
    def test_all_four_display_states(self):
        self.assertEqual(set(LABELS),{'active','inactive','failed','unknown'})
        for active,expected in [('active','active'),('inactive','inactive'),('failed','failed'),('activating','unknown'),('deactivating','unknown')]:
            self.assertEqual(normalize_state('loaded',active),expected)
        self.assertEqual(normalize_state('not-found','active'),'unknown')
    def test_start_changes_runtime_only(self):
        b=SimulatedBackend();new=b.operate('mariadb','start')
        self.assertEqual(new.state,'active');self.assertFalse(new.autostart)
    def test_stop_requires_confirmation_and_preserves_previous_state(self):
        b=SimulatedBackend();old=b.status('apache')
        with self.assertRaises(OperationError):b.operate('apache','stop')
        self.assertEqual(b.status('apache'),old)
        self.assertEqual(b.operate('apache','stop',True).state,'inactive')
    def test_restart_requires_confirmation(self):
        b=SimulatedBackend()
        with self.assertRaises(OperationError):b.operate('docker','restart')
        self.assertEqual(b.operate('docker','restart',True).state,'active')
    def test_enable_does_not_start_service(self):
        b=SimulatedBackend();new=b.operate('mariadb','enable')
        self.assertTrue(new.autostart);self.assertEqual(new.state,'inactive')
    def test_disable_does_not_stop_service(self):
        b=SimulatedBackend();b.operate('apache','enable')
        with self.assertRaises(OperationError):b.operate('apache','disable')
        new=b.operate('apache','disable',True)
        self.assertFalse(new.autostart);self.assertEqual(new.state,'active')
    def test_rejects_arbitrary_service_and_shell_input(self):
        for service in ['ssh','apache; reboot','--all','../docker','docker.service']:
            with self.subTest(service=service):
                with self.assertRaises(OperationError):admin_argv(service,'start')
                with self.assertRaises(OperationError):SimulatedBackend().operate(service,'start')
    def test_rejects_arbitrary_operation(self):
        for action in ['unmask','daemon-reload','reset-failed','start; reboot','--root=/']:
            with self.assertRaises(OperationError):admin_argv('apache',action)
    def test_command_is_fixed_vector_only(self):
        self.assertEqual(admin_argv('docker','restart'),['/usr/bin/pkexec','/usr/libexec/devlite-control2-helper','restart','docker'])
    def test_denied_authentication_preserves_state(self):
        b=SimulatedBackend();old=b.status('mariadb');b.next_error='Autorização cancelada'
        with self.assertRaisesRegex(OperationError,'cancelada'):b.operate('mariadb','start')
        self.assertEqual(old,b.status('mariadb'))
        self.assertEqual(b.operate('mariadb','start').state,'active')
    def test_missing_unit_does_not_affect_other_services(self):
        b=SimulatedBackend();b.unavailable('docker')
        self.assertEqual(b.status('docker').state,'unknown')
        with self.assertRaises(OperationError):b.operate('docker','start')
        self.assertEqual(b.operate('apache','stop',True).state,'inactive')
    def test_logs_are_bounded_and_simulated(self):
        b=SimulatedBackend()
        for _ in range(60):b.operate('apache','start')
        self.assertLessEqual(len(b.logs('apache').splitlines()),50)
        self.assertTrue(all('SIMULAÇÃO' in x for x in b.logs('apache').splitlines()))
    def test_returned_state_immutable(self):
        b=SimulatedBackend();state=b.status('apache')
        with self.assertRaises(AttributeError):state.state='inactive'
    def test_information_is_explicitly_fictional(self):
        values=SimulatedBackend().system_info()
        for key in ['PHP','Node.js','TypeScript','Composer','Git','CPU','Memória','Disco','Endereço IP','Gateway','DNS','Versão']:self.assertIn(key,values)
        self.assertTrue(all('simulad' in x or 'demonstração' in x for x in values.values()))
    def test_serial_worker_recovers_after_error(self):
        b=SimulatedBackend();b.next_error='Serviço indisponível'
        with ThreadPoolExecutor(max_workers=1) as pool:
            with self.assertRaises(OperationError):pool.submit(b.operate,'apache','start').result(timeout=2)
            self.assertEqual(pool.submit(b.operate,'apache','stop',True).result(timeout=2).state,'inactive')
    def test_policy_requires_admin_and_active_session(self):
        root=ET.parse(ROOT/'prototypes/control2/policy-proposal.xml').getroot()
        self.assertEqual(root.findtext('action/defaults/allow_active'),'auth_admin')
        self.assertEqual(root.findtext('action/defaults/allow_any'),'no')
        self.assertEqual(root.findtext('action/defaults/allow_inactive'),'no')
        self.assertEqual(len(root.findall('action')),1)
    def test_prototype_has_no_host_execution_backend(self):
        for name in ['model.py','app.py']:
            tree=ast.parse((ROOT/'prototypes/control2'/name).read_text())
            imports=[]
            for node in ast.walk(tree):
                if isinstance(node,ast.Import):imports.extend(n.name.split('.')[0] for n in node.names)
                if isinstance(node,ast.ImportFrom):imports.append((node.module or '').split('.')[0])
            self.assertFalse({'subprocess','socket','ctypes','os'} & set(imports))
    def test_html_preview_has_no_external_resources_or_scripts(self):
        text=(ROOT/'prototypes/control2/preview.html').read_text()
        self.assertNotIn('<script',text);self.assertNotIn('src=',text);self.assertNotIn('https://',text)
        self.assertIn('dados fictícios',text)
