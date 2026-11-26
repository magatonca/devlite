"""ProtectSystem/ProtectHome regression, simulated service and mount evidence."""
import copy,json,os,runpy,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from pipeline.devlite import public_execution as e,public_isolation as i
ROOT=Path(__file__).resolve().parents[1]
class HomeIsolationTests(unittest.TestCase):
 def setUp(self):
  env=patch.dict(os.environ,{'INVOCATION_ID':'1'*32});env.start();self.addCleanup(env.stop)
 def temp(self):return tempfile.TemporaryDirectory(dir=ROOT/'work')
 def properties(self,job):
  return {'LoadState':'loaded','ProtectSystem':'strict','ProtectHome':'read-only','ReadWritePaths':str(job),'PrivateMounts':'yes','PrivateNetwork':'yes','NoNewPrivileges':'yes','MemoryMax':'2684354560','MemorySwapMax':'1073741824','TasksMax':'128','CPUQuotaPerSecUSec':'1s','InvocationID':'1'*32,'MainPID':str(os.getpid())}
 def procinfo(self):
  return '1 0 8:1 / / ro - ext4 /dev/fake ro\n2 1 8:1 /home /home rw - ext4 /dev/fake rw\n3 1 8:1 /job /job rw - ext4 /dev/fake rw\n'
 def capture(self,job,phase='systemd'):
  with patch.object(i,'service_properties',return_value=('unit.service',self.properties(job),{'returncode':0,'stdout':'','stderr':''})),patch.object(e,'filesystem_proof',return_value={'host_readonly':{},'job_writable':str(job)}):return i.capture(job,{'host_critical_files':{}},phase,approval_sha256='a'*64)

 def test_command_adds_protect_home_without_dropping_strict(self):
  args=e.command(ROOT/'work/release-test','a'*64)
  self.assertIn('--property=ProtectSystem=strict',args);self.assertIn('--property=ProtectHome=read-only',args)

 def test_single_write_exception_stays_exactly_job(self):
  job=ROOT/'work/release-test';args=e.command(job,'a'*64)
  self.assertEqual([x for x in args if x.startswith('--property=ReadWritePaths=')],['--property=ReadWritePaths='+str(job)])

 def test_unshare_options_preserved_after_diagnostic_entry(self):
  job=ROOT/'work/release-test';args=e.command(job,'a'*64)
  self.assertEqual(args[args.index('--')+1:],e.namespace_command(job,'a'*64))
  self.assertIn('--mount',args);self.assertIn('--propagation',args);self.assertIn('private',args)

 def test_strict_without_home_protection_remains_blocked(self):
  def statvfs(path):
   writable=str(path).startswith(('/home','/root','/run/user')) or str(path)=='/job'
   return SimpleNamespace(f_flag=0 if writable else os.ST_RDONLY)
  with patch.object(e.os,'statvfs',side_effect=statvfs),self.assertRaises(e.FilesystemIsolationError) as found:e.filesystem_proof(self.procinfo(),Path('/job'))
  failed=found.exception.evidence['writable_or_unproven_host_paths']
  self.assertIn(str(ROOT),failed);self.assertIn(str(e.SOURCE),failed);self.assertIn('/home',failed)

 def test_protected_home_with_writable_job_passes(self):
  with patch.object(e.os,'statvfs',side_effect=lambda p:SimpleNamespace(f_flag=0 if str(p)=='/job' else os.ST_RDONLY)):
   result=e.filesystem_proof(self.procinfo(),Path('/job'))
  self.assertEqual(result['writable_or_unproven_host_paths'],[])

 def test_collected_service_defaults_are_not_accepted_as_effective(self):
  job=Path('/job');values=self.properties(job);values.update(LoadState='not-found',ProtectSystem='no')
  errors=i.property_errors(values,job)
  self.assertIn('LoadState',errors);self.assertIn('ProtectSystem',errors)

 def test_extra_write_path_is_rejected(self):
  job=Path('/job');values=self.properties(job);values['ReadWritePaths']='/job /other'
  self.assertIn('ReadWritePaths',i.property_errors(values,job))

 def test_missing_home_protection_is_rejected(self):
  job=Path('/job');values=self.properties(job);values['ProtectHome']='no'
  self.assertIn('ProtectHome',i.property_errors(values,job))

 def test_captures_external_mounts_and_rejects_missing_inner_attestation(self):
  with self.temp() as folder:
   job=Path(folder);self.capture(job,'systemd')
   saved=json.loads((job/'isolation-systemd.json').read_text())
   self.assertEqual(saved['status'],'passed');self.assertEqual(saved['service_properties']['ProtectHome'],'read-only')
   with self.assertRaisesRegex(ValueError,'attestation'):self.capture(job,'unshare')
   blocked=json.loads((job/'isolation-unshare.json').read_text())
   self.assertEqual(blocked['status'],'blocked');self.assertIn('filesystem',blocked)

 def test_failure_persists_exact_writable_paths(self):
  with self.temp() as folder:
   job=Path(folder);detail={'writable_or_unproven_host_paths':[str(ROOT)],'host_readonly':{str(ROOT):{'vfs_readonly':False}}}
   with patch.object(i,'service_properties',return_value=('unit.service',self.properties(job),{'returncode':0,'stdout':'','stderr':''})),patch.object(e,'filesystem_proof',side_effect=e.FilesystemIsolationError('Host filesystem is not read-only',detail)),self.assertRaises(ValueError):i.capture(job,{'host_critical_files':{}},'systemd',approval_sha256='a'*64)
   report=json.loads((job/'isolation-systemd.json').read_text())
   self.assertEqual(report['filesystem'],detail);self.assertEqual(report['status'],'blocked');self.assertFalse((job/'attempt').exists())

 def test_property_mismatch_also_persisted(self):
  with self.temp() as folder:
   job=Path(folder);values=self.properties(job);values['ReadWritePaths']='/wrong'
   with patch.object(i,'service_properties',return_value=('unit.service',values,{'returncode':0,'stdout':'','stderr':''})),patch.object(e,'filesystem_proof',return_value={}),self.assertRaises(ValueError):i.capture(job,{'host_critical_files':{}},'systemd',approval_sha256='a'*64)
   self.assertIn('ReadWritePaths',json.loads((job/'isolation-systemd.json').read_text())['property_errors'])

 def test_does_not_overwrite_previous_evidence(self):
  with self.temp() as folder:
   job=Path(folder);path=job/'isolation-systemd.json';path.write_text('preserve')
   with self.assertRaises(ValueError):self.capture(job)
   self.assertEqual(path.read_text(),'preserve')

 def test_entry_does_not_enter_namespaces_if_preflight_blocks(self):
  job=ROOT/'work/release-test';approval='a'*64;argv=['entry','--job',str(job),'--approval-sha256',approval,'--execute-authorized','--',*e.namespace_command(job,approval)]
  with patch('sys.argv',argv),patch.object(e.os,'geteuid',return_value=0),patch.object(e,'read',return_value=(job,{})),patch.object(i,'capture',side_effect=ValueError('blocked')),patch.object(e.subprocess,'call') as child,self.assertRaises(SystemExit):runpy.run_path(str(ROOT/'scripts/iniciar-publico-isolado-root.py'),run_name='__main__')
  child.assert_not_called()

 def test_entry_rejects_unsealed_namespace_command(self):
  job=ROOT/'work/release-test';argv=['entry','--job',str(job),'--approval-sha256','a'*64,'--execute-authorized','--','/bin/true']
  with patch('sys.argv',argv),patch.object(e.os,'geteuid',return_value=0),patch.object(e,'read',return_value=(job,{})),patch.object(i,'capture') as capture,patch.object(e.subprocess,'call') as child,self.assertRaises(SystemExit):runpy.run_path(str(ROOT/'scripts/iniciar-publico-isolado-root.py'),run_name='__main__')
  child.assert_not_called();capture.assert_not_called()
