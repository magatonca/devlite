"""Validação da estrutura de camadas DevLite OS v4."""

import re

from pipeline.devlite.modern_layers_v4 import (
    INSTALL_STACK,
    LIVE_STACK,
)


def validate_layout_v4(tree):
    casper = tree / "casper"

    expected = set(INSTALL_STACK) | set(LIVE_STACK)

    actual = {
        path.name
        for path in casper.glob("*.squashfs")
    }

    if actual != expected:
        raise ValueError(
            f"Camadas v4 incorretas: {sorted(actual)}"
        )

    catalog = (casper / "install-sources.yaml").read_text()

    if catalog.count(
        "  path: minimal.visual.fix.squashfs"
    ) != 1:
        raise ValueError("Catálogo não aponta para a camada v4")

    sizes = {}

    for name in (
        "minimal.size",
        "minimal.visual.size",
        "minimal.visual.fix.size",
        "minimal.live.size",
        "minimal.visual.live.fix.size",
        "filesystem.size",
    ):
        path = casper / name

        if not path.is_file():
            raise ValueError(f"Metadado ausente: {name}")

        sizes[name] = int(path.read_text().strip())

        if sizes[name] <= 0:
            raise ValueError(f"Tamanho inválido: {name}")

    install_total = (
        sizes["minimal.size"]
        + sizes["minimal.visual.size"]
        + sizes["minimal.visual.fix.size"]
    )

    live_total = (
        sizes["minimal.size"]
        + sizes["minimal.visual.size"]
        + sizes["minimal.live.size"]
        + sizes["minimal.visual.live.fix.size"]
    )

    match = re.search(
        r"(?m)^  size: ([0-9]+)$",
        catalog,
    )

    if not match or int(match.group(1)) != install_total:
        raise ValueError("Tamanho do catálogo incorreto")

    if sizes["filesystem.size"] != live_total:
        raise ValueError("Tamanho Live incorreto")

    # Verificar a seleção da cadeia Live no GRUB.
    for name in ("grub.cfg", "loopback.cfg"):
        grub = tree / "boot/grub" / name

        if not grub.is_file():
            raise ValueError(f"GRUB ausente: {name}")

        content = grub.read_text()

        linux_lines = [
            line
            for line in content.splitlines()
            if re.match(r"^\s*linux\s+/casper/vmlinuz(?:\s|$)", line)
        ]

        if not linux_lines:
            raise ValueError(f"Entradas Live ausentes: {name}")

        required = (
            "layerfs-path=minimal.visual.live.fix.squashfs",
            "username=devlite",
            "hostname=devlite",
        )

        for line in linux_lines:
            if any(parameter not in line for parameter in required):
                raise ValueError(
                    f"Parâmetros DevLite ausentes em {name}"
                )

    # Validar os parametros de inicializacao Live.
    for name in ("grub.cfg", "loopback.cfg"):
        grub = tree / "boot/grub" / name

        if not grub.is_file():
            raise ValueError(f"GRUB ausente: {name}")

        content = grub.read_text()

        linux_lines = [
            line
            for line in content.splitlines()
            if re.match(r"^\s*linux\s+/casper/vmlinuz(?:\s|$)", line)
        ]

        if not linux_lines:
            raise ValueError(f"Entradas Live ausentes: {name}")

        required = (
            "layerfs-path=minimal.visual.live.fix.squashfs",
            "username=devlite",
            "hostname=devlite",
        )

        for line in linux_lines:
            if any(parameter not in line for parameter in required):
                raise ValueError(
                    f"Parametros DevLite ausentes em {name}"
                )

    return sorted(actual)
