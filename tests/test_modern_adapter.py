import copy,hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from prototypes import modern_adapter as m
R=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('modern_apply_test',R/'scripts/aplicar-modern-isolado.py');e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)
class ModernAdapterTests(unittest.TestCase):
 def config(self):return m.validate_review()['results']['base']['configuration']
 def test_both_real_views_render_same_seven_files(self):
  views=m.validate_review()['results'];a=m.render(views['base']['configuration']);b=m.render(views['live']['configuration'])
  self.assertEqual(a,b);self.assertEqual(len(a),7)
  self.assertNotIn('etc/dconf/profile/user',a)
  self.assertIn("'gsettings','set'",a['usr/libexec/devlite-first-session']['text'])
 def test_render_keeps_all_panel_plugins(self):
  import xml.etree.ElementTree as ET
  c=self.config();out=m.render(c);old=ET.fromstring(c[m.PANEL]['text']);new=ET.fromstring(out[m.PANEL]['text'])
  self.assertEqual(ET.tostring(old.find("property[@name='plugins']")),ET.tostring(new.find("property[@name='plugins']")))
  self.assertIn('p=10;x=0;y=0',out[m.PANEL]['text'])
 def test_changed_config_hash_rejected(self):
  c=copy.deepcopy(self.config());c[m.PANEL]['text']+='tamper'
  with self.assertRaises(ValueError):m.render(c)
 def test_existing_profiles_stop_automatic_render(self):
  c=copy.deepcopy(self.config());c['home_accounts']=[{'user':'test'}]
  with self.assertRaises(ValueError):m.render(c)
 def test_missing_theme_stops_render(self):
  c=copy.deepcopy(self.config());c['usr/share/themes/Greybird-dark/index.theme']=None
  with self.assertRaises(ValueError):m.render(c)
 def test_application_rejects_preimage_before_writing(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t)/'root';root.mkdir();(root/'test').write_text('old');bundle=Path(t)/'bundle';(bundle/'configuration').mkdir(parents=True);(bundle/'configuration/test').write_text('new')
   item={'kind':'file','sha256':hashlib.sha256(b'new').hexdigest(),'preimage_sha256':'0'*64,'mode':420}
   (bundle/'patch.json').write_text(json.dumps({'test':item}))
   with self.assertRaises(ValueError):m.apply_patch(root,bundle,{'test':{'type':'file','sha256':'1'*64,'hardlinks':['test']}})
   self.assertEqual((root/'test').read_text(),'old')
 def test_undeclared_change_rejected(self):
  with self.assertRaises(Exception):m.verify_patch({'keep':{'type':'file'}},{'keep':{'type':'dir'}},{},set())
 def test_privileged_execution_requires_explicit_authorization(self):
  with self.assertRaises(ValueError):e.run(None,None,False)
 def test_no_privileged_prepare(self):
  with patch.object(e.os,'geteuid',return_value=0):
   with self.assertRaises(ValueError):e.prepare()
 def test_command_retains_security_and_limits(self):
  job=R/'work/modern-apply-test';args=e.command(job,'a'*64)
  for item in ['--property=ProtectSystem=strict','--property=ProtectHome=read-only','--property=PrivateNetwork=yes','--property=MemoryMax=2684354560','--property=TasksMax=128','--property=RuntimeMaxSec=10800']:self.assertIn(item,args)
  self.assertEqual([x for x in args if x.startswith('--property=ReadWritePaths=')],['--property=ReadWritePaths='+str(job)])

 def test_fowner_missing_fails_before_copy(self):
  with self.assertRaisesRegex(ValueError,'CAP_FOWNER missing'):e.require_fowner('CapEff:\t0000000000000000\n')
 def test_fowner_effective_bit_accepted(self):
  e.require_fowner('CapEff:\t0000000000000008\n')
  cap=next(x for x in e.command(R/'work/modern-apply-test','a'*64) if x.startswith('--property=CapabilityBoundingSet='))
  self.assertIn('CAP_FOWNER',cap.split())
 def test_missing_capability_evidence_fails_closed(self):
  for value in ['', 'CapEff: invalid', 'CapEff:']:
   with self.assertRaises(ValueError):e.require_fowner(value)
