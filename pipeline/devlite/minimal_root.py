"""Auxiliar privilegiado restrito ao workspace: sem montagem, chroot ou pacotes."""
import base64
import errno
import hashlib
import json
import os
import stat
import subprocess
from pathlib import Path, PurePosixPath
from .runtime import BuildError

PROJECT = Path('/home/magaton/DevLite-OS')
HASHES = {'minimal.squashfs': 'b258171ed250cb92f2adc75041710a52fd1a0f3bfe0c952b4660f39a5cef3876',
          'minimal.live.squashfs': '48c5aee7da2216808dab276fe69ff240e2cd9bdb1ea4761e2358d7cdb795bf17'}
EPOCH = 1788856610
BASIC = {'etc/locale.conf', 'etc/locale.gen', 'etc/default/keyboard', 'etc/timezone', 'etc/localtime',
         'etc/devlite-release', 'usr/share/devlite-os/identity.json', 'usr/lib/os-release', 'etc/lsb-release'}
LOCALE_FILES = {'LC_CTYPE', 'LC_NUMERIC', 'LC_TIME', 'LC_COLLATE', 'LC_MONETARY', 'LC_MESSAGES/SYS_LC_MESSAGES',
                'LC_PAPER', 'LC_NAME', 'LC_ADDRESS', 'LC_TELEPHONE', 'LC_MEASUREMENT', 'LC_IDENTIFICATION'}


