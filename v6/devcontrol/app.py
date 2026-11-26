#!/usr/bin/env python3
"""DevControl 3.0 GTK3: asynchronous information and restricted service control."""
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# Fixed root-owned installed directory; works with Python isolated mode.
sys.path.insert(0, '/usr/lib/devlite/devcontrol')
if __package__:
    from .metrics import DevControlCollector
    from .services import ServiceClient, ServiceError
else:
    from metrics import DevControlCollector
    from services import ServiceClient, ServiceError


CSS = b"""
.devcontrol .title { font-weight: bold; font-size: 1.25em; }
.devcontrol .header { border-bottom: 2px solid #268e81; padding-bottom: 7px; }
.devcontrol .card { border-radius: 7px; border: 1px solid alpha(@theme_fg_color, 0.20); padding: 8px; }
.devcontrol .metric-title { font-weight: bold; }
.devcontrol .muted { opacity: 0.85; }
.devcontrol .running { color: @success_color; }
.devcontrol .attention { color: @warning_color; }
.devcontrol .failed { color: @error_color; }
"""

ACTIVE = {'active': 'Ativo', 'inactive': 'Parado', 'failed': 'Falhou',
          'activating': 'Iniciando', 'deactivating': 'Parando', 'reloading': 'Recarregando'}
