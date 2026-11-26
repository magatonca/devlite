"""Fluxo integrado: modelos/fixtures, sem instalação/mount/chroot/ISO/VM."""
import copy
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from pipeline.devlite import release_layers as layers
from pipeline.devlite import release_acceptance as acceptance
from pipeline.devlite import release_iso as iso
from pipeline.devlite import release_pack as pack
from pipeline.devlite import release_flow as flow
from pipeline.devlite import release_install as installer
from pipeline.devlite.customize.manifest import SpecError
from pipeline.devlite.minimal_root import snapshot,EPOCH

ROOT=flow.ROOT

class ReleaseTests(unittest.TestCase):
    def temp(self):return tempfile.TemporaryDirectory(dir=ROOT/'work')

    def fixture(self,folder):
        base=Path(folder)/'base';base.mkdir();(base/'etc').mkdir();(base/'etc/file').write_bytes(b'original')
        live=Path(folder)/'live';shutil.copytree(base,live,copy_function=shutil.copy2)
        return base,live

    def test_delta_identical_view_composes_without_payload(self):
        with self.temp() as folder:
            base,live=self.fixture(folder);b=snapshot(base);l=snapshot(live);plan=layers.recipe(b,l)
            self.assertEqual(layers.compose(b,plan),l);self.assertEqual(plan['put'],{});self.assertEqual(plan['whiteouts'],[])

    def test_delta_whiteouts_collapse_removed_tree(self):
        with self.temp() as folder:
            base,live=self.fixture(folder);(live/'etc/file').unlink();(live/'etc').rmdir()
            plan=layers.recipe(snapshot(base),snapshot(live));self.assertEqual(plan['whiteouts'],['etc'])

    def test_directory_replaced_by_symlink_needs_no_child_whiteout(self):
        with self.temp() as folder:
            base,live=self.fixture(folder);(live/'etc/file').unlink();(live/'etc').rmdir();(live/'etc').symlink_to('other')
            plan=layers.recipe(snapshot(base),snapshot(live));self.assertEqual(plan['whiteouts'],[]);self.assertEqual(plan['put']['etc']['type'],'symlink')

    def test_materialized_payload_preserves_xattrs_links_metadata(self):
        with self.temp() as folder:
            base,live=self.fixture(folder);file=live/'etc/file';file.write_bytes(b'custom');os.setxattr(file,'user.devlite',b'attribute');os.link(file,live/'etc/hard');(live/'etc/link').symlink_to('file')
            expected=snapshot(live);plan=layers.recipe(snapshot(base),expected);target=Path(folder)/'delta'
            result=layers.materialize(live,target,plan,EPOCH)
            self.assertEqual(os.readlink(target/'etc/link'),'file');self.assertEqual(os.getxattr(target/'etc/file','user.devlite'),b'attribute')
            self.assertEqual((target/'etc/file').stat().st_ino,(target/'etc/hard').stat().st_ino)
            self.assertEqual(layers.compose(snapshot(base),plan),expected)

    def test_whiteout_materialization_refuses_nonroot_before_creation(self):
        with self.temp() as folder:
            base,live=self.fixture(folder);(live/'etc/file').unlink();target=Path(folder)/'delta';plan=layers.recipe(snapshot(base),snapshot(live))
            with patch.object(layers.os,'geteuid',return_value=1000):
                with self.assertRaises(SpecError):layers.materialize(live,target,plan,EPOCH)
            self.assertFalse(target.exists())

    def test_payload_tamper_is_rejected(self):
        with self.temp() as folder:
            base,live=self.fixture(folder);(live/'etc/file').write_bytes(b'new');plan=layers.recipe(snapshot(base),snapshot(live));(live/'etc/file').write_bytes(b'changed')
            with self.assertRaises(SpecError):layers.materialize(live,Path(folder)/'delta',plan,EPOCH)

    def test_delta_refuses_escape_and_stale_overlay_attributes(self):
        with self.temp() as folder:
            base,live=self.fixture(folder);tree=snapshot(base)
            for bad in ('../outside','/etc/passwd'):
                value=copy.deepcopy(tree);value[bad]={'type':'file'}
                with self.assertRaises(SpecError):layers.recipe(tree,value)
            tree['etc']['xattrs']['trusted.overlay.origin']='old'
            with self.assertRaises(SpecError):layers.recipe(tree,snapshot(live))

    def test_hardlink_group_inconsistency_blocks_recipe(self):
        with self.temp() as folder:
            base,live=self.fixture(folder);value=snapshot(live);value['etc/file']['hardlinks']=['missing']
            with self.assertRaises(SpecError):layers.recipe(snapshot(base),value)

    def test_sanitization_only_allows_empty_executor_directories(self):
        with self.temp() as folder:
            base,live=self.fixture(folder);(base/'var/lib/devlite-executor/lists/partial').mkdir(parents=True)
            self.assertNotIn('var/lib/devlite-executor',layers.clean_snapshot(snapshot(base)))
            (base/'var/lib/devlite-executor/unexpected').write_text('secret')
            with self.assertRaises(SpecError):layers.clean_snapshot(snapshot(base))

    def test_manifests_use_observed_delta_format_and_preserve_snap(self):
        values=layers.manifests({'base':'1'},{'base':'1','installer':'2'},'base\t1\nsnap:ubuntu-desktop-bootstrap\t572\n')
        self.assertTrue(values['minimal.manifest'].startswith('--- '));self.assertIn('+base\t1',values['minimal.manifest']);self.assertNotIn('@@',values['minimal.live.manifest'])
        self.assertIn('+installer\t2',values['minimal.live.manifest']);self.assertIn('snap:ubuntu-desktop-bootstrap\t572',values['filesystem.manifest'])

    def test_pack_args_bound_resources_preserve_owners_and_payload_times(self):
        args=pack.compress_args(Path('/source'),Path('/output'),{'mtime':100,'mode':493,'uid':22,'gid':33})
        self.assertEqual(args[args.index('-processors')+1],'1');self.assertEqual(args[args.index('-mem')+1],'256M')
        self.assertNotIn('-all-root',args);self.assertNotIn('-all-time',args);self.assertEqual(args[args.index('-root-uid')+1],'22')

    def test_install_wrapper_never_calls_executor_without_approval(self):
        with self.temp() as folder:
            with patch.object(installer.os,'geteuid',return_value=0),patch.object(installer,'read',return_value=(Path(folder),{})),patch.object(installer,'execute') as execute:
                with self.assertRaisesRegex(SpecError,'não autorizada'):installer.run(Path(folder),'proof')
                execute.assert_not_called()

    def test_install_wrapper_restores_permission_and_exports_failure(self):
        with self.temp() as folder:
            root=Path(folder);project=root/'project';(project/'config').mkdir(parents=True);job=root/'job';job.mkdir();executor=root/'executor';executor.mkdir()
            config=project/'config/projeto.json';config.write_text(json.dumps({'executor_autorizado':True,'iso_final_autorizada':False}))
            with patch.object(installer,'ROOT',project),patch.object(installer.os,'geteuid',return_value=0),patch.object(installer,'read',return_value=(job,{'executor_job':str(executor),'executor_sha256':'proof'})),patch.object(installer,'execute',side_effect=SpecError('fixture failure')):
                with self.assertRaises(SpecError):installer.run(job,'contract')
            self.assertFalse(json.loads(config.read_text())['executor_autorizado'])
            result=json.loads((job/'installation-result.json').read_text());self.assertEqual(result['status'],'quarantined');self.assertFalse(result['iso_generated'])

    def test_install_wrapper_exports_only_accepted_pair(self):
        with self.temp() as folder:
            root=Path(folder);project=root/'project';(project/'config').mkdir(parents=True);job=root/'job';job.mkdir();executor=root/'executor';executor.mkdir()
            config=project/'config/projeto.json';config.write_text(json.dumps({'executor_autorizado':True}))
            pair={'job_sha256':'proof','results':{'base':{'status':'validated'},'live':{'status':'validated'}}}
            with patch.object(installer,'ROOT',project),patch.object(installer.os,'geteuid',return_value=0),patch.object(installer,'read',return_value=(job,{'executor_job':str(executor),'executor_sha256':'proof'})),patch.object(installer,'execute',return_value=executor/'attempt/accepted-pair.json'),patch.object(installer,'accepted_pair',return_value=pair):
                result=installer.run(job,'contract')
            self.assertEqual(json.loads(result.read_text())['status'],'installed_and_audited');self.assertFalse(json.loads(config.read_text())['executor_autorizado'])

    def test_install_wrapper_rejects_nonroot(self):
        with patch.object(installer.os,'geteuid',return_value=1000),patch.object(installer,'execute') as execute:
            with self.assertRaises(SpecError):installer.run(ROOT/'work/none','proof')
            execute.assert_not_called()

    def test_root_pack_is_blocked_without_privileges(self):
        with patch.object(pack.os,'geteuid',return_value=1000):
            with self.assertRaises(SpecError):pack.run(ROOT/'work/absent','proof')

    def test_iso_generation_flag_blocks_before_tool_creation(self):
        with self.temp() as folder:
            with patch.object(iso,'read',return_value=(Path(folder),{})),patch.object(iso,'Runner') as runner:
                with self.assertRaisesRegex(SpecError,'não autorizada'):iso.build(Path(folder),'proof')
                runner.assert_not_called()

    def test_user_owned_layer_receipt_cannot_approve_iso(self):
        with self.temp() as folder:
            root=Path(folder);(root/'layers-ready.json').write_text('{}')
            with self.assertRaises(SpecError):iso.ready_layers(root,'proof')

    def test_staged_cache_is_verified_and_does_not_overwrite(self):
        with self.temp() as folder:
            root=Path(folder);cache=root/'cache';cache.mkdir();(cache/'demo.deb').write_bytes(b'data');destination=root/'staged'
            item={'filename':'pool/demo.deb','sha256':hashlib.sha256(b'data').hexdigest(),'download_bytes':4}
            result=flow.stage_cache(cache,destination,[item]);self.assertEqual(result[0]['strategy'],'hardlink')
            (destination/'extra').write_text('unexpected')
            with self.assertRaises(SpecError):flow.stage_cache(cache,destination,[item])

    def test_different_signed_snapshots_can_describe_same_artifacts(self):
        item={'package':'p','version':'1','architecture':'all','filename':'pool/p.deb','sha256':'a'*64,'download_bytes':4,'targets':['base'],'urls':['https://archive.ubuntu.com/ubuntu/pool/p.deb'],'origins':['old']}
        changed=copy.deepcopy(item);changed['origins']=['new']
        flow.equivalent_artifacts([item],[changed])
        changed['sha256']='b'*64
        with self.assertRaises(SpecError):flow.equivalent_artifacts([item],[changed])

    def test_invalid_acceptance_document_cannot_crash_or_pass(self):
        with self.temp() as folder:
            for document in (None,[],{'schema':1,'profile':'full-edition','runs':{'bios':[],'uefi':{}}}):
                self.assertTrue(acceptance.validate(document,'a'*64,Path(folder)))

    def test_empty_template_is_never_an_approved_boot_report(self):
        with self.temp() as folder:self.assertTrue(acceptance.validate(acceptance.template(),'a'*64,Path(folder)))

    def filled_report(self,root):
        evidence=root/'boot.log';evidence.write_bytes(b'fixture only');proof={'path':'boot.log','sha256':hashlib.sha256(b'fixture only').hexdigest()}
        report=acceptance.template();report['iso']={'path':'fixture.iso','sha256':'a'*64};report['profile']='ubuntu-experimental'
        for mode,run in report['runs'].items():
            run.update(vm_id='vm-'+mode,virtual_disk_id='disk-'+mode,disk_disposable=True)
            run['environment'].update(operator='fixture',date='2026-11-16',hypervisor='fixture')
            for value in run['checks'].values():value.update(status='passed',evidence=[proof])
            for context in run['programs'].values():
                for name,value in context.items():
                    if name not in acceptance.EXTERNAL:value.update(status='passed',version='fixture',evidence=[proof])
        return report

    def test_external_tools_required_for_full_edition(self):
        with self.temp() as folder:
            root=Path(folder);report=self.filled_report(root)
            self.assertFalse(acceptance.validate(report,'a'*64,root));report['profile']='full-edition'
            self.assertTrue(acceptance.validate(report,'a'*64,root))

    def test_evidence_tamper_and_reused_disks_are_rejected(self):
        with self.temp() as folder:
            root=Path(folder);report=self.filled_report(root);(root/'boot.log').write_text('tampered')
            self.assertTrue(acceptance.validate(report,'a'*64,root))
            report['runs']['uefi']['virtual_disk_id']='disk-bios'
            self.assertIn('VMs e discos devem ser distintos',acceptance.validate(report,'a'*64,root))

    def test_reproducibility_refuses_untrusted_reference_before_build(self):
        with self.temp() as folder:
            with patch.object(iso,'read',return_value=(Path(folder),{})),patch.object(iso,'build') as build:
                with self.assertRaises(SpecError):iso.reproduce(Path(folder),'proof',Path(folder)/'outside-artifacts.json')
                build.assert_not_called()

    def test_unsupported_mounts_or_installs_not_present_in_prepare_cli(self):
        result=subprocess.run(['python3',str(ROOT/'scripts/devlite-release.py'),'--help'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0);self.assertNotIn('--execute',result.stdout)

    @unittest.skipUnless(shutil.which('mksquashfs') and shutil.which('unsquashfs'),'SquashFS ausente')
    def test_small_squashfs_rebuild_is_reproducible_without_mounts(self):
        with self.temp() as folder:
            root=Path(folder);source=root/'source';source.mkdir();(source/'file').write_bytes(b'fixture');os.setxattr(source/'file','user.fixture',b'x');(source/'link').symlink_to('file')
            outputs=[]
            for name in ('one','two'):
                image=root/(name+'.sqfs');args=pack.compress_args(source,image,snapshot(source)['.']);args[args.index('256M')]='32M'
                env=dict(os.environ);env.pop('SOURCE_DATE_EPOCH',None)
                subprocess.run(args,capture_output=True,check=True,env=env);outputs.append(hashlib.sha256(image.read_bytes()).hexdigest())
            self.assertEqual(outputs[0],outputs[1])
            subprocess.run(['unsquashfs','-processors','1','-d',str(root/'extracted'),str(root/'one.sqfs')],capture_output=True,check=True)
            self.assertEqual(snapshot(source),snapshot(root/'extracted'))

if __name__=='__main__':unittest.main()