def file_hash(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def guard_workspace(workspace):
    if (PROJECT / 'work').is_symlink():
        raise BuildError('work não pode ser symlink')
    if workspace.is_symlink() or workspace.resolve().parent != (PROJECT / 'work').resolve() or not workspace.name.startswith('phase4b1-'):
        raise BuildError('Workspace fora do escopo autorizado')
    if workspace.stat().st_uid != 1000:
        raise BuildError('Workspace deve pertencer a magaton')
    marker = json.loads((workspace / '.devlite-workspace.json').read_text())
    if marker.get('path') != str(workspace.resolve()) or marker.get('uid') != 1000:
        raise BuildError('Marcador de workspace inválido')


def member(root, relative):
    value = PurePosixPath(relative)
    if value.is_absolute() or '..' in value.parts or relative in ('', '.'):
        raise BuildError('Caminho de alteração inseguro')
    current = root
    if current.is_symlink() or not current.is_dir():
        raise BuildError('Raiz inválida')
    for component in value.parts[:-1]:
        current = current / component
        if current.is_symlink():
            raise BuildError('Ancestral symlink não pode ser seguido')
    return root / value


def read_xattrs(path,name,absence_proof):
    try:
        keys=os.listxattr(path,follow_symlinks=False)
    except OSError as error:
        # Only callers with a sealed, table-less SquashFS proof may authorize
        # individual paths whose independently computed expected xattrs are empty.
        if error.errno==errno.EOPNOTSUPP and name in absence_proof:return {}
        raise
    return {key:base64.b64encode(os.getxattr(path,key,follow_symlinks=False)).decode() for key in sorted(keys)}


def snapshot(root,*,xattr_absence=frozenset()):
    entries, links = {}, {}
    paths = [root] + sorted(root.rglob('*'))
    for number, path in enumerate(paths, 1):
        if number % 10000 == 0:
            print(f'Auditoria: {number}/{len(paths)} caminhos — {root.name}', flush=True)
        info = path.lstat()
        name = path.relative_to(root).as_posix()
        kind = ('file' if stat.S_ISREG(info.st_mode) else 'dir' if stat.S_ISDIR(info.st_mode)
                else 'symlink' if stat.S_ISLNK(info.st_mode) else 'char' if stat.S_ISCHR(info.st_mode)
                else 'block' if stat.S_ISBLK(info.st_mode) else 'fifo' if stat.S_ISFIFO(info.st_mode)
                else 'socket' if stat.S_ISSOCK(info.st_mode) else 'unknown')
        value = {'type': kind, 'mode': stat.S_IMODE(info.st_mode), 'uid': info.st_uid, 'gid': info.st_gid,
                 'mtime': int(info.st_mtime), 'xattrs': read_xattrs(path,name,xattr_absence)}
        if kind == 'file':
            key = (info.st_dev, info.st_ino)
            if key not in links:
                links[key] = {'paths': [], 'sha256': file_hash(path)}
            links[key]['paths'].append(name)
            value.update(size=info.st_size, sha256=links[key]['sha256'])
            value['_link_key'] = key
        elif kind == 'symlink':
            value['target'] = os.readlink(path)
        elif kind in ('char', 'block'):
            value['device'] = [os.major(info.st_rdev), os.minor(info.st_rdev)]
        entries[name] = value
    for value in entries.values():
        if value['type'] == 'file':
            value['hardlinks'] = sorted(links[value.pop('_link_key')]['paths'])
    return entries



def allocated_usage(root):
    seen, total = set(), 0
    for path in [root] + list(root.rglob('*')):
        info = path.lstat()
        key = (info.st_dev, info.st_ino)
        if key not in seen:
            seen.add(key); total += info.st_blocks * 512
    return total

def write_json(path, data):
    with path.open('x') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def command(workspace, label, args):
    env = dict(os.environ, LC_ALL='C', TZ='UTC')
    env.pop('SOURCE_DATE_EPOCH', None)
    logs = workspace / 'root-logs'
    logs.mkdir(exist_ok=True)
    for path in (logs, logs / (label + '.stdout'), logs / (label + '.stderr')):
        if path.is_symlink():
            raise BuildError('Log não pode ser symlink')
    write_json(logs / (label + '.command.json'), args)
    print(label, flush=True)
    with (logs / (label + '.stdout')).open('x') as out, (logs / (label + '.stderr')).open('x') as err:
        result = subprocess.run(args, stdout=out, stderr=err, env=env, cwd=workspace)
    if result.returncode:
        raise BuildError(f'{label} falhou: {result.returncode}; ver root-logs')


def extract(workspace):
    for name, folder in (('minimal.squashfs', 'base-root'), ('minimal.live.squashfs', 'live-root')):
        source = workspace / 'original-casper' / name
        if source.is_symlink() or file_hash(source) != HASHES[name]:
            raise BuildError('Camada de entrada não autenticada')
        target = workspace / folder
        if target.exists() or target.is_symlink():
            raise BuildError('Destino de extração já existe')
        command(workspace, 'extract-' + folder, ['unsquashfs', '-strict-errors', '-processors', '1',
                '-data-queue', '64', '-frag-queue', '64', '-no-progress', '-d', str(target), str(source)])
        print('Auditoria original: ' + folder, flush=True)
        write_json(workspace / (folder + '.before.json'), snapshot(target))
    write_json(workspace / 'root-extract-ok.json', {'status': 'ok'})


def allowed_configuration(name):
    return name in BASIC or (name.startswith('usr/lib/locale/pt_BR.utf8/') and name.removeprefix('usr/lib/locale/pt_BR.utf8/') in LOCALE_FILES)


def load_payloads(workspace):
    manifest = json.loads((workspace / 'configuration.json').read_text())
    if not isinstance(manifest, dict) or not manifest:
        raise BuildError('Manifest de configuração inválido')
    for name, value in manifest.items():
        if not allowed_configuration(name):
            raise BuildError('Configuração fora da allowlist: ' + name)
        if value['kind'] == 'file':
            payload = member(workspace / 'configuration', name)
            if payload.is_symlink() or not payload.is_file() or file_hash(payload) != value['sha256']:
                raise BuildError('Payload alterado ou symlink')
        elif name != 'etc/localtime' or value.get('kind') != 'symlink' or value.get('target') != '../usr/share/zoneinfo/America/Sao_Paulo':
            raise BuildError('Somente o symlink localtime pode ser substituído')
    return manifest


def is_masked(name, old_live):
    if name in old_live:
        return True
    parents = [str(parent) for parent in PurePosixPath(name).parents]
    if any(parent in old_live and old_live[parent].get('type', 'dir') != 'dir' for parent in parents):
        raise BuildError('Ancestral live não diretório exige reconciliação específica')
    return any(any(key.endswith('overlay.opaque') for key in old_live.get(parent, {}).get('xattrs', {})) for parent in parents)


def apply_to_tree(workspace, root, manifest, before):
    changed = set(manifest)
    for name, value in manifest.items():
        path = member(root, name)
        for parent in reversed(path.parents):
            if parent == root or root not in parent.parents:
                continue
            if not parent.exists():
                parent.mkdir(mode=0o755)
                changed.add(parent.relative_to(root).as_posix())
                os.utime(parent, (EPOCH, EPOCH))
        old = before.get(name, {})
        if any(key in old.get('xattrs', {}) for key in ('security.ima', 'security.evm')):
            raise BuildError('Assinatura IMA/EVM exige política específica')
        if value['kind'] == 'file':
            if path.is_symlink() or (path.exists() and (not path.is_file() or path.stat().st_nlink > 1)):
                raise BuildError('Tipo/hardlink inesperado: ' + name)
            old = before.get(name, {})
            if any(key in old.get('xattrs', {}) for key in ('security.ima', 'security.evm')):
                raise BuildError('Arquivo com assinatura IMA/EVM requer política específica')
            path.write_bytes(member(workspace / 'configuration', name).read_bytes())
            path.chmod(0o644)
        else:
            if path.exists() or path.is_symlink():
                if not path.is_symlink():
                    raise BuildError('localtime original deveria ser symlink')
                path.unlink()  # Exclusivamente o symlink permitido dentro da cópia extraída.
            path.symlink_to(value['target'])
        os.chown(path, 0, 0, follow_symlinks=False)
        for key, encoded in old.get('xattrs', {}).items():
            os.setxattr(path, key, base64.b64decode(encoded), follow_symlinks=False)
        os.utime(path, (EPOCH, EPOCH), follow_symlinks=False)
    # Criar filhos altera mtime dos ancestrais: restaurar diretórios originais.
    for name, old in before.items():
        if old['type'] == 'dir':
            path = root if name == '.' else member(root, name)
            os.utime(path, (old['mtime'], old['mtime']))
    for name in changed - set(before):
        path = member(root, name)
        if path.is_dir() and not path.is_symlink():
            os.utime(path, (EPOCH, EPOCH))
    return changed


def check_diff(before, after, allowed):
    if set(after) != set(before) | set(allowed):
        raise BuildError('Adição/remoção fora do conjunto autorizado')
    for name in before:
        if name not in allowed and before[name] != after[name]:
            raise BuildError('Alteração inesperada: ' + name)


def apply(workspace):
    if not (workspace / 'root-extract-ok.json').is_file():
        raise BuildError('Extração não aprovada')
    manifest = load_payloads(workspace)
    for folder in ('base-root', 'live-root'):
        before = json.loads((workspace / (folder + '.before.json')).read_text())
        selected = manifest if folder == 'base-root' else {name: value for name, value in manifest.items() if is_masked(name, before)}
        allowed = apply_to_tree(workspace, workspace / folder, selected, before)
        print('Validando patch: ' + folder, flush=True)
        after = snapshot(workspace / folder)
        check_diff(before, after, allowed)
        for name, value in selected.items():
            actual = after[name]
            if actual['uid'] != 0 or actual['gid'] != 0 or (value['kind'] == 'file' and actual['sha256'] != value['sha256']):
                raise BuildError('Payload ou ownership incorreto')
        write_json(workspace / (folder + '.after.json'), after)
        write_json(workspace / (folder + '.changes.json'), {'allowed': sorted(allowed), 'mirrored': sorted(selected)})
    write_json(workspace / 'root-apply-ok.json', {'status': 'ok'})


def pack(workspace):
    if not (workspace / 'root-apply-ok.json').is_file():
        raise BuildError('Patch não aprovado')
    destination = workspace / 'rebuilt-casper'
    if destination.is_symlink() or not destination.is_dir():
        raise BuildError('Diretório de saída deve ter sido criado por magaton')
    for name, folder in (('minimal.squashfs', 'base-root'), ('minimal.live.squashfs', 'live-root')):
        output = destination / name
        if output.exists() or output.is_symlink():
            raise BuildError('Não sobrescrever SquashFS')
        if (workspace / folder).is_symlink() or not (workspace / folder).is_dir():
            raise BuildError('Raiz de origem inválida')
        expected = json.loads((workspace / (folder + '.after.json')).read_text())
        root = expected['.']
        command(workspace, 'pack-' + folder, ['mksquashfs', str(workspace / folder), str(output), '-noappend',
                '-no-recovery', '-comp', 'xz', '-b', '131072', '-processors', '1', '-mem', '256M', '-no-progress',
                '-exit-on-error', '-mkfs-time', str(EPOCH), '-root-time', str(root['mtime']), '-root-mode', format(root['mode'], 'o'),
                '-root-uid', str(root['uid']), '-root-gid', str(root['gid'])])
        verify = workspace / ('verify-' + folder)
        if verify.exists() or verify.is_symlink():
            raise BuildError('Destino de verificação já existe')
        command(workspace, 'verify-' + folder, ['unsquashfs', '-strict-errors', '-processors', '1', '-data-queue', '64',
                '-frag-queue', '64', '-no-progress', '-d', str(verify), str(output)])
        print('Comparação integral da SquashFS: ' + folder, flush=True)
        actual = snapshot(verify)
        if actual != expected:
            differences = [key for key in set(actual) | set(expected) if actual.get(key) != expected.get(key)]
            raise BuildError('Round-trip alterou dados/metadados: ' + str(differences[:10]))
        write_json(workspace / (folder + '.verified.json'), {'status': 'ok', 'entries': len(actual), 'sha256': file_hash(output), 'uncompressed_allocated_bytes': allocated_usage(verify)})
    write_json(workspace / 'root-pack-ok.json', {'status': 'ok'})


def main(workspace, stage):
    if os.geteuid() != 0:
        raise BuildError('Este auxiliar exige a autorização root específica apresentada ao usuário')
    guard_workspace(workspace)
    if stage not in ('extract', 'apply', 'pack'):
        raise BuildError('Etapa desconhecida')
    {'extract': extract, 'apply': apply, 'pack': pack}[stage](workspace)
