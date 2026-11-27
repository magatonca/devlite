"""Updates page embedded in the existing DevControl GTK dashboard."""
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

import updater


def add_page(dashboard, Gtk, GLib):
    page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin=10)
    dashboard.notebook.append_page(page, Gtk.Label(label='Atualizações'))
    details = Gtk.Label(label=f'Versão instalada: {updater.installed()}', xalign=0)
    details.set_line_wrap(True)
    details.set_selectable(True)
    scroll = Gtk.ScrolledWindow()
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scroll.add(details)
    page.pack_end(scroll, True, True, 0)
    state = {'tag': None, 'downloaded': False}
    buttons = {label: Gtk.Button(label=label) for label in
               ('Consultar', 'Baixar e verificar', 'Instalar', 'Histórico', 'Restaurar versão anterior')}

    def enable(busy=False):
        for button in buttons.values():
            button.set_sensitive(not busy)
        buttons['Baixar e verificar'].set_sensitive(not busy and state['tag'] is not None)
        buttons['Instalar'].set_sensitive(not busy and state['downloaded'])

    def launch(task, finish):
        enable(True)
        details.set_text('Processando solicitação…')

        def completed(future):
            if not dashboard.closed:
                try:
                    details.set_text(finish(future.result()))
                except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
                    details.set_text(f'Operação interrompida. {error}')
                enable()
            return False

        future = dashboard.pool.submit(task)
        future.add_done_callback(lambda done: GLib.idle_add(completed, done))

    def consult(_button):
        state.update(tag=None, downloaded=False)

        def report(result):
            tag, notes = result
            state['tag'] = tag
            return f'Instalada: {updater.installed()}\n' + (f'Disponível: {tag}\n\n' if tag else '') + notes

        launch(updater.latest, report)

    def download(_button):
        state['downloaded'] = False
        tag = state['tag']

        def fetch():
            with TemporaryDirectory(prefix='devlite-update-') as folder:
                path = Path(folder)
                updater.download(tag, path)
                return updater.digest(updater.verify(tag, path))

        def report(digest):
            state['downloaded'] = digest
            return f'{tag}: assinatura e SHA-256 válidos. A instalação fará uma nova verificação administrativa.'

        launch(fetch, report)

    def admin(action):
        arguments = [action, state['tag'], state['downloaded']] if action == 'install' else [action]
        state.update(tag=None, downloaded=False)

        def run():
            process = subprocess.run(['/usr/bin/pkexec', updater.HELPER, *arguments],
                                     capture_output=True, text=True, stdin=subprocess.DEVNULL)
            if process.returncode:
                raise ValueError(process.stderr.strip() or 'Autorização cancelada ou instalação indisponível.')

        launch(run, lambda _: f'Operação concluída. Versão instalada: {updater.installed()}. Reabra o DevControl.')

    def restore(_button):
        dialog = Gtk.MessageDialog(transient_for=dashboard, modal=True,
                                   message_type=Gtk.MessageType.QUESTION, buttons=Gtk.ButtonsType.OK_CANCEL,
                                   text='Restaurar a versão anterior verificada?')
        dialog.set_default_response(Gtk.ResponseType.CANCEL)
        confirmed = dialog.run() == Gtk.ResponseType.OK
        dialog.destroy()
        if confirmed:
            admin('restore')

    callbacks = (consult, download, lambda _: admin('install'),
                 lambda _: launch(updater.history, str), restore)
    for button, callback in zip(buttons.values(), callbacks):
        button.set_halign(Gtk.Align.START)
        button.connect('clicked', callback)
        page.pack_start(button, False, False, 0)
    enable()
