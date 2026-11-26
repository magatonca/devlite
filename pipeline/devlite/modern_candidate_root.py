"""Root-only clone, payload application, and layered-pack worker."""
import json
import os
import shutil
import stat
import re
from pathlib import Path

from .customize.isolation_validation import cgroup_limits, critical_files
from .customize.installation import compatibility, installed
from .minimal_root import allocated_usage, snapshot, EPOCH
from .modern_candidate import (
    HOST_BASELINE, LIMITS, ROOT, SOURCE_APPROVAL, SOURCE_IMAGES,
    checkpoint_contract_mismatches, read_job, save, sha,
)
from .public_apply import apply as apply_payload, tree_digest, validate_payload
from .public_execution import filesystem_proof
from .release_layers import clean_snapshot, manifests, materialize, recipe
from .release_pack import compress_args
from .release_resume import absent_xattrs
from .runtime import BuildError, Runner

REQUIRED = {
    'minimal.squashfs', 'minimal.live.squashfs', 'minimal.size',
    'minimal.live.size', 'filesystem.size', 'install-sources.yaml',
    'minimal.manifest', 'minimal.live.manifest', 'filesystem.manifest',
    'devlite-base.manifest.full',
}
PACK_RESERVE = 20 * 1024**3
ORIGINAL = ROOT / 'work/phase4b1-dhzezpnz/original-casper'
PLAN = ROOT / 'work/release-browser-2f24tvsg/plan.json'
VS_CODE_LAUNCHER = ROOT / 'overlay/final-candidate/usr/share/applications/devlite-get-vscode.desktop'
EXPECTED_INSTALLER_MARKER = 'ubuntu-desktop-bootstrap --try-or-install'
DEPENDENCIES = ('python3', 'python3-gi', 'gir1.2-gtk-3.0')


def require_package_status(root, plan, target):
    status_path = root / 'var/lib/dpkg/status'
    packages = installed(status_path.read_text())
    expected = plan['targets'][target]['final_versions']
    if packages != expected:
        raise BuildError('Pacotes da imagem diferem do plano aceito: ' + target)
    missing = [name for name in DEPENDENCIES if name not in packages]
    if missing:
        raise BuildError('Dependências GTK ausentes na imagem ' + target + ': ' + ', '.join(missing))
    return packages


def package_compatibility(base, live):
    result = compatibility(
        {'final_versions': base},
        {'final_versions': live},
    )
    result['live_only_versions'] = {
        package: live[package] for package in result['live_only_packages']
    }
    return result


def layer_compress_args(name, source, output, root):
    if name not in ('minimal.squashfs', 'minimal.live.squashfs'):
        raise BuildError('Camada SquashFS não suportada: ' + name)
    args = compress_args(source, output, root)
    if name == 'minimal.squashfs':
        args += ['-e', 'var/lib/devlite-executor']
    return args


def pin_existing_modern(root):
    wallpaper = root / 'usr/share/backgrounds/devlite/devlite-modern.svg'
    if wallpaper.is_symlink() or not wallpaper.is_file():
        raise BuildError('Wallpaper Modern ausente na imagem aceita')
    launcher = root / 'usr/share/applications/devlite-get-vscode.desktop'
    if launcher.is_symlink():
        raise BuildError('Lançador do VS Code é symlink')
    if launcher.is_file() and sha(launcher) != sha(VS_CODE_LAUNCHER):
        raise BuildError('Lançador do VS Code difere da versão oficial revisada')
    if launcher.is_file() and b'code.visualstudio.com' not in launcher.read_bytes():
        raise BuildError('Lançador não aponta para a fonte oficial do VS Code')
    return launcher.is_file()


def pin_installer(root):
    unit = root / 'usr/lib/systemd/user/xubuntu-installer.service'
    if unit.is_symlink() or not unit.is_file():
        raise BuildError('Serviço funcional do instalador não encontrado')
    if EXPECTED_INSTALLER_MARKER not in unit.read_text():
        raise BuildError('ExecStart do instalador não corresponde ao serviço aceito')
    if (root / 'usr/share/applications/devlite-installer.desktop').exists():
        raise BuildError('Atalho do instalador já existe; colisão bloqueada')


