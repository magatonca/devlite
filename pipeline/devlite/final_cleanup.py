"""Bounded cleanup of the reviewed 21 paths; no approval implied by this code."""
import collections,errno,hashlib,json,os,re,shutil,stat,subprocess
from pathlib import Path
ROOT=Path('/home/magaton/DevLite-OS')
TARGETS=(
'work/release-63m6oz2_/iso-8szxc4eu/source-tree',
'work/release-63m6oz2_/iso-8szxc4eu/result-tree',
'work/release-63m6oz2_/iso-xoaxo4dp/source-tree',
'work/release-63m6oz2_/iso-xoaxo4dp/result-tree',
'work/phase3b-frka50es/source-tree','work/phase3b-frka50es/result-tree',
'work/phase3b-reproduction-jvzarclv/reproduced.iso',
'artifacts/release-22snj8_v/devlite-os-1.0-ubuntu-experimental.iso',
'work/phase4b1-dhzezpnz/source-iso-tree','work/phase4b1-dhzezpnz/base-root',
'work/phase4b1-dhzezpnz/live-root','work/phase4b1-dhzezpnz/verify-base-root',
'work/phase4b1-dhzezpnz/verify-live-root',
'work/release-ku78mn3t/pack-attempt/verify-minimal.live.squashfs',
'work/release-ku78mn3t/pack-attempt/verify-minimal.squashfs',
'work/release-ku78mn3t/pack-attempt/delta',
'work/phase4b1-dhzezpnz/rebuilt-casper/minimal.squashfs',
'work/phase4b1-dhzezpnz/rebuilt-casper/minimal.live.squashfs',
'work/phase4b3-wnej6dpv/probe-attempt/base.ext4',
'work/phase4b3-wnej6dpv/probe-attempt/layers/minimal.squashfs',
'work/phase4b3-wnej6dpv/probe-attempt/layers/minimal.live.squashfs')
DUPLICATES=(
(TARGETS[6],'artifacts/phase3b-9adp_k5i/devlite-os-1.0-experimental-rebuild.iso'),
(TARGETS[7],'artifacts/release-c0srssh8/devlite-os-1.0-ubuntu-experimental.iso'),
(TARGETS[16],'work/phase4b1-dhzezpnz/result-iso-tree/casper/minimal.squashfs'),
(TARGETS[17],'work/phase4b1-dhzezpnz/result-iso-tree/casper/minimal.live.squashfs'),
(TARGETS[19],'work/phase4b1-dhzezpnz/result-iso-tree/casper/minimal.squashfs'),
(TARGETS[20],'work/phase4b1-dhzezpnz/result-iso-tree/casper/minimal.live.squashfs'))

def digest(path):
 with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def under(path,base):
 return path==base or path.startswith(base+'/')

def inventory(paths):
 """lstat only, no symlink following, no filesystem crossings; count hardlinks."""
 result={};counts=collections.Counter();blocks={};identity={}
 for top in paths:
  top=Path(top)
  if top.is_symlink():raise ValueError('Candidate root is a symlink')
  device=top.stat().st_dev;stack=[top]
  while stack:
   path=stack.pop();info=path.lstat()
   if info.st_dev!=device:raise ValueError('Filesystem crossing')
   result[str(path)]=(info.st_dev,info.st_ino,info.st_mode,info.st_size,info.st_mtime_ns,info.st_ctime_ns,info.st_nlink)
   key=(info.st_dev,info.st_ino);blocks[key]=info.st_blocks*512
   if not stat.S_ISDIR(info.st_mode):counts[key]+=1;identity[key]=info.st_nlink
   elif not stat.S_ISLNK(info.st_mode):
    with os.scandir(path) as entries:stack.extend(Path(e.path) for e in entries)
 if any(n>counts[key] for key,n in identity.items()):raise ValueError('External hardlink to a candidate; preserve and revise plan')
 return result,sum(blocks.values())

