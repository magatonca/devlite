import tempfile
import unittest
from pathlib import Path

from v6.payload import apply

PROFILES = ('etc/xdg/xfce4/whiskermenu/defaults.rc',
            'etc/xdg/xdg-xubuntu/xfce4/whiskermenu/defaults.rc')
ICON = '/usr/share/icons/hicolor/scalable/apps/devlite.svg'


class XfceIdentityTests(unittest.TestCase):
    def test_same_native_defaults_in_base_and_live(self):
        for target in ('base', 'live'):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                prefs = root / 'home/existente/.config/xfce4/panel/whiskermenu-1.rc'
                prefs.parent.mkdir(parents=True)
                prefs.write_text('button-icon=personalizado\nbutton-title=Personalizado\n')
                original = prefs.read_bytes()
                written = apply(root, target)
                for profile in PROFILES:
                    self.assertIn(profile, written)
                    lines = (root / profile).read_text().splitlines()
                    self.assertEqual([line for line in lines if line.startswith('button-title')],
                                     ['button-title=Menu DevLite OS'])
                    self.assertEqual([line for line in lines if line.startswith('button-icon=')],
                                     [f'button-icon={ICON}'])
                    self.assertIn('show-button-title=false', lines)
                    self.assertIn('show-button-icon=true', lines)
                self.assertEqual(prefs.read_bytes(), original)
                self.assertFalse(any(name.startswith(('home/', 'etc/skel/')) for name in written))
