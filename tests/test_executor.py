"""Executor: fixtures, subprocessos mockados; nunca chroot/mount/systemd reais."""
import copy
import json
import os
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from pipeline.devlite.customize import executor_contract as c
from pipeline.devlite.customize import executor as e
from pipeline.devlite.customize import executor_worker as w
from pipeline.devlite.customize import guest_runner as g
from pipeline.devlite.customize.manifest import SpecError

ROOT=c.ROOT
STATUS='Package: demo\nStatus: install ok installed\nArchitecture: amd64\nVersion: 1\n\n'


def plan():
    item={'package':'demo','version':'2','previous':'1','architecture':'amd64','origin':'Ubuntu','sha256':'a'*64,'filename':'pool/demo.deb','download_bytes':1}
    target={'status_sha256':'b'*64,'changes':[item],'final_versions':{'demo':'2'}}
    return {'status':'dependencias_resolvidas_offline','targets':{'base':copy.deepcopy(target),'live':copy.deepcopy(target)},'resources':{'additional_required_bytes':0}}


class ExecutorTests(unittest.TestCase):
    def temp(self): return tempfile.TemporaryDirectory(dir=ROOT/'work')

    def test_contract_accepts_only_complete_ubuntu_transaction(self):
        c.validate_plan(plan())
        for field,value in (('package','casper'),('package','npm'),('package','a;touch'),('architecture','arm64'),('origin','Microsoft'),('version','--evil'),('sha256','bad'),('filename','pool/../../host.deb')):
            p=plan();p['targets']['base']['changes'][0][field]=value
            with self.subTest(field=field,value=value),self.assertRaises(SpecError): c.validate_plan(p)

    def test_contract_blocks_shared_version_conflicts(self):
        p=plan();p['targets']['live']['final_versions']['demo']='3'
        with self.assertRaises(SpecError): c.validate_plan(p)

    def test_contract_blocks_duplicate_operations(self):
        p=plan();p['targets']['base']['changes']*=2
        with self.assertRaises(SpecError): c.validate_plan(p)

    def test_paths_cannot_escape_project_or_follow_symlinks(self):
        with self.temp() as folder:
            root=Path(folder);(root/'link').symlink_to('/etc')
            with self.assertRaises(SpecError): c.confined(root/'link/passwd')
            with self.assertRaises(SpecError): c.confined(Path('/etc/passwd'))

    def test_command_enforces_namespaces_and_cgroup_limits(self):
        args=c.command(ROOT/'work/phase4b3-abcdefgh',{'limits':c.LIMITS},'base')
        for token in ('--mount','--pid','--net','--ipc','--uts','--cgroup','--kill-child=KILL','--property=MemoryMax=2684354560','--property=MemorySwapMax=1073741824','--property=TasksMax=128','--property=CPUQuota=100%','--property=KillMode=control-group'):
            self.assertIn(token,args)
        self.assertEqual(args[args.index('--propagation')+1],'private')
        self.assertNotIn('--probe',args)
        self.assertIn('--probe',c.command(ROOT/'work/phase4b3-abcdefgh',{'limits':c.LIMITS},'base',True))

    def test_current_policy_refuses_root_before_any_subprocess(self):
        with self.temp() as folder:
            job=ROOT/'work/phase4b3-policy-test'
            with patch.object(e.os,'geteuid',return_value=0),patch.object(e.subprocess,'run') as run:
                with self.assertRaisesRegex(SpecError,'não autorizado'): e.gate(job,'a'*64)
                run.assert_not_called()

    def test_nonroot_cannot_execute(self):
        with patch.object(e.os,'geteuid',return_value=1000):
            with self.assertRaisesRegex(SpecError,'root autorizado'): e.gate(ROOT/'work/phase4b3-abcdefgh','a'*64)

    def test_prepare_refuses_root(self):
        with patch.object(c.os,'geteuid',return_value=0):
            with self.assertRaises(SpecError): c.prepare(Path('anything'))

    def test_missing_probe_blocks_real_install(self):
        with self.temp() as folder:
            with self.assertRaisesRegex(SpecError,'probe privilegiado'): e.verify_probe(Path(folder),'a'*64)

    def test_service_guard_restores_bytes_mode_xattr_after_failure(self):
        with self.temp() as folder:
            root=Path(folder);path=w.safe(root,'usr/sbin/policy-rc.d')
            path.write_bytes(b'original policy');path.chmod(0o740);os.setxattr(path,'user.devlite',b'original')
            with self.assertRaises(RuntimeError):
                with w.service_guard(root):
                    self.assertIn('exit 101',path.read_text());raise RuntimeError('maintainer failed')
            self.assertEqual(path.read_bytes(),b'original policy')
            self.assertEqual(path.stat().st_mode & 0o777,0o740)
            self.assertEqual(os.getxattr(path,'user.devlite'),b'original')

    def test_service_guard_restores_symlink_without_following_it(self):
        with self.temp() as folder:
            root=Path(folder);path=w.safe(root,'usr/sbin/policy-rc.d');path.symlink_to('original-policy')
            with w.service_guard(root): self.assertFalse(path.is_symlink())
            self.assertEqual(os.readlink(path),'original-policy')

    def test_service_guard_removes_only_own_temporary_policy(self):
        with self.temp() as folder:
            root=Path(folder)
            with w.service_guard(root): self.assertTrue((root/'usr/sbin/policy-rc.d').exists())
            self.assertFalse((root/'usr/sbin/policy-rc.d').exists())

    def test_worker_rejects_symlink_ancestor_before_writing(self):
        with self.temp() as folder:
            root=Path(folder);(root/'etc').symlink_to('/etc')
            with self.assertRaises(SpecError): w.safe(root,'etc/anything')

    def test_protected_inventory_detects_installer_modification(self):
        with self.temp() as folder:
            root=Path(folder);path=root/'var/lib/snapd/snaps/installer.snap';path.parent.mkdir(parents=True);path.write_bytes(b'original')
            before=c.protected_inventory(root)
            path.chmod(0o600)
            with self.assertRaises(SpecError): c.require_equal(before,c.protected_inventory(root))
            path.chmod(0o644)
            os.link(path,root/'extra-link')
            with self.assertRaises(SpecError): c.require_equal(before,c.protected_inventory(root))
            (root/'extra-link').unlink();path.write_bytes(b'tampered')
            with self.assertRaisesRegex(SpecError,'Instalador'): c.require_equal(before,c.protected_inventory(root))

    def test_protected_package_inventory_covers_owned_files(self):
        with self.temp() as folder:
            root=Path(folder);info=root/'var/lib/dpkg/info';info.mkdir(parents=True)
            (info/'casper.list').write_text('/usr/bin/casper-helper\n')
            path=root/'usr/bin/casper-helper';path.parent.mkdir(parents=True);path.write_bytes(b'protected')
            self.assertIn('usr/bin/casper-helper',c.protected_inventory(root))

    def test_final_database_rejects_extra_or_missing_packages(self):
        self.assertEqual(c.assert_final(STATUS,{'final_versions':{'demo':'1'}}),{'demo':'1'})
        with self.assertRaises(SpecError): c.assert_final(STATUS,{'final_versions':{'demo':'2'}})

    def test_guest_simulation_rejects_removal_and_parses_annotations(self):
        text='Inst demo [1] (2 local-deb [amd64]) [other:amd64 ]'
        self.assertEqual(g.changes(text),{'demo':'2'})
        with self.assertRaises(RuntimeError): g.changes('Remv demo [1]')

    def test_apt_auto_state_preserves_old_flags_and_marks_only_new_dependencies(self):
        changes=[{'package':'direct','previous':None},{'package':'newdep','previous':None},{'package':'oldmanual','previous':'1'}]
        result=g.automatic_packages(['oldauto','direct'],changes,['direct'])
        self.assertEqual(result,['newdep','oldauto'])

    def test_guest_apt_config_does_not_inherit_image_hooks_or_network_sources(self):
        text=w.apt_config()
        self.assertIn('Dir::Etc::parts "/run/devlite/empty"',text)
        self.assertIn('APT::Get::Download "false"',text)
        self.assertNotIn('AllowUnauthenticated',text)
        self.assertIn('--force-confold',text)

    def test_no_admin_chroot_ptrace_mknod_capabilities_retained(self):
        for cap in (16,17,18,19,21,22,23,25,26,27): self.assertNotIn(cap,w.KEEP_CAPS)
        self.assertIn(31,w.KEEP_CAPS)  # preservar file capabilities de pacotes

    def test_stop_refuses_arbitrary_system_units(self):
        with patch.object(e.subprocess,'run') as run:
            for unit in ('ssh','docker.service','devlite-bad;cmd'):
                with self.assertRaises(SpecError): e.stop(unit)
            run.assert_not_called()

    def test_disk_monitor_kills_only_job_unit_and_preserves_logs(self):
        with self.temp() as folder:
            proc=Mock();proc.poll.return_value=None;proc.wait.return_value=0
            with patch.object(e.subprocess,'Popen',return_value=proc),patch.object(e.shutil,'disk_usage',return_value=SimpleNamespace(free=1)),patch.object(e,'stop') as stop:
                with self.assertRaisesRegex(SpecError,'Reserva'): e.supervise(['mock'],Path(folder),'devlite-fixture',2)
                stop.assert_called_once_with('devlite-fixture')
            self.assertTrue((Path(folder)/'devlite-fixture.log').exists())

    def test_result_parser_accepts_systemd_footer_but_not_duplicate_proof(self):
        text='APT output\nDEVLITE_RESULT={"target":"base","status":"validated"}\nFinished with result: success\n'
        self.assertEqual(c.worker_result(text,'base')['status'],'validated')
        with self.assertRaises(SpecError): c.worker_result(text+text,'base')
        with self.assertRaises(SpecError): c.worker_result(text,'live')

    def test_pair_is_not_accepted_if_journal_quarantined(self):
        with self.temp() as folder:
            p=Path(folder);c.dump(p/'state.json',{'state':'quarantined','job_sha256':'a'})
            c.dump(p/'accepted-pair.json',{'job_sha256':'a','results':{'base':{},'live':{}}})
            with self.assertRaises(SpecError): c.accepted_pair(p)

    def test_atomic_state_write_retains_no_partial_json(self):
        with self.temp() as folder:
            p=Path(folder)/'state.json';c.dump(p,{'state':'quarantined'})
            self.assertEqual(json.loads(p.read_text())['state'],'quarantined')
            self.assertFalse(p.with_name('state.json.new').exists())

    def test_live_failure_quarantines_base_without_accepting_pair(self):
        with self.temp() as folder:
            job=Path(folder);spec={'limits':c.LIMITS,'layers':{},'source_plan':str(job/'source.json')}
            p=plan()
            (job/'debs').mkdir();(job/'debs/demo.deb').write_bytes(b'fixture')
            def fake(args,attempt,unit,reserve):
                if unit.endswith('-live'): raise SpecError('live failure')
                (attempt/(unit+'.log')).write_text('DEVLITE_RESULT={"target":"base","status":"validated"}\n')
            with ExitStack() as stack:
                stack.enter_context(patch.object(e,'gate',return_value=(job,spec,p)))
                stack.enter_context(patch.object(e,'verify_probe'))
                stack.enter_context(patch.object(e,'verify_archives'))
                stack.enter_context(patch.object(e,'authenticate',return_value=[]))
                stack.enter_context(patch.object(e,'validate_image',return_value={'sha256':'fixture'}))
                stack.enter_context(patch.object(e.shutil,'disk_usage',return_value=SimpleNamespace(free=100*1024**3)))
                stack.enter_context(patch.object(e,'supervise',side_effect=fake))
                stack.enter_context(patch.object(e,'stop'))
                with self.assertRaisesRegex(SpecError,'live failure'): e.execute(job,'a'*64)
            self.assertEqual(json.loads((job/'attempt/state.json').read_text())['state'],'quarantined')
            self.assertFalse((job/'attempt/accepted-pair.json').exists())

