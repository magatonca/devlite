"""Offline public application fixtures: no root execution, mounts or programs."""
import copy,hashlib,json,os,stat,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from pipeline.devlite import public_apply as a,public_execution as e
from pipeline.devlite.minimal_root import EPOCH
ROOT=Path(__file__).resolve().parents[1]
class PublicApplicationTests(unittest.TestCase):
 def temp(self):return tempfile.TemporaryDirectory(dir=ROOT/'work')
 def fixture(self,root):
  tree=root/'payload';(tree/'opt').mkdir(parents=True);(tree/'opt/tool').write_bytes(b'data')
  manifest={'opt':{'type':'dir','mode':'0755','uid':0,'gid':0},'opt/tool':{'type':'file','mode':'0755','uid':0,'gid':0,'sha256':hashlib.sha256(b'data').hexdigest(),'size':4}}
  return tree,manifest
 def records(self):
  original={'.':{'type':'dir','mode':0o755,'uid':0,'gid':0,'mtime':1,'xattrs':{}}}
  manifest={'tool':{'type':'file','mode':'0755','uid':0,'gid':0,'size':4,'sha256':'a'*64}}
  after=copy.deepcopy(original);after['tool']={'type':'file','mode':0o755,'uid':0,'gid':0,'mtime':EPOCH,'xattrs':{},'size':4,'sha256':'a'*64,'hardlinks':['tool']}
  return original,after,manifest

 def test_valid_payload(self):
  with self.temp() as folder:
   tree,manifest=self.fixture(Path(folder));a.validate_payload(tree,manifest)

 def test_payload_traversal_blocked(self):
  with self.temp() as folder:
   tree,manifest=self.fixture(Path(folder));manifest['../escape']=manifest.pop('opt/tool')
   with self.assertRaises(ValueError):a.validate_payload(tree,manifest)

 def test_payload_file_tampering_blocked(self):
  with self.temp() as folder:
   tree,manifest=self.fixture(Path(folder));(tree/'opt/tool').write_bytes(b'tampered')
   with self.assertRaises(ValueError):a.validate_payload(tree,manifest)

 def test_payload_extra_entries_blocked(self):
  with self.temp() as folder:
   tree,manifest=self.fixture(Path(folder));(tree/'extra').write_text('extra')
   with self.assertRaises(ValueError):a.validate_payload(tree,manifest)

 def test_payload_external_hardlink_blocked(self):
  with self.temp() as folder:
   root=Path(folder);tree,manifest=self.fixture(root);os.link(tree/'opt/tool',root/'outside')
   with self.assertRaises(ValueError):a.validate_payload(tree,manifest)

 def test_payload_escaping_symlink_blocked(self):
  with self.temp() as folder:
   root=Path(folder);tree,manifest=self.fixture(root);(tree/'opt/tool').unlink();(tree/'opt/tool').symlink_to('/etc/passwd')
   manifest['opt/tool']={'type':'symlink','target':'/etc/passwd','mode':'0777','uid':0,'gid':0}
   with self.assertRaises(ValueError):a.validate_payload(tree,manifest)

 def test_existing_file_collision_blocks_before_copy(self):
  with self.temp() as folder:
   root=Path(folder);tree,manifest=self.fixture(root);target=root/'rootfs';(target/'opt').mkdir(parents=True);(target/'opt/tool').write_text('preserve')
   with self.assertRaisesRegex(ValueError,'Existing destination'):a.copy_payload(target,tree,manifest)
   self.assertEqual((target/'opt/tool').read_text(),'preserve')

 def test_destination_symlink_ancestor_blocks(self):
  with self.temp() as folder:
   root=Path(folder);tree,manifest=self.fixture(root);target=root/'rootfs';target.mkdir();outside=root/'outside';outside.mkdir();(target/'opt').symlink_to(outside)
   with self.assertRaises(Exception):a.copy_payload(target,tree,manifest)
   self.assertEqual(list(outside.iterdir()),[])

 def test_copy_restores_existing_directory_nanosecond_timestamps(self):
  with self.temp() as folder:
   root=Path(folder);tree,manifest=self.fixture(root);target=root/'rootfs';(target/'opt').mkdir(parents=True)
   times=(1780000000123456789,1780000000987654321);os.utime(target/'opt',ns=times)
   with patch.object(a.os,'chown'):a.copy_payload(target,tree,manifest)
   self.assertEqual((target/'opt/tool').read_bytes(),b'data')
   self.assertEqual((target/'opt').stat().st_mtime_ns,times[1])
   self.assertEqual(int((target/'opt/tool').stat().st_mtime),EPOCH)
   self.assertEqual(stat.S_IMODE((target/'opt/tool').stat().st_mode),0o755)

 def test_accepts_only_declared_additions(self):
  before,after,manifest=self.records();a.check_changes(before,after,manifest)

 def test_existing_metadata_change_blocks(self):
  before,after,manifest=self.records();after['.']['mtime']=3
  with self.assertRaisesRegex(ValueError,'Existing'):a.check_changes(before,after,manifest)

 def test_undeclared_new_entry_blocks(self):
  before,after,manifest=self.records();after['unexpected']=after['tool']
  with self.assertRaisesRegex(ValueError,'Unexpected'):a.check_changes(before,after,manifest)

 def test_wrong_owner_mode_xattr_or_digest_blocks(self):
  for field,value in [('uid',1000),('gid',1000),('mode',0o4755),('xattrs',{'user.extra':'x'}),('sha256','b'*64),('hardlinks',['tool','other'])]:
   with self.subTest(field=field):
    before,after,manifest=self.records();after['tool'][field]=value
    with self.assertRaises(ValueError):a.check_changes(before,after,manifest)

 def test_private_gate_does_not_change_host_config(self):
  with self.temp() as folder:
   root=Path(folder);config=root/'host.json';config.write_text('{"integracao_camadas_autorizada": false}\n');original=config.read_bytes()
   e.private_gate(config,root/'private.json')
   self.assertEqual(config.read_bytes(),original)
   self.assertTrue(json.loads((root/'private.json').read_text())['integracao_camadas_autorizada'])

 def test_existing_private_gate_fails_without_host_change(self):
  with self.temp() as folder:
   root=Path(folder);config=root/'host.json';config.write_text('{"integracao_camadas_autorizada": false}\n');gate=root/'gate.json';gate.write_text('preserve')
   with self.assertRaises(FileExistsError):e.private_gate(config,gate)
   self.assertFalse(json.loads(config.read_text())['integracao_camadas_autorizada']);self.assertEqual(gate.read_text(),'preserve')

 def test_command_limits_network_pid_and_write_scope(self):
  job=ROOT/'work/release-fixture';args=e.command(job,'a'*64)
  for value in ('--property=MemoryMax=2684354560','--property=MemorySwapMax=1073741824','--property=CPUQuota=100%','--property=TasksMax=128','--property=RuntimeMaxSec=10800','--property=ProtectSystem=strict','--property=ReadWritePaths='+str(job),'--property=PrivateNetwork=yes','--property=NoNewPrivileges=yes','--pid','--net','--mount-proc'):self.assertIn(value,args)
  self.assertEqual(sum(x.startswith('--property=ReadWritePaths=') for x in args),1)
  self.assertNotIn('chroot',args)

 def test_root_run_requires_specific_authorization(self):
  with patch.object(e,'read') as reader,self.assertRaises(ValueError):e.run(ROOT/'work/release-fixture','a'*64,False)
  reader.assert_not_called()

 def test_root_run_requires_root(self):
  with patch.object(e.os,'geteuid',return_value=1000),patch.object(e,'read') as reader,self.assertRaises(ValueError):e.run(ROOT/'work/release-fixture','a'*64,True)
  reader.assert_not_called()

 def test_root_run_requires_private_namespaces_before_mounts(self):
  data={'host_namespaces':{name:os.readlink('/proc/self/ns/'+name) for name in ('mnt','pid','net','ipc','uts')}}
  with patch.object(e.os,'geteuid',return_value=0),patch.object(e.os,'getpid',return_value=1),patch.object(e,'read',return_value=(ROOT/'work/release-fixture',data)),self.assertRaisesRegex(ValueError,'Private namespaces'):e.run(ROOT/'work/release-fixture','a'*64,True)

 def test_components_are_versioned_without_dpkg_claims(self):
  plan=json.loads((ROOT/'packages/final-external-plan.json').read_text());value=e.component_manifest(plan)
  self.assertEqual(len(value['components']),3);self.assertIn('not dpkg',value['package_manager'])
  self.assertEqual(value['components'][0]['version'],'26.13.1');self.assertEqual(value['components'][1]['version'],'7.0.2')

 def test_tree_digest_is_order_independent(self):
  self.assertEqual(a.tree_digest({'a':1,'b':2}),a.tree_digest({'b':2,'a':1}))

 def test_mount_flags_choose_specific_mount(self):
  info='1 0 8:1 / / ro - ext4 /dev/fake ro\n2 1 8:1 /job /job rw - ext4 /dev/fake rw\n'
  self.assertIn('ro',e.filesystem_flags(info,'/etc/passwd'));self.assertIn('rw',e.filesystem_flags(info,'/job/file'))

 def test_missing_mount_evidence_blocks(self):
  with self.assertRaises(ValueError):e.filesystem_flags('','/job')

 def test_filesystem_proof_requires_kernel_readonly_host(self):
  from types import SimpleNamespace
  job=Path('/job');info='1 0 8:1 / / ro - ext4 /dev/fake ro\n2 1 8:1 /job /job rw - ext4 /dev/fake rw\n'
  with patch.object(e.os,'statvfs',side_effect=lambda p:SimpleNamespace(f_flag=0 if Path(p)==job else os.ST_RDONLY)):
   proof=e.filesystem_proof(info,job)
  self.assertEqual(proof['job_writable'],'/job')
  self.assertTrue(all(v['vfs_readonly'] for v in proof['host_readonly'].values()))

 def test_writable_host_fails_even_if_mountinfo_claims_readonly(self):
  from types import SimpleNamespace
  with patch.object(e.os,'statvfs',return_value=SimpleNamespace(f_flag=0)),self.assertRaisesRegex(ValueError,'read-only'):
   e.filesystem_proof('1 0 8:1 / / ro - ext4 /dev/fake ro\n',Path('/job'))
