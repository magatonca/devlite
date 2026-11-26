#!/usr/bin/env python3
"""Build one isolated ISO candidate from sealed Modern layers."""
import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.devlite.build import EXPECTED, NAME, detect, validate_layout
from pipeline.devlite.minimal_build import compare_iso_trees, make_md5
from pipeline.devlite.minimal_root import EPOCH
from pipeline.devlite.modern_candidate import (
    HOST_BASELINE_V3_EVIDENCE_REFERENCE,
    HOST_BASELINE_V3_REFERENCE,
    read_approved_pack_for_iso,
    save,
    sha,
)

from pipeline.devlite.modern_identity_v4 import brand_grub_v4
from pipeline.devlite.modern_validation_v4 import validate_layout_v4
from pipeline.devlite.modern_catalog_v4 import render_install_catalog_v4
from pipeline.devlite.modern_integration_v4 import (
    prepare_fix_layers,
    build_layer_metadata,
)

from pipeline.devlite.modern_identity import brand_grub_titles, set_grub_layer_path
from pipeline.devlite.public_iso import REQUIRED, ready_layers
from pipeline.devlite.runtime import BuildError, Runner, owned_directory
from pipeline.devlite.structure import compare_boot_metadata, region_digest
from pipeline.devlite.validation import inventory, iso_metadata, verify_manifest
from pipeline.devlite.modern_visual import (
    DEVLITE_WALLPAPER,
    INSTALL_LAYER,
    LAYER_MAX_BYTES,
    LIVE_LAYER,
    XFCE_CONFIG,
    build_visual_layer,
    layer_stack,
    preflight_visual_sources,
    remove_md5_entries,
    render_install_catalog,
)

ENTRY = 'scripts/gerar-iso-modern-v4.py'
BASELINE = ROOT / 'artifacts/modern-release-vz4edu99/devlite-os-1.0-amd64.iso'
SOURCE_ISO = ROOT / 'sources' / NAME
GRUB_SOURCE = ROOT / 'work/phase4b1-dhzezpnz/original-grub'
CASPER_SOURCE = ROOT / 'work/phase4b1-dhzezpnz/original-casper'
MD5_SOURCE = ROOT / 'work/phase4b1-dhzezpnz/original-md5sum.txt'
TRUSTED_KEYS = ROOT / 'sources/verification/trustedkeys.gpg'
GIB = 1024**3
RESERVE = 20 * GIB
CODE = (
    'pipeline/devlite/build.py',
    'pipeline/devlite/minimal_build.py',
    'pipeline/devlite/minimal_root.py',
    'pipeline/devlite/modern_candidate.py',
    'pipeline/devlite/modern_identity.py',
    'pipeline/devlite/modern_visual.py',
    'pipeline/devlite/public_iso.py',
    'pipeline/devlite/runtime.py',
    'pipeline/devlite/structure.py',
    'pipeline/devlite/validation.py',
    'scripts/empacotar-modern-candidata.py',
    'scripts/gerar-iso-modern-controlada.py',
    'scripts/empacotar-modern-isolado.py',
)


