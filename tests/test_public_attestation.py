"""Sealed attestation and failed query regressions; no namespaces or real service."""
import copy,errno,fcntl,hashlib,json,os,runpy,subprocess,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from pipeline.devlite import public_attestation as a,public_isolation as i,public_execution as e
ROOT=Path(__file__).resolve().parents[1]
APPROVAL='a'*64
NONCE='b'*64
class AttestationTests(unittest.TestCase):
 def temp(self):return tempfile.TemporaryDirectory(dir=ROOT/'work')
 def fixture(self,job):
  unit='devlite-public-'+job.name.removeprefix('release-')+'.service'
  props={'LoadState':'loaded','ProtectSystem':'strict','ProtectHome':'read-only','ReadWritePaths':str(job),'PrivateMounts':'yes','PrivateNetwork':'yes','NoNewPrivileges':'yes','MemoryMax':'2684354560','MemorySwapMax':'1073741824','TasksMax':'128','CPUQuotaPerSecUSec':'1s','InvocationID':'1'*32,'MainPID':'2000','ExecStart':'fixture'}
  data={'host_critical_files':{},'host_namespaces':{n:n+':['+str(50+x)+']' for x,n in enumerate(a.NAMES)}}
  inner={'pid':1,'uid':0,'invocation_id':'1'*32,'boot_id':'22222222-2222-2222-2222-222222222222','cgroup':'0::/system.slice/'+unit,'namespaces':{n:n+':['+str(200+x)+']' for x,n in enumerate(a.NAMES)}}
  fs={'host_readonly':{p:{'vfs_readonly':True} for p in e.protected_paths(data)},'job_writable':str(job),'writable_or_unproven_host_paths':[]}
  report={'phase':'systemd','status':'passed','uid':0,'pid':2000,'application_started':False,'job':str(job),'contract_sha256':APPROVAL,'invocation_id':inner['invocation_id'],'boot_id':inner['boot_id'],'cgroup':inner['cgroup'],'namespaces':{n:n+':['+str(100+x)+']' for x,n in enumerate(a.NAMES)},'mountinfo':'fixture mount table','unit':unit,'service_properties':props,'property_errors':{},'filesystem':fs,'service_query':{'argv':i.query_argv(job)[1],'returncode':0,'stdout':'\n'.join(k+'='+v for k,v in props.items())+'\n','stderr':''}}
  envelope={'schema':1,'job':str(job),'contract_sha256':APPROVAL,'execution_nonce':NONCE,'invocation_id':inner['invocation_id'],'boot_id':inner['boot_id'],'cgroup':inner['cgroup'],'report':report}
  return report,envelope,inner,data
 def root_owner(self):
  original=os.fstat
  def info(fd):
   v=original(fd)
   return SimpleNamespace(st_mode=v.st_mode,st_uid=0,st_size=v.st_size)
  return patch.object(a.os,'fstat',side_effect=info)
 def test_failed_query_retains_stdout_stderr_and_exit_code(self):
  result=SimpleNamespace(returncode=1,stdout='partial output',stderr='transport failure')
  with patch.object(i.subprocess,'run',return_value=result) as call,self.assertRaises(i.ServiceQueryError) as found:i.service_properties(Path('/job'))
  self.assertEqual(found.exception.query['stdout'],'partial output');self.assertEqual(found.exception.query['stderr'],'transport failure');self.assertEqual(found.exception.query['returncode'],1)
  self.assertFalse(call.call_args.kwargs['check'])
 def test_query_timeout_retains_partial_output(self):
  error=subprocess.TimeoutExpired(['systemctl'],15,output=b'partial',stderr=b'timed out')
  with patch.object(i.subprocess,'run',side_effect=error),self.assertRaises(i.ServiceQueryError) as found:i.service_properties(Path('/job'))
  self.assertEqual(found.exception.query['stdout'],'partial');self.assertEqual(found.exception.query['stderr'],'timed out');self.assertIsNone(found.exception.query['returncode'])
 def test_success_query_records_raw_streams(self):
  with patch.object(i.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='ProtectSystem=strict\n',stderr='warning')):
   unit,values,query=i.service_properties(Path('/job'))
  self.assertEqual(values,{'ProtectSystem':'strict'});self.assertEqual(query['stderr'],'warning');self.assertEqual(query['returncode'],0)
 def test_query_failure_still_records_filesystem(self):
  with self.temp() as folder:
   job=Path(folder);report,envelope,current,data=self.fixture(job);error=i.ServiceQueryError('failed',report['unit'],{'argv':['systemctl'],'returncode':1,'stdout':'out','stderr':'err'})
   with patch.object(i,'runtime_context',return_value=current),patch.object(i,'service_properties',side_effect=error),patch.object(e,'filesystem_proof',return_value=report['filesystem']) as proof,self.assertRaises(ValueError):i.capture(job,data,'systemd',approval_sha256=APPROVAL)
   saved=json.loads((job/'isolation-systemd.json').read_text());self.assertEqual(saved['service_query']['stderr'],'err');self.assertIn('filesystem',saved);proof.assert_called_once()
 def test_memfd_is_immutable(self):
  with self.temp() as folder:
   job=Path(folder);report,*_=self.fixture(job);fd,digest=a.seal(report,job,APPROVAL,NONCE)
   try:
    self.assertEqual(fcntl.fcntl(fd,fcntl.F_GET_SEALS)&a.REQUIRED_SEALS,a.REQUIRED_SEALS)
    with self.assertRaises(OSError):os.write(fd,b'tamper')
   finally:os.close(fd)
 def test_unprivileged_memfd_owner_is_rejected(self):
  with self.temp() as folder:
   job=Path(folder);report,*_=self.fixture(job);fd,digest=a.seal(report,job,APPROVAL,NONCE)
   try:
    with self.assertRaisesRegex(ValueError,'owner'):a.read_sealed(fd,digest)
   finally:os.close(fd)
 def test_unsealed_memfd_is_rejected(self):
  fd=os.memfd_create('fixture',os.MFD_ALLOW_SEALING)
  try:
   os.write(fd,b'{}')
   with self.root_owner(),self.assertRaisesRegex(ValueError,'sealed'):a.read_sealed(fd,hashlib.sha256(b'{}').hexdigest())
  finally:os.close(fd)
 def test_modified_expected_digest_is_rejected(self):
  with self.temp() as folder:
   job=Path(folder);report,*_=self.fixture(job);fd,digest=a.seal(report,job,APPROVAL,NONCE)
   try:
    with self.root_owner(),self.assertRaisesRegex(ValueError,'digest'):a.read_sealed(fd,'0'*64)
   finally:os.close(fd)
 def test_complete_sealed_handoff_is_accepted(self):
  with self.temp() as folder:
   job=Path(folder);report,envelope,current,data=self.fixture(job);fd,digest=a.seal(report,job,APPROVAL,NONCE)
   try:
    with self.root_owner():received=a.read_sealed(fd,digest)
    self.assertEqual(a.verify(received,job,APPROVAL,NONCE,current,data),report)
   finally:os.close(fd)
 def test_other_job_contract_nonce_and_execution_are_rejected(self):
  with self.temp() as folder:
   job=Path(folder);report,envelope,current,data=self.fixture(job)
   for key in ('job','contract_sha256','execution_nonce','invocation_id','boot_id','cgroup'):
    bad=copy.deepcopy(envelope);bad[key]='other'
    with self.subTest(key=key),self.assertRaises(ValueError):a.verify(bad,job,APPROVAL,NONCE,current,data)
 def test_absent_or_incomplete_external_evidence_is_rejected(self):
  with self.temp() as folder:
   job=Path(folder);report,envelope,current,data=self.fixture(job)
   for key in envelope:
    bad=copy.deepcopy(envelope);del bad[key]
    with self.subTest(key=key),self.assertRaises(ValueError):a.verify(bad,job,APPROVAL,NONCE,current,data)
   for key in report:
    bad=copy.deepcopy(envelope);del bad['report'][key]
    with self.subTest(report_key=key),self.assertRaises(ValueError):a.verify(bad,job,APPROVAL,NONCE,current,data)
 def test_failed_external_status_is_not_trusted(self):
  with self.temp() as folder:
   job=Path(folder);report,envelope,current,data=self.fixture(job);envelope['report']['status']='blocked'
   with self.assertRaises(ValueError):a.verify(envelope,job,APPROVAL,NONCE,current,data)
 def test_missing_or_writable_home_in_external_evidence_is_rejected(self):
  with self.temp() as folder:
   job=Path(folder);report,envelope,current,data=self.fixture(job)
   for mutate in ('missing','writable'):
    bad=copy.deepcopy(envelope)
    if mutate=='missing':del bad['report']['filesystem']['host_readonly']['/home']
    else:bad['report']['filesystem']['host_readonly']['/home']['vfs_readonly']=False
    with self.subTest(mutate=mutate),self.assertRaises(ValueError):a.verify(bad,job,APPROVAL,NONCE,current,data)
 def test_raw_stdout_must_match_effective_properties(self):
  with self.temp() as folder:
   job=Path(folder);report,envelope,current,data=self.fixture(job);envelope['report']['service_query']['stdout']='ProtectHome=no\n'
   with self.assertRaises(ValueError):a.verify(envelope,job,APPROVAL,NONCE,current,data)
 def test_namespace_must_differ_from_outer_and_host(self):
  with self.temp() as folder:
   job=Path(folder);report,envelope,current,data=self.fixture(job)
   for source in (report['namespaces'],data['host_namespaces']):
    bad=copy.deepcopy(current);bad['namespaces']['pid']=source['pid']
    with self.assertRaises(ValueError):a.verify(envelope,job,APPROVAL,NONCE,bad,data)
 def test_regular_job_file_is_not_an_attestation(self):
  with self.temp() as folder:
   path=Path(folder)/'fake';path.write_text('{}');fd=os.open(path,os.O_RDONLY)
   try:
    with self.root_owner(),self.assertRaises(ValueError):a.read_sealed(fd,hashlib.sha256(b'{}').hexdigest())
   finally:os.close(fd)
 def test_no_fallback_to_modifiable_job_report(self):
  with self.temp() as folder:
   job=Path(folder);report,envelope,current,data=self.fixture(job);(job/'isolation-systemd.json').write_text(json.dumps(report))
   with patch.object(i,'runtime_context',return_value=current),patch.object(i,'service_properties') as service,patch.object(e,'filesystem_proof',return_value=report['filesystem']) as proof,self.assertRaises(ValueError):i.capture(job,data,'unshare',approval_sha256=APPROVAL)
   service.assert_not_called();proof.assert_called_once()
 def test_inner_capture_never_queries_systemctl(self):
  with self.temp() as folder:
   job=Path(folder);report,envelope,current,data=self.fixture(job);fd,digest=a.seal(report,job,APPROVAL,NONCE)
   try:
    with self.root_owner(),patch.object(i,'runtime_context',return_value=current),patch.object(i,'service_properties',side_effect=AssertionError('must not query internal bus')),patch.object(e,'filesystem_proof',return_value=report['filesystem']) as proof:
     result=i.capture(job,data,'unshare',approval_sha256=APPROVAL,inherited={'fd':fd,'sha256':digest,'nonce':NONCE})
    self.assertEqual(result['properties_source'],'verified_sealed_external_memfd');proof.assert_called_once()
   finally:os.close(fd)
 def test_inner_vfs_failure_blocks_valid_attestation(self):
  with self.temp() as folder:
   job=Path(folder);report,envelope,current,data=self.fixture(job);fd,digest=a.seal(report,job,APPROVAL,NONCE)
   try:
    with self.root_owner(),patch.object(i,'runtime_context',return_value=current),patch.object(e,'filesystem_proof',side_effect=e.FilesystemIsolationError('writable',{'path':'/home'})),self.assertRaises(ValueError):i.capture(job,data,'unshare',approval_sha256=APPROVAL,inherited={'fd':fd,'sha256':digest,'nonce':NONCE})
   finally:os.close(fd)
 def test_launcher_passes_only_immutable_descriptor_and_closes_it(self):
  job=ROOT/'work/release-test';report,*_=self.fixture(job);saved=[]
  def child(args,**kwargs):
   fd=kwargs['pass_fds'][0];saved.append(fd)
   self.assertEqual(fcntl.fcntl(fd,fcntl.F_GET_SEALS)&a.REQUIRED_SEALS,a.REQUIRED_SEALS);self.assertIn('--external-evidence-sha256',args);return 0
  argv=['entry','--job',str(job),'--approval-sha256',APPROVAL,'--execute-authorized','--',*e.namespace_command(job,APPROVAL)]
  with patch('sys.argv',argv),patch.object(e.os,'geteuid',return_value=0),patch.object(e,'read',return_value=(job,{})),patch.object(i,'capture',return_value=report),patch.object(e.subprocess,'call',side_effect=child),self.assertRaises(SystemExit) as result:runpy.run_path(str(ROOT/'scripts/iniciar-publico-isolado-root.py'),run_name='__main__')
  self.assertEqual(result.exception.code,0)
  with self.assertRaises(OSError):os.fstat(saved[0])

 def test_missing_systemctl_records_local_os_error(self):
  with patch.object(i.subprocess,'run',side_effect=FileNotFoundError(2,'missing')),self.assertRaises(i.ServiceQueryError) as found:i.service_properties(Path('/job'))
  self.assertIsNone(found.exception.query['returncode']);self.assertEqual(found.exception.query['exception_type'],'FileNotFoundError')
 def diagnostic_fixture(self,job):
  images={}
  for name in ('base','live'):
   path=job/(name+'.ext4');path.write_bytes(name.encode());path.chmod(0o600)
   images[name]={'file':str(path),'bytes':len(name),'sha256':hashlib.sha256(name.encode()).hexdigest()}
  data={'source_job_sha256':'f'*64,'source_images':images}
  receipt={'job_sha256':'f'*64,'results':{n:{'image':v} for n,v in images.items()}}
  original=Path.stat
  def root_image_stat(path,*args,**kwargs):
   value=original(path,*args,**kwargs)
   if str(path) in {v['file'] for v in images.values()}:return SimpleNamespace(st_uid=0,st_size=value.st_size,st_mode=value.st_mode)
   return value
  return data,receipt,root_image_stat
 def test_readonly_diagnostic_preserves_query_error_and_image_bytes(self):
  with self.temp() as folder:
   job=Path(folder);data,receipt,info=self.diagnostic_fixture(job)
   query={'argv':['systemctl'],'returncode':1,'stdout':'partial','stderr':'original transport error'}
   error=i.ServiceQueryError('failed','unit',query)
   with patch.object(e,'accepted_pair',return_value=receipt),patch.object(Path,'stat',info),patch.object(i,'service_properties',side_effect=error),patch.object(e,'apply') as application:
    output=e.diagnostic(job,data,{'external_attestation_sha256':'a'*64})
   result=json.loads(output.read_text());self.assertEqual(result['status'],'diagnostic_completed')
   self.assertEqual(result['legacy_internal_systemctl']['query']['stderr'],'original transport error')
   self.assertTrue(result['source_images_verified']);application.assert_not_called()
   for name in ('base','live'):self.assertEqual((job/(name+'.ext4')).read_bytes(),name.encode())
   self.assertFalse((job/'attempt').exists())
 def test_readonly_diagnostic_blocks_changed_image(self):
  with self.temp() as folder:
   job=Path(folder);data,receipt,info=self.diagnostic_fixture(job);(job/'base.ext4').write_bytes(b'xxxx')
   error=i.ServiceQueryError('failed','unit',{'argv':[],'returncode':1,'stdout':'','stderr':'error'})
   with patch.object(e,'accepted_pair',return_value=receipt),patch.object(Path,'stat',info),patch.object(i,'service_properties',side_effect=error),self.assertRaisesRegex(ValueError,'integrity'):e.diagnostic(job,data,{'external_attestation_sha256':'a'*64})
   self.assertEqual(json.loads((job/'isolation-diagnostic-result.json').read_text())['status'],'blocked')
