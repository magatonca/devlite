"""Cleanup safety fixtures; no deletion of real artifacts."""
import hashlib,json,os,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from pipeline.devlite import final_cleanup as c
ROOT=Path(__file__).resolve().parents[1]
class CleanupTests(unittest.TestCase):
 def temp(self):return tempfile.TemporaryDirectory(dir=ROOT/'work')

 def test_external_hardlink_blocks_before_deletion(self):
  with self.temp() as folder:
   r=Path(folder);target=r/'target';target.mkdir();(target/'file').write_text('data');os.link(target/'file',r/'preserve')
   with self.assertRaisesRegex(ValueError,'hardlink'):c.inventory([target])
   self.assertTrue((r/'preserve').exists())

 def test_internal_hardlinks_counted_once(self):
  with self.temp() as folder:
   r=Path(folder);(r/'a').write_bytes(b'a'*8192);os.link(r/'a',r/'b')
   rows,size=c.inventory([r])
   self.assertEqual(len(rows),3);self.assertEqual(size,r.stat().st_blocks*512+(r/'a').stat().st_blocks*512)

 def test_root_symlink_rejected(self):
  with self.temp() as folder:
   r=Path(folder);(r/'real').mkdir();(r/'link').symlink_to(r/'real',target_is_directory=True)
   with self.assertRaisesRegex(ValueError,'symlink'):c.inventory([r/'link'])

 def test_mutation_blocks_removal(self):
  with self.temp() as folder:
   r=Path(folder);target=r/'target';target.mkdir();(target/'file').write_text('before')
   rows,_=c.inventory([target]);(target/'file').write_text('after')
   with self.assertRaisesRegex(ValueError,'changed'):c.delete_paths([target],rows)
   self.assertTrue(target.exists())

 def test_fixture_removal_does_not_follow_inner_symlink(self):
  with self.temp() as folder:
   r=Path(folder);target=r/'target';target.mkdir();(r/'preserved').write_text('preserved');(target/'link').symlink_to(r/'preserved')
   rows,_=c.inventory([target]);self.assertEqual(c.delete_paths([target],rows),[str(target)])
   self.assertEqual((r/'preserved').read_text(),'preserved')

 def test_plan_rejects_unreviewed_path_even_with_valid_hash(self):
  with self.temp() as folder:
   path=Path(folder)/'plan.json';path.write_text(json.dumps({'candidates':[{'path':'/etc'}]}))
   with self.assertRaisesRegex(ValueError,'exact'):c.validate_plan(path,c.digest(path))

 def test_loop_reference_blocks(self):
  result=SimpleNamespace(stdout=json.dumps({'loopdevices':[{'back-file':'/candidate/base.ext4'}]}))
  with patch.object(c.subprocess,'run',return_value=result):
   with self.assertRaisesRegex(ValueError,'loop'):c.resources_clear([Path('/candidate')])

 def test_active_job_blocks(self):
  replies=[SimpleNamespace(stdout='{"loopdevices":[]}'),SimpleNamespace(stdout='[{"active":"active"}]')]
  with patch.object(c.subprocess,'run',side_effect=replies):
   with self.assertRaisesRegex(ValueError,'Active'):c.resources_clear([Path('/candidate')])

