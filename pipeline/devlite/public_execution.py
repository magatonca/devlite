"""Sealed public application + layer integration, never an ISO or guest execution."""
import copy,json,os,re,shutil,stat,subprocess
from pathlib import Path
from .release_contract import ROOT,CODE as OLD_CODE,save
from .minimal_root import snapshot,EPOCH
from .structure import digest
from .runtime import owned_directory,Runner
from .customize.executor_contract import accepted_pair,confined
from .customize.isolation_validation import critical_files,cgroup_limits
from .public_apply import apply,validate_payload
from .public_attestation import POLICY
NEW_CODE=('pipeline/devlite/public_execution.py','pipeline/devlite/public_apply.py',
          'pipeline/devlite/final_payload.py','pipeline/devlite/final_artifacts.py',
          'pipeline/devlite/final_archive.py','scripts/preparar-aplicacao-publica.py',
          'scripts/aplicar-publico-root.py','scripts/iniciar-publico-isolado-root.py',
          'pipeline/devlite/public_isolation.py','pipeline/devlite/public_attestation.py')
CODE=tuple(sorted(set(OLD_CODE+NEW_CODE)))
SOURCE=ROOT/'work/phase4b3-wnej6dpv'
LIMITS={'memory_bytes':2684354560,'swap_bytes':1073741824,'tasks':128}
REFERENCES=('work/phase4b1-dhzezpnz/original-casper/filesystem.manifest','work/phase4b1-dhzezpnz/original-casper/install-sources.yaml')
ENV={'PATH':'/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin','LC_ALL':'C','PYTHONDONTWRITEBYTECODE':'1'}

def command(job,approval):
 unit='devlite-public-'+job.name.removeprefix('release-')
 properties=['MemoryMax=2684354560','MemorySwapMax=1073741824','CPUQuota=100%','TasksMax=128',
             'RuntimeMaxSec=10800','TimeoutStopSec=60','KillMode=control-group','OOMPolicy=kill',
             'ProtectSystem=strict','ProtectHome=read-only','ReadWritePaths='+str(job),'PrivateNetwork=yes','PrivateMounts=yes',
             'NoNewPrivileges=yes','ProtectKernelTunables=yes','ProtectKernelModules=yes',
             'ProtectControlGroups=yes','RestrictRealtime=yes',
             'RestrictAddressFamilies=AF_UNIX',
             'CapabilityBoundingSet=CAP_SYS_ADMIN CAP_CHOWN CAP_DAC_OVERRIDE CAP_DAC_READ_SEARCH CAP_FOWNER CAP_FSETID CAP_MKNOD CAP_SETFCAP']
 return ['sudo','systemd-run','--unit='+unit,'--wait','--pipe','--collect']+['--property='+p for p in properties]+[
         '/usr/bin/python3',str(ROOT/'scripts/iniciar-publico-isolado-root.py'),
         '--job',str(job),'--approval-sha256',approval,'--execute-authorized','--']+namespace_command(job,approval)

def namespace_command(job,approval):
 return ['unshare','--mount','--propagation','private','--pid','--fork','--kill-child','--mount-proc',
         '--net','--ipc','--uts','/usr/bin/python3',str(ROOT/'scripts/aplicar-publico-root.py'),
         '--job',str(job),'--approval-sha256',approval,'--execute-authorized']


def component_manifest(plan):
 return {'schema':1,'components':[{'id':i['id'],'version':i['version'],'url':i['url'],
         'algorithm':i['algorithm'],'digest':i['digest'],'prefix':i['prefix']} for i in plan['artifacts']],
         'package_manager':'versioned upstream prefixes; not dpkg packages',
         'license_policy':'upstream LICENSE/NOTICE files preserved within each prefix',
         'vscode':'optional official documentation entry; no Microsoft binary bundled'}

