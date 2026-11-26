from contextlib import contextmanager, nullcontext
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from v7 import assemble, browser, live_installer, pack, release_gate


class WorkerTest(unittest.TestCase):
    def test_catalog_preserves_localization_and_source_id(self):
        old = pack.STACKS['base'][-1]
        text = f'- id: xubuntu-desktop-minimal\n  name:\n    pt_BR: DevLite OS 1.0\n  path: {old}\n  size: 10\n'
        updated = assemble.render_catalog(text, 7)
        self.assertIn('size: 17', updated)
        self.assertIn('pt_BR: DevLite OS 1.0', updated)
        self.assertIn('id: xubuntu-desktop-minimal', updated)
        self.assertIn(pack.LEAVES['base'], updated)

    def test_release_gate_rejects_missing_runtime_evidence(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'release.json').write_text('{"validated": {"abi": true}}')
            with patch.object(release_gate, 'INPUTS', root), patch.object(release_gate, 'trusted'):
                with self.assertRaisesRegex(ValueError, 'Incomplete'):
                    release_gate.inputs('worker')

    def test_live_reset_rejects_old_state(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / 'var/lib/snapd/state.json'
            state.parent.mkdir(parents=True)
            state.touch()
            run = Mock()
            with self.assertRaisesRegex(ValueError, 'survived'):
                live_installer.reset(root, run)
            run.assert_called_once_with(['/usr/lib/snapd/snap-preseed', '--reset-chroot'])

    def test_live_installer_restricts_socket_directory(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            live_installer.reset(root, Mock())
            self.assertIn('-g sudo -m 0750 /run/subiquity',
                          (root / live_installer.SOCKET_DROPIN).read_text())
            launcher = root / 'usr/share/applications/devlite-installer.desktop'
            self.assertIn('Exec=/' + live_installer.LAUNCHER, launcher.read_text())
            script = root / live_installer.LAUNCHER
            self.assertIn('devlite-launch-snap devlite-installer', script.read_text())
            shortcut = root / 'etc/skel/Desktop/devlite-installer.desktop'
            self.assertEqual(shortcut.read_text(), launcher.read_text())
            self.assertTrue(shortcut.stat().st_mode & 0o100)

    def test_reset_runs_inside_live_guest_and_failure_unwinds(self):
        with TemporaryDirectory() as directory:
            job = Path(directory)
            mounts = Mock(job=job)
            events = []

            @contextmanager
            def devices(_mounts, root):
                events.append(('prepare', root))
                try:
                    yield
                finally:
                    events.append(('cleanup', root))

            def run(_runner, root, args):
                events.append((args[-1], root))
                if fail and args[-1] == '--reset-chroot':
                    raise RuntimeError('reset failed')
                return ''

            with patch.object(pack, 'guest_devices', side_effect=devices), \
                    patch.object(pack, 'service_guard', return_value=nullcontext()), \
                    patch.object(pack, 'guest', side_effect=run), \
                    patch.object(pack.layers, 'apply', side_effect=lambda root, *a, **kw:
                                 events.append(('layers', root))):
                for target in ('base', 'live'):
                    root = job / target / 'root'
                    root.mkdir(parents=True)
                    fail = False
                    pack.apply_guest(mounts, root, target, job / 'seed', 'devlite-installer', 'local')
                    stages = ['prepare']
                    if target == 'live':
                        stages.append('--reset-chroot')
                    stages.extend(['layers', 'check', '--audit', 'cleanup'])
                    self.assertEqual(events, [(stage, root) for stage in stages])
                    events.clear()
                fail = True
                with self.assertRaisesRegex(RuntimeError, 'reset failed'):
                    pack.apply_guest(mounts, root, 'live', job / 'seed', 'devlite-installer', 'local')
                self.assertEqual(events, [(stage, root) for stage in
                                         ('prepare', '--reset-chroot', 'cleanup')])
                with self.assertRaisesRegex(ValueError, 'Unapproved guest root'):
                    pack.apply_guest(mounts, Path('/'), 'live', job / 'seed', 'devlite-installer', 'local')

    def test_browser_accepts_snapd_yaml_list_form(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            settings = root / 'var/lib/snapd/seed/seed.yaml'
            settings.parent.mkdir(parents=True)
            settings.write_text('snaps:\n- name: firefox\n- name: core26\n')
            # The empty fixture deliberately stops after the seed gate.
            with self.assertRaisesRegex(FileNotFoundError, 'dpkg/status'):
                browser.apply(root)
