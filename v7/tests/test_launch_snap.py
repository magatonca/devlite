import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest


class SnapLauncherTests(unittest.TestCase):
    def run_launcher(self, ready, app_status):
        original = Path('v7/overlay/usr/libexec/devlite-launch-snap')
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for name, script in {
                'systemctl': 'exit "$READY"',
                'timeout': 'shift; if [ "$READY" = 0 ] || [ "${1##*/}" = notify-send ]; then exec "$@"; fi; exit 124',
                'snap': 'echo "$*" >> "$TRACE"; if [ "$1" = run ]; then exit "$APP_STATUS"; fi',
                'notify-send': 'echo notification >> "$TRACE"',
            }.items():
                path = root / name
                path.write_text('#!/bin/sh\n' + script + '\n')
                path.chmod(0o700)
            script = original.read_text()
            for name in ('systemctl', 'timeout', 'snap', 'notify-send'):
                script = script.replace('/usr/bin/' + name, str(root / name))
            trace = root / 'trace'
            result = subprocess.run(['/bin/sh', '-s', 'devlite-installer'], input=script,
                                    text=True, capture_output=True, timeout=5,
                                    env={**os.environ, 'READY': str(ready),
                                         'APP_STATUS': str(app_status), 'TRACE': str(trace)})
            return result.returncode, trace.read_text().splitlines()

    def test_installer_does_not_query_privileged_seed_configuration(self):
        self.assertEqual(self.run_launcher(0, 0), (0, [
            'list devlite-installer', 'run devlite-installer']))

    def test_timeout_notifies_without_running_unready_snap(self):
        self.assertEqual(self.run_launcher(1, 0), (1, ['notification']))

    def test_snap_failure_notifies_and_preserves_exit_status(self):
        self.assertEqual(self.run_launcher(0, 5), (5, [
            'list devlite-installer', 'run devlite-installer', 'notification']))
