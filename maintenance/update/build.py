#!/usr/bin/env python3
"""Build a local DEB and checksum. Signing is a separate operator action."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from maintenance.update.updater import package_name
from v7.desktop import OVERLAY, PANEL, apply_devcontrol


def build(output, public_key=None):
    version = (ROOT / 'VERSION').read_text().strip()
    filename = package_name('v' + version)
    output.mkdir(parents=True, exist_ok=False)
    with TemporaryDirectory(prefix='devlite-update-build-') as work:
        root = Path(work)
        legacy = root / 'usr/lib/devlite/devcontrol'
        legacy.mkdir(parents=True)
        shutil.copyfile(ROOT / 'v6/devcontrol/app.py', legacy / 'app.py')
        apply_devcontrol(root)
        rendered = (legacy / 'app.py').read_text().replace('DevControl 3.0', 'DevControl 3.1')
        rendered = rendered.replace("sys.path.insert(0, '/usr/lib/devlite/devcontrol')",
                                    "sys.path.insert(0, '/usr/lib/devlite/devcontrol')\n"
                                    "sys.path.insert(0, '/usr/lib/devlite-update')")
        anchor = '            self._create_services(notebook)'
        if rendered.count(anchor) != 1:
            raise ValueError('Ponto de integração do DevControl ausente.')
        rendered = rendered.replace(anchor, anchor + '\n            from update_ui import add_page\n'
                                    '            add_page(self, Gtk, GLib)')
        compile(rendered, 'app.py', 'exec')
        shutil.rmtree(legacy)

        def write(relative, content, mode=0o644):
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            path.chmod(mode)

        app = 'usr/lib/devlite-update'
        if public_key is not None:
            with TemporaryDirectory(prefix='devlite-public-key-') as key_home:
                packets = subprocess.check_output(
                    ['/usr/bin/gpg', '--homedir', key_home, '--batch', '--no-options',
                     '--no-autostart', '--list-packets', str(public_key)], text=True, timeout=15)
            if packets.count(':public key packet:') != 1 or ':secret ' in packets:
                raise ValueError('O chaveiro deve conter somente uma chave pública OpenPGP.')
            target = root / 'usr/share/keyrings/devlite-update.gpg'
            target.parent.mkdir(parents=True)
            shutil.copyfile(public_key, target)
            target.chmod(0o644)
        write(f'{app}/app.py', rendered)
        for filename_in in ('updater.py', 'update_ui.py'):
            write(f'{app}/{filename_in}', Path(__file__).with_name(filename_in).read_text(),
                  0o755 if filename_in == 'updater.py' else 0o644)
        policy = 'org.devlite.update.policy'
        write('usr/share/polkit-1/actions/' + policy, Path(__file__).with_name(policy).read_text())
        launcher = (ROOT / 'v6/overlay/usr/share/applications/devcontrol.desktop').read_text()
        write('usr/share/devlite-update/xdg-data/applications/devcontrol.desktop',
              launcher.replace('DevControl 3.0', 'DevControl 3.1').replace(
                  '/usr/lib/devlite/devcontrol/app.py', '/usr/lib/devlite-update/app.py'))
        branding = 'etc/default/grub.d/99-devlite-branding.cfg'
        session = 'etc/X11/Xsession.d/65devlite-update-xdg'
        profiles = 'usr/share/devlite-update/xdg-config'
        write(f'{profiles}/xfce4/panel/default.xml', (OVERLAY / PANEL).read_text())
        for name, overlay in [('terminal/terminalrc', OVERLAY),
                              ('whiskermenu/defaults.rc', ROOT / 'v6/overlay')]:
            source = overlay / 'etc/xdg/xdg-xubuntu/xfce4' / name
            write(f'{profiles}/xfce4/{name}', source.read_text())
        write(f'{profiles}/xfce-mimeapps.list', '[Default Applications]\ntext/plain=org.xfce.mousepad.desktop;\n')
        write(branding, (OVERLAY / branding).read_text())
        write(session, Path(__file__).with_name('session-xdg').read_text())
        write('DEBIAN/conffiles', f'/{branding}\n/{session}\n')
        for name in ('preinst', 'postrm', 'postinst'):
            write('DEBIAN/' + name, Path(__file__).with_name(name).read_text(), 0o755)
        for name, source in [('CHANGELOG.md', ROOT / 'CHANGELOG.md'),
                             ('manutencao.md', ROOT / 'docs/v7/manutencao-1.0.md'),
                             ('atualizacao.md', ROOT / 'docs/v7/atualizacao-1.0.1.md')]:
            write('usr/share/doc/devlite-update/' + name, source.read_text())
        write('DEBIAN/control', f'''Package: devlite-update
Version: {version}
Section: admin
Priority: optional
Architecture: amd64
Maintainer: DevLite OS <magatonca@users.noreply.github.com>
Depends: python3 (>= 3.11), python3-gi, gir1.2-gtk-3.0, gpgv, pkexec, ca-certificates, mousepad
Description: Manutenção da DevLite OS e DevControl 3.1
 Atualizações assinadas e padrões do desktop para a DevLite OS.
''')
        env = {**os.environ, 'SOURCE_DATE_EPOCH': os.environ.get('SOURCE_DATE_EPOCH', '1764547200')}
        subprocess.run(['/usr/bin/dpkg-deb', '--root-owner-group', '--build', str(root),
                        str(output / filename)], env=env, check=True)
    with (output / filename).open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    (output / 'SHA256SUMS').write_text(f'{digest}  {filename}\n')
    print(output / filename)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--public-key', type=Path)
    args = parser.parse_args()
    build(args.output, args.public_key)
