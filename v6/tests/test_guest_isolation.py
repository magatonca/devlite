import os
import runpy
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from v6 import guest_probe, pack


class GuestIsolationTests(unittest.TestCase):
    def guest(self, runner):
        with patch.dict(sys.modules, {'guest_runner': runner}):
            return runpy.run_path(str(pack.ROOT / 'v6/guest.py'))

    def test_only_loopback_and_both_socket_families(self):
        guest = self.guest(Mock())
        net = 'headers\nheaders\n lo: 0\n'
        with patch.object(Path, 'read_text', return_value=net), patch.object(
                socket, 'socket') as create:
            guest['check_loopback']()
        self.assertEqual([call.args for call in create.call_args_list],
                         [(socket.AF_INET, socket.SOCK_STREAM),
                          (socket.AF_INET6, socket.SOCK_STREAM)])
        with patch.object(Path, 'read_text', return_value=net + ' eth0: 0\n'), patch.object(
                socket, 'socket') as create:
            with self.assertRaisesRegex(SystemExit, 'Unexpected guest network'):
                guest['check_loopback']()
            create.assert_not_called()

    def test_apache_and_mandb_errors_block_guest(self):
        for command in ('/usr/sbin/apache2ctl', '/usr/bin/setpriv'):
            with self.subTest(command=command):
                def run(args):
                    if args[0] == command:
                        raise RuntimeError('command failed')
                    return ''
                runner = Mock()
                runner.run.side_effect = run
                guest = self.guest(runner)
                with patch.dict(guest['validate'].__globals__, {'check_loopback': Mock()}):
                    with self.assertRaisesRegex(RuntimeError, 'command failed'):
                        guest['validate']()
                expected = ['/usr/sbin/apache2ctl', '-t'] if command.endswith('apache2ctl') else [
                    '/usr/bin/setpriv', '--reuid', 'man', '--regid', 'man', '--init-groups',
                    '--', '/usr/bin/mandb', '-pq',
                ]
                runner.run.assert_any_call(expected)

    def test_ssh_uses_ephemeral_key_and_cleans_up_on_success_or_failure(self):
        for failure in (None, 'keygen', '-t', '-T', 'policy'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as workspace:
                runner = Mock()
                guest = self.guest(runner)
                real_temp = tempfile.TemporaryDirectory
                locations = []

                def temp(*, prefix, dir):
                    self.assertEqual(dir, '/run')
                    directory = real_temp(prefix=prefix, dir=workspace)
                    self.assertEqual(os.stat(directory.name).st_mode & 0o777, 0o700)
                    locations.append(Path(directory.name))
                    return directory

                def run(args):
                    if args[0] == '/usr/bin/ssh-keygen':
                        key = Path(args[args.index('-f') + 1])
                        self.assertEqual(key.parent, locations[0])
                        key.touch(mode=0o600)
                        key.with_suffix('.pub').touch()
                        if failure == 'keygen':
                            raise RuntimeError('injected failure')
                        return ''
                    self.assertEqual(args[0], '/usr/sbin/sshd')
                    self.assertIn(args[1], ('-t', '-T'))
                    self.assertEqual(args[args.index('-f') + 1], '/etc/ssh/sshd_config')
                    self.assertTrue(Path(args[args.index('-h') + 1]).is_file())
                    if failure == args[1]:
                        raise RuntimeError('injected failure')
                    if args[1] == '-T':
                        self.assertIn('user=root', args[-1])
                    return 'permitrootlogin ' + ('yes' if failure == 'policy' else 'no') + '\npermitemptypasswords no'

                runner.run.side_effect = run
                with patch.object(tempfile, 'TemporaryDirectory', side_effect=temp):
                    if failure == 'policy':
                        with self.assertRaisesRegex(SystemExit, 'Unexpected SSH policy'):
                            guest['validate_ssh']()
                    elif failure:
                        with self.assertRaisesRegex(RuntimeError, 'injected failure'):
                            guest['validate_ssh']()
                    else:
                        guest['validate_ssh']()
                self.assertEqual(len(locations), 1)
                self.assertFalse(locations[0].exists())

    def test_upper_adopts_reference_mode_without_opening_job(self):
        with tempfile.TemporaryDirectory() as directory:
            job = Path(directory)
            upper = job / 'upper'
            upper.mkdir(mode=0o700)
            reference = Mock()
            reference.lstat.return_value = SimpleNamespace(st_mode=0o40755, st_uid=0, st_gid=0)
            pack.prepare_upper_root(reference, upper)
            self.assertEqual(upper.stat().st_mode & 0o777, 0o755)
            self.assertEqual(job.stat().st_mode & 0o777, 0o700)
            reference.lstat.return_value.st_mode = 0o40777
            with self.assertRaisesRegex(ValueError, 'Unexpected inherited'):
                pack.prepare_upper_root(reference, upper)

    def test_probe_rejects_path_traversal_and_preserves_launcher_isolation(self):
        for bad in ('../pack-_kl0txm8', '/var/lib/devlite-v6/pack-_kl0txm8'):
            with self.assertRaisesRegex(ValueError, 'Expected a pack ID'):
                guest_probe.probe_inputs(bad)
        script = (pack.ROOT / 'v6/build-manual.sh').read_text()
        for setting in ('PrivateNetwork=yes', 'PrivateMounts=yes', 'NoNewPrivileges=yes',
                        'RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6',
                        'ProtectKernelTunables=yes', 'ProtectHome=read-only'):
            self.assertIn(setting, script)
        self.assertNotIn('CAP_NET_ADMIN', script)
