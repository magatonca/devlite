"""Apply v7 desktop defaults to a disposable guest root."""
import os
from pathlib import Path

from v5.image import confined, put
from v6.payload import prepare_parent

DIRECTORY = Path(__file__).resolve().parent
OVERLAY = DIRECTORY / 'overlay'
LIVE_OVERLAY = DIRECTORY / 'live-overlay'
ICON = 'usr/share/icons/hicolor/scalable/apps/devlite.svg'


def apply(root, *, live=False):
    icon = confined(root, ICON)
    if icon.is_symlink() or not icon.is_file():
        raise ValueError('The inherited DevLite logo is required')
    written = []
    for overlay in (OVERLAY, LIVE_OVERLAY) if live else (OVERLAY,):
        for source in sorted(overlay.rglob('*')):
            if source.is_symlink():
                raise ValueError(f'Unexpected desktop overlay symlink: {source}')
            if source.is_file():
                relative = source.relative_to(overlay).as_posix()
                prepare_parent(root, relative)
                mode = 0o755 if relative in (
                    'usr/libexec/devlite-install-vscode', 'usr/libexec/devlite-launch-snap',
                    'usr/libexec/devlite-live-desktop'
                ) else 0o644
                put(root, relative, source.read_text(), mode)
                if os.geteuid() == 0 and relative in (
                        'usr/libexec/devlite-install-vscode',
                        'usr/share/polkit-1/actions/org.devlite.v7.vscode.policy'):
                    target = confined(root, relative)
                    for item in (target, *target.parents):
                        if item.is_symlink() or item.stat().st_uid != 0 or item.stat().st_mode & 0o022:
                            raise ValueError(f'Untrusted VS Code privilege path: {item}')
                        if item == root:
                            break
                written.append(relative)
    return written


def apply_devcontrol(root):
    """Reuse the installed v6 GTK application and add v7 runtime diagnostics."""
    directory = 'usr/lib/devlite/devcontrol'
    app = confined(root, directory + '/app.py')
    text = app.read_text()
    marker = 'from metrics import DevControlCollector'
    if text.count(marker) != 1:
        raise ValueError('Expected the v6 installed DevControl app')
    put(root, directory + '/metrics_v7.py', Path(__file__).with_name('devcontrol_metrics.py').read_text())
    put(root, directory + '/vscode_v7.py', (DIRECTORY / 'vscode.py').read_text())
    put(root, directory + '/adminer_action.py', (DIRECTORY / 'adminer_action.py').read_text())
    text = text.replace(marker, 'from metrics_v7 import DevControlCollector\n    import subprocess\n    import vscode_v7, adminer_action')
    anchor = '                    content.pack_start(tools, False, False, 0)'
    if text.count(anchor) != 1:
        raise ValueError('Expected the Development tools container')
    text = text.replace(anchor, anchor + '''
                    database = Gtk.Button(label='Gerenciar banco de dados')
                    database.set_halign(Gtk.Align.START)
                    database.connect('clicked', self.open_adminer)
                    content.pack_start(database, False, False, 0)''')
    tools = """            tools = Gtk.LinkButton.new_with_label(
                'https://code.visualstudio.com/docs/setup/linux', 'Obter VS Code')"""
    if text.count(tools) != 1:
        raise ValueError('Expected the original VS Code action')
    text = text.replace(tools, """            tools = Gtk.Button(label='Instalar VS Code oficial')
            tools.set_sensitive(
                not vscode_v7.live(self.collector._read('/proc/cmdline').split())
                and not vscode_v7.installed()
            )
            tools.connect('clicked', self.install_vscode)""")
    method = """        def open_adminer(self, _button):
            future = self.pool.submit(adminer_action.open_adminer)
            future.add_done_callback(lambda done: GLib.idle_add(self.adminer_finished, done))

        def adminer_finished(self, future):
            if not self.closed:
                try:
                    self.message.set_text(future.result())
                except (OSError, subprocess.SubprocessError):
                    self.message.set_text('Não foi possível verificar os serviços ou abrir o Firefox.')
            return False

        def install_vscode(self, button):
            dialog = Gtk.MessageDialog(
                transient_for=self, modal=True, message_type=Gtk.MessageType.QUESTION,
                text='Instalar Visual Studio Code da Microsoft?',
            )
            dialog.format_secondary_text(
                'O Snap oficial usa confinamento clássico e tem acesso aos arquivos do usuário. '
                'A instalação exige internet e autorização administrativa.'
            )
            dialog.add_button('Cancelar', Gtk.ResponseType.CANCEL)
            dialog.add_button('Instalar', Gtk.ResponseType.OK)
            dialog.set_default_response(Gtk.ResponseType.CANCEL)
            confirmed = dialog.run() == Gtk.ResponseType.OK
            dialog.destroy()
            if not confirmed:
                return
            button.set_sensitive(False)
            self.message.set_text('Instalação do VS Code em andamento…')
            future = self.pool.submit(vscode_v7.install)
            future.add_done_callback(lambda done: GLib.idle_add(self.vscode_finished, button, done))

        def vscode_finished(self, button, future):
            if self.closed:
                return False
            try:
                future.result()
                self.message.set_text('VS Code instalado.')
            except RuntimeError as error:
                self.message.set_text(str(error))
            button.set_sensitive(not vscode_v7.installed())
            if vscode_v7.installed():
                self.refresh()
            return False

"""
    text = text.replace('        def close(self, *_args):', method + '        def close(self, *_args):')
    put(root, directory + '/app.py', text)
