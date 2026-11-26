"""Orquestração da reconstrução experimental; sem customização interna."""
import json
import os
import pwd
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from .runtime import BuildError, Runner, owned_directory
from .structure import digest, parse_boot, pvd_metadata, region_digest, compare_boot_metadata
from .validation import compare_trees, inventory, verify_manifest, iso_metadata

NAME = 'xubuntu-24.04.5-minimal-amd64.iso'
EXPECTED = '9d47f975696ce496b8be882b6d7cc9079c1ea89fb625ac2c86caa63a4f180033'


def preflight(root):
    if pwd.getpwuid(os.getuid()).pw_name != 'magaton':
        raise BuildError('Executar como magaton, sem sudo')
    for name in ('xorriso', 'gpgv', 'unsquashfs'):
        if not shutil.which(name):
            raise BuildError(f'Ferramenta ausente: {name}; não instalar automaticamente')
    source = root / 'sources' / NAME
    if source.is_symlink() or not source.is_file():
        raise BuildError('A entrada deve ser a ISO regular autenticada em sources')
    for name in ('sources', 'work', 'artifacts'):
        directory = root / name
        if directory.is_symlink() or not directory.is_dir():
            raise BuildError(f'Diretório inválido: {directory}')
    # Duas árvores de auditoria, saída, e margem de 10 GiB para o host.
    required = 4 * source.stat().st_size + 10 * 1024**3
    if shutil.disk_usage(root).free < required:
        raise BuildError(f'Espaço insuficiente: requer {required} bytes livres')
    return source


def rebuild_args(source, candidate, timestamp):
    if source.resolve() == candidate.resolve() or candidate.exists() or candidate.is_symlink():
        raise BuildError('Saída existente ou igual à entrada')
    return ['-indev', str(source), '-outdev', str(candidate),
            '-assess_indev_features', 'replay', '-boot_image', 'any', 'replay',
            '-volume_date', 'uuid', timestamp, '-changes_pending', 'yes', '-end']


def detect(runner, image, label):
    report = runner.xorriso(label + '-boot', '-indev', image,
                           '-report_el_torito', 'plain', '-report_system_area', 'plain')
    structure = parse_boot(report)
    structure.update(pvd_metadata(image))
    runner.xorriso(label + '-boot-recipe', '-indev', image, '-report_el_torito', 'as_mkisofs')
    return structure


def extract(runner, image, tree, label):
    if tree.exists():
        raise BuildError('Destino de extração já existe')
    runner.xorriso(label + '-extract', '-osirrox', 'on', '-indev', image, '-extract', '/', tree)


def validate_layout(tree):
    layers = sorted(p.name for p in (tree / 'casper').glob('*.squashfs'))
    if layers != ['minimal.live.squashfs', 'minimal.squashfs']:
        raise BuildError(f'Camadas não suportadas: {layers}')
    catalog = (tree / 'casper/install-sources.yaml').read_text()
    if 'path: minimal.squashfs' not in catalog or 'type: fsimage-layered' not in catalog:
        raise BuildError('Catálogo de instalação inesperado')
    for name in ('casper/initrd', 'casper/vmlinuz', 'casper/filesystem.manifest',
                 'casper/minimal.manifest', 'casper/minimal.live.manifest',
                 'EFI/boot/bootx64.efi', 'EFI/boot/grubx64.efi', 'boot/grub/grub.cfg'):
        if not (tree / name).is_file():
            raise BuildError(f'Componente essencial ausente: {name}')
    manifest = (tree / 'casper/filesystem.manifest').read_text()
    if 'snap:ubuntu-desktop-bootstrap' not in manifest:
        raise BuildError('Instalador Desktop Bootstrap não identificado')
    return layers


