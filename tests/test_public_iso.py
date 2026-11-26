"""Public ISO controller fixtures: no xorriso, mounts, real ISO or root."""
import copy,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from pipeline.devlite import public_iso as iso,public_iso_control as control
from pipeline.devlite.customize.manifest import SpecError
ROOT=Path(__file__).resolve().parents[1]
class PublicISOTests(unittest.TestCase):
 def temp(self):return tempfile.TemporaryDirectory(dir=ROOT/'work')
 def receipt(self,job):
  layers=job/'layers-ready.json';layers.write_text('fixture receipt')
  return {'status':'public_layers_verified','public_contract_sha256':'a'*64,'host_critical_unchanged':True,
   'host_permissions_unchanged':True,'cleanup_errors':[],'target_programs_executed':False,'iso_generated':False,
   'results':{name:{'status':'validated','file_audit':{'only_declared_additions':True}} for name in ('base','live')},
   'layers_receipt':str(layers),'layers_receipt_sha256':iso.digest(layers),'derived_pack_contract_sha256':'b'*64}
 def inputs(self,job,receipt,operation='apply-and-pack'):
  with patch('pipeline.devlite.public_execution.read',return_value=(job,{'operation':operation})),patch.object(iso,'trusted_report',return_value=receipt),patch.object(iso,'read'),patch.object(iso,'ready_layers'):
   return iso.public_inputs(job,'a'*64)
 def test_accepts_fully_verified_public_pair(self):
  with self.temp() as folder:
   job=Path(folder);report=self.receipt(job);value,spec=self.inputs(job,report)
   self.assertEqual(value,report)
 def test_diagnostic_is_not_a_public_application(self):
  with self.temp() as folder:
   job=Path(folder)
   with self.assertRaises(SpecError):self.inputs(job,self.receipt(job),'isolation-diagnostic')
 def test_quarantined_or_running_receipt_blocked(self):
  with self.temp() as folder:
   job=Path(folder)
   for status in ('running','quarantined'):
    report=self.receipt(job);report['status']=status
    with self.assertRaises(SpecError):self.inputs(job,report)
 def test_another_public_contract_blocked(self):
  with self.temp() as folder:
   job=Path(folder);report=self.receipt(job);report['public_contract_sha256']='c'*64
   with self.assertRaises(SpecError):self.inputs(job,report)
 def test_host_or_cleanup_failure_blocked(self):
  with self.temp() as folder:
   job=Path(folder)
   for key,value in (('host_critical_unchanged',False),('host_permissions_unchanged',False),('cleanup_errors',['failure'])):
    report=self.receipt(job);report[key]=value
    with self.subTest(key=key),self.assertRaises(SpecError):self.inputs(job,report)
 def test_missing_live_or_unverified_file_audit_blocked(self):
  with self.temp() as folder:
   job=Path(folder);report=self.receipt(job);del report['results']['live']
   with self.assertRaises(SpecError):self.inputs(job,report)
   report=self.receipt(job);report['results']['base']['file_audit']['only_declared_additions']=False
   with self.assertRaises(SpecError):self.inputs(job,report)
 def test_changed_layers_receipt_blocked(self):
  with self.temp() as folder:
   job=Path(folder);report=self.receipt(job);(job/'layers-ready.json').write_text('changed')
   with self.assertRaises(SpecError):self.inputs(job,report)
 def test_normal_user_cannot_forge_root_receipt(self):
  with self.temp() as folder:
   path=Path(folder)/'public-result.json';path.write_text('{}')
   with self.assertRaises(SpecError):iso.trusted_report(path)
 def test_authorization_required_before_any_build(self):
  with patch.object(control,'assemble') as build,patch.object(control,'read') as read,self.assertRaises(SpecError):control.run(ROOT/'work/public-iso-fixture','a'*64,False)
  build.assert_not_called();read.assert_not_called()
 def test_no_root_iso_generation(self):
  with patch.object(control.os,'geteuid',return_value=0),patch.object(control,'assemble') as build,self.assertRaises(SpecError):control.run(ROOT/'work/public-iso-fixture','a'*64,True)
  build.assert_not_called()
 def test_single_build_claim_cannot_be_reused(self):
  with self.temp() as folder:
   job=Path(folder);control.claim(job,'a'*64)
   with self.assertRaises(FileExistsError):control.claim(job,'a'*64)
   self.assertEqual(json.loads((job/'single-build-claimed.json').read_text())['build_count'],1)
 def controller_fixture(self,root):
  job=root/'control';job.mkdir();application=root/'application';(application/'published-casper').mkdir(parents=True)
  for name in ('minimal.squashfs','minimal.live.squashfs'):(application/'published-casper'/name).write_bytes(b'fixture')
  original=ROOT/'sources'/control.NAME
  data={'application_sha256':'a'*64,'pack_contract_sha256':'b'*64,'source_bytes':original.stat().st_size}
  return job,application,data
 def test_one_candidate_and_no_global_gate_changes(self):
  with self.temp() as folder:
   root=Path(folder);job,application,data=self.controller_fixture(root);config=(ROOT/'config/projeto.json').read_bytes()
   with patch.dict(os.environ,{'PYTHONHASHSEED':'0'}),patch.object(control,'read',return_value=(job,data)),patch.object(control,'inputs',return_value=(application,{},{})),patch.object(control,'digest',return_value=control.EXPECTED),patch.object(control,'assemble',return_value=root/'report.json') as build:
    output=control.run(job,'c'*64,True)
    self.assertEqual(build.call_count,1)
    with self.assertRaises(FileExistsError):control.run(job,'c'*64,True)
    self.assertEqual(build.call_count,1)
   record=json.loads(output.read_text());self.assertTrue(record['permission_flags_unchanged']);self.assertFalse(record['release_approved'])
   self.assertEqual((ROOT/'config/projeto.json').read_bytes(),config)
 def test_failed_build_preserves_claim_and_records_error(self):
  with self.temp() as folder:
   root=Path(folder);job,application,data=self.controller_fixture(root)
   with patch.dict(os.environ,{'PYTHONHASHSEED':'0'}),patch.object(control,'read',return_value=(job,data)),patch.object(control,'inputs',return_value=(application,{},{})),patch.object(control,'digest',return_value=control.EXPECTED),patch.object(control,'assemble',side_effect=ValueError('fixture failure')),self.assertRaises(ValueError):control.run(job,'c'*64,True)
   self.assertTrue((job/'single-build-claimed.json').exists())
   report=json.loads((job/'execution.json').read_text());self.assertEqual(report['status'],'failed_preserved');self.assertTrue(report['permission_flags_unchanged'])

 def test_changed_configuration_is_not_accepted(self):
  with self.temp() as folder:
   root=Path(folder);job,application,data=self.controller_fixture(root);config=ROOT/'config/projeto.json';original=Path.read_text;count=0
   def reading(path,*args,**kwargs):
    nonlocal count
    value=original(path,*args,**kwargs)
    if path==config:
     count+=1
     if count>1:
      changed=json.loads(value);changed['fixture_changed']=True;return json.dumps(changed)
    return value
   with patch.dict(os.environ,{'PYTHONHASHSEED':'0'}),patch.object(control,'read',return_value=(job,data)),patch.object(control,'inputs',return_value=(application,{},{})),patch.object(control,'digest',return_value=control.EXPECTED),patch.object(control,'assemble',return_value=root/'report.json'),patch.object(Path,'read_text',reading),self.assertRaises(SpecError):control.run(job,'c'*64,True)
   self.assertEqual(json.loads((job/'execution.json').read_text())['status'],'failed_preserved')
