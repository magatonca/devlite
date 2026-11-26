"""Identidade de inicialização do DevLite OS v4."""

import re

from pipeline.devlite.modern_identity import brand_grub_titles

LIVE_LAYER_V4 = "minimal.visual.live.fix.squashfs"

BOOT_ARGUMENTS = (
    "layerfs-path=" + LIVE_LAYER_V4,
    "username=devlite",
    "hostname=devlite",
)


def brand_grub_v4(document):
    """Personaliza as entradas de inicialização Live."""

    document = brand_grub_titles(document)
    output = []

    for line in document.splitlines(keepends=True):
        if not re.match(r"^\s*linux\s+/casper/vmlinuz(?:\s|$)", line):
            output.append(line)
            continue

        for argument in BOOT_ARGUMENTS:
            key = argument.split("=", 1)[0]

            line = re.sub(
                r"(?<!\S)" + re.escape(key) + r"=\S+",
                "",
                line,
            )

        marker = re.search(r"(?<!\S)---(?=\s|$)", line)

        if marker:
            position = marker.start()
            line = (
                line[:position].rstrip()
                + " "
                + " ".join(BOOT_ARGUMENTS)
                + " "
                + line[position:]
            )
        else:
            newline = "\n" if line.endswith("\n") else ""
            line = (
                line.rstrip()
                + " "
                + " ".join(BOOT_ARGUMENTS)
                + newline
            )

        output.append(line)

    return "".join(output)
