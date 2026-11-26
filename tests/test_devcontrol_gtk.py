import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
DEVCONTROL_DIR = ROOT / 'prototypes/devcontrol'

try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import GLib, Gtk
except (ImportError, ValueError):
    GLib = None
    Gtk = None


@unittest.skipUnless(
    Gtk is not None and os.environ.get('DISPLAY'),
    'GTK3 e display gráfico são necessários',
)
class DevControlGtkTests(unittest.TestCase):
    def test_application_window_opens_and_closes(self):
        sys.path.insert(0, str(DEVCONTROL_DIR))
        try:
            spec = importlib.util.spec_from_file_location(
                'devlite_devcontrol_gtk_test_app', DEVCONTROL_DIR / 'app.py',
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            from collector import DevControlCollector
            real_main = Gtk.main
            opened = []

            def inspect_main_loop():
                windows = [
                    window for window in Gtk.Window.list_toplevels()
                    if window.get_title() == 'DevControl 1.0'
                ]
                self.assertEqual(len(windows), 1)
                window = windows[0]
                self.assertTrue(window.get_mapped())
                self.assertEqual(len(window.values), 7)
                self.assertTrue(all(len(rows) == 12 for rows in window.values.values()))
                opened.append(window)

                def close_window():
                    window.destroy()
                    return GLib.SOURCE_REMOVE

                GLib.timeout_add(100, close_window)
                real_main()
                self.assertFalse(window.get_visible())

            empty_snapshot = {section: [] for section in module.SECTIONS}
            with patch.object(DevControlCollector, 'snapshot', return_value=empty_snapshot):
                with patch.object(Gtk, 'main', new=inspect_main_loop):
                    module.main()
            self.assertEqual(len(opened), 1)
        finally:
            sys.path.remove(str(DEVCONTROL_DIR))


if __name__ == '__main__':
    unittest.main()
