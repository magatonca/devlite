#!/usr/bin/env python3
"""Prepare and execute the isolated Modern candidate pack."""
import argparse
import importlib.util
import json
import os
import re
import shlex
import shutil
import stat
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.devlite.modern_candidate import (
    HOST_BASELINE_ID, HOST_BASELINE_REFERENCE, HOST_BASELINE_SHA256, LIMITS,
    REFERENCE_FILES, RESERVE, ROOT_WORKER, SOURCE, SOURCE_APPROVAL, SOURCE_IMAGES,
    WRAPPER, checkpoint_contract_mismatches, load_host_baseline, read_job, save,
    sha, validate_host_baseline,
)
from pipeline.devlite.runtime import owned_directory
from pipeline.devlite.customize.isolation_validation import critical_files

spec = importlib.util.spec_from_file_location(
    'modern_pack_precedent', ROOT / 'scripts/empacotar-modern-isolado.py'
)
precedent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(precedent)
PAYLOAD_FILES = {
    'prototypes/devcontrol/app.py': 'usr/lib/devlite/devcontrol/app.py',
    'prototypes/devcontrol/collector.py': 'usr/lib/devlite/devcontrol/collector.py',
    'prototypes/devcontrol/devcontrol.desktop': 'usr/share/applications/devcontrol.desktop',
    'overlay/final-candidate/usr/share/applications/devlite-get-vscode.desktop':
        'usr/share/applications/devlite-get-vscode.desktop',
    'overlay/modern-release-v1/usr/share/applications/devlite-installer.desktop':
        'usr/share/applications/devlite-installer.desktop',
    'overlay/modern-release-v1/etc/systemd/user/xubuntu-installer.service.d/10-devlite-branding.conf':
        'etc/systemd/user/xubuntu-installer.service.d/10-devlite-branding.conf',
}
GIB = 1024**3


def namespace_command(job, approval):
    return [
        'unshare', '--mount', '--propagation', 'private', '--pid', '--fork',
        '--kill-child', '--mount-proc', '--net', '--ipc', '--uts',
        '/usr/bin/python3', '-m', 'pipeline.devlite.modern_candidate_root',
        '--job', str(job), '--approval-sha256', approval, '--execute-authorized',
    ]


def root_command(job, approval):
    name = 'devlite-' + job.name
    properties = (
        'MemoryMax=2684354560', 'MemorySwapMax=1073741824',
        'CPUQuota=100%', 'TasksMax=128', 'RuntimeMaxSec=14400',
        'TimeoutStopSec=60', 'KillMode=control-group', 'OOMPolicy=kill',
        'ProtectSystem=strict', 'ProtectHome=read-only',
        'ReadWritePaths=' + str(job), 'PrivateNetwork=yes', 'PrivateMounts=yes',
        'NoNewPrivileges=yes', 'ProtectKernelTunables=yes',
        'ProtectKernelModules=yes', 'ProtectControlGroups=yes',
        'RestrictRealtime=yes', 'RestrictAddressFamilies=AF_UNIX',
        'CapabilityBoundingSet=CAP_SYS_ADMIN CAP_CHOWN CAP_DAC_OVERRIDE CAP_DAC_READ_SEARCH CAP_FOWNER CAP_FSETID CAP_MKNOD CAP_SETFCAP',
    )
    return [
        'sudo', 'systemd-run', '--unit=' + name, '--wait', '--pipe', '--collect',
        *['--property=' + value for value in properties],
        '/usr/bin/python3', str(ROOT / 'scripts/iniciar-modern-candidata-root.py'),
        '--job', str(job), '--approval-sha256', approval, '--execute-authorized', '--',
        *namespace_command(job, approval),
    ]


def package_payload(bundle):
    manifests = {}
    files = dict(PAYLOAD_FILES)
    for target in ('base', 'live'):
        selected = {
            destination: source for source, destination in files.items()
            if not destination.startswith(('etc/', 'usr/share/applications/devlite-installer'))
            and not destination.startswith('etc/systemd/')
        }
        if target == 'live':
            selected.update({
                'usr/share/applications/devlite-installer.desktop':
                    'overlay/modern-release-v1/usr/share/applications/devlite-installer.desktop',
                'etc/systemd/user/xubuntu-installer.service.d/10-devlite-branding.conf':
                    'overlay/modern-release-v1/etc/systemd/user/xubuntu-installer.service.d/10-devlite-branding.conf',
            })
        tree = bundle / target
        entries = {}
        for destination, source in selected.items():
            source_path = ROOT / source
            if source_path.is_symlink() or not source_path.is_file():
                raise ValueError('Payload fonte ausente/inseguro: ' + source)
            output = tree / destination
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_path, output)
            output.chmod(0o644)
            entries[destination] = {
                'type': 'file', 'uid': 0, 'gid': 0, 'mode': '0644',
                'size': output.stat().st_size, 'sha256': sha(output),
            }
            for parent in output.parents:
                if parent == tree:
                    break
                relative = parent.relative_to(tree).as_posix()
                entries.setdefault(relative, {
                    'type': 'dir', 'uid': 0, 'gid': 0, 'mode': '0755',
                })
        manifests[target] = entries
    save(bundle.parent / 'payload-manifest.json', manifests)


