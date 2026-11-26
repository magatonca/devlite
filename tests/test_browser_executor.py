import ast,copy,errno,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
from pipeline.devlite import browser_executor as e
from pipeline.devlite.browser_guest import network_denied
from pipeline.devlite.browser import FILES,settings

ROOT=Path(__file__).resolve().parents[1]
class BrowserExecutorTests(unittest.TestCase):
    def plan(self):
        item={'package':'epiphany-browser','version':'46.5-0ubuntu1','previous':None,
          'architecture':'amd64','origin':'Ubuntu','sha256':'a'*64,
          'filename':'pool/universe/e/epiphany-browser/epiphany-browser_46.5-0ubuntu1_amd64.deb'}
        final={'epiphany-browser':'46.5-0ubuntu1','epiphany-browser-data':'46.5-0ubuntu1',
          'ca-certificates':'20240203','dbus-user-session':'1.14.10-4ubuntu4'}
        target={'status_sha256':'b'*64,'changes':[item],'final_versions':final}
        return {'status':'dependencies_resolved_offline','source':str(e.SOURCE),
          'targets':{'base':copy.deepcopy(target),'live':copy.deepcopy(target)},
          'artifacts':[copy.deepcopy(item)],'settings_preview':{n:{f:{} for f in FILES} for n in ('base','live')}}
    def test_derives_exact_browser_lock_without_mutation(self):
        p=self.plan();before=copy.deepcopy(p);converted=e.checked_plan(p)
        self.assertEqual(p,before)
        self.assertEqual(converted['targets'],p['targets'])
        self.assertEqual(converted['requested_ubuntu'],sorted(e.REQUIRED_PACKAGES))
        self.assertEqual(converted['status'],'dependencias_resolvidas_offline')
    def test_rejects_historical_source(self):
        p=self.plan();p['source']='work/old'
        with self.assertRaises(ValueError):e.checked_plan(p)
    def test_rejects_missing_view(self):
        p=self.plan();del p['targets']['live']
        with self.assertRaises(ValueError):e.checked_plan(p)
    def test_rejects_upgrade(self):
        p=self.plan();p['targets']['base']['changes'][0]['previous']='1'
        with self.assertRaises(ValueError):e.checked_plan(p)
    def test_rejects_different_view_dependencies(self):
        p=self.plan();p['targets']['live']['changes'][0]['sha256']='f'*64
        with self.assertRaises(ValueError):e.checked_plan(p)
    def test_existing_56GiB_gate_preserved(self):
        with self.assertRaises(ValueError):e.budget(55*e.GIB,initial=True)
        self.assertEqual(e.budget(56*e.GIB,initial=True),56*e.GIB)
    def test_20GiB_reserve_additional_budget(self):
        with self.assertRaises(ValueError):e.budget(22*e.GIB,3*e.GIB)
        e.budget(23*e.GIB,3*e.GIB)
    def test_command_keeps_strict_home_one_writable_exception(self):
        job=e.ROOT/'work/release-browser-test';args=e.command(job,'a'*64)
        self.assertIn('--property=ProtectSystem=strict',args)
        self.assertIn('--property=ProtectHome=read-only',args)
        self.assertEqual([a for a in args if a.startswith('--property=ReadWritePaths=')],['--property=ReadWritePaths='+str(job)])
        for value in ['PrivateMounts=yes','PrivateNetwork=yes','NoNewPrivileges=yes','RestrictAddressFamilies=AF_UNIX','MemoryMax=2684354560','MemorySwapMax=1073741824','TasksMax=128']:
            self.assertIn('--property='+value,args)
    def test_namespace_has_no_network_option_to_enable_access(self):
        args=e.namespace_command(e.ROOT/'work/release-browser-test','a'*64)
        for value in ['--mount','--pid','--net','--ipc','--uts','--kill-child=KILL']:self.assertIn(value,args)
        self.assertNotIn('--map-root-user',args)
    def test_guest_required_capabilities_are_in_parent_bounding_set(self):
        required=['CAP_CHOWN','CAP_DAC_OVERRIDE','CAP_FOWNER','CAP_FSETID','CAP_KILL','CAP_SETGID','CAP_SETUID','CAP_SETPCAP','CAP_SETFCAP']
        self.assertTrue(set(required)<=set(e.CAPS.split()))
    def test_execute_without_specific_authorization_fails_before_job_read(self):
        with patch.object(e,'read') as read:
            with self.assertRaises(ValueError):e.outer(Path('/unrelated'),'a'*64,False)
            read.assert_not_called()
    def test_unprivileged_inner_rejected_before_job_read(self):
        with patch.object(e.os,'geteuid',return_value=1000),patch.object(e,'read') as read:
            with self.assertRaises(ValueError):e.inner(Path('/unrelated'),'a'*64,True)
            read.assert_not_called()
    def test_missing_cache_fails_before_capture_or_namespace(self):
        with tempfile.TemporaryDirectory() as tmp:
            job=Path(tmp);plan=self.plan()
            d={'additional_budget_bytes':1}
            with patch.object(e.os,'geteuid',return_value=0),patch.object(e,'read',return_value=(job,d,plan)),patch.object(e,'budget'),patch.object(e,'guard_job') as guard:
                with self.assertRaises(ValueError):e.outer(job,'a'*64,True)
                guard.assert_not_called()
    def test_root_preparation_rejected(self):
        with patch.object(e.os,'geteuid',return_value=0):
            with self.assertRaises(ValueError):e.prepare(Path('/nonexistent'))
    def test_preimage_mismatch_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);name=FILES[0];p=root/name;p.parent.mkdir(parents=True);p.write_text('WebBrowser=keep\n')
            preview={n:{'source_sha256':None,'sha256':'f'*64} for n in FILES}
            with self.assertRaises(ValueError):e.merge_browser(root,preview)
            self.assertEqual(p.read_text(),'WebBrowser=keep\n')
    def test_symlink_settings_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=root/FILES[0];p.parent.mkdir(parents=True);outside=root/'outside';outside.write_text('keep');p.symlink_to(outside)
            with self.assertRaises(ValueError):e.merge_browser(root,{})
            self.assertEqual(outside.read_text(),'keep')
    def test_network_socket_family_denied_is_proven_denial(self):
        def denied():raise OSError(errno.EAFNOSUPPORT,'blocked')
        self.assertEqual(network_denied(denied),{'socket_denied_errno':errno.EAFNOSUPPORT})
    def test_network_creation_unexpected_error_not_ignored(self):
        def denied():raise OSError(errno.EMFILE,'unexpected')
        with self.assertRaises(OSError):network_denied(denied)
    def test_connect_unreachable_accepted(self):
        socket=Mock();socket.__enter__=Mock(return_value=socket);socket.__exit__=Mock(return_value=False)
        socket.connect.side_effect=OSError(errno.ENETUNREACH,'offline')
        self.assertEqual(network_denied(lambda:socket),{'connect_denied_errno':errno.ENETUNREACH})
    def test_successful_connect_rejected(self):
        socket=Mock();socket.__enter__=Mock(return_value=socket);socket.__exit__=Mock(return_value=False)
        with self.assertRaises(RuntimeError):network_denied(lambda:socket)
    def test_network_timeout_not_accepted_as_proof(self):
        socket=Mock();socket.__enter__=Mock(return_value=socket);socket.__exit__=Mock(return_value=False)
        socket.connect.side_effect=TimeoutError()
        with self.assertRaises(TimeoutError):network_denied(lambda:socket)
    def test_guest_probe_precedes_first_apt(self):
        tree=ast.parse((ROOT/'pipeline/devlite/browser_guest.py').read_text())
        main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
        text=ast.unparse(main)
        self.assertLess(text.index('probe(config, legacy)'),text.index("'/usr/bin/apt-get'"))
        for unsafe in ['WEBKIT_DISABLE_SANDBOX','--no-sandbox','locale-gen','apache2ctl','dockerd']:self.assertNotIn(unsafe,text)
    def test_all_imported_pipeline_code_is_sealed(self):
        names=e.code_files()
        for name in ['pipeline/devlite/browser_guest.py','pipeline/devlite/browser_executor.py','pipeline/devlite/public_isolation.py','pipeline/devlite/public_attestation.py','pipeline/devlite/customize/executor_worker.py',e.ENTRY]:self.assertIn(name,names)
        self.assertEqual(len(names),len(set(names)))

    def test_attestation_includes_current_readonly_source_images(self):
        data={'host_critical_files':{'/etc/fstab':'a'},'source_receipt_sha256':'b',
          'source_images':{'base':{'file':'/project/base.ext4','sha256':'c'}}}
        before=copy.deepcopy(data);out=e.isolation_spec(data)
        self.assertEqual(data,before)
        self.assertEqual(out['host_critical_files']['/project/base.ext4'],'c')
        self.assertIn(str(e.SOURCE),out['host_critical_files'])

    def test_extra_artifact_rejected_before_copy(self):
        p=self.plan();p['artifacts'].append(dict(p['artifacts'][0],package='unrequested'))
        with self.assertRaises(ValueError):e.checked_plan(p)
    def test_incomplete_settings_allowlist_rejected(self):
        p=self.plan();del p['settings_preview']['live'][FILES[0]]
        with self.assertRaises(ValueError):e.checked_plan(p)

    def test_view_rejects_unprivileged_attempt_before_mount(self):
        with tempfile.TemporaryDirectory() as tmp:
            job=Path(tmp);(job/'attempt').mkdir(mode=0o700)
            with patch.object(e,'read',return_value=(job,{},{})),patch.object(e.os,'geteuid',return_value=0),patch.object(e.os,'getpid',return_value=1),patch.object(e.subprocess,'run') as run:
                with self.assertRaises(ValueError):e.view_worker(job,'base','a'*64)
                run.assert_not_called()
    def test_modified_contract_hash_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);job=root/'work/release-browser-test';job.mkdir(parents=True)
            (job/'browser-contract.json').write_text('{}')
            with patch.object(e,'ROOT',root),patch.object(e,'confined',return_value=job):
                with self.assertRaisesRegex(ValueError,'seal differs'):e.read(job,'f'*64)