def validate_plan(plan_path,expected):
 if not re.fullmatch('[a-f0-9]{64}',expected) or plan_path.is_symlink() or digest(plan_path)!=expected:raise ValueError('Plan digest changed')
 plan=json.loads(plan_path.read_text());paths=[x['path'] for x in plan['candidates']]
 if paths!=[str(ROOT/x) for x in TARGETS]:raise ValueError('The exact reviewed list is required')
 for rel in TARGETS:
  path=ROOT/rel
  for parent in [path,*path.parents]:
   if parent.is_symlink():raise ValueError('Symlink ancestor')
 return [ROOT/x for x in TARGETS]

class ResourceBlocked(ValueError):
 """A blocking resource observation, serializable in the cleanup report."""
 def __init__(self,message,evidence):
  self.evidence=evidence
  super().__init__(message+'; '+json.dumps(evidence,ensure_ascii=False,sort_keys=True))

def process_identity(process):
 """Use start time as well as PID, so PID reuse cannot hide a new process."""
 try:text=(process/'stat').read_text()
 except OSError as error:
  if error.errno in (errno.ENOENT,errno.ESRCH):return None
  raise
 opening=text.index('(');closing=text.rindex(')')
 fields=text[closing+1:].split()
 return {'pid':int(text[:opening].strip()),'process_name':text[opening+1:closing],
         'start_ticks':int(fields[19]),'state':fields[0]}

def same_process(first,second):
 return first is not None and second is not None and (first['pid'],first['start_ticks'])==(second['pid'],second['start_ticks'])

def read_reference(link):
 try:return os.readlink(link)
 except OSError as error:
  if error.errno in (errno.ENOENT,errno.ESRCH):return None
  raise

def resources_clear(paths,evidence=None,proc_root=Path('/proc')):
 strings=[str(p) for p in paths]
 check={'status':'inspecting','events':[],'processes_examined':0}
 if evidence is not None:evidence.append(check)
 def event(kind,identity,**details):
  item={'kind':kind,**identity,**details};check['events'].append(item);return item
 def blocked(message,item):
  check['status']='blocked'
  raise ResourceBlocked(message,item)
 loops=json.loads(subprocess.run(['/usr/sbin/losetup','--list','--json'],capture_output=True,text=True,check=True).stdout)
 if any(any(under(x.get('back-file',''),p) for p in strings) for x in loops.get('loopdevices',[])):raise ValueError('Candidate loop backing file active')
 units=json.loads(subprocess.run(['/usr/bin/systemctl','list-units','--all','--output=json','--no-pager','devlite-*'],capture_output=True,text=True,check=True).stdout)
 if any(x.get('active') not in ('inactive','failed') for x in units):raise ValueError('Active DevLite job')
 def decoded(value):return re.sub(r'\\\\([0-7]{3})',lambda m:chr(int(m[1],8)),value)
 for process in proc_root.iterdir():
  if not process.name.isdigit():continue
  identity=process_identity(process)
  if identity is None:
   event('process_disappeared',{'pid':int(process.name)},phase='before_inspection')
   continue
  check['processes_examined']+=1
  try:
   for line in (process/'mountinfo').read_text().splitlines():
    fields=line.split()
    for index in (3,4):
     value=decoded(fields[index])
     candidate=next((p for p in strings if under(value,p)),None)
     if candidate is not None:
      current=process_identity(process)
      if current is None:break
      if not same_process(identity,current):
       blocked('PID reused during mount inspection',event('process_identity_changed',identity,current=current))
      blocked('Candidate mounted in process namespace',event('mount_in_use',current,path=value,candidate=candidate,reference_type='mount_root' if index==3 else 'mountpoint',source_path=str(process/'mountinfo')))
   for link in [process/'cwd',process/'root',*(process/'fd').iterdir()]:
    raw=read_reference(link)
    if raw is None:continue
    value=raw.removesuffix(' (deleted)')
    if not any(under(value,p) for p in strings):continue
    reference_type='fd' if link.parent.name=='fd' else link.name
    details={'reference_type':reference_type,'source_path':str(link),'path':value,
             'raw_path':raw,'fd':int(link.name) if reference_type=='fd' else None,
             'is_controller':identity['pid']==os.getpid()}
    # Re-read both identity and reference. A vanished process or closed fd must
    # not be diagnosed as an active user; a still-active holder always blocks.
    current=process_identity(process)
    if current is None:
     event('process_disappeared',identity,phase='confirm_reference',**details)
     break
    if not same_process(identity,current):
     blocked('PID reused during reference inspection',event('process_identity_changed',identity,current=current,**details))
    confirmed=read_reference(link)
    after=process_identity(process)
    if after is None:
     event('process_disappeared',identity,phase='after_reference',**details)
     break
    if not same_process(identity,after):
     blocked('PID reused during reference confirmation',event('process_identity_changed',identity,current=after,**details))
    confirmed_path=confirmed.removesuffix(' (deleted)') if confirmed is not None else None
    candidate=next((p for p in strings if confirmed_path is not None and under(confirmed_path,p)),None)
    if candidate is None:
     event('reference_released',after,confirmed_path=confirmed_path,**details)
     continue
    details.update(path=confirmed_path,raw_path=confirmed,candidate=candidate)
    blocked('Candidate in use by process '+str(after['pid']),event('candidate_in_use',after,**details))
   after=process_identity(process)
   if after is not None and not same_process(identity,after):
    blocked('PID reused during process inspection',event('process_identity_changed',identity,current=after))
  except OSError as error:
   if error.errno not in (errno.ENOENT,errno.ESRCH):raise
   current=process_identity(process)
   if current is None:
    event('process_disappeared',identity,phase='inspect_process',errno=error.errno)
    continue
   # Missing metadata while the process still exists is not proof of safety.
   blocked('Incomplete metadata for existing process',event('incomplete_process_metadata',current,path=error.filename,errno=error.errno))
 check['status']='clear'
 # Permission errors are deliberately fatal; incomplete global visibility is unsafe.

