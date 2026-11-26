import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from prototypes.devcontrol.collector import COMMANDS, DevControlCollector


ROOT = Path(__file__).resolve().parents[1]


class FakeRunner:
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.calls = []

    def __call__(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        command = Path(argv[0]).name
        response = self.responses.get((command, tuple(argv[1:])))
        if isinstance(response, Exception):
            raise response
        if response is None:
            return subprocess.CompletedProcess(argv, 0, '', '')
        return subprocess.CompletedProcess(argv, *response)


class DevControlTests(unittest.TestCase):
    def test_command_allowlist_is_fixed_and_never_uses_shell(self):
        runner = FakeRunner()
        collector = DevControlCollector(runner=runner)
        result, error = collector._run('systemctl', 'is-system-running')
        self.assertIsNone(error)
        self.assertEqual(result[0], 0)
        argv, options = runner.calls[0]
        self.assertEqual(argv[0], COMMANDS['systemctl'])
        self.assertIs(options['shell'], False)
        self.assertEqual(options['timeout'], 3)
        self.assertNotIn('sudo', COMMANDS)
        self.assertNotIn('pkexec', COMMANDS)

    def test_unknown_command_key_is_rejected_without_execution(self):
        runner = FakeRunner()
        result, error = DevControlCollector(runner=runner)._run('arbitrary-command')
        self.assertIsNone(result)
        self.assertIn('não permitido', error)
        self.assertEqual(runner.calls, [])

    def test_command_keeps_only_required_graphical_session_environment(self):
        runner = FakeRunner()
        with patch.dict(os.environ, {
            'DBUS_SESSION_BUS_ADDRESS': 'unix:path=/run/user/1000/bus',
            'XDG_RUNTIME_DIR': '/run/user/1000',
            'PATH': '/tmp/untrusted',
            'LD_PRELOAD': '/tmp/untrusted.so',
        }, clear=True):
            DevControlCollector(runner=runner)._run('xfconf-query', '-c', 'xsettings', '-p', '/Net/ThemeName')
        environment = runner.calls[0][1]['env']
        self.assertEqual(environment['DBUS_SESSION_BUS_ADDRESS'], 'unix:path=/run/user/1000/bus')
        self.assertEqual(environment['XDG_RUNTIME_DIR'], '/run/user/1000')
        self.assertEqual(environment['PATH'], '/usr/sbin:/usr/bin:/sbin:/bin')
        self.assertNotIn('LD_PRELOAD', environment)

    def test_command_timeout_and_missing_dependency_are_reported(self):
        runner = FakeRunner({
            ('php', ('--version',)): FileNotFoundError(),
            ('node', ('--version',)): subprocess.TimeoutExpired('node', 3),
        })
        collector = DevControlCollector(runner=runner)
        missing, missing_error = collector._run('php', '--version')
        timed_out, timeout_error = collector._run('node', '--version')
        self.assertIsNone(missing)
        self.assertEqual(missing_error, 'componente não instalado')
        self.assertIsNone(timed_out)
        self.assertEqual(timeout_error, 'tempo limite excedido')

    def test_overview_reads_identity_cpu_memory_and_disk(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'usr/share/devlite-os').mkdir(parents=True)
            (root / 'usr/share/devlite-os/identity.json').write_text(
                json.dumps({'name': 'DevLite OS', 'version': '1.0'})
            )
            (root / 'etc').mkdir()
            (root / 'etc/os-release').write_text('PRETTY_NAME="Xubuntu 24.04"\n')
            (root / 'proc').mkdir()
            (root / 'proc/cpuinfo').write_text('model name : Example CPU\n')
            (root / 'proc/meminfo').write_text(
                'MemTotal:       2097152 kB\nMemAvailable:    1048576 kB\n'
            )
            (root / 'sys/class/dmi/id').mkdir(parents=True)
            (root / 'sys/class/dmi/id/sys_vendor').write_text('Example Vendor\n')
            (root / 'sys/class/dmi/id/product_name').write_text('Example VM\n')
            disk = SimpleNamespace(total=80 * 1024**3, free=24 * 1024**3)
            values = dict(DevControlCollector(root=root, disk_usage=lambda _p: disk).overview())
        self.assertEqual(values['Sistema'], 'DevLite OS 1.0')
        self.assertIn('Example CPU', values['CPU'])
        self.assertIn('1024 MiB disponíveis', values['Memória RAM'])
        self.assertEqual(values['Armazenamento raiz'], '24 GiB livres de 80 GiB')
        self.assertEqual(values['Equipamento'], 'Example Vendor Example VM')

    def test_network_parses_interfaces_routes_and_dns(self):
        runner = FakeRunner({
            ('ip', ('-j', 'address')): (
                0,
                json.dumps([{
                    'ifname': 'eth0',
                    'operstate': 'UP',
                    'addr_info': [
                        {'local': '192.0.2.10', 'prefixlen': 24, 'scope': 'global'},
                        {'local': '127.0.0.1', 'prefixlen': 8, 'scope': 'host'},
                    ],
                }]),
                '',
            ),
            ('ip', ('-j', 'route', 'show', 'default')): (
                0, json.dumps([{'dst': 'default', 'gateway': '192.0.2.1', 'dev': 'eth0'}]), '',
            ),
            ('resolvectl', ('dns',)): (0, 'Global: 192.0.2.53\n', ''),
            ('nmcli', ('-t', '-f', 'NAME,TYPE,DEVICE', 'connection', 'show', '--active')): (
                0, 'Home:vpn:tun0\nWired:802-3-ethernet:eth0\n', '',
            ),
        })
        values = dict(DevControlCollector(runner=runner).network())
        self.assertIn('eth0 (UP): 192.0.2.10/24', values['Interfaces e endereços'])
        self.assertNotIn('127.0.0.1', values['Interfaces e endereços'])
        self.assertIn('192.0.2.1', values['Gateway'])
        self.assertIn('192.0.2.53', values['DNS por interface'])
        self.assertEqual(values['VPN ativa'], 'Home:vpn:tun0')

    def test_missing_commands_are_presented_per_development_tool(self):
        runner = FakeRunner({
            ('php', ('--version',)): FileNotFoundError(),
            ('node', ('--version',)): (0, 'v26.1.0\n', ''),
            ('code', ('--version',)): FileNotFoundError(),
        })
        values = dict(DevControlCollector(runner=runner).development())
        self.assertIn('Não disponível', values['PHP'])
        self.assertEqual(values['Node.js'], 'v26.1.0')
        self.assertIn('Não disponível', values['Visual Studio Code'])

    def test_service_state_is_reported_without_mutation(self):
        runner = FakeRunner({
            ('systemctl', (
                'show', 'docker.service',
                '--property=LoadState,ActiveState,SubState,UnitFileState',
                '--no-pager',
            )): (
                0,
                'LoadState=loaded\nActiveState=inactive\nSubState=dead\nUnitFileState=masked\n',
                '',
            ),
        })
        service = DevControlCollector(runner=runner)._service('docker.service')
        self.assertEqual(service, {'state': 'Parado', 'startup': 'bloqueada'})
        self.assertTrue(all(call[0][1] == 'show' for call in runner.calls))

    def test_docker_limits_displayed_container_rows(self):
        output = ''.join(f'c{i}\timage{i}\tUp 1 minute\n' for i in range(12))
        runner = FakeRunner({
            ('systemctl', (
                'show', 'docker.service',
                '--property=LoadState,ActiveState,SubState,UnitFileState',
                '--no-pager',
            )): (0, 'LoadState=loaded\nActiveState=active\nUnitFileState=enabled\n', ''),
            ('docker', ('ps', '--format', '{{.Names}}\t{{.Image}}\t{{.Status}}')): (0, output, ''),
        })
        values = dict(DevControlCollector(runner=runner).docker())
        self.assertIn('c9', values['Contêineres em execução'])
        self.assertNotIn('c10', values['Contêineres em execução'])
        self.assertIn('e mais 2', values['Contêineres em execução'])

    def test_appearance_only_queries_fixed_xfconf_channels(self):
        runner = FakeRunner({
            ('xfconf-query', ('-c', 'xsettings', '-p', '/Net/ThemeName')): (0, 'Greybird-dark\n', ''),
            ('xfconf-query', ('-c', 'xsettings', '-p', '/Net/IconThemeName')): (0, 'elementary-xfce-dark\n', ''),
            ('xfconf-query', ('-c', 'xfce4-desktop', '-l', '-v')): (
                0, '/backdrop/screen0/monitor0/workspace0/last-image: /tmp/wall.svg\n', '',
            ),
            ('xfconf-query', ('-c', 'xfce4-panel', '-l', '-v')): (
                0, '/panels: 1\n/panels/panel-1/size: 40\n', '',
            ),
        })
        values = dict(DevControlCollector(runner=runner).appearance())
        self.assertEqual(values['Tema GTK'], 'Greybird-dark')
        self.assertEqual(values['Wallpaper por monitor'], '/tmp/wall.svg')
        self.assertIn('/panels/panel-1/size: 40', values['Painel XFCE'])
        self.assertTrue(all(call[0][0] == COMMANDS['xfconf-query'] for call in runner.calls))

    def test_security_and_updates_are_queries_only(self):
        runner = FakeRunner({
            ('systemctl', (
                'show', 'ufw.service',
                '--property=LoadState,ActiveState,SubState,UnitFileState',
                '--no-pager',
            )): (0, 'LoadState=not-found\nActiveState=inactive\n', ''),
            ('apt-check', ('--human-readable',)): (0, '0 packages can be updated.\n', ''),
            ('systemctl', ('is-system-running', '--no-pager')): (0, 'running\n', ''),
        })
        values = dict(DevControlCollector(runner=runner).security())
        self.assertEqual(values['Firewall UFW'], 'Não instalado')
        self.assertIn('0 packages', values['Atualizações no cache local'])
        self.assertEqual(values['Estado do systemd'], 'running')
        self.assertIn('Somente consulta', values['Escopo'])
        self.assertFalse(any('upgrade' in arg or 'start' in arg for argv, _ in runner.calls for arg in argv))

    def test_snapshot_keeps_all_sections_when_a_collector_fails(self):
        class PartiallyBrokenCollector(DevControlCollector):
            def network(self):
                raise RuntimeError('fixture failure')

        snapshot = PartiallyBrokenCollector(runner=FakeRunner()).snapshot()
        self.assertEqual(len(snapshot), 7)
        self.assertIn('Falha inesperada', snapshot['Rede'][0][1])
        self.assertIn('Sistema', dict(snapshot['Visão geral']))

    def test_desktop_manifest_and_source_have_no_admin_launcher(self):
        folder = ROOT / 'prototypes/devcontrol'
        desktop = (folder / 'devcontrol.desktop').read_text()
        manifest = json.loads((folder / 'manifest.json').read_text())
        app = (folder / 'app.py').read_text()
        self.assertIn('Terminal=false', desktop)
        self.assertIn('devcontrol.desktop', manifest['target_paths'])
        self.assertFalse(manifest['privileged_operations'])
        self.assertNotIn('pkexec', app)
        self.assertNotIn('sudo', app)
        self.assertNotIn('devlite-service-control', app)


if __name__ == '__main__':
    unittest.main()
