"""Inspeção de tar autenticado, sem extrair nem executar conteúdo."""
import hashlib,posixpath,tarfile
from pathlib import PurePosixPath


def inspect(path,prefix,max_bytes,max_files=50000):
    if not prefix or '/' in prefix or prefix in ('.','..'):raise ValueError('Prefixo inválido')
    entries={};total=0
    with tarfile.open(path,'r|*') as archive:
        for member in archive:
            if len(entries)>=max_files or len(member.name)>4096:raise ValueError('Limite de inventário excedido')
            name=PurePosixPath(member.name)
            if name.is_absolute() or '..' in name.parts or not name.parts or name.parts[0]!=prefix:raise ValueError('Path fora do prefixo')
            relative=PurePosixPath(*name.parts[1:]).as_posix()
            if relative in entries:raise ValueError('Entrada duplicada')
            if member.mode & 0o6000 or any(k.startswith(('SCHILY.xattr.','LIBARCHIVE.xattr.')) for k in member.pax_headers):raise ValueError('Permissões/atributos privilegiados inesperados')
            if member.isdir():record={'type':'dir','mode':'0755'}
            elif member.isfile():
                if member.size<0 or total+member.size>max_bytes:raise ValueError('Orçamento descomprimido excedido')
                total+=member.size
                with archive.extractfile(member) as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
                record={'type':'file','size':member.size,'sha256':digest,'mode':'0755' if member.mode & 0o111 else '0644'}
            elif member.issym():
                target=PurePosixPath(member.linkname)
                resolved=posixpath.normpath(str(name.parent/target))
                if target.is_absolute() or not (resolved==prefix or resolved.startswith(prefix+'/')):raise ValueError('Symlink escapa do prefixo')
                record={'type':'symlink','target':member.linkname,'mode':'0777'}
            else:raise ValueError('Devices/hardlinks/tipos especiais não permitidos')
            if relative=='.' and record['type']!='dir':raise ValueError('Raiz não diretório')
            entries[relative]={'archive_member':member.name,**record}
    for name in entries:
        for parent in PurePosixPath(name).parents:
            if str(parent) in entries and entries[str(parent)]['type']!='dir':raise ValueError('Entrada sob ancestral symlink/não diretório')
    return {'prefix':prefix,'unpacked_bytes':total,'entries':entries,'extracted':False,'executed':False}
