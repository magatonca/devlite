"""Updates page embedded in the existing DevControl GTK dashboard."""
from collections import deque
from datetime import datetime
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

import updater

INSTALL_STAGES = {
    'prepare': (0.2, 'Preparando o pacote em área administrativa…'),
    'verified': (0.6, 'Assinatura digital e SHA-256 confirmados pelo instalador.'),
    'dpkg': (0.8, 'Aplicando o pacote pelo dpkg…'),
}


def run_admin(arguments, progress):
    errors = deque(maxlen=5)
    with subprocess.Popen(['/usr/bin/pkexec', updater.HELPER, *arguments],
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, stdin=subprocess.DEVNULL) as process:
        for line in process.stdout:
            prefix, _, code = line.strip().partition(' ')
            if prefix == 'DEVLITE_PROGRESS' and code in INSTALL_STAGES:
                progress(*INSTALL_STAGES[code])
            elif line.strip():
                errors.append(line.strip()[:500])
        if process.wait():
            raise ValueError(' '.join(errors) or 'Autorização cancelada ou instalação indisponível.')


def add_page(dashboard, Gtk, GLib):
    scroll = Gtk.ScrolledWindow()
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin=10)
    scroll.add(page)
    dashboard.notebook.append_page(scroll, Gtk.Label(label='Atualizações'))

    def label(parent, text, heading=False):
        widget = Gtk.Label(label=text, xalign=0)
        widget.set_line_wrap(True)
        widget.set_selectable(True)
        if heading:
            widget.get_style_context().add_class('metric-title')
        parent.pack_start(widget, False, False, 0)
        return widget

    versions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18, homogeneous=True)
    page.pack_start(versions, False, False, 0)
    installed_column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
    available_column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
    for column in (installed_column, available_column):
        column.get_style_context().add_class('card')
        versions.pack_start(column, True, True, 0)
    label(installed_column, 'Versão instalada')
    current = label(installed_column, updater.installed(), True)
    label(available_column, 'Versão disponível')
    available = label(available_column, 'A consultar', True)
    last_check = label(page, 'Última consulta nesta sessão: nenhuma')
    details = label(page, 'Consulte o GitHub para verificar atualizações.')
    signature = label(page, 'Assinatura digital: aguardando verificação')
    bar = Gtk.ProgressBar()
    bar.set_show_text(True)
    bar.set_text('Pronto')
    page.pack_start(bar, False, False, 0)

    state = {'tag': None, 'downloaded': None}
    actions = ('Consultar', 'Baixar e verificar', 'Instalar', 'Atualizar histórico', 'Restaurar versão anterior')
    buttons = {action: Gtk.Button(label=action) for action in actions}
    for group in (actions[:3], actions[3:]):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        page.pack_start(row, False, False, 0)
        for action in group:
            row.pack_start(buttons[action], False, False, 0)

    label(page, 'Alterações da versão', True)
    changelog = label(page, 'O CHANGELOG será exibido após a consulta.')
    label(page, 'Histórico de atualizações', True)
    history = label(page, 'Consulte o histórico para ver os resultados anteriores.')

    def enable(busy=False):
        for button in buttons.values():
            button.set_sensitive(not busy)
        buttons['Baixar e verificar'].set_sensitive(not busy and state['tag'] is not None)
        buttons['Instalar'].set_sensitive(not busy and bool(state['downloaded']))

    def show_progress(fraction, message):
        if not dashboard.closed:
            bar.set_fraction(fraction)
            bar.set_text(message)
        return False

    def progress(fraction, message):
        GLib.idle_add(show_progress, fraction, message)

    def launch(task, finish, started, failed=None):
        enable(True)
        show_progress(0, started)

        def completed(future):
            if not dashboard.closed:
                try:
                    details.set_text(finish(future.result()))
                    show_progress(1, 'Concluído')
                except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
                    details.set_text(f'Operação interrompida. {error}')
                    show_progress(0, 'Interrompido')
                    if failed:
                        failed()
                enable()
            return False

        future = dashboard.pool.submit(task)
        future.add_done_callback(lambda done: GLib.idle_add(completed, done))

    def mark_consultation():
        stamp = datetime.now().astimezone().strftime('%d/%m/%Y %H:%M:%S %Z')
        last_check.set_text(f'Última consulta nesta sessão: {stamp}')

    def consult(_button):
        state.update(tag=None, downloaded=None)
        signature.set_text('Assinatura digital: aguardando verificação')
        available.set_text('Consultando…')
        changelog.set_text('Carregando as notas da versão…')

        def report(result):
            tag, notes = result
            state['tag'] = tag
            mark_consultation()
            current.set_text(updater.installed())
            available.set_text(tag.removeprefix('v') if tag else 'Nenhuma')
            changelog.set_text(notes if tag else 'Nenhuma atualização pendente.')
            return 'Atualização disponível.' if tag else notes

        def failed():
            mark_consultation()
            available.set_text('Consulta indisponível')
            changelog.set_text('O CHANGELOG está indisponível.')

        launch(updater.latest, report, 'Consultando GitHub…', failed)

    def download(_button):
        state['downloaded'] = None
        tag = state['tag']
        signature.set_text('Assinatura digital: aguardando o download')

        def fetch():
            with TemporaryDirectory(prefix='devlite-update-') as folder:
                path = Path(folder)
                updater.download(tag, path, lambda fraction, message: progress(fraction * 0.85, message))
                progress(0.9, 'Verificando assinatura e SHA-256…')
                return updater.digest(updater.verify(tag, path))

        def report(digest):
            state['downloaded'] = digest
            signature.set_text('Assinatura digital: válida. SHA-256 confirmado.')
            return f'{tag}: pacote pronto para instalação administrativa.'

        launch(fetch, report, 'Iniciando download…',
               lambda: signature.set_text('Assinatura digital: verificação não concluída'))

    def admin(action):
        arguments = [action, state['tag'], state['downloaded']] if action == 'install' else [action]

        def report(_result):
            state.update(tag=None, downloaded=None)
            current.set_text(updater.installed())
            available.set_text('A consultar')
            signature.set_text('Assinatura digital: válida. Verificação administrativa concluída.')
            return 'Operação concluída. Reabra o DevControl para carregar a versão instalada.'

        launch(lambda: run_admin(arguments, progress), report, 'Aguardando autorização administrativa…')

    def restore(_button):
        dialog = Gtk.MessageDialog(transient_for=dashboard, modal=True,
                                   message_type=Gtk.MessageType.QUESTION, buttons=Gtk.ButtonsType.OK_CANCEL,
                                   text='Restaurar a versão anterior verificada?')
        dialog.set_default_response(Gtk.ResponseType.CANCEL)
        confirmed = dialog.run() == Gtk.ResponseType.OK
        dialog.destroy()
        if confirmed:
            admin('restore')

    def show_history(records):
        history.set_text(records)
        return 'Histórico atualizado.'

    callbacks = (consult, download, lambda _: admin('install'),
                 lambda _: launch(updater.history, show_history, 'Lendo o histórico…'), restore)
    for button, callback in zip(buttons.values(), callbacks):
        button.connect('clicked', callback)
    enable()
