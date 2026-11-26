"""Validação e metadados das camadas DevLite OS v4."""

import hashlib
from pathlib import Path

from pipeline.devlite.modern_visual import layer_stack

INSTALL_FIX = "minimal.visual.fix.squashfs"
LIVE_FIX = "minimal.visual.live.fix.squashfs"

INSTALL_STACK = (
    "minimal.squashfs",
    "minimal.visual.squashfs",
    INSTALL_FIX,
)

LIVE_STACK = (
    "minimal.squashfs",
    "minimal.visual.squashfs",
    "minimal.visual.live.squashfs",
    LIVE_FIX,
)


def validate_stacks():
    if layer_stack(INSTALL_FIX) != INSTALL_STACK:
        raise ValueError("Cadeia de instalação v4 inválida")

    if layer_stack(LIVE_FIX) != LIVE_STACK:
        raise ValueError("Cadeia Live v4 inválida")

    return True


def sha256_file(path):
    digest = hashlib.sha256()

    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def layer_hashes(paths):
    expected = set(LIVE_STACK)

    if set(paths) != expected:
        raise ValueError("Conjunto de camadas v4 incompleto")

    hashes = {}

    for name in LIVE_STACK:
        path = Path(paths[name])

        if not path.is_file() or path.is_symlink():
            raise ValueError(f"Camada ausente ou inválida: {name}")

        hashes[name] = sha256_file(path)

    return hashes


def render_checksums(hashes):
    if set(hashes) != set(LIVE_STACK):
        raise ValueError("Hashes das camadas incompletos")

    return "".join(
        f"{hashes[name]} *{name}\n"
        for name in sorted(hashes)
    )


def uncompressed_size(path):
    """Soma os tamanhos dos arquivos regulares do SquashFS."""

    import subprocess

    result = subprocess.run(
        ["unsquashfs", "-ll", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )

    total = 0

    for line in result.stdout.splitlines():
        parts = line.split(maxsplit=5)

        if len(parts) < 6:
            continue

        permissions = parts[0]

        if permissions.startswith("-"):
            total += int(parts[2])

    return total
