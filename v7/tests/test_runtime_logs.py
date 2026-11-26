import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

from pipeline.devlite.runtime import Runner


class RunnerLogTest(unittest.TestCase):
    def test_guest_path_and_equivalent_labels_get_distinct_logs(self):
        with TemporaryDirectory() as directory:
            logs = Path(directory)
            runner = Runner(logs, 0)
            for label, stem in [
                ('guest-var/tmp', '01-guest-var-tmp'),
                ('guest-var-tmp', '02-guest-var-tmp'),
                ('guest-var\\tmp', '03-guest-var-tmp'),
                ('../guest.foo/../../tmp', '04-guest-foo-tmp'),
            ]:
                args = [sys.executable, '-c', f'print({label!r})']
                self.assertEqual(runner.run(label, args), label + '\n')
                self.assertEqual(json.loads((logs / f'{stem}.command.json').read_text()), args)
                self.assertEqual((logs / f'{stem}.stdout').read_text(), label + '\n')
                self.assertTrue((logs / f'{stem}.stderr').is_file())
            self.assertEqual(len(list(logs.iterdir())), 12)
            self.assertTrue(all(path.is_file() for path in logs.iterdir()))

    def test_existing_log_cannot_be_overwritten_or_followed(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            logs = root / 'logs'
            logs.mkdir()
            evidence = root / 'evidence'
            evidence.write_text('preserve')
            (logs / '01-guest-var-tmp.stdout').symlink_to(evidence)
            marker = root / 'executed'
            args = [sys.executable, '-c', f'open({str(marker)!r}, "w").close()']
            with self.assertRaises(FileExistsError):
                Runner(logs, 0).run('guest-var/tmp', args)
            self.assertEqual(evidence.read_text(), 'preserve')
            self.assertFalse(marker.exists())