def checkpoint_reference(source_job, bundle_sha, manifest_sha):
    checkpoint_job = Path(source_job).absolute()
    if (checkpoint_job.is_symlink()
            or checkpoint_job.resolve().parent != (ROOT / 'work').resolve()
            or not checkpoint_job.name.startswith('modern-candidate-pack-')):
        raise ValueError('Job de checkpoint fora do workspace autorizado')
    contract_path = checkpoint_job / 'contract.json'
    report_path = checkpoint_job / 'pack-report.json'
    lock_path = checkpoint_job / 'execution.lock'
    for path in (contract_path, report_path, lock_path):
        if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o022:
            raise ValueError('Recibo de checkpoint ausente ou inseguro')
    approval = sha(contract_path)
    previous = json.loads(contract_path.read_text())
    report = json.loads(report_path.read_text())
    if (previous.get('job') != str(checkpoint_job)
            or previous.get('operation') != 'modern-candidate-pack-v1'
            or previous.get('source_approval') != SOURCE_APPROVAL
            or previous.get('source_images') != SOURCE_IMAGES
            or previous.get('bundle_sha256') != bundle_sha
            or previous.get('payload_manifest_sha256') != manifest_sha
            or previous.get('code_sha256', {}).get(ROOT_WORKER) is None
            or lock_path.read_text() != approval):
        raise ValueError('Contrato/lock do checkpoint não corresponde ao payload atual')
    if (report.get('status') != 'quarantined'
            or report.get('contract_sha256') != approval
            or report.get('phase') != 'e2fsck-live'
            or report.get('error') != 'Pacotes Base e Live divergentes'
            or report.get('source_images_modified') is not False
            or report.get('iso_generated') is not False
            or report.get('target_programs_executed') is not False
            or report.get('cleanup_errors') != []
            or set(report.get('results', {})) != {'base', 'live'}
            or (checkpoint_job / 'layers-ready.json').exists()
            or (checkpoint_job / 'published-casper').exists()
            or (checkpoint_job / 'published-casper').is_symlink()):
        raise ValueError('Tentativa anterior não é um checkpoint recuperável')
    for target in ('base', 'live'):
        audit = report['results'][target].get('file_audit', {})
        if (audit.get('only_declared_additions') is not True
                or audit.get('target_programs_executed') is not False
                or not re.fullmatch(r'[0-9a-f]{64}', audit.get('after_tree_sha256', ''))):
            raise ValueError('Auditoria de checkpoint incompleta: ' + target)
    return {
        'job': str(checkpoint_job),
        'approval_sha256': approval,
        'contract_sha256': approval,
        'report_sha256': sha(report_path),
        'worker_sha256': previous['code_sha256'][ROOT_WORKER],
    }


