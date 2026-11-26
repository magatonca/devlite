"""Contract helpers for the next isolated Modern candidate."""
import hashlib
import json
import os
import re
import stat
from pathlib import Path

from .customize.isolation_validation import critical_files

ROOT = Path('/home/magaton/DevLite-OS')
SOURCE = ROOT / 'work/modern-apply-5w334rzl'
SOURCE_APPROVAL = '153cd14745cdddb20d1c9f00448b9a4fbcf1376387e9cdcdcc017fdb6e8771e2'
HOST_BASELINE = ROOT / 'config/modern-host-baseline-v2.json'
HOST_BASELINE_ID = 'devlite-modern-host-baseline-v2-2026-11-21'
HOST_BASELINE_SHA256 = '683648417001f9491780f11575d1ad4e90c9fcd68ff85221aa4d8e7b7b73c7f2'
HOST_BASELINE_REFERENCE = 'config/modern-host-baseline-v2.json'
HOST_BASELINE_V3 = ROOT / 'config/modern-host-baseline-v3.json'
HOST_BASELINE_V3_ID = 'devlite-modern-host-baseline-v3-2026-11-22'
HOST_BASELINE_V3_SHA256 = '4ba5cf3ca70d817f44d2aeea3cf8e2ef9f7a1187a782461ca1c506c605729fcb'
HOST_BASELINE_V3_REFERENCE = 'config/modern-host-baseline-v3.json'
HOST_BASELINE_V3_EVIDENCE_REFERENCE = 'reports/host-baseline-v3-apt-transaction.json'
HOST_BASELINE_V3_EVIDENCE_SHA256 = '2e7974bafee7ada5a449dfa8d8c8ff33585acce3b8a8da03088e017beef6ccf0'
SOURCE_IMAGES = {
    'base': {
        'file': str(SOURCE / 'attempt/base.ext4'),
        'sha256': 'b8af978223c9a1db12a8bd9b0e4af7e600c0a01129a11385079762923bbb5e09',
    },
    'live': {
        'file': str(SOURCE / 'attempt/live.ext4'),
        'sha256': '3010e3b5c8b73fac32fa030f002da744081f94069868bac11d4bcb600ede5d8a',
    },
}
RESERVE = 20 * 1024**3
LIMITS = {'memory_bytes': 2684354560, 'swap_bytes': 1073741824, 'tasks': 128}
WRAPPER = 'scripts/empacotar-modern-candidata.py'
ROOT_WORKER = 'pipeline/devlite/modern_candidate_root.py'
REFERENCE_FILES = (
    'work/release-browser-2f24tvsg/plan.json',
    'work/phase4b1-dhzezpnz/original-casper/filesystem.manifest',
    'work/phase4b1-dhzezpnz/original-casper/install-sources.yaml',
    HOST_BASELINE_REFERENCE,
)
CHECKPOINT_SHARED_REFERENCE_FILES = frozenset(REFERENCE_FILES) - {
    HOST_BASELINE_REFERENCE,
}


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def load_host_baseline():
    if (HOST_BASELINE.is_symlink() or not HOST_BASELINE.is_file()
            or sha(HOST_BASELINE) != HOST_BASELINE_SHA256):
        raise ValueError('Baseline do host v2 ausente ou alterada')
    baseline = json.loads(HOST_BASELINE.read_text())
    if (baseline.get('schema') != 1
            or baseline.get('baseline_id') != HOST_BASELINE_ID
            or baseline.get('scope') !=
            'host-critical-files-only; target Base/Live inventories, source images and ISO are unchanged'):
        raise ValueError('Identidade ou escopo da baseline v2 inválido')
    return baseline


