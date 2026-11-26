import copy
import hashlib
import importlib.util
import json
import stat
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from pipeline.devlite.customize.manifest import SpecError
from pipeline.devlite.runtime import BuildError


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/gerar-iso-modern-candidata.py'
SPEC = importlib.util.spec_from_file_location('modern_candidate_iso_test', SCRIPT)
ISO = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ISO)


def receipt():
    return {
        'job_sha256': 'a' * 64,
        'status': 'layers_verified',
        'kernel_composition_verified': True,
        'roundtrip_verified': True,
        'source_metadata_unchanged': True,
        'host_critical_unchanged': True,
        'iso_generated': False,
        'layers': {
            'minimal.squashfs': {'sha256': '1' * 64},
            'minimal.live.squashfs': {'sha256': '2' * 64},
        },
        'package_states': {
            'base': {'base-package': '1.0'},
            'live': {'base-package': '1.0', 'live-package': '2.0'},
        },
    }


def report():
    return {
        'status': 'layers_verified',
        'contract_sha256': 'a' * 64,
        'source_images_modified': False,
        'iso_generated': False,
        'target_programs_executed': False,
        'cleanup_errors': [],
        'layers': receipt()['layers'],
        'package_compatibility': {
            'base_packages_missing_live': [],
            'common_version_conflicts': {},
        },
        'results': {
            target: {
                'package_count': count,
                'file_audit': {
                    'only_declared_additions': True,
                    'target_programs_executed': False,
                    'before_tree_sha256': '3' * 64,
                    'after_tree_sha256': '4' * 64,
                },
            }
            for target, count in (('base', 1), ('live', 2))
        },
    }


