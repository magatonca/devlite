"""Pure branding transforms for the next DevLite Modern candidate."""
import re


TITLE_MAP = {
    'Try or Install Xubuntu': 'Try or Install DevLite OS 1.0',
    'Xubuntu (safe graphics)': 'DevLite OS 1.0 (safe graphics)',
}
MENUENTRY = re.compile(r"""^(\s*menuentry\s+)(["'])(.*?)\2(?=\s|\{)""", re.MULTILINE)
CASPER_KERNEL_LINE = re.compile(
    r'(?m)^([ \t]*linux[ \t]+/casper/vmlinuz(?:[ \t]|$))([^\r\n]*)(\r?\n?)$'
)
LAYERFS_ARGUMENT = 'layerfs-path=minimal.visual.live.squashfs'


def brand_grub_titles(text):
    """Rename only the two known GRUB titles; preserve all boot instructions."""
    titles = [match.group(3) for match in MENUENTRY.finditer(text)]
    for original, branded in TITLE_MAP.items():
        if titles.count(original) + titles.count(branded) != 1:
            raise ValueError('Entrada GRUB ausente, duplicada ou ambígua: ' + original)

    def replace(match):
        title = match.group(3)
        if title in TITLE_MAP:
            return match.group(1) + match.group(2) + TITLE_MAP[title] + match.group(2)
        return match.group(0)

    return MENUENTRY.sub(replace, text)


def set_grub_layer_path(text):
    """Point each live boot entry at the complete Modern layer stack."""
    matches = list(CASPER_KERNEL_LINE.finditer(text))
    if not matches:
        raise ValueError('Nenhuma entrada GRUB para o kernel Casper')

    def replace(match):
        prefix, arguments, newline = match.groups()
        existing = re.findall(r'(?<!\S)layerfs-path=([^\s]+)', arguments)
        if existing:
            if existing != ['minimal.visual.live.squashfs']:
                raise ValueError('Caminho de camada GRUB inesperado ou ambíguo')
            return match.group(0)
        terminator = re.search(r'[ \t]+---(?=[ \t]|$)', arguments)
        if terminator:
            arguments = (
                arguments[:terminator.start()] + ' ' + LAYERFS_ARGUMENT
                + arguments[terminator.start():]
            )
        else:
            arguments += ' ' + LAYERFS_ARGUMENT
        return prefix + arguments + newline

    return CASPER_KERNEL_LINE.sub(replace, text)


INSTALLER_SERVICE_DROPIN = (
    '[Unit]\n'
    'Description=Instalador do DevLite OS 1.0\n'
)

INSTALLER_DESKTOP_ENTRY = (
    '[Desktop Entry]\n'
    'Type=Application\n'
    'Name=Instalar DevLite OS 1.0\n'
    'Name[pt_BR]=Instalar DevLite OS 1.0\n'
    'Comment=Iniciar o instalador do sistema DevLite\n'
    'Exec=/usr/bin/systemctl --user start xubuntu-installer.service\n'
    'TryExec=/usr/bin/systemctl\n'
    'Icon=devlite\n'
    'Terminal=false\n'
    'Categories=System;X-DevLite;\n'
    'StartupNotify=false\n'
)

