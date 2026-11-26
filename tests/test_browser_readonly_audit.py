import importlib.util,os,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('browser_readonly_audit',ROOT/'scripts/auditar-imagens-navegador.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
class BrowserReadonlyAuditTests(unittest.TestCase):
    def fixture(self,root):
        p=root/'program';p.write_bytes(b'preserved');p.chmod(0o644)
        return {'program':{'type':'file','mode':'0644','size':9,'sha256':a.sha(p)}}
    def test_expected_file_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);m=self.fixture(root)
            self.assertEqual(a.verify_entries(root,m,owner=(os.getuid(),os.getgid())),1)
    def test_modified_file_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);m=self.fixture(root);(root/'program').write_bytes(b'modified!')
            with self.assertRaises(ValueError):a.verify_entries(root,m,owner=(os.getuid(),os.getgid()))
    def test_metadata_change_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);m=self.fixture(root);(root/'program').chmod(0o755)
            with self.assertRaises(ValueError):a.verify_entries(root,m,owner=(os.getuid(),os.getgid()))
    def test_escaping_path_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):a.verify_entries(Path(tmp),{'../outside':{'type':'file'}})
    def test_symlink_ancestor_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);outside=root/'outside';outside.mkdir();(root/'link').symlink_to(outside)
            with self.assertRaises(ValueError):a.verify_entries(root,{'link/file':{'type':'file'}})
    def test_link_target_verified_without_following(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'link').symlink_to('missing')
            m={'link':{'type':'symlink','mode':'0777','target':'missing'}}
            self.assertEqual(a.verify_entries(root,m,owner=(os.getuid(),os.getgid())),0)
            m['link']['target']='different'
            with self.assertRaises(ValueError):a.verify_entries(root,m,owner=(os.getuid(),os.getgid()))
    def test_shared_directory_mode_not_overwritten_or_assumed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'shared').mkdir(mode=0o700)
            self.assertEqual(a.verify_entries(root,{'shared':{'type':'dir','mode':'0755'}},owner=(os.getuid(),os.getgid())),0)
            self.assertEqual((root/'shared').stat().st_mode&0o777,0o700)
    def test_command_limits_and_single_writable_job(self):
        job=a.ROOT/'work/browser-final-audit-test';args=a.argv(job,'f'*64)
        for v in ['ProtectSystem=strict','ProtectHome=read-only','PrivateNetwork=yes','NoNewPrivileges=yes','ReadWritePaths='+str(job)]:self.assertIn('--property='+v,args)
        self.assertEqual(len([x for x in args if x.startswith('--property=ReadWritePaths=')]),1)
    def test_no_root_execution_without_namespace_authorization(self):
        with self.assertRaises(ValueError):a.run(Path('/irrelevant'),'f'*64,False)