def verify_sources():
 """Critical duplicates, original ISO and accepted receipts must still agree."""
 from .release_contract import read
 read(ROOT/'work/release-63m6oz2_','bc32e0ce9fb1a95d4b0170c1130f46ec523ddee0871b9fd3915e8f126a91d19d')
 original=ROOT/'sources/xubuntu-24.04.5-minimal-amd64.iso'
 if digest(original)!='9d47f975696ce496b8be882b6d7cc9079c1ea89fb625ac2c86caa63a4f180033':raise ValueError('Original ISO integrity failed')
 for candidate,preserve in DUPLICATES:
  if digest(ROOT/candidate)!=digest(ROOT/preserve):raise ValueError('Duplicate mismatch: '+candidate)
 from .customize.executor_contract import accepted_pair
 pair=accepted_pair(ROOT/'work/phase4b3-wnej6dpv/attempt')
 receipt=ROOT/'work/phase4b3-wnej6dpv/probe-attestation.json'
 data=json.loads(receipt.read_text())
 if receipt.stat().st_uid!=0 or data.get('status')!='probe_passed' or data.get('job_sha256')!=pair['job_sha256']:raise ValueError('Probe receipt not preserved')

def delete_paths(paths,expected):
 """Hardened dir-fd removal; no glob, no following symlink roots."""
 if not shutil.rmtree.avoids_symlink_attacks:raise ValueError('Hardened rmtree unavailable')
 removed=[]
 for path in paths:
  # Check complete subtree identities immediately before each removal.
  current,_=inventory([path])
  if any(expected.get(p)!=identity for p,identity in current.items()) or any(p not in current for p in expected if under(p,str(path))):
   raise ValueError('Candidate changed since preflight')
  fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
  try:
   info=os.stat(path.name,dir_fd=fd,follow_symlinks=False)
   if (info.st_dev,info.st_ino)!=expected[str(path)][:2]:raise ValueError('Candidate root changed')
   if stat.S_ISDIR(info.st_mode):shutil.rmtree(path.name,dir_fd=fd)
   elif stat.S_ISREG(info.st_mode):os.unlink(path.name,dir_fd=fd)
   else:raise ValueError('Candidate type not supported')
  finally:os.close(fd)
  removed.append(str(path))
 return removed
