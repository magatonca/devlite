"""One-shot cleanup of precisely eight user-approved outputs. Root execution is separate."""
import collections
import datetime
import errno
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
from .final_cleanup import inventory, resources_clear, delete_paths, under, process_identity, same_process, ResourceBlocked
from .runtime import owned_directory

ROOT = Path('/home/magaton/DevLite-OS')
TARGETS = (
 'work/release-cezaiofx/pack-attempt/verify-minimal.squashfs',
 'work/release-cezaiofx/pack-attempt/verify-minimal.live.squashfs',
 'work/release-cezaiofx/pack-attempt/delta',
 'work/release-cezaiofx/pack-attempt/packed',
 'work/release-cezaiofx/iso-1mzrr68i/source-tree',
 'work/release-cezaiofx/iso-1mzrr68i/result-tree',
 'work/phase2/casper',
 'artifacts/phase3b-9adp_k5i/devlite-os-1.0-experimental-rebuild.iso')
CODE = ('pipeline/devlite/cleanup_eight.py', 'pipeline/devlite/final_cleanup.py',
        'pipeline/devlite/runtime.py', 'pipeline/devlite/__init__.py', 'scripts/limpar-oito-controlado.py')
RECEIPTS = ('work/release-cezaiofx/public-contract.json', 'work/release-cezaiofx/public-result.json',
            'work/release-cezaiofx/layers-ready.json', 'work/release-63m6oz2_/layers-ready.json')
SOURCE_DIRS = ('pipeline','scripts','config','packages','overlay','assets','tests','docs','reports','.git')

def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def canonical(p):
 p=Path(p)
 if p.resolve(strict=True)!=p or p.is_symlink():raise ValueError('Noncanonical path or symlink: '+str(p))
 return p

def checked_paths(root, names):
 if tuple(names)!=TARGETS:raise ValueError('Only the exact eight approved paths are accepted')
 canonical(root)
 paths=[]
 for i,name in enumerate(names):
  p=canonical(root/name)
  if (i<7 and not p.is_dir()) or (i==7 and not p.is_file()):raise ValueError('Unexpected candidate type: '+str(p))
  paths.append(p)
 if any(a!=b and a in b.parents for a in paths for b in paths):raise ValueError('Overlapping candidates')
 return paths

def source_files(root):
 files={}
 for name in SOURCE_DIRS:
  top=root/name
  if top.is_symlink():raise ValueError('Source directory is symlink: '+str(top))
  if not top.exists():continue
  for base,dirs,names in os.walk(top,followlinks=False):
   for child in dirs+names:
    p=Path(base)/child;s=p.lstat()
    if stat.S_ISLNK(s.st_mode):files[str(p.relative_to(root))]={'symlink':os.readlink(p)}
    elif stat.S_ISREG(s.st_mode):files[str(p.relative_to(root))]={'sha256':sha(p)}
 for p in root.iterdir():
  if p.is_file() and not p.is_symlink():files[str(p.relative_to(root))]={'sha256':sha(p)}
 return files

def expected_assets(root):
 """Use verified published receipts; preserve both accepted raw pairs and all caches."""
 public=json.loads((root/RECEIPTS[0]).read_text())
 result=json.loads((root/RECEIPTS[1]).read_text())
 if result.get('status')!='public_layers_verified' or result.get('cleanup_errors')!=[]:raise ValueError('Public application is not accepted')
 assets={
 'sources/xubuntu-24.04.5-minimal-amd64.iso':'9d47f975696ce496b8be882b6d7cc9079c1ea89fb625ac2c86caa63a4f180033',
 'artifacts/release-1hu5dx5v/devlite-os-1.0-amd64.iso':'2c699f3facb3f84ced392fd37bc25a9b7e46c74022c62816be2119af7f294d77',
 'artifacts/release-c0srssh8/devlite-os-1.0-ubuntu-experimental.iso':'7f49f8b03ad0201f70c5deed4879ffedb79bf7b7a3f1f105ca8380be8da3e4db'}
 for item in public['source_images'].values():assets[str(Path(item['file']).relative_to(root))]=item['sha256']
 for value in result['results'].values():
  item=value['image'];assets[str(Path(item['file']).relative_to(root))]=item['sha256']
 for name in RECEIPTS[2:]:
  p=root/name
  if p.is_symlink() or p.stat().st_uid!=0 or p.stat().st_mode&0o022:raise ValueError('Untrusted layer receipt')
  record=json.loads(p.read_text())
  if record.get('status')!='layers_verified':raise ValueError('Layer receipt not accepted')
  published=Path(record['published'])
  if published!=p.parent/'published-casper':raise ValueError('Published path mismatch')
  for file,value in record['files'].items():
   if Path(file).name!=file:raise ValueError('Unsafe layer name')
   assets[str((published/file).relative_to(root))]=value
 for name in RECEIPTS:assets[name]=sha(root/name)
 for name in assets:
  if any(under(name,t) or under(t,name) for t in TARGETS):raise ValueError('Deletion overlaps protected asset')
 return assets

