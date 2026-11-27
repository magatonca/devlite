#!/usr/bin/python3 -I
"""GitHub release client and narrowly scoped privileged installer."""
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request

PROJECT = 'magatonca/devlite'
API = f'https://api.github.com/repos/{PROJECT}/releases/latest'
RELEASE = f'https://github.com/{PROJECT}/releases/download'
KEYRING = Path('/usr/share/keyrings/devlite-update.gpg')
ADMIN_KEYRING = Path('/etc/devlite-update.gpg')
STATE = Path('/var/lib/devlite-update')
HELPER = '/usr/lib/devlite-update/updater.py'
PACKAGE = 'devlite-update'
ARCH = 'amd64'
MAX_PACKAGE = 32 * 1024**2
ENV = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LC_ALL': 'C.UTF-8', 'DEBIAN_FRONTEND': 'noninteractive'}


def version(tag):
    if not re.fullmatch(r'v(?:0|[1-9][0-9]{0,8})(?:\.(?:0|[1-9][0-9]{0,8})){2}', tag):
        raise ValueError('Versão inválida.')
    return tag[1:]


def package_name(tag):
    return f'{PACKAGE}_{version(tag)}_{ARCH}.deb'


class ReleaseRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urllib.parse.urlsplit(newurl)
        if (target.scheme != 'https' or target.netloc not in {
                'github.com', 'api.github.com', 'release-assets.githubusercontent.com',
                'objects.githubusercontent.com'}):
            raise ValueError('Redirecionamento fora dos servidores de Releases.')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url, limit):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), ReleaseRedirect())
    request = urllib.request.Request(url, headers={'User-Agent': 'DevLite-Update'})
    with opener.open(request, timeout=12) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Arquivo excede o tamanho permitido.')
    return data


def installed():
    result = subprocess.run(['/usr/bin/dpkg-query', '-W', '-f=${db:Status-Status} ${Version}',
                             PACKAGE], env=ENV, capture_output=True, text=True, timeout=10)
    status, _, current = result.stdout.partition(' ')
    return current if status not in ('', 'not-installed', 'config-files') else '1.0.0'


def latest():
    data = json.loads(fetch(API, 256 * 1024))
    tag = data['tag_name']
    available = version(tag)
    names = {asset['name'] for asset in data['assets']}
    if (data['draft'] or data['prerelease'] or
            not {package_name(tag), 'SHA256SUMS', 'SHA256SUMS.sig'} <= names):
        raise ValueError('Publicação incompleta.')
    if not newer(available, installed()):
        return None, 'O DevControl já está atualizado.'
    return tag, str(data.get('body') or 'Sem notas publicadas.')[:4000]


def newer(a, b):
    return subprocess.run(['/usr/bin/dpkg', '--compare-versions', a, 'gt', b],
                          env=ENV, timeout=10).returncode == 0


def download(tag, folder):
    name = package_name(tag)
    for asset, size in [('SHA256SUMS', 4096), ('SHA256SUMS.sig', 16384), (name, MAX_PACKAGE)]:
        (folder / asset).write_bytes(fetch(f'{RELEASE}/{tag}/{asset}', size))


def verify(tag, folder, keyring=None):
    if keyring is None:
        keyring = ADMIN_KEYRING if os.path.lexists(ADMIN_KEYRING) else KEYRING
    name = package_name(tag)
    mode = keyring.lstat()
    if not stat.S_ISREG(mode.st_mode) or mode.st_uid != 0 or mode.st_mode & 0o022:
        raise ValueError('O chaveiro precisa ser um arquivo administrativo protegido.')
    sums = folder / 'SHA256SUMS'
    signature = folder / 'SHA256SUMS.sig'
    package = folder / name
    for path, limit in [(sums, 4096), (signature, 16384), (package, MAX_PACKAGE)]:
        if not stat.S_ISREG(path.lstat().st_mode) or path.stat().st_size > limit:
            raise ValueError('Arquivo de atualização inválido.')
    # An explicit, absolute keyring is the only trust source for gpgv.
    subprocess.run(['/usr/bin/gpgv', '--keyring', str(keyring), str(signature), str(sums)],
                   env=ENV, check=True, capture_output=True, timeout=15)
    match = re.fullmatch(r'([0-9a-f]{64}) [ *]' + re.escape(name) + r'\n', sums.read_text('ascii'))
    if not match:
        raise ValueError('Manifesto SHA-256 incompatível.')
    if digest(package) != match[1]:
        raise ValueError('SHA-256 divergente.')
    for field, expected in [('Package', PACKAGE), ('Version', version(tag)), ('Architecture', ARCH)]:
        actual = subprocess.check_output(['/usr/bin/dpkg-deb', '-f', str(package), field],
                                         env=ENV, text=True, timeout=10).strip()
        if actual != expected:
            raise ValueError(f'Metadado DEB incorreto: {field}.')
    return package


