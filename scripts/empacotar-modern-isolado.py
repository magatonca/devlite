#!/usr/bin/env python3
"""Sealed layered pack of accepted Modern views. No ISO or guest execution."""
import argparse,hashlib,importlib.util,json,os,re,shlex,shutil,stat,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pipeline.devlite.runtime import owned_directory,Runner
from pipeline.devlite.minimal_root import snapshot,allocated_usage,EPOCH
from pipeline.devlite.release_layers import clean_snapshot,recipe,materialize,manifests
from pipeline.devlite.release_pack import compress_args
from pipeline.devlite.release_resume import absent_xattrs
from pipeline.devlite.customize.installation import installed
from pipeline.devlite.public_execution import filesystem_proof
from pipeline.devlite.customize.isolation_validation import critical_files,cgroup_limits
spec=importlib.util.spec_from_file_location('accepted_modern_adapter',ROOT/'scripts/aplicar-modern-isolado.py');app=importlib.util.module_from_spec(spec);spec.loader.exec_module(app)
ENTRY='scripts/empacotar-modern-isolado.py'
SOURCE=ROOT/'work/modern-apply-5w334rzl'
APPROVAL='153cd14745cdddb20d1c9f00448b9a4fbcf1376387e9cdcdcc017fdb6e8771e2'
LIMITS=app.LIMITS
RESERVE=20*1024**3
CAPS='CAP_SYS_ADMIN CAP_SYS_CHROOT CAP_SETPCAP CAP_KILL CAP_CHOWN CAP_DAC_OVERRIDE CAP_DAC_READ_SEARCH CAP_FOWNER CAP_FSETID CAP_SETGID CAP_SETUID CAP_SETFCAP CAP_MKNOD'
def sha(p):return app.sha(p)
def storage_required(base,live):return 3*base+5*live+RESERVE

def accepted():
 app.read(SOURCE,APPROVAL)
 p=SOURCE/'result.json';s=p.lstat();d=json.loads(p.read_text())
 if p.is_symlink() or not stat.S_ISREG(s.st_mode) or s.st_uid!=0 or s.st_mode&0o022 or d.get('status')!='modern_full_views_verified' or d.get('contract_sha256')!=APPROVAL or d.get('host_critical_unchanged') is not True or d.get('source_metadata_unchanged') is not True or d.get('source_images_modified') is not False or d.get('iso_generated') is not False or set(d.get('results',{}))!={'base','live'}:raise ValueError('Modern views not accepted')
 for n,v in d['results'].items():
  if v.get('allowed_patch_verified') is not True or v.get('filesystem_check')!='passed' or v['image']['file']!=str(SOURCE/'attempt'/(n+'.ext4')):raise ValueError('Incomplete Modern proof')
 return d

def locked_browser_plan():
 browser=app.review.SOURCE
 result=app.review.legacy.load(browser/'browser-result.json')
 contract=app.review.legacy.load(browser/'browser-contract.json',result['contract_sha256'])
 return app.review.legacy.load(browser/'plan.json',contract['plan_sha256'])

def command(job,h):
 cmd=app.command(job,h)
 return [str(ROOT/ENTRY) if x==str(ROOT/app.ENTRY) else '--property=CapabilityBoundingSet='+CAPS if x.startswith('--property=CapabilityBoundingSet=') else x for x in cmd]

def prepare():
 if os.geteuid()==0:raise ValueError('Prepare as magaton')
 source=accepted();locked_browser_plan();required=storage_required(*(source['results'][n]['allocated_bytes'] for n in ('base','live')))
 if shutil.disk_usage(ROOT).free<required:raise ValueError('Conservative pack budget insufficient')
 job=owned_directory(ROOT/'work','modern-pack-');old=json.loads((SOURCE/'contract.json').read_text())
 refs=['work/phase4b1-dhzezpnz/original-casper/filesystem.manifest','work/phase4b1-dhzezpnz/original-casper/install-sources.yaml','work/release-browser-2f24tvsg/plan.json']
 code={**old['code_sha256'],ENTRY:sha(ROOT/ENTRY)}
 data={'operation':'modern-layered-pack-v1','job':str(job),'modern_contract_sha256':APPROVAL,'modern_result_sha256':sha(SOURCE/'result.json'),
 'source_images':{n:v['image'] for n,v in source['results'].items()},'reference_sha256':{n:sha(ROOT/n) for n in refs},'code_sha256':code,
 'host_critical_files':critical_files(),'host_namespaces':{n:os.readlink('/proc/self/ns/'+n) for n in ('mnt','pid','net','ipc','uts')},
 'limits':LIMITS,'reserve_bytes':RESERVE,'initial_required_bytes':required,'iso_generation':False,'guest_execution':False,'package_installation':False}
 (job/'contract.json').write_text(json.dumps(data,indent=2)+'\n');h=sha(job/'contract.json')
 (job/'command.json').write_text(json.dumps({'command':command(job,h),'approval_sha256':h},indent=2)+'\n')
 print(job);print(h);print(shlex.join(command(job,h)))