def prepare(payload_job,diagnostic_only=False):
 if os.geteuid()==0 or os.getuid()!=1000:raise ValueError('Prepare as magaton')
 payload_job=confined(payload_job)
 if payload_job.parent!=ROOT/'work' or not payload_job.name.startswith('public-payload-'):raise ValueError('Unexpected payload job')
 report_path=payload_job/'payload-report.json';report=json.loads(report_path.read_text())
 if report['status']!='staged_only_application_blocked' or report['payload']!=str(payload_job/'payload'):raise ValueError('Payload not ready')
 validate_payload(payload_job/'payload',report['manifest'])
 plan=json.loads((ROOT/'packages/final-external-plan.json').read_text())
 if report['source_plan_sha256']!=__import__('hashlib').sha256(json.dumps(plan,sort_keys=True).encode()).hexdigest():raise ValueError('Payload plan changed')
 origin=json.loads((ROOT/'docs/evidencias/instalacao-4b7-tentativa5.json').read_text())['accepted_pair']
 job=owned_directory(ROOT/'work','release-')
 shutil.copyfile(SOURCE/'plan.json',job/'plan.json')
 spec={'schema':1,'job':str(job),'profile':'public-release','source_job':str(SOURCE),
       'source_job_sha256':origin['job_sha256'],'source_images':{k:v['image'] for k,v in origin['results'].items()},
       'payload_job':str(payload_job),'payload_report_sha256':digest(report_path),
       'plan_sha256':digest(job/'plan.json'),'external_plan_sha256':digest(ROOT/'packages/final-external-plan.json'),
       'project_config_sha256':digest(ROOT/'config/projeto.json'),'host_critical_files':critical_files(),
       'reference_sha256':{p:digest(ROOT/p) for p in REFERENCES},
       'host_namespaces':{n:os.readlink('/proc/self/ns/'+n) for n in ('mnt','pid','net','ipc','uts')},
       'limits':LIMITS,'initial_free_bytes':70*1024**3,'reserve_bytes':56*1024**3,
       'components':component_manifest(plan),'code_sha256':{p:digest(ROOT/p) for p in CODE},
       'operations':['copy and audit only declared new files in disposable full Base/Live clones','reconcile delta and verify SquashFS with existing sealed backend'],
       'target_program_execution':False,'iso_generation':False,'isolation_attestation':POLICY,
       'operation':'isolation-diagnostic' if diagnostic_only else 'apply-and-pack'}
 if diagnostic_only:spec['operations']=['capture effective external service properties','verify sealed handoff and internal namespace/VFS directly','record legacy internal systemctl stdout/stderr/returncode for diagnosis only','read-only SHA-256 of original accepted Base/Live images; no copies, application or pack']
 save(job/'public-contract.json',spec);approval=digest(job/'public-contract.json')
 save(job/'public-command.json',{'command':command(job,approval),'approval_sha256':approval,'executed':False})
 return job,approval

def read(job,approval):
 job=confined(job)
 if job.parent!=ROOT/'work' or not job.name.startswith('release-') or job.is_symlink():raise ValueError('Unexpected application job')
 path=job/'public-contract.json'
 if path.is_symlink() or digest(path)!=approval:raise ValueError('Public contract changed')
 data=json.loads(path.read_text())
 if data.get('schema')!=1 or data.get('job')!=str(job) or data.get('profile')!='public-release':raise ValueError('Public contract identity')
 if set(data.get('code_sha256',{}))!=set(CODE) or any(digest(ROOT/p)!=h for p,h in data['code_sha256'].items()):raise ValueError('Reviewed public code changed')
 if data['source_job']!=str(SOURCE) or data['limits']!=LIMITS or data['initial_free_bytes']!=70*1024**3 or data['reserve_bytes']!=56*1024**3:raise ValueError('Unexpected source or limits')
 if set(data['source_images'])!={'base','live'} or any(v['file']!=str(SOURCE/'attempt'/(k+'.ext4')) for k,v in data['source_images'].items()):raise ValueError('Unexpected source images')
 if digest(job/'plan.json')!=data['plan_sha256'] or digest(ROOT/'packages/final-external-plan.json')!=data['external_plan_sha256']:raise ValueError('Application plan changed')
 if set(data.get('reference_sha256',{}))!=set(REFERENCES) or any(digest(ROOT/p)!=h for p,h in data['reference_sha256'].items()):raise ValueError('Original installer metadata changed')
 if data.get('operation') not in ('isolation-diagnostic','apply-and-pack'):raise ValueError('Unknown sealed operation')
 if data.get('isolation_attestation')!=POLICY:raise ValueError('Attestation protocol differs from approved profile')
 if data.get('target_program_execution') is not False or data.get('iso_generation') is not False:raise ValueError('Operation exceeds scope')
 payload=confined(data['payload_job'])
 if payload.parent!=ROOT/'work' or not payload.name.startswith('public-payload-') or digest(payload/'payload-report.json')!=data['payload_report_sha256']:raise ValueError('Staged payload changed')
 return job,data