def source_root_from_contract(contract):
    roots = {
        Path(contract['source_images'][name]['file']).resolve().parents[1]
        for name in ('base', 'live')
    }
    if len(roots) != 1:
        raise BuildError('Imagens aceitas não compartilham a mesma origem')
    source_root = roots.pop()
    if source_root.parent != ROOT / 'work' or not source_root.name.startswith('modern-apply-'):
        raise BuildError('Origem das imagens fora do workspace Modern aceito')
    return source_root


def validate_candidate_payload_bundle(bundle, manifests):
    if bundle.is_symlink() or not bundle.is_dir():
        raise ValueError('Unsafe payload root')
    targets = {'base', 'live'}
    if not isinstance(manifests, dict) or set(manifests) != targets:
        raise ValueError('Unexpected payload targets')
    actual = {path.name for path in bundle.iterdir()}
    if actual != targets:
        missing = sorted(targets - actual)
        extra = sorted(actual - targets)
        raise ValueError(
            f'Payload target coverage differs: missing={missing}, extra={extra}'
        )
    for target in sorted(targets):
        validate_payload(bundle / target, manifests[target])


def ensure_fresh_job(job):
    pending = ('execution.lock', 'attempt', 'pack-report.json', 'layers-ready.json')
    if any((job / name).exists() or (job / name).is_symlink() for name in pending):
        raise BuildError('Job já iniciado ou com recibos; não reutilizar')


def validate_checkpoint_tree(report, target, tree):
    expected = report['results'][target]['file_audit']['after_tree_sha256']
    if tree_digest(tree) != expected:
        raise BuildError('Árvore do checkpoint diverge da auditoria: ' + target)


