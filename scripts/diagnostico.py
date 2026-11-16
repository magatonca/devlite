#!/usr/bin/env python3
"""Diagnóstico somente de leitura, sem rede ou privilégios."""
import json
import platform
import shutil
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    disk = shutil.disk_usage(root)
    memory = {}
    for line in Path('/proc/meminfo').read_text().splitlines():
        key, value = line.split(':', 1)
        if key in {'MemTotal', 'MemAvailable', 'SwapTotal', 'SwapFree'}:
            memory[key] = int(value.split()[0]) * 1024
    tools = {name: shutil.which(name) for name in
             ('python3', 'git', 'xorriso', 'mksquashfs', 'unsquashfs', 'gpg')}
    warnings = []
    if disk.free < 60 * 1024**3:
        warnings.append('Menos de 60 GiB livres: reavaliar antes do build.')
    if memory['MemTotal'] < 8 * 1024**3:
        warnings.append('Menos de 8 GiB RAM: limitar compressão e executar sequencialmente.')
    if platform.machine() not in ('x86_64', 'amd64'):
        warnings.append('Host difere da arquitetura AMD64 planejada.')
    if any(value is None for value in tools.values()):
        warnings.append('Há ferramentas ausentes; não instalar automaticamente.')
    print(json.dumps({'arquitetura': platform.machine(), 'python': platform.python_version(),
                      'disco_bytes': {'total': disk.total, 'livre': disk.free},
                      'memoria_bytes': memory, 'ferramentas': tools, 'avisos': warnings,
                      'escopo': 'Planejamento; não certifica ou autoriza build.'},
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