def validate_host_baseline(baseline, previous, current=None):
    predecessor = baseline.get('supersedes', {})
    transition = baseline.get('authorized_host_transition', {})
    previous_files = predecessor.get('host_critical_files')
    current_files = baseline.get('current_host_critical_files')
    if (not isinstance(previous_files, dict)
            or predecessor.get('baseline_id')
            != 'devlite-modern-host-baseline-v1-embedded-in-source-contract'
            or predecessor.get('source_contract')
            != 'work/modern-apply-5w334rzl/contract.json'
            or predecessor.get('source_contract_sha256') != SOURCE_APPROVAL
            or previous_files != previous
            or not isinstance(current_files, dict)
            or transition.get('changed_host_critical_paths') != ['/var/lib/dpkg/status']):
        raise ValueError('Linhagem da baseline de host não corresponde ao contrato v1')
    changed = {
        path: (previous_files.get(path), current_files.get(path))
        for path in sorted(set(previous_files) | set(current_files))
        if previous_files.get(path) != current_files.get(path)
    }
    if changed != {
            '/var/lib/dpkg/status': (
                'c89700b29c7b3095f1262c16b80543726ea1541d54021c09c4b99183c359e06a',
                '4b167d947d7c25a2343f2dff02a85e777c06ce50c846635ac14557af38be6277',
            )}:
        raise ValueError('Baseline v2 contém divergências além da atualização autorizada')
    approved_copy = transition.get('approved_copy', {})
    current_status = transition.get('current_status', {})
    package = transition.get('package_record', {})
    target_artifacts = baseline.get('target_artifacts_unchanged', {})
    if (approved_copy.get('path') != '/var/backups/dpkg.status.0'
            or approved_copy.get('sha256') != changed['/var/lib/dpkg/status'][0]
            or current_status.get('path') != '/var/lib/dpkg/status'
            or current_status.get('sha256') != changed['/var/lib/dpkg/status'][1]
            or target_artifacts.get('approved_iso_sha256')
            != '7373cb9be11ebda5218f20795fec87eab20c2cebef3c763ae6e5c63d4e7cd7bd'
            or package != {
                'package': 'python3-jwt', 'architecture': 'all',
                'previous_version': '2.7.0-1ubuntu0.4',
                'current_version': '2.7.0-1ubuntu0.5',
                'previous_installed_size': 116, 'current_installed_size': 117,
                'status_before_and_after': 'install ok installed',
                'added_records': 0, 'removed_records': 0,
                'installation_state_changes': 0,
            }):
        raise ValueError('Evidência da transição da baseline está inconsistente')
    if current is not None and current != current_files:
        raise ValueError('Arquivos críticos atuais não coincidem com a baseline v2')
    return current_files


def load_host_baseline_v3():
    if (HOST_BASELINE_V3.is_symlink() or not HOST_BASELINE_V3.is_file()
            or sha(HOST_BASELINE_V3) != HOST_BASELINE_V3_SHA256):
        raise ValueError('Baseline do host v3 ausente ou alterada')
    baseline = json.loads(HOST_BASELINE_V3.read_text())
    if (baseline.get('schema') != 1
            or baseline.get('baseline_id') != HOST_BASELINE_V3_ID
            or baseline.get('scope') !=
            'host-critical-files-only; target Base/Live inventories, source images and ISO are unchanged'):
        raise ValueError('Identidade ou escopo da baseline v3 inválido')
    evidence_path = ROOT / HOST_BASELINE_V3_EVIDENCE_REFERENCE
    evidence_ref = baseline.get('authorized_host_transition', {}).get(
        'evidence_report', {},
    )
    if (evidence_ref != {
            'path': HOST_BASELINE_V3_EVIDENCE_REFERENCE,
            'sha256': HOST_BASELINE_V3_EVIDENCE_SHA256,
    } or evidence_path.is_symlink() or not evidence_path.is_file()
            or sha(evidence_path) != HOST_BASELINE_V3_EVIDENCE_SHA256):
        raise ValueError('Evidência da baseline v3 ausente ou alterada')
    return baseline


