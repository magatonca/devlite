"""Execução explícita e preservação de evidências, sem shell ou exclusões."""
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path


class BuildError(RuntimeError):
    pass


def owned_directory(parent, prefix):
    import tempfile
    if parent.is_symlink() or not parent.is_dir():
        raise BuildError(f'Diretório inválido ou symlink: {parent}')
    path = Path(tempfile.mkdtemp(prefix=prefix, dir=parent))
    (path / '.devlite-workspace.json').write_text(json.dumps({
        'uid': os.getuid(), 'path': str(path.resolve()),
        'politica': 'preservar; nenhuma exclusão automática'}))
    return path


class Runner:
    def __init__(self, logs, epoch):
        self.logs = logs
        self.env = dict(os.environ, LC_ALL='C', TZ='UTC', SOURCE_DATE_EPOCH=str(epoch))
        self.counter = 0

    def run(self, label, args, allowed=(0,)):
        self.counter += 1
        safe_label = re.sub(r'[^A-Za-z0-9_-]+', '-', label).strip('-')[:100] or 'operation'
        prefix = self.logs / f'{self.counter:02d}-{safe_label}'
        # Operation numbers distinguish labels that normalize to the same name.
        with prefix.with_suffix('.command.json').open('x') as command:
            command.write(json.dumps(args, indent=2))
        print(f'[{datetime.now(timezone.utc).isoformat(timespec="seconds")}] {label}', flush=True)
        with prefix.with_suffix('.stdout').open('x') as out, prefix.with_suffix('.stderr').open('x') as err:
            result = subprocess.run(args, stdout=out, stderr=err, env=self.env)
        stdout = prefix.with_suffix('.stdout').read_text()
        stderr = prefix.with_suffix('.stderr').read_text()
        if result.returncode not in allowed:
            raise BuildError(f'{label}: código {result.returncode}; ver {prefix}.stderr')
        return stdout + stderr

    def xorriso(self, label, *args):
        return self.run(label, ['xorriso', '-no_rc', '-abort_on', 'FAILURE',
                               '-return_with', 'SORRY', '32', *map(str, args)])
