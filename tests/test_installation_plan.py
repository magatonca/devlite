"""Regressões do plano de instalação; nenhuma instalação ou acesso à rede."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from pipeline.devlite.customize import installation as m
from pipeline.devlite.customize import service_profiles as s
from pipeline.devlite.customize.manifest import SpecError

ROOT=Path(__file__).resolve().parents[1]
STATUS='Package: demo\nStatus: install ok installed\nArchitecture: amd64\nVersion: 1\n\n'

class InstallationTests(unittest.TestCase):
    def test_status_rejects_half_configured_packages(self):
        self.assertEqual(m.installed(STATUS),{'demo':'1'})
        with self.assertRaises(SpecError): m.installed(STATUS.replace('install ok installed','install ok unpacked'))

    def test_status_rejects_foreign_architecture_and_duplicates(self):
        for text in (STATUS.replace('amd64','arm64'),STATUS+STATUS):
            with self.assertRaises(SpecError): m.installed(text)

    def test_status_preserves_continued_dependency_fields(self):
        self.assertEqual(m.control('Package: demo\nDepends: foo,\n bar | baz\n')[0]['Depends'],'foo,\nbar | baz')

    def test_real_apt_annotations_and_virtual_dependency_selection(self):
        line='Inst libperl5.38t64 [5.38.2-3.2ubuntu0.4] (5.38.2-3.2ubuntu0.7 Ubuntu:24.04/noble-updates [amd64]) [perl:amd64 ]'
        value=m.parse_transaction(line,set())[0]
        self.assertEqual(value['previous'],'5.38.2-3.2ubuntu0.4')
        self.assertEqual(value['version'],'5.38.2-3.2ubuntu0.7')

    def test_transaction_blocks_removals_and_protected_updates(self):
        for text in ('Remv demo [1]','Inst casper (2 Ubuntu [amd64])','Inst linux-image-demo (2 Ubuntu [amd64])','Inst npm (2 Ubuntu [all])','Inst bad;cmd (1 Ubuntu [all])'):
            with self.assertRaises(SpecError): m.parse_transaction(text,{'npm'})

    def test_apt_config_does_not_inherit_host_hooks_or_dpkg(self):
        config=m.apt_config(Path('/project/work/x'),Path('/project/work/x/base.status'))
        self.assertIn('Dir::Etc::parts "/project/work/x/empty"',config)
        self.assertIn('Dir::State::status "/project/work/x/base.status"',config)
        self.assertIn('Dir::Bin::dpkg "/bin/false"',config)
        self.assertIn('Dir::Etc::preferences "/project/work/x/base.preferences"',m.apt_config(Path('/project/work/x'),Path('/project/work/x/base.status'),Path('/project/work/x/base.preferences')))
        self.assertIn('APT::Install-Recommends "false"',config)
        with self.assertRaises(SpecError): m.apt_config(Path('/bad"path'),Path('/status'))

    def test_index_selection_excludes_external_backports_multiverse(self):
        self.assertIsNotNone(m.INDEX.fullmatch('security.ubuntu.com_ubuntu_dists_noble-security_universe_binary-amd64_Packages'))
        for text in ('evil.org_ubuntu_dists_noble_main_binary-amd64_Packages','br.archive.ubuntu.com_ubuntu_dists_noble-backports_main_binary-amd64_Packages','archive.ubuntu.com_ubuntu_dists_noble_multiverse_binary-amd64_Packages'):
            self.assertIsNone(m.INDEX.fullmatch(text))

    def test_preparation_refuses_root(self):
        with patch.object(m.os,'geteuid',return_value=0):
            with self.assertRaises(SpecError): m.prepare(ROOT)

    def test_reconciliation_does_not_replace_dpkg_status(self):
        result=m.compatibility({'final_versions':{'base':'1','shared':'1'}},{'final_versions':{'shared':'2','installer':'3'}})
        self.assertEqual(result['base_packages_missing_live'],['base'])
        self.assertEqual(result['live_only_packages'],['installer'])
        self.assertIn('shared',result['common_version_conflicts'])

    def test_space_budget_accounts_for_four_copies_and_archives(self):
        target={'gross_installed_bytes':1024**3,'download_bytes':100}
        result=m.estimate(target,target,1024)
        self.assertFalse(result['sufficient'])
        self.assertEqual(result['additional_required_bytes'],39*1024**3+200)
        self.assertEqual(result['memory']['squashfs_cache_mib'],256)

    def test_profiles_do_not_enable_daemons_or_privileged_groups(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as folder:
            w=Path(folder);plan=s.export(w)
            self.assertFalse(plan['applied'])
            self.assertIn('docker.socket',plan['unit_masks'])
            self.assertIn('mysql.service',plan['unit_masks'])
            self.assertIn('exit 101',(w/'guards/policy-rc.d').read_text())
            self.assertIn('127.0.0.1',s.FILES['etc/apache2/ports.conf'])
            self.assertNotIn('hosts',json.loads(s.FILES['etc/docker/daemon.json']))
            for name,record in plan['files'].items(): self.assertEqual(m.sha(w/'payloads'/name),record['sha256'])

    def test_deb_hashes_reject_tamper_and_symlink(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as folder:
            w=Path(folder);file=w/'demo.deb';file.write_bytes(b'deb fixture')
            plan={'targets':{'base':{'changes':[{'filename':'pool/demo.deb','sha256':m.sha(file)}]}}}
            self.assertEqual(m.verify_archives(plan,w),1)
            file.write_bytes(b'changed')
            with self.assertRaises(SpecError): m.verify_archives(plan,w)
            file.unlink();file.symlink_to('other')
            with self.assertRaises(SpecError): m.verify_archives(plan,w)

    def test_dpkg_audit_rejects_missing_inventory_and_pending_journal(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as folder:
            w=Path(folder);db=w/'var/lib/dpkg';(db/'info').mkdir(parents=True);(db/'updates').mkdir()
            (db/'status').write_text(STATUS)
            with self.assertRaises(SpecError): m.audit_database(w)
            (db/'info/demo.list').write_text('/usr/bin/demo\n')
            self.assertEqual(m.audit_database(w)['installed'],1)
            (db/'updates/0001').write_text('pending')
            with self.assertRaises(SpecError): m.audit_database(w)

    def test_index_signature_and_signed_hash_fail_closed(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as folder:
            w=Path(folder);source=w/'input';source.mkdir();(w/'lists').mkdir();(w/'logs').mkdir()
            prefix='archive.ubuntu.com_ubuntu_dists_noble'
            (source/(prefix+'_InRelease')).write_text('signed fixture')
            (source/(prefix+'_main_binary-amd64_Packages')).write_text('tampered index')
            def fake(work,label,args,**kwargs):
                Path(args[args.index('--output')+1]).write_text('Origin: Ubuntu\nSuite: noble\nCodename: noble\nDate: Thu, 25 Apr 2024 15:10:33 UTC\nSHA256:\n '+'a'*64+' 1 main/binary-amd64/Packages\n')
                return SimpleNamespace(stdout='[GNUPG:] VALIDSIG '+m.ARCHIVE_KEY+' rest\n')
            with patch.object(m,'run',side_effect=fake):
                with self.assertRaisesRegex(SpecError,'diverge'): m.snapshot_indexes(w,source)
            with patch.object(m,'run',return_value=SimpleNamespace(stdout='[GNUPG:] VALIDSIG BAD rest\n')):
                with self.assertRaisesRegex(SpecError,'Assinatura'): m.snapshot_indexes(w,source)

    @unittest.skipUnless(shutil.which('apt-get'),'APT ausente')
    def test_real_offline_solver_resolves_transitive_version_and_alternative(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'work') as folder:
            w=Path(folder)
            for name in ('empty','lists/partial','cache/archives/partial','logs'): (w/name).mkdir(parents=True)
            for name in ('empty.conf','preferences','extended_states'): (w/name).write_text('')
            (w/'sources.list').write_text('deb [trusted=yes] file:'+str(w/'test_repository')+' noble main\n')
            # trusted=yes existe apenas nesta fixture sem rede e não no planejador real.
            index=w/'lists'/((str(w/'test_repository').replace('_','%5f').replace('/','_'))+'_dists_noble_main_binary-amd64_Packages')
            index.write_text('Package: demo\nVersion: 2\nArchitecture: amd64\nDepends: missing | child (>= 2)\nFilename: pool/demo.deb\nSize: 1\nSHA256: '+'a'*64+'\n\nPackage: child\nVersion: 2\nArchitecture: amd64\nDepends: leaf\nFilename: pool/child.deb\nSize: 1\nSHA256: '+'b'*64+'\n\nPackage: leaf\nVersion: 1\nArchitecture: amd64\nFilename: pool/leaf.deb\nSize: 1\nSHA256: '+'c'*64+'\n\n')
            status=w/'status';status.write_text(STATUS)
            config=w/'apt.conf';config.write_text(m.apt_config(w,status))
            result=subprocess.run(['apt-get','-s','--no-remove','--no-install-recommends','install','demo'],env=dict(os.environ,APT_CONFIG=str(config),LC_ALL='C'),capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            changes=m.parse_transaction(result.stdout,set())
            self.assertEqual({i['package'] for i in changes},{'demo','child','leaf'})
            self.assertEqual(status.read_text(),STATUS)

if __name__=='__main__': unittest.main()
