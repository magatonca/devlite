"""Integração das camadas incrementais DevLite OS v4."""

from pathlib import Path

from pipeline.devlite.modern_layers_v4 import (
    INSTALL_FIX,
    LIVE_FIX,
    LIVE_STACK,
    layer_hashes,
    render_checksums,
    uncompressed_size,
    validate_stacks,
)


def prepare_fix_layers(project_root):
    """Verifica as camadas v4 sem modificar os arquivos."""

    validate_stacks()

    directory = Path(project_root) / "work/devlite-v4"

    install = directory / INSTALL_FIX
    live = directory / LIVE_FIX

    for path in (install, live):
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"Camada v4 inválida: {path}")

    install_size = uncompressed_size(install)
    live_size = uncompressed_size(live)

    if install_size <= 0 or live_size <= 0:
        raise ValueError("Camadas v4 vazias")

    return {
        "install_layer": install,
        "live_layer": live,
        "install_size": install_size,
        "live_size": live_size,
    }


def build_layer_metadata(base, visual, approved_live, fixes):
    """Calcula hashes das quatro camadas da ISO."""

    paths = {
        "minimal.squashfs": Path(base),
        "minimal.visual.squashfs": Path(visual),
        "minimal.visual.live.squashfs": Path(approved_live),
        INSTALL_FIX: fixes["install_layer"],
        LIVE_FIX: fixes["live_layer"],
    }

    # A cadeia Live inclui também a camada de instalação v4.
    expected = set(LIVE_STACK) | {INSTALL_FIX}

    if set(paths) != expected:
        raise ValueError("Composição v4 incompleta")

    # A função original valida apenas a cadeia Live.
    hashes = layer_hashes({
        name: paths[name]
        for name in LIVE_STACK
    })

    from pipeline.devlite.modern_layers_v4 import sha256_file

    hashes[INSTALL_FIX] = sha256_file(paths[INSTALL_FIX])

    checksums = "".join(
        f"{hashes[name]} *{name}\n"
        for name in sorted(hashes)
    )

    return {
        "paths": paths,
        "hashes": hashes,
        "checksums": checksums,
    }