class ProcessInspectionTests(unittest.TestCase):
 def temp(self):return tempfile.TemporaryDirectory(dir=ROOT/'work')
 def fixture(self,root):
  proc=root/'proc';process=proc/'112774';(process/'fd').mkdir(parents=True)
  (process/'stat').write_text('112774 (temporary reader (worker)) '+' '.join(['S']+['0']*18+['77'])+'\n')
  (process/'mountinfo').write_text('1 0 8:1 / / rw - ext4 /dev/fake rw\n')
  (process/'cwd').symlink_to('/safe');(process/'root').symlink_to('/')
  return proc,process
 def commands(self):
  return patch.object(c.subprocess,'run',side_effect=[SimpleNamespace(stdout='{"loopdevices":[]}'),SimpleNamespace(stdout='[]')])
 def inspect(self,proc,evidence):
  with self.commands():c.resources_clear([Path('/candidate')],evidence,proc_root=proc)

 def test_active_reference_reports_pid_name_path_and_type(self):
  for kind in ('cwd','root','fd'):
   with self.subTest(kind=kind),self.temp() as folder:
    proc,process=self.fixture(Path(folder));link=process/'fd/7' if kind=='fd' else process/kind
    if link.is_symlink():link.unlink()
    link.symlink_to('/candidate/file');evidence=[]
    with self.assertRaises(c.ResourceBlocked) as found:self.inspect(proc,evidence)
    item=found.exception.evidence
    self.assertEqual(item['pid'],112774);self.assertEqual(item['process_name'],'temporary reader (worker)')
    self.assertEqual(item['path'],'/candidate/file');self.assertEqual(item['reference_type'],kind)
    self.assertEqual(item['source_path'],str(link));self.assertEqual(item['candidate'],'/candidate')
    self.assertEqual(item['fd'],7 if kind=='fd' else None)

 def test_controller_is_not_exempted(self):
  with self.temp() as folder:
   proc,process=self.fixture(Path(folder));(process/'fd/9').symlink_to('/candidate/open');evidence=[]
   with patch.object(c.os,'getpid',return_value=112774),self.assertRaises(c.ResourceBlocked) as found:self.inspect(proc,evidence)
   self.assertTrue(found.exception.evidence['is_controller'])

 def test_process_disappears_before_stat_read(self):
  with self.temp() as folder:
   proc,process=self.fixture(Path(folder));(process/'stat').unlink();evidence=[]
   self.inspect(proc,evidence)
   self.assertEqual(evidence[0]['status'],'clear');self.assertEqual(evidence[0]['events'][0]['kind'],'process_disappeared')

 def test_process_exits_after_candidate_reference_observed(self):
  with self.temp() as folder:
   proc,process=self.fixture(Path(folder));link=process/'fd/8';link.symlink_to('/candidate/open');evidence=[]
   original=c.read_reference
   def read(path):
    value=original(path)
    if path==link:(process/'stat').unlink()
    return value
   with patch.object(c,'read_reference',side_effect=read):self.inspect(proc,evidence)
   item=evidence[0]['events'][0]
   self.assertEqual(item['kind'],'process_disappeared');self.assertEqual(item['reference_type'],'fd')
   self.assertEqual(item['path'],'/candidate/open')

 def test_process_disappears_while_enumerating_descriptors(self):
  with self.temp() as folder:
   proc,process=self.fixture(Path(folder));evidence=[];original=Path.iterdir
   def entries(path):
    if path==process/'fd':
     (process/'stat').unlink();raise ProcessLookupError(3,'process vanished',str(path))
    return original(path)
   with patch.object(Path,'iterdir',entries):self.inspect(proc,evidence)
   self.assertEqual(evidence[0]['events'][0]['kind'],'process_disappeared')

 def test_closed_descriptor_of_living_process_is_recorded(self):
  with self.temp() as folder:
   proc,process=self.fixture(Path(folder));link=process/'fd/8';link.symlink_to('/candidate/open');evidence=[];original=c.read_reference;seen=0
   def read(path):
    nonlocal seen
    if path==link:
     seen+=1
     return '/candidate/open' if seen==1 else None
    return original(path)
   with patch.object(c,'read_reference',side_effect=read):self.inspect(proc,evidence)
   self.assertEqual(evidence[0]['events'][0]['kind'],'reference_released');self.assertTrue((process/'stat').exists())

 def test_process_disappears_during_reference_confirmation(self):
  with self.temp() as folder:
   proc,process=self.fixture(Path(folder));link=process/'fd/8';link.symlink_to('/candidate/open');evidence=[];original=c.read_reference;seen=0
   def read(path):
    nonlocal seen
    value=original(path)
    if path==link:
     seen+=1
     if seen==2:(process/'stat').unlink()
    return value
   with patch.object(c,'read_reference',side_effect=read):self.inspect(proc,evidence)
   self.assertEqual(evidence[0]['events'][0]['kind'],'process_disappeared')

 def test_pid_reuse_fails_closed(self):
  with self.temp() as folder:
   proc,process=self.fixture(Path(folder));(process/'fd/8').symlink_to('/candidate/open');evidence=[]
   identity=c.process_identity(process);changed={**identity,'start_ticks':88}
   with patch.object(c,'process_identity',side_effect=[identity,changed]),self.assertRaises(c.ResourceBlocked) as found:self.inspect(proc,evidence)
   self.assertEqual(found.exception.evidence['kind'],'process_identity_changed')

 def test_permission_denied_is_not_treated_as_process_exit(self):
  with self.temp() as folder:
   proc,process=self.fixture(Path(folder));evidence=[]
   with patch.object(c,'read_reference',side_effect=PermissionError(13,'denied')),self.assertRaises(PermissionError):self.inspect(proc,evidence)

 def test_missing_metadata_of_existing_process_blocks(self):
  with self.temp() as folder:
   proc,process=self.fixture(Path(folder));(process/'mountinfo').unlink();evidence=[]
   with self.assertRaises(c.ResourceBlocked) as found:self.inspect(proc,evidence)
   self.assertEqual(found.exception.evidence['kind'],'incomplete_process_metadata')

 def test_mount_check_remains_blocking(self):
  with self.temp() as folder:
   proc,process=self.fixture(Path(folder));(process/'mountinfo').write_text('1 0 8:1 /candidate /other rw - ext4 /dev/fake rw\n');evidence=[]
   with self.assertRaises(c.ResourceBlocked) as found:self.inspect(proc,evidence)
   self.assertEqual(found.exception.evidence['reference_type'],'mount_root');self.assertEqual(found.exception.evidence['path'],'/candidate')

 def test_cli_persists_structured_block_before_any_deletion(self):
  import runpy
  with self.temp() as folder:
   root=Path(folder);real_mkstemp=tempfile.mkstemp
   item={'kind':'candidate_in_use','pid':112774,'process_name':'reader','path':'/candidate/open','reference_type':'fd','source_path':'/proc/112774/fd/7','fd':7}
   def fail(paths,evidence):
    evidence.append({'status':'blocked','events':[item]})
    raise c.ResourceBlocked('Candidate in use',item)
   def create(**kwargs):return real_mkstemp(prefix='report-',suffix='.json',dir=root)
   with patch('sys.argv',['limpeza-controlada-final.py','--plan','unused','--plan-sha256','0'*64]),patch.object(c.os,'geteuid',return_value=0),patch.object(c,'validate_plan',return_value=[Path('/candidate')]),patch.object(c,'resources_clear',side_effect=fail),patch.object(tempfile,'mkstemp',side_effect=create),patch.object(c,'delete_paths') as deletion,self.assertRaises(c.ResourceBlocked):
    runpy.run_path(str(ROOT/'scripts/limpeza-controlada-final.py'),run_name='__main__')
   report=json.loads(next(root.glob('report-*.json')).read_text())
   self.assertEqual(report['resource_block'],item);self.assertEqual(report['deleted'],[])
   self.assertEqual(report['resource_checks'][0]['events'],[item]);deletion.assert_not_called()
