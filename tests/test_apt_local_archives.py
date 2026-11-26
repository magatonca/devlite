"""Regressão APT real sem instalar: dpkg=/bin/false + Debug::pkgDPkgPM."""
import os
import contextlib
from unittest.mock import patch
from pipeline.devlite.customize import guest_runner as g
import subprocess
import tempfile
import unittest
from pathlib import Path
from pipeline.devlite.customize.executor_worker import apt_config
from pipeline.devlite.customize.guest_runner import archive_cache
ROOT=Path(__file__).resolve().parents[1]

class LocalArchiveTests(unittest.TestCase):
    def test_guest_uses_writable_target_cache_with_readonly_bundle(self):
        config=apt_config()
        self.assertIn('Dir::Cache::archives "/var/cache/apt/archives";',config)
        self.assertIn('DPkg::Use-Pty "false";',config)
        self.assertIn('APT::Get::Download "false";',config)

    def test_real_apt_reproduces_relative_path_failure_and_accepts_archive_directory(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as folder:
            w=Path(folder);(w/'pkg/DEBIAN').mkdir(parents=True)
            (w/'pkg/DEBIAN/control').write_text('Package: devlite-path-fixture\nVersion: 1\nArchitecture: all\nMaintainer: DevLite <test@localhost>\nDescription: fixture without payload or scripts\n')
            deb=w/'devlite-path-fixture_1_all.deb'
            subprocess.run(['dpkg-deb','--build',str(w/'pkg'),str(deb)],check=True,capture_output=True)
            for name in ('empty','lists/partial','archives/partial'):(w/name).mkdir(parents=True)
            for name in ('status','empty.conf'):(w/name).write_text('')
            config=apt_config().replace('/run/devlite/empty.conf',str(w/'empty.conf')).replace('/run/devlite/sources.list',str(w/'empty.conf')).replace('/run/devlite/empty',str(w/'empty')).replace('/var/lib/dpkg/status',str(w/'status')).replace('/var/lib/devlite-executor/lists',str(w/'lists')).replace('/var/cache/apt/archives',str(w))
            config+=f'Dir::State::extended_states "{w}/extended_states";\nDir::Cache "{w}/archives";\nDir::Log "{w}";\nDir::Bin::dpkg "/bin/false";\nDebug::pkgDPkgPM "true";\n'
            status_before=(w/'status').read_bytes()
            outputs={}
            for label,text in [('broken',config.replace(f'Dir::Cache::archives "{w}";\n','')),('corrected',config)]:
                (w/'apt.conf').write_text(text)
                result=subprocess.run(['apt-get','-y','--no-download','--no-remove','--no-install-recommends','install',str(deb)],env=dict(os.environ,APT_CONFIG=str(w/'apt.conf'),LC_ALL='C'),capture_output=True,text=True,timeout=30)
                outputs[label]=(result.returncode,result.stdout+result.stderr)
            self.assertNotEqual(outputs['broken'][0],0)
            self.assertIn('Pathname to install is not absolute',outputs['broken'][1])
            self.assertEqual(outputs['corrected'][0],0,outputs['corrected'][1])
            self.assertIn('/bin/false --force-confold --status-fd',outputs['corrected'][1])
            self.assertIn(str(deb),outputs['corrected'][1])
            self.assertEqual((w/'status').read_bytes(),status_before)

    def test_cache_links_are_removed_on_error_without_overwriting_existing_files(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as folder:
            w=Path(folder);source=w/'demo.deb';source.write_bytes(b'fixture');cache=w/'cache'
            with self.assertRaisesRegex(RuntimeError,'maintainer failed'):
                with archive_cache([str(source)],cache):
                    self.assertEqual((cache/source.name).readlink(),source)
                    raise RuntimeError('maintainer failed')
            self.assertFalse((cache/source.name).is_symlink())
            (cache/source.name).write_bytes(b'previous')
            with self.assertRaisesRegex(RuntimeError,'Não sobrescrever'):
                with archive_cache([str(source)],cache):self.fail('must refuse')
            self.assertEqual((cache/source.name).read_bytes(),b'previous')

    def test_real_apt_readonly_bundle_requires_writable_cache_partial_and_lock(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as folder:
            w=Path(folder);bundle=w/'bundle';bundle.mkdir();(w/'pkg/DEBIAN').mkdir(parents=True)
            (w/'pkg/DEBIAN/control').write_text('Package: devlite-readonly-fixture\nVersion: 1\nArchitecture: all\nMaintainer: DevLite <test@localhost>\nDescription: no payload or maintainer scripts\n')
            deb=bundle/'devlite-readonly-fixture_1_all.deb'
            subprocess.run(['dpkg-deb','--build',str(w/'pkg'),str(deb)],check=True,capture_output=True)
            for name in ('empty','lists/partial'):(w/name).mkdir(parents=True)
            for name in ('status','empty.conf'):(w/name).write_text('')
            cache=w/'cache'
            cfg=apt_config().replace('/run/devlite/empty.conf',str(w/'empty.conf')).replace('/run/devlite/sources.list',str(w/'empty.conf')).replace('/run/devlite/empty',str(w/'empty')).replace('/var/lib/dpkg/status',str(w/'status')).replace('/var/lib/devlite-executor/lists',str(w/'lists')).replace('/var/cache/apt/archives',str(cache))
            cfg+=f'Dir::State::extended_states "{w}/extended_states";\nDir::Log "{w}";\nDir::Bin::dpkg "/bin/false";\nDebug::pkgDPkgPM "true";\n'
            deb.chmod(0o444);bundle.chmod(0o555)
            before=deb.read_bytes()
            def apt(config):
                (w/'apt.conf').write_text(config)
                return subprocess.run(['apt-get','-y','--no-download','--no-remove','--no-install-recommends','install',str(deb)],env=dict(os.environ,APT_CONFIG=str(w/'apt.conf'),LC_ALL='C'),capture_output=True,text=True,timeout=30)
            try:
                broken=apt(cfg.replace(str(cache),str(bundle)))
                self.assertNotEqual(broken.returncode,0)
                self.assertIn('partial',broken.stdout+broken.stderr)
                with archive_cache([str(deb)],cache):
                    result=apt(cfg)
                    self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                    self.assertIn(str(cache/deb.name),result.stdout+result.stderr)
                    self.assertIn('/bin/false --force-confold --status-fd',result.stdout+result.stderr)
                self.assertEqual((w/'status').read_bytes(),b'')
                self.assertEqual(deb.read_bytes(),before)
                self.assertEqual({f.name for f in bundle.iterdir()},{deb.name})
                self.assertFalse((cache/deb.name).is_symlink())
            finally:bundle.chmod(0o755);deb.chmod(0o644)

    def test_canonical_epoch_names_and_unsafe_identity(self):
        item={'package':'zlib1g:amd64','version':'1:1.3.dfsg-3.1ubuntu2.3','architecture':'amd64'}
        self.assertEqual(g.apt_archive_name(item),'zlib1g_1%3a1.3.dfsg-3.1ubuntu2.3_amd64.deb')
        item.update(package='libreoffice-common',version='4:24.2.7-0ubuntu0.24.04.7',architecture='all')
        self.assertEqual(g.apt_archive_name(item),'libreoffice-common_4%3a24.2.7-0ubuntu0.24.04.7_all.deb')
        for field,value in [('package','../host'),('version','1/escape'),('architecture','../all')]:
            with self.subTest(field=field),self.assertRaises(RuntimeError):g.apt_archive_name(dict(item,**{field:value}))

    def test_apt_command_preflight_blocks_actual_install_on_failure(self):
        with patch.object(g,'archive_cache',return_value=contextlib.nullcontext()),patch.object(g,'run',side_effect=RuntimeError('dry-run failed')) as run:
            with self.assertRaisesRegex(RuntimeError,'dry-run failed'):g.install_local([],[],['--no-download'])
            self.assertEqual(run.call_count,1)
            self.assertIn('Debug::pkgDPkgPM=true',run.call_args.args[0])
            self.assertIn('Dir::Bin::dpkg=/bin/false',run.call_args.args[0])
        with patch.object(g,'archive_cache',return_value=contextlib.nullcontext()),patch.object(g,'run',return_value='') as run:
            g.install_local([],[],['--no-download'])
            self.assertEqual(run.call_count,2)
            self.assertNotIn('Debug::pkgDPkgPM=true',run.call_args_list[1].args[0])

    def test_real_apt_epoch_package_requires_canonical_alias(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as folder:
            w=Path(folder);(w/'pkg/DEBIAN').mkdir(parents=True);bundle=w/'bundle';bundle.mkdir()
            (w/'pkg/DEBIAN/control').write_text('Package: devlite-epoch-fixture\nVersion: 1:2.0-1\nArchitecture: all\nMaintainer: DevLite <test@localhost>\nDescription: epoch regression, no scripts or payload\n')
            deb=bundle/'devlite-epoch-fixture_2.0-1_all.deb';subprocess.run(['dpkg-deb','--build',str(w/'pkg'),str(deb)],check=True,capture_output=True)
            item={'package':'devlite-epoch-fixture','version':'1:2.0-1','architecture':'all','filename':'pool/'+deb.name}
            for name in ('empty','lists/partial'):(w/name).mkdir(parents=True)
            for name in ('status','empty.conf'):(w/name).write_text('')
            cache=w/'cache';cfg=apt_config().replace('/run/devlite/empty.conf',str(w/'empty.conf')).replace('/run/devlite/sources.list',str(w/'empty.conf')).replace('/run/devlite/empty',str(w/'empty')).replace('/var/lib/dpkg/status',str(w/'status')).replace('/var/lib/devlite-executor/lists',str(w/'lists')).replace('/var/cache/apt/archives',str(cache))
            cfg+=f'Dir::State::extended_states "{w}/extended_states";\nDir::Log "{w}";\nDir::Bin::dpkg "/bin/false";\nDebug::pkgDPkgPM "true";\n'
            (w/'apt.conf').write_text(cfg)
            outputs={}
            for label,changes in [('broken',None),('fixed',[item])]:
                with archive_cache([str(deb)],cache,changes=changes):
                    result=subprocess.run(['apt-get','-y','--no-download','--no-remove','--no-install-recommends','install',str(deb)],env=dict(os.environ,APT_CONFIG=str(w/'apt.conf'),LC_ALL='C'),capture_output=True,text=True,timeout=30)
                    outputs[label]=(result.returncode,result.stdout+result.stderr)
            self.assertNotEqual(outputs['broken'][0],0)
            self.assertIn('Pathname to install is not absolute',outputs['broken'][1])
            self.assertEqual(outputs['fixed'][0],0,outputs['fixed'][1])
            self.assertIn(str(cache/'devlite-epoch-fixture_1%3a2.0-1_all.deb'),outputs['fixed'][1])
            self.assertEqual((w/'status').read_bytes(),b'')
            self.assertFalse(any(cache.glob('*.deb')))

    def test_incomplete_dpkg_command_preflight_never_starts_unpack(self):
        item={'package':'demo','version':'1:2','architecture':'all','filename':'pool/demo_2_all.deb'}
        with patch.object(g,'archive_cache',return_value=contextlib.nullcontext()),patch.object(g,'run',return_value='') as run:
            with self.assertRaisesRegex(RuntimeError,'não cobriu todos'):g.install_local(['/bundle/demo_2_all.deb'],[item],['--no-download'])
            self.assertEqual(run.call_count,1)
