import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from v7 import release_gate, seed
from v7.seed import BROWSER, FIREFOX_ID, read_seed


class SeedTests(unittest.TestCase):
    def set_up_seed(self, root):
        (root / 'snaps').mkdir()
        entries = [{'name': name,
                    'snap-id': FIREFOX_ID if name == 'firefox' else 'fixture',
                    'file': name + '_1.snap'} for name in sorted(BROWSER)]
        for snap in entries:
            (root / 'snaps' / snap['file']).touch()
        return entries

    def test_seed_rejects_unasserted_revision_and_classic_firefox(self):
        with tempfile.TemporaryDirectory() as path:
            root = Path(path)
            entries = self.set_up_seed(root)
            filename = root / 'seed.yaml'
            def write():
                filename.write_text(yaml.safe_dump({'snaps': entries}))
            write()
            self.assertEqual(read_seed(root)[1].keys(), BROWSER)
            firefox = next(snap for snap in entries if snap['name'] == 'firefox')
            firefox['classic'] = True
            write()
            with self.assertRaisesRegex(ValueError, 'official confined'):
                read_seed(root)
            firefox.pop('classic')
            firefox['file'] = 'firefox_x1.snap'
            write()
            with self.assertRaisesRegex(ValueError, 'numeric revision'):
                read_seed(root)

    def test_local_seed_is_hash_pinned_and_live_only(self):
        with tempfile.TemporaryDirectory() as path:
            root = Path(path)
            entries = self.set_up_seed(root)
            for entry in ({'name': 'core22', 'snap-id': 'fixture', 'file': 'core22_1.snap'},
                          dict(seed.LOCAL_ENTRY)):
                entries.append(entry)
                (root / 'snaps' / entry['file']).write_bytes(b'approved')
            config = root / 'seed.yaml'

            def save():
                config.write_text(yaml.safe_dump({'snaps': entries}))

            save()
            expected = hashlib.sha256(b'approved').hexdigest()
            with patch.object(seed, 'LOCAL_SHA256', expected):
                _, result = read_seed(root, seed.LOCAL_NAME, local=True)
                self.assertEqual(result[seed.LOCAL_NAME], seed.LOCAL_ENTRY)
                with self.assertRaisesRegex(ValueError, 'unasserted'):
                    read_seed(root, seed.LOCAL_NAME)
                with self.assertRaisesRegex(ValueError, 'Live'):
                    read_seed(root, local=True)
                entries[-1]['snap-id'] = 'fake'
                save()
                with self.assertRaisesRegex(ValueError, 'seed entry'):
                    read_seed(root, seed.LOCAL_NAME, local=True)
                del entries[-1]['snap-id']
                entries[0]['unasserted'] = True
                save()
                with self.assertRaisesRegex(ValueError, 'unasserted'):
                    read_seed(root, seed.LOCAL_NAME, local=True)
                del entries[0]['unasserted']
                save()
                (root / 'snaps' / seed.LOCAL_ENTRY['file']).write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError, 'SHA-256'):
                    read_seed(root, seed.LOCAL_NAME, local=True)

    def test_local_receipt_cannot_approve_distribution(self):
        with tempfile.TemporaryDirectory() as path:
            root = Path(path)
            for name in ('base-seed', 'live-seed'):
                (root / name).mkdir()
            record = {
                'installer_mode': 'local', 'installer_sha256': seed.LOCAL_SHA256,
                'authorization': dict(release_gate.LOCAL_ACK),
                'validated': dict.fromkeys(release_gate.LOCAL_CHECKS, True),
                'worker_sha256': 'worker',
            }
            receipt = root / 'release.json'
            receipt.write_text(json.dumps(record))
            with patch.object(release_gate, 'INPUTS', root), patch.object(release_gate, 'trusted'), \
                    patch.object(seed, 'validate') as validate:
                self.assertEqual(release_gate.inputs('worker')[-1], 'local')
                validate.assert_called_with(root / 'live-seed', seed.LOCAL_NAME, local=True)
                record['authorization']['distribution_approved'] = True
                receipt.write_text(json.dumps(record))
                with self.assertRaisesRegex(ValueError, 'local candidate authorization'):
                    release_gate.inputs('worker')

    def test_store_route_requires_assertions_and_full_validation(self):
        with tempfile.TemporaryDirectory() as path:
            root = Path(path)
            for name in ('base-seed', 'live-seed'):
                (root / name / 'snaps').mkdir(parents=True)
            artifact = root / 'live-seed/snaps/devlite-installer_1.snap'
            artifact.write_bytes(b'asserted')
            record = {'installer_mode': 'store', 'installer_snap_id': 'store-id',
                      'installer_sha256': hashlib.sha256(b'asserted').hexdigest(),
                      'validated': dict.fromkeys(release_gate.REQUIRED_CHECKS, True),
                      'worker_sha256': 'worker'}
            receipt = root / 'release.json'
            receipt.write_text(json.dumps(record))
            entries = {seed.LOCAL_NAME: {'snap-id': 'store-id', 'classic': True,
                                        'file': artifact.name}}
            with patch.object(release_gate, 'INPUTS', root), patch.object(release_gate, 'trusted'), \
                    patch.object(seed, 'validate') as native, \
                    patch.object(seed, 'read_seed', return_value=(None, entries)):
                self.assertEqual(release_gate.inputs('worker')[-1], 'store')
                native.assert_called_with(root / 'live-seed', seed.LOCAL_NAME, local=False)
                with self.assertRaisesRegex(ValueError, 'does not match'):
                    release_gate.inputs('changed')
                record['validated'].pop('backend_socket')
                receipt.write_text(json.dumps(record))
                with self.assertRaisesRegex(ValueError, 'Incomplete'):
                    release_gate.inputs('worker')
