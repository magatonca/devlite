#!/usr/bin/env python3
"""Valida e lê a ISO; salva relatórios e cópias de inspeção fora do Git.
Não monta imagens, não executa arquivos extraídos, não modifica a ISO.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ISO = ROOT / "sources/xubuntu-24.04.5-minimal-amd64.iso"
REPORTS = ROOT / "reports/phase2"
WORK = ROOT / "work/phase2"


def record(name, command):
    result = subprocess.run(command, capture_output=True, text=True)
    (REPORTS / name).write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError(f"Falha: {command[0]}; consultar {name}")


def main():
    subprocess.run([sys.executable, str(ROOT / "scripts/validar-iso.py")], check=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    if (WORK / "casper").exists():
        raise RuntimeError("Destino casper já existe; revisar manualmente, sem sobrescrever")
    record("boot.txt", ["xorriso", "-indev", str(ISO),
                          "-report_el_torito", "plain", "-report_system_area", "plain"])
    record("boot-replay.txt", ["xorriso", "-indev", str(ISO), "-report_el_torito", "as_mkisofs"])
    record("iso-tree.txt", ["xorriso", "-indev", str(ISO), "-find", "/", "-exec", "lsdl", "--"])
    for source, destination in (("/casper", "casper"), ("/boot/grub", "grub"), ("/.disk", "disk")):
        record("extract-" + destination + ".txt", ["xorriso", "-osirrox", "on", "-indev", str(ISO),
               "-extract", source, str(WORK / destination)])
    record("initrd-files.txt", ["lsinitramfs", str(WORK / "casper/initrd")])
    if (WORK / "initrd").exists():
        raise RuntimeError("Destino initrd já existe; revisar manualmente")
    record("initrd-extract.txt", ["unmkinitramfs", str(WORK / "casper/initrd"), str(WORK / "initrd")])
    for squash in sorted((WORK / "casper").glob("*.squashfs")):
        record(squash.name + "-stat.txt", ["unsquashfs", "-s", str(squash)])
        record(squash.name + "-files.txt", ["unsquashfs", "-ll", str(squash)])
    subprocess.run([sys.executable, str(ROOT / "scripts/validar-iso.py")], check=True)
    print("Inspeção concluída; ver reports/phase2 e work/phase2.")


if __name__ == "__main__":
    main()
