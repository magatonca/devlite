"""Compilação/materialização do delta. Só opera em cópias novas; sem mounts."""
import copy
import difflib
import os
import shutil
import stat
from pathlib import Path,PurePosixPath
from .customize.manifest import SpecError
from .minimal_root import snapshot,member
from .structure import digest


def validate_tree(tree):
    if '.' not in tree or tree['.']['type']!='dir':raise SpecError('Inventário sem raiz')
    for name,value in tree.items():
        path=PurePosixPath(name)
        if name!='.' and (path.is_absolute() or '..' in path.parts or str(path)!=name):raise SpecError('Path de camada inseguro')
        if value['type'] not in ('dir','file','symlink','char','block','fifo'):raise SpecError('Tipo não suportado')
        if any(k.startswith(('trusted.overlay.','user.overlay.')) for k in value.get('xattrs',{})):raise SpecError('Xattrs OverlayFS antigos exigem revisão')
        if name!='.':
            for parent in path.parents:
                key=str(parent)
                if key not in tree or tree[key]['type']!='dir':raise SpecError('Ancestral ausente/não diretório')
        if value['type']=='file':
            for link in value.get('hardlinks',[name]):
                if link not in tree or tree[link].get('sha256')!=value.get('sha256') or tree[link].get('hardlinks')!=value.get('hardlinks'):raise SpecError('Grupo hardlink inconsistente')


def recipe(base,live):
    validate_tree(base);validate_tree(live)
    removed=set(base)-set(live)
    whiteouts=[]
    for name in sorted(removed):
        ancestors=[str(p) for p in PurePosixPath(name).parents]
        if any(p in removed or (p in live and live[p]['type']!='dir') for p in ancestors):continue
        whiteouts.append(name)
    puts={p for p in live if p!='.' and base.get(p)!=live[p]}
    for name in list(puts):
        if live[name]['type']=='file':puts.update(live[name].get('hardlinks',[name]))
    dirs={'.'}
    for name in puts|set(whiteouts):
        dirs.update(str(p) for p in PurePosixPath(name).parents)
    dirs.update(p for p in puts if live[p]['type']=='dir')
    result={'schema':1,'directories':{p:live[p] for p in sorted(dirs,key=lambda p:(len(PurePosixPath(p).parts),p))},
            'put':{p:live[p] for p in sorted(puts) if live[p]['type']!='dir'},'whiteouts':whiteouts}
    if compose(base,result)!=live:raise SpecError('Delta não reproduz a visão live')
    return result


def compose(base,plan):
    # Index direct children once: replacing a file must not rescan the whole tree.
    result=copy.deepcopy(base)
    children={}
    for path in result:
        if path!='.':children.setdefault(str(PurePosixPath(path).parent),set()).add(path)
    def remove(name):
        pending=[name]
        while pending:
            path=pending.pop()
            if path!='.':pending.extend(children.pop(path,()))
            result.pop(path,None)
            if path!='.':children.get(str(PurePosixPath(path).parent),set()).discard(path)
    for name in plan['whiteouts']:remove(name)
    for name,value in {**plan['directories'],**plan['put']}.items():
        if name!='.' and (value['type']!='dir' or (name in result and result[name]['type']!='dir')):
            for path in tuple(children.get(name,())):remove(path)
        result[name]=copy.deepcopy(value)
        if name!='.':children.setdefault(str(PurePosixPath(name).parent),set()).add(name)
    return result


def metadata(path,value):
    os.chown(path,value['uid'],value['gid'],follow_symlinks=False)
    if value['type']!='symlink':path.chmod(value['mode'])
    import base64
    for name in os.listxattr(path,follow_symlinks=False):
        if name not in value['xattrs']:os.removexattr(path,name,follow_symlinks=False)
    for name,data in value['xattrs'].items():os.setxattr(path,name,base64.b64decode(data),follow_symlinks=False)
    os.utime(path,(value['mtime'],value['mtime']),follow_symlinks=False)


def materialize(source,destination,plan,epoch):
    if destination.exists() or destination.is_symlink():raise SpecError('Delta exige destino inexistente')
    if plan['whiteouts'] and os.geteuid()!=0:raise SpecError('Whiteouts exigem root autorizado')
    source=source.resolve();destination.mkdir(mode=0o700);links={}
    for name,value in plan['directories'].items():
        if name!='.':member(destination,name).mkdir()
    for name,value in plan['put'].items():
        target=member(destination,name);original=member(source,name)
        if value['type']=='file':
            if original.is_symlink() or digest(original)!=value['sha256']:raise SpecError('Payload live mudou')
            group=tuple(value['hardlinks'])
            if group in links:os.link(links[group],target)
            else:shutil.copyfile(original,target);links[group]=target
        elif value['type']=='symlink':target.symlink_to(value['target'])
        elif value['type'] in ('char','block'):
            if os.geteuid()!=0:raise SpecError('Device exige root autorizado')
            os.mknod(target,(stat.S_IFCHR if value['type']=='char' else stat.S_IFBLK)|value['mode'],os.makedev(*value['device']))
        elif value['type']=='fifo':os.mkfifo(target,value['mode'])
        else:raise SpecError('Tipo não materializável')
        metadata(target,value)
    for name in plan['whiteouts']:
        target=member(destination,name);os.mknod(target,stat.S_IFCHR,os.makedev(0,0));os.utime(target,(epoch,epoch))
    for name,value in reversed(list(plan['directories'].items())):metadata(destination if name=='.' else member(destination,name),value)
    return snapshot(destination)


def clean_snapshot(tree):
    # Somente o diretório operacional criado pelo executor; nenhuma remoção no input RO.
    result=copy.deepcopy(tree);prefix='var/lib/devlite-executor'
    allowed={prefix,prefix+'/lists',prefix+'/lists/partial',prefix+'/lists/auxfiles'}
    for name in list(result):
        if name==prefix or name.startswith(prefix+'/'):
            if name==prefix+'/lists/lock' and result[name]['type']=='file' and result[name].get('size')==0 and result[name].get('sha256')=='e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855':pass
            elif name not in allowed or result[name]['type']!='dir':raise SpecError('Estado operacional inesperado: '+name)
            del result[name]
    return result


def full_manifest(versions,snaps=None):
    values=dict(versions)
    for name,version in (snaps or {}).items():
        if not name.startswith('snap:'):raise SpecError('Manifest snap inválido')
        values[name]=version
    return ''.join(name+'\t'+str(values[name])+'\n' for name in sorted(values))


def delta_manifest(before,after,left,right):
    # Mesmo formato observado: cabeçalhos ---/+++ e alterações +/-; sem hunks/contexto.
    diff=difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile=left,tofile=right,n=0)
    return ''.join(line for line in diff if not line.startswith('@@'))


def manifests(base,live,original_full):
    snaps={}
    for line in original_full.splitlines():
        if line.startswith('snap:'):
            fields=line.split('\t')
            if len(fields) not in (2,3) or any(not field or any(c.isspace() for c in field) for field in fields):raise SpecError('Registro Snap inesperado no manifest original')
            name=fields[0]
            if name in snaps:raise SpecError('Snap duplicado no manifest original')
            snaps[name]='\t'.join(fields[1:])
    base_full=full_manifest(base)
    live_full=full_manifest(live,snaps)
    return {'minimal.manifest':delta_manifest('',base_full,'devlite-empty.manifest.full','devlite-minimal.manifest.full'),
            'minimal.live.manifest':delta_manifest(base_full,live_full,'devlite-minimal.manifest.full','devlite-minimal.live.manifest.full'),
            'filesystem.manifest':live_full,'devlite-base.manifest.full':base_full}
