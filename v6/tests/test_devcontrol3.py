import os
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from v6.devcontrol import app, services
from v6.payload import DEVCONTROL, RETIRED, ROOT, apply


class DevControlReplacementTests(unittest.TestCase):
    def test_upgrade_replaces_both_v5_installations(self):
        for target in ('base', 'live'):
            with self.subTest(target=target), TemporaryDirectory() as directory:
                guest = Path(directory).resolve()
                shutil.copytree(ROOT / 'v5/overlay', guest, dirs_exist_ok=True)
                shutil.copytree(ROOT / 'v5/devcontrol', guest / DEVCONTROL,
                                ignore=shutil.ignore_patterns('__pycache__'))
                for name in RETIRED:
                    path = guest / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    if not path.exists():
                        path.write_text('legacy')
                apply(guest, target)
                self.assertFalse(any((guest / name).exists() for name in RETIRED))
                launchers = [p for p in (guest / 'usr/share/applications').glob('*.desktop')
                             if '/usr/lib/devlite/devcontrol/' in p.read_text()]
                self.assertEqual([p.name for p in launchers], ['devcontrol.desktop'])
                self.assertIn('Name=DevControl 3.0', launchers[0].read_text())
                self.assertEqual((guest / DEVCONTROL / 'app.py').read_text(),
                                 (ROOT / 'v6/devcontrol/app.py').read_text())
                self.assertFalse((guest / (DEVCONTROL + '-v6')).exists())
                self.assertEqual(len(list((guest / 'usr/share/polkit-1/actions').glob('org.devlite*'))), 1)

    def test_docker_stop_verifies_socket_and_preserves_containerd(self):
        with TemporaryDirectory() as directory:
            guest = Path(directory)
            marker = guest / 'usr/share/devlite-os/identity.json'
            marker.parent.mkdir(parents=True)
            marker.write_text('{"name":"DevLite OS"}')
            active = {'docker.service': 'active', 'docker.socket': 'active',
                      'containerd.service': 'active'}
            mutations = []

            def systemctl(argv, **kwargs):
                if argv[2] == 'show':
                    state = active[argv[3]]
                    return SimpleNamespace(returncode=0, stdout=(
                        f'LoadState=loaded\nActiveState={state}\nUnitFileState=disabled\n'))
                mutations.append(argv[2:])
                active['docker.service'] = 'inactive'
                return SimpleNamespace(returncode=0, stdout='')

            with patch.object(services.os, 'geteuid', return_value=0):
                with self.assertRaisesRegex(services.ServiceError, 'Parada não concluída'):
                    services.admin('stop', 'docker', guest, runner=systemctl)
                with self.assertRaisesRegex(services.ServiceError, 'consumidores externos'):
                    services.admin('stop', 'containerd', guest, runner=systemctl)
            self.assertEqual(mutations, [['stop', '--', 'docker.socket', 'docker.service']])
            self.assertEqual(active['containerd.service'], 'active')

    def test_polkit_cancelled_is_distinguished_from_denied(self):
        for code, message in ((126, 'cancelada'), (127, 'negada')):
            with self.subTest(code=code), patch.object(services, 'resolve'), patch.object(
                    services.subprocess, 'run', return_value=SimpleNamespace(returncode=code, stdout='')):
                with self.assertRaisesRegex(services.ServiceError, message):
                    services.ServiceClient().operate('apache', 'start')


@unittest.skipUnless(os.environ.get('DISPLAY'), 'Requer Xvfb ou sessão gráfica')
class DevControlSmallWindowTests(unittest.TestCase):
    def test_compact_window_and_dynamic_cards(self):
        import gi
        gi.require_version('Gtk', '3.0')
        from gi.repository import GLib, Gtk

        real_main = Gtk.main
        observed = {}

        def inspect():
            window = next(w for w in Gtk.Window.list_toplevels() if w.get_title() == 'DevControl 3.0')
            window.resize(640, 440)

            def measure():
                view = window.section_views['Visão geral']
                observed['size'] = tuple(window.get_size())
                observed['cards'] = len(view.get_children())
                observed['service_cards'] = len(window.service_content.get_children())
                service_card = window.service_content.get_children()[0]
                controls = service_card.get_children()[-1].get_children()
                observed['boot_toggle'] = controls[-1].get_active()
                window.destroy()
                return GLib.SOURCE_REMOVE

            GLib.timeout_add(200, measure)
            real_main()

        data = {'Visão geral': [('Memória RAM', '51% · 2300 MiB'), ('Kernel', 'Linux')]}
        services = [{'id': 'apache', 'label': 'Apache2', 'unit': 'apache2.service',
                     'LoadState': 'loaded', 'ActiveState': 'inactive', 'UnitFileState': 'enabled'}]
        with patch.object(app.DevControlCollector, 'snapshot', return_value=data), patch.object(
                app.ServiceClient, 'snapshot', return_value=services), patch.object(Gtk, 'main', side_effect=inspect):
            app.main()
        self.assertLessEqual(observed['size'][0], 640)
        self.assertLessEqual(observed['size'][1], 440)
        self.assertEqual(observed['cards'], 2)
        self.assertEqual(observed['service_cards'], 1)
        self.assertTrue(observed['boot_toggle'])
