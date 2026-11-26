"""Fixtures sem mounts/root: composição, retomada e bloqueios de publicação."""
import copy
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from pipeline.devlite import release_layers as layers, release_resume as resume, release_pack as pack
from pipeline.devlite.customize.manifest import SpecError


def oracle(base,plan):
    result=copy.deepcopy(base)
    for name in plan['whiteouts']:
        for path in list(result):
            if path==name or path.startswith(name+'/'):del result[path]
    for name,value in {**plan['directories'],**plan['put']}.items():
        if value['type']!='dir' or (name in result and result[name]['type']!='dir'):
            for path in list(result):
                if path.startswith(name+'/'):del result[path]
        result[name]=copy.deepcopy(value)
    return result


class ResumeTests(unittest.TestCase):
    def test_indexed_compose_matches_reference_for_overlapping_operations(self):
        randomizer=random.Random(17)
        base={'.':{'type':'dir'}}
        for n in range(60):
            base[f'd{n}']={'type':'dir'}
            for k in range(10):base[f'd{n}/f{k}']={'type':'file','value':k}
        for _ in range(50):
            plan={'whiteouts':randomizer.sample(list(base)[1:],15),'directories':{},'put':{}}
            for name in randomizer.sample(list(base),40):
                plan['put'][name]={'type':randomizer.choice(['dir','file','symlink']),'value':1}
            self.assertEqual(layers.compose(base,plan),oracle(base,plan))

    def test_large_independent_replacements_do_not_scan_entire_tree(self):
        # Deterministic operation count, without a machine-speed dependent timer.
        class Name(str):
            calls=0
            def startswith(self,*args):type(self).calls+=1;return super().startswith(*args)
        base={'.':{'type':'dir'}}
        for n in range(6000):base[Name(f'f{n}') ]={'type':'file'}
        plan={'directories':{},'whiteouts':[],'put':{Name(f'f{n}'): {'type':'file','changed':True} for n in range(6000)}}
        result=layers.compose(base,plan)
        self.assertEqual(len(result),6001);self.assertLess(Name.calls,60000)

    def test_composition_does_not_mutate_input_metadata(self):
        base={'.':{'type':'dir','xattrs':{}},'a':{'type':'file','xattrs':{}}};before=copy.deepcopy(base)
        plan={'whiteouts':['a'],'directories':{'.':base['.']},'put':{}}
        result=layers.compose(base,plan);result['.']['xattrs']['new']='value';self.assertEqual(base,before)

    def test_delta_inventory_contains_exact_whiteout_metadata(self):
        plan={'directories':{'.':{'type':'dir'}},'put':{'new':{'type':'file'}},'whiteouts':['removed']}
        expected=resume.delta_inventory(plan)
        self.assertEqual(expected['removed'],{'type':'char','mode':0,'uid':0,'gid':0,'mtime':resume.EPOCH,'xattrs':{},'device':[0,0]})
        expected['.']['type']='file';self.assertEqual(plan['directories']['.']['type'],'dir')

    def test_snapshot_failure_is_not_treated_as_empty_xattrs(self):
        with patch.object(resume,'snapshot',side_effect=OSError(95,'unsupported')):
            with self.assertRaises(OSError):resume.checked_snapshot(Path('/fixture'),{},'fixture')

    def test_snapshot_mismatch_blocks_publication(self):
        with patch.object(resume,'snapshot',return_value={'.':{'type':'dir'}}):
            with self.assertRaisesRegex(SpecError,'divergências'):resume.checked_snapshot(Path('/fixture'),{},'fixture')

    def test_unprivileged_source_is_not_trusted_even_with_matching_hash(self):
        with tempfile.TemporaryDirectory(dir=resume.ROOT/'work') as folder:
            path=Path(folder)/'payload';path.write_text('fixture')
            with self.assertRaises(SpecError):resume.sealed(path,resume.digest(path))

    def test_resume_is_blocked_by_gate_before_dispatch(self):
        with tempfile.TemporaryDirectory(dir=resume.ROOT/'work') as folder:
            root=Path(folder);(root/'config').mkdir();(root/'config/projeto.json').write_text('{"integracao_camadas_autorizada":false}')
            with patch.object(pack.os,'geteuid',return_value=0),patch.object(pack,'ROOT',root),patch.object(pack,'contract',return_value=(root,{'resume_packed':{}})),patch.object(resume,'run') as execute:
                with self.assertRaisesRegex(SpecError,'não autorizada'):pack.run(root,'proof')
                execute.assert_not_called()

    def fixture_resume(self,folder,mismatch=False):
        import json
        root=Path(folder);work=root/'work';work.mkdir();job=work/'release-new';job.mkdir();source=work/'release-old';source.mkdir();executor=work/'executor';(executor/'attempt').mkdir(parents=True)
        original=work/'phase4b1-dhzezpnz/original-casper';original.mkdir(parents=True)
        (original/'filesystem.manifest').write_text('demo\t1\nsnap:test\t2\n')
        (original/'install-sources.yaml').write_text('  size: 1\n  type: fsimage-layered\n  path: minimal.squashfs\n')
        states={'demo':'1'};(executor/'plan.json').write_text(json.dumps({'targets':{n:{'final_versions':states} for n in ('base','live')}}))
        historical={'executor_job':str(executor),'executor_sha256':'executor-proof','profile':'ubuntu-experimental'}
        (source/'release-contract.json').write_text(json.dumps(historical));old=source/'pack-attempt';(old/'packed').mkdir(parents=True)
        (old/'pack-report.json').write_text('{"status":"quarantined"}')
        hashes={}
        for name in resume.LAYERS:
            file=old/'packed'/name;file.write_bytes(b'fixture-only');hashes[name]=resume.digest(file)
        data={**historical,'resume_packed':{'job':str(source),'contract_sha256':resume.digest(source/'release-contract.json'),'report_sha256':resume.digest(old/'pack-report.json'),'layers':hashes}}
        # Fixture deliberately runs as magaton; supply the accepted directory stat only.
        pair={'job_sha256':'executor-proof','results':{n:{'image':{'file':str(executor/'attempt'/(n+'.ext4')),'sha256':hashes[resume.LAYERS[0]]}} for n in ('base','live')}}
        for n in ('base','live'):(executor/'attempt'/(n+'.ext4')).write_bytes(b'fixture-only')
        tree={'.':{'type':'dir','mode':493,'uid':0,'gid':0,'mtime':0,'xattrs':{}}}
        def fake_snapshot(path):
            if mismatch and path.name=='mounted-merged':return {}
            return copy.deepcopy(tree)
        def fake_run(label,args):
            if label in ('mount-base','mount-live'):
                target=Path(args[-1]);(target/'var/lib/dpkg').mkdir(parents=True);(target/'var/lib/dpkg/status').write_text('fixture')
        real_stat=Path.stat
        def fixture_stat(path,*args,**kwargs):
            info=real_stat(path,*args,**kwargs)
            if path==executor/'attempt':
                from types import SimpleNamespace
                return SimpleNamespace(st_uid=0,st_mode=info.st_mode)
            return info
        with patch.object(Path,'stat',fixture_stat),patch.object(resume,'ROOT',root),patch.object(resume,'confined',side_effect=lambda p:Path(p)),patch.object(resume,'sealed',side_effect=lambda p,s:Path(p)),patch.object(resume,'accepted_pair',return_value=pair),patch.object(resume,'installed',return_value=states),patch.object(resume,'snapshot',side_effect=fake_snapshot),patch.object(resume,'absent_xattrs',return_value=frozenset()),patch.object(resume,'allocated_usage',return_value=4096),patch.object(resume.Runner,'run',side_effect=fake_run) as commands:
            if mismatch:
                with self.assertRaises(SpecError):resume.run(job,data,'new-proof')
                self.assertFalse((job/'layers-ready.json').exists());self.assertFalse((job/'published-casper').exists())
                self.assertEqual(json.loads((job/'pack-attempt/pack-report.json').read_text())['status'],'quarantined')
            else:
                report=json.loads(resume.run(job,data,'new-proof').read_text())
                self.assertEqual(report['status'],'layers_verified');self.assertTrue(report['kernel_composition_verified']);self.assertFalse(report['compression_repeated']);self.assertFalse(report['iso_generated'])
            for call in commands.call_args_list:self.assertEqual(call.args[1][0],'mount')

    def test_resume_fixture_publishes_only_after_all_comparisons(self):
        with tempfile.TemporaryDirectory(dir=resume.ROOT/'work') as folder:self.fixture_resume(folder)

    def test_resume_fixture_quarantines_failed_kernel_composition(self):
        with tempfile.TemporaryDirectory(dir=resume.ROOT/'work') as folder:self.fixture_resume(folder,mismatch=True)

    def test_three_field_snap_manifest_preserves_channel_and_revision(self):
        original='pkg\t1\nsnap:core22\tstable\t2437\nsnap:ubuntu-desktop-bootstrap\t24.04/stable/ubuntu-24.04\t572\n'
        rendered=layers.manifests({'pkg':'1'},{'pkg':'1'},original)
        self.assertEqual(rendered['filesystem.manifest'],original)
        self.assertIn('+snap:ubuntu-desktop-bootstrap\t24.04/stable/ubuntu-24.04\t572\n',rendered['minimal.live.manifest'])

    def test_duplicate_and_malformed_snap_manifest_fail_early(self):
        for original in ('snap:demo\tstable\t1\n'*2,'snap:demo\tstable\t1\textra\n','snap:demo stable 1\n','snap:demo\t\t1\n'):
            with self.subTest(original=original),self.assertRaises(SpecError):layers.manifests({}, {}, original)

    def test_real_official_snap_lines_are_preserved_without_reformatting(self):
        source=resume.ROOT/'work/phase4b1-dhzezpnz/original-casper/filesystem.manifest'
        if not source.is_file():self.skipTest('manifest oficial indisponível')
        original=source.read_text();rendered=layers.manifests({}, {}, original)['filesystem.manifest']
        self.assertEqual([line for line in original.splitlines() if line.startswith('snap:')],rendered.splitlines())