class ModernCandidateISOTests(unittest.TestCase):
    def test_accepts_pack_report_and_layer_receipt_from_same_verified_contract(self):
        ISO.validate_pack_report(report(), receipt(), 'a' * 64)

    def test_rejects_receipts_not_bound_to_successful_audited_pack(self):
        invalid_cases = (
            ('wrong contract', lambda r, p: r.update(contract_sha256='b' * 64)),
            ('failed cleanup', lambda r, p: r.update(cleanup_errors=['mount left behind'])),
            ('missing layer roundtrip', lambda r, p: p.update(roundtrip_verified=False)),
            ('modified source', lambda r, p: r.update(source_images_modified=True)),
            ('layer digest mismatch', lambda r, p: r['layers']['minimal.squashfs'].update(
                sha256='f' * 64,
            )),
            ('package conflict', lambda r, p: r['package_compatibility'].update(
                common_version_conflicts={'pkg': ['1', '2']},
            )),
            ('unverified tree audit', lambda r, p: r['results']['live']['file_audit'].update(
                only_declared_additions=False,
            )),
            ('missing tree digest', lambda r, p: r['results']['base']['file_audit'].update(
                after_tree_sha256='not-a-digest',
            )),
            ('package count mismatch', lambda r, p: r['results']['base'].update(
                package_count=0,
            )),
        )
        for label, mutate in invalid_cases:
            with self.subTest(label=label):
                current_report, current_receipt = copy.deepcopy(report()), copy.deepcopy(receipt())
                mutate(current_report, current_receipt)
                with self.assertRaises(BuildError):
                    ISO.validate_pack_report(
                        current_report, current_receipt, 'a' * 64,
                    )

    def test_ready_layer_reader_rejects_changed_published_artifacts(self):
        with TemporaryDirectory(prefix='modern-pack-layer-reader-') as temp:
            job = Path(temp)
            published = job / 'published-casper'
            published.mkdir()
            files = {}
            for name in ISO.REQUIRED:
                path = published / name
                path.write_bytes(('approved:' + name).encode())
                files[name] = ISO.sha(path)
            approval = 'a' * 64
            sealed_receipt = {
                'job_sha256': approval,
                'status': 'layers_verified',
                'kernel_composition_verified': True,
                'roundtrip_verified': True,
                'published': str(published),
                'files': files,
            }
            receipt_path = job / 'layers-ready.json'
            receipt_path.write_text(json.dumps(sealed_receipt), encoding='utf-8')
            real_stat = Path.stat

            def root_owned_receipt(path, *args, **kwargs):
                if path == receipt_path:
                    return SimpleNamespace(
                        st_uid=0, st_mode=stat.S_IFREG | 0o444,
                    )
                return real_stat(path, *args, **kwargs)

            with patch.object(Path, 'stat', root_owned_receipt):
                self.assertEqual(ISO.ready_layers(job, approval), sealed_receipt)
                (published / 'minimal.squashfs').write_bytes(b'tampered')
                with self.assertRaisesRegex(SpecError, 'Payload alterado'):
                    ISO.ready_layers(job, approval)

    def test_assembly_budget_includes_source_replay_layers_and_reserve(self):
        with TemporaryDirectory() as directory:
            published = Path(directory)
            (published / 'minimal.squashfs').write_bytes(b'base-layer')
            (published / 'minimal.live.squashfs').write_bytes(b'live-layer')
            expected = (
                2 * 100 + 3 * (len(b'base-layer') + len(b'live-layer'))
                + 3 * ISO.LAYER_MAX_BYTES + ISO.RESERVE
            )
            self.assertEqual(ISO.required_assembly_bytes(100, published), expected)

    def test_v3_contract_revalidates_visual_inputs_before_accepting_the_job(self):
        input_validation = {
            'base_config_sha256': '1' * 64,
            'wallpaper_sha256': '2' * 64,
            'visual_config_sha256': '3' * 64,
            'base_os_release_sha256': '4' * 64,
            'visual_os_release_sha256': '5' * 64,
            'devlite_icon_sha256': '6' * 64,
            'plymouth_default_source':
                '/usr/share/plymouth/themes/xubuntu-logo/xubuntu-logo.plymouth',
            'plymouth_text_source':
                '/usr/share/plymouth/themes/xubuntu-text/xubuntu-text.plymouth',
            'plymouth_theme_sha256': '7' * 64,
            'live_config_override': False,
            'live_plymouth_override': False,
        }
        visual_layer = ISO.visual_layer_profile(input_validation)
        with TemporaryDirectory(
                prefix='modern-candidate-iso-test-', dir=ROOT / 'work') as temp:
            job = Path(temp)
            pack = job / 'pack-fixture'
            pack.mkdir()
            (pack / 'contract.json').write_text('{}', encoding='utf-8')
            (pack / 'layers-ready.json').write_text('{}', encoding='utf-8')
            receipt = {'files': {'minimal.squashfs': 'a' * 64}}
            contract = {
                'schema': 3, 'operation': 'modern-candidate-iso-v3',
                'job': str(job), 'reserve_bytes': ISO.RESERVE,
                'release_approved': False,
                'pack_job': str(pack), 'pack_approval': 'b' * 64,
                'pack_contract_sha256': 'c' * 64,
                'layers_receipt_sha256': 'd' * 64,
                'layer_files': receipt['files'],
                'source_iso_sha256': ISO.EXPECTED,
                'approved_iso_sha256': 'e' * 64,
                'visual_layer': copy.deepcopy(visual_layer),
                'required_assembly_bytes': 123,
                'code_sha256': {}, 'references_sha256': {},
            }
            contract_path = job / 'contract.json'
            contract_path.write_text(json.dumps(contract), encoding='utf-8')
            real_sha = ISO.sha

            def fake_sha(path):
                path = Path(path)
                if path == contract_path:
                    return real_sha(path)
                return {
                    pack / 'contract.json': 'c' * 64,
                    pack / 'layers-ready.json': 'd' * 64,
                    ISO.SOURCE_ISO: ISO.EXPECTED,
                    ISO.BASELINE: 'e' * 64,
                }[path]

            with (
                patch.object(ISO, 'sha', side_effect=fake_sha),
                patch.object(ISO, 'verified_pack', return_value=(pack, {}, {}, receipt)),
                patch.object(
                    ISO, 'preflight_visual_sources',
                    side_effect=lambda *args: copy.deepcopy(input_validation),
                ),
                patch.object(ISO, 'required_assembly_bytes', return_value=123),
            ):
                approval = real_sha(contract_path)
                self.assertEqual(ISO.read_iso_job(job, approval)[1]['visual_layer'],
                                 visual_layer)

                contract['visual_layer']['input_validation']['wallpaper_sha256'] = 'f' * 64
                contract_path.write_text(json.dumps(contract), encoding='utf-8')
                with self.assertRaisesRegex(BuildError, 'Perfil da camada visual'):
                    ISO.read_iso_job(job, real_sha(contract_path))


if __name__ == '__main__':
    unittest.main()
