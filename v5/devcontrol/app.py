#!/usr/bin/env python3
"""DevControl 2.0 GTK3: asynchronous information and restricted service control."""
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# Fixed root-owned installed directory; works with Python isolated mode.
sys.path.insert(0, '/usr/lib/devlite/devcontrol')
from collector import DevControlCollector
from services import ServiceClient


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
            super().__init__(title='DevControl 2.0')
            self.set_default_size(900, 650)
            self.set_size_request(620, 420)
            self.set_icon_name('devlite')
            self.get_style_context().add_class('devcontrol')
            self.collector = DevControlCollector()
            self.services = ServiceClient()
            self.service_busy = False
            self.service_buttons = []
            self.last_service_message = ""
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
            title = Gtk.Label(label='DevControl 2.0', xalign=0)
            title.get_style_context().add_class('title')
            heading.pack_start(title, True, True, 0)
            self.refresh_button = Gtk.Button(label='Atualizar')
            self.refresh_button.connect('clicked', lambda _button: self.refresh())
            heading.pack_end(self.refresh_button, False, False, 0)
            root.pack_start(heading, False, False, 0)

            notice = Gtk.Label(
                label='Consultas sem privilégios. Alterações de serviços exigem autorização administrativa.',
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
            self._create_services(notebook)
            self.show_all()
            self.refresh()
            self.refresh_services()
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

        def _create_services(self, notebook):
            page=Gtk.ScrolledWindow();content=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10);content.set_border_width(14);page.add(content)
            self.service_box=content
            self.service_notice=Gtk.Label(label='Consultando unidades…',xalign=0);self.service_notice.set_line_wrap(True);content.pack_start(self.service_notice,False,False,0)
            refresh=Gtk.Button(label='Atualizar serviços');refresh.connect('clicked',lambda _b:self.refresh_services());content.pack_start(refresh,False,False,0)
            self.service_content=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=10);content.pack_start(self.service_content,False,False,0)
            notebook.append_page(page,Gtk.Label(label='Serviços'))
        def refresh_services(self):
            if self.closed or self.service_busy or getattr(self,'service_query_pending',False):return
            self.service_query_pending=True
            f=self.pool.submit(self.services.snapshot);f.add_done_callback(lambda f:GLib.idle_add(self.show_services,f))
        def show_services(self,future):
            self.service_query_pending=False
            if self.closed:return False
            try:rows=future.result()
            except Exception as error:self.service_notice.set_text(str(error));return False
            for child in self.service_content.get_children():self.service_content.remove(child)
            self.service_buttons=[]
            for row in rows:
                frame=Gtk.Frame(label=row['label']);box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=6);box.set_border_width(9);frame.add(box)
                state={'active':'Ativo','inactive':'Parado','failed':'Falhou'}.get(row.get('ActiveState'),'Desconhecido')
                available=row.get('LoadState')=='loaded' and not row.get('UnitFileState','').startswith('masked')
                if row.get('LoadState')=='not-found':state='Não instalado'
                elif row.get('LoadState')=='masked' or row.get('UnitFileState','').startswith('masked'):state='Mascarado; operação bloqueada'
                label=Gtk.Label(label=state+' • '+row.get('UnitFileState','desconhecido')+' • '+row['unit'],xalign=0);label.set_line_wrap(True);box.pack_start(label,False,False,0)
                actions=Gtk.Box(spacing=5);box.pack_start(actions,False,False,0)
                for text,action in [('Iniciar','start'),('Parar','stop'),('Reiniciar','restart'),('Ativar no boot','enable'),('Desativar no boot','disable')]:
                    button=Gtk.Button(label=text);button.set_sensitive(available and not self.service_busy);button.connect('clicked',lambda _b,key=row['id'],a=action:self.change_service(key,a));actions.pack_start(button,False,False,0);self.service_buttons.append(button)
                self.service_content.pack_start(frame,False,False,0)
            ids=[row['id'] for row in rows];missing=[]
            if not any(i.startswith('openvpn:') for i in ids):missing.append('OpenVPN: nenhum perfil cliente disponível.')
            if not any(i.startswith('php:') for i in ids):missing.append('PHP-FPM não instalado; PHP CLI não é serviço.')
            if not self.service_busy:self.service_notice.set_text(self.last_service_message+' '+ ' '.join(missing))
            self.service_box.show_all();return False
        def change_service(self,key,action):
            if self.service_busy:return
            if action in ('stop','restart','disable'):
                dialog=Gtk.MessageDialog(transient_for=self,modal=True,message_type=Gtk.MessageType.QUESTION,buttons=Gtk.ButtonsType.OK_CANCEL,text='Confirmar alteração de serviço?')
                dialog.format_secondary_text('Apenas o próximo boot será alterado; o serviço atual permanece.' if action=='disable' else 'Conexões e trabalhos podem ser interrompidos. Docker afeta contêineres; SSH pode desconectar acesso remoto.')
                accepted=dialog.run()==Gtk.ResponseType.OK;dialog.destroy()
                if not accepted:return
            self.service_busy=True
            for button in self.service_buttons:button.set_sensitive(False)
            self.service_notice.set_text('Aguardando autorização e conclusão…')
            f=self.pool.submit(self.services.operate,key,action);f.add_done_callback(lambda f:GLib.idle_add(self.service_finished,f))
        def service_finished(self,future):
            if self.closed:return False
            try:self.last_service_message=future.result().get('message','Operação concluída.')
            except Exception as error:self.last_service_message='Falha: '+str(error)
            self.service_busy=False;self.refresh_services();return False

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