def read(job,h):
 job=app.review.legacy.confined(job)
 if job.parent!=ROOT/'work' or not job.name.startswith('modern-pack-'):raise ValueError('Unexpected pack job')
 d=app.review.legacy.load(job/'contract.json',h)
 if d['job']!=str(job) or d['operation']!='modern-layered-pack-v1' or d['modern_contract_sha256']!=APPROVAL or d['limits']!=LIMITS or d['reserve_bytes']!=RESERVE or any(d[k] is not False for k in ('iso_generation','guest_execution','package_installation')):raise ValueError('Pack scope changed')
 if any(sha(ROOT/n)!=v for n,v in d['code_sha256'].items()) or any(sha(ROOT/n)!=v for n,v in d['reference_sha256'].items()):raise ValueError('Code/references changed')
 source=accepted()
 if sha(SOURCE/'result.json')!=d['modern_result_sha256'] or d['source_images']!={n:v['image'] for n,v in source['results'].items()}:raise ValueError('Source receipt changed')
 if d['initial_required_bytes']!=storage_required(*(source['results'][n]['allocated_bytes'] for n in ('base','live'))):raise ValueError('Budget changed')
 if critical_files()!=d['host_critical_files']:raise ValueError('Host baseline changed')
 return job,d

def run(job,h,authorized):
 if not authorized or os.geteuid()!=0 or os.getpid()!=1:raise ValueError('Approved root namespace PID1 required')
 job,d=read(job,h)
 if shutil.disk_usage(job).free<d['initial_required_bytes']:raise ValueError('Insufficient pack budget')
 if any(os.readlink('/proc/self/ns/'+n)==v for n,v in d['host_namespaces'].items()):raise ValueError('Namespace missing')
 group=Path('/sys/fs/cgroup')/Path('/proc/self/cgroup').read_text().strip().split('::',1)[1].lstrip('/')
 if group.name!='devlite-'+job.name+'.service':raise ValueError('Wrong cgroup')
 cgroup_limits(group,LIMITS)
 if 'NoNewPrivs:\t1' not in Path('/proc/self/status').read_text():raise ValueError('NoNewPrivileges missing')
 filesystem_proof(Path('/proc/self/mountinfo').read_text(),job,tuple(d['host_critical_files'])+(str(SOURCE),))
 with (job/'execution.lock').open('x') as f:f.write(h)
 os.chown(job,0,0);job.chmod(0o700);work=job/'pack-attempt';work.mkdir(mode=0o700);(work/'logs').mkdir()
 runner=Runner(work/'logs',EPOCH);runner.env.pop('SOURCE_DATE_EPOCH',None)
 report={'status':'running','contract_sha256':h,'iso_generated':False,'guest_executed':False};mounted=[];source_metadata={}
 def persist():(job/'pack-report.json').write_text(json.dumps(report,indent=2)+'\n')
 def call(label,args):
  if shutil.disk_usage(job).free<RESERVE:raise ValueError('20 GiB reserve reached')
  report['phase']=label;persist();runner.run(label,args)
 def unmount(path):runner.run('umount-'+path.name,['umount',str(path)]);mounted.remove(path)
 try:
  call('private',['mount','--make-rprivate','/']);trees={};states={}
  expected_plan=locked_browser_plan()
  for n,image in d['source_images'].items():
   p=app.review.legacy.confined(image['file']);s=p.lstat()
   if p!=SOURCE/'attempt'/(n+'.ext4') or not stat.S_ISREG(s.st_mode) or s.st_uid!=0 or s.st_mode&0o022 or s.st_size!=image['bytes'] or sha(p)!=image['sha256']:raise ValueError('Accepted Modern image changed')
   source_metadata[n]=(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
   root=work/n;root.mkdir();call('mount-'+n,['mount','-t','ext4','-o','loop,ro,noload,nodev,nosuid,noexec',str(p),str(root)]);mounted.append(root)
   if not os.statvfs(root).f_flag & os.ST_RDONLY:raise ValueError('Source view writable')
   states[n]=installed((root/'var/lib/dpkg/status').read_text())
   if states[n]!=expected_plan['targets'][n]['final_versions']:raise ValueError('Package versions differ from browser lock')
   trees[n]=clean_snapshot(snapshot(root))
  if any(states['live'].get(p)!=v for p,v in states['base'].items()):raise ValueError('Incompatible Base/Live versions')
  required=storage_required(allocated_usage(work/'base'),allocated_usage(work/'live'))
  if shutil.disk_usage(job).free<max(required,d['initial_required_bytes']):raise ValueError('Actual pack budget insufficient')
  delta=recipe(trees['base'],trees['live']);(work/'delta-recipe.json').write_text(json.dumps(delta,indent=2)+'\n')
  delta_root=work/'delta';delta_tree=materialize(work/'live',delta_root,delta,EPOCH)
  packed=work/'packed';packed.mkdir();verified={}
  for n,source,expected in [('minimal.squashfs',work/'base',trees['base']),('minimal.live.squashfs',delta_root,delta_tree)]:
   output=packed/n;args=compress_args(source,output,expected['.'])
   if n=='minimal.squashfs':args+=['-e','var/lib/devlite-executor']
   call('compress-'+n,args);extracted=work/('verify-'+n)
   call('extract-'+n,['unsquashfs','-strict-errors','-processors','1','-data-queue','64','-frag-queue','64','-d',str(extracted),str(output)])
   if snapshot(extracted)!=expected:raise ValueError('SquashFS round-trip differs: '+n)
   verified[n]={'sha256':sha(output),'uncompressed_bytes':allocated_usage(extracted),'entries':len(expected)}
  for name,file in [('base','minimal.squashfs'),('delta','minimal.live.squashfs')]:
   target=work/('mounted-'+name);target.mkdir();call('mount-new-'+name,['mount','-t','squashfs','-o','loop,ro,nodev,nosuid',str(packed/file),str(target)]);mounted.append(target)
  merged=work/'mounted-merged';merged.mkdir();call('kernel-compose',['mount','-t','overlay','overlay','-o','ro,lowerdir='+str(work/'mounted-delta')+':'+str(work/'mounted-base'),str(merged)]);mounted.append(merged)
  absence=absent_xattrs(packed/'minimal.live.squashfs',delta_tree);absence=frozenset(p for p in absence if p in trees['live'] and not trees['live'][p].get('xattrs'))
  if snapshot(merged,xattr_absence=absence)!=trees['live']:raise ValueError('Kernel composition differs from accepted Live')
  for target in list(reversed(mounted)):unmount(target)
  original=ROOT/'work/phase4b1-dhzezpnz/original-casper';values=manifests(states['base'],states['live'],(original/'filesystem.manifest').read_text())
  values.update({'minimal.size':str(verified['minimal.squashfs']['uncompressed_bytes'])+'\n','minimal.live.size':str(verified['minimal.live.squashfs']['uncompressed_bytes'])+'\n','filesystem.size':str(sum(v['uncompressed_bytes'] for v in verified.values()))+'\n'})
  catalog,count=re.subn(r'^  size: [0-9]+$','  size: '+str(verified['minimal.squashfs']['uncompressed_bytes']),(original/'install-sources.yaml').read_text(),flags=re.M)
  if count!=1 or 'type: fsimage-layered' not in catalog or 'path: minimal.squashfs' not in catalog:raise ValueError('Installer catalog incompatible')
  values['install-sources.yaml']=catalog
  published=job/'published-casper';published.mkdir(mode=0o755)
  for name in verified:
   if shutil.disk_usage(job).free<RESERVE+(packed/name).stat().st_size:raise ValueError('Publication reserve insufficient')
   shutil.copyfile(packed/name,published/name);(published/name).chmod(0o444)
  for name,text in values.items():(published/name).write_text(text);(published/name).chmod(0o444)
  for name,record in d['source_images'].items():
   s=Path(record['file']).stat()
   if source_metadata[name]!=(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns):raise ValueError('Source image metadata changed')
  if critical_files()!=d['host_critical_files']:raise ValueError('Host baseline changed')
  receipt={'status':'layers_verified','job_sha256':h,'modern_contract_sha256':APPROVAL,'modern_result_sha256':d['modern_result_sha256'],'published':str(published),'layers':verified,'files':{p.name:sha(p) for p in sorted(published.iterdir())},'kernel_composition_verified':True,'roundtrip_verified':True,'source_metadata_unchanged':True,'host_critical_unchanged':True,'iso_generated':False}
  (job/'layers-ready.json').write_text(json.dumps(receipt,indent=2)+'\n');(job/'layers-ready.json').chmod(0o444)
  report.update(status='layers_verified',free_bytes=shutil.disk_usage(job).free,layers=verified)
 except BaseException as error:report.update(status='quarantined',error=str(error));raise
 finally:
  for path in list(reversed(mounted)):
   try:unmount(path)
   except BaseException as error:report.setdefault('cleanup_errors',[]).append(str(error))
  persist();(job/'pack-report.json').chmod(0o444);job.chmod(0o755)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--job',type=Path);p.add_argument('--approval-sha256');p.add_argument('--execute-authorized',action='store_true');a=p.parse_args()
 if a.prepare:prepare()
 else:run(a.job,a.approval_sha256,a.execute_authorized)
