import ast,hashlib,importlib.util,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('adminer_php_check',ROOT/'scripts/verificar-php-adminer.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
class AdminerPhpCheckTests(unittest.TestCase):
    def test_only_fixed_version_and_lint_no_php_application(self):
        self.assertEqual(a.commands(),[['/usr/bin/php8.3','-n','-v'],['/usr/bin/php8.3','-n','-l','/run/adminer-check/adminer.php']])
        for command in a.commands():
            self.assertNotIn('-r',command);self.assertNotIn('-f',command);self.assertNotIn('-S',command)
    def test_profile_is_strict_single_job_writable(self):
        j=ROOT/'work/adminer-php-check-test';args=a.command(j,'f'*64)
        for p in ['ProtectSystem=strict','ProtectHome=read-only','PrivateNetwork=yes','NoNewPrivileges=yes','ReadWritePaths='+str(j)]:self.assertIn('--property='+p,args)
        self.assertEqual(len([x for x in args if x.startswith('--property=ReadWritePaths=')]),1)
    def test_source_hash_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'source.php';p.write_bytes(b'<?php echo "not executed";')
            with patch.object(a,'EXPECTED',hashlib.sha256(p.read_bytes()).hexdigest()):a.check_candidate(p)
            p.write_bytes(b'changed')
            with self.assertRaises(ValueError):a.check_candidate(p)
    def test_symlink_source_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'original';p.write_bytes(b'not executed');q=Path(tmp)/'link';q.symlink_to(p)
            with self.assertRaises(ValueError):a.check_candidate(q)
    def test_no_authorization_fails_before_input_access(self):
        with patch.object(a,'load') as load:
            with self.assertRaises(ValueError):a.run(Path('/unrelated'),'f'*64,False)
            load.assert_not_called()
    def test_prepare_cannot_be_run_as_root(self):
        with patch.object(a.os,'geteuid',return_value=0):
            with self.assertRaises(ValueError):a.prepare()
    def test_child_is_restricted_before_exec(self):
        tree=ast.parse((ROOT/'scripts/verificar-php-adminer.py').read_text())
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='compile_child')
        code=ast.unparse(fn)
        self.assertLess(code.index('os.closerange'),code.index('os.execve'))
        self.assertLess(code.index('os.setuid(65534)'),code.index('os.execve'))
        self.assertIn('CapBnd:',code);self.assertIn('RLIMIT_CPU',code)
