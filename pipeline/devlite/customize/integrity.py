"""Integridade local de payloads e overlays; não prova autenticidade de origem."""
import base64
import hashlib
import hmac
import json
import re
import stat
from ..validation import safe_member
from .manifest import SpecError


def verify_payload(path, sha256, integrity=None):
    if path.is_symlink() or not path.is_file():
        raise SpecError('Payload deve ser arquivo regular, sem symlink')
    if not re.fullmatch(r'[0-9a-f]{64}', sha256):
        raise SpecError('SHA-256 de referência inválido')
    h256, h512 = hashlib.sha256(), hashlib.sha512()
    with path.open('rb') as stream:
        while block := stream.read(1024 * 1024):
            h256.update(block); h512.update(block)
    if not hmac.compare_digest(h256.hexdigest(), sha256):
        raise SpecError('Payload alterado: SHA-256 divergente')
    if integrity is not None:
        try:
            algorithm, encoded = integrity.split('-', 1)
            expected = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError) as exc:
            raise SpecError('SRI inválido') from exc
        if algorithm != 'sha512' or not hmac.compare_digest(h512.digest(), expected):
            raise SpecError('Payload alterado: SRI SHA-512 divergente')
    return {'sha256': h256.hexdigest(), 'bytes': path.stat().st_size}


def verify_export(workspace):
    manifest_path = workspace / 'overlay-manifest.json'
    if manifest_path.is_symlink():
        raise SpecError('Manifest de overlay não pode ser symlink')
    manifest = json.loads(manifest_path.read_text())
    if not isinstance(manifest, dict) or not manifest:
        raise SpecError('Manifest de overlay inválido')
    root = workspace / 'overlay'
    if root.is_symlink() or not root.is_dir():
        raise SpecError('Raiz de overlay inválida')
    for name, value in manifest.items():
        if not isinstance(value, dict):
            raise SpecError('Entrada de manifest inválida')
        path = safe_member(root, name)
        if value.get('kind') == 'symlink':
            if not path.is_symlink() or path.readlink().as_posix() != value['target']:
                raise SpecError(f'Symlink de configuração alterado: {name}')
        elif value.get('kind') == 'text':
            verify_payload(path, value['sha256'])
            if stat.S_IMODE(path.stat().st_mode) != value['mode']:
                raise SpecError(f'Modo de arquivo alterado: {name}')
        else:
            raise SpecError('Tipo de arquivo inesperado')
    actual = {path.relative_to(root).as_posix() for path in root.rglob('*') if path.is_file() or path.is_symlink()}
    if actual != set(manifest):
        raise SpecError('Arquivos inesperados/ausentes no overlay')
    return {'files_verified': len(manifest), 'applied': False,
            'limit': 'Integridade relativa ao manifest local; não equivale a assinatura ou instalação.'}
