#!/usr/bin/env python3
"""Modern-only application to new disposable full views; never builds an ISO."""
import argparse,hashlib,importlib.util,json,os,shlex,shutil,stat,subprocess,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from prototypes.modern_adapter import render,validate_review,write_bundle,apply_patch,verify_patch,REVIEW
from pipeline.devlite.minimal_root import snapshot,allocated_usage
from pipeline.devlite.runtime import owned_directory
from pipeline.devlite.public_execution import filesystem_proof
from pipeline.devlite.customize.isolation_validation import critical_files,cgroup_limits
spec=importlib.util.spec_from_file_location('modern_review_runtime',ROOT/'scripts/validar-prototipos-isolados.py');review=importlib.util.module_from_spec(spec);spec.loader.exec_module(review)
ENTRY='scripts/aplicar-modern-isolado.py'
GIB=1024**3
LIMITS={'memory_bytes':2560*1024**2,'swap_bytes':GIB,'tasks':128}
INITIAL=81771356160
RESERVE=20*GIB

def sha(p):return review.sha(p)
def command(job,approval):
 review.legacy.ENTRY=ENTRY
 cmd=review.legacy.command(job,approval)
 replacements={'--property=MemoryMax=1073741824':'--property=MemoryMax=2684354560','--property=MemorySwapMax=536870912':'--property=MemorySwapMax=1073741824','--property=TasksMax=64':'--property=TasksMax=128','--property=RuntimeMaxSec=300':'--property=RuntimeMaxSec=10800'}
 return [replacements.get(x,x)+' CAP_FOWNER' if x.startswith('--property=CapabilityBoundingSet=') else replacements.get(x,x) for x in cmd]

def require_fowner(status):
 try:effective=int(next(line.split()[1] for line in status.splitlines() if line.startswith('CapEff:')),16)
 except (StopIteration,ValueError,IndexError) as error:raise ValueError('Missing effective capability evidence') from error
 if not effective & (1<<3):raise ValueError('CAP_FOWNER missing before copying images')

def budget(additional=0,initial=False):
 required=max(INITIAL if initial else 0,RESERVE+additional)
 if shutil.disk_usage(ROOT).free<required:raise ValueError('Storage budget insufficient: '+str(required))
 return required

def prepare():
 if os.geteuid()==0:raise ValueError('Prepare as magaton')
 budget(initial=True);approved=validate_review()
 receipt=review.SOURCE/'browser-result.json';r=review.legacy.load(receipt)
 if r['status']!='browser_full_views_verified':raise ValueError('Browser source not accepted')
 old=review.legacy.load(review.SOURCE/'browser-contract.json',r['contract_sha256'])
 code={**old['code_sha256'],ENTRY:sha(ROOT/ENTRY),'scripts/validar-prototipos-isolados.py':sha(ROOT/'scripts/validar-prototipos-isolados.py'),'scripts/verificar-php-adminer.py':sha(ROOT/'scripts/verificar-php-adminer.py'),'prototypes/modern_adapter.py':sha(ROOT/'prototypes/modern_adapter.py')}
 if any(sha(ROOT/n)!=h for n,h in code.items()):raise ValueError('Accepted code changed')
 job=owned_directory(ROOT/'work','modern-apply-');(job/'bundles').mkdir();patch_hashes={}
 for target in ('base','live'):
  patch=render(approved['results'][target]['configuration']);write_bundle(job/'bundles',target,patch)
 for p in (job/'bundles').rglob('*'):
  if p.is_file():patch_hashes[str(p.relative_to(job))]=sha(p)
 data={'operation':'modern-only-full-views-v1','job':str(job),'review_sha256':sha(REVIEW),'source_receipt_sha256':sha(receipt),
 'source_images':{n:r['results'][n]['image'] for n in ('base','live')},'code_sha256':code,'bundle_sha256':patch_hashes,
 'host_critical_files':critical_files(),'host_namespaces':{n:os.readlink('/proc/self/ns/'+n) for n in ('mnt','pid','net','ipc','uts')},
 'limits':LIMITS,'reserve_bytes':RESERVE,'initial_bytes':INITIAL,'iso_generated':False,'packages_installed':False,'adminer_installed':False,'control2_installed':False}
 (job/'contract.json').write_text(json.dumps(data,indent=2)+'\n');h=sha(job/'contract.json')
 (job/'command.json').write_text(json.dumps({'command':command(job,h),'approval_sha256':h},indent=2)+'\n')
 print(job);print(h);print(shlex.join(command(job,h)))

def read(job,approval):
 job=review.legacy.confined(job)
 if job.parent!=ROOT/'work' or not job.name.startswith('modern-apply-'):raise ValueError('Wrong job')
 d=review.legacy.load(job/'contract.json',approval)
 if d['job']!=str(job) or d['operation']!='modern-only-full-views-v1' or d['limits']!=LIMITS or d['reserve_bytes']!=RESERVE or d['initial_bytes']!=INITIAL:raise ValueError('Scope changed')
 if any(d[k] is not False for k in ('iso_generated','packages_installed','adminer_installed','control2_installed')):raise ValueError('Scope expanded')
 if any(sha(ROOT/n)!=h for n,h in d['code_sha256'].items()) or any(sha(job/n)!=h for n,h in d['bundle_sha256'].items()):raise ValueError('Sealed code/payload changed')
 actual={str(p.relative_to(job)) for p in (job/'bundles').rglob('*') if p.is_file()}
 if actual!=set(d['bundle_sha256']):raise ValueError('Payload coverage changed')
 if sha(REVIEW)!=d['review_sha256'] or sha(review.SOURCE/'browser-result.json')!=d['source_receipt_sha256']:raise ValueError('Accepted receipt changed')
 approved=validate_review();source=review.legacy.load(review.SOURCE/'browser-result.json')
 if d['source_images']!={n:source['results'][n]['image'] for n in ('base','live')}:raise ValueError('Source images changed')
 for target in ('base','live'):
  expected={n:{k:v for k,v in x.items() if k!='text'} for n,x in render(approved['results'][target]['configuration']).items()}
  if json.loads((job/'bundles'/target/'patch.json').read_text())!=expected:raise ValueError('Patch differs from renderer')
 if critical_files()!=d['host_critical_files']:raise ValueError('Host baseline changed')
 return job,d

