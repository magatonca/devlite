"""External service query and authenticated inner evidence, with direct VFS checks."""
import json,os,re,subprocess
from .release_contract import ROOT,save
from .public_attestation import runtime_context,read_sealed,verify
PROPERTIES=('LoadState','ProtectSystem','ProtectHome','ReadWritePaths','PrivateMounts','PrivateNetwork',
            'NoNewPrivileges','MemoryMax','MemorySwapMax','TasksMax','CPUQuotaPerSecUSec','ExecStart',
            'InvocationID','MainPID')
ENV={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LC_ALL':'C','PYTHONDONTWRITEBYTECODE':'1'}
class ServiceQueryError(ValueError):
 def __init__(self,message,unit,query):
  self.unit=unit;self.query=query
  super().__init__(message)

def query_argv(job):
 unit='devlite-public-'+job.name.removeprefix('release-')+'.service'
 return unit,['/usr/bin/systemctl','show',unit,'--no-pager']+['--property='+name for name in PROPERTIES]

def service_properties(job):
 unit,args=query_argv(job)
 query={'argv':args,'returncode':None,'stdout':'','stderr':''}
 def text(value):return value.decode(errors='replace') if isinstance(value,bytes) else value or ''
 try:
  result=subprocess.run(args,capture_output=True,text=True,check=False,env=ENV,timeout=15)
  query.update(returncode=result.returncode,stdout=result.stdout,stderr=result.stderr)
 except (OSError,subprocess.TimeoutExpired) as error:
  query.update(stdout=text(getattr(error,'stdout','')),stderr=text(getattr(error,'stderr','')) or str(error),exception_type=type(error).__name__)
  raise ServiceQueryError('External systemctl query failed: '+str(error),unit,query) from error
 if query['returncode']!=0:raise ServiceQueryError('External systemctl query exited '+str(query['returncode']),unit,query)
 values={}
 for line in query['stdout'].splitlines():
  if '=' not in line:continue
  key,value=line.split('=',1)
  if key in values:raise ServiceQueryError('Duplicate external property: '+key,unit,query)
  values[key]=value
 return unit,values,query

def property_errors(values,job):
 expected={'LoadState':'loaded','ProtectSystem':'strict','ProtectHome':'read-only',
           'ReadWritePaths':str(job),'PrivateMounts':'yes','PrivateNetwork':'yes','NoNewPrivileges':'yes',
           'MemoryMax':'2684354560','MemorySwapMax':'1073741824','TasksMax':'128','CPUQuotaPerSecUSec':'1s'}
 return {key:{'expected':value,'observed':values.get(key)} for key,value in expected.items() if values.get(key)!=value}

def capture(job,data,phase,*,approval_sha256=None,inherited=None):
 from pathlib import Path
 from .public_execution import filesystem_proof
 if phase not in ('systemd','unshare'):raise ValueError('Unknown isolation phase')
 output=job/('isolation-'+phase+'.json')
 if output.exists() or output.is_symlink():raise ValueError('Do not overwrite isolation evidence')
 current=runtime_context()
 report={'phase':phase,**current,'job':str(job),'contract_sha256':approval_sha256,
         'application_started':False,'mountinfo':Path('/proc/self/mountinfo').read_text(),'status':'inspecting'}
 failures=[]
 try:
  try:
   if not re.fullmatch('[a-f0-9]{64}',approval_sha256 or ''):raise ValueError('Missing approved contract identity')
   if phase=='systemd':
    unit,values,query=service_properties(job)
    report.update(unit=unit,service_properties=values,service_query=query,properties_source='live_external_systemctl')
    errors=property_errors(values,job);report['property_errors']=errors
    if errors:raise ValueError('Effective service properties differ: '+json.dumps(errors,sort_keys=True))
    if not re.fullmatch('[a-f0-9]{32}',current['invocation_id']) or values.get('InvocationID')!=current['invocation_id'] or values.get('MainPID')!=str(current['pid']):raise ValueError('External invocation/MainPID differs')
   else:
    if inherited is None:raise ValueError('Missing sealed external attestation')
    envelope=read_sealed(inherited.get('fd'),inherited.get('sha256'))
    outer=verify(envelope,job,approval_sha256,inherited.get('nonce'),current,data)
    report.update(unit=outer['unit'],service_properties=outer['service_properties'],property_errors={},
                  service_query=outer['service_query'],properties_source='verified_sealed_external_memfd',
                  external_attestation_sha256=inherited['sha256'],execution_nonce=inherited['nonce'],
                  external_namespaces=outer['namespaces'])
  except ServiceQueryError as error:
   report.update(unit=error.unit,service_query=error.query);failures.append(str(error))
  except (OSError,ValueError,KeyError,TypeError) as error:failures.append(str(error))
  # This check is independent of service query/handoff success and always runs.
  try:report['filesystem']=filesystem_proof(report['mountinfo'],job,tuple(data['host_critical_files'])+(str(ROOT/'config/projeto.json'),))
  except (OSError,ValueError) as error:
   report['filesystem']=getattr(error,'evidence',{});failures.append(str(error))
  report['status']='passed' if not failures else 'blocked'
  if failures:raise ValueError('; '.join(failures))
 except BaseException as error:
  report.update(status='blocked',error=str(error));raise
 finally:
  save(output,report);output.chmod(0o444)
 return report
