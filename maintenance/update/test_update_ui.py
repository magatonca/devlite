"""GTK regression test, e.g. xvfb-run -a python3 -B -m unittest maintenance.update.test_update_ui."""
from concurrent.futures import ThreadPoolExecutor
from importlib import import_module
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from maintenance.update import updater


class UpdatesPageTests(unittest.TestCase):
    def test_layout_and_update_flow(self):
        try:
            import gi
            gi.require_version('Gtk', '3.0')
            from gi.repository import Gtk, GLib
        except (ImportError, ValueError):
            self.skipTest('GTK indisponível')
        if not Gtk.init_check()[0]:
            self.skipTest('Execute com Xvfb')
        with patch.dict(sys.modules, {'updater': updater}):
            ui = import_module('maintenance.update.update_ui')

        def widgets(widget):
            yield widget
            if isinstance(widget, Gtk.Container):
                for child in widget.get_children():
                    yield from widgets(child)

        window = Gtk.Window()
        window.set_default_size(820, 570)
        notebook = Gtk.Notebook()
        window.add(notebook)
        events = GLib.MainContext.default()

        def flush():
            while events.pending():
                events.iteration(False)

        def labels():
            return [w.get_text() for w in widgets(window) if isinstance(w, Gtk.Label)]

        with (ThreadPoolExecutor(max_workers=1) as pool,
              patch.object(updater, 'installed', side_effect=['1.0.1', '1.0.1', '1.0.2', '1.0.2']),
              patch.object(updater, 'latest', side_effect=[
                  ('v1.0.2', 'Notas de teste'), (None, 'O DevControl já está atualizado.')]),
              patch.object(updater, 'download') as download,
              patch.object(updater, 'verify'),
              patch.object(updater, 'digest', return_value='a' * 64),
              patch.object(ui, 'run_admin') as admin):
            page = SimpleNamespace(notebook=notebook, pool=pool, closed=False)
            ui.add_page(page, Gtk, GLib)
            window.show_all()
            flush()
            self.assertLessEqual(window.get_size().width, 1366)
            self.assertLessEqual(window.get_size().height, 768)
            buttons = {w.get_label(): w for w in widgets(window) if isinstance(w, Gtk.Button)}

            def click(label):
                self.assertTrue(buttons[label].get_sensitive())
                buttons[label].clicked()
                pool.submit(lambda: None).result(timeout=5)
                flush()

            self.assertFalse(buttons['Instalar'].get_sensitive())
            click('Consultar')
            self.assertIn('Notas de teste', labels())
            self.assertIn('1.0.2', labels())
            self.assertTrue(any(text.startswith('Última consulta nesta sessão: ') for text in labels()))
            click('Baixar e verificar')
            download.assert_called_once()
            self.assertIn('Assinatura digital: válida. SHA-256 confirmado.', labels())
            click('Instalar')
            self.assertEqual(admin.call_args.args[0], ['install', 'v1.0.2', 'a' * 64])
            click('Consultar')
            self.assertIn('O DevControl já está atualizado.', labels())
            page.closed = True
            window.destroy()
