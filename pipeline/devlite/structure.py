"""Detecção do layout observado e validação de regiões de boot."""
import hashlib
import re
from .runtime import BuildError


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def region_digest(path, offset, length):
    if offset < 0 or length <= 0 or offset + length > path.stat().st_size:
        raise BuildError('Região de boot fora da imagem')
    h = hashlib.sha256()
    with path.open('rb') as stream:
        stream.seek(offset)
        remaining = length
        while remaining:
            block = stream.read(min(1024 * 1024, remaining))
            if not block:
                raise BuildError('Leitura incompleta da imagem EFI')
            h.update(block)
            remaining -= len(block)
    return h.hexdigest()


def parse_boot(report):
    images = []
    for match in re.finditer(r'^El Torito boot img :\s+(\d+)\s+(BIOS|UEFI)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\d+)\s+(\d+)\s*$', report, re.M):
        n, platform, bootable, emulation, segment, hdpt, load, lba = match.groups()
        images.append({'id': int(n), 'platform': platform, 'bootable': bootable,
                       'emulation': emulation, 'load_sectors': int(load), 'lba_2048': int(lba)})
    if [item['platform'] for item in images] != ['BIOS', 'UEFI'] or any(item['bootable'] != 'y' or item['emulation'] != 'none' for item in images):
        raise BuildError('Layout El Torito não suportado: requer BIOS e UEFI sem emulação')
    paths = {int(n): name.strip() for n, name in re.findall(r'^El Torito img path :\s+(\d+)\s+(.+)$', report, re.M)}
    if paths.get(1) != '/boot/grub/i386-pc/eltorito.img':
        raise BuildError('Caminho BIOS inesperado')
    summary = re.search(r'^System area summary:\s+(.+)$', report, re.M)
    if not summary or any(token not in summary[1] for token in ('grub2-mbr', 'GPT', 'protective-msdos-label')):
        raise BuildError('Boot híbrido MBR/GPT ausente')
    partitions = {int(n): (int(start), int(size)) for n, start, size in re.findall(r'^GPT start and size :\s+(\d+)\s+(\d+)\s+(\d+)', report, re.M)}
    types = {int(n): value for n, value in re.findall(r'^GPT type GUID\s*:\s+(\d+)\s+([0-9a-f]+)', report, re.M)}
    if 2 not in partitions or types.get(2) != '28732ac11ff8d211ba4b00a0c93ec93b':
        raise BuildError('Partição EFI anexada não identificada')
    start, size = partitions[2]
    if start * 512 != images[1]['lba_2048'] * 2048 or size != images[1]['load_sectors']:
        raise BuildError('GPT e El Torito discordam sobre EFI')
    return {'images': images, 'bios_path': paths[1], 'efi_offset': start * 512,
            'efi_bytes': size * 512, 'summary': summary[1]}


def pvd_metadata(iso):
    with iso.open('rb') as stream:
        stream.seek(16 * 2048)
        pvd = stream.read(2048)
    if pvd[:7] != b'\x01CD001\x01':
        raise BuildError('Descritor primário ISO9660 não encontrado')
    timestamp = pvd[830:846].decode('ascii')
    if not re.fullmatch(r'[0-9]{16}', timestamp):
        raise BuildError('Timestamp ISO inválido')
    return {'volume_id': pvd[40:72].decode('ascii').strip(), 'timestamp': timestamp}


def compare_boot_metadata(source, result, before, after):
    for left, right in zip(before['images'], after['images']):
        if any(left[key] != right[key] for key in ('platform', 'bootable', 'emulation', 'load_sectors')):
            raise BuildError('Parâmetros de carga El Torito mudaram')
    with source.open('rb') as stream:
        original_mbr = stream.read(512)
    with result.open('rb') as stream:
        rebuilt_mbr = stream.read(512)
    if len(original_mbr) != 512 or len(rebuilt_mbr) != 512:
        raise BuildError('MBR incompleto')
    if original_mbr[:432] != rebuilt_mbr[:432]:
        raise BuildError('Código MBR mudou')
    if original_mbr[510:512] != rebuilt_mbr[510:512] or rebuilt_mbr[510:512] != b'\x55\xaa':
        raise BuildError('Assinatura MBR inválida')
