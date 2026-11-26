"""Representação lossless de SquashFS via pseudo 4.6.1, sem executar definições F."""
import hashlib
import re
import shutil
from pathlib import PurePosixPath
from .runtime import BuildError

MARKER = b'#\n# START OF DATA - DO NOT MODIFY\n#\n'



def decode_name(value):
    output = bytearray()
    pos = 0
    while pos < len(value):
        if value[pos] == 92:
            pos += 1
            if pos == len(value):
                raise BuildError('Escape incompleto')
        output.append(value[pos]); pos += 1
    text = output.decode('utf-8', 'surrogateescape')
    if text != '/' and (text.startswith('/') or '..' in text.split('/') or not text):
        raise BuildError('Caminho inseguro no pseudo')
    if any(ord(c) in (0, 10, 13) for c in text):
        raise BuildError('Nome pseudo com controle não suportado')
    return text


def encode_name(value):
    if value != '/' and (value.startswith('/') or '..' in value.split('/') or not value):
        raise BuildError('Caminho inseguro no patch')
    if any(ord(c) in (0, 10, 13) for c in value):
        raise BuildError('Controle no nome')
    return ''.join(chr(92) + c if c.isspace() or ord(c) in (92, 34) else c for c in value).encode('utf-8', 'surrogateescape')


def split_record(line):
    pos = 0
    while pos < len(line):
        if line[pos] == 92:
            pos += 2
            continue
        if chr(line[pos]).isspace():
            break
        pos += 1
    rest = line[pos:].lstrip(b' ')
    if len(rest) < 3 or rest[0] not in b'DRSBCILx' or rest[1] != 32 or not rest.endswith(bytes([10])):
        raise BuildError('Definição pseudo inválida ou executável proibida')
    return decode_name(line[:pos]), chr(rest[0]), rest[2:-1]