def validate_host_baseline_v3(baseline, previous, current=None):
    baseline_v2 = load_host_baseline()
    source_contract = json.loads((SOURCE / 'contract.json').read_text())
    validate_host_baseline(
        baseline_v2, source_contract.get('host_critical_files'),
        baseline_v2.get('current_host_critical_files'),
    )
    predecessor = baseline.get('supersedes', {})
    previous_files = baseline_v2.get('current_host_critical_files')
    current_files = baseline.get('current_host_critical_files')
    if (baseline.get('schema') != 1
            or baseline.get('baseline_id') != HOST_BASELINE_V3_ID
            or predecessor.get('baseline_id') != HOST_BASELINE_ID
            or predecessor.get('path') != HOST_BASELINE_REFERENCE
            or predecessor.get('sha256') != HOST_BASELINE_SHA256
            or predecessor.get('host_critical_files') != previous_files
            or previous != previous_files
            or not isinstance(current_files, dict)):
        raise ValueError('Linhagem da baseline v3 não corresponde à v2')

    transition = baseline.get('authorized_host_transition', {})
    previous_hashes = {
        '/var/lib/apt/extended_states':
            '874c5ee29eb26b405bd24b9c15879f466cd51311e1866039342ff3263ccd81fb',
        '/var/lib/dpkg/status':
            '4b167d947d7c25a2343f2dff02a85e777c06ce50c846635ac14557af38be6277',
    }
    current_hashes = {
        '/var/lib/apt/extended_states':
            '00306f277d9c2157221470ba65ce665e8faabe72f0479256f296f4c38bc49b43',
        '/var/lib/dpkg/status':
            '790d119695327b07fb3b2222a498fc95219cb514b46915a21859853fec02e0d0',
    }
    changed = {
        path: (previous_files.get(path), current_files.get(path))
        for path in sorted(set(previous_files) | set(current_files))
        if previous_files.get(path) != current_files.get(path)
    }
    if (changed != {
            path: (previous_hashes[path], current_hashes[path])
            for path in previous_hashes
    } or transition.get('id')
            != 'authorized-gtk3-xvfb-test-tools-2026-11-22'
            or transition.get('apt_commandline')
            != 'apt-get -y --no-install-recommends install xvfb gir1.2-gtk-3.0'
            or transition.get('changed_host_critical_paths')
            != sorted(previous_hashes)
            or transition.get('previous_hashes') != previous_hashes
            or transition.get('current_hashes') != current_hashes
            or transition.get('evidence_report') != {
                'path': HOST_BASELINE_V3_EVIDENCE_REFERENCE,
                'sha256': HOST_BASELINE_V3_EVIDENCE_SHA256,
            }):
        raise ValueError('Baseline v3 contém divergências além da instalação autorizada')

    evidence = json.loads(
        (ROOT / HOST_BASELINE_V3_EVIDENCE_REFERENCE).read_text(),
    )
    transaction = evidence.get('apt_transaction', {})
    expected_artifacts = {
        'iso_v2_sha256':
            'd32779839ad6bd67dbc1f157b5d3f646ac1df55ab4afef430c5d6f9abef12e75',
        'pack_contract_sha256':
            'babdc55e0604d96180f7df8c2a89d6cd3712934ee7442b60216f9e66f00b25b1',
        'base_sha256':
            '72c74045749b790d01ceae52387a0ca1054c3a99848a93520d5057fef6fea4a0',
        'live_sha256':
            '013cd6ec9b6b934128a755f3c384d05337e741cc7021f76ab17fb4915e68b0d9',
    }
    expected_baseline_artifacts = {
        'iso_v2_sha256': expected_artifacts['iso_v2_sha256'],
        'pack_contract_sha256': expected_artifacts['pack_contract_sha256'],
        'base_squashfs_sha256': expected_artifacts['base_sha256'],
        'live_squashfs_sha256': expected_artifacts['live_sha256'],
    }
    if (evidence.get('schema') != 1
            or transaction.get('commandline') != transition['apt_commandline']
            or transaction.get('install_record_count') != 93
            or len(transaction.get('install_records', [])) != 93
            or transaction.get('upgrade_records') != []
            or transaction.get('remove_records') != []
            or transaction.get('summary') != {
                'new_packages': 93, 'upgraded': 0, 'removed': 0,
                'not_upgraded': 18, 'additional_disk_bytes': 276824064,
            }
            or transaction.get('requested_packages') != [
                {'package': 'xvfb', 'version': '2:21.1.12-1ubuntu1.9'},
                {'package': 'gir1.2-gtk-3.0', 'version': '3.24.41-4ubuntu1.3'},
            ]
            or transaction.get('preinstalled_packages') != [
                {'package': 'python3-gi', 'version': '3.48.2-1'},
            ]
            or evidence.get('host_critical_files') != {
                'before_baseline_v2': previous_files,
                'after_baseline_v3': current_files,
                'changed': {
                    path: {'before': previous_hashes[path],
                           'after': current_hashes[path]}
                    for path in previous_hashes
                },
            }
            or evidence.get('protected_artifacts') != expected_artifacts
            or baseline.get('target_artifacts_unchanged')
            != expected_baseline_artifacts):
        raise ValueError('Evidência da transição de baseline v3 é inconsistente')
    if current is not None and current != current_files:
        raise ValueError('Arquivos críticos atuais não coincidem com a baseline v3')
    return current_files