def run(job,approval,authorized):
 if not authorized or os.geteuid()!=0 or os.getpid()!=1:raise ValueError('Approved root PID1 required')
 job,d=read(job,approval);budget(initial=True)
 if any(os.readlink('/proc/self/ns/'+n)==v for n,v in d['host_namespaces'].items()):raise ValueError('Namespace isolation missing')
 group=Path('/sys/fs/cgroup')/Path('/proc/self/cgroup').read_text().strip().split('::',1)[1].lstrip('/')
 if group.name!='devlite-'+job.name+'.service':raise ValueError('Wrong cgroup')
 cgroup_limits(group,LIMITS)
 if 'NoNewPrivs:\t1' not in Path('/proc/self/status').read_text():raise ValueError('NoNewPrivileges missing')
 filesystem_proof(Path('/proc/self/mountinfo').read_text(),job,tuple(d['host_critical_files'])+(str(review.SOURCE),))
 require_fowner(Path('/proc/self/status').read_text())
 with (job/'execution.lock').open('x') as f:f.write(approval)
 os.chown(job,0,0);job.chmod(0o700);attempt=job/'attempt';attempt.mkdir(mode=0o700)
 report={'status':'running','results':{},'contract_sha256':approval,'source_images_modified':False,'iso_generated':False,'packages_installed':False}
 def persist():
  (job/'result.json').write_text(json.dumps(report,indent=2)+'\n')
 def call(args):subprocess.run(args,check=True,stdin=subprocess.DEVNULL,env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LC_ALL':'C'})
 try:
  call(['mount','--make-rprivate','/'])
  for target,record in d['source_images'].items():
   read(job,approval);budget(12*GIB+GIB)
   source=review.legacy.confined(record['file']);s=source.lstat()
   if source!=review.SOURCE/'attempt'/(target+'.ext4') or not stat.S_ISREG(s.st_mode) or s.st_uid!=0 or s.st_mode&0o022 or s.st_size!=record['bytes'] or sha(source)!=record['sha256']:raise ValueError('Source image integrity failed')
   identity=(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
   image=attempt/(target+'.ext4')
   if image.exists():raise ValueError('Clone already exists')
   report['current_target']=target;report['phase']='cloning';persist()
   call(['cp','--reflink=auto','--sparse=always','--no-clobber','--',str(source),str(image)])
   image.chmod(0o600)
   if image.stat().st_nlink!=1 or sha(image)!=record['sha256']:raise ValueError('Clone integrity failed')
   budget(GIB);root=attempt/(target+'-root');root.mkdir()
   call(['mount','-t','ext4','-o','loop,rw,noatime,nodev,nosuid,noexec',str(image),str(root)])
   try:
    report['phase']='auditing_and_patching';persist();before=snapshot(root)
    patch,allowed=apply_patch(root,job/'bundles'/target,before)
    after=snapshot(root);verify_patch(before,after,patch,allowed)
    if before['var/lib/dpkg/status']!=after['var/lib/dpkg/status']:raise ValueError('dpkg changed')
    allocated=allocated_usage(root)
    (attempt/(target+'-changes.json')).write_text(json.dumps({'allowed':sorted(allowed),'patch_files':list(patch),'unmodified_entries':len(before)-len(set(patch)&set(before))},indent=2)+'\n')
    del before,after
   finally:call(['umount',str(root)])
   report['phase']='checking_filesystem';persist()
   call(['e2fsck','-f','-n',str(image)])
   value=sha(image);s=source.stat()
   if identity!=(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns):raise ValueError('Source metadata changed')
   report['results'][target]={'image':{'file':str(image),'bytes':image.stat().st_size,'sha256':value},'allocated_bytes':allocated,'allowed_patch_verified':True,'filesystem_check':'passed','graphical_tested':False}
   persist();budget(GIB)
  required=3*report['results']['base']['allocated_bytes']+5*report['results']['live']['allocated_bytes']+10*GIB
  if shutil.disk_usage(job).free<required:raise ValueError('Next pack budget insufficient; preserve views for audit')
  if critical_files()!=d['host_critical_files']:raise ValueError('Host baseline changed')
  report.update(status='modern_full_views_verified',pack_required_bytes=required,free_bytes=shutil.disk_usage(job).free,host_critical_unchanged=True,source_metadata_unchanged=True)
 except BaseException as e:report.update(status='quarantined',error=str(e));raise
 finally:
  persist();(job/'result.json').chmod(0o444);job.chmod(0o755)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--prepare',action='store_true');ap.add_argument('--job',type=Path);ap.add_argument('--approval-sha256');ap.add_argument('--execute-authorized',action='store_true');a=ap.parse_args()
 if a.prepare:prepare()
 else:run(a.job,a.approval_sha256,a.execute_authorized)