def preflight_resume_checkpoint(checkpoint, contract):
    expected_fields = {
        'job', 'approval_sha256', 'contract_sha256', 'report_sha256',
        'worker_sha256',
    }
    if not isinstance(checkpoint, dict) or set(checkpoint) != expected_fields:
        raise ValueError('Referência de checkpoint incompleta')
    source_job = Path(checkpoint['job'])
    if (source_job.is_symlink()
            or source_job.resolve().parent != (ROOT / 'work').resolve()
            or source_job == Path(contract['job'])):
        raise ValueError('Job de checkpoint fora do workspace autorizado')
    job_info = source_job.lstat()
    if (not stat.S_ISDIR(job_info.st_mode) or job_info.st_uid != 0
            or job_info.st_mode & 0o022):
        raise ValueError('Ownership/permissões do checkpoint inesperados')
    contract_path = source_job / 'contract.json'
    report_path = source_job / 'pack-report.json'
    lock_path = source_job / 'execution.lock'
    for path in (contract_path, report_path, lock_path):
        if path.is_symlink() or not path.is_file():
            raise ValueError('Recibo de checkpoint ausente ou inseguro')
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o022:
            raise ValueError('Recibo de checkpoint modificável por grupo/outros')
    if (sha(contract_path) != checkpoint['contract_sha256']
            or checkpoint['approval_sha256'] != checkpoint['contract_sha256']
            or lock_path.read_text() != checkpoint['contract_sha256']):
        raise ValueError('Contrato/lock do checkpoint não corresponde ao recibo')
    previous = json.loads(contract_path.read_text())
    mismatches = checkpoint_contract_mismatches(previous, checkpoint, contract)
    if mismatches:
        raise ValueError(
            'Contrato de checkpoint incompatível: ' + ', '.join(mismatches)
        )
    if sha(report_path) != checkpoint['report_sha256']:
        raise ValueError('Relatório de checkpoint alterado')
    report = json.loads(report_path.read_text())
    if (report.get('status') != 'quarantined'
            or report.get('contract_sha256') != checkpoint['contract_sha256']
            or report.get('phase') != 'e2fsck-live'
            or report.get('error') != 'Pacotes Base e Live divergentes'
            or report.get('source_images_modified') is not False
            or report.get('iso_generated') is not False
            or report.get('target_programs_executed') is not False
            or report.get('cleanup_errors') != []
            or set(report.get('results', {})) != {'base', 'live'}):
        raise ValueError('Tentativa anterior não é um checkpoint recuperável')
    if ((source_job / 'layers-ready.json').exists()
            or (source_job / 'published-casper').exists()
            or (source_job / 'published-casper').is_symlink()):
        raise ValueError('Checkpoint já publicou artefatos')
    attempt = source_job / 'attempt'
    if attempt.is_symlink() or not attempt.is_dir():
        raise ValueError('Diretório de checkpoint ausente ou inseguro')
    attempt_info = attempt.lstat()
    if (not stat.S_ISDIR(attempt_info.st_mode) or attempt_info.st_uid != 0
            or stat.S_IMODE(attempt_info.st_mode) != 0o700):
        raise ValueError('Diretório de clones do checkpoint inesperado')
    plan = json.loads((ROOT / 'work/release-browser-2f24tvsg/plan.json').read_text())
    for target in ('base', 'live'):
        audit = report['results'][target].get('file_audit', {})
        if (report['results'][target].get('package_count')
                != len(plan['targets'][target]['final_versions'])
                or audit.get('only_declared_additions') is not True
                or audit.get('target_programs_executed') is not False
                or not re.fullmatch(r'[0-9a-f]{64}', audit.get('after_tree_sha256', ''))):
            raise ValueError('Auditoria de checkpoint incompleta: ' + target)
    return report


def accepted_source(baseline):
    app = precedent.app
    source = app.review.legacy.confined(SOURCE)
    if source.parent != ROOT / 'work' or not source.name.startswith('modern-apply-'):
        raise ValueError('Job de origem fora do workspace autorizado')
    source_contract = app.review.legacy.load(
        source / 'contract.json', SOURCE_APPROVAL,
    )
    if (source_contract.get('job') != str(source)
            or source_contract.get('operation') != 'modern-only-full-views-v1'
            or source_contract.get('limits') != app.LIMITS
            or source_contract.get('reserve_bytes') != app.RESERVE
            or source_contract.get('initial_bytes') != app.INITIAL
            or any(source_contract.get(name) is not False for name in (
                'iso_generated', 'packages_installed', 'adminer_installed',
                'control2_installed',
            ))):
        raise ValueError('Contrato de origem aceito inválido')
    if any(sha(ROOT / name) != digest
           for name, digest in source_contract['code_sha256'].items()):
        raise ValueError('Código da origem aceita foi alterado')
    if any(sha(source / name) != digest
           for name, digest in source_contract['bundle_sha256'].items()):
        raise ValueError('Payload da origem aceita foi alterado')
    actual_bundle = {
        str(path.relative_to(source))
        for path in (source / 'bundles').rglob('*')
        if path.is_file() and not path.is_symlink()
    }
    if actual_bundle != set(source_contract['bundle_sha256']):
        raise ValueError('Cobertura do payload da origem alterada')
    if (sha(app.REVIEW) != source_contract['review_sha256']
            or sha(app.review.SOURCE / 'browser-result.json')
            != source_contract['source_receipt_sha256']):
        raise ValueError('Recibo de revisão da origem alterado')
    approved = app.validate_review()
    browser_result = app.review.legacy.load(
        app.review.SOURCE / 'browser-result.json',
    )
    if source_contract['source_images'] != {
            name: browser_result['results'][name]['image']
            for name in ('base', 'live')}:
        raise ValueError('Imagens da origem aceita divergentes')
    for target in ('base', 'live'):
        expected = {
            name: {key: value for key, value in item.items() if key != 'text'}
            for name, item in app.render(
                approved['results'][target]['configuration'],
            ).items()
        }
        if json.loads(
                (source / 'bundles' / target / 'patch.json').read_text()
        ) != expected:
            raise ValueError('Patch da origem difere do renderizador aceito')
    validate_host_baseline(
        baseline, source_contract['host_critical_files'], critical_files(),
    )

    receipt = source / 'result.json'
    info = receipt.lstat()
    result = json.loads(receipt.read_text())
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
            or info.st_mode & 0o022
            or sha(receipt) != '4385bc18de48fffc0c1cf9b468e2a28741a98aa9600fd2d5999d8c5fc335c7f0'
            or result.get('status') != 'modern_full_views_verified'
            or result.get('contract_sha256') != SOURCE_APPROVAL
            or result.get('host_critical_unchanged') is not True
            or result.get('source_metadata_unchanged') is not True
            or result.get('source_images_modified') is not False
            or result.get('iso_generated') is not False
            or set(result.get('results', {})) != {'base', 'live'}):
        raise ValueError('Recibo de origem não aprovado')
    for name, record in SOURCE_IMAGES.items():
        image = result['results'][name]
        if (image.get('allowed_patch_verified') is not True
                or image.get('filesystem_check') != 'passed'
                or image.get('image', {}).get('file') != record['file']
                or image.get('image', {}).get('sha256') != record['sha256']):
            raise ValueError('Imagem de origem diverge do recibo: ' + name)
    return result


