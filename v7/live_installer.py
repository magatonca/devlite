"""Prepare first boot of the asserted installer on a disposable Live overlay."""
from v5.image import confined, put
from v6.payload import prepare_parent

DESKTOP = '''[Desktop Entry]
Type=Application
Name=Instalar DevLite OS 1.0
Comment=Instalar o sistema neste computador
Exec=/usr/libexec/devlite-launch-installer
Icon=/usr/share/icons/hicolor/scalable/apps/devlite.svg
StartupWMClass=ubuntu_bootstrap
Terminal=false
Categories=System;
'''


LAUNCHER = 'usr/libexec/devlite-launch-installer'
START = '''#!/bin/sh
set -eu
exec /usr/libexec/devlite-launch-snap devlite-installer
'''


SOCKET_DROPIN = 'etc/systemd/system/snap.devlite-installer.subiquity-server.service.d/20-socket-access.conf'
SOCKET_ACCESS = '''[Service]
ExecStartPre=/usr/bin/install -d -o root -g sudo -m 0750 /run/subiquity
'''


def reset(root, run):
    # This is the snapd classic reset phase used after its own chroot/reexec.
    # The worker supplies a runner already confined to the disposable root.
    run(['/usr/lib/snapd/snap-preseed', '--reset-chroot'])
    state = confined(root, 'var/lib/snapd/state.json')
    if state.exists() or state.is_symlink():
        raise ValueError('Inherited snapd state survived reset')
    if list(confined(root, 'etc/systemd/system').rglob('*bootstrap*')):
        raise ValueError('Inherited installer units survived reset')
    put(root, 'usr/share/applications/devlite-installer.desktop', DESKTOP)
    shortcut = 'etc/skel/Desktop/devlite-installer.desktop'
    prepare_parent(root, shortcut)
    put(root, shortcut, DESKTOP, 0o755)
    stale = confined(root, 'etc/xdg/autostart/devlite-installer-branding.desktop')
    if stale.is_symlink() or (stale.exists() and not stale.is_file()):
        raise ValueError('Unexpected inherited installer autostart')
    if stale.exists():
        stale.unlink()
    prepare_parent(root, LAUNCHER)
    put(root, LAUNCHER, START, 0o755)
    prepare_parent(root, SOCKET_DROPIN)
    put(root, SOCKET_DROPIN, SOCKET_ACCESS)
