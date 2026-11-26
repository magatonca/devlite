"""Install the verified Adminer payload and launch its fixed local endpoint."""
import hashlib
from pathlib import Path

from v5.image import confined, put
from v6.payload import prepare_parent

FILES = Path(__file__).with_name('adminer_files')
VENDOR = 'adminer-6.3.1-mysql.php'
SHA256 = '97fdb49c3e941636fe4b0559b2b042de3ac105dff0daafec3c255cd6bd81d4b6'
REQUIRED = {'apache2', 'libapache2-mod-php8.3', 'php8.3-mysql', 'mariadb-server'}


def apply(root, packages, run):
    if not REQUIRED <= packages.keys():
        raise ValueError('Missing Adminer runtime packages')
    payload = (FILES / VENDOR).read_bytes()
    if hashlib.sha256(payload).hexdigest() != SHA256:
        raise ValueError('Unexpected Adminer upstream SHA-256')
    base = 'usr/share/devlite-os/adminer'
    target = prepare_parent(root, f'{base}/{VENDOR}')
    with target.open('xb') as stream:
        stream.write(payload)
    target.chmod(0o644)
    empty = confined(root, f'{base}/empty')
    empty.mkdir(mode=0o755)
    empty.chmod(0o755)
    for name in ('index.php', 'policy.php'):
        put(root, f'{base}/{name}', (FILES / name).read_text())
    put(root, 'etc/apache2/conf-available/devlite-adminer.conf', (FILES / 'apache.conf').read_text())
    enabled = confined(root, 'etc/apache2/conf-enabled/devlite-adminer.conf')
    enabled.symlink_to('../conf-available/devlite-adminer.conf')
    for name in (VENDOR, 'index.php', 'policy.php'):
        run(['/usr/bin/php8.3', '-n', '-l', f'/{base}/{name}'])
    run(['/usr/sbin/apache2ctl', 'configtest'])
