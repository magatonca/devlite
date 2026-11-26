import builtins
import copy
import importlib.util
import json
import shutil
import symtable
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pipeline.devlite import modern_candidate_root as worker
from pipeline.devlite import modern_candidate as candidate_contract
from pipeline.devlite.modern_candidate_root import (
    pin_existing_modern,
    pin_installer,
    package_compatibility,
    require_package_status,
    validate_candidate_payload_bundle,
)
from pipeline.devlite.modern_candidate import (
    CHECKPOINT_SHARED_REFERENCE_FILES,
    HOST_BASELINE_REFERENCE,
    HOST_BASELINE_SHA256,
    HOST_BASELINE_ID,
    REFERENCE_FILES,
    SOURCE,
    checkpoint_contract_mismatches,
    load_host_baseline,
    load_host_baseline_v3,
    validate_host_baseline,
    validate_host_baseline_v3,
)
from pipeline.devlite.public_apply import validate_payload


ROOT = Path(__file__).resolve().parents[1]
PACKER_PATH = ROOT / 'scripts/empacotar-modern-candidata.py'
HANDOFF_PATH = ROOT / 'scripts/iniciar-modern-candidata-root.py'


def load_packer():
    spec = importlib.util.spec_from_file_location('modern_candidate_packer_test', PACKER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_handoff():
    spec = importlib.util.spec_from_file_location('modern_candidate_handoff_test', HANDOFF_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ModernCandidateTests(unittest.TestCase):
    def test_historical_pack_reader_does_not_weaken_current_pack_code_seal(self):
        code_path = 'pipeline/devlite/modern_identity.py'
        historical = {
            'code_sha256': {code_path: '0' * 64},
        }
        approved_pack = (Path('/sealed-pack'), historical, {})
        with patch.object(
                candidate_contract, '_read_pack_job', return_value=approved_pack):
            self.assertEqual(
                candidate_contract.read_approved_pack_for_iso(
                    '/sealed-pack', 'a' * 64, root=True,
                ),
                approved_pack,
            )
            with self.assertRaisesRegex(ValueError, 'Código selado alterado'):
                candidate_contract.read_job(
                    '/sealed-pack', 'a' * 64, root=True,
                )

    def test_historical_pack_reader_rejects_malformed_code_provenance(self):
        malformed = {
            'code_sha256': {
                'pipeline/devlite/modern_identity.py': 'not-a-sha256',
            },
        }
        with patch.object(
                candidate_contract, '_read_pack_job',
                return_value=(Path('/sealed-pack'), malformed, {})):
            with self.assertRaisesRegex(
                    ValueError, 'Manifesto de código selado inválido'):
                candidate_contract.read_approved_pack_for_iso(
                    '/sealed-pack', 'a' * 64, root=True,
                )

    def test_historical_pack_reader_rejects_an_unapproved_contract_digest(self):
        with tempfile.TemporaryDirectory(
                prefix='modern-candidate-pack-test-', dir=ROOT / 'work') as temp:
            job = Path(temp)
            (job / 'contract.json').write_text('{}', encoding='utf-8')
            with self.assertRaisesRegex(
                    ValueError, 'Contrato de build divergente'):
                candidate_contract.read_approved_pack_for_iso(
                    job, '0' * 64, root=True,
                )

    def test_packaging_entrypoints_have_no_unresolved_global_names(self):
        paths = (
            ROOT / 'pipeline/devlite/modern_candidate_root.py',
            HANDOFF_PATH,
            PACKER_PATH,
        )
        builtin_names = set(vars(builtins)) | {'__name__', '__file__', '__package__'}
        for path in paths:
            with self.subTest(path=path.name):
                source = path.read_text()
                top = symtable.symtable(source, path.name, 'exec')
                module_names = {
                    symbol.get_name() for symbol in top.get_symbols()
                    if symbol.is_assigned() or symbol.is_imported()
                }
                unresolved = []

                def inspect(table):
                    for symbol in table.get_symbols():
                        if (symbol.is_global() and symbol.is_referenced()
                                and symbol.get_name() not in module_names | builtin_names):
                            unresolved.append((table.get_name(), symbol.get_name()))
                    for child in table.get_children():
                        inspect(child)

                inspect(top)
                self.assertEqual(unresolved, [])

    @unittest.skipUnless(
        shutil.which('mksquashfs') and shutil.which('unsquashfs'),
        'SquashFS tools absent',
    )
    def test_base_squashfs_roundtrip_excludes_executor_runtime_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            runtime = source / 'var/lib/devlite-executor/lists'
            runtime.mkdir(parents=True)
            (runtime / 'partial').mkdir()
            (source / 'etc').mkdir()
            (source / 'etc/example').write_text('preserved\n')
            expected = worker.clean_snapshot(worker.snapshot(source))
            image = root / 'minimal.squashfs'
            args = worker.layer_compress_args(
                'minimal.squashfs', source, image, expected['.'],
            )
            args[args.index('256M')] = '32M'
            subprocess.run(args, check=True, capture_output=True)

            extracted = root / 'extracted'
            subprocess.run(
                ['unsquashfs', '-strict-errors', '-processors', '1',
                 '-d', str(extracted), str(image)],
                check=True, capture_output=True,
            )
            self.assertEqual(worker.snapshot(extracted), expected)

    def test_layer_compression_rejects_unknown_squashfs_names(self):
        with self.assertRaisesRegex(RuntimeError, 'não suportada'):
            worker.layer_compress_args(
                'unexpected.squashfs', Path('/source'), Path('/image'), {},
            )

    def test_source_root_is_derived_from_pinned_image_paths(self):
        source_root = worker.source_root_from_contract({
            'source_images': worker.SOURCE_IMAGES,
        })
        self.assertEqual(
            source_root,
            ROOT / 'work/modern-apply-5w334rzl',
        )

    def test_host_baseline_v2_accepts_only_the_authorized_status_transition(self):
        baseline = load_host_baseline()
        previous = baseline['supersedes']['host_critical_files']
        current = baseline['current_host_critical_files']
        self.assertEqual(baseline['baseline_id'], HOST_BASELINE_ID)
        self.assertEqual(
            validate_host_baseline(
                baseline, previous, current,
            ),
            current,
        )

        altered = {
            **baseline,
            'current_host_critical_files': {
                **current, '/etc/passwd': '0' * 64,
            },
        }
        with self.assertRaisesRegex(ValueError, 'divergências além'):
            validate_host_baseline(altered, previous, current)

    def test_host_baseline_v3_accepts_only_the_authorized_gtk_xvfb_transition(self):
        baseline_v2 = load_host_baseline()
        baseline_v3 = load_host_baseline_v3()
        previous = baseline_v2['current_host_critical_files']
        current = baseline_v3['current_host_critical_files']
        self.assertEqual(
            validate_host_baseline_v3(
                baseline_v3, previous, current,
            ),
            current,
        )

        with self.assertRaisesRegex(ValueError, 'Arquivos críticos atuais'):
            validate_host_baseline_v3(
                baseline_v3, previous, {**current, '/var/lib/dpkg/status': '0' * 64},
            )

        altered = copy.deepcopy(baseline_v3)
        altered['current_host_critical_files']['/etc/passwd'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'divergências além'):
            validate_host_baseline_v3(altered, previous, current)

        altered = copy.deepcopy(baseline_v3)
        altered['authorized_host_transition']['changed_host_critical_paths'].append(
            '/etc/passwd',
        )
        with self.assertRaisesRegex(ValueError, 'divergências além'):
            validate_host_baseline_v3(altered, previous, current)

        altered = copy.deepcopy(baseline_v3)
        altered['authorized_host_transition']['evidence_report']['sha256'] = 'f' * 64
        with self.assertRaisesRegex(ValueError, 'divergências além'):
            validate_host_baseline_v3(altered, previous, current)

        altered = copy.deepcopy(baseline_v3)
        altered['target_artifacts_unchanged']['base_squashfs_sha256'] = 'f' * 64
        with self.assertRaisesRegex(ValueError, 'Evidência da transição'):
            validate_host_baseline_v3(altered, previous, current)

    def checkpoint_contracts_for_v1_to_v2(self):
        baseline = load_host_baseline()
        shared_references = {
            name: f'{index:064x}'
            for index, name in enumerate(sorted(CHECKPOINT_SHARED_REFERENCE_FILES), 1)
        }
        source_images = {
            'base': {'file': '/source/base.ext4', 'sha256': '1' * 64},
            'live': {'file': '/source/live.ext4', 'sha256': '2' * 64},
        }
        bundle = {'base/usr/bin/tool': '3' * 64, 'live/usr/bin/tool': '4' * 64}
        checkpoint_job = '/workspace/work/modern-candidate-pack-checkpoint'
        previous = {
            'job': checkpoint_job,
            'operation': 'modern-candidate-pack-v1',
            'source_approval': 'accepted-source',
            'source_result_sha256': '5' * 64,
            'source_images': source_images,
            'bundle_sha256': bundle,
            'payload_manifest_sha256': '6' * 64,
            'reference_sha256': shared_references,
            'host_critical_files': baseline['supersedes']['host_critical_files'],
            'code_sha256': {'pipeline/devlite/modern_candidate_root.py': '7' * 64},
        }
        current = {
            'source_approval': previous['source_approval'],
            'source_result_sha256': previous['source_result_sha256'],
            'source_images': copy.deepcopy(source_images),
            'bundle_sha256': copy.deepcopy(bundle),
            'payload_manifest_sha256': previous['payload_manifest_sha256'],
            'reference_sha256': {
                **shared_references, HOST_BASELINE_REFERENCE: HOST_BASELINE_SHA256,
            },
            'host_baseline': {
                'id': HOST_BASELINE_ID,
                'file': HOST_BASELINE_REFERENCE,
                'sha256': HOST_BASELINE_SHA256,
            },
            'host_critical_files': baseline['current_host_critical_files'],
            'code_sha256': {'pipeline/devlite/modern_candidate_root.py': '8' * 64},
        }
        checkpoint = {
            'job': checkpoint_job,
            'approval_sha256': '9' * 64,
            'contract_sha256': '9' * 64,
            'report_sha256': 'a' * 64,
            'worker_sha256': '7' * 64,
        }
        return previous, checkpoint, current

    def test_checkpoint_contract_accepts_only_v1_to_v2_host_transition(self):
        previous, checkpoint, current = self.checkpoint_contracts_for_v1_to_v2()
        self.assertEqual(
            checkpoint_contract_mismatches(previous, checkpoint, current),
            (),
        )

    def test_checkpoint_contract_rejects_artifact_plan_and_transition_changes(self):
        mutations = (
            ('source_images', lambda value: value['source_images']['base'].update(
                sha256='f' * 64,
            ), 'source_images'),
            ('bundle_sha256', lambda value: value['bundle_sha256'].update(
                {'base/extra': 'f' * 64},
            ), 'bundle_sha256'),
            ('payload_manifest_sha256', lambda value: value.update(
                payload_manifest_sha256='f' * 64,
            ), 'payload_manifest_sha256'),
            ('package_plan', lambda value: value['reference_sha256'].update(
                {'work/release-browser-2f24tvsg/plan.json': 'f' * 64},
            ), 'reference_sha256:work/release-browser-2f24tvsg/plan.json'),
            ('host_change', lambda value: value['host_critical_files'].update(
                {'/etc/passwd': 'f' * 64},
            ), 'host_baseline_transition'),
        )
        for name, mutate, expected in mutations:
            with self.subTest(name=name):
                previous, checkpoint, current = self.checkpoint_contracts_for_v1_to_v2()
                target = previous if name == 'host_change' else current
                mutate(target)
                self.assertIn(
                    expected,
                    checkpoint_contract_mismatches(previous, checkpoint, current),
                )

    def test_checkpoint_reference_sets_keep_all_non_host_artifacts_sealed(self):
        previous, checkpoint, current = self.checkpoint_contracts_for_v1_to_v2()
        self.assertEqual(
            set(previous['reference_sha256']),
            CHECKPOINT_SHARED_REFERENCE_FILES,
        )
        self.assertEqual(set(current['reference_sha256']), set(REFERENCE_FILES))
        current['reference_sha256']['work/phase4b1-dhzezpnz/original-casper/filesystem.manifest'] = 'f' * 64
        self.assertIn(
            'reference_sha256:work/phase4b1-dhzezpnz/original-casper/filesystem.manifest',
            checkpoint_contract_mismatches(previous, checkpoint, current),
        )

    def test_accepted_images_validate_through_host_baseline_v2(self):
        packer = load_packer()
        baseline = load_host_baseline()
        with patch.object(
                packer, 'critical_files',
                return_value=baseline['current_host_critical_files']):
            result = packer.accepted_source(baseline)
        self.assertEqual(result['status'], 'modern_full_views_verified')
        self.assertEqual(
            worker.sha(SOURCE / 'contract.json'),
            worker.SOURCE_APPROVAL,
        )

    def test_preflight_reaches_first_operation_without_touching_images(self):
        class StopAtFirstOperation(Exception):
            pass

        job_name = 'modern-candidate-pack-integration'
        with tempfile.TemporaryDirectory() as directory:
            job = Path(directory) / job_name
            job.mkdir()
            critical = {'/host-critical-file': 'fixture-hash'}
            host_namespaces = {
                name: 'host:' + name for name in ('mnt', 'pid', 'net', 'ipc', 'uts')
            }
            contract = {
                'host_critical_files': critical,
                'host_namespaces': host_namespaces,
                'source_images': worker.SOURCE_IMAGES,
                'initial_required_bytes': 1,
            }
            commands = []
            filesystem_calls = []

            class BoundaryRunner:
                def __init__(self, _logs, _epoch):
                    self.env = {}

                def run(self, label, argv):
                    commands.append((label, argv))
                    raise StopAtFirstOperation()

            original_read_text = Path.read_text

            def read_runtime_file(path, *args, **kwargs):
                if path == Path('/proc/self/cgroup'):
                    return (
                        '0::/system.slice/devlite-' + job_name + '.service\n'
                    )
                if path == Path('/proc/self/status'):
                    return 'NoNewPrivs:\t1\n'
                if path == Path('/proc/self/mountinfo'):
                    return 'fixture mountinfo\n'
                if path == Path('/proc/net/dev'):
                    return 'Inter-| Receive | Transmit\n face | counters\n lo: 0 0\n'
                return original_read_text(path, *args, **kwargs)

            def record_filesystem(mountinfo, checked_job, extra):
                filesystem_calls.append((mountinfo, checked_job, extra))
                return {}

            with (
                patch.object(worker.os, 'geteuid', return_value=0),
                patch.object(worker.os, 'getpid', return_value=1),
                patch.object(worker.os, 'readlink', side_effect=lambda value: 'isolated:' + value),
                patch.object(worker.os, 'chown'),
                patch.object(worker, 'read_job', return_value=(job, contract, {})),
                patch.object(worker, 'critical_files', return_value=critical),
                patch.object(worker, 'cgroup_limits', return_value={'memory.max': 'ok'}),
                patch.object(worker, 'filesystem_proof', side_effect=record_filesystem),
                patch.object(worker.shutil, 'disk_usage', return_value=SimpleNamespace(free=100 * 1024**3)),
                patch.object(worker, 'Runner', BoundaryRunner),
                patch.object(Path, 'read_text', new=read_runtime_file),
            ):
                with self.assertRaises(StopAtFirstOperation):
                    worker.run(job, 'a' * 64, authorized=True)

            self.assertEqual(commands, [
                ('private-mounts', ['mount', '--make-rprivate', '/']),
            ])
            self.assertEqual(filesystem_calls[0][1], job)
            self.assertEqual(
                filesystem_calls[0][2][-2:],
                (
                    str(ROOT / 'work/modern-apply-5w334rzl'),
                    str(ROOT / 'config/modern-host-baseline-v2.json'),
                ),
            )
            self.assertFalse((job / 'attempt/base.ext4').exists())
            report = json.loads((job / 'pack-report.json').read_text())
            self.assertEqual(report['phase'], 'private-mounts')

    def test_preflight_refuses_a_job_with_existing_execution_markers(self):
        job_name = 'modern-candidate-pack-failed'
        with tempfile.TemporaryDirectory() as directory:
            job = Path(directory) / job_name
            job.mkdir()
            lock = job / 'execution.lock'
            lock.write_text('prior-approval')
            critical = {'/host-critical-file': 'fixture-hash'}
            host_namespaces = {
                name: 'host:' + name for name in ('mnt', 'pid', 'net', 'ipc', 'uts')
            }
            contract = {
                'host_critical_files': critical,
                'host_namespaces': host_namespaces,
                'source_images': worker.SOURCE_IMAGES,
                'initial_required_bytes': 1,
            }
            class NeverRun:
                def __init__(self, *_args):
                    raise AssertionError('runner must not start for a used job')

            original_read_text = Path.read_text

            def read_runtime_file(path, *args, **kwargs):
                if path == Path('/proc/self/cgroup'):
                    return '0::/system.slice/devlite-' + job_name + '.service\n'
                if path == Path('/proc/self/status'):
                    return 'NoNewPrivs:\t1\n'
                if path == Path('/proc/self/mountinfo'):
                    return 'fixture mountinfo\n'
                if path == Path('/proc/net/dev'):
                    return 'Inter-| Receive | Transmit\n face | counters\n lo: 0 0\n'
                return original_read_text(path, *args, **kwargs)

            with (
                patch.object(worker.os, 'geteuid', return_value=0),
                patch.object(worker.os, 'getpid', return_value=1),
                patch.object(worker.os, 'readlink', side_effect=lambda value: 'isolated:' + value),
                patch.object(worker, 'read_job', return_value=(job, contract, {})),
                patch.object(worker, 'critical_files', return_value=critical),
                patch.object(worker, 'cgroup_limits', return_value={'memory.max': 'ok'}),
                patch.object(worker, 'filesystem_proof', return_value={}),
                patch.object(worker.shutil, 'disk_usage', return_value=SimpleNamespace(free=100 * 1024**3)),
                patch.object(worker, 'Runner', NeverRun),
                patch.object(Path, 'read_text', new=read_runtime_file),
            ):
                with self.assertRaisesRegex(RuntimeError, 'não reutilizar'):
                    worker.run(job, 'a' * 64, authorized=True)
            self.assertEqual(lock.read_text(), 'prior-approval')
            self.assertFalse((job / 'attempt').exists())

    def test_checkpoint_tree_must_match_the_prior_audit_digest(self):
        tree = {'.': {'type': 'dir', 'mode': 0o755}}
        report = {
            'results': {'base': {'file_audit': {
                'after_tree_sha256': worker.tree_digest(tree),
            }}},
        }
        worker.validate_checkpoint_tree(report, 'base', tree)
        changed = {'.': {'type': 'dir', 'mode': 0o700}}
        with self.assertRaisesRegex(RuntimeError, 'diverge da auditoria'):
            worker.validate_checkpoint_tree(report, 'base', changed)

    def test_checkpoint_validation_pins_contract_report_lock_and_clone_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work = root / 'work'
            work.mkdir()
            source_job = work / 'modern-candidate-pack-previous'
            attempt = source_job / 'attempt'
            source_job.mkdir(mode=0o700)
            attempt.mkdir(mode=0o700)
            current_job = work / 'modern-candidate-pack-resume'
            current_job.mkdir()
            source_images = {}
            for target, content in (('base', b'base-image'), ('live', b'live-image')):
                source = work / (target + '-source.ext4')
                source.write_bytes(content)
                source.chmod(0o600)
                source_images[target] = {
                    'file': str(source), 'sha256': worker.sha(source),
                }
                clone = attempt / (target + '.ext4')
                clone.write_bytes(content)
                clone.chmod(0o600)
            bundle = {'base/file': '1' * 64, 'live/file': '2' * 64}
            new_contract = {
                'source_approval': 'accepted-source',
                'source_result_sha256': '3' * 64,
                'source_images': source_images,
                'bundle_sha256': bundle,
                'payload_manifest_sha256': '4' * 64,
            }
            baseline = load_host_baseline()
            references = {
                name: f'{index:064x}'
                for index, name in enumerate(sorted(CHECKPOINT_SHARED_REFERENCE_FILES), 1)
            }
            new_contract.update({
                'reference_sha256': {
                    **references, HOST_BASELINE_REFERENCE: HOST_BASELINE_SHA256,
                },
                'host_baseline': {
                    'id': HOST_BASELINE_ID,
                    'file': HOST_BASELINE_REFERENCE,
                    'sha256': HOST_BASELINE_SHA256,
                },
                'host_critical_files': baseline['current_host_critical_files'],
            })
            old_contract = {
                **new_contract,
                'job': str(source_job),
                'operation': 'modern-candidate-pack-v1',
                'code_sha256': {'pipeline/devlite/modern_candidate_root.py': '6' * 64},
                'reference_sha256': references,
                'host_baseline': None,
                'host_critical_files': baseline['supersedes']['host_critical_files'],
            }
            contract_path = source_job / 'contract.json'
            contract_path.write_text(json.dumps(old_contract))
            contract_path.chmod(0o600)
            approval = worker.sha(contract_path)
            (source_job / 'execution.lock').write_text(approval)
            (source_job / 'execution.lock').chmod(0o600)
            results = {}
            plan = {'targets': {}}
            for target, count in (('base', 1), ('live', 2)):
                packages = {f'package-{i}': '1.0' for i in range(count)}
                plan['targets'][target] = {'final_versions': packages}
                results[target] = {
                    'package_count': count,
                    'file_audit': {
                        'only_declared_additions': True,
                        'target_programs_executed': False,
                        'after_tree_sha256': 'a' * 64,
                    },
                }
            old_report = {
                'status': 'quarantined', 'contract_sha256': approval,
                'phase': 'e2fsck-live',
                'error': 'Pacotes Base e Live divergentes',
                'source_images_modified': False, 'iso_generated': False,
                'target_programs_executed': False, 'cleanup_errors': [],
                'results': results,
            }
            report_path = source_job / 'pack-report.json'
            report_path.write_text(json.dumps(old_report))
            report_path.chmod(0o600)
            checkpoint = {
                'job': str(source_job), 'approval_sha256': approval,
                'contract_sha256': approval,
                'report_sha256': worker.sha(report_path),
                'worker_sha256': '6' * 64,
            }
            with patch.object(worker, 'ROOT', root), patch.object(
                worker, 'SOURCE_IMAGES', source_images,
            ):
                validated = worker.validate_resume_checkpoint(
                    current_job, checkpoint, new_contract, plan,
                )
                self.assertEqual(
                    validated['clone_sha256'],
                    {'base': worker.sha(attempt / 'base.ext4'),
                     'live': worker.sha(attempt / 'live.ext4')},
                )
                report_path.write_text('{}')
                with self.assertRaisesRegex(RuntimeError, 'Relatório de checkpoint alterado'):
                    worker.validate_resume_checkpoint(
                        current_job, checkpoint, new_contract, plan,
                    )

    def test_packer_creates_resume_reference_only_for_matching_failed_job(self):
        packer = load_packer()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            work = root / 'work'
            work.mkdir()
            source_job = work / 'modern-candidate-pack-failed'
            source_job.mkdir(mode=0o700)
            bundle = {'base/usr/bin/tool': '1' * 64, 'live/usr/bin/tool': '1' * 64}
            manifest_sha = '2' * 64
            previous = {
                'job': str(source_job),
                'operation': 'modern-candidate-pack-v1',
                'source_approval': worker.SOURCE_APPROVAL,
                'source_images': worker.SOURCE_IMAGES,
                'bundle_sha256': bundle,
                'payload_manifest_sha256': manifest_sha,
                'code_sha256': {packer.ROOT_WORKER: '3' * 64},
            }
            contract_path = source_job / 'contract.json'
            contract_path.write_text(json.dumps(previous))
            contract_path.chmod(0o600)
            approval = packer.sha(contract_path)
            (source_job / 'execution.lock').write_text(approval)
            (source_job / 'execution.lock').chmod(0o600)
            report = {
                'status': 'quarantined', 'contract_sha256': approval,
                'phase': 'e2fsck-live',
                'error': 'Pacotes Base e Live divergentes',
                'source_images_modified': False, 'iso_generated': False,
                'target_programs_executed': False, 'cleanup_errors': [],
                'results': {
                    target: {'file_audit': {
                        'only_declared_additions': True,
                        'target_programs_executed': False,
                        'after_tree_sha256': '4' * 64,
                    }}
                    for target in ('base', 'live')
                },
            }
            (source_job / 'pack-report.json').write_text(json.dumps(report))
            (source_job / 'pack-report.json').chmod(0o600)

            with patch.object(packer, 'ROOT', root):
                reference = packer.checkpoint_reference(
                    source_job, bundle, manifest_sha,
                )
                self.assertEqual(reference['job'], str(source_job))
                self.assertEqual(reference['approval_sha256'], approval)
                self.assertEqual(reference['worker_sha256'], '3' * 64)
                (source_job / 'layers-ready.json').touch()
                with self.assertRaisesRegex(ValueError, 'checkpoint recuperável'):
                    packer.checkpoint_reference(
                        source_job, bundle, manifest_sha,
                    )

    def test_payload_manifest_places_devcontrol_and_live_installer_only(self):
        packer = load_packer()
        with tempfile.TemporaryDirectory() as directory:
            job = Path(directory) / 'job'
            payload = job / 'payload'
            payload.mkdir(parents=True)
            packer.package_payload(payload)
            manifest = json.loads((job / 'payload-manifest.json').read_text())

        base = manifest['base']
        live = manifest['live']
        self.assertIn('usr/share/applications/devcontrol.desktop', base)
        self.assertIn('usr/lib/devlite/devcontrol/app.py', base)
        self.assertIn('usr/share/applications/devlite-get-vscode.desktop', base)
        self.assertNotIn('usr/share/applications/devlite-installer.desktop', base)
        self.assertNotIn(
            'etc/systemd/user/xubuntu-installer.service.d/10-devlite-branding.conf',
            base,
        )
        self.assertIn('usr/share/applications/devlite-installer.desktop', live)
        self.assertIn(
            'etc/systemd/user/xubuntu-installer.service.d/10-devlite-branding.conf',
            live,
        )

    def test_split_target_manifest_is_validated_against_each_payload_tree(self):
        packer = load_packer()
        with tempfile.TemporaryDirectory() as directory:
            job = Path(directory) / 'job'
            payload = job / 'payload'
            payload.mkdir(parents=True)
            packer.package_payload(payload)
            manifest = json.loads((job / 'payload-manifest.json').read_text())

            with self.assertRaisesRegex(ValueError, 'Payload manifest coverage differs'):
                validate_payload(payload, manifest)
            validate_candidate_payload_bundle(payload, manifest)

            (payload / 'unlisted').mkdir()
            with self.assertRaisesRegex(ValueError, 'Payload target coverage differs'):
                validate_candidate_payload_bundle(payload, manifest)

    def test_payload_contains_official_launcher_not_vscode_binary(self):
        packer = load_packer()
        with tempfile.TemporaryDirectory() as directory:
            job = Path(directory) / 'job'
            payload = job / 'payload'
            payload.mkdir(parents=True)
            packer.package_payload(payload)
            desktop = (
                payload / 'base/usr/share/applications/devlite-get-vscode.desktop'
            ).read_text()
            files = [path.relative_to(payload).as_posix() for path in payload.rglob('*') if path.is_file()]
        self.assertIn('https://code.visualstudio.com', desktop)
        self.assertFalse(any('visual-studio-code' in name.lower() or name.endswith('/code') for name in files))

    def test_installer_service_is_checked_without_replacing_its_execstart(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            unit = root / 'usr/lib/systemd/user/xubuntu-installer.service'
            unit.parent.mkdir(parents=True)
            unit.write_text(
                '[Service]\nExecStart=sh -c "/snap/bin/ubuntu-desktop-bootstrap '
                '--try-or-install"\n'
            )
            pin_installer(root)
            unit.write_text('[Service]\nExecStart=/bin/false\n')
            with self.assertRaisesRegex(RuntimeError, 'ExecStart'):
                pin_installer(root)

    def test_modern_wallpaper_and_vscode_launcher_are_pinned(self):
        source = ROOT / 'overlay/final-candidate/usr/share/applications/devlite-get-vscode.desktop'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wallpaper = root / 'usr/share/backgrounds/devlite/devlite-modern.svg'
            wallpaper.parent.mkdir(parents=True)
            wallpaper.write_text('<svg/>')
            launcher = root / 'usr/share/applications/devlite-get-vscode.desktop'
            launcher.parent.mkdir(parents=True)
            shutil.copyfile(source, launcher)
            self.assertTrue(pin_existing_modern(root))
            launcher.write_text('Exec=/usr/bin/false\n')
            with self.assertRaisesRegex(RuntimeError, 'difere'):
                pin_existing_modern(root)

    def test_missing_vscode_launcher_is_reported_for_conditional_addition(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wallpaper = root / 'usr/share/backgrounds/devlite/devlite-modern.svg'
            wallpaper.parent.mkdir(parents=True)
            wallpaper.write_text('<svg/>')
            self.assertFalse(pin_existing_modern(root))

    def test_gtk_dependencies_must_be_present_in_accepted_dpkg_state(self):
        names = ('python3', 'python3-gi', 'gir1.2-gtk-3.0')
        status = '\n\n'.join(
            f'Package: {name}\nStatus: install ok installed\n'
            f'Architecture: amd64\nVersion: 1.0'
            for name in names
        )
        plan = {'targets': {'base': {'final_versions': {
            name: '1.0' for name in names
        }}}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'var/lib/dpkg/status'
            path.parent.mkdir(parents=True)
            path.write_text(status)
            self.assertEqual(require_package_status(Path(directory), plan, 'base'), {
                name: '1.0' for name in names
            })
            missing = '\n\n'.join(status.split('\n\n')[:-1])
            path.write_text(missing)
            plan['targets']['base']['final_versions'].pop('gir1.2-gtk-3.0')
            with self.assertRaisesRegex(RuntimeError, 'ausentes'):
                require_package_status(Path(directory), plan, 'base')

    def test_live_only_packages_are_compatible_but_base_only_and_version_conflicts_are_not(self):
        base = {'common': '1.0', 'base-tool': '2.0'}
        live = {'common': '1.0', 'base-tool': '2.0', 'casper': '1.498'}
        result = package_compatibility(base, live)
        self.assertEqual(result['base_packages_missing_live'], [])
        self.assertEqual(result['common_version_conflicts'], {})
        self.assertEqual(result['live_only_packages'], ['casper'])
        self.assertEqual(result['live_only_versions'], {'casper': '1.498'})

        base_only = package_compatibility(
            {'common': '1.0', 'base-tool': '2.0'},
            {'common': '1.0'},
        )
        self.assertEqual(base_only['base_packages_missing_live'], ['base-tool'])

        version_conflict = package_compatibility(
            {'common': '1.0'},
            {'common': '2.0'},
        )
        self.assertEqual(
            version_conflict['common_version_conflicts'],
            {'common': {'base': '1.0', 'live': '2.0'}},
        )

    def test_root_worker_namespace_is_fixed_and_networkless(self):
        packer = load_packer()
        command = packer.namespace_command(Path('/tmp/job'), 'a' * 64)
        for namespace_flag in (
            '--mount', '--propagation', 'private', '--pid', '--fork',
            '--kill-child', '--mount-proc', '--net', '--ipc', '--uts',
        ):
            self.assertIn(namespace_flag, command)
        self.assertIn('-m', command)
        self.assertIn('pipeline.devlite.modern_candidate_root', command)
        self.assertNotIn(
            '/home/magaton/DevLite-OS/pipeline/devlite/modern_candidate_root.py',
            command,
        )
        self.assertNotIn('sudo', command)
        self.assertNotIn('bash', command)
        self.assertIn('--execute-authorized', command)
        root_command = packer.root_command(Path('/tmp/job'), 'a' * 64)
        for protection in (
            '--property=MemoryMax=2684354560',
            '--property=MemorySwapMax=1073741824',
            '--property=CPUQuota=100%',
            '--property=TasksMax=128',
            '--property=RuntimeMaxSec=14400',
            '--property=TimeoutStopSec=60',
            '--property=KillMode=control-group',
            '--property=OOMPolicy=kill',
            '--property=ProtectSystem=strict',
            '--property=ProtectHome=read-only',
            '--property=ReadWritePaths=/tmp/job',
            '--property=PrivateNetwork=yes',
            '--property=PrivateMounts=yes',
            '--property=NoNewPrivileges=yes',
            '--property=ProtectKernelTunables=yes',
            '--property=ProtectKernelModules=yes',
            '--property=ProtectControlGroups=yes',
            '--property=RestrictRealtime=yes',
            '--property=RestrictAddressFamilies=AF_UNIX',
            '--property=CapabilityBoundingSet=CAP_SYS_ADMIN CAP_CHOWN CAP_DAC_OVERRIDE CAP_DAC_READ_SEARCH CAP_FOWNER CAP_FSETID CAP_MKNOD CAP_SETFCAP',
        ):
            self.assertIn(protection, root_command)
        handoff = load_handoff()
        self.assertEqual(handoff.WORKER_ENV['PYTHONPATH'], str(ROOT))
        self.assertEqual(
            handoff.WORKER_ENV['PATH'],
            '/usr/sbin:/usr/bin:/sbin:/bin',
        )


if __name__ == '__main__':
    unittest.main()
