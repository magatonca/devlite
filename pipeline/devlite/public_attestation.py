"""Root-owned sealed-memory handoff; no trust in replaceable job report files."""
import fcntl,hashlib,hmac,json,os,re,stat
from pathlib import Path
NAMES=('mnt','pid','net','ipc','uts')
MAX_BYTES=2*1024*1024
REQUIRED_SEALS=fcntl.F_SEAL_WRITE|fcntl.F_SEAL_GROW|fcntl.F_SEAL_SHRINK|fcntl.F_SEAL_SEAL
POLICY={'transport':'root-owned-sealed-memfd-v1','contract_binding':True,'invocation_binding':True,
        'nonce_bytes':32,'inner_systemctl':False}
def runtime_context():
 return {'pid':os.getpid(),'uid':os.geteuid(),
         'namespaces':{name:os.readlink('/proc/self/ns/'+name) for name in NAMES},
         'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
         'cgroup':Path('/proc/self/cgroup').read_text().strip(),
         'invocation_id':os.environ.get('INVOCATION_ID','')}

def seal(report,job,approval,nonce):
 envelope={'schema':1,'job':str(job),'contract_sha256':approval,'execution_nonce':nonce,
           'invocation_id':report['invocation_id'],'boot_id':report['boot_id'],'cgroup':report['cgroup'],'report':report}
 raw=json.dumps(envelope,sort_keys=True,separators=(',',':')).encode()
 if not raw or len(raw)>MAX_BYTES:raise ValueError('Attestation size limit')
 fd=os.memfd_create('devlite-isolation',os.MFD_CLOEXEC|os.MFD_ALLOW_SEALING)
 try:
  offset=0
  while offset<len(raw):
   written=os.write(fd,raw[offset:])
   if written<=0:raise ValueError('Short attestation write')
   offset+=written
  os.fchmod(fd,0o400)
  fcntl.fcntl(fd,fcntl.F_ADD_SEALS,REQUIRED_SEALS)
  return fd,hashlib.sha256(raw).hexdigest()
 except BaseException:os.close(fd);raise

def read_sealed(fd,expected_digest):
 if type(fd) is not int or fd<3 or not re.fullmatch('[a-f0-9]{64}',expected_digest or ''):raise ValueError('Missing/invalid inherited attestation')
 info=os.fstat(fd)
 if not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or info.st_size<=0 or info.st_size>MAX_BYTES:raise ValueError('Untrusted attestation owner/type/size')
 try:seals=fcntl.fcntl(fd,fcntl.F_GET_SEALS)
 except OSError as error:raise ValueError('Attestation is not sealable memory') from error
 if seals & REQUIRED_SEALS!=REQUIRED_SEALS:raise ValueError('Attestation not fully sealed')
 raw=os.pread(fd,info.st_size+1,0)
 if len(raw)!=info.st_size or not hmac.compare_digest(hashlib.sha256(raw).hexdigest(),expected_digest):raise ValueError('Attestation digest differs')
 try:return json.loads(raw)
 except (UnicodeError,ValueError) as error:raise ValueError('Invalid attestation JSON') from error

def verify(envelope,job,approval,nonce,current,data):
 from .public_isolation import property_errors,query_argv
 from .public_execution import protected_paths
 try:
  required={'schema','job','contract_sha256','execution_nonce','invocation_id','boot_id','cgroup','report'}
  if not isinstance(envelope,dict) or set(envelope)!=required or envelope['schema']!=1:raise ValueError('Incomplete attestation envelope')
  if not re.fullmatch('[a-f0-9]{64}',nonce or '') or envelope['execution_nonce']!=nonce:raise ValueError('Attestation execution nonce differs')
  if envelope['job']!=str(job) or envelope['contract_sha256']!=approval:raise ValueError('Attestation belongs to another job/contract')
  if not re.fullmatch('[a-f0-9]{32}',current['invocation_id']) or any(envelope[k]!=current[k] for k in ('invocation_id','boot_id','cgroup')):raise ValueError('Attestation belongs to another invocation/boot/cgroup')
  if not re.fullmatch('[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}',current['boot_id']) or not current['cgroup']:raise ValueError('Missing boot/cgroup identity')
  report=envelope['report']
  if report['phase']!='systemd' or report['status']!='passed' or report['uid']!=0 or report['application_started'] is not False:raise ValueError('External attestation not approved')
  if report['job']!=str(job) or report['contract_sha256']!=approval or any(report[k]!=envelope[k] for k in ('invocation_id','boot_id','cgroup')):raise ValueError('External report context differs')
  unit='devlite-public-'+job.name.removeprefix('release-')+'.service'
  if current['cgroup'].split('/')[-1]!=unit:raise ValueError('Unexpected service cgroup')
  props=report['service_properties']
  if report['unit']!=unit or props['InvocationID']!=current['invocation_id'] or props['MainPID']!=str(report['pid']) or property_errors(props,job) or report['property_errors']!={}:raise ValueError('External service properties incomplete/different')
  query=report['service_query']
  if query['returncode']!=0 or not isinstance(query['stdout'],str) or not isinstance(query['stderr'],str) or query['argv']!=query_argv(job)[1]:raise ValueError('External query not successful/complete')
  parsed=dict(line.split('=',1) for line in query['stdout'].splitlines() if '=' in line)
  if parsed!=props:raise ValueError('External query stdout differs from recorded properties')
  fs=report['filesystem'];paths=set(protected_paths(data))
  if set(fs['host_readonly'])!=paths or any(v['vfs_readonly'] is not True for v in fs['host_readonly'].values()) or fs['job_writable']!=str(job) or fs['writable_or_unproven_host_paths']!=[]:raise ValueError('External filesystem evidence incomplete')
  if not report['mountinfo'] or set(report['namespaces'])!=set(NAMES) or set(current['namespaces'])!=set(NAMES):raise ValueError('Missing namespace/mount evidence')
  if current['pid']!=1 or current['uid']!=0:raise ValueError('Inner PID/UID differs')
  for name in NAMES:
   outer=report['namespaces'][name];inner=current['namespaces'][name]
   if not re.fullmatch(name+r':\[[0-9]+\]',outer) or not re.fullmatch(name+r':\[[0-9]+\]',inner):raise ValueError('Malformed namespace identity')
   if inner==outer or inner==data['host_namespaces'][name]:raise ValueError('Inner namespace isolation missing: '+name)
  return report
 except (KeyError,TypeError,AttributeError) as error:raise ValueError('Incomplete attestation data') from error