def save_new(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def verified_pack(job, approval):
    job, contract, _ = read_approved_pack_for_iso(job, approval, root=True)
    report_path = job / 'pack-report.json'
    if (report_path.is_symlink() or not report_path.is_file()
            or report_path.stat().st_uid != 0
            or report_path.stat().st_mode & 0o022):
        raise BuildError('Relatório do empacotamento precisa ser root-owned e selado')
    report = json.loads(report_path.read_text())
    receipt = ready_layers(job, approval)
    validate_pack_report(report, receipt, approval)
    return job, contract, report, receipt


def validate_pack_report(report, receipt, approval):
    if (report.get('status') != 'layers_verified'
            or report.get('contract_sha256') != approval
            or report.get('source_images_modified') is not False
            or report.get('iso_generated') is not False
            or report.get('target_programs_executed') is not False
            or report.get('cleanup_errors') != []
            or report.get('layers') != receipt.get('layers')
            or receipt.get('job_sha256') != approval
            or receipt.get('status') != 'layers_verified'
            or receipt.get('kernel_composition_verified') is not True
            or receipt.get('roundtrip_verified') is not True
            or receipt.get('source_metadata_unchanged') is not True
            or receipt.get('host_critical_unchanged') is not True
            or receipt.get('iso_generated') is not False
            or set(report.get('results', {})) != {'base', 'live'}
            or set(receipt.get('package_states', {})) != {'base', 'live'}):
        raise BuildError('Recibos das camadas não comprovam sucesso para este contrato')
    compatibility = report.get('package_compatibility', {})
    if (compatibility.get('base_packages_missing_live') != []
            or compatibility.get('common_version_conflicts') != {}):
        raise BuildError('Compatibilidade de pacotes Base/Live não foi validada')
    for target in ('base', 'live'):
        result = report['results'][target]
        audit = result.get('file_audit', {})
        if (result.get('package_count') != len(receipt['package_states'][target])
                or audit.get('only_declared_additions') is not True
                or audit.get('target_programs_executed') is not False
                or not re.fullmatch(r'[0-9a-f]{64}', audit.get('before_tree_sha256', ''))
                or not re.fullmatch(r'[0-9a-f]{64}', audit.get('after_tree_sha256', ''))):
            raise BuildError('Auditoria de camada ausente ou incompleta: ' + target)


def visual_layer_profile(input_validation):
    return {
        'installer_path': INSTALL_LAYER,
        'live_path': LIVE_LAYER,
        'wallpaper_path': DEVLITE_WALLPAPER,
        'xfce_config': XFCE_CONFIG,
        'plymouth_default_theme': 'DevLite OS 1.0',
        'plymouth_text_theme': 'DevLite OS 1.0',
        'plymouth_initramfs': 'unchanged; upstream Xubuntu splash remains',
        'os_release_logo': 'devlite',
        'max_bytes': LAYER_MAX_BYTES,
        'input_validation': input_validation,
    }


def required_assembly_bytes(source_bytes, published):
    total = sum(
        (published / name).stat().st_size
        for name in ('minimal.squashfs', 'minimal.live.squashfs')
    )
    return 2 * source_bytes + 3 * (total + LAYER_MAX_BYTES) + RESERVE


def validate_visual_layout(tree):
    casper = tree / 'casper'
    expected_layers = sorted((
        'minimal.squashfs', INSTALL_LAYER, LIVE_LAYER,
    ))
    layers = sorted(path.name for path in casper.glob('*.squashfs'))
    if layers != expected_layers:
        raise BuildError(f'Cadeia SquashFS visual inesperada: {layers}')
    if (layer_stack(INSTALL_LAYER) != ('minimal.squashfs', INSTALL_LAYER)
            or layer_stack(LIVE_LAYER) != (
                'minimal.squashfs', INSTALL_LAYER, LIVE_LAYER,
            )):
        raise BuildError('Nomes das camadas não formam as cadeias aprovadas')

    catalog = (casper / 'install-sources.yaml').read_text()
    required_catalog_lines = (
        '- default: true',
        '  id: xubuntu-desktop-minimal',
        '  locale_support: langpack',
        '  name:\n    en: DevLite OS 1.0',
        '  description:\n    en: A minimal installation of DevLite OS 1.0.',
        '  path: ' + INSTALL_LAYER,
        '  type: fsimage-layered',
        '  variant: desktop',
    )
    if any(catalog.count(line) != 1 for line in required_catalog_lines):
        raise BuildError('Catálogo visual não preserva os identificadores esperados')

    try:
        base_size = int((casper / 'minimal.size').read_text().strip())
        live_size = int((casper / 'minimal.live.size').read_text().strip())
        visual_size = int((casper / 'minimal.visual.size').read_text().strip())
        filesystem_size = int((casper / 'filesystem.size').read_text().strip())
        catalog_sizes = re.findall(r'(?m)^  size: ([0-9]+)$', catalog)
        if len(catalog_sizes) != 1:
            raise ValueError('Tamanho do catálogo ausente ou ambíguo')
        catalog_size = int(catalog_sizes[0])
    except (OSError, ValueError, AttributeError) as error:
        raise BuildError('Metadados de tamanho da cadeia visual inválidos') from error
    if (min(base_size, live_size, visual_size) <= 0
            or catalog_size != base_size + visual_size
            or filesystem_size != base_size + live_size + visual_size):
        raise BuildError('Tamanhos do catálogo ou das camadas não correspondem')

    required_files = (
        'casper/initrd', 'casper/vmlinuz', 'casper/filesystem.manifest',
        'casper/minimal.manifest', 'casper/minimal.live.manifest',
        'EFI/boot/bootx64.efi', 'EFI/boot/grubx64.efi', 'boot/grub/grub.cfg',
    )
    for name in required_files:
        if not (tree / name).is_file():
            raise BuildError(f'Componente essencial ausente: {name}')
    if 'snap:ubuntu-desktop-bootstrap' not in (
            casper / 'filesystem.manifest').read_text():
        raise BuildError('Instalador Desktop Bootstrap não identificado')
    try:
        release = json.loads((casper / 'devlite-release.json').read_text())
    except (OSError, ValueError) as error:
        raise BuildError('Relatório de identidade visual ausente ou inválido') from error
    expected_plymouth = {
        'rootfs_default_theme': 'DevLite OS 1.0',
        'rootfs_text_theme': 'DevLite OS 1.0',
        'live_initramfs': 'unchanged; upstream Xubuntu splash remains',
    }
    if release.get('plymouth') != expected_plymouth:
        raise BuildError('Identidade Plymouth não corresponde à camada visual')
    for name in ('grub.cfg', 'loopback.cfg'):
        path = tree / 'boot/grub' / name
        if path.is_file() and set_grub_layer_path(path.read_text()) != path.read_text():
            raise BuildError('GRUB não seleciona a cadeia live visual: ' + name)
    if not (tree / 'boot/grub/loopback.cfg').is_file():
        raise BuildError('Configuração GRUB loopback ausente')
    return layers


def audit_visual_iso(runner, source, candidate, workspace, mapped, provenance):
    before_boot = detect(runner, source, 'source')
    after_boot = detect(runner, candidate, 'candidate')
    compare_boot_metadata(source, candidate, before_boot, after_boot)
    if after_boot['volume_id'] != 'DevLite OS 1.0 Candidate':
        raise BuildError('Rótulo do candidato público incorreto')
    if before_boot['timestamp'] != after_boot['timestamp']:
        raise BuildError('UUID de volume mudou')
    if region_digest(source, before_boot['efi_offset'], before_boot['efi_bytes']) != region_digest(
            candidate, after_boot['efi_offset'], after_boot['efi_bytes']):
        raise BuildError('EFI anexada alterada')

    source_tree = workspace / 'source-tree'
    result_tree = workspace / 'result-tree'
    for image, target, label in (
            (source, source_tree, 'source'),
            (candidate, result_tree, 'candidate')):
        runner.xorriso(label + '-tree', '-osirrox', 'on', '-indev', image, '-extract', '/', target)
        if label == 'source':
            validate_layout(target)
        else:
            validate_layout_v4(target)

            # Verificações essenciais preservadas da auditoria v3.
            required_files = (
                'casper/initrd',
                'casper/vmlinuz',
                'casper/filesystem.manifest',
                'casper/minimal.manifest',
                'casper/minimal.live.manifest',
                'EFI/boot/bootx64.efi',
                'EFI/boot/grubx64.efi',
                'boot/grub/grub.cfg',
                'boot/grub/loopback.cfg',
            )

            for required in required_files:
                if not (target / required).is_file():
                    raise BuildError(
                        'Componente essencial ausente: ' + required
                    )

            if 'snap:ubuntu-desktop-bootstrap' not in (
                target / 'casper/filesystem.manifest'
            ).read_text():
                raise BuildError(
                    'Instalador Desktop Bootstrap não identificado'
                )
    before, after = inventory(source_tree), inventory(result_tree)
    additions = set(provenance) | {
        'casper/devlite-provenance', 'casper/devlite-release.json',
        'casper/devlite-base.manifest.full', 'casper/devlite-components.json',
        'casper/minimal.visual.squashfs',
        'casper/minimal.visual.live.squashfs',
        'casper/minimal.visual.fix.squashfs',
        'casper/minimal.visual.live.fix.squashfs',
        'casper/minimal.visual.size',
        'casper/minimal.visual.fix.size',
        'casper/minimal.visual.live.fix.size',
    }
    removed = {'casper/SHA256SUMS.gpg', 'casper/minimal.live.squashfs'}
    compare_iso_trees(
        before, after, source_tree, result_tree, set(mapped), additions, removed,
    )
    for name, file in {**mapped, **provenance}.items():
        if sha(result_tree / name) != sha(file):
            raise BuildError('Arquivo ISO diverge do payload: ' + name)
    old_metadata = iso_metadata(runner.xorriso(
        'source-metadata', '-indev', source, '-find', '/', '-exec', 'lsdl', '--',
    ))
    new_metadata = iso_metadata(runner.xorriso(
        'candidate-metadata', '-indev', candidate, '-find', '/', '-exec', 'lsdl', '--',
    ))
    for name in old_metadata.keys() & new_metadata.keys():
        if (name.lstrip('/') not in set(mapped) | additions | {'boot.catalog'}
                and old_metadata[name] != new_metadata[name]):
            raise BuildError('Metadados ISO inesperados: ' + name)
    for name in set(mapped) | set(provenance):
        value = new_metadata['/' + name]
        if value[0] != '-r--r--r--' or value[2:4] != ['0', '0']:
            raise BuildError('UID/GID/modo ISO incorreto')
    md5 = verify_manifest(result_tree, Path('md5sum.txt'), 'md5')
    layers = verify_manifest(result_tree, Path('casper/SHA256SUMS'), 'sha256')
    runner.run('original-provenance', [
        'gpgv', '--homedir', str(ROOT / 'sources/verification'),
        '--keyring', str(TRUSTED_KEYS),
        str(result_tree / 'casper/devlite-provenance/original-SHA256SUMS.gpg'),
        str(result_tree / 'casper/devlite-provenance/original-SHA256SUMS'),
    ])
    return {
        'boot_structure': after_boot, 'md5_entries': md5,
        'layer_checksums': layers, 'boot_vm': 'not_tested',
        'installation_vm': 'not_tested',
        'plymouth_rootfs': 'devlite',
        'plymouth_initramfs': 'upstream_xubuntu_unchanged',
        'initramfs_sha256': sha(result_tree / 'casper/initrd'),
    }


def prepare(pack_job, pack_approval):
    if os.getuid() != 1000 or os.geteuid() == 0:
        raise BuildError('Preparação da ISO deve rodar como magaton, sem root')
    for tool in ('mksquashfs', 'unsquashfs'):
        if shutil.which(tool) is None:
            raise BuildError(f'Ferramenta necessária ausente: {tool}; não instalar automaticamente')
    pack, pack_contract, report, receipt = verified_pack(pack_job, pack_approval)
    visual_inputs = preflight_visual_sources(
        pack / 'published-casper/minimal.squashfs',
        pack / 'published-casper/minimal.live.squashfs',
    )
    try:
        base_size = int((pack / 'published-casper/minimal.size').read_text().strip())
        live_size = int((pack / 'published-casper/minimal.live.size').read_text().strip())
        filesystem_size = int((pack / 'published-casper/filesystem.size').read_text().strip())
        render_install_catalog(
            (pack / 'published-casper/install-sources.yaml').read_text(),
            base_size, 1,
        )
    except (OSError, ValueError) as error:
        raise BuildError(f'Metadados visuais ou de tamanho incompatíveis: {error}') from error
    if filesystem_size != base_size + live_size:
        raise BuildError('Tamanho agregado das camadas aprovadas é inconsistente')
    try:
        remove_md5_entries(
            MD5_SOURCE.read_text(), {'casper/minimal.live.squashfs'},
        )
        for file in sorted(GRUB_SOURCE.glob('*.cfg')):
            text = file.read_text()
            if ('linux /casper/vmlinuz' in text
                    or '\tlinux\t/casper/vmlinuz' in text):
                set_grub_layer_path(brand_grub_titles(text))
    except (OSError, ValueError) as error:
        raise BuildError(f'Preflight de GRUB ou MD5 falhou: {error}') from error
    if SOURCE_ISO.is_symlink() or sha(SOURCE_ISO) != EXPECTED:
        raise BuildError('ISO oficial de origem não confere')
    if BASELINE.is_symlink() or not BASELINE.is_file():
        raise BuildError('ISO aprovada anterior não foi encontrada para preservação')
    if sha(BASELINE) != '7373cb9be11ebda5218f20795fec87eab20c2cebef3c763ae6e5c63d4e7cd7bd':
        raise BuildError('Hash da ISO aprovada anterior diverge')
    required_bytes = required_assembly_bytes(
        SOURCE_ISO.stat().st_size, pack / 'published-casper',
    )
    available_bytes = shutil.disk_usage(ROOT).free
    if available_bytes < required_bytes:
        raise BuildError(
            f'Espaço insuficiente para montagem e auditoria ISO: '
            f'requer {required_bytes} bytes; disponível {available_bytes}'
        )
    references = {
        str(path.relative_to(ROOT)): sha(path)
        for path in (
            MD5_SOURCE, CASPER_SOURCE / 'SHA256SUMS',
            CASPER_SOURCE / 'SHA256SUMS.gpg', TRUSTED_KEYS,
            ROOT / HOST_BASELINE_V3_REFERENCE,
            ROOT / HOST_BASELINE_V3_EVIDENCE_REFERENCE,
        )
    }
    for name in (
        'work/devlite-v4/minimal.visual.fix.squashfs',
        'work/devlite-v4/minimal.visual.live.fix.squashfs',
    ):
        references[name] = sha(ROOT / name)

    grub_refs = {
        str(path.relative_to(ROOT)): sha(path)
        for path in sorted(GRUB_SOURCE.glob('*.cfg'))
    }
    if not {'work/phase4b1-dhzezpnz/original-grub/grub.cfg',
            'work/phase4b1-dhzezpnz/original-grub/loopback.cfg'} <= set(grub_refs):
        raise BuildError('Entradas GRUB originais incompletas')
    job = owned_directory(ROOT / 'work', 'modern-candidate-iso-')
    code = {name: sha(ROOT / name) for name in CODE}
    code[ENTRY] = sha(ROOT / ENTRY)

    for name in (
        'pipeline/devlite/modern_identity_v4.py',
        'pipeline/devlite/modern_catalog_v4.py',
        'pipeline/devlite/modern_layers_v4.py',
        'pipeline/devlite/modern_integration_v4.py',
        'pipeline/devlite/modern_validation_v4.py',
    ):
        code[name] = sha(ROOT / name)
    contract = {
        'schema': 4, 'operation': 'modern-candidate-iso-v4', 'job': str(job),
        'pack_job': str(pack), 'pack_approval': pack_approval,
        'pack_contract_sha256': sha(pack / 'contract.json'),
        'layers_receipt_sha256': sha(pack / 'layers-ready.json'),
        'layer_files': receipt['files'], 'source_iso_sha256': EXPECTED,
        'approved_iso_sha256': sha(BASELINE),
        'visual_layer': visual_layer_profile(visual_inputs),
        'required_assembly_bytes': required_bytes,
        'references_sha256': {**references, **grub_refs},
        'code_sha256': code, 'reserve_bytes': RESERVE,
        'release_approved': False, 'vm_tested': False,
    }
    save_new(job / 'contract.json', contract)
    approval = sha(job / 'contract.json')
    print(job)
    print(approval)


def read_iso_job(job, approval):
    job = Path(job)
    if job.is_symlink() or job.resolve().parent != (ROOT / 'work').resolve():
        raise BuildError('Job ISO fora do workspace')
    if not job.name.startswith('modern-candidate-iso-'):
        raise BuildError('Nome de job ISO inesperado')
    contract_path = job / 'contract.json'
    if sha(contract_path) != approval:
        raise BuildError('Contrato ISO alterado')
    contract = json.loads(contract_path.read_text())
    if (contract.get('schema') != 4
            or contract.get('operation') != 'modern-candidate-iso-v4'
            or contract.get('job') != str(job)):
        raise BuildError('Perfil ISO inválido')
    if contract.get('reserve_bytes') != RESERVE or contract.get('release_approved') is not False:
        raise BuildError('Escopo ISO inesperado')
    for name, digest in contract['code_sha256'].items():
        if sha(ROOT / name) != digest:
            raise BuildError('Código ISO mudou: ' + name)
    for name, digest in contract['references_sha256'].items():
        if sha(ROOT / name) != digest:
            raise BuildError('Referência de origem mudou: ' + name)
    pack, pack_contract, report, receipt = verified_pack(
        Path(contract['pack_job']), contract['pack_approval']
    )
    visual_inputs = preflight_visual_sources(
        pack / 'published-casper/minimal.squashfs',
        pack / 'published-casper/minimal.live.squashfs',
    )
    if contract.get('visual_layer') != visual_layer_profile(visual_inputs):
        raise BuildError('Perfil da camada visual diverge do contrato')
    if (sha(pack / 'contract.json') != contract['pack_contract_sha256']
            or sha(pack / 'layers-ready.json') != contract['layers_receipt_sha256']
            or receipt['files'] != contract['layer_files']):
        raise BuildError('Camadas seladas mudaram após a aprovação da ISO')
    if sha(SOURCE_ISO) != contract['source_iso_sha256'] or sha(BASELINE) != contract['approved_iso_sha256']:
        raise BuildError('ISO de origem ou ISO aprovada mudou')
    if contract.get('required_assembly_bytes') != required_assembly_bytes(
            SOURCE_ISO.stat().st_size, pack / 'published-casper'):
        raise BuildError('Orçamento selado da ISO diverge das entradas')
    return job, contract, pack, receipt


def execute(job, approval, authorized):
    if not authorized:
        raise BuildError('Use --execute-authorized')
    if os.getuid() != 1000 or os.geteuid() == 0:
        raise BuildError('Geração da ISO deve rodar como magaton, sem root')
    job, contract, pack, receipt = read_iso_job(job, approval)
    needed = contract['required_assembly_bytes']
    if shutil.disk_usage(job).free < needed:
        raise BuildError(f'Orçamento ISO insuficiente; requer {needed} bytes livres')
    if sha(BASELINE) != '7373cb9be11ebda5218f20795fec87eab20c2cebef3c763ae6e5c63d4e7cd7bd':
        raise BuildError('ISO aprovada alterada antes da construção')

    work = owned_directory(job, 'assembly-')
    (work / 'logs').mkdir()
    runner = Runner(work / 'logs', EPOCH)
    updates = work / 'updates'
    updates.mkdir()
    visual_layer = updates / INSTALL_LAYER
    visual_size = build_visual_layer(
        pack / 'published-casper/minimal.squashfs',
        visual_layer,
        work,
        runner.run,
        EPOCH,
    )
    base_size = int((pack / 'published-casper/minimal.size').read_text().strip())
    live_size = int((pack / 'published-casper/minimal.live.size').read_text().strip())
    filesystem_size = int(
        (pack / 'published-casper/filesystem.size').read_text().strip()
    )
    if filesystem_size != base_size + live_size:
        raise BuildError('Tamanho agregado das camadas aprovadas é inconsistente')

    mapped = {
        'casper/' + name: pack / 'published-casper' / name
        for name in sorted(REQUIRED)
        if name != 'minimal.live.squashfs'
    }
    mapped['casper/' + INSTALL_LAYER] = visual_layer
    mapped['casper/' + LIVE_LAYER] = pack / 'published-casper/minimal.live.squashfs'

    # Camadas incrementais DevLite OS v4.
    fixes = prepare_fix_layers(ROOT)
    mapped['casper/minimal.visual.fix.squashfs'] = fixes['install_layer']
    mapped['casper/minimal.visual.live.fix.squashfs'] = fixes['live_layer']

    catalog = updates / 'install-sources.yaml'
    catalog.write_text(
        render_install_catalog_v4(
            (pack / 'published-casper/install-sources.yaml').read_text(),
            base_size,
            visual_size,
            fixes['install_size'],
        ),
        encoding='utf-8',
    )
    mapped['casper/install-sources.yaml'] = catalog
    visual_size_file = updates / 'minimal.visual.size'
    visual_size_file.write_text(str(visual_size) + '\n', encoding='ascii')
    mapped['casper/minimal.visual.size'] = visual_size_file

    # Metadados das duas camadas incrementais v4.
    install_fix_size_file = updates / 'minimal.visual.fix.size'
    install_fix_size_file.write_text(
        str(fixes['install_size']) + '\n',
        encoding='ascii',
    )
    mapped['casper/minimal.visual.fix.size'] = install_fix_size_file

    live_fix_size_file = updates / 'minimal.visual.live.fix.size'
    live_fix_size_file.write_text(
        str(fixes['live_size']) + '\n',
        encoding='ascii',
    )
    mapped['casper/minimal.visual.live.fix.size'] = live_fix_size_file
    filesystem_size_file = updates / 'filesystem.size'
    filesystem_size_file.write_text(
        str(
            filesystem_size
            + visual_size
            + fixes['live_size']
        ) + '\n',
        encoding='ascii',
    )
    mapped['casper/filesystem.size'] = filesystem_size_file

    layer_metadata_v4 = build_layer_metadata(
        pack / 'published-casper/minimal.squashfs',
        visual_layer,
        pack / 'published-casper/minimal.live.squashfs',
        fixes,
    )

    checksums = updates / 'SHA256SUMS'
    checksums.write_text(
        layer_metadata_v4['checksums'],
        encoding='ascii',
    )
    mapped['casper/SHA256SUMS'] = checksums
    release = updates / 'devlite-release.json'
    save_new(release, {
        'profile': 'DevLite OS 1.0 Modern — Developer + Network Edition',
        'devcontrol': '1.0 GTK3; graphical execution pending Hyper-V validation',
        'vscode': 'official Microsoft launcher only; binary not bundled',
        'modern_wallpaper_and_xfce': 'static four-monitor default in a validated visual layer',
        'plymouth': {
            'rootfs_default_theme': 'DevLite OS 1.0',
            'rootfs_text_theme': 'DevLite OS 1.0',
            'live_initramfs': 'unchanged; upstream Xubuntu splash remains',
        },
        'wallpaper': {
            'path': DEVLITE_WALLPAPER,
            'xfce_config': XFCE_CONFIG,
            'layer': INSTALL_LAYER,
            'sha256': sha(visual_layer),
            'uncompressed_bytes': visual_size,
        },
        'installer': 'existing service preserved; Live desktop launcher added',
        'docker_openvpn': 'included from accepted package selection; runtime test pending',
        'boot_installation': 'not tested',
        'release_approved': False,
        'pack_contract_sha256': contract['pack_approval'],
        'iso_contract_sha256': approval,
    })
    mapped['casper/devlite-release.json'] = release
    components = updates / 'devlite-components.json'
    save_new(components, {
        'edition': 'Developer + Network',
        'devcontrol': {'version': '1.0', 'gtk': 3, 'read_only': True},
        'vscode': {'binary_in_iso': False, 'official_launcher': True},
        'packages': receipt['package_states']['base'],
    })
    mapped['casper/devlite-components.json'] = components

    for file in sorted(GRUB_SOURCE.glob('*.cfg')):
        original = file.read_text()
        if 'linux /casper/vmlinuz' not in original and '\tlinux\t/casper/vmlinuz' not in original:
            continue
        source_copy = work / ('source-' + file.name)
        runner.xorriso(
            'verify-original-' + file.stem,
            '-indev', SOURCE_ISO, '-osirrox', 'on',
            '-extract', '/boot/grub/' + file.name, source_copy,
        )
        if sha(source_copy) != sha(file):
            raise BuildError('GRUB de referência não corresponde à ISO oficial: ' + file.name)
        branded = brand_grub_v4(original)
        output = updates / file.name
        output.write_text(branded)
        mapped['boot/grub/' + file.name] = output
    if not {'boot/grub/grub.cfg', 'boot/grub/loopback.cfg'} <= set(mapped):
        raise BuildError('Entradas GRUB incompletas')

    provenance = {
        'casper/devlite-provenance/original-SHA256SUMS': CASPER_SOURCE / 'SHA256SUMS',
        'casper/devlite-provenance/original-SHA256SUMS.gpg': CASPER_SOURCE / 'SHA256SUMS.gpg',
    }
    md5 = updates / 'md5sum.txt'
    original_md5 = remove_md5_entries(
        MD5_SOURCE.read_text(), {'casper/minimal.live.squashfs'},
    )
    md5.write_text(make_md5(original_md5, mapped, provenance))
    mapped['md5sum.txt'] = md5
    output = owned_directory(ROOT / 'artifacts', 'modern-release-')
    candidate = output / 'devlite-os-1.0-amd64.iso.partial'
    boot = detect(runner, SOURCE_ISO, 'official-source')
    args = [
        '-indev', str(SOURCE_ISO), '-outdev', str(candidate), '-overwrite', 'on',
        '-mkdir', '/casper/devlite-provenance', '--',
        '-mv', '/casper/SHA256SUMS.gpg',
        '/casper/devlite-provenance/original-SHA256SUMS.gpg', '--',
        '-rm', '/casper/minimal.live.squashfs', '--',
    ]
    for name, file in {**mapped, **provenance}.items():
        args += [
            '-map', str(file), '/' + name, '-chown', '0', '/' + name, '--',
            '-chgrp', '0', '/' + name, '--', '-chmod', '0444', '/' + name, '--',
            '-alter_date', 'm', '=' + str(EPOCH), '/' + name, '--',
        ]
    args += [
        '-chown', '0', '/casper/devlite-provenance', '--',
        '-chgrp', '0', '/casper/devlite-provenance', '--',
        '-chmod', '0755', '/casper/devlite-provenance', '--',
        '-alter_date', 'm', '=' + str(EPOCH), '/casper/devlite-provenance', '--',
        '-assess_indev_features', 'replay', '-boot_image', 'any', 'replay',
        '-volid', 'DevLite OS 1.0 Candidate', '-volume_date', 'uuid',
        boot['timestamp'], '-end',
    ]
    runner.xorriso('assemble', *args)
    validation = audit_visual_iso(
        runner, SOURCE_ISO, candidate, work, mapped, provenance,
    )
    if sha(SOURCE_ISO) != EXPECTED or sha(BASELINE) != contract['approved_iso_sha256']:
        raise BuildError('ISO fonte ou ISO aprovada mudou durante a construção')
    if sha(pack / 'layers-ready.json') != contract['layers_receipt_sha256']:
        raise BuildError('Receipt de camadas mudou durante a construção')
    final = candidate.with_suffix('')
    candidate.rename(final)
    report = {
        'status': 'iso_structurally_verified', 'iso': str(final),
        'bytes': final.stat().st_size, 'sha256': sha(final),
        'contract_sha256': approval, 'pack_contract_sha256': contract['pack_approval'],
        'validation': validation, 'vm_tested': False, 'release_approved': False,
    }
    save_new(output / 'release-report.json', report)
    (output / 'SHA256SUMS').write_text(report['sha256'] + '  ' + final.name + '\n')
    return output / 'release-report.json'


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--pack-job', type=Path)
    parser.add_argument('--pack-approval-sha256')
    parser.add_argument('--job', type=Path)
    parser.add_argument('--approval-sha256')
    parser.add_argument('--execute-authorized', action='store_true')
    args = parser.parse_args()
    if args.prepare:
        prepare(args.pack_job, args.pack_approval_sha256)
    else:
        print(execute(args.job, args.approval_sha256, args.execute_authorized))