def validate_resume_checkpoint(job, checkpoint, contract, plan):
    expected_fields = {
        'job', 'approval_sha256', 'contract_sha256', 'report_sha256',
        'worker_sha256',
    }
    if not isinstance(checkpoint, dict) or set(checkpoint) != expected_fields:
        raise BuildError('Referência de checkpoint incompleta')
    source_job = Path(checkpoint['job'])
    if (source_job.is_symlink() or source_job == job
            or source_job.resolve().parent != (ROOT / 'work').resolve()
            or not source_job.name.startswith('modern-candidate-pack-')):
        raise BuildError('Job de checkpoint fora do workspace autorizado')
    job_info = source_job.lstat()
    if (not stat.S_ISDIR(job_info.st_mode) or job_info.st_uid != os.geteuid()
            or job_info.st_mode & 0o022):
        raise BuildError('Ownership/permissões do job de checkpoint inesperados')
    contract_path = source_job / 'contract.json'
    report_path = source_job / 'pack-report.json'
    lock_path = source_job / 'execution.lock'
    for path in (contract_path, report_path, lock_path):
        if path.is_symlink() or not path.is_file():
            raise BuildError('Recibo de checkpoint ausente ou inseguro')
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o022:
            raise BuildError('Recibo de checkpoint modificável por grupo/outros')
        if path != contract_path and info.st_uid != os.geteuid():
            raise BuildError('Relatório/lock de checkpoint não pertence ao worker')
    if sha(contract_path) != checkpoint['contract_sha256']:
        raise BuildError('Contrato de checkpoint alterado')
    previous = json.loads(contract_path.read_text())
    approval = checkpoint['contract_sha256']
    if lock_path.read_text() != approval:
        raise BuildError('Lock de checkpoint não corresponde ao contrato selado')
    mismatches = checkpoint_contract_mismatches(
        previous, checkpoint, contract,
    )
    if mismatches:
        raise BuildError(
            'Contrato de checkpoint não corresponde ao job atual: '
            + ', '.join(mismatches)
        )
    if sha(report_path) != checkpoint['report_sha256']:
        raise BuildError('Relatório de checkpoint alterado')
    previous_report = json.loads(report_path.read_text())
    if (previous_report.get('status') != 'quarantined'
            or previous_report.get('contract_sha256') != approval
            or previous_report.get('phase') != 'e2fsck-live'
            or previous_report.get('error') != 'Pacotes Base e Live divergentes'
            or previous_report.get('source_images_modified') is not False
            or previous_report.get('iso_generated') is not False
            or previous_report.get('target_programs_executed') is not False
            or previous_report.get('cleanup_errors') != []
            or set(previous_report.get('results', {})) != {'base', 'live'}):
        raise BuildError('Tentativa anterior não é um checkpoint recuperável')
    if ((source_job / 'layers-ready.json').exists()
            or (source_job / 'published-casper').exists()
            or (source_job / 'published-casper').is_symlink()):
        raise BuildError('Job de checkpoint já publicou artefatos')
    attempt = source_job / 'attempt'
    if (attempt.is_symlink() or not attempt.is_dir()
            or attempt.stat().st_uid != os.geteuid()):
        raise BuildError('Diretório de checkpoint ausente ou inseguro')
    clones = {}
    source_metadata = {}
    clone_hashes = {}
    for target in ('base', 'live'):
        audit = previous_report['results'][target].get('file_audit', {})
        if (previous_report['results'][target].get('package_count')
                != len(plan['targets'][target]['final_versions'])
                or audit.get('only_declared_additions') is not True
                or audit.get('target_programs_executed') is not False
                or not re.fullmatch(r'[0-9a-f]{64}', audit.get('after_tree_sha256', ''))):
            raise BuildError('Auditoria de checkpoint incompleta: ' + target)
        source = Path(contract['source_images'][target]['file'])
        source_info = source.lstat()
        if (not stat.S_ISREG(source_info.st_mode) or source_info.st_uid != os.geteuid()
                or source_info.st_mode & 0o022
                or sha(source) != contract['source_images'][target]['sha256']):
            raise BuildError('Imagem fonte mudou desde o checkpoint: ' + target)
        source_metadata[target] = (
            source_info.st_dev, source_info.st_ino, source_info.st_size,
            source_info.st_mtime_ns, source_info.st_ctime_ns,
        )
        clone = attempt / (target + '.ext4')
        before = clone.lstat()
        if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.geteuid()
                or stat.S_IMODE(before.st_mode) != 0o600 or before.st_nlink != 1
                or before.st_size != source_info.st_size):
            raise BuildError('Imagem clonada não atende ao perfil de checkpoint: ' + target)
        clone_hash = sha(clone)
        after = clone.stat()
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise BuildError('Imagem clonada mudou durante a verificação: ' + target)
        clones[target] = clone
        clone_hashes[target] = clone_hash
    return {
        'job': source_job, 'report': previous_report, 'clones': clones,
        'source_metadata': source_metadata, 'clone_sha256': clone_hashes,
    }


