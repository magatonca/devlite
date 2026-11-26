"""Prepara somente configurações e locale, sem root e sem pacotes."""
import hashlib
import gzip
import json
import os
import platform
import re
import subprocess
from pathlib import Path
from .runtime import BuildError, Runner, owned_directory
from .minimal_root import allowed_configuration, EPOCH, guard_workspace
from .customize.settings import render


def read_member(image, name):
    result = subprocess.run(['unsquashfs', '-cat', str(image), name], capture_output=True)
    if result.returncode:
        raise BuildError('Não foi possível ler ' + name)
    return result.stdout


def replace_field(text, key, value):
    replacement = key + '=' + json.dumps(value, ensure_ascii=False)
    result, count = re.subn(r'^' + re.escape(key) + r'=.*$', lambda match: replacement, text, flags=re.M)
    return result if count else text.rstrip() + '\n' + replacement + '\n'


def prepare_configuration(root, workspace):
    guard_workspace(workspace)
    source = workspace / 'original-casper/minimal.squashfs'
    settings = json.loads((root / 'config/customization.json').read_text())
    files = render(settings)['files']
    payloads = {}
    for name in ('etc/default/keyboard', 'etc/timezone', 'etc/devlite-release', 'usr/share/devlite-os/identity.json'):
        payloads[name] = files[name]['content'].encode()
    payloads['etc/locale.conf'] = b'LANG=pt_BR.UTF-8\nLANGUAGE=pt_BR:pt\n'
    current = read_member(source, 'etc/locale.gen').decode()
    current = re.sub(r'^#\s*(pt_BR\.UTF-8\s+UTF-8)\s*$', r'\1', current, flags=re.M)
    if not re.search(r'^pt_BR\.UTF-8\s+UTF-8$', current, re.M):
        current += '\npt_BR.UTF-8 UTF-8\n'
    payloads['etc/locale.gen'] = current.encode()
    release = read_member(source, 'usr/lib/os-release').decode()
    for key, value in (('NAME', 'DevLite OS'), ('PRETTY_NAME', 'DevLite OS 1.0 — Developer + Network Edition'),
                       ('VARIANT', 'Developer + Network Edition'), ('VARIANT_ID', 'developer-network'), ('DEVLITE_VERSION', '1.0')):
        release = replace_field(release, key, value)
    if not re.search(r'^ID=ubuntu$', release, re.M) or not re.search(r'^UBUNTU_CODENAME=noble$', release, re.M):
        raise BuildError('Não alterar ID Ubuntu nem codename Noble')
    payloads['usr/lib/os-release'] = release.encode()
    lsb = read_member(source, 'etc/lsb-release').decode()
    payloads['etc/lsb-release'] = replace_field(lsb, 'DISTRIB_DESCRIPTION', 'DevLite OS 1.0 — Developer + Network Edition').encode()
    logs = owned_directory(workspace, 'configuration-logs-')
    runner = Runner(logs, EPOCH)
    i18n = workspace / 'locale-input'
    if not i18n.exists():
        runner.run('extract-locale-data', ['unsquashfs', '-no-xattrs', '-processors', '1', '-no-progress',
               '-d', str(i18n), str(source), 'usr/share/i18n'])
    data = i18n / 'usr/share/i18n'
    status = read_member(source, 'var/lib/dpkg/status').decode()
    libc = next(block for block in status.split('\n\n') if block.startswith('Package: libc6\n'))
    version = re.search(r'^Version: (.+)$', libc, re.M)[1]
    if not version.startswith(platform.libc_ver()[1] + '-'):
        raise BuildError('Formato locale exige glibc host/alvo da mesma versão principal/secundária')
    charmap = workspace / 'UTF-8.charmap'
    if not charmap.exists():
        charmap.write_bytes(gzip.decompress((data / 'charmaps/UTF-8.gz').read_bytes()))
    localedir = owned_directory(workspace, 'generated-locales-')
    runner.env['I18NPATH'] = str(data / 'locales')
    runner.run('generate-pt-BR', ['localedef', '--no-archive', '-i', str(data / 'locales/pt_BR'),
               '-f', str(charmap), str(localedir / 'pt_BR.utf8')])
    runner.env.update(LOCPATH=str(localedir), LC_ALL='pt_BR.UTF-8')
    if runner.run('verify-generated-locale', ['locale', 'charmap']).strip() != 'UTF-8':
        raise BuildError('Locale gerado inválido')
    for path in (localedir / 'pt_BR.utf8').rglob('*'):
        if path.is_file():
            payloads['usr/lib/locale/pt_BR.utf8/' + path.relative_to(localedir / 'pt_BR.utf8').as_posix()] = path.read_bytes()
    output = workspace / 'configuration'; output.mkdir()
    manifest = {}
    for name, content in payloads.items():
        if not allowed_configuration(name):
            raise BuildError('Payload fora da allowlist')
        path = output / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(content)
        manifest[name] = {'kind': 'file', 'sha256': hashlib.sha256(content).hexdigest()}
    manifest['etc/localtime'] = {'kind': 'symlink', 'target': '../usr/share/zoneinfo/America/Sao_Paulo'}
    (workspace / 'configuration.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (workspace / 'rebuilt-casper').mkdir()
    print('Configurações preparadas:', len(manifest), flush=True)
