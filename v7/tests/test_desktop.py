from configparser import ConfigParser
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from xml.etree import ElementTree

from v7.assemble import LEAVES, STACKS, render_grub
from v7.desktop import GENERIC_PANEL, ICON, PANEL, apply


class DesktopDefaultsTests(unittest.TestCase):
    def test_settings_apply_to_new_users_and_preserve_existing_home(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            icon = root / ICON
            icon.parent.mkdir(parents=True)
            icon.write_text('<svg/>')
            user = root / 'home/ana/.config/xfce4/panel/whiskermenu-1.rc'
            user.parent.mkdir(parents=True)
            user.write_text('button-icon=personalizado\n')
            user_panel = user.parent.parent / 'xfconf/xfce-perchannel-xml/xfce4-panel.xml'
            user_panel.parent.mkdir(parents=True)
            user_panel.write_text('<channel name="xfce4-panel" version="1.0" />\n')
            written = apply(root, live=True)
            profile = root / 'etc/skel/.config/xfce4/panel/whiskermenu-1.rc'
            self.assertIn(f'button-icon=/{ICON}', profile.read_text().splitlines())
            self.assertIn('button-title=Menu DevLite OS', profile.read_text().splitlines())
            self.assertEqual(user.read_text(), 'button-icon=personalizado\n')
            self.assertEqual(user_panel.read_text(), '<channel name="xfce4-panel" version="1.0" />\n')
            self.assertEqual((root / PANEL).read_bytes(), (root / GENERIC_PANEL).read_bytes())
            panel = ElementTree.parse(root / PANEL)
            main = panel.find("./property[@name='panels']/property[@name='panel-1']")
            for name, value in {'position': 'p=10;x=0;y=0', 'mode': '0', 'length': '100',
                                'nrows': '1', 'size': '40'}.items():
                self.assertEqual(main.find(f"property[@name='{name}']").get('value'), value)
            plugins = panel.find("./property[@name='plugins']")
            order = [plugins.find(f"property[@name='plugin-{item.get('value')}']")
                     for item in main.findall("property[@name='plugin-ids']/value")]
            self.assertEqual(order[0].get('value'), 'whiskermenu')
            self.assertEqual(order[0].find("property[@name='button-icon']").get('value'), f'/{ICON}')
            self.assertEqual(order[0].find("property[@name='button-title']").get('value'),
                             'Menu DevLite OS')
            self.assertEqual(order[-1].get('value'), 'clock')
            self.assertEqual(order[3].find("property[@name='expand']").get('value'), 'true')
            self.assertEqual((root / 'etc/default/grub.d/99-devlite-branding.cfg').read_text(),
                             "GRUB_DISTRIBUTOR='DevLite OS 1.0'\n")
            for name in written:
                self.assertEqual((root / name).stat().st_mode & 0o777,
                                 0o755 if name in ('usr/libexec/devlite-install-vscode',
                                                   'usr/libexec/devlite-launch-snap',
                                                   'usr/libexec/devlite-live-desktop') else 0o644)
            for path in ('etc/xdg/xfce4/terminal/terminalrc',
                         'etc/xdg/xdg-xubuntu/xfce4/terminal/terminalrc'):
                config = ConfigParser()
                config.read(root / path)
                colors = config['Configuration']
                self.assertEqual(colors['ColorForeground'], '#F0F6FC')
                self.assertEqual(colors['ColorBackground'], '#131926')
                self.assertEqual(len(colors['ColorPalette'].split(';')), 16)

    def test_live_grub_avoids_inherited_splash(self):
        previous = STACKS['live'][-1]
        new = LEAVES['live']
        other = 'echo splash\n'
        source = f'  linux /casper/vmlinuz layerfs-path={previous} --- quiet splash\n'
        self.assertEqual(render_grub(other + source),
                         other + f'  linux /casper/vmlinuz layerfs-path={new} --- quiet nosplash\n')


class RuntimeDiagnosticsTests(unittest.TestCase):
    def test_live_and_overlay_detection_use_guest_kernel_state(self):
        from unittest.mock import patch

        from v6.devcontrol.metrics import DevControlCollector as V6Collector
        from v7.devcontrol_metrics import DevControlCollector
        collector = DevControlCollector()
        with patch.object(V6Collector, 'overview', return_value=[]), patch.object(
                V6Collector, 'docker', side_effect=lambda: []):
            with patch.object(collector, '_read', side_effect=lambda name: {
                '/proc/cmdline': 'quiet layerfs-path=example.squashfs',
                '/proc/self/mountinfo': '1 0 0:1 / / rw - overlay overlay rw',
            }[name]):
                self.assertEqual(collector.overview(), [('Ambiente', 'Sessão Live')])
                self.assertIn('overlay2', collector.docker()[0][1])
            with patch.object(collector, '_read', side_effect=lambda name: {
                '/proc/cmdline': 'quiet root=UUID=fixture',
                '/proc/self/mountinfo': '1 0 8:1 / / rw - ext4 /dev/sda1 rw',
            }[name]):
                self.assertEqual(collector.overview(), [('Ambiente', 'Sistema instalado')])
                self.assertFalse(collector.docker())

    def test_overlay_reuses_the_existing_application_and_service_backend(self):
        from v7.desktop import apply_devcontrol

        with TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / 'usr/lib/devlite/devcontrol'
            target.mkdir(parents=True)
            source = Path('v6/devcontrol/app.py').read_text()
            (target / 'app.py').write_text(source)
            (target / 'services.py').write_text('backend preserved')
            apply_devcontrol(root)
            rendered = (target / 'app.py').read_text()
            compile(rendered, 'installed-app.py', 'exec')
            self.assertIn('from metrics_v7 import DevControlCollector', rendered)
            self.assertIn('self.pool.submit(vscode_v7.install)', rendered)
            self.assertTrue((target / 'metrics_v7.py').is_file())
            self.assertEqual((target / 'services.py').read_text(), 'backend preserved')