def filesystem_flags(mountinfo,path):
 candidates=[]
 for line in mountinfo.splitlines():
  fields=line.split()
  target=re.sub(r'\\([0-7]{3})',lambda m:chr(int(m[1],8)),fields[4])
  if str(path)==target or str(path).startswith(target.rstrip('/')+'/'):
   candidates.append((len(target),set(fields[5].split(','))))
 if not candidates:raise ValueError('Missing mount protection evidence')
 return max(candidates,key=lambda item:item[0])[1]

class FilesystemIsolationError(ValueError):
 def __init__(self,message,evidence):
  self.evidence=evidence
  super().__init__(message+'; '+json.dumps(evidence,sort_keys=True))

def filesystem_proof(mountinfo,job,extra=()):
 protected=('/etc','/usr','/var/lib/dpkg','/home','/root','/run/user',str(ROOT),str(SOURCE),*extra)
 result={}
 for p in dict.fromkeys(protected):
  try:
   result[p]={'mount_flags':sorted(filesystem_flags(mountinfo,p)),
              'vfs_readonly':bool(os.statvfs(p).f_flag & os.ST_RDONLY),'resolved_path':str(Path(p).resolve())}
  except (OSError,ValueError) as error:result[p]={'vfs_readonly':False,'observation_error':str(error)}
 evidence={'host_readonly':result,'job_writable':str(job)}
 failed=[p for p,value in result.items() if not value['vfs_readonly']]
 evidence['writable_or_unproven_host_paths']=failed
 if failed:raise FilesystemIsolationError('Host filesystem is not read-only',evidence)
 if os.statvfs(job).f_flag & os.ST_RDONLY:raise FilesystemIsolationError('Job is not the writable exception',evidence)
 return evidence

def private_gate(config,destination):
 settings=json.loads(config.read_text());settings['integracao_camadas_autorizada']=True
 save(destination,settings);destination.chmod(0o444)

def diagnostic(job,data,isolation):
 from .public_isolation import service_properties,ServiceQueryError
 result={'status':'running','application_executed':False,'images_modified':False,'iso_generated':False,
         'isolation_attestation_sha256':isolation['external_attestation_sha256']}
 try:
  # Explicit forensic probe only; this query is never used to approve isolation.
  try:
   unit,values,query=service_properties(job);result['legacy_internal_systemctl']={'unit':unit,'properties':values,'query':query}
  except ServiceQueryError as error:
   result['legacy_internal_systemctl']={'unit':error.unit,'query':error.query,'error':str(error)}
  receipt=accepted_pair(SOURCE/'attempt')
  if receipt['job_sha256']!=data['source_job_sha256']:raise ValueError('Source receipt changed')
  result['source_images']={}
  for name,item in data['source_images'].items():
   if receipt['results'][name]['image']!=item:raise ValueError('Source image record changed')
   path=Path(item['file'])
   info=path.lstat()
   if not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or info.st_mode&0o022 or info.st_size!=item['bytes']:raise ValueError('Source image metadata differs')
   actual=digest(path)
   result['source_images'][name]={'sha256':actual,'expected':item['sha256'],'matches':actual==item['sha256']}
   if actual!=item['sha256']:raise ValueError('Source image integrity differs')
  result.update(status='diagnostic_completed',isolation_verified=True,source_images_verified=True)
 except BaseException as error:
  result.update(status='blocked',error=str(error));raise
 finally:
  save(job/'isolation-diagnostic-result.json',result);(job/'isolation-diagnostic-result.json').chmod(0o444)
 return job/'isolation-diagnostic-result.json'

def protected_paths(data):
 return tuple(dict.fromkeys(('/etc','/usr','/var/lib/dpkg','/home','/root','/run/user',str(ROOT),str(SOURCE),*tuple(data['host_critical_files']),str(ROOT/'config/projeto.json'))))