def prepare(resume_from=None):
    if os.geteuid() == 0 or os.getuid() != 1000:
        raise ValueError('Prepare como magaton, sem root')
    baseline = load_host_baseline()
    source_result = accepted_source(baseline)
    precedent.locked_browser_plan()
    required = 3 * source_result['results']['base']['allocated_bytes'] + 5 * source_result['results']['live']['allocated_bytes'] + RESERVE
    if shutil.disk_usage(ROOT).free < required:
        raise ValueError(f'Orçamento insuficiente: requer {required} bytes livres')
    old_contract = json.loads((SOURCE / 'contract.json').read_text())
    code = dict(old_contract['code_sha256'])
    code.update({
        WRAPPER: sha(ROOT / WRAPPER),
        ROOT_WORKER: sha(ROOT / ROOT_WORKER),
        'pipeline/devlite/modern_candidate.py': sha(ROOT / 'pipeline/devlite/modern_candidate.py'),
        'pipeline/devlite/public_apply.py': sha(ROOT / 'pipeline/devlite/public_apply.py'),
        'pipeline/devlite/final_payload.py': sha(ROOT / 'pipeline/devlite/final_payload.py'),
        'pipeline/devlite/public_execution.py': sha(ROOT / 'pipeline/devlite/public_execution.py'),
        'pipeline/devlite/modern_identity.py': sha(ROOT / 'pipeline/devlite/modern_identity.py'),
        'pipeline/devlite/customize/isolation_validation.py': sha(ROOT / 'pipeline/devlite/customize/isolation_validation.py'),
        'pipeline/devlite/customize/installation.py': sha(ROOT / 'pipeline/devlite/customize/installation.py'),
        'pipeline/devlite/minimal_root.py': sha(ROOT / 'pipeline/devlite/minimal_root.py'),
        'pipeline/devlite/release_layers.py': sha(ROOT / 'pipeline/devlite/release_layers.py'),
        'pipeline/devlite/release_pack.py': sha(ROOT / 'pipeline/devlite/release_pack.py'),
        'pipeline/devlite/release_resume.py': sha(ROOT / 'pipeline/devlite/release_resume.py'),
        'pipeline/devlite/runtime.py': sha(ROOT / 'pipeline/devlite/runtime.py'),
        'pipeline/devlite/structure.py': sha(ROOT / 'pipeline/devlite/structure.py'),
        'pipeline/devlite/build.py': sha(ROOT / 'pipeline/devlite/build.py'),
        'pipeline/devlite/public_iso.py': sha(ROOT / 'pipeline/devlite/public_iso.py'),
        'pipeline/devlite/validation.py': sha(ROOT / 'pipeline/devlite/validation.py'),
        'pipeline/devlite/minimal_build.py': sha(ROOT / 'pipeline/devlite/minimal_build.py'),
        'pipeline/devlite/customize/executor_contract.py': sha(ROOT / 'pipeline/devlite/customize/executor_contract.py'),
        'scripts/gerar-iso-modern-controlada.py': sha(ROOT / 'scripts/gerar-iso-modern-controlada.py'),
        'scripts/empacotar-modern-isolado.py': sha(ROOT / 'scripts/empacotar-modern-isolado.py'),
        'scripts/iniciar-modern-candidata-root.py':
            sha(ROOT / 'scripts/iniciar-modern-candidata-root.py'),
        'overlay/final-candidate/usr/share/applications/devlite-get-vscode.desktop':
            sha(ROOT / 'overlay/final-candidate/usr/share/applications/devlite-get-vscode.desktop'),
        **{source: sha(ROOT / source) for source in PAYLOAD_FILES},
    })
    if any(sha(ROOT / name) != digest for name, digest in code.items()):
        raise ValueError('Código de origem aceito foi alterado')
    job = owned_directory(ROOT / 'work', 'modern-candidate-pack-')
    payload = job / 'payload'
    payload.mkdir()
    package_payload(payload)
    bundle_sha = {
        path.relative_to(payload).as_posix(): sha(path)
        for path in payload.rglob('*') if path.is_file()
    }
    contract = {
        'schema': 1, 'operation': 'modern-candidate-pack-v1', 'job': str(job),
        'source_approval': SOURCE_APPROVAL,
        'source_result_sha256': sha(SOURCE / 'result.json'),
        'source_images': SOURCE_IMAGES, 'code_sha256': code,
        'reference_sha256': {
            name: sha(ROOT / name) for name in REFERENCE_FILES
        },
        'host_baseline': {
            'id': HOST_BASELINE_ID,
            'file': HOST_BASELINE_REFERENCE,
            'sha256': HOST_BASELINE_SHA256,
        },
        'bundle_sha256': bundle_sha, 'payload_manifest_sha256': sha(job / 'payload-manifest.json'),
        'host_critical_files': baseline['current_host_critical_files'],
        'host_namespaces': {
            name: os.readlink('/proc/self/ns/' + name)
            for name in ('mnt', 'pid', 'net', 'ipc', 'uts')
        },
        'limits': LIMITS, 'reserve_bytes': RESERVE,
        'initial_required_bytes': required,
        'iso_generated': False, 'guest_execution': False,
        'package_installation': False,
    }
    if resume_from is not None:
        contract['resume_checkpoint'] = checkpoint_reference(
            resume_from, bundle_sha, contract['payload_manifest_sha256'],
        )
        preflight_resume_checkpoint(contract['resume_checkpoint'], contract)
    save(job / 'contract.json', contract)
    approval = sha(job / 'contract.json')
    save(job / 'command.json', {
        'command': root_command(job, approval), 'approval_sha256': approval,
        'executed': False,
    })
    print(job)
    print(approval)
    print(shlex.join(root_command(job, approval)))