class Pseudo:
    def __init__(self, path):
        self.path = path
        self.records = []
        self.nodes = {}
        self.attrs = {}
        with path.open('rb') as stream:
            while True:
                line = stream.readline(65537)
                if not line or len(line) > 65536:
                    raise BuildError('Pseudo incompleto ou linha excessiva')
                if line == b'#\n':
                    if line + stream.read(len(MARKER) - len(line)) != MARKER:
                        raise BuildError('Marcador de dados inválido')
                    self.start = stream.tell()
                    break
                name, kind, tail = split_record(line)
                self.records.append((name, kind, tail, line))
                if kind == 'x':
                    self.attrs.setdefault(name, []).append(tail)
                else:
                    if name in self.nodes:
                        raise BuildError('Nó pseudo duplicado')
                    self.nodes[name] = (kind, tail)
        self.data_size = path.stat().st_size - self.start
        for name, (kind, tail) in self.nodes.items():
            if kind == 'R':
                fields = list(map(int, tail.split()))
                if len(fields) != 7 or min(fields) < 0 or fields[5] + fields[4] > self.data_size:
                    raise BuildError(f'Dados pseudo fora do arquivo: {name}')
        if self.nodes.get('/', (None,))[0] != 'D':
            raise BuildError('Raiz pseudo inválida')
        if any(name not in self.nodes for name in self.attrs):
            raise BuildError('Xattr sem inode')

    def primary(self, name):
        seen = set()
        while self.nodes[name][0] == 'L':
            if name in seen:
                raise BuildError('Ciclo de hardlinks')
            seen.add(name)
            name = decode_name(self.nodes[name][1])
            if name not in self.nodes:
                raise BuildError('Hardlink sem destino')
        return name

    def read(self, name):
        kind, tail = self.nodes[self.primary(name)]
        if kind != 'R':
            raise BuildError(f'Arquivo regular requerido: {name}')
        fields = list(map(int, tail.split()))
        with self.path.open('rb') as stream:
            stream.seek(self.start + fields[5])
            data = stream.read(fields[4])
        if len(data) != fields[4]:
            raise BuildError('Dados pseudo truncados')
        return data

    def inventory(self):
        groups = {}
        for name in self.nodes:
            primary = self.primary(name)
            groups.setdefault(primary, []).append(name)
        signatures = {}
        with self.path.open('rb') as stream:
            for name, (kind, tail) in self.nodes.items():
                if kind == 'L':
                    continue
                fields = tail.split(maxsplit=4)
                if len(fields) < 4:
                    raise BuildError('Metadados pseudo incompletos')
                metadata = [int(fields[0]), int(fields[1], 8), int(fields[2]), int(fields[3])]
                entry = {'type': kind, 'metadata': metadata,
                         'xattrs': sorted(value.hex() for value in self.attrs.get(name, [])),
                         'hardlinks': sorted(groups[name])}
                if kind == 'R':
                    numbers = list(map(int, tail.split()))
                    size, offset = numbers[4:6]
                    stream.seek(self.start + offset)
                    h = hashlib.sha256()
                    remaining = size
                    while remaining:
                        block = stream.read(min(1024 * 1024, remaining))
                        if not block:
                            raise BuildError('Dados pseudo truncados')
                        h.update(block); remaining -= len(block)
                    entry.update(size=size, sha256=h.hexdigest())
                else:
                    entry['extra'] = fields[4].hex() if len(fields) > 4 else ''
                signatures[name] = entry
        return {name: signatures[self.primary(name)] for name in self.nodes}

    def patch(self, output, updates, epoch):
        if output.exists() or output.is_symlink() or output.resolve() == self.path.resolve():
            raise BuildError('Saída pseudo existente ou igual à entrada')
        updates = dict(updates)
        for name in list(updates):
            decode_name(name.encode())
            for parent in PurePosixPath(name).parents:
                if str(parent) == '.':
                    continue
                text = str(parent)
                if text not in self.nodes and text not in updates:
                    updates[text] = {'kind': 'D', 'mode': 0o755}
                elif text in self.nodes and self.nodes[text][0] != 'D':
                    raise BuildError(f'Ancestral não é diretório: {text}')
        for name in updates:
            if name in self.nodes and len([n for n in self.nodes if self.nodes[n][0] == 'L' and self.primary(n) == self.primary(name)]) > 0:
                raise BuildError(f'Alteração em grupo de hardlinks requer revisão: {name}')
            if any(b'security.ima=' in x or b'security.evm=' in x for x in self.attrs.get(name, [])):
                raise BuildError('Arquivo alterado tem assinatura IMA/EVM')
        replacement, appended, offset = {}, [], self.data_size
        for name, value in sorted(updates.items(), key=lambda item: (item[0].count('/'), item[0])):
            kind = value['kind']
            mode = value.get('mode', 0o644 if kind == 'R' else 0o777)
            prefix = encode_name(name) + f' {kind} {epoch} {mode:o} 0 0'.encode()
            if kind == 'R':
                data = value['data']
                line = prefix + f' {len(data)} {offset} 0\n'.encode()
                offset += len(data); appended.append(data)
            elif kind == 'S':
                target = value['target']
                if '\n' in target or '\x00' in target:
                    raise BuildError('Symlink inválido')
                line = prefix + b' ' + target.encode() + b'\n'
            elif kind == 'D':
                line = prefix + b'\n'
            else:
                raise BuildError('Patch permite somente arquivo, diretório ou symlink')
            replacement[name] = line
        with output.open('xb') as stream:
            for name, kind, tail, original in self.records:
                if kind == 'x':
                    stream.write(original)
                elif name in replacement:
                    stream.write(replacement.pop(name))
                else:
                    stream.write(original)
            for line in replacement.values():
                stream.write(line)
            stream.write(MARKER)
            with self.path.open('rb') as source:
                source.seek(self.start)
                shutil.copyfileobj(source, stream, 1024 * 1024)
            for data in appended:
                stream.write(data)
        return set(updates)

    def root_options(self):
        fields = self.nodes['/'][1].split()
        return ['-root-time', fields[0].decode(), '-root-mode', fields[1].decode(),
                '-root-uid', fields[2].decode(), '-root-gid', fields[3].decode()]


def reconcile_live(base, live, updates):
    mirrors = {}
    for name, update in updates.items():
        parents = [str(p) for p in PurePosixPath(name).parents if str(p) != '.'] + ['/']
        opaque = any(any(b'overlay.opaque=' in attr for attr in live.attrs.get(parent, [])) for parent in parents)
        if name in live.nodes or opaque:
            mirrors[name] = update
    return mirrors
