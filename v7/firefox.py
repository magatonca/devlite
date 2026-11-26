"""Acquire Firefox's official signed apt packages without changing the host."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from urllib.request import urlopen

from v6.storage import GIB, ROOT, require_space

ORIGIN = 'https://packages.mozilla.org/apt'
FINGERPRINT = '35BAA0B33E9EB396F59CA838C0BA5CE6DC6315A3'
PACKAGES = ('firefox', 'firefox-l10n-pt-br')


def primary_fingerprints(output):
    fingerprints = []
    primary = False
    for line in output.splitlines():
        fields = line.split(':')
        if fields[0] in ('pub', 'sub'):
            primary = fields[0] == 'pub'
        elif fields[0] == 'fpr' and primary:
            fingerprints.append(fields[9])
            primary = False
    return fingerprints


def acquire():
    require_space(ROOT, GIB)
    job = Path(tempfile.mkdtemp(prefix='v7-firefox-', dir=ROOT / 'work'))
    for relative in ('lists/partial', 'archives/partial', 'gnupg', 'empty', 'payload'):
        (job / relative).mkdir(mode=0o700, parents=True)
    key = job / 'mozilla.asc'
    with urlopen(ORIGIN + '/repo-signing-key.gpg', timeout=30) as response:
        content = response.read(65537)
    if len(content) > 65536:
        raise ValueError('Unexpected key size')
    key.write_bytes(content)
    output = subprocess.check_output(['/usr/bin/gpg', '--homedir', str(job / 'gnupg'),
                                      '--batch', '--with-colons', '--show-keys', str(key)], text=True)
    if primary_fingerprints(output) != [FINGERPRINT]:
        raise ValueError('Mozilla key does not match the published fingerprint')
    source = job / 'mozilla.list'
    source.write_text(f'deb [arch=amd64 signed-by={key}] {ORIGIN} mozilla main\n')
    (job / 'status').touch()
    conf = job / 'apt.conf'
    conf.write_text(f'''Dir::Etc::main "/dev/null";
Dir::Etc::parts "{job}/empty";
Dir::Etc::sourcelist "{source}";
Dir::Etc::sourceparts "{job}/empty";
Dir::State::status "{job}/status";
Dir::State::lists "{job}/lists";
Dir::Cache::archives "{job}/archives";
Dir::Cache::pkgcache "";
Dir::Cache::srcpkgcache "";
Acquire::AllowInsecureRepositories "false";
Acquire::Check-Valid-Until "true";
Acquire::Retries "0";
Acquire::Languages "none";
''')
    env = {**os.environ, 'APT_CONFIG': str(conf), 'LC_ALL': 'C'}
    subprocess.run(['/usr/bin/apt-get', 'update'], env=env, cwd=job, timeout=90, check=True)
    candidates = {}
    for package in PACKAGES:
        policy = subprocess.check_output(['/usr/bin/apt-cache', 'policy', package], env=env, text=True)
        candidates[package] = next(line.split(':', 1)[1].strip() for line in policy.splitlines()
                                   if line.strip().startswith('Candidate:'))
    if len(set(candidates.values())) != 1 or '(none)' in candidates.values():
        raise ValueError('Firefox and pt-BR pack candidates differ')
    subprocess.run(['/usr/bin/apt-get', 'download',
                    *(f'{name}=\u200b{version}'.replace('\u200b', '') for name, version in candidates.items())],
                   env=env, cwd=job / 'payload', timeout=300, check=True)
    files = {}
    for archive in sorted((job / 'payload').glob('*.deb')):
        with archive.open('rb') as stream:
            files[archive.name] = hashlib.file_digest(stream, 'sha256').hexdigest()
    if len(files) != len(PACKAGES):
        raise ValueError('Unexpected number of archives')
    (job / 'receipt.json').write_text(json.dumps({'origin': ORIGIN, 'key_fingerprint': FINGERPRINT,
                                                'packages': candidates, 'sha256': files}, indent=2) + '\n')
    print(job)


if __name__ == '__main__':
    acquire()