def run(job, approval, authorized):
    if not authorized or os.geteuid() != 0 or os.getpid() != 1:
        raise BuildError('Exige aprovação e namespace root PID1')
    job, contract, _ = read_job(job, approval, root=True)
    if critical_files() != contract['host_critical_files']:
        raise BuildError('Baseline crítico do host mudou')
    if any(os.readlink('/proc/self/ns/' + name) == value
           for name, value in contract['host_namespaces'].items()):
        raise BuildError('Namespaces privados ausentes')
    cgroup_entries = Path('/proc/self/cgroup').read_text().splitlines()
    unified = next((line.partition('::')[2] for line in cgroup_entries
                    if '::' in line), None)
    if not unified:
        raise BuildError('Worker exige cgroup v2 unificado')
    group = Path('/sys/fs/cgroup') / unified.lstrip('/')
    if group.name != 'devlite-' + job.name + '.service':
        raise BuildError('Cgroup de serviço inesperado')
    limits = cgroup_limits(group, LIMITS)
    if 'NoNewPrivs:\t1' not in Path('/proc/self/status').read_text():
        raise BuildError('NoNewPrivileges ausente')
    source_root = source_root_from_contract(contract)
    checkpoint_spec = contract.get('resume_checkpoint')
    protected_paths = (
        tuple(contract['host_critical_files'])
        + (str(source_root), str(HOST_BASELINE))
    )
    if checkpoint_spec is not None:
        if not isinstance(checkpoint_spec, dict) or not isinstance(checkpoint_spec.get('job'), str):
            raise BuildError('Referência de checkpoint inválida')
        checkpoint_path = Path(checkpoint_spec['job'])
        if (checkpoint_path.is_symlink()
                or checkpoint_path.resolve().parent != (ROOT / 'work').resolve()):
            raise BuildError('Job de checkpoint fora do workspace autorizado')
        protected_paths += (str(checkpoint_path),)
    filesystem_proof(
        Path('/proc/self/mountinfo').read_text(), job, protected_paths,
    )
    if any(line.split(':')[0].strip() not in ('lo', 'Inter-|face') for line in
           Path('/proc/net/dev').read_text().splitlines() if ':' in line):
        raise BuildError('Interface de rede externa visível')
    required_initial = contract['initial_required_bytes']
    if shutil.disk_usage(job).free < required_initial:
        raise BuildError('Espaço livre abaixo do orçamento selado')
    ensure_fresh_job(job)
    with (job / 'execution.lock').open('x') as stream:
        stream.write(approval)
    os.chown(job, 0, 0)
    job.chmod(0o700)
    attempt = job / 'attempt'
    attempt.mkdir(mode=0o700)
    (attempt / 'logs').mkdir()
    runner = Runner(attempt / 'logs', EPOCH)
    runner.env.pop('SOURCE_DATE_EPOCH', None)
    mounted = []
    source_metadata = {}
    report = {
        'status': 'running', 'contract_sha256': approval,
        'source_images_modified': False, 'iso_generated': False,
        'target_programs_executed': False, 'limits': limits,
        'results': {}, 'cleanup_errors': [],
    }

    def persist():
        with (job / 'pack-report.json').open('w') as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write('\n')

    def call(label, args):
        if shutil.disk_usage(job).free < PACK_RESERVE:
            raise BuildError('Reserva mínima de 20 GiB atingida')
        report['phase'] = label
        persist()
        runner.run(label, args)

    def unmount(path):
        call('umount-' + path.name, ['umount', str(path)])
        mounted.remove(path)

    try:
        call('private-mounts', ['mount', '--make-rprivate', '/'])
        bundle = job / 'payload'
        for path in [bundle, *bundle.rglob('*')]:
            if path.is_symlink():
                raise BuildError('Symlink no payload')
            os.chown(path, 0, 0)
            if path.is_dir():
                path.chmod(0o755)
            elif path.is_file():
                path.chmod(0o644)
        manifest = json.loads((job / 'payload-manifest.json').read_text())
        validate_candidate_payload_bundle(bundle, manifest)
        plan = json.loads(PLAN.read_text())
        clones = {}
        package_states = {}
        checkpoint_result = None
        if checkpoint_spec is None:
            for target in ('base', 'live'):
                source = Path(SOURCE_IMAGES[target]['file'])
                record = SOURCE_IMAGES[target]
                info = source.lstat()
                if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022
                        or sha(source) != record['sha256']):
                    raise BuildError('Imagem fonte não autenticada: ' + target)
                source_metadata[target] = (
                    info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns,
                )
                clone = attempt / (target + '.ext4')
                call('clone-' + target, [
                    'cp', '--reflink=auto', '--sparse=always', '--no-clobber',
                    '--', str(source), str(clone),
                ])
                clone.chmod(0o600)
                if sha(clone) != record['sha256']:
                    raise BuildError('Clone difere da imagem aceita: ' + target)
                root = attempt / (target + '-root')
                root.mkdir()
                call('mount-' + target, [
                    'mount', '-t', 'ext4', '-o', 'loop,rw,noatime,nodev,nosuid,noexec',
                    str(clone), str(root),
                ])
                mounted.append(root)
                package_states[target] = require_package_status(root, plan, target)
                has_vscode_launcher = pin_existing_modern(root)
                if target == 'live':
                    pin_installer(root)
                apply_bundle = attempt / ('payload-' + target)
                shutil.copytree(bundle / target, apply_bundle, symlinks=True)
                if has_vscode_launcher:
                    launcher_path = 'usr/share/applications/devlite-get-vscode.desktop'
                    (apply_bundle / launcher_path).unlink()
                    manifest[target].pop(launcher_path)
                audit = apply_payload(root, apply_bundle, manifest[target])
                report['results'][target] = {
                    'file_audit': audit, 'package_count': len(package_states[target]),
                }
                unmount(root)
                call('e2fsck-' + target, ['e2fsck', '-f', '-n', str(clone)])
                clones[target] = clone
        else:
            checkpoint_result = validate_resume_checkpoint(
                job, checkpoint_spec, contract, plan,
            )
            source_metadata.update(checkpoint_result['source_metadata'])
            clones.update(checkpoint_result['clones'])
            report['resumed_from'] = str(checkpoint_result['job'])
            report['resume_checkpoint'] = {
                'contract_sha256': checkpoint_spec['contract_sha256'],
                'report_sha256': checkpoint_spec['report_sha256'],
                'clone_sha256': checkpoint_result['clone_sha256'],
                'ext4_checked': {},
                'trees_verified': {},
            }
            for target in ('base', 'live'):
                previous = checkpoint_result['report']['results'][target]
                report['results'][target] = previous
                call('checkpoint-e2fsck-' + target, [
                    'e2fsck', '-f', '-n', str(clones[target]),
                ])
                report['resume_checkpoint']['ext4_checked'][target] = True

        trees, roots = {}, {}
        for target in ('base', 'live'):
            root = attempt / ('pack-' + target)
            root.mkdir()
            call('mount-ro-' + target, [
                'mount', '-t', 'ext4',
                '-o', 'loop,ro,noload,nodev,nosuid,noexec',
                str(clones[target]), str(root),
            ])
            mounted.append(root)
            roots[target] = root
            package_states[target] = require_package_status(root, plan, target)
        package_comparison = package_compatibility(
            package_states['base'], package_states['live'],
        )
        report['package_compatibility'] = package_comparison
        if (package_comparison['base_packages_missing_live']
                or package_comparison['common_version_conflicts']):
            raise BuildError('Pacotes Base/Live incompatíveis com o plano aceito')
        for target in ('base', 'live'):
            original = Path(SOURCE_IMAGES[target]['file'])
            info = original.stat()
            if source_metadata[target] != (
                info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns,
            ):
                raise BuildError('Metadados da imagem fonte mudaram')
            raw_tree = snapshot(roots[target])
            if checkpoint_result is not None:
                validate_checkpoint_tree(checkpoint_result['report'], target, raw_tree)
                report['resume_checkpoint']['trees_verified'][target] = tree_digest(raw_tree)
            trees[target] = clean_snapshot(raw_tree)
        actual_required = 3 * allocated_usage(roots['base']) + 5 * allocated_usage(roots['live']) + PACK_RESERVE
        if shutil.disk_usage(job).free < actual_required:
            raise BuildError('Espaço livre inferior ao orçamento de empacotamento')
        delta = recipe(trees['base'], trees['live'])
        delta_root = attempt / 'delta'
        delta_tree = materialize(roots['live'], delta_root, delta, EPOCH)
        packed = attempt / 'packed'
        packed.mkdir()
        verified = {}
        for name, source, expected in (
            ('minimal.squashfs', roots['base'], trees['base']),
            ('minimal.live.squashfs', delta_root, delta_tree),
        ):
            output = packed / name
            call('compress-' + name, layer_compress_args(
                name, source, output, expected['.'],
            ))
            extracted = attempt / ('verify-' + name)
            call('roundtrip-' + name, [
                'unsquashfs', '-strict-errors', '-processors', '1',
                '-data-queue', '64', '-frag-queue', '64',
                '-d', str(extracted), str(output),
            ])
            if snapshot(extracted) != expected:
                raise BuildError('Round-trip SquashFS divergiu: ' + name)
            verified[name] = {
                'sha256': sha(output), 'uncompressed_bytes': allocated_usage(extracted),
                'entries': len(expected),
            }
        mounted_squash = []
        for alias, file in (('base', 'minimal.squashfs'), ('delta', 'minimal.live.squashfs')):
            target = attempt / ('mounted-' + alias)
            target.mkdir()
            call('mount-squash-' + alias, [
                'mount', '-t', 'squashfs', '-o', 'loop,ro,nodev,nosuid',
                str(packed / file), str(target),
            ])
            mounted.append(target)
            mounted_squash.append(target)
        merged = attempt / 'mounted-merged'
        merged.mkdir()
        call('kernel-compose', [
            'mount', '-t', 'overlay', 'overlay', '-o',
            'ro,lowerdir=' + str(mounted_squash[1]) + ':' + str(mounted_squash[0]),
            str(merged),
        ])
        mounted.append(merged)
        absence = absent_xattrs(packed / 'minimal.live.squashfs', delta_tree)
        absence = frozenset(
            name for name in absence
            if name in trees['live'] and not trees['live'][name].get('xattrs')
        )
        if snapshot(merged, xattr_absence=absence) != trees['live']:
            raise BuildError('Composição do kernel difere da visão Live')
        for path in list(reversed(mounted)):
            unmount(path)

        values = manifests(
            package_states['base'], package_states['live'],
            (ORIGINAL / 'filesystem.manifest').read_text(),
        )
        values.update({
            'minimal.size': str(verified['minimal.squashfs']['uncompressed_bytes']) + '\n',
            'minimal.live.size': str(verified['minimal.live.squashfs']['uncompressed_bytes']) + '\n',
            'filesystem.size': str(sum(item['uncompressed_bytes'] for item in verified.values())) + '\n',
        })
        catalog, count = re.subn(
            r'^  size: [0-9]+$',
            '  size: ' + str(verified['minimal.squashfs']['uncompressed_bytes']),
            (ORIGINAL / 'install-sources.yaml').read_text(), flags=re.M,
        )
        if count != 1 or 'type: fsimage-layered' not in catalog or 'path: minimal.squashfs' not in catalog:
            raise BuildError('Catálogo do instalador incompatível')
        values['install-sources.yaml'] = catalog
        published = job / 'published-casper'
        published.mkdir(mode=0o755)
        for name, item in verified.items():
            shutil.copyfile(packed / name, published / name)
            (published / name).chmod(0o444)
        for name, text in values.items():
            (published / name).write_text(text)
            (published / name).chmod(0o444)
        for name, expected in SOURCE_IMAGES.items():
            info = Path(expected['file']).stat()
            if source_metadata[name] != (
                info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns,
            ):
                raise BuildError('Metadados da imagem original mudaram')
        if critical_files() != contract['host_critical_files']:
            raise BuildError('Baseline crítico do host mudou durante a compilação')
        if set(path.name for path in published.iterdir()) != REQUIRED:
            raise BuildError('Conjunto de camadas publicado divergente')
        receipt = {
            'status': 'layers_verified', 'job_sha256': approval,
            'modern_contract_sha256': SOURCE_APPROVAL,
            'published': str(published), 'layers': verified,
            'files': {path.name: sha(path) for path in sorted(published.iterdir())},
            'kernel_composition_verified': True, 'roundtrip_verified': True,
            'source_metadata_unchanged': True, 'host_critical_unchanged': True,
            'iso_generated': False, 'package_states': package_states,
        }
        save(job / 'layers-ready.json', receipt)
        (job / 'layers-ready.json').chmod(0o444)
        report.update(
            status='layers_verified', free_bytes=shutil.disk_usage(job).free,
            layers=verified, actual_required_bytes=actual_required,
        )
    except BaseException as error:
        report.update(status='quarantined', error=str(error))
        raise
    finally:
        for path in list(reversed(mounted)):
            try:
                runner.run('cleanup-umount-' + path.name, ['umount', str(path)])
                mounted.remove(path)
            except BaseException as error:
                report['cleanup_errors'].append(str(error))
        persist()
        (job / 'pack-report.json').chmod(0o444)
        job.chmod(0o755)
    return job / 'pack-report.json'


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--job', type=Path, required=True)
    parser.add_argument('--approval-sha256', required=True)
    parser.add_argument('--execute-authorized', action='store_true')
    args = parser.parse_args()
    try:
        run(args.job, args.approval_sha256, args.execute_authorized)
    except (OSError, ValueError, BuildError) as error:
        raise SystemExit(str(error))
