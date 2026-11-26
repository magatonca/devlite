import json,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from v5.devcontrol import services as m
class FakeManager:
 def __init__(self):self.calls=[];self.states={u:{'LoadState':'loaded','ActiveState':'inactive','SubState':'dead','UnitFileState':'disabled'} for u in ['apache2.service','mariadb.service','docker.service','docker.socket','containerd.service','ssh.service','ssh.socket']};self.fail=None
 def __call__(self,argv,**kwargs):
  assert kwargs['shell'] is False;self.calls.append(argv);verb=argv[2]
  if verb=='show':return subprocess.CompletedProcess(argv,0,'\n'.join(k+'='+v for k,v in self.states.get(argv[3],{'LoadState':'not-found'}).items()),'')
  if self.fail==verb:return subprocess.CompletedProcess(argv,1,'','test failure')
  for u in argv[4:]:
   if verb in ('start','restart'):self.states[u]['ActiveState']='active'
   if verb=='stop':self.states[u]['ActiveState']='inactive'
   if verb in ('enable','disable'):self.states[u]['UnitFileState']='enabled' if verb=='enable' else 'disabled'
  return subprocess.CompletedProcess(argv,0,'','')
class ServiceTests(unittest.TestCase):
 def run_action(self,action,key,f):
  with patch.object(m.os,'geteuid',return_value=0),patch.object(m,'identity'):return m.admin(action,key,runner=f)
 def test_nonroot_never_reaches_manager(self):
  f=FakeManager()
  with patch.object(m.os,'geteuid',return_value=1000),self.assertRaises(m.ServiceError):m.admin('start','apache',runner=f)
  self.assertFalse(f.calls)
 def test_invalid_actions_and_units_never_mutate(self):
  for a,k in [('reboot','apache'),('start','../../evil'),('start;reboot','ssh'),('start','php:9;evil'),('start','openvpn:../../evil')]:
   f=FakeManager()
   with self.assertRaises(m.ServiceError):self.run_action(a,k,f)
   self.assertFalse(f.calls)
 def test_start_docker_starts_runtime_then_service(self):
  f=FakeManager();self.run_action('start','docker',f)
  ops=[x for x in f.calls if x[2]!='show'];self.assertEqual([x[4:] for x in ops],[['containerd.service'],['docker.service']])
  self.assertFalse(any(x[2] in ('mask','unmask','enable') for x in f.calls))
 def test_stop_docker_closes_socket_without_stopping_shared_containerd(self):
  f=FakeManager();f.states['containerd.service']['ActiveState']='active';self.run_action('stop','docker',f)
  self.assertEqual(next(x for x in f.calls if x[2]=='stop')[4:],['docker.socket','docker.service']);self.assertEqual(f.states['containerd.service']['ActiveState'],'active')
 def test_disable_docker_no_now_or_runtime_changes(self):
  f=FakeManager();f.states['docker.service']['ActiveState']='active';self.run_action('disable','docker',f)
  self.assertEqual(f.states['docker.service']['ActiveState'],'active');self.assertFalse(any('--now' in x for x in f.calls));self.assertEqual(next(x for x in f.calls if x[2]=='disable')[4:],['docker.service','docker.socket'])
 def test_ssh_stop_and_disable_include_socket(self):
  for a in ('stop','disable'):
   f=FakeManager();self.run_action(a,'ssh',f);self.assertIn('ssh.socket',next(x for x in f.calls if x[2]==a))
 def test_masks_rejected_never_removed(self):
  f=FakeManager();f.states['containerd.service']['LoadState']='masked'
  with self.assertRaises(m.ServiceError):self.run_action('start','docker',f)
  self.assertTrue(all(x[2]=='show' for x in f.calls))
 def test_failure_does_not_remask_or_kill_shared_services(self):
  f=FakeManager();f.fail='start'
  with self.assertRaises(m.ServiceError):self.run_action('start','docker',f)
  self.assertFalse(any(x[2] in ('mask','unmask','stop') for x in f.calls))
 def test_absent_php_cli_is_not_fpm(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t);(r/'var/lib/dpkg').mkdir(parents=True);(r/'var/lib/dpkg/status').write_text('Package: php8.3-cli\nStatus: install ok installed\n\n')
   self.assertFalse(any(x['id'].startswith('php:') for x in m.catalog(r)))
 def test_fpm_requires_installed_package(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t);(r/'var/lib/dpkg').mkdir(parents=True);(r/'var/lib/dpkg/status').write_text('Package: php8.3-fpm\nStatus: install ok installed\n\n')
   self.assertEqual(m.resolve('php:8.3',r),'php8.3-fpm.service')
 def test_openvpn_untrusted_and_path_names_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t);(r/'etc/openvpn/client').mkdir(parents=True);(r/'etc/openvpn/client/demo.conf').write_text('')
   self.assertFalse(any(x['id'].startswith('openvpn:') for x in m.catalog(r)))
 def test_timeout_is_reported(self):
  def runner(*a,**k):raise subprocess.TimeoutExpired(a[0],90)
  self.assertIn('error',m.query('apache2.service',runner))

class DeadlineTests(unittest.TestCase):
 def test_admin_deadline_exhaustion_does_not_start_services(self):
  f=FakeManager()
  with patch.object(m.os,'geteuid',return_value=0),patch.object(m,'identity'),patch.object(m.time,'monotonic',side_effect=[0,121]):
   with self.assertRaises(m.ServiceError):m.admin('start','apache',runner=f)
  self.assertFalse(f.calls)