def prepare(root=ROOT):
 if os.geteuid()==0 or os.getuid()!=1000:raise ValueError('Prepare as magaton')
 assets=expected_assets(root)
 public=json.loads((root/RECEIPTS[0]).read_text())
 originals=root/'work/phase4b1-dhzezpnz/original-casper'
 # Snapshot names/hashes only; every large file will be read before deletion under approved root execution.
 for p in originals.iterdir():
  if p.is_file() and not p.is_symlink():assets[str(p.relative_to(root))]=sha(p) if p.suffix!='.squashfs' else None
 # The two official SquashFS are authenticated by the archived SHA256SUMS.
 for line in (originals/'SHA256SUMS').read_text().splitlines():
  parts=line.split()
  if len(parts)==2:
   name=parts[1].lstrip('*').removeprefix('./')
   if Path(name).name==name and (originals/name).is_file():assets[str((originals/name).relative_to(root))]=parts[0]
 if any(v is None for v in assets.values()):raise ValueError('Official squashfs checksum absent')
 pair=json.loads((root/'work/phase4b3-wnej6dpv/plan.json').read_text())
 # Lock cache package hashes directly from the accepted transaction, not from filenames.
 cache={}
 for target in pair['targets'].values():
  for item in target['changes']:
   name=Path(item['filename']).name
   value=item['sha256']
   if name in cache and cache[name]!=value:raise ValueError('Conflicting deb hashes')
   cache[name]=value
 if len(cache)!=243:raise ValueError('Expected the preserved 243-deb cache')
 for name,value in cache.items():assets['work/phase4b5-g78yd2oc/debs/'+name]=value
 # Canonical cache uses preserved hardlink names which are checked during preparation.
 for name in cache:
  if not (root/'work/phase4b5-g78yd2oc/debs'/name).is_file():raise ValueError('Cache path missing: '+name)
 sources=source_files(root)
 job=owned_directory(root/'work','cleanup-eight-')
 plan={'schema':1,'job':str(job),'operation':'exact-eight-cleanup','targets':list(TARGETS),
       'code_sha256':{n:sha(root/n) for n in CODE},'protected_sha256':assets,
       'host_critical_files':{name:sha(name) for name in public['host_critical_files']},'source_files':sources,
       'expected_entries':263081,'expected_allocated_bytes':23174307840,
       'permissions_config_sha256':sha(root/'config/projeto.json'),
       'private_preflight':'deferred until separately approved root execution',
       'iso_generation':False,'browser_installation':False,'visual_changes':False}
 (job/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
 return job,sha(job/'plan.json')

def read(job, approval, root=ROOT):
 job=canonical(Path(job))
 if job.parent!=root/'work' or not job.name.startswith('cleanup-eight-'):raise ValueError('Cleanup job out of scope')
 plan_path=canonical(job/'plan.json')
 if sha(plan_path)!=approval:raise ValueError('Cleanup plan changed')
 data=json.loads(plan_path.read_text())
 if data.get('schema')!=1 or data.get('job')!=str(job) or data.get('operation')!='exact-eight-cleanup' or tuple(data.get('targets',[]))!=TARGETS:raise ValueError('Scope mismatch')
 if any(data.get(k) is not False for k in ('iso_generation','browser_installation','visual_changes')):raise ValueError('Unexpected operation enabled')
 if set(data.get('code_sha256',{}))!=set(CODE) or any(sha(root/n)!=v for n,v in data['code_sha256'].items()):raise ValueError('Cleanup code changed')
 return data

def project_metadata(root, skip):
 """Observe all preserved objects without following symlinks; dirs may change mtime after child deletion."""
 result={};stack=[root]
 while stack:
  p=stack.pop()
  if any(p==q or q in p.parents for q in skip):continue
  s=p.lstat()
  if s.st_dev!=root.stat().st_dev:raise ValueError('Unexpected filesystem in project: '+str(p))
  if stat.S_ISDIR(s.st_mode):
   with os.scandir(p) as entries:stack.extend(Path(e.path) for e in entries)
   result[str(p)]=(s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid)
  else:result[str(p)]=(s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_nlink,os.readlink(p) if p.is_symlink() else None)
 return result

def memory_references(paths, evidence, proc_root=Path('/proc')):
 """Also reject mappings/executables whose original descriptor has already closed."""
 for process in proc_root.iterdir():
  if not process.name.isdigit():continue
  first=process_identity(process)
  if first is None:continue
  try:
   try:exe=os.readlink(process/'exe')
   except OSError as error:
    if error.errno not in (errno.ENOENT,errno.ESRCH):raise
    exe=''
   mappings=(process/'maps').read_text().splitlines()
   refs=[('exe',exe)]
   refs += [('mmap',parts[5]) for line in mappings if len(parts:=line.split(None,5))==6]
   last=process_identity(process)
   if last is None:continue
   if not same_process(first,last):raise ValueError('PID reused during mappings audit')
   for kind,value in refs:
    value=value.removesuffix(' (deleted)')
    if any(under(value,str(p)) for p in paths):
     item={**last,'reference_type':kind,'path':value};evidence.append(item)
     raise ResourceBlocked('Candidate executable/mapping is in use',item)
  except OSError as error:
   if error.errno in (errno.ENOENT,errno.ESRCH) and process_identity(process) is None:continue
   raise

def fingerprint(p):
 s=Path(p).lstat()
 return (s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_nlink)

def verify_hashes(root, assets, report):
 report.setdefault('protected_verified_metadata',{})
 for name,value in assets.items():
  p=canonical(root/name)
  before=fingerprint(p)
  if not p.is_file() or sha(p)!=value or fingerprint(p)!=before:raise ValueError('Protected hash/identity mismatch: '+name)
  report['protected_verified_metadata'][str(p)]=before
 report['protected_hashes_verified']=len(assets)

def verify_duplicates(root, report, assets):
 current=json.loads((root/'work/release-cezaiofx/layers-ready.json').read_text())
 official=root/'work/phase4b1-dhzezpnz/original-casper'
 pairs=[]
 for name in ('minimal.squashfs','minimal.live.squashfs'):
  canonical_layer=root/'work/release-cezaiofx/published-casper'/name
  for copy in (root/'work/release-cezaiofx/pack-attempt/packed'/name,
               root/'work/release-cezaiofx/iso-1mzrr68i/result-tree/casper'/name):
   if sha(canonical(copy))!=current['files'][name]:raise ValueError('Candidate duplicate mismatch: '+str(copy))
   pairs.append([str(copy),str(canonical_layer)])
  for copy in (root/'work/phase2/casper'/name,root/'work/release-cezaiofx/iso-1mzrr68i/source-tree/casper'/name):
   if sha(canonical(copy))!=assets[str((official/name).relative_to(root))]:raise ValueError('Official duplicate mismatch: '+str(copy))
   pairs.append([str(copy),str(official/name)])
 old=root/TARGETS[-1]
 if sha(canonical(old))!='2e3a6eecf59d535a4825ff41655c542f6ef2017ccce9a9672891ace2672f2bc7':raise ValueError('Historical ISO no longer matches its retained report')
 report['duplicate_pairs_verified']=pairs

def execute(job, approval, authorized=False):
 if not authorized:raise ValueError('Explicit privileged execution approval required')
 if os.geteuid()!=0:raise ValueError('Global/private preflight requires separately approved root execution')
 job=Path(job);data=read(job,approval)
 # Exclusive report prevents automatic retry of the same approved job.
 fd=os.open(job/'execution.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 report={'status':'preflight','plan_sha256':approval,'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
         'removed':[],'resource_checks':[],'memory_reference_checks':[],'iso_generated':False,'browser_installed':False,'visual_changes':False}
 def persist():
  raw=(json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode();os.lseek(fd,0,0);os.ftruncate(fd,0);os.write(fd,raw);os.fsync(fd)
 before=None
 try:
  paths=checked_paths(ROOT,data['targets'])
  report['df_before']=subprocess.run(['df','-B1',str(ROOT)],capture_output=True,text=True,check=True).stdout
  report['free_bytes_before']=shutil.disk_usage(ROOT).free
  resources_clear(paths,report['resource_checks']);memory_references(paths,report['memory_reference_checks'])
  identities,size=inventory(paths)
  if len(identities)!=data['expected_entries'] or size!=data['expected_allocated_bytes']:raise ValueError('Candidate inventory differs from reviewed storage audit')
  for p in paths:inventory([p]) # no hardlink groups crossing item boundaries
  report.update(candidate_entries=len(identities),candidate_allocated_bytes=size)
  verify_hashes(ROOT,data['protected_sha256'],report)
  verify_duplicates(ROOT,report,data['protected_sha256'])
  if source_files(ROOT)!=data['source_files']:raise ValueError('Source/docs/reports/cache metadata changed after plan')
  for name,value in data['host_critical_files'].items():
   if sha(name)!=value:raise ValueError('Host critical baseline changed: '+name)
  if sha(ROOT/'config/projeto.json')!=data['permissions_config_sha256']:raise ValueError('Project gates changed')
  if any(fingerprint(p)!=value for p,value in report['protected_verified_metadata'].items()):raise ValueError('Protected input changed after hashing')
  before=project_metadata(ROOT,paths+[job])
  resources_clear(paths,report['resource_checks']);memory_references(paths,report['memory_reference_checks'])
  report['status']='preflight_passed';persist()
  for p in paths:
   report['current_item']=str(p);persist()
   # Repeat global resources, code, and subtree identity checks immediately before each deletion.
   read(job,approval)
   resources_clear(paths,report['resource_checks']);memory_references(paths,report['memory_reference_checks'])
   canonical(p);canonical(p.parent)
   report['deletion_started']=str(p);persist()
   report['removed']+=delete_paths([p],identities)
   report.pop('deletion_started',None)
   report['status']='cleaning';persist()
  if project_metadata(ROOT,[job])!=before:raise ValueError('Unexpected change outside the exact eight candidates')
  if source_files(ROOT)!=data['source_files']:raise ValueError('Preserved source/reports changed')
  if any(fingerprint(p)!=value for p,value in report['protected_verified_metadata'].items()):raise ValueError('Protected asset changed during cleanup')
  for name,value in data['host_critical_files'].items():
   if sha(name)!=value:raise ValueError('Host critical file changed: '+name)
  if sha(ROOT/'config/projeto.json')!=data['permissions_config_sha256']:raise ValueError('Project gates changed during cleanup')
  # Fully rehash the canonical published layers after removal; accepted raw images were hashed before and remain metadata-identical.
  layer_assets={k:v for k,v in data['protected_sha256'].items() if '/published-casper/' in k}
  after={};verify_hashes(ROOT,layer_assets,after)
  report.update(status='completed',preserved_metadata_unchanged=True,source_files_unchanged=True,
                canonical_layers_rehashed_after=True,accepted_images_hashed_before_and_metadata_unchanged=True)
 except BaseException as error:
  report.update(status='stopped',error=str(error))
  if report.get('deletion_started'):report['possibly_partial_item']=report['deletion_started']
  if isinstance(error,ResourceBlocked):report['resource_block']=error.evidence
  raise
 finally:
  report['free_bytes_after']=shutil.disk_usage(ROOT).free
  if 'free_bytes_before' in report:report['recovered_bytes_measured']=report['free_bytes_after']-report['free_bytes_before']
  report['df_after']=subprocess.run(['df','-B1',str(ROOT)],capture_output=True,text=True).stdout
  report['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
  persist();os.fchmod(fd,0o444);os.close(fd)
 return job/'execution.json'
