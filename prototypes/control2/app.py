#!/usr/bin/env python3
"""DevLite Control 2.0: standalone GTK3 MOCK ONLY; never invoke host service tools."""
import argparse,json,sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from prototypes.control2.model import SimulatedBackend,SERVICES,LABELS,requires_confirmation
from prototypes.control2.adminer_model import browser_request

CSS=b"""
.devlite-control { background: #171c24; color: #e3e9f0; }
.devlite-control label { color: #e3e9f0; }
.devlite-control button { background-image: none; background-color: #263342; color: #e3e9f0; border-color: #425168; }
.devlite-control button:disabled { color: #91a3b7; }
.devlite-control .accent { background-color: #24659e; }
.devlite-control notebook header { background: #202833; }
.devlite-control textview text { background: #171c24; color: #e3e9f0; }
"""

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true',help='Check GTK3 bindings without opening a window')
    args=parser.parse_args()
    try:
        import gi
        gi.require_version('Gtk','3.0')
        from gi.repository import Gtk,GLib,Gdk
    except (ImportError,ValueError) as error:
        raise SystemExit('GTK3/PyGObject indisponível; nenhum pacote será instalado: '+str(error))
    if args.check:
        print(json.dumps({'gtk_major':Gtk.MAJOR_VERSION,'backend':'simulated-only','host_operations':False}));return
    if not Gtk.init_check()[0]:raise SystemExit('Sem sessão gráfica. Abra preview.html ou execute este protótipo em uma sessão XFCE.')

    class Window(Gtk.Window):
        def __init__(self):
            super().__init__(title='DevLite Control 2.0 — Protótipo')
            self.set_default_size(820,560);self.set_size_request(650,440)
            self.set_icon_name('devlite');self.get_style_context().add_class('devlite-control')
            self.backend=SimulatedBackend();self.pool=ThreadPoolExecutor(max_workers=1)
            self.closed=False;self.busy=False;self.controls=[];self.states={};self.boot={}
            self.connect('destroy',self.close)
            box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=14);box.set_border_width(20)
            box.get_style_context().add_class('devlite-control');self.add(box)
            title=Gtk.Label(label='DevLite Control 2.0',xalign=0);box.pack_start(title,False,False,0)
            box.pack_start(Gtk.Label(label='PROTÓTIPO • dados simulados • nenhum serviço real será controlado',xalign=0),False,False,0)
            tabs=Gtk.Notebook();box.pack_start(tabs,True,True,0)
            services=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12);services.set_border_width(12)
            service_scroll=Gtk.ScrolledWindow();service_scroll.set_policy(Gtk.PolicyType.AUTOMATIC,Gtk.PolicyType.AUTOMATIC)
            service_scroll.add(services);tabs.append_page(service_scroll,Gtk.Label(label='Serviços'))
            for key,unit in SERVICES.items():
                frame=Gtk.Frame(label={'apache':'Apache','mariadb':'MariaDB','docker':'Docker'}[key])
                content=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8);content.set_border_width(10);frame.add(content)
                line=Gtk.Box(spacing=10);content.pack_start(line,False,False,0)
                line.pack_start(Gtk.Label(label=unit,xalign=0),True,True,0)
                label=Gtk.Label();self.states[key]=label;line.pack_end(label,False,False,0)
                actions=Gtk.Box(spacing=6);content.pack_start(actions,False,False,0)
                for text,action in [('Iniciar','start'),('Parar','stop'),('Reiniciar','restart')]:
                    button=Gtk.Button(label=text)
                    icon={'start':'media-playback-start-symbolic','stop':'media-playback-stop-symbolic','restart':'view-refresh-symbolic'}[action]
                    button.set_image(Gtk.Image.new_from_icon_name(icon,Gtk.IconSize.BUTTON));button.set_always_show_image(True)
                    if action=='start':button.get_style_context().add_class('accent')
                    button.connect('clicked',lambda _b,k=key,a=action:self.operate(k,a))
                    self.controls.append(button);actions.pack_start(button,False,False,0)
                logs=Gtk.Button(label='Logs recentes');logs.connect('clicked',lambda _b,k=key:self.logs(k))
                self.controls.append(logs);actions.pack_end(logs,False,False,0)
                bootrow=Gtk.Box(spacing=8);content.pack_start(bootrow,False,False,0)
                boot=Gtk.Label(xalign=0);self.boot[key]=boot;bootrow.pack_start(boot,True,True,0)
                for text,action in [('Ativar no boot','enable'),('Desativar no boot','disable')]:
                    button=Gtk.Button(label=text);button.connect('clicked',lambda _b,k=key,a=action:self.operate(k,a))
                    self.controls.append(button);bootrow.pack_end(button,False,False,0)
                if key=='mariadb':
                    manage=Gtk.Button(label='Gerenciar bancos de dados')
                    manage.connect('clicked',lambda _b:self.databases())
                    self.controls.append(manage);content.pack_start(manage,False,False,0)
                services.pack_start(frame,False,False,0)
            info=Gtk.Grid(column_spacing=20,row_spacing=9);info.set_border_width(16)
            for row,(name,value) in enumerate(self.backend.system_info().items()):
                info.attach(Gtk.Label(label=name,xalign=0),0,row,1,1)
                label=Gtk.Label(label=value,xalign=0);label.set_line_wrap(True);info.attach(label,1,row,1,1)
            scroll=Gtk.ScrolledWindow();scroll.add(info);tabs.append_page(scroll,Gtk.Label(label='Sistema e rede'))
            refresh=Gtk.Button(label='Atualizar status');refresh.connect('clicked',lambda _b:self.refresh())
            self.controls.append(refresh);box.pack_start(refresh,False,False,0)
            self.message=Gtk.Label(label='Simulação pronta. Nenhum acesso administrativo.',xalign=0)
            self.message.set_line_wrap(True);box.pack_start(self.message,False,False,0)
            style=Gtk.CssProvider();style.load_from_data(CSS)
            Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(),style,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            self.refresh();self.show_all()
        def close(self,*_):
            self.closed=True;self.pool.shutdown(wait=False,cancel_futures=True);Gtk.main_quit()
        def refresh(self):
            if self.closed:return
            for key,state in self.backend.all_status().items():
                self.states[key].set_text(LABELS[state.state])
                self.boot[key].set_text('Inicialização automática: '+('ativada' if state.autostart else 'desativada'))
        def operate(self,key,action):
            if self.busy:return
            confirmed=False
            if requires_confirmation(action):
                extra=' Contêineres e conexões podem ser interrompidos.' if key=='docker' else ' Conexões e trabalhos em andamento podem ser interrompidos.'
                if action=='disable':extra=' O serviço atual não será parado; muda somente o próximo boot.'
                dialog=Gtk.MessageDialog(transient_for=self,modal=True,message_type=Gtk.MessageType.QUESTION,buttons=Gtk.ButtonsType.OK_CANCEL,text='Confirmar operação simulada?')
                verb={'stop':'Parar','restart':'Reiniciar','disable':'Desativar inicialização automática de'}[action]
                dialog.get_style_context().add_class('devlite-control')
                dialog.format_secondary_text(verb+' '+SERVICES[key]+'.'+extra)
                confirmed=dialog.run()==Gtk.ResponseType.OK;dialog.destroy()
                if not confirmed:return
            self.busy=True
            for button in self.controls:button.set_sensitive(False)
            self.message.set_text('Executando simulação…')
            future=self.pool.submit(self.backend.operate,key,action,confirmed)
            future.add_done_callback(lambda result:GLib.idle_add(self.finished,result))
        def finished(self,future):
            if self.closed:return False
            try:future.result();self.message.set_text('Operação simulada concluída; status atualizado.')
            except Exception as error:self.message.set_text('Operação não concluída: '+str(error))
            finally:
                self.busy=False
                for button in self.controls:button.set_sensitive(True)
                self.refresh()
            return False
        def databases(self):
            try:
                url=browser_request(self.backend.status('apache').state=='active',self.backend.status('mariadb').state=='active')
                self.message.set_text('SIMULAÇÃO: abriria '+url+' no navegador padrão. Adminer ainda não instalado; revisão de segurança pendente.')
            except ValueError as error:self.message.set_text(str(error))
        def logs(self,key):
            dialog=Gtk.Dialog(title='Logs simulados — '+SERVICES[key],transient_for=self,modal=True)
            dialog.get_style_context().add_class('devlite-control')
            dialog.add_button('Fechar',Gtk.ResponseType.CLOSE);dialog.set_default_size(650,300)
            view=Gtk.TextView();view.set_editable(False);view.set_monospace(True)
            view.get_buffer().set_text(self.backend.logs(key))
            scroll=Gtk.ScrolledWindow();scroll.add(view);dialog.get_content_area().pack_start(scroll,True,True,8)
            dialog.show_all();dialog.run();dialog.destroy()
    window=Window()
    Gtk.main()

if __name__=='__main__':main()
