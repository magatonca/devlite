"""Comparação de conteúdo extraído e integridade dos manifests originais."""
import hashlib
import os
import stat
from .runtime import BuildError
from .structure import digest


def safe_member(root, name):
    from pathlib import PurePosixPath
    relative = PurePosixPath(name)
    if relative.is_absolute() or '..' in relative.parts:
        raise BuildError(f'Caminho inseguro no manifest: {name}')
    candidate = root / relative
    if not candidate.resolve().is_relative_to(root.resolve()):
        raise BuildError(f'Membro fora da árvore: {name}')
    return candidate


def inventory(root):
    result = {}
    for path in sorted(root.rglob('*')):
        info = path.lstat()
        name = path.relative_to(root).as_posix()
        mode = stat.S_IMODE(info.st_mode)
        if path.is_symlink():
            result[name] = {'type': 'symlink', 'target': os.readlink(path), 'mode': mode}
        elif path.is_file():
            result[name] = {'type': 'file', 'bytes': info.st_size, 'sha256': digest(path), 'mode': mode}
        elif path.is_dir():
            result[name] = {'type': 'dir', 'mode': mode}
        else:
            raise BuildError(f'Tipo de arquivo não suportado: {name}')
    return result


def normalized_bios(path):
    content = bytearray(path.read_bytes())
    if len(content) < 2556:
        raise BuildError('Imagem BIOS curta demais')
    content[8:64] = bytes(56)
    content[2548:2556] = bytes(8)
    return content


def compare_trees(before, after, source, result, bios_path):
    if set(before) != set(after):
        raise BuildError('Árvore de arquivos mudou')
    changed = []
    for name in before:
        if before[name] == after[name]:
            continue
        if name in ('boot.catalog', bios_path.lstrip('/')) and any(before[name].get(key) != after[name].get(key) for key in ('type', 'mode', 'bytes')):
            raise BuildError(f'Metadados de boot alterados: {name}')
        if name == 'boot.catalog':
            if before[name]['type'] != 'file' or after[name]['type'] != 'file':
                raise BuildError('Tipo do catálogo mudou')
        elif name == bios_path.lstrip('/'):
            if normalized_bios(source / name) != normalized_bios(result / name):
                raise BuildError('Código BIOS alterado fora das tabelas de endereços')
        else:
            raise BuildError(f'Conteúdo ou modo alterado: {name}')
        changed.append(name)
    return changed


def verify_manifest(root, name, algorithm):
    entries = 0
    seen = set()
    for line in (root / name).read_text().splitlines():
        fields = line.split(maxsplit=1)
        if len(fields) != 2:
            raise BuildError(f'Linha inválida em {name}')
        expected, member = fields
        member = member.lstrip('* ')
        if member in seen:
            raise BuildError(f'Entrada duplicada em {name}')
        seen.add(member)
        path = safe_member(root / name.parent, member)
        with path.open('rb') as stream:
            actual = hashlib.file_digest(stream, algorithm).hexdigest()
        if actual != expected:
            raise BuildError(f'{algorithm} divergente: {member}')
        entries += 1
    if not entries:
        raise BuildError(f'Manifest vazio: {name}')
    return entries


def iso_metadata(text):
    import shlex
    result = {}
    for line in text.splitlines():
        if len(line) < 11 or line[0] not in '-dl' or line[1] not in 'r-':
            continue
        fields = shlex.split(line)
        if len(fields) >= 9 and fields[8].startswith('/'):
            result[fields[8]] = fields[:8] + fields[9:]
    if not result:
        raise BuildError('Inventário de metadados ISO vazio')
    return result
