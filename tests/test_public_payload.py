"""Public payload adapter: synthetic archives only, no software executed."""
import hashlib,io,json,os,tarfile,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from pipeline.devlite.final_payload import stage
ROOT=Path(__file__).resolve().parents[1]

class PublicPayloadTests(unittest.TestCase):
 def fixture(self,root,tsbin='bin/tsc',native_version='7.0.2',extra=None):
  (root/'work').mkdir();cache=root/'cache';cache.mkdir();overlay=root/'overlay';overlay.mkdir()
  (overlay/'brand').write_bytes(b'brand')
  node_version='26.13.1';node_prefix='node-v'+node_version+'-linux-x64'
  header=b'\x7fELF\x02\x01'+b'\0'*12+b'\x3e\0'
  node={'bin/node':(header,0o755),'bin/npm':(b'not executed',0o755),'bin/npx':(b'not executed',0o755)}
  ts={'package.json':(json.dumps({'name':'typescript','version':'7.0.2','bin':{'tsc':tsbin}}).encode(),0o644),tsbin:(b'#!/usr/bin/env node\n',0o755)}
  native={'package.json':(json.dumps({'name':'@typescript/typescript-linux-x64','version':native_version,'os':['linux'],'cpu':['x64']}).encode(),0o644)}
  items=[]
  specs=[('node-lts',node_version,'node.tar.xz',node_prefix,node,'/opt/devlite/node/v26.13.1'),('typescript','7.0.2','typescript.tgz','package',ts,'/opt/devlite/typescript/7.0.2/node_modules/typescript'),('@typescript/typescript-linux-x64','7.0.2','native.tgz','package',native,'/opt/devlite/typescript/7.0.2/node_modules/@typescript/typescript-linux-x64')]
  for name,version,filename,prefix,content,dest in specs:
   path=cache/filename
   with tarfile.open(path,'w:gz') as archive:
    for relative,(data,mode) in content.items():
     member=tarfile.TarInfo(prefix+'/'+relative);member.size=len(data);member.mode=mode;archive.addfile(member,io.BytesIO(data))
    if extra and name=='node-lts':
     member=tarfile.TarInfo(prefix+'/'+extra);member.size=1;archive.addfile(member,io.BytesIO(b'x'))
   items.append({'id':name,'version':version,'filename':filename,'prefix':dest,'algorithm':'sha256','digest':hashlib.sha256(path.read_bytes()).hexdigest(),'download_bytes':path.stat().st_size})
  plan={'artifacts':items,'download_cap_bytes':1024*1024,'max_unpacked_node_bytes':1024*1024,'max_unpacked_typescript_bytes':1024*1024,'installed_bytes_reserve_per_full_view':2*1024*1024}
  branding={'overlay':'overlay','files':{'brand':{'sha256':hashlib.sha256(b'brand').hexdigest(),'uid':0,'gid':0,'mode':'0644'}}}
  return cache,plan,branding

 def folder(self):return tempfile.TemporaryDirectory(dir=ROOT/'work')

 def test_stages_only_and_records_root_ownership_without_chown(self):
  with self.folder() as name:
   root=Path(name);args=self.fixture(root);job=stage(root,*args);report=json.loads((job/'payload-report.json').read_text())
   self.assertEqual(report['status'],'staged_only_application_blocked')
   self.assertFalse(report['image_modified']);self.assertFalse(report['programs_executed']);self.assertFalse(report['application_authorized'])
   self.assertTrue(all(v['uid']==0 for v in report['manifest'].values()))
   self.assertEqual((job/'payload/brand').stat().st_uid,os.geteuid())
   self.assertIn('/opt/devlite/node/v26.13.1/bin/node',(job/'payload/usr/local/bin/tsc').read_text())

 def test_cache_tampering_fails_before_workspace_creation(self):
  with self.folder() as name:
   root=Path(name);cache,plan,branding=self.fixture(root);(cache/'node.tar.xz').write_bytes(b'changed')
   with self.assertRaises(ValueError):stage(root,cache,plan,branding)
   self.assertEqual(list((root/'work').iterdir()),[])

 def test_traversal_quarantines_without_outside_write(self):
  with self.folder() as name:
   root=Path(name);args=self.fixture(root,extra='../../escaped')
   with self.assertRaises(ValueError):stage(root,*args)
   self.assertFalse((root/'escaped').exists())
   job=next((root/'work').iterdir());self.assertEqual(json.loads((job/'payload-report.json').read_text())['status'],'quarantined')

 def test_wrong_native_identity_fails_closed(self):
  with self.folder() as name:
   root=Path(name);args=self.fixture(root,native_version='8.0.0')
   with self.assertRaisesRegex(ValueError,'identity'):stage(root,*args)

 def test_overlay_tampering_is_rejected(self):
  with self.folder() as name:
   root=Path(name);args=self.fixture(root);(root/'overlay/brand').write_bytes(b'tampered')
   with self.assertRaisesRegex(ValueError,'digest'):stage(root,*args)

 def test_combined_budget_is_enforced(self):
  with self.folder() as name:
   root=Path(name);cache,plan,branding=self.fixture(root);plan['installed_bytes_reserve_per_full_view']=1
   with self.assertRaisesRegex(ValueError,'budget'):stage(root,cache,plan,branding)

 def test_wrapper_quotes_package_bin_path(self):
  with self.folder() as name:
   root=Path(name);args=self.fixture(root,tsbin="bin/tsc'$(touch nope)");job=stage(root,*args)
   wrapper=(job/'payload/usr/local/bin/tsc').read_text()
   import shlex
   line=wrapper.splitlines()[-1];tokens=shlex.split(line)
   self.assertEqual(tokens[2],"/opt/devlite/typescript/7.0.2/node_modules/typescript/bin/tsc'$(touch nope)")
   self.assertFalse((root/'nope').exists())

 def test_root_preparation_is_forbidden(self):
  with self.folder() as name:
   root=Path(name);args=self.fixture(root)
   with patch('pipeline.devlite.final_payload.os.geteuid',return_value=0):
    with self.assertRaisesRegex(ValueError,'normal'):stage(root,*args)