def build(root):
    source = preflight(root)
    meta = pvd_metadata(source)
    epoch = int(datetime.strptime(meta['timestamp'][:14], '%Y%m%d%H%M%S').replace(tzinfo=timezone.utc).timestamp())
    workspace = owned_directory(root / 'work', 'phase3b-')
    logs = workspace / 'logs'
    logs.mkdir()
    runner = Runner(logs, epoch)
    report = {'status': 'em_andamento', 'workspace': str(workspace), 'fonte': str(source),
              'usuario': 'magaton', 'source_date_epoch': epoch,
              'boot_vm': 'adiado pelo usuário; não testado', 'instalacao': 'não testada',
              'limpeza': 'nenhuma exclusão; preservar arquivos em sucesso, erro ou interrupção'}
    report_path = workspace / 'report.json'
    def save():
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    save()
    try:
        report['ferramentas'] = {name: runner.run(name + '-version', [name, *args], allowed=(0, 1) if name == 'unsquashfs' else (0,)) for name, args in
                                 (('xorriso', ['-no_rc', '-version']), ('unsquashfs', ['-version']),
                                  ('python3', ['--version']))}
        if 'unsquashfs version' not in report['ferramentas']['unsquashfs']:
            raise BuildError('Não foi possível identificar a versão do unsquashfs')
        runner.run('authenticate-source', [sys.executable, str(root / 'scripts/validar-iso.py')])
        original = detect(runner, source, 'source')
        source_tree = workspace / 'source-tree'
        extract(runner, source, source_tree, 'source')
        layers = validate_layout(source_tree)
        report['estrutura_original'] = original
        report['camadas'] = layers
        for layer in layers:
            runner.run(layer + '-superblock', ['unsquashfs', '-s', str(source_tree / 'casper' / layer)])
        source_metadata = iso_metadata(runner.xorriso('source-metadata', '-indev', source, '-find', '/', '-exec', 'lsdl', '--'))
        before = inventory(source_tree)
        (workspace / 'source-inventory.json').write_text(json.dumps(before, indent=2))
        output_dir = owned_directory(root / 'artifacts', 'phase3b-')
        candidate = output_dir / 'devlite-os-1.0-experimental-rebuild.iso.partial'
        report['saida_em_preparacao'] = str(candidate)
        save()
        runner.xorriso('rebuild', *rebuild_args(source, candidate, meta['timestamp']))
        result = detect(runner, candidate, 'result')
        compare_boot_metadata(source, candidate, original, result)
        report['codigo_mbr_e_carga_eltorito_verificados'] = True
        if result['volume_id'] != original['volume_id'] or result['timestamp'] != original['timestamp']:
            raise BuildError('Identidade ou timestamp de volume mudou')
        if result['efi_bytes'] != original['efi_bytes']:
            raise BuildError('Tamanho EFI mudou')
        source_efi = region_digest(source, original['efi_offset'], original['efi_bytes'])
        result_efi = region_digest(candidate, result['efi_offset'], result['efi_bytes'])
        if source_efi != result_efi:
            raise BuildError('Conteúdo da EFI anexada mudou')
        result_tree = workspace / 'result-tree'
        extract(runner, candidate, result_tree, 'result')
        validate_layout(result_tree)
        result_metadata = iso_metadata(runner.xorriso('result-metadata', '-indev', candidate, '-find', '/', '-exec', 'lsdl', '--'))
        for name in set(source_metadata) | set(result_metadata):
            if name != '/boot.catalog' and source_metadata.get(name) != result_metadata.get(name):
                raise BuildError(f'Metadados ISO alterados: {name}')
        report['metadados_iso_comparados'] = len(source_metadata)
        after = inventory(result_tree)
        (workspace / 'result-inventory.json').write_text(json.dumps(after, indent=2))
        report['arquivos_boot_relocalizados'] = compare_trees(before, after, source_tree, result_tree, original['bios_path'])
        report['md5_entradas_verificadas'] = verify_manifest(result_tree, Path('md5sum.txt'), 'md5')
        report['sha256_camadas_verificadas'] = verify_manifest(result_tree, Path('casper/SHA256SUMS'), 'sha256')
        runner.run('verify-casper-signature', ['gpgv', '--homedir', str(root / 'sources/verification'),
                   '--keyring', str(root / 'sources/verification/trustedkeys.gpg'),
                   str(result_tree / 'casper/SHA256SUMS.gpg'), str(result_tree / 'casper/SHA256SUMS')])
        report['iso_sha256'] = digest(candidate)
        if digest(source) != EXPECTED:
            raise BuildError('ISO original mudou durante o processamento; não promover saída')
        final = output_dir / 'devlite-os-1.0-experimental-rebuild.iso'
        if final.exists() or final.is_symlink():
            raise BuildError('Destino final já existe')
        candidate.rename(final)
        (output_dir / 'SHA256SUMS').write_text(f"{report['iso_sha256']}  {final.name}\n")
        report.update(status='validado_estruturalmente', saida=str(final), bytes=final.stat().st_size,
                      estrutura_resultante=result, efi_sha256=source_efi,
                      conteudo_interno='inalterado; exceções apenas catálogo e endereços BIOS verificados',
                      original_sha256=EXPECTED, reproducibilidade_binaria='não medida por segunda execução')
        save()
        (output_dir / 'build-report.json').write_text(report_path.read_text())
        print(f'ISO experimental: {final}\nRelatório: {report_path}', flush=True)
        return report
    except BaseException as error:
        report.update(status='interrompido' if isinstance(error, KeyboardInterrupt) else 'falhou', erro=str(error))
        save()
        print(f'Processo interrompido; arquivos preservados em {workspace}', file=sys.stderr, flush=True)
        raise


