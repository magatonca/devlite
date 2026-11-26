#!/usr/bin/env python3
"""DevControl 1.0 GTK3 read-only prototype."""
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from collector import DevControlCollector


CSS = b"""
.devcontrol { background: #171c24; color: #e3e9f0; }
.devcontrol label { color: #e3e9f0; }
.devcontrol button { background-image: none; background-color: #263342; color: #e3e9f0; border-color: #425168; }
.devcontrol .muted { color: #a7b8ca; }
.devcontrol notebook header { background: #202833; }
"""

SECTIONS = (
    'Visão geral',
    'Rede',
    'Desenvolvimento',
    'Docker',
    'VPN',
    'Aparência',
    'Segurança e manutenção',
)


def main():
    try:
        import gi
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gdk, GLib, Gtk
    except (ImportError, ValueError) as error:
        raise SystemExit('GTK3/PyGObject indisponível; nenhum pacote será instalado: ' + str(error))
    if not Gtk.init_check()[0]:
        raise SystemExit('Sem sessão gráfica. Inicie o DevControl em uma sessão XFCE.')

    class Dashboard(Gtk.Window):
        def __init__(self):
            super().__init__(title='DevControl 1.0')
            self.set_default_size(900, 650)
            self.set_size_request(620, 420)
            self.set_icon_name('devlite')
            self.get_style_context().add_class('devcontrol')
            self.collector = DevControlCollector()
            self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='devcontrol')
            self.closed = False
            self.busy = False
            self.values = {}
            self.connect('destroy', self.close)

            root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            root.set_border_width(18)
            root.get_style_context().add_class('devcontrol')
            self.add(root)

            heading = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            title = Gtk.Label(label='DevControl 1.0', xalign=0)
            title.get_style_context().add_class('title')
            heading.pack_start(title, True, True, 0)
            self.refresh_button = Gtk.Button(label='Atualizar')
            self.refresh_button.connect('clicked', lambda _button: self.refresh())
            heading.pack_end(self.refresh_button, False, False, 0)
            root.pack_start(heading, False, False, 0)

            notice = Gtk.Label(
                label='Central de consulta do sistema. Nenhuma operação administrativa é executada.',
                xalign=0,
            )
            notice.set_line_wrap(True)
            notice.get_style_context().add_class('muted')
            root.pack_start(notice, False, False, 0)

            notebook = Gtk.Notebook()
            notebook.set_scrollable(True)
            self.notebook = notebook
            self.grids = {}
            root.pack_start(notebook, True, True, 0)
            for section in SECTIONS:
                page = Gtk.ScrolledWindow()
                page.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
                grid = Gtk.Grid(column_spacing=18, row_spacing=12)
                grid.set_border_width(16)
                page.add(grid)
                self.grids[section] = grid
                value_labels = []
                self.values[section] = value_labels
                notebook.append_page(page, Gtk.Label(label=section))
            self.message = Gtk.Label(label='Pronto para consultar.', xalign=0)
            self.message.set_line_wrap(True)
            root.pack_start(self.message, False, False, 0)

            style = Gtk.CssProvider()
            style.load_from_data(CSS)
            screen = Gdk.Screen.get_default()
            if screen:
                Gtk.StyleContext.add_provider_for_screen(
                    screen, style, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
                )
            self._create_rows()
            self.show_all()
            self.refresh()
            GLib.timeout_add_seconds(30, self._refresh_if_idle)

        def _create_rows(self):
            for section in SECTIONS:
                grid = self.grids[section]
                self.values[section].clear()
                for row_index in range(12):
                    key = Gtk.Label(xalign=0, yalign=0)
                    key.set_selectable(True)
                    key.set_line_wrap(True)
                    value = Gtk.Label(label='Consultando…', xalign=0, yalign=0)
                    value.set_selectable(True)
                    value.set_line_wrap(True)
                    value.set_max_width_chars(72)
                    grid.attach(key, 0, row_index, 1, 1)
                    grid.attach(value, 1, row_index, 1, 1)
                    self.values[section].append((key, value))

        def close(self, *_args):
            self.closed = True
            self.pool.shutdown(wait=False, cancel_futures=True)
            Gtk.main_quit()

        def _refresh_if_idle(self):
            if self.closed:
                return False
            if not self.busy:
                self.refresh()
            return True

        def refresh(self):
            if self.closed or self.busy:
                return
            self.busy = True
            self.refresh_button.set_sensitive(False)
            self.message.set_text('Consultando informações locais…')
            future = self.pool.submit(self.collector.snapshot)
            future.add_done_callback(lambda completed: GLib.idle_add(self._show_result, completed))

        def _show_result(self, future):
            if self.closed:
                return False
            try:
                snapshot = future.result()
                for section in SECTIONS:
                    rows = snapshot.get(section, [])
                    widgets = self.values[section]
                    for index, (key, value) in enumerate(widgets):
                        if index < len(rows):
                            key.set_text(str(rows[index][0]))
                            value.set_text(str(rows[index][1]))
                            key.show()
                            value.show()
                        else:
                            key.hide()
                            value.hide()
                self.message.set_text(
                    'Consulta concluída: ' + datetime.now().strftime('%H:%M:%S')
                    + '. Informações não são enviadas nem armazenadas.'
                )
            except Exception:
                self.message.set_text('A consulta falhou; tente atualizar novamente.')
            finally:
                self.busy = False
                self.refresh_button.set_sensitive(True)
            return False

    window = Dashboard()
    window.show_all()
    Gtk.main()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
