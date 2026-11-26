from pathlib import Path
import stat
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from v7.pack import guest_devices


class GuestRuntimeTest(unittest.TestCase):
    def exercise(self, root, target, valid):
        for name in ('run', 'var/tmp', 'tmp', 'dev', 'sys', 'proc'):
            (root / name).mkdir(parents=True)
        (root / 'var/lock').symlink_to(target)
        events = []

        class Mounts:
            paths = []

            def mount(self, label, args, path):
                events.append(('mount', path))
                self.paths.append(path)

            def unmount(self, path):
                events.append(('unmount', path))
                self.paths.pop()

        mounts = Mounts()
        with patch('v7.pack.os.mknod', side_effect=lambda path, *_: path.touch()), \
                patch('v7.pack.os.chown') as chown:
            if valid:
                with guest_devices(mounts, root):
                    lock = root / 'run/lock'
                    self.assertEqual(stat.S_IMODE(lock.stat().st_mode), 0o1777)
                    self.assertEqual(stat.S_IMODE((root / 'run/apache2').stat().st_mode), 0o755)
                    chown.assert_any_call(lock, 0, 0)
            else:
                with self.assertRaisesRegex(ValueError, '/var/lock'):
                    with guest_devices(mounts, root):
                        self.fail('Unsafe lock path was accepted')
                chown.assert_not_called()
        mounted = [path for action, path in events if action == 'mount']
        unmounted = [path for action, path in events if action == 'unmount']
        self.assertEqual(unmounted, mounted[::-1])
        self.assertFalse(mounts.paths)

    def test_private_lock_modes_and_unmount_order(self):
        with TemporaryDirectory() as directory:
            self.exercise(Path(directory), '/run/lock', True)

    def test_rejects_external_lock_and_cleans_partial_setup(self):
        with TemporaryDirectory() as directory:
            self.exercise(Path(directory), '/outside/lock', False)
