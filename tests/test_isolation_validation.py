"""Probe: testes sem chroot, rede, mounts, namespaces ou serviços reais."""
import errno
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,mock_open,patch
from pipeline.devlite.customize import isolation_validation as v
from pipeline.devlite.customize import guest_runner as g
from pipeline.devlite.customize import executor as e
from pipeline.devlite.customize.executor_contract import ROOT,LIMITS
from pipeline.devlite.customize.manifest import SpecError


def status(cap=0,no_new=1):
    return ''.join(name+':\t'+format(cap,'016x')+'\n' for name in ('CapEff','CapPrm','CapBnd'))+'CapInh:\t0\nCapAmb:\t0\nNoNewPrivs:\t'+str(no_new)+'\n'


class IsolationValidationTests(unittest.TestCase):
    def temp(self): return tempfile.TemporaryDirectory(dir=ROOT/'work')

    def test_checkpoint_detects_host_changes(self):
        before={'critical_files_sha256':{'db':'a'},'namespaces':{'mnt':'one'},'mountinfo_sha256':'m'}
        after=dict(before,critical_files_sha256={'db':'b'})
        self.assertFalse(v.compare(before,after)['critical_files_unchanged'])
        self.assertTrue(v.compare(before,before)['critical_files_unchanged'])

    def test_cgroup_effective_limits_match(self):
        with self.temp() as folder:
            p=Path(folder)
            for name,value in {'memory.max':str(LIMITS['memory_bytes']),'memory.swap.max':str(LIMITS['swap_bytes']),'pids.max':'128','cpu.max':'100000 100000'}.items(): (p/name).write_text(value)
            self.assertEqual(v.cgroup_limits(p,LIMITS)['pids.max'],'128')
            (p/'memory.max').write_text('max')
            with self.assertRaises(ValueError): v.cgroup_limits(p,LIMITS)

    def test_cgroup_rejects_missing_limit(self):
        with self.temp() as folder:
            with self.assertRaises(FileNotFoundError): v.cgroup_limits(Path(folder),LIMITS)

    def test_capability_checks_all_sets_and_no_new_privileges(self):
        self.assertEqual(g.capabilities(status(1),[0])['CapEff'],1)
        for text in (status(1<<21),status(0,0),status(0).replace('CapAmb:\t0','CapAmb:\t1')):
            with self.assertRaises(RuntimeError): g.capabilities(text,[0])

    def test_readonly_open_requires_erofs_not_missing_file(self):
        with patch('builtins.open',side_effect=OSError(errno.EROFS,'readonly')):
            self.assertEqual(g.denied_open('fixture','r+b',{errno.EROFS}),errno.EROFS)
        with patch('builtins.open',side_effect=FileNotFoundError(errno.ENOENT,'absent')):
            with self.assertRaises(FileNotFoundError): g.denied_open('fixture','r+b',{errno.EROFS})

    def test_sentinel_accessible_fails_without_writing_it(self):
        opener=mock_open()
        with patch('builtins.open',opener):
            with self.assertRaises(RuntimeError): g.denied_open('fixture','r+b',{errno.ENOENT})
        opener().write.assert_not_called()

    def test_mount_flags_require_exact_mountpoint(self):
        text='1 0 8:1 / / rw,nosuid,nodev - ext4 source rw\n2 1 0:2 / /proc ro,nosuid,nodev,noexec - proc proc ro\n'
        self.assertIn('ro',g.mount_flags(text,'/proc'))
        with self.assertRaises(RuntimeError): g.mount_flags(text,'/run/devlite')

    def test_probe_mode_never_calls_apt_or_dpkg(self):
        config={'host_namespaces':{'mnt':'host'},'file_bytes':1024,'allowed_caps':[]}
        def content(path,*args,**kwargs):
            return json.dumps(config) if str(path)=='/run/devlite/transaction.json' else status()
        with patch.object(Path,'read_text',content),patch.object(g.os,'readlink',return_value='isolated'),patch.object(g.resource,'setrlimit'),patch.object(g,'probe') as probe,patch.object(g,'run') as run,patch.object(g.sys,'argv',['guest.py','--probe-only']):
            g.main();probe.assert_called_once_with(config);run.assert_not_called()

    def test_interrupt_supervisor_stops_job_and_keeps_log(self):
        with self.temp() as folder:
            process=Mock();process.poll.side_effect=KeyboardInterrupt;process.wait.return_value=0
            with patch.object(e.subprocess,'Popen',return_value=process),patch.object(e,'stop') as stop:
                with self.assertRaises(KeyboardInterrupt): e.supervise(['mock'],Path(folder),'devlite-probe-test',0)
                stop.assert_called_once_with('devlite-probe-test')
            self.assertTrue((Path(folder)/'devlite-probe-test.log').exists())

    def test_recovery_quarantines_without_mount_or_dpkg(self):
        with self.temp() as folder:
            job=Path(folder);attempt=job/'probe-attempt';attempt.mkdir()
            (attempt/'state.json').write_text(json.dumps({'state':'running_base','job_sha256':'proof'}))
            spec={'limits':LIMITS}
            real_stat=Path.stat
            def fake_stat(path,*args,**kwargs):
                value=real_stat(path,*args,**kwargs)
                if path in (attempt,attempt/'state.json'):
                    fields=list(value);fields[4]=0;return os.stat_result(fields)
                return value
            with patch.object(e,'gate',return_value=(job,spec,{})),patch.object(Path,'stat',fake_stat),patch.object(e,'stop') as stop,patch.object(e.subprocess,'run') as run:
                e.recover(job,'proof');self.assertEqual(stop.call_count,2);run.assert_not_called()
            result=json.loads((attempt/'state.json').read_text())
            self.assertEqual(result['state'],'quarantined')

    def test_host_guard_checks_apt_and_account_files(self):
        with self.temp() as folder:
            with patch.object(e,'sha',return_value='db'),patch.object(e,'critical_files',return_value={'/etc/passwd':'changed'}):
                with self.assertRaises(SpecError): e.host_guard(Path(folder),'db',{'/etc/passwd':'original'})
            self.assertTrue((Path(folder)/'host-guard.json').exists())

if __name__=='__main__': unittest.main()