DESCRIPTIONS = {
    'apache': 'Servidor HTTP para desenvolvimento local.',
    'mariadb': 'Servidor de banco de dados SQL local.',
    'docker': 'Gerencia contêineres e imagens.',
    'docker-socket': 'Ativa o Docker sob demanda.',
    'containerd': 'Runtime compartilhado de contêineres.',
    'ssh': 'Acesso remoto seguro e transferência SFTP.',
    'ssh-socket': 'Ativa o servidor SSH sob demanda.',
}
BOOT = {'enabled': 'Habilitado', 'enabled-runtime': 'Habilitado até reiniciar',
        'disabled': 'Desabilitado', 'static': 'Gerenciado por dependências',
        'indirect': 'Indireto', 'masked': 'Mascarado', 'alias': 'Alias'}

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
    if os.geteuid() == 0:
        raise SystemExit('Abra o DevControl em uma sessão de usuário comum.')
    try:
        import gi
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gdk, GLib, Gtk, Pango
    except (ImportError, ValueError) as error:
        raise SystemExit('GTK3/PyGObject indisponível; nenhum pacote será instalado: ' + str(error))
    if not Gtk.init_check()[0]:
        raise SystemExit('Sem sessão gráfica. Inicie o DevControl em uma sessão XFCE.')

    class Dashboard(Gtk.Window):
        def __init__(self):
            super().__init__(title='DevControl 3.0')
            self.set_default_size(820, 570)
            self.set_size_request(440, 320)
            self.set_icon_name('devlite')
            self.get_style_context().add_class('devcontrol')
            self.collector = DevControlCollector()
            self.services = ServiceClient()
            self.service_busy = False
            self.service_buttons = []
            self.last_service_message = ""
            self.service_results = {}
            self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='devcontrol')
            self.closed = False
            self.busy = False
            self.connect('destroy', self.close)

            root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
            root.set_border_width(10)
            root.get_style_context().add_class('devcontrol')
            self.add(root)

            heading = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            heading.get_style_context().add_class('header')
            heading.pack_start(Gtk.Image.new_from_icon_name('devlite', Gtk.IconSize.LARGE_TOOLBAR),
                               False, False, 0)
            title = Gtk.Label(label='DevControl 3.0', xalign=0)
            title.get_style_context().add_class('title')
            heading.pack_start(title, True, True, 0)
            self.refresh_button = Gtk.Button(label='Atualizar')
            self.refresh_button.connect('clicked', lambda _button: self.refresh())
            heading.pack_end(self.refresh_button, False, False, 0)
            root.pack_start(heading, False, False, 0)

            self.summary = Gtk.Label(label='Consultando serviços…', xalign=0)
            root.pack_start(self.summary, False, False, 0)

            tools = Gtk.LinkButton.new_with_label(
                'https://code.visualstudio.com/docs/setup/linux', 'Obter VS Code')

            notebook = Gtk.Notebook()
            notebook.set_scrollable(True)
            self.notebook = notebook
            self.section_views = {}
            root.pack_start(notebook, True, True, 0)
            for section in SECTIONS:
                page = Gtk.ScrolledWindow()
                page.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
                content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
                content.set_border_width(6)
                page.add(content)
                if section == 'Desenvolvimento':
                    tools.set_halign(Gtk.Align.START)
                    content.pack_start(tools, False, False, 0)
                if section == 'Visão geral':
                    view = Gtk.FlowBox()
                    view.set_selection_mode(Gtk.SelectionMode.NONE)
                    view.set_max_children_per_line(3)
                    view.set_homogeneous(True)
                    view.set_row_spacing(6)
                    view.set_column_spacing(6)
                else:
                    view = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
                content.pack_start(view, False, False, 0)
                self.section_views[section] = view
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
            self._create_services(notebook)
            self.show_all()
            self.refresh()
            self.refresh_services()
            self.refresh_timer = GLib.timeout_add_seconds(30, self._refresh_if_idle)

        def populate_section(self, section, rows):
            view = self.section_views[section]
            for child in view.get_children():
                view.remove(child)
            for key, value in rows:
                box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
                box.get_style_context().add_class('card')
                heading = Gtk.Label(label=key, xalign=0)
                heading.set_line_wrap(True)
                heading.get_style_context().add_class('metric-title')
                box.pack_start(heading, False, False, 0)
                value = str(value)
                label = Gtk.Label(label=value, xalign=0)
                label.set_selectable(True)
                label.set_line_wrap(True)
                label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
                label.set_max_width_chars(38)
                box.pack_start(label, False, False, 0)
                percent = value.partition('%')[0]
                if section == 'Visão geral' and percent.isdecimal() and '%' in value:
                    meter = Gtk.ProgressBar()
                    meter.set_fraction(min(1, int(percent) / 100))
                    meter.set_tooltip_text(value)
                    box.pack_start(meter, False, False, 0)
                view.add(box)
            view.show_all()

        def _create_services(self, notebook):
            page = Gtk.ScrolledWindow()
            page.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            content.set_border_width(6)
            page.add(content)
            self.service_box=content
            self.service_notice=Gtk.Label(label='Consultando unidades…',xalign=0);self.service_notice.set_line_wrap(True);content.pack_start(self.service_notice,False,False,0)
            refresh=Gtk.Button(label='Atualizar serviços');refresh.connect('clicked',lambda _b:self.refresh_services());content.pack_start(refresh,False,False,0)
            self.service_content=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=6);content.pack_start(self.service_content,False,False,0)
            notebook.append_page(page,Gtk.Label(label='Serviços'))
        def refresh_services(self):
            if self.closed or self.service_busy or getattr(self,'service_query_pending',False):return
            self.service_query_pending=True
            f=self.pool.submit(self.services.snapshot);f.add_done_callback(lambda f:GLib.idle_add(self.show_services,f))
        def show_services(self,future):
            self.service_query_pending=False
            if self.closed:return False
            try:rows=future.result()
            except Exception:
                self.service_notice.set_text('Não foi possível consultar o estado dos serviços.')
                return False
            running = sum(row.get('ActiveState') == 'active' for row in rows)
            failed = sum(row.get('ActiveState') == 'failed' for row in rows)
            self.summary.set_text(f'Serviços ativos: {running} · Com falha: {failed}')
            for child in self.service_content.get_children():self.service_content.remove(child)
            self.service_buttons=[]
            for row in rows:
                key = row['id']
                box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
                box.get_style_context().add_class('card')
                heading = Gtk.Label(label=row['label'], xalign=0)
                heading.get_style_context().add_class('metric-title')
                box.pack_start(heading, False, False, 0)
                active = row.get('ActiveState')
                boot = row.get('UnitFileState', '')
                state = ACTIVE.get(active, 'Desconhecido')
                available=row.get('LoadState')=='loaded' and not row.get('UnitFileState','').startswith('masked')
                if row.get('LoadState')=='not-found':state='Não instalado'
                elif row.get('LoadState')=='masked' or row.get('UnitFileState','').startswith('masked'):state='Mascarado; operação bloqueada'
                indicator = {'active':'●', 'inactive':'○', 'failed':'✖'}.get(active, '◐')
                label = Gtk.Label(label=f"{indicator} {state} · Inicialização: {BOOT.get(boot, 'Desconhecido')} · {row['unit']}", xalign=0)
                label.set_line_wrap(True)
                label.get_style_context().add_class({
                    'active': 'running', 'failed': 'failed', 'inactive': 'muted',
                }.get(active, 'attention'))
                box.pack_start(label, False, False, 0)
                description = Gtk.Label(label=DESCRIPTIONS.get(row['id'], row['label']), xalign=0)
                description.set_line_wrap(True)
                box.pack_start(description, False, False, 0)
                if row['id'] in self.service_results:
                    result = Gtk.Label(label=self.service_results[row['id']], xalign=0)
                    result.set_line_wrap(True)
                    box.pack_start(result, False, False, 0)
                eligible = {
                    'start': active in ('inactive', 'failed'),
                    'stop': active == 'active' and key != 'containerd',
                    'restart': active == 'active' and key != 'containerd',
                }
                if key == 'docker-socket':
                    docker = next((item for item in rows if item['id'] == 'docker'), {})
                    if docker.get('ActiveState') not in ('inactive', 'failed'):
                        eligible.update(stop=False, restart=False)
                actions = Gtk.Box(spacing=5)
                box.pack_start(actions, False, False, 0)
                for text, action in [('Iniciar', 'start'), ('Parar', 'stop'), ('Reiniciar', 'restart')]:
                    button = Gtk.Button(label=text)
                    button.set_sensitive(available and eligible[action] and not self.service_busy)
                    button.connect('clicked', lambda _button, service=key, verb=action:
                                   self.change_service(service, verb))
                    actions.pack_start(button, False, False, 0)
                    self.service_buttons.append(button)
                boot_control = Gtk.Box(spacing=5)
                boot_control.pack_start(Gtk.Label(label='Iniciar com o sistema', xalign=0), False, False, 0)
                toggle = Gtk.Switch()
                toggle.set_active(boot == 'enabled')
                toggle.set_sensitive(available and boot in ('enabled', 'enabled-runtime', 'disabled')
                                     and not self.service_busy)
                toggle.get_accessible().set_name(f"Iniciar {row['label']} com o sistema")
                toggle.connect('state-set', lambda _switch, enabled, service=key:
                               self.change_boot(service, enabled))
                boot_control.pack_start(toggle, False, False, 0)
                if boot == 'enabled-runtime':
                    clear = Gtk.Button(label='Desativar configuração temporária')
                    clear.set_sensitive(available and not self.service_busy)
                    clear.connect('clicked', lambda _, service=key: self.change_service(service, 'disable'))
                    box.pack_start(clear, False, False, 0)
                    self.service_buttons.append(clear)
                box.pack_start(boot_control, False, False, 0)
                self.service_buttons.append(toggle)
                self.service_content.pack_start(box, False, False, 0)
            ids=[row['id'] for row in rows];missing=[]
            if not any(i.startswith('openvpn:') for i in ids):missing.append('OpenVPN: nenhum perfil cliente disponível.')
            if not any(i.startswith('php:') for i in ids):missing.append('PHP-FPM não instalado; PHP CLI não é serviço.')
            if not self.service_busy:self.service_notice.set_text(self.last_service_message+' '+ ' '.join(missing))
            self.service_box.show_all();return False
        def change_boot(self, service, enabled):
            self.change_service(service, 'enable' if enabled else 'disable')
            return True  # A posição só muda após leitura do estado real.

        def change_service(self,key,action):
            if self.service_busy:return
            if action in ('stop','restart','disable'):
                dialog=Gtk.MessageDialog(transient_for=self,modal=True,message_type=Gtk.MessageType.QUESTION,buttons=Gtk.ButtonsType.NONE,text='Confirmar alteração de serviço?')
                dialog.add_button('Cancelar', Gtk.ResponseType.CANCEL)
                dialog.add_button('Confirmar', Gtk.ResponseType.OK)
                dialog.set_default_response(Gtk.ResponseType.CANCEL)
                dialog.format_secondary_text('A inicialização automática será alterada. O estado atual do serviço será mantido.' if action=='disable' else 'Conexões e trabalhos podem ser interrompidos. Docker afeta contêineres; SSH pode desconectar acesso remoto.')
                accepted=dialog.run()==Gtk.ResponseType.OK;dialog.destroy()
                if not accepted:return
            self.service_busy=True
            for button in self.service_buttons:button.set_sensitive(False)
            self.service_notice.set_text('Aguardando autorização e conclusão…')
            f=self.pool.submit(self.services.operate,key,action);f.add_done_callback(lambda f:GLib.idle_add(self.service_finished,f,key))
        def service_finished(self,future,key):
            if self.closed:return False
            try:self.last_service_message=future.result().get('message','Operação concluída.')
            except ServiceError as error:self.last_service_message='Falha: '+str(error)
            except Exception:self.last_service_message='Falha ao consultar a operação administrativa.'
            self.service_results[key] = self.last_service_message
            self.service_busy=False;self.refresh_services();return False

        def close(self, *_args):
            self.closed = True
            GLib.source_remove(self.refresh_timer)
            self.pool.shutdown(wait=False, cancel_futures=True)
            Gtk.main_quit()

        def _refresh_if_idle(self):
            if self.closed:
                return False
            if not self.busy:
                self.refresh()
            self.refresh_services()
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
                    self.populate_section(section, snapshot.get(section, []))
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