class ReconciliationTests(unittest.TestCase):
    def test_delta_plans_removals_and_replacements_without_execution(self):
        from pipeline.devlite.customize.reconcile import plan_delta
        base={'gone':{'type':'file'},'changed':{'type':'file','sha256':'a'}}
        live={'changed':{'type':'symlink','target':'other'},'new':{'type':'file'}}
        result=plan_delta(base,live,{'p':'1'},{'p':'1','installer':'1'})
        self.assertEqual(result['whiteouts_required'],['gone'])
        self.assertTrue(result['put'][0]['replace_type'])
        self.assertFalse(result['apply_implemented'])

    def test_delta_rejects_stale_overlay_origins(self):
        from pipeline.devlite.customize.reconcile import plan_delta
        with self.assertRaises(SpecError): plan_delta({}, {'x':{'type':'file','xattrs':{'trusted.overlay.origin':'old'}}},{},{})

    def test_delta_rejects_version_drift_and_unsafe_paths(self):
        from pipeline.devlite.customize.reconcile import plan_delta
        with self.assertRaises(SpecError): plan_delta({}, {},{'p':'1'},{'p':'2'})
        with self.assertRaises(SpecError): plan_delta({}, {'../host':{'type':'file'}},{},{})

    def test_delta_sorts_deletions_children_first(self):
        from pipeline.devlite.customize.reconcile import plan_delta
        result=plan_delta({'d':{'type':'dir'},'d/a':{'type':'file'}},{},{},{})
        self.assertEqual(result['whiteouts_required'],['d/a','d'])

if __name__=='__main__': unittest.main()