def history():
    try:
        with (STATE / 'history.jsonl').open() as stream:
            from collections import deque
            records = deque(stream, maxlen=20)
    except FileNotFoundError:
        return 'Nenhuma atualização registrada pelo DevControl.'
    return '\n'.join(f"{item['date']} · {item['action']} {item['tag']} · {item['result']}"
                      for item in map(json.loads, reversed(records)))


def privileged(action, tag=None, expected=None):
    if os.geteuid() != 0:
        raise ValueError('É necessária autorização administrativa.')
    if action == 'install':
        version(tag)
        if not re.fullmatch(r'[0-9a-f]{64}', expected or ''):
            raise ValueError('SHA-256 da atualização não informado.')
    os.umask(0o022)
    STATE.mkdir(mode=0o755, exist_ok=True)
    cache = STATE / 'releases'
    cache.mkdir(mode=0o700, exist_ok=True)
    for path in (STATE, cache):
        meta = path.lstat()
        if not stat.S_ISDIR(meta.st_mode) or meta.st_uid != 0 or meta.st_mode & 0o022:
            raise ValueError('Diretório de atualizações inseguro.')
    with (cache / 'lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        current = installed()
        if action == 'restore':
            candidates = [p.name for p in cache.iterdir() if p.is_dir() and
                          (p / 'installed').is_file() and
                          re.fullmatch(r'v[0-9]+(?:\.[0-9]+){2}', p.name) and newer(current, version(p.name))]
            if not candidates:
                raise ValueError('Nenhuma versão anterior armazenada. Consulte o roteiro de recuperação.')
            tag = max(candidates, key=lambda candidate: tuple(map(int, version(candidate).split('.'))))
        elif not newer(version(tag), current):
            raise ValueError('A atualização precisa ser mais recente que a versão instalada.')
        result = 'falhou'
        try:
            destination = cache / tag
            if not destination.exists() and action == 'install':
                with tempfile.TemporaryDirectory(dir=cache, prefix='fetch-') as temporary:
                    source = Path(temporary)
                    download(tag, source)
                    package = verify(tag, source)
                    if digest(package) != expected:
                        raise ValueError('A publicação mudou desde a verificação na interface.')
                    # Keep a verified copy for later recovery.
                    destination.mkdir(mode=0o700)
                    try:
                        for asset in ('SHA256SUMS', 'SHA256SUMS.sig', package_name(tag)):
                            (source / asset).replace(destination / asset)
                    except OSError:
                        for entry in destination.iterdir():
                            entry.unlink()
                        destination.rmdir()
                        raise
            package = verify(tag, destination)
            if action == 'install' and digest(package) != expected:
                raise ValueError('A publicação mudou desde a verificação na interface.')
            # dpkg installs only the verified local package. Dependencies are
            # resolved on initial installation through official Ubuntu APT.
            args = ['/usr/bin/dpkg', '--force-confold', '--refuse-downgrade']
            if action == 'restore':
                args.remove('--refuse-downgrade')
            subprocess.run([*args, '--install', str(package)], env=ENV, check=True)
            (destination / 'installed').touch()
            result = 'concluída'
        finally:
            record = {'date': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
                      'action': 'instalação' if action == 'install' else 'recuperação',
                      'tag': tag, 'result': result}
            with (STATE / 'history.jsonl').open('a') as stream:
                stream.write(json.dumps(record, ensure_ascii=False) + '\n')


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main(argv):
    if len(argv) == 3 and argv[1] == 'verify-local' and os.geteuid() != 0:
        print(verify(argv[2], Path.cwd()))
    elif len(argv) == 4 and argv[1] == 'install':
        privileged('install', argv[2], argv[3])
    elif argv[1:] == ['restore']:
        privileged('restore')
    else:
        raise ValueError('Operação de atualização inválida.')


if __name__ == '__main__':
    try:
        main(sys.argv)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error))