def execute(job, approval, authorized):
    if not authorized:
        raise ValueError('Use --execute-authorized')
    job, contract, _ = read_job(job, approval, root=True)
    if sha(job / 'payload-manifest.json') != contract['payload_manifest_sha256']:
        raise ValueError('Manifest de payload alterado')
    if any((job / name).exists() or (job / name).is_symlink()
           for name in ('execution.lock', 'attempt', 'pack-report.json', 'layers-ready.json')):
        raise ValueError('Job atual já iniciado; não reutilizar')
    if contract.get('resume_checkpoint') is not None:
        preflight_resume_checkpoint(contract['resume_checkpoint'], contract)
    command = root_command(job, approval)
    print(shlex.join(command))
    result = __import__('subprocess').run(command, check=False)
    if result.returncode:
        raise ValueError(f'Worker isolado falhou: {result.returncode}')
    report = job / 'pack-report.json'
    receipt = job / 'layers-ready.json'
    if (not report.is_file() or not receipt.is_file() or report.is_symlink()
            or receipt.is_symlink()):
        raise ValueError('Recibo de empacotamento ausente')
    result = json.loads(report.read_text())
    if result.get('status') != 'layers_verified' or result.get('cleanup_errors'):
        raise ValueError('Empacotamento não foi concluído com limpeza íntegra')
    print(report)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--job', type=Path)
    parser.add_argument('--approval-sha256')
    parser.add_argument('--execute-authorized', action='store_true')
    parser.add_argument('--resume-from', type=Path)
    args = parser.parse_args()
    if args.prepare:
        prepare(args.resume_from)
    else:
        execute(args.job, args.approval_sha256, args.execute_authorized)
