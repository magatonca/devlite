"""DevControl action for the built-in loopback Adminer instance."""
import subprocess

URL = 'http://127.0.0.1:8081/devlite-adminer'


def open_adminer(run=subprocess.run, launch=subprocess.Popen):
    unavailable = []
    for unit, name in (('apache2.service', 'Apache'), ('mariadb.service', 'MariaDB')):
        result = run(['/usr/bin/systemctl', 'is-active', '--quiet', unit], timeout=5)
        if result.returncode:
            unavailable.append(name)
    if unavailable:
        return 'Serviços inativos ou indisponíveis: ' + ', '.join(unavailable) + '.'
    launch(['/snap/bin/firefox', URL], start_new_session=True)
    return 'Solicitação de abertura do Adminer enviada ao Firefox.'