def checkpoint_contract_mismatches(previous, checkpoint, current):
    mismatches = []
    for field in (
            'source_approval', 'source_result_sha256', 'source_images',
            'bundle_sha256', 'payload_manifest_sha256'):
        if previous.get(field) != current.get(field):
            mismatches.append(field)
    if (previous.get('job') != checkpoint.get('job')
            or previous.get('operation') != 'modern-candidate-pack-v1'):
        mismatches.append('checkpoint_identity')
    checkpoint_approval = checkpoint.get('contract_sha256')
    if (checkpoint.get('approval_sha256') != checkpoint_approval
            or previous.get('code_sha256', {}).get(ROOT_WORKER)
            != checkpoint.get('worker_sha256')):
        mismatches.append('checkpoint_seal')

    previous_references = previous.get('reference_sha256')
    current_references = current.get('reference_sha256')
    if (not isinstance(previous_references, dict)
            or set(previous_references) != CHECKPOINT_SHARED_REFERENCE_FILES):
        mismatches.append('checkpoint_reference_set')
        previous_references = {}
    if (not isinstance(current_references, dict)
            or set(current_references) != set(REFERENCE_FILES)):
        mismatches.append('current_reference_set')
        current_references = {}
    for name in sorted(CHECKPOINT_SHARED_REFERENCE_FILES):
        if previous_references.get(name) != current_references.get(name):
            mismatches.append('reference_sha256:' + name)

    expected_baseline = {
        'id': HOST_BASELINE_ID,
        'file': HOST_BASELINE_REFERENCE,
        'sha256': HOST_BASELINE_SHA256,
    }
    if (current.get('host_baseline') != expected_baseline
            or current_references.get(HOST_BASELINE_REFERENCE)
            != HOST_BASELINE_SHA256
            or previous.get('host_baseline') is not None):
        mismatches.append('host_baseline_identity')
    else:
        baseline = load_host_baseline()
        try:
            validate_host_baseline(
                baseline, previous.get('host_critical_files'),
                current.get('host_critical_files'),
            )
        except ValueError:
            mismatches.append('host_baseline_transition')

    # The checkpoint's code remains pinned by its own contract; current code is
    # independently pinned and checked by read_job() for the new contract.
    return tuple(mismatches)


def _validate_approved_pack_host_baseline(data):
    baseline_v2 = load_host_baseline()
    previous_contract = json.loads((SOURCE / 'contract.json').read_text())
    accepted_v2_files = validate_host_baseline(
        baseline_v2, previous_contract.get('host_critical_files'),
        baseline_v2.get('current_host_critical_files'),
    )
    baseline_v3 = load_host_baseline_v3()
    validate_host_baseline_v3(
        baseline_v3, accepted_v2_files, critical_files(),
    )
    if (data.get('host_baseline') != {
            'id': HOST_BASELINE_ID,
            'file': HOST_BASELINE_REFERENCE,
            'sha256': HOST_BASELINE_SHA256,
    } or data.get('host_critical_files') != accepted_v2_files):
        raise ValueError('Pack aprovado não está selado na baseline histórica v2')


