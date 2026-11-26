"""Offline curl transaction and strict checks inside the isolated v6 guest."""
import json
import socket
import sys
import tempfile
from pathlib import Path

import guest_runner as apt


def install():
    runtime = Path('/run/devlite-v6')
    locked = json.loads((runtime / 'request.json').read_text())
    archives = [str(runtime / 'debs' / Path(item['filename']).name) for item in locked]
    expected = {item['package']: item['version'] for item in locked}
    common = ['--no-download', '--no-remove', '--no-install-recommends']
    if apt.changes(apt.run(['/usr/bin/apt-get', '-s', *common, 'install', *archives])) != expected:
        raise SystemExit('APT transaction differs from pinned packages')
    apt.install_local(archives, locked, common)


def check_loopback():
    lines = Path('/proc/net/dev').read_text().splitlines()[2:]
    interfaces = {line.split(':', 1)[0].strip() for line in lines if ':' in line}
    if interfaces != {'lo'}:
        raise SystemExit(f'Unexpected guest network interfaces: {sorted(interfaces)}')
    for family, address in ((socket.AF_INET, '127.0.0.1'), (socket.AF_INET6, '::1')):
        with socket.socket(family, socket.SOCK_STREAM) as listener:
            listener.bind((address, 0))
    print('IPv4 and IPv6 loopback sockets verified in the private network', flush=True)


def validate():
    check_loopback()
    if apt.run(['/usr/bin/dpkg', '--audit']).strip():
        raise SystemExit('Incomplete package database')
    apt.run(['/usr/bin/apt-get', '-s', 'check'])
    apt.run(['/usr/sbin/apache2ctl', '-t'])
    # The Debian trigger deliberately ignores mandb failures. Run the same
    # operation as the same account and require a successful exit.
    apt.run(['/usr/bin/setpriv', '--reuid', 'man', '--regid', 'man', '--init-groups',
             '--', '/usr/bin/mandb', '-pq'])
    apt.run(['/usr/bin/curl', '--version'])
    validate_ssh()


def validate_ssh():
    # /run is a private tmpfs mounted by the executor and is removed
    # before the guest filesystem is inventoried for the SquashFS delta.
    with tempfile.TemporaryDirectory(prefix='devlite-sshd-check-', dir='/run') as directory:
        key = str(Path(directory) / 'host_ed25519')
        apt.run(['/usr/bin/ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', key])
        options = ['-f', '/etc/ssh/sshd_config', '-h', key]
        apt.run(['/usr/sbin/sshd', '-t', *options])
        output = apt.run(['/usr/sbin/sshd', '-T', *options, '-C',
                          'user=root,host=localhost,addr=127.0.0.1,laddr=127.0.0.1,lport=22'])
        settings = dict(line.split(' ', 1) for line in output.splitlines() if ' ' in line)
        if settings.get('permitrootlogin') != 'no' or settings.get('permitemptypasswords') != 'no':
            raise SystemExit('Unexpected SSH policy')


if __name__ == '__main__':
    if sys.argv[1:] == []:
        install()
    elif sys.argv[1:] != ['--validate-only']:
        raise SystemExit('Unknown guest mode')
    validate()
