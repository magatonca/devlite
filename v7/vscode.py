"""DevControl client for the fixed official VS Code action."""
from pathlib import Path
import subprocess

HELPER = '/usr/libexec/devlite-install-vscode'
ENV = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8'}


def installed():
    return any(Path(path).is_file() for path in ('/usr/bin/code', '/snap/bin/code'))


def live(tokens):
    return 'boot=casper' in tokens or any(token.startswith('layerfs-path=') for token in tokens)


def install():
    try:
        result = subprocess.run(['/usr/bin/pkexec', HELPER], env=ENV, stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                timeout=660, check=False)
    except subprocess.TimeoutExpired as error:
        raise RuntimeError('Tempo limite excedido. Atualize o estado antes de tentar novamente.') from error
    except OSError as error:
        raise RuntimeError('A autorização administrativa está indisponível.') from error
    if result.returncode == 126:
        raise RuntimeError('Autenticação cancelada.')
    if result.returncode == 127:
        raise RuntimeError('Autorização negada ou indisponível.')
    if result.returncode or not installed():
        raise RuntimeError('A instalação não foi confirmada pelo sistema.')
