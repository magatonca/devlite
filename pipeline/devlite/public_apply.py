"""Offline addition of pinned public files to a disposable full rootfs.

No program in the image is executed. Existing filesystem entries must be
unchanged after the copy; collisions with existing non-directories fail closed.
"""
import hashlib,json,os,stat
from pathlib import Path,PurePosixPath
from .minimal_root import member,snapshot,EPOCH
from .final_payload import relative,sha

def tree_digest(value):
 digest=hashlib.sha256()
 for chunk in json.JSONEncoder(sort_keys=True,separators=(',',':')).iterencode(value):digest.update(chunk.encode())
 return digest.hexdigest()

def validate_payload(tree,manifest):
 if tree.is_symlink() or not tree.is_dir():raise ValueError('Unsafe payload root')
 actual=set()
 for base,dirs,files in os.walk(tree,followlinks=False):
  for name in dirs+files:actual.add((Path(base)/name).relative_to(tree).as_posix())
 if actual!=set(manifest):raise ValueError('Payload manifest coverage differs')
 for name,item in manifest.items():
  relative(name);path=member(tree,name);info=path.lstat();kind=item.get('type')
  if item.get('uid')!=0 or item.get('gid')!=0:raise ValueError('Unexpected target owner')
  if kind=='dir':
   if not stat.S_ISDIR(info.st_mode) or item['mode']!='0755':raise ValueError('Unsafe payload directory')
  elif kind=='file':
   if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or item['mode'] not in ('0644','0755'):raise ValueError('Unsafe payload file')
   if info.st_size!=item['size'] or sha(path)!=item['sha256']:raise ValueError('Payload file changed')
  elif kind=='symlink':
   if not stat.S_ISLNK(info.st_mode) or os.readlink(path)!=item['target'] or item['mode']!='0777':raise ValueError('Payload link changed')
   if Path(item['target']).is_absolute() or not path.resolve().is_relative_to(tree.resolve()):raise ValueError('Escaping payload symlink')
  else:raise ValueError('Unsupported payload entry')

def check_changes(before,after,manifest):
 if set(after)!=set(before)|set(manifest):raise ValueError('Unexpected rootfs entries')
 for name,original in before.items():
  if after.get(name)!=original:raise ValueError('Existing rootfs entry changed: '+name)
 for name,item in manifest.items():
  actual=after[name]
  if name in before:
   if item['type']!='dir' or before[name]['type']!='dir':raise ValueError('Payload collision')
   continue
  if actual['type']!=item['type'] or actual['uid']!=0 or actual['gid']!=0 or actual['mode']!=int(item['mode'],8) or actual['xattrs'] or actual['mtime']!=EPOCH:raise ValueError('New entry metadata differs: '+name)
  if item['type']=='file' and (actual['sha256']!=item['sha256'] or actual['size']!=item['size'] or actual['hardlinks']!=[name]):raise ValueError('New file differs: '+name)
  if item['type']=='symlink' and actual['target']!=item['target']:raise ValueError('New link differs: '+name)

def copy_payload(root,tree,manifest):
 validate_payload(tree,manifest)
 existing_dirs={}
 # All collisions and symlink ancestors are checked before the first write.
 for name,item in manifest.items():
  destination=member(root,name)
  try:info=destination.lstat()
  except FileNotFoundError:continue
  if item['type']!='dir' or not stat.S_ISDIR(info.st_mode):raise ValueError('Existing destination: '+name)
 for name in {'.'}|{str(p) for name in manifest for p in PurePosixPath(name).parents}|{n for n,v in manifest.items() if v['type']=='dir'}:
  destination=root if name=='.' else member(root,name)
  try:info=destination.lstat()
  except FileNotFoundError:continue
  if not stat.S_ISDIR(info.st_mode):raise ValueError('Non-directory ancestor')
  existing_dirs[name]=(info.st_atime_ns,info.st_mtime_ns)
 created=[]
 for name,item in sorted(manifest.items(),key=lambda p:(len(PurePosixPath(p[0]).parts),p[0])):
  destination=member(root,name)
  if name in existing_dirs:continue
  if item['type']=='dir':destination.mkdir()
  elif item['type']=='file':
   with member(tree,name).open('rb') as incoming,destination.open('xb') as outgoing:
    import shutil
    shutil.copyfileobj(incoming,outgoing,1024*1024)
   if sha(destination)!=item['sha256']:raise ValueError('Copy integrity failed')
  elif item['type']=='symlink':destination.symlink_to(item['target'])
  os.chown(destination,0,0,follow_symlinks=False)
  if item['type']!='symlink':destination.chmod(int(item['mode'],8))
  for key in os.listxattr(destination,follow_symlinks=False):os.removexattr(destination,key,follow_symlinks=False)
  created.append(name)
 for name in sorted(created,key=lambda p:len(PurePosixPath(p).parts),reverse=True):os.utime(member(root,name),(EPOCH,EPOCH),follow_symlinks=False)
 for name,times in sorted(existing_dirs.items(),key=lambda p:len(PurePosixPath(p[0]).parts),reverse=True):os.utime(root if name=='.' else member(root,name),ns=times,follow_symlinks=False)
 validate_payload(tree,manifest)

def apply(root,tree,manifest):
 before=snapshot(root)
 copy_payload(root,tree,manifest)
 after=snapshot(root)
 check_changes(before,after,manifest)
 return {'existing_entries_preserved':len(before),'new_entries':len(set(after)-set(before)),
         'before_tree_sha256':tree_digest(before),'after_tree_sha256':tree_digest(after),
         'only_declared_additions':True,'target_programs_executed':False}
