"""Preparação final: fixtures sem downloads, instalações, montagens ou VMs."""
import base64,copy,hashlib,importlib.util,json,os,shutil,subprocess,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from xml.etree import ElementTree as ET
from importlib.machinery import SourceFileLoader
from pipeline.devlite.customize.executor_contract import ROOT
from pipeline.devlite import final_storage as storage,final_artifacts as artifacts


def module(name,path):
 loader=SourceFileLoader(name,str(path));spec=importlib.util.spec_from_loader(name,loader);m=importlib.util.module_from_spec(spec);loader.exec_module(m);return m
metadata=module('metadata_final',ROOT/'scripts/verificar-metadados-externos.py')
guest=module('guest_final',ROOT/'scripts/coletar-evidencias-guest.py')
first_session=module('first_session_final',ROOT/'overlay/final-candidate/usr/libexec/devlite-first-session')
control=module('control_final',ROOT/'overlay/final-candidate/usr/bin/devlite-control')
service_helper=module('service_helper_final',ROOT/'overlay/final-candidate/usr/libexec/devlite-service-control')

class FinalPreparationTests(unittest.TestCase):
 def temp(self):return tempfile.TemporaryDirectory(dir=ROOT/'work')
 def identity(self,root):
  p=root/'usr/share/devlite-os/identity.json';p.parent.mkdir(parents=True);p.write_text('{"name":"DevLite OS","version":"1.0"}')

 def test_storage_does_not_follow_external_symlinks(self):
  with self.temp() as folder:
   r=Path(folder);inside=r/'inside';outside=r/'outside';inside.mkdir();outside.mkdir();(outside/'secret').write_text('fixture');(inside/'link').symlink_to(outside,target_is_directory=True)
   rows,errors=storage.scan(inside);self.assertFalse(errors);self.assertEqual(len(rows),2);self.assertTrue(any(v['kind']=='symlink' for v in rows))
 def test_storage_outside_hardlinks_are_not_reclaimable(self):
  with self.temp() as folder:
   r=Path(folder);inside=r/'inside';inside.mkdir();(r/'shared').write_bytes(b'x'*8192);os.link(r/'shared',inside/'alias')
   rows,_=storage.scan(inside);files=[v for v in rows if v['kind']=='file'];u=storage.usage(files);self.assertEqual(u['outside_hardlink_inodes'],1);self.assertEqual(u['reclaimable_bytes_if_all_listed_paths_removed'],0)
 def test_storage_hardlinks_counted_once_when_all_are_included(self):
  with self.temp() as folder:
   r=Path(folder);(r/'one').write_bytes(b'x'*8192);os.link(r/'one',r/'two');rows,_=storage.scan(r);files=[v for v in rows if v['kind']=='file'];u=storage.usage(files)
   self.assertEqual(u['unique_inodes'],1);self.assertEqual(u['allocated_bytes'],u['reclaimable_bytes_if_all_listed_paths_removed'])
 def test_storage_sparse_size_is_not_claimed_as_allocated(self):
  with self.temp() as folder:
   r=Path(folder)
   with (r/'sparse').open('wb') as f:f.truncate(32*1024**2)
   rows,_=storage.scan(r);u=storage.usage(rows);self.assertGreater(u['logical_file_bytes'],u['allocated_bytes'])
 def test_storage_symlink_root_refused(self):
  with self.temp() as folder:
   r=Path(folder);(r/'link').symlink_to(r,target_is_directory=True)
   with self.assertRaises(ValueError):storage.scan(r/'link')
 def test_storage_incomplete_candidate_has_no_reclaim_estimate(self):
  with self.temp() as folder:
   r=Path(folder);rows,_=storage.scan(r);c=storage.candidate(rows,[{'path':str(r/'private'),'error':'permission denied'}],r,'fixture','fixture');self.assertFalse(c['complete_inventory']);self.assertIsNone(c['reclaimable_bytes_if_all_listed_paths_removed'])

 def fixture_cache(self,root):
  cache=root/'cache';cache.mkdir();data=b'fixture';(cache/'one').write_bytes(data);(cache/'two').write_bytes(data)
  plan={'download_cap_bytes':100,'artifacts':[{'id':'one','filename':'one','algorithm':'sha256','digest':hashlib.sha256(data).hexdigest(),'download_bytes':len(data)},{'id':'two','filename':'two','algorithm':'sha512-sri','digest':'sha512-'+base64.b64encode(hashlib.sha512(data).digest()).decode()}]}
  return cache,plan
 def test_artifact_cache_verifies_sha256_and_sri(self):
  with self.temp() as folder:
   cache,plan=self.fixture_cache(Path(folder));self.assertEqual(len(artifacts.verify(plan,cache)),2)
 def test_artifact_corruption_rejected(self):
  with self.temp() as folder:
   cache,plan=self.fixture_cache(Path(folder));(cache/'two').write_bytes(b'changed')
   with self.assertRaises(ValueError):artifacts.verify(plan,cache)
 def test_artifact_symlink_rejected(self):
  with self.temp() as folder:
   root=Path(folder);cache,plan=self.fixture_cache(root);(cache/'two').unlink();(root/'target').write_bytes(b'fixture');(cache/'two').symlink_to(root/'target')
   with self.assertRaises(ValueError):artifacts.verify(plan,cache)
 def test_artifact_missing_or_unexpected_files_rejected(self):
  with self.temp() as folder:
   cache,plan=self.fixture_cache(Path(folder));(cache/'extra').write_text('fixture')
   with self.assertRaises(ValueError):artifacts.verify(plan,cache)
 def test_artifact_path_escape_rejected(self):
  with self.temp() as folder:
   cache,plan=self.fixture_cache(Path(folder));plan['artifacts'][0]['filename']='../one'
   with self.assertRaises(ValueError):artifacts.verify(plan,cache)
 def test_artifact_total_budget_rejected(self):
  with self.temp() as folder:
   cache,plan=self.fixture_cache(Path(folder));plan['download_cap_bytes']=10
   with self.assertRaises(ValueError):artifacts.verify(plan,cache)

 def test_guest_host_guard_runs_before_subprocesses(self):
  with self.temp() as folder,patch.object(guest,'command') as execute:
   with self.assertRaises(ValueError):guest.collect('live','bios',root=Path(folder))
   execute.assert_not_called()
 def test_guest_context_and_firmware_mismatch_abort(self):
  with self.temp() as folder,patch.object(guest,'command') as execute:
   root=Path(folder);self.identity(root);(root/'proc').mkdir();(root/'proc/cmdline').write_text('boot=casper')
   with self.assertRaises(ValueError):guest.collect('installed','bios',root=root)
   with self.assertRaises(ValueError):guest.collect('live','uefi',root=root)
   execute.assert_not_called()
 def test_guest_collects_without_approving_real_tests(self):
  with self.temp() as folder,patch.object(guest,'command',return_value={'returncode':0}) as execute,patch.object(guest.shutil,'which',return_value=None),patch.dict(os.environ,{'XDG_SESSION_ID':''}):
   root=Path(folder);self.identity(root);(root/'proc').mkdir();(root/'proc/cmdline').write_text('boot=casper')
   data=guest.collect('live','bios',root=root);self.assertFalse(data['practical_approval']);self.assertEqual(data['manual_checks']['installer'],'pending');self.assertFalse(any(v['version_check_executed'] for v in data['programs'].values()))
   self.assertTrue(all(c.args[0][:2]==['systemctl','show'] for c in execute.call_args_list))

 def test_branding_assets_are_self_contained_xml(self):
  for p in (ROOT/'assets/branding').glob('*.svg'):
   tree=ET.parse(p)
   for node in tree.iter():self.assertFalse(any(k.endswith('href') and (v.startswith('http') or v.startswith('file:')) for k,v in node.attrib.items()))
  ET.parse(ROOT/'overlay/final-candidate/etc/xdg/menus/xfce-applications-merged/devlite.menu')
 def test_branding_declared_hashes_and_modes_match_staging(self):
  plan=json.loads((ROOT/'config/final-branding-plan.json').read_text());self.assertFalse(plan['image_modified'])
  for path,item in plan['files'].items():
   p=ROOT/'overlay/final-candidate'/path;self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),item['sha256']);self.assertIn(item['mode'],('0644','0755'))
 def test_first_session_host_guard_is_inert(self):
  with self.temp() as folder,patch.object(first_session.os,'geteuid',return_value=1000):
   runner=unittest.mock.Mock();self.assertEqual(first_session.apply(root=Path(folder),runner=runner),'not-devlite-user');runner.assert_not_called()
 def test_first_session_preserves_user_choices_after_first_run(self):
  with self.temp() as folder,patch.object(first_session.os,'geteuid',return_value=1000):
   root=Path(folder)/'root';root.mkdir();self.identity(root);wall=root/'usr/share/backgrounds/devlite/devlite-wallpaper.svg';wall.parent.mkdir(parents=True);wall.write_text('fixture');home=Path(folder)/'home';opt=home/'.config/devlite';opt.mkdir(parents=True);(opt/'apply-initial-defaults').write_text('opt in')
   def runner(args,**kwargs):return SimpleNamespace(returncode=0,stdout='/backdrop/screen0/monitorVirtual-9/workspace0/last-image\n' if '-l' in args else '')
   env={'XDG_CURRENT_DESKTOP':'XFCE','DBUS_SESSION_BUS_ADDRESS':'fixture'};self.assertEqual(first_session.apply(root,home,env,runner),'applied');self.assertTrue((opt/'initial-defaults-v1.json').exists())
   with patch.object(first_session,'subprocess') as subprocess_mock:self.assertEqual(first_session.apply(root,home,env,unittest.mock.Mock()),'preserved')
 def test_first_session_rejects_config_outside_home(self):
  with self.temp() as folder,patch.object(first_session.os,'geteuid',return_value=1000):
   root=Path(folder)/'root';root.mkdir();self.identity(root);home=Path(folder)/'home';home.mkdir();runner=unittest.mock.Mock();env={'XDG_CURRENT_DESKTOP':'XFCE','DBUS_SESSION_BUS_ADDRESS':'fixture','XDG_CONFIG_HOME':str(Path(folder)/'outside')}
   self.assertEqual(first_session.apply(root,home,env,runner),'unsafe-config-path');runner.assert_not_called()
 def test_control_only_queries_units(self):
  with self.temp() as folder:
   root=Path(folder);self.identity(root);runner=unittest.mock.Mock(return_value=SimpleNamespace(returncode=0,stdout='ActiveState=inactive',stderr=''))
   result=control.status(root,runner);self.assertTrue(result['actions_require_administrator']);self.assertEqual(len(runner.call_args_list),6)
   self.assertTrue(all(c.args[0][:2]==['systemctl','show'] for c in runner.call_args_list))
 def test_metadata_redirect_to_package_is_blocked(self):
  import urllib.request
  request=urllib.request.Request(metadata.URLS['node-key'])
  with self.assertRaises(ValueError):metadata.Redirect().redirect_request(request,None,302,'redirect',{},'https://nodejs.org/dist/v26.13.1/node-v26.13.1-linux-x64.tar.xz')
 def test_metadata_gpg_fingerprint_mismatch_blocks(self):
  with self.temp() as folder,patch.object(metadata,'cmd',return_value='fpr:::::::::BAD:') as cmd:
   with self.assertRaises(ValueError):metadata.verify_gpg(Path(folder),'fixture',Path(folder)/'key',Path(folder)/'signed','EXPECTED')
   self.assertEqual(cmd.call_count,2)

 @unittest.skipUnless(shutil.which('openssl'),'openssl ausente')
 def test_npm_real_ecdsa_and_corruption(self):
  with self.temp() as folder:
   root=Path(folder);private=root/'private.pem';pub=root/'public.der'
   subprocess.run(['openssl','genpkey','-algorithm','EC','-pkeyopt','ec_paramgen_curve:P-256','-out',str(private)],check=True,capture_output=True)
   subprocess.run(['openssl','pkey','-in',str(private),'-pubout','-outform','DER','-out',str(pub)],check=True,capture_output=True)
   key={'expires':None,'keyid':'fixture-registry-key','key':base64.b64encode(pub.read_bytes()).decode()};data={'metadata':{'npm_keys':{'value':{'keys':[key]}}}}
   for label,name in [('typescript','typescript'),('typescript_linux_x64','@typescript/typescript-linux-x64')]:
    sri='sha512-'+base64.b64encode(hashlib.sha512(b'fixture').digest()).decode();message=root/(label+'.sign-input');message.write_text(name+'@7.0.2:'+sri);signature=root/(label+'.signed')
    subprocess.run(['openssl','dgst','-sha256','-sign',str(private),'-out',str(signature),str(message)],check=True,capture_output=True)
    data['metadata'][label]={'value':{'name':name,'version':'7.0.2','os':['linux'],'cpu':['x64'],'dist':{'integrity':sri,'unpackedSize':7,'signatures':[{'keyid':key['keyid'],'sig':base64.b64encode(signature.read_bytes()).decode()}]}}}
   self.assertEqual(len(metadata.verify_npm(root,data)),2)
   bad=copy.deepcopy(data);bad['metadata']['typescript']['value']['dist']['integrity']='sha512-'+base64.b64encode(hashlib.sha512(b'corrupt').digest()).decode()
   with self.assertRaises(ValueError):metadata.verify_npm(root,bad)
   bad=copy.deepcopy(data);bad['metadata']['typescript']['value']['name']='another-package'
   with self.assertRaises(ValueError):metadata.verify_npm(root,bad)

 def test_public_template_requires_node_ts_and_keeps_vscode_optional(self):
  from pipeline.devlite.public_acceptance import template,validate
  with self.temp() as folder:
   data=template();errors=validate(data,'a'*64,Path(folder));self.assertTrue(any('/node:' in e for e in errors));self.assertTrue(any('/typescript:' in e for e in errors));self.assertFalse(any('/vscode:' in e for e in errors));self.assertTrue(any('vscode_optional_entry' in e for e in errors))
 def test_public_policy_rejects_bundled_microsoft_binary(self):
  from pipeline.devlite.public_acceptance import template,validate
  with self.temp() as folder:
   data=template();data['release_policy']['vscode_binary_bundled']=True;self.assertIn('Política pública incompatível',validate(data,'a'*64,Path(folder)))
 def test_public_proof_rejects_path_escape_and_tampering(self):
  from pipeline.devlite.public_acceptance import proof
  with self.temp() as folder:
   root=Path(folder);file=root/'evidence';file.write_bytes(b'fixture');value={'path':'evidence','sha256':hashlib.sha256(b'fixture').hexdigest()};self.assertTrue(proof([value],root));file.write_bytes(b'changed');self.assertFalse(proof([value],root));value['path']='../outside';self.assertFalse(proof([value],root))
 def test_public_vscode_launcher_never_installs_or_downloads(self):
  text=(ROOT/'overlay/final-candidate/usr/share/applications/devlite-get-vscode.desktop').read_text();self.assertIn('Exec=xdg-open https://code.visualstudio.com/docs/setup/linux',text);self.assertNotIn('sudo',text);self.assertNotIn('apt ',text)

 def test_service_helper_rejects_unprivileged_before_actions(self):
  runner=unittest.mock.Mock()
  with patch.object(service_helper.os,'geteuid',return_value=1000),self.assertRaises(ValueError):service_helper.act('start','apache',runner=runner)
  runner.assert_not_called()
 def test_service_helper_rejects_unknown_units(self):
  with self.temp() as folder,patch.object(service_helper.os,'geteuid',return_value=0):
   root=Path(folder);self.identity(root);runner=unittest.mock.Mock()
   with self.assertRaises(ValueError):service_helper.act('start','ssh',root,runner)
   runner.assert_not_called()
 def test_service_helper_always_restores_boot_masks(self):
  with self.temp() as folder,patch.object(service_helper.os,'geteuid',return_value=0):
   root=Path(folder);self.identity(root);runner=unittest.mock.Mock(return_value=SimpleNamespace(returncode=0,stderr=''))
   result=service_helper.act('start','apache',root,runner);self.assertTrue(result['boot_masks_restored'])
   self.assertEqual([c.args[0][2] for c in runner.call_args_list],['unmask','start','mask'])
   self.assertTrue(all(c.args[0][0]=='/usr/bin/systemctl' and 'shell' not in c.kwargs for c in runner.call_args_list))
 def test_service_helper_failed_start_rolls_back_and_masks(self):
  with self.temp() as folder,patch.object(service_helper.os,'geteuid',return_value=0):
   root=Path(folder);self.identity(root)
   def runner(argv,**kwargs):return SimpleNamespace(returncode=1 if argv[2]=='start' else 0,stderr='fixture')
   mock=unittest.mock.Mock(side_effect=runner)
   with self.assertRaises(ValueError):service_helper.act('start','apache',root,mock)
   self.assertEqual([c.args[0][2] for c in mock.call_args_list],['unmask','start','stop','mask'])
 def test_polkit_policy_requires_admin_and_denies_inactive(self):
  tree=ET.parse(ROOT/'overlay/final-candidate/usr/share/polkit-1/actions/org.devlite.services.policy')
  self.assertEqual(tree.find('.//allow_active').text,'auth_admin');self.assertEqual(tree.find('.//allow_any').text,'no');self.assertEqual(tree.find('.//allow_inactive').text,'no')
 def test_control_requests_only_fixed_privileged_helper(self):
  runner=unittest.mock.Mock(return_value=SimpleNamespace(returncode=0));control.request('start','apache',runner);self.assertEqual(runner.call_args.args[0],['/usr/bin/pkexec','/usr/libexec/devlite-service-control','start','apache'])
  with self.assertRaises(ValueError):control.request('start','../../evil',runner)

 def archive_fixture(self,root,items):
  import io,tarfile
  path=root/'fixture.tar'
  with tarfile.open(path,'w') as archive:
   for name,kind,target in items:
    item=tarfile.TarInfo(name);item.mode=0o755
    if kind=='file':item.size=7;archive.addfile(item,io.BytesIO(b'fixture'))
    else:
     item.type={'link':tarfile.SYMTYPE,'dir':tarfile.DIRTYPE,'device':tarfile.CHRTYPE}[kind];item.linkname=target;archive.addfile(item)
  return path
 def test_archive_relative_internal_link_is_supported_without_extraction(self):
  from pipeline.devlite.final_archive import inspect
  with self.temp() as folder:
   root=Path(folder);path=self.archive_fixture(root,[('package/lib/app','file',''),('package/bin/app','link','../lib/app')]);result=inspect(path,'package',100);self.assertFalse(result['extracted']);self.assertFalse((root/'package').exists());self.assertEqual(result['unpacked_bytes'],7)
 def test_archive_traversal_and_external_links_are_rejected(self):
  from pipeline.devlite.final_archive import inspect
  for items in [[('../escape','file','')],[('/package/absolute','file','')],[('package/link','link','../../escape')]]:
   with self.subTest(items=items),self.temp() as folder:
    path=self.archive_fixture(Path(folder),items)
    with self.assertRaises(ValueError):inspect(path,'package',100)
 def test_archive_child_under_link_rejected_even_if_link_arrives_later(self):
  from pipeline.devlite.final_archive import inspect
  with self.temp() as folder:
   path=self.archive_fixture(Path(folder),[('package/alias/file','file',''),('package/alias','link','target')])
   with self.assertRaises(ValueError):inspect(path,'package',100)
 def test_archive_special_files_and_duplicate_names_rejected(self):
  from pipeline.devlite.final_archive import inspect
  for items in [[('package/device','device','')],[('package/file','file',''),('package/file','file','')]]:
   with self.subTest(items=items),self.temp() as folder:
    path=self.archive_fixture(Path(folder),items)
    with self.assertRaises(ValueError):inspect(path,'package',100)
 def test_archive_budget_rejected_before_reading_oversized_member(self):
  from pipeline.devlite.final_archive import inspect
  with self.temp() as folder:
   path=self.archive_fixture(Path(folder),[('package/file','file','')])
   with self.assertRaises(ValueError):inspect(path,'package',6)

 def test_public_selection_retains_ubuntu_set_and_excludes_vscode_binary(self):
  from pipeline.devlite.customize.manifest import resolve
  original=json.loads((ROOT/'packages/selection.json').read_text());public=json.loads((ROOT/'packages/public-selection.json').read_text());old=resolve(original);new=resolve(public)
  self.assertEqual({p['id'] for p in old if p['provider']=='ubuntu'},{p['id'] for p in new if p['provider']=='ubuntu'});self.assertEqual(len(new),46);self.assertNotIn('vscode',{p['id'] for p in new});self.assertFalse(public['optional_post_install']['vscode']['binary_bundled'])
