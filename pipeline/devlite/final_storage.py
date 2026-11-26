"""Auditoria sem exclusões: blocos reais, hardlinks e limites de acesso."""
import os,stat
from pathlib import Path


def scan(root):
    root=Path(root).absolute()
    if root.is_symlink() or not root.is_dir():raise ValueError('Raiz deve ser diretório real')
    rows=[];errors=[];pending=[root]
    while pending:
        path=pending.pop()
        try:
            info=path.lstat()
            kind='dir' if stat.S_ISDIR(info.st_mode) else 'file' if stat.S_ISREG(info.st_mode) else 'symlink' if stat.S_ISLNK(info.st_mode) else 'special'
            rows.append({'path':str(path),'device':info.st_dev,'inode':info.st_ino,'uid':info.st_uid,'mode':stat.S_IMODE(info.st_mode),'kind':kind,'bytes':info.st_size,'allocated_bytes':info.st_blocks*512,'links':info.st_nlink,'mtime_ns':info.st_mtime_ns,'ctime_ns':info.st_ctime_ns})
            if kind=='dir':
                with os.scandir(path) as entries:
                    pending.extend(Path(e.path) for e in entries if not (path==root and e.name=='.git'))
        except OSError as error:errors.append({'path':str(path),'error':str(error)})
    return rows,errors


def usage(rows):
    inodes={}
    for row in rows:
        key=(row['device'],row['inode']);record=inodes.setdefault(key,{'row':row,'observed_links':0});record['observed_links']+=1
    allocated=sum(v['row']['allocated_bytes'] for v in inodes.values())
    reclaimable=sum(v['row']['allocated_bytes'] for v in inodes.values() if v['row']['kind']=='dir' or v['observed_links']==v['row']['links'])
    return {'entries':len(rows),'unique_inodes':len(inodes),'logical_file_bytes':sum(v['row']['bytes'] for v in inodes.values() if v['row']['kind']=='file'),'allocated_bytes':allocated,'reclaimable_bytes_if_all_listed_paths_removed':reclaimable,'outside_hardlink_inodes':sum(v['row']['kind']!='dir' and v['observed_links']<v['row']['links'] for v in inodes.values())}


def subset(rows,path):
    root=Path(path).absolute()
    return [r for r in rows if Path(r['path'])==root or root in Path(r['path']).parents]


def candidate(rows,errors,path,reason,risk):
    values=subset(rows,path)
    if not values:raise ValueError('Candidato não encontrado')
    root=Path(path).absolute()
    blocked=[e for e in errors if Path(e['path'])==root or root in Path(e['path']).parents]
    result={'path':str(root),'reason':reason,'risk':risk,'complete_inventory':not blocked,**usage(values),'approved':False,'deleted':False}
    if blocked:result['reclaimable_bytes_if_all_listed_paths_removed']=None
    return result
