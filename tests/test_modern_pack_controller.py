import importlib.util,unittest
from pathlib import Path
from unittest.mock import patch
R=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('modern_pack_control_test',R/'scripts/empacotar-modern-isolado.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class ModernPackControllerTests(unittest.TestCase):
 def test_storage_keeps_twenty_gib_reserve(self):
  self.assertEqual(m.storage_required(0,0),20*1024**3)
  self.assertGreater(m.storage_required(4*1024**3,6*1024**3),3*4*1024**3+5*6*1024**3+10*1024**3)
 def test_explicit_approval_required_before_job_access(self):
  with self.assertRaises(ValueError):m.run(None,None,False)
 def test_root_cannot_prepare(self):
  with patch.object(m.os,'geteuid',return_value=0):
   with self.assertRaises(ValueError):m.prepare()
 def test_root_command_confines_job_and_retains_limits(self):
  job=R/'work/modern-pack-test';cmd=m.command(job,'a'*64)
  self.assertIn(str(R/m.ENTRY),cmd)
  self.assertNotIn(str(R/m.app.ENTRY),cmd)
  self.assertEqual([x for x in cmd if x.startswith('--property=ReadWritePaths=')],['--property=ReadWritePaths='+str(job)])
  for prop in ['--property=ProtectSystem=strict','--property=ProtectHome=read-only','--property=PrivateNetwork=yes','--property=MemoryMax=2684354560','--property=CPUQuota=100%']:self.assertIn(prop,cmd)
  cap=next(x for x in cmd if x.startswith('--property=CapabilityBoundingSet='))
  self.assertIn('CAP_MKNOD',cap);self.assertIn('CAP_SETFCAP',cap)

 def test_browser_lock_requires_accepted_digest_chain(self):
  with patch.object(m.app.review.legacy,'load',side_effect=[{'contract_sha256':'a'*64},{'plan_sha256':'b'*64},{'targets':{}}]) as loader:
   self.assertEqual(m.locked_browser_plan(),{'targets':{}})
   self.assertEqual(loader.call_args_list[1].args[1],'a'*64)
   self.assertEqual(loader.call_args_list[2].args[1],'b'*64)