def reproduce(root, report_path):
    """Segunda geração da mesma receita; comparar bytes sem reextrair rootfs."""
    source = preflight(root)
    if report_path.is_symlink() or not report_path.resolve().is_relative_to((root / 'artifacts').resolve()):
        raise BuildError('Relatório deve estar em artifacts, sem symlink')
    first = json.loads(report_path.read_text())
    reference = Path(first.get('saida', ''))
    if (first.get('status') != 'validado_estruturalmente' or first.get('original_sha256') != EXPECTED
            or reference.is_symlink() or not reference.is_file()
            or reference.resolve().parent != report_path.resolve().parent):
        raise BuildError('Relatório ou artefato de referência inválido')
    proof_path = reference.parent / 'reproducibility.json'
    if proof_path.exists() or proof_path.is_symlink():
        raise BuildError('Prova já existe; não sobrescrever')
    workspace = owned_directory(root / 'work', 'phase3b-reproduction-')
    logs = workspace / 'logs'
    logs.mkdir()
    runner = Runner(logs, first['source_date_epoch'])
    proof = {'status': 'em_andamento', 'referencia': str(reference), 'workspace': str(workspace)}
    proof_file = workspace / 'reproducibility.json'
    try:
        runner.run('authenticate-source', [sys.executable, str(root / 'scripts/validar-iso.py')])
        print('Comparando hash do primeiro artefato...', flush=True)
        reference_hash = digest(reference)
        if reference_hash != first['iso_sha256']:
            raise BuildError('Artefato de referência foi alterado')
        candidate = workspace / 'reproduced.iso'
        runner.xorriso('reproduce', *rebuild_args(source, candidate, pvd_metadata(source)['timestamp']))
        print('Comparando hash da reprodução...', flush=True)
        second_hash = digest(candidate)
        if second_hash != reference_hash:
            raise BuildError('Reprodução binária divergiu; preservar as duas imagens para investigação')
        if digest(source) != EXPECTED:
            raise BuildError('Fonte mudou durante a reprodução')
        proof.update(status='identidade_binaria_confirmada', sha256=second_hash,
                     segunda_imagem=str(candidate), bytes=candidate.stat().st_size)
        proof_file.write_text(json.dumps(proof, indent=2) + '\n')
        with proof_path.open('x') as stream:
            json.dump(proof, stream, indent=2)
        print(f'Reprodução binária confirmada: {proof_path}', flush=True)
        return proof
    except BaseException as error:
        proof.update(status='falhou', erro=str(error))
        proof_file.write_text(json.dumps(proof, indent=2) + '\n')
        raise
