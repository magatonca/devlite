"""Verificação futura do cache externo. Sem download, extração ou instalação."""
import base64,hashlib,re,stat
from pathlib import Path


def verify(plan,cache):
    cache=Path(cache)
    if cache.is_symlink() or not cache.is_dir():raise ValueError('Cache deve ser diretório real')
    items=plan.get('artifacts',[]);names=[i['filename'] for i in items]
    if not names or len(set(names))!=len(names) or any(Path(n).name!=n or n in ('','.','..') for n in names):raise ValueError('Nomes de artefatos inseguros/duplicados')
    if set(p.name for p in cache.iterdir())!=set(names):raise ValueError('Cache incompleto ou com arquivos inesperados')
    result=[]
    for item in items:
        path=cache/item['filename'];info=path.lstat()
        if not stat.S_ISREG(info.st_mode):raise ValueError('Artefato deve ser regular, sem symlink')
        if item.get('download_bytes') is not None and info.st_size!=item['download_bytes']:raise ValueError('Tamanho do artefato divergente')
        if info.st_size>plan.get('download_cap_bytes',512*1024**2):raise ValueError('Orçamento do artefato excedido')
        algorithm=item['algorithm'];expected=item['digest']
        if algorithm=='sha256':
            if not re.fullmatch('[0-9a-f]{64}',expected):raise ValueError('SHA-256 inválido')
            with path.open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
        elif algorithm=='sha512-sri':
            if not expected.startswith('sha512-') or len(base64.b64decode(expected[7:],validate=True))!=64:raise ValueError('SRI SHA-512 inválido')
            with path.open('rb') as stream:actual='sha512-'+base64.b64encode(hashlib.file_digest(stream,'sha512').digest()).decode()
        else:raise ValueError('Algoritmo não permitido')
        if actual!=expected:raise ValueError('Integridade do artefato não confere')
        result.append({'id':item['id'],'file':str(path),'bytes':info.st_size,'digest':actual})
    if sum(r['bytes'] for r in result)>plan.get('download_cap_bytes',512*1024**2):raise ValueError('Orçamento agregado excedido')
    return result
