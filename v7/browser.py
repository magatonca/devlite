"""Install Firefox defaults after an offline guest browser transaction."""
import yaml

from pipeline.devlite.customize.installation import installed
from v5.image import confined, put
from v6.payload import prepare_parent

DESKTOP = 'devlite-firefox.desktop'
HELPER = 'usr/share/xfce4/helpers/devlite-firefox.desktop'
PROFILE = 'etc/apparmor.d/epiphany'
MIME = (
    'etc/skel/.config/mimeapps.list',
    'etc/xdg/xdg-xubuntu/xfce-mimeapps.list',
)
KEYS = {'text/html', 'application/xhtml+xml', 'x-scheme-handler/http', 'x-scheme-handler/https'}
HELPER_TEXT = '''[Desktop Entry]
Type=X-XFCE-Helper
Name=Firefox
Icon=firefox
X-XFCE-Category=WebBrowser
X-XFCE-Binaries=/usr/libexec/devlite-launch-snap;
X-XFCE-Commands=%B firefox;
X-XFCE-CommandsWithParameter=%B firefox "%s";
'''


def render_mime(text):
    header = '[Default Applications]'
    output = []
    section = ''
    found = set()
    for line in text.splitlines(keepends=True):
        value = line.strip()
        if value.startswith('[') and value.endswith(']'):
            section = value
        name = value.split('=', 1)[0]
        if section == header and name in KEYS and '=' in value:
            if name in found:
                raise ValueError(f'Duplicate default browser association: {name}')
            found.add(name)
            line = f'{name}={DESKTOP};\n'
        output.append(line)
    if found != KEYS:
        raise ValueError('Missing inherited browser associations')
    return ''.join(output)


def apply(root):
    # The image build must prepare and authenticate the seed before switching
    # defaults. These names reference the snapd-created launcher and desktop ID.
    seed = confined(root, 'var/lib/snapd/seed/seed.yaml')
    if seed.is_symlink() or not seed.is_file():
        raise ValueError('Missing verified Firefox seed')
    data = yaml.safe_load(seed.read_text())
    entries = {item['name'] for item in data['snaps']}
    if not {'firefox', 'core26'} <= entries:
        raise ValueError('Firefox and its base must be present in the verified seed')
    status = confined(root, 'var/lib/dpkg/status')
    if status.is_symlink() or {'epiphany-browser', 'epiphany-browser-data'} & installed(status.read_text()).keys():
        raise ValueError('Run the verified Epiphany removal before switching browser defaults')
    profile = confined(root, PROFILE)
    if profile.is_symlink() or (profile.exists() and not profile.is_file()):
        raise ValueError('Unexpected Epiphany profile')
    for name in MIME:
        current = confined(root, name)
        if current.is_symlink():
            raise ValueError(f'Unexpected browser defaults symlink: {name}')
        put(root, name, render_mime(current.read_text()))
    helpers = 'etc/skel/.config/xfce4/helpers.rc'
    original = confined(root, helpers)
    if original.is_symlink():
        raise ValueError('Unexpected XFCE helper defaults symlink')
    lines = original.read_text().splitlines(keepends=True)
    if sum(line.startswith('WebBrowser=') for line in lines) != 1:
        raise ValueError('Unexpected XFCE browser selection')
    put(root, helpers, ''.join('WebBrowser=devlite-firefox\n' if line.startswith('WebBrowser=') else line
                               for line in lines))
    prepare_parent(root, HELPER)
    put(root, HELPER, HELPER_TEXT)
    if profile.exists():
        profile.unlink()


def remove_epiphany(run):
    """Remove only the two Epiphany packages inside the isolated guest."""
    packages = ('epiphany-browser', 'epiphany-browser-data')
    command = ['/usr/bin/apt-get', '-o', 'DPkg::Use-Pty=0', '--no-download', '--no-install-recommends']
    preview = run([*command, '-s', 'purge', *packages])
    changes = []
    for line in preview.splitlines():
        if line.startswith(('Inst ', 'Conf ', 'Remv ', 'Purg ')):
            action, package, *_ = line.split()
            if action not in ('Remv', 'Purg'):
                raise ValueError('Epiphany removal proposed package installations or changes')
            changes.append(package)
    if sorted(changes) != sorted(packages):
        raise ValueError('Epiphany removal would affect packages outside its own payload')
    run([*command, '-y', 'purge', *packages])
