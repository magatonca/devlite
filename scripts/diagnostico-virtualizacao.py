#!/usr/bin/env python3
"""Diagnóstico somente de leitura; não abre /dev/kvm nem inicia hipervisor."""
import json
import os
import platform
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_text(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


def cpu_extensions(cpuinfo):
    sets = []
    for line in cpuinfo.splitlines():
        key, separator, value = line.partition(':')
        if separator and key.strip() in ('flags', 'Features'):
            sets.append(set(value.split()))
    return sorted(set.intersection(*sets) & {'vmx', 'svm'}) if sets else []


def assess(extensions, kvm_exists, kvm_access, qemu, ram_bytes):
    blockers = []
    if not extensions:
        blockers.append('CPU não expõe vmx/svm; virtualização assistida não disponível ao guest.')
    if not kvm_exists:
        blockers.append('/dev/kvm ausente.')
    elif not kvm_access:
        blockers.append('Usuário sem acesso de leitura/escrita a /dev/kvm.')
    if not qemu:
        blockers.append('qemu-system-x86_64 ausente.')
    if ram_bytes < 8 * 1024**3:
        blockers.append('RAM total menor que 8 GiB; não há margem para uma VM de teste de 4 GiB.')
    return {
        'kvm_precondicoes_observadas': bool(extensions and kvm_exists and kvm_access),
        'bloqueios_qemu_local': blockers,
        'recomendacao': 'VMware Workstation no Windows; confirmar recursos físicos antes de criar VMs.',
        'limite': 'Sinais de leitura não comprovam KVM funcional; nenhum ioctl, carga de módulo ou VM foi executado.'
    }


def collect():
    cpuinfo = read_text('/proc/cpuinfo') or ''
    extensions = cpu_extensions(cpuinfo)
    memory = {}
    for line in (read_text('/proc/meminfo') or '').splitlines():
        key, _, value = line.partition(':')
        if key in ('MemTotal', 'MemAvailable', 'SwapTotal'):
            memory[key] = int(value.split()[0]) * 1024
    tools = {name: shutil.which(name) for name in
             ('qemu-system-x86_64', 'qemu-img', 'virsh', 'virt-host-validate')}
    kvm = Path('/dev/kvm')
    exists = kvm.exists()
    access = exists and os.access(kvm, os.R_OK | os.W_OK)
    nested = {str(p): read_text(p) for p in
              (Path('/sys/module/kvm_intel/parameters/nested'),
               Path('/sys/module/kvm_amd/parameters/nested'))}
    firmware = sorted(str(p) for base in ('/usr/share/OVMF', '/usr/share/edk2/ovmf')
                      for p in Path(base).glob('*.fd'))
    return {
        'usuario': os.getuid(), 'arquitetura': platform.machine(),
        'extensoes_virtualizacao': extensions,
        'cpus_online': read_text('/sys/devices/system/cpu/online'),
        'dmi_vendor': read_text('/sys/class/dmi/id/sys_vendor'),
        'dmi_product': read_text('/sys/class/dmi/id/product_name'),
        'kvm_dispositivo_existe': exists, 'kvm_acesso_usuario': access,
        'nested_modulos_carregados': nested, 'ferramentas': tools,
        'firmware_ovmf': firmware, 'memoria_bytes': memory,
        'disco_livre_bytes': shutil.disk_usage(ROOT).free,
        'avaliacao': assess(extensions, exists, access, tools['qemu-system-x86_64'], memory.get('MemTotal', 0))
    }


if __name__ == '__main__':
    print(json.dumps(collect(), ensure_ascii=False, indent=2))
