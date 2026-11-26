"""Catálogo de instalação do DevLite OS v4."""

import re

from pipeline.devlite.modern_visual import render_install_catalog

INSTALL_LAYER_V4 = "minimal.visual.fix.squashfs"


def render_install_catalog_v4(document, base_size, visual_size, fix_size):
    """Gera catálogo v4 a partir do catálogo original aprovado."""

    for name, value in (
        ("base_size", base_size),
        ("visual_size", visual_size),
        ("fix_size", fix_size),
    ):
        if type(value) is not int or value < 0:
            raise ValueError(f"Tamanho inválido: {name}")

    rendered = render_install_catalog(
        document, base_size, visual_size
    )

    rendered, count = re.subn(
        r"(?m)^  path: minimal\.visual\.squashfs$",
        f"  path: {INSTALL_LAYER_V4}",
        rendered,
    )

    if count != 1:
        raise ValueError("Camada de instalação v3 ausente ou ambígua")

    rendered, count = re.subn(
        r"(?m)^  size: " + str(base_size + visual_size) + r"$",
        "  size: " + str(base_size + visual_size + fix_size),
        rendered,
    )

    if count != 1:
        raise ValueError("Tamanho de instalação v3 ausente ou ambíguo")

    return rendered
