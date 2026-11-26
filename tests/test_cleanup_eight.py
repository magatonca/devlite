import json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from pipeline.devlite import cleanup_eight as c

class EightCleanupTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  for i,name in enumerate(c.TARGETS):
   p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True)
   if i<7:p.mkdir()
   else:p.write_bytes(b'old iso fixture')
 def tearDown(self):self.tmp.cleanup()
 def job(self):
  job=self.root/'work/cleanup-eight-test';job.mkdir()
  for name in c.CODE:
   p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('# sealed fixture\n')
  data={'schema':1,'job':str(job),'operation':'exact-eight-cleanup','targets':list(c.TARGETS),
        'code_sha256':{n:c.sha(self.root/n) for n in c.CODE},'iso_generation':False,'browser_installation':False,'visual_changes':False}
  p=job/'plan.json';p.write_text(json.dumps(data));return job,p,data
 def test_exact_eight_and_types(self):
  self.assertEqual(len(c.checked_paths(self.root,c.TARGETS)),8)
 def test_missing_root_rejected(self):
  (self.root/c.TARGETS[0]).rmdir()
  with self.assertRaises(FileNotFoundError):c.checked_paths(self.root,c.TARGETS)
 def test_scope_cannot_expand_shrink_or_reorder(self):
  for names in (c.TARGETS[:-1],c.TARGETS+('etc',),tuple(reversed(c.TARGETS))):
   with self.subTest(names=names),self.assertRaises(ValueError):c.checked_paths(self.root,names)
 def test_symlink_candidate_rejected(self):
  p=self.root/c.TARGETS[0];p.rmdir();p.symlink_to(self.root,target_is_directory=True)
  with self.assertRaises(ValueError):c.checked_paths(self.root,c.TARGETS)
 def test_symlink_ancestor_rejected(self):
  alias=self.root/'alias';alias.symlink_to(self.root/'work',target_is_directory=True)
  with self.assertRaises(ValueError):c.canonical(alias/'release-cezaiofx')
 def test_tree_type_mismatch_rejected(self):
  p=self.root/c.TARGETS[0];p.rmdir();p.write_text('unexpected file')
  with self.assertRaises(ValueError):c.checked_paths(self.root,c.TARGETS)
 def test_external_hardlink_blocks(self):
  p=self.root/c.TARGETS[0]/'data';p.write_bytes(b'keep');os.link(p,self.root/'external')
  with self.assertRaises(ValueError):c.inventory([self.root/c.TARGETS[0]])
 def test_internal_hardlinks_count_once(self):
  p=self.root/c.TARGETS[0]/'data';p.write_bytes(b'keep');os.link(p,p.with_name('second'))
  records,total=c.inventory([p.parent]);self.assertEqual(len(records),3)
  self.assertEqual(total,p.parent.stat().st_blocks*512+p.stat().st_blocks*512)
 def test_preserved_symlink_target_not_followed(self):
  outside=self.root/'outside';outside.write_text('keep')
  p=self.root/c.TARGETS[0];(p/'link').symlink_to(outside)
  records,_=c.inventory([p]);c.delete_paths([p],records)
  self.assertEqual(outside.read_text(),'keep')
 def test_identity_change_blocks_before_delete(self):
  p=self.root/c.TARGETS[0];(p/'data').write_bytes(b'a');records,_=c.inventory([p]);(p/'data').write_bytes(b'changed')
  with self.assertRaises(ValueError):c.delete_paths([p],records)
  self.assertTrue(p.exists())
 def test_contract_and_code_are_sealed(self):
  job,p,_=self.job();approval=c.sha(p);c.read(job,approval,self.root)
  (self.root/c.CODE[0]).write_text('# changed\n')
  with self.assertRaises(ValueError):c.read(job,approval,self.root)
 def test_altered_contract_blocked(self):
  job,p,data=self.job();approval=c.sha(p);data['targets'].append('etc');p.write_text(json.dumps(data))
  with self.assertRaises(ValueError):c.read(job,approval,self.root)
 def test_wrong_operation_or_gate_blocked(self):
  for key,value in (('operation','anything'),('iso_generation',True),('browser_installation',True),('visual_changes',True)):
   # Use the same reviewed job for each independent rejected mutation.
   job=self.root/'work/cleanup-eight-test'
   if job.exists():
    (job/'plan.json').unlink();job.rmdir()
   job,p,data=self.job();data[key]=value;p.write_text(json.dumps(data))
   with self.assertRaises(ValueError):c.read(job,c.sha(p),self.root)
 def test_no_unapproved_or_nonroot_execution(self):
  with self.assertRaisesRegex(ValueError,'approval required'):c.execute(self.root,'x',False)
  with patch.object(c.os,'geteuid',return_value=1000),self.assertRaisesRegex(ValueError,'root execution'):c.execute(self.root,'x',True)
 def test_preserved_metadata_detects_file_change_but_allows_parent_directory_mtime(self):
  p=self.root/'keep';p.write_text('keep');targets=[self.root/n for n in c.TARGETS]
  before=c.project_metadata(self.root,targets)
  os.utime(self.root/'work',None)
  self.assertEqual(before,c.project_metadata(self.root,targets))
  p.write_text('changed');self.assertNotEqual(before,c.project_metadata(self.root,targets))
 def test_hash_verification_records_identity_and_rejects_tampering(self):
  p=self.root/'keep';p.write_text('keep');d={};c.verify_hashes(self.root,{'keep':c.sha(p)},d)
  self.assertEqual(d['protected_verified_metadata'][str(p)],c.fingerprint(p))
  with self.assertRaises(ValueError):c.verify_hashes(self.root,{'keep':'0'*64},{})
 def process(self,folder,contents):
  p=folder/'123';p.mkdir();(p/'stat').write_text('123 (test-task) S '+'0 '*18+'456 0\n');(p/'maps').write_text(contents);return p
 def test_closed_fd_but_active_mapping_blocks(self):
  proc=self.root/'proc';proc.mkdir();path=self.root/c.TARGETS[0]/'mapped'
  self.process(proc,'1000-2000 r--p 00000000 00:00 1 '+str(path)+'\n')
  evidence=[]
  with self.assertRaises(c.ResourceBlocked):c.memory_references([path.parent],evidence,proc)
  self.assertEqual(evidence[0]['reference_type'],'mmap')
 def test_executable_under_candidate_blocks(self):
  proc=self.root/'proc';proc.mkdir();path=self.root/c.TARGETS[0]/'program'
  p=self.process(proc,'');(p/'exe').symlink_to(path)
  with self.assertRaises(c.ResourceBlocked):c.memory_references([path.parent],[],proc)
 def test_disappearing_process_in_mapping_audit_is_allowed(self):
  proc=self.root/'proc';proc.mkdir();self.process(proc,'')
  with patch.object(c,'process_identity',side_effect=[{'pid':123,'start_ticks':1},None]):c.memory_references([],[],proc)
 def test_pid_reuse_in_mapping_audit_blocks(self):
  proc=self.root/'proc';proc.mkdir();self.process(proc,'')
  with patch.object(c,'process_identity',side_effect=[{'pid':123,'start_ticks':1},{'pid':123,'start_ticks':2}]):
   with self.assertRaisesRegex(ValueError,'PID reused'):c.memory_references([],[],proc)

if __name__=='__main__':unittest.main()
