import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
DEVCONTROL_DIR = ROOT / 'devcontrol'

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
                    if window.get_title() == 'DevControl 2.0'
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
                with patch('services.ServiceClient.snapshot', return_value=[]), patch.object(Gtk, 'main', new=inspect_main_loop):
                    module.main()
            self.assertEqual(len(opened), 1)
        finally:
            sys.path.remove(str(DEVCONTROL_DIR))

    def test_service_operation_keeps_gtk_main_loop_responsive(self):
        import threading
        sys.path.insert(0,str(DEVCONTROL_DIR))
        entered=threading.Event();release=threading.Event();ticks=[];windows=[];errors=[]
        try:
            spec=importlib.util.spec_from_file_location('devlite_v5_async_app',DEVCONTROL_DIR/'app.py')
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            from collector import DevControlCollector
            real_main=Gtk.main;main_thread=threading.get_ident()
            def operate(service,action):
                if threading.get_ident()==main_thread:errors.append('administration ran on GTK thread')
                entered.set()
                if not release.wait(2):errors.append('GTK did not release simulated operation')
                return {'message':'Simulado OK'}
            def start_loop():
                window=next(w for w in Gtk.Window.list_toplevels() if w.get_title()=='DevControl 2.0')
                windows.append(window);window.change_service('apache','start')
                def tick():
                    ticks.append(1)
                    if entered.is_set() and len(ticks)>=3:release.set()
                    if entered.is_set() and not window.service_busy:
                        window.destroy();return GLib.SOURCE_REMOVE
                    if len(ticks)>200:
                        errors.append('operation did not complete');release.set();window.destroy();return GLib.SOURCE_REMOVE
                    return GLib.SOURCE_CONTINUE
                GLib.timeout_add(10,tick);real_main()
            with patch.object(DevControlCollector,'snapshot',return_value={section:[] for section in module.SECTIONS}),patch('services.ServiceClient.snapshot',return_value=[]),patch('services.ServiceClient.operate',side_effect=operate),patch.object(Gtk,'main',new=start_loop):
                module.main()
            self.assertFalse(errors);self.assertGreaterEqual(len(ticks),3)
            self.assertEqual(windows[0].last_service_message,'Simulado OK')
        finally:
            release.set();sys.path.remove(str(DEVCONTROL_DIR))


if __name__ == '__main__':
    unittest.main()
