import importlib.util,importlib.machinery,json,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
R=Path(__file__).resolve().parents[1]
def module(name,path):
 loader=importlib.machinery.SourceFileLoader(name,str(path));spec=importlib.util.spec_from_loader(name,loader);m=importlib.util.module_from_spec(spec);loader.exec_module(m);return m
review=module('prototype_review_tests',R/'scripts/validar-prototipos-isolados.py')
first=module('modern_first_test',R/'prototypes/devlite-modern/payload/usr/libexec/devlite-first-session')
class ReviewTests(unittest.TestCase):
 def test_fixed_guest_commands_do_not_run_upstream(self):
  commands=review.commands();self.assertEqual(len(commands),7)
  for cmd in commands:
   if 'adminer-6.3.0-mysql.php' in cmd[-1]:self.assertIn('-l',cmd)
  self.assertEqual(commands[5],['/usr/bin/php8.3','-n','/run/prototype-review/test-policy.php'])
  self.assertIn('-I',commands[-1]);self.assertIn('SimulatedBackend',commands[-1][-1])
 def test_isolation_command_restricts_write_scope(self):
  job=R/'work/prototype-review-test';cmd=review.command(job,'a'*64)
  self.assertIn('--property=ProtectSystem=strict',cmd)
  self.assertIn('--property=ProtectHome=read-only',cmd)
  self.assertEqual([x for x in cmd if x.startswith('--property=ReadWritePaths=')],['--property=ReadWritePaths='+str(job)])
  self.assertIn('--property=PrivateNetwork=yes',cmd);self.assertIn('--net',cmd)
 def test_no_root_preparation(self):
  with patch.object(review.os,'geteuid',return_value=0):
   with self.assertRaises(ValueError):review.prepare()
 def test_run_refuses_before_files_or_commands(self):
  with self.assertRaises(ValueError):review.run(None,None,False)
 def test_inspect_rejects_configuration_symlink_escape(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);(root/'etc').symlink_to('/etc')
   with self.assertRaises((ValueError,RuntimeError)):review.inspect(root)
class FirstSessionTests(unittest.TestCase):
 def setup_tree(self,root):
  identity=root/'usr/share/devlite-os/identity.json';identity.parent.mkdir(parents=True);identity.write_text('{"name":"DevLite OS"}')
  wall=root/'usr/share/backgrounds/devlite/devlite-modern.svg';wall.parent.mkdir(parents=True);wall.write_text('<svg/>')
  home=root/'home/test';folder=home/'.config/devlite';folder.mkdir(parents=True);(folder/'apply-initial-defaults').write_text('')
  env={'XDG_CURRENT_DESKTOP':'XFCE','DBUS_SESSION_BUS_ADDRESS':'mock'}
  return home,folder,env
 def test_new_user_dark_and_wallpaper_only_after_success(self):
  with tempfile.TemporaryDirectory() as t,patch.object(first.os,'geteuid',return_value=1000):
   root=Path(t);home,folder,env=self.setup_tree(root);calls=[]
   def runner(argv,**kwargs):
    calls.append(argv);return subprocess.CompletedProcess(argv,0,'/backdrop/screen0/monitor0/workspace0/last-image\n','')
   self.assertEqual(first.apply(root,home,env,runner),'applied')
   self.assertTrue((folder/'initial-defaults-modern-v2.json').is_file())
   self.assertTrue(any('Greybird-dark' in a for a in calls));self.assertFalse(any('Greybird' in a for a in calls))
 def test_existing_user_and_optout_preserved(self):
  for marker in ['initial-defaults-v1.json','initial-defaults-modern-v2.json','keep-user-settings']:
   with tempfile.TemporaryDirectory() as t,patch.object(first.os,'geteuid',return_value=1000):
    root=Path(t);home,folder,env=self.setup_tree(root);(folder/marker).write_text('')
    def runner(*a,**k):raise AssertionError('Must preserve user')
    self.assertEqual(first.apply(root,home,env,runner),'preserved')
 def test_failed_wallpaper_never_marks_applied(self):
  with tempfile.TemporaryDirectory() as t,patch.object(first.os,'geteuid',return_value=1000):
   root=Path(t);home,folder,env=self.setup_tree(root)
   def runner(argv,**kwargs):return subprocess.CompletedProcess(argv,0 if '-l' in argv else 1,'/backdrop/screen0/monitor0/workspace0/last-image\n','')
   self.assertEqual(first.apply(root,home,env,runner),'wallpaper-failed')
   self.assertFalse((folder/'initial-defaults-modern-v2.json').exists())