def _read_pack_job(job, approval, *, root, approved_historical=False):
    job = Path(job)
    if job.is_symlink() or job.resolve().parent != (ROOT / 'work').resolve():
        raise ValueError('Job fora do workspace autorizado')
    if not job.name.startswith('modern-candidate-pack-'):
        raise ValueError('Nome de job inesperado')
    info = job.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid not in ((0, 1000) if root else (1000,)):
        raise ValueError('Ownership do job inesperado')
    path = job / 'contract.json'
    if path.is_symlink() or not path.is_file() or sha(path) != approval:
        raise ValueError('Contrato de build divergente')
    data = json.loads(path.read_text())
    if data.get('schema') != 1 or data.get('operation') != 'modern-candidate-pack-v1':
        raise ValueError('Perfil de build inválido')
    if data.get('job') != str(job) or data.get('source_approval') != SOURCE_APPROVAL:
        raise ValueError('Identidade do contrato divergente')
    if data.get('source_images') != SOURCE_IMAGES or data.get('reserve_bytes') != RESERVE:
        raise ValueError('Entradas ou reserva divergentes')
    if data.get('limits') != LIMITS or data.get('iso_generated') is not False:
        raise ValueError('Limites ou escopo divergentes')
    if approved_historical:
        _validate_approved_pack_host_baseline(data)
    else:
        baseline = load_host_baseline()
        previous_contract = json.loads((SOURCE / 'contract.json').read_text())
        accepted_host_files = validate_host_baseline(
            baseline, previous_contract.get('host_critical_files'), critical_files(),
        )
        if (data.get('host_baseline') != {
                'id': HOST_BASELINE_ID,
                'file': HOST_BASELINE_REFERENCE,
                'sha256': HOST_BASELINE_SHA256,
            }
                or data.get('host_critical_files') != accepted_host_files):
            raise ValueError('Contrato não está vinculado à baseline de host aprovada')
    if set(data.get('reference_sha256', {})) != set(REFERENCE_FILES):
        raise ValueError('Referências seladas ausentes ou inesperadas')
    for name, expected in data['reference_sha256'].items():
        file = ROOT / name
        if file.is_symlink() or not file.is_file() or sha(file) != expected:
            raise ValueError('Referência selada alterada: ' + name)
    if sha(SOURCE / 'contract.json') != SOURCE_APPROVAL:
        raise ValueError('Contrato de origem foi alterado')
    receipt = SOURCE / 'result.json'
    info = receipt.lstat()
    result = json.loads(receipt.read_text())
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022
            or sha(receipt) != data.get('source_result_sha256')
            or result.get('status') != 'modern_full_views_verified'
            or result.get('contract_sha256') != SOURCE_APPROVAL
            or result.get('source_images_modified') is not False
            or result.get('iso_generated') is not False
            or set(result.get('results', {})) != {'base', 'live'}):
        raise ValueError('Recibo de origem não aprovado')
    for name, record in SOURCE_IMAGES.items():
        result_image = result['results'][name]['image']
        if result_image.get('file') != record['file'] or result_image.get('sha256') != record['sha256']:
            raise ValueError('Imagem de origem diverge do recibo: ' + name)
    if data.get('bundle_sha256'):
        bundle = job / 'payload'
        actual = {
            path.relative_to(bundle).as_posix(): sha(path)
            for path in bundle.rglob('*') if path.is_file() and not path.is_symlink()
        }
        if actual != data['bundle_sha256']:
            raise ValueError('Payload alterado ou cobertura divergente')
    if data.get('payload_manifest_sha256') and sha(job / 'payload-manifest.json') != data['payload_manifest_sha256']:
        raise ValueError('Manifesto de payload alterado')
    return job, data, result


def _validated_code_manifest(data):
    code = data.get('code_sha256')
    if not isinstance(code, dict) or not code:
        raise ValueError('Manifesto de código selado inválido')
    for name, expected in code.items():
        path = Path(name) if isinstance(name, str) else None
        if (path is None or not name or path.is_absolute()
                or path.as_posix() != name or '..' in path.parts
                or '\\' in name or not isinstance(expected, str)
                or not re.fullmatch(r'[0-9a-f]{64}', expected)):
            raise ValueError('Manifesto de código selado inválido')
    return code


def read_job(job, approval, *, root=False):
    job, data, result = _read_pack_job(job, approval, root=root)
    for name, expected in _validated_code_manifest(data).items():
        file = ROOT / name
        if file.is_symlink() or not file.is_file() or sha(file) != expected:
            raise ValueError('Código selado alterado: ' + name)
    return job, data, result


def read_approved_pack_for_iso(job, approval, *, root=False):
    """Validate an approved historical pack without comparing its code to today's tree."""
    job, data, result = _read_pack_job(
        job, approval, root=root, approved_historical=True,
    )
    _validated_code_manifest(data)
    return job, data, result