def run(job,approval,authorized=False,external=None):
 if not authorized or os.geteuid()!=0:raise ValueError('Separately approved root execution required')
 job,data=read(job,approval)
 if os.getpid()!=1 or any(os.readlink('/proc/self/ns/'+n)==old for n,old in data['host_namespaces'].items()):raise ValueError('Private namespaces required')
 group=Path('/sys/fs/cgroup')/Path('/proc/self/cgroup').read_text().strip().split('::',1)[1].lstrip('/')
 actual_limits=cgroup_limits(group,LIMITS)
 from .public_isolation import capture
 isolation=capture(job,data,'unshare',approval_sha256=approval,inherited=external);filesystem=isolation['filesystem']
 interfaces={line.split(':')[0].strip() for line in Path('/proc/net/dev').read_text().splitlines() if ':' in line}
 if interfaces-{'lo'}:raise ValueError('External network interface visible')
 if critical_files()!=data['host_critical_files']:raise ValueError('Host critical files changed before application')
 config=ROOT/'config/projeto.json'
 if digest(config)!=data['project_config_sha256'] or any(v for v in json.loads(config.read_text()).values() if isinstance(v,bool)):raise ValueError('Host execution flags/config changed')
 if data['operation']=='isolation-diagnostic':return diagnostic(job,data,isolation)
 if shutil.disk_usage(job).free<data['initial_free_bytes']:raise ValueError('Require 70 GiB before clones')
 attempt=job/'attempt'
 if attempt.exists() or attempt.is_symlink():raise ValueError('Do not reuse a prior attempt')
 pair_path=SOURCE/'attempt/accepted-pair.json'
 if pair_path.stat().st_uid!=0 or pair_path.stat().st_mode&0o022:raise ValueError('Untrusted source receipt')
 original=accepted_pair(SOURCE/'attempt')
 if digest(SOURCE/'job.json')!=data['source_job_sha256'] or original['job_sha256']!=data['source_job_sha256']:raise ValueError('Source contract changed')
 if any(original['results'][name]['image']!=item for name,item in data['source_images'].items()):raise ValueError('Source image receipt changed')
 attempt.mkdir(mode=0o700);(attempt/'logs').mkdir()
 runner=Runner(attempt/'logs',EPOCH);runner.env.pop('SOURCE_DATE_EPOCH',None)
 mounted=[];gate_mounted=False
 report={'status':'running','public_contract_sha256':approval,'target_programs_executed':False,'iso_generated':False,'limits':actual_limits,'filesystem':filesystem,'results':{}}
 def reserve():
  if shutil.disk_usage(job).free<data['reserve_bytes']:raise ValueError('Existing 56 GiB reserve reached')
 try:
  runner.run('private',['mount','--make-rprivate','/'])
  payload_job=Path(data['payload_job']);payload_report=json.loads((payload_job/'payload-report.json').read_text())
  validate_payload(payload_job/'payload',payload_report['manifest'])
  bundle=attempt/'payload';shutil.copytree(payload_job/'payload',bundle,symlinks=True)
  manifest=copy.deepcopy(payload_report['manifest']);validate_payload(bundle,manifest)
  external=bundle/'usr/share/devlite-os/external-components.json'
  # This deterministic provenance entry is part of the reviewed contract.
  external.parent.mkdir(parents=True,exist_ok=True)
  if external.exists() or external.is_symlink():raise ValueError('Existing external provenance entry')
  external.write_text(json.dumps(data['components'],sort_keys=True,indent=2)+'\n')
  for path in [external.parent,external]:
   rel=path.relative_to(bundle).as_posix()
   if rel not in manifest:manifest[rel]=({'type':'dir','mode':'0755'} if path.is_dir() else {'type':'file','mode':'0644','sha256':digest(path),'size':path.stat().st_size})|{'uid':0,'gid':0}
  validate_payload(bundle,manifest)
  save(attempt/'payload-manifest.json',manifest)
  for name in ('base','live'):
   reserve()
   source=Path(data['source_images'][name]['file']);record=data['source_images'][name];info=source.lstat()
   if not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or info.st_mode&0o022 or info.st_size!=record['bytes'] or digest(source)!=record['sha256']:raise ValueError('Source image integrity failed: '+name)
   clone=attempt/(name+'.ext4')
   if clone.exists() or clone.is_symlink():raise ValueError('Clone already exists')
   runner.run('clone-'+name,['cp','--sparse=always','--reflink=auto','--no-clobber',str(source),str(clone)])
   clone.chmod(0o600)
   if digest(clone)!=record['sha256']:raise ValueError('Clone differs from accepted source')
   mount=attempt/(name+'-root');mount.mkdir()
   runner.run('mount-'+name,['mount','-t','ext4','-o','loop,rw,noatime,nodev,nosuid,noexec',str(clone),str(mount)]);mounted.append(mount)
   status=digest(mount/'var/lib/dpkg/status')
   expected=original['results'][name]['final_status_sha256']
   if status!=expected:raise ValueError('Unexpected source dpkg database')
   audit=apply(mount,bundle,manifest)
   if digest(mount/'var/lib/dpkg/status')!=status:raise ValueError('dpkg database changed')
   runner.run('umount-'+name,['umount',str(mount)]);mounted.remove(mount)
   runner.run('fsck-'+name,['e2fsck','-f','-n',str(clone)])
   reserve()
   report['results'][name]={'target':name,'status':'validated','final_status_sha256':status,'file_audit':audit,
       'image':{'file':str(clone),'bytes':clone.stat().st_size,'sha256':digest(clone)}}
   save(attempt/(name+'-public-audit.json'),report['results'][name])
  save(attempt/'accepted-pair.json',{'job_sha256':approval,'results':report['results'],'rebase_required':True,'iso_generated':False})
  save(attempt/'state.json',{'state':'accepted','job_sha256':approval})
  # Invoke the unchanged packer with a root-owned derived contract. Its gate
  # is a read-only bind in this private namespace; the host config stays false.
  derived={'schema':1,'job':str(job),'executor_job':str(job),'executor_sha256':approval,
           'host_mount_namespace':data['host_namespaces']['mnt'],'source_date_epoch':EPOCH,
           'profile':'public-release','code_sha256':{p:data['code_sha256'][p] for p in OLD_CODE}}
  save(job/'release-contract.json',derived);(job/'release-contract.json').chmod(0o444)
  pack_approval=digest(job/'release-contract.json');gate=attempt/'private-pack-gate.json'
  private_gate(config,gate)
  runner.run('bind-private-gate',['mount','--bind',str(gate),str(config)]);gate_mounted=True
  runner.run('readonly-private-gate',['mount','-o','remount,bind,ro',str(config)])
  from .release_pack import run as pack
  if any(digest(ROOT/p)!=h for p,h in data['reference_sha256'].items()):raise ValueError('Installer metadata changed before pack')
  receipt=pack(job,pack_approval)
  if any(digest(ROOT/p)!=h for p,h in data['reference_sha256'].items()):raise ValueError('Installer metadata changed during pack')
  runner.run('unbind-private-gate',['umount',str(config)]);gate_mounted=False
  if digest(config)!=data['project_config_sha256'] or critical_files()!=data['host_critical_files']:raise ValueError('Host/config integrity changed')
  report.update(status='public_layers_verified',derived_pack_contract_sha256=pack_approval,layers_receipt=str(receipt),
                layers_receipt_sha256=digest(receipt),host_critical_unchanged=True,host_permissions_unchanged=True)
 except BaseException as error:
  report.update(status='quarantined',error=str(error));raise
 finally:
  failures=[]
  if gate_mounted:
   try:runner.run('cleanup-private-gate',['umount',str(config)])
   except BaseException as error:failures.append(str(error))
  for mount in reversed(mounted):
   try:runner.run('cleanup-'+mount.name,['umount',str(mount)])
   except BaseException as error:failures.append(str(error))
  report['cleanup_errors']=failures
  report['host_critical_unchanged']=critical_files()==data['host_critical_files']
  report['host_permissions_unchanged']=digest(config)==data['project_config_sha256']
  if failures or not report['host_critical_unchanged'] or not report['host_permissions_unchanged']:report['status']='quarantined'
  save(job/'public-result.json',report);(job/'public-result.json').chmod(0o444)
 if report['status']!='public_layers_verified':raise ValueError('Public operation not accepted')
 return job/'public-result.json'
