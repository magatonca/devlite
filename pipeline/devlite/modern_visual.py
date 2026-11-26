"""Layered visual defaults for the Modern ISO candidate."""
import hashlib
import os
import re
import stat
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath

from .minimal_root import allocated_usage
from .runtime import BuildError


XFCE_CONFIG = (
    'etc/xdg/xdg-xubuntu/xfce4/xfconf/xfce-perchannel-xml/'
    'xfce4-desktop.xml'
)
OS_RELEASE = 'etc/os-release'
WALLPAPER_FILE = 'usr/share/backgrounds/devlite/devlite-modern.svg'
DEVLITE_ICON = 'usr/share/icons/hicolor/scalable/apps/devlite.svg'
XUBUNTU_WALLPAPER = '/usr/share/xfce4/backdrops/xubuntu-wallpaper.png'
DEVLITE_WALLPAPER = '/usr/share/backgrounds/devlite/devlite-modern.svg'
PLYMOUTH_ALIASES = {
    'etc/alternatives/default.plymouth':
        '/usr/share/plymouth/themes/devlite/devlite.plymouth',
    'etc/alternatives/text.plymouth':
        '/usr/share/plymouth/themes/devlite/devlite-text.plymouth',
}
XUBUNTU_PLYMOUTH_ALIASES = {
    'etc/alternatives/default.plymouth':
        '/usr/share/plymouth/themes/xubuntu-logo/xubuntu-logo.plymouth',
    'etc/alternatives/text.plymouth':
        '/usr/share/plymouth/themes/xubuntu-text/xubuntu-text.plymouth',
}
PLYMOUTH_THEME_FILES = {
    'usr/share/plymouth/themes/devlite/devlite.plymouth': (
        '[Plymouth Theme]\n'
        'Name=DevLite OS 1.0\n'
        'Description=DevLite OS 1.0 graphical boot theme\n'
        'ModuleName=script\n'
        '\n'
        '[script]\n'
        'ImageDir=/usr/share/plymouth/themes/devlite\n'
        'ScriptFile=/usr/share/plymouth/themes/devlite/devlite.script\n'
    ),
    'usr/share/plymouth/themes/devlite/devlite.script': (
        'Window.SetBackgroundTopColor(0.06, 0.10, 0.16);\n'
        'Window.SetBackgroundBottomColor(0.02, 0.04, 0.08);\n'
        'title_image = Image.Text("DevLite OS 1.0", 0.92, 0.95, 1.0);\n'
        'title_sprite = Sprite(title_image);\n'
        'title_sprite.SetPosition(\n'
        '    Window.GetX() + (Window.GetWidth() - title_image.GetWidth()) / 2,\n'
        '    Window.GetY() + (Window.GetHeight() - title_image.GetHeight()) / 2,\n'
        '    100\n'
        ');\n'
    ),
    'usr/share/plymouth/themes/devlite/devlite-text.plymouth': (
        '[Plymouth Theme]\n'
        'Name=DevLite OS 1.0 Text\n'
        'Description=DevLite OS 1.0 text boot theme\n'
        'ModuleName=ubuntu-text\n'
        '\n'
        '[ubuntu-text]\n'
        'title=DevLite OS 1.0\n'
        'black=0x000000\n'
        'white=0xffffff\n'
        'brown=0x000000\n'
        'blue=0xffffff\n'
    ),
}
INSTALL_LAYER = 'minimal.visual.squashfs'
LIVE_LAYER = 'minimal.visual.live.squashfs'
LAYER_MAX_BYTES = 1024 * 1024
BLOCK_SIZE = 131072

PROPERTY_TAG = re.compile(r'<property\b[^>]*?/>')
VALUE_ATTRIBUTE = re.compile(r'(\bvalue\s*=\s*)(["\'])(.*?)\2')


def _xfce_image_paths(document):
    root = ET.fromstring(document)
    if root.tag != 'channel' or root.get('name') != 'xfce4-desktop':
        raise ValueError('Canal XFCE de desktop inválido')
    backdrop = root.find("./property[@name='backdrop']/property[@name='screen0']")
    if backdrop is None:
        raise ValueError('Configuração backdrop/screen0 ausente')
    monitors = {
        prop.get('name'): prop
        for prop in backdrop.findall('property')
        if prop.get('name', '').startswith('monitor')
    }
    if set(monitors) != {f'monitor{index}' for index in range(4)}:
        raise ValueError('Configuração XFCE não contém os quatro monitores esperados')
    image_paths = []
    for monitor_name in sorted(monitors):
        properties = [
            prop for prop in monitors[monitor_name].findall('property')
            if prop.get('name') == 'image-path'
        ]
        if len(properties) != 1 or properties[0].get('type') != 'string':
            raise ValueError('Chave image-path XFCE ausente ou ambígua')
        image_paths.append(properties[0].get('value'))
    all_image_paths = [
        prop for prop in root.iter('property') if prop.get('name') == 'image-path'
    ]
    if len(all_image_paths) != 4:
        raise ValueError('Quantidade inesperada de chaves XFCE image-path')
    return image_paths


def render_wallpaper_xml(document):
    values = _xfce_image_paths(document)
    if any(value not in (XUBUNTU_WALLPAPER, DEVLITE_WALLPAPER) for value in values):
        raise ValueError('Wallpaper XFCE não corresponde à configuração aprovada')

    def replace_tag(match):
        tag = match.group(0)
        try:
            element = ET.fromstring(tag)
        except ET.ParseError as error:
            raise ValueError('Tag XFCE image-path inválida') from error
        if element.get('name') != 'image-path':
            return tag
        value = element.get('value')
        if value == DEVLITE_WALLPAPER:
            return tag
        updated, count = VALUE_ATTRIBUTE.subn(
            lambda attribute: (
                attribute.group(1) + attribute.group(2)
                + DEVLITE_WALLPAPER + attribute.group(2)
            ),
            tag,
            count=1,
        )
        if count != 1:
            raise ValueError('Não foi possível atualizar a chave XFCE image-path')
        return updated

    rendered = PROPERTY_TAG.sub(replace_tag, document)
    if _xfce_image_paths(rendered) != [DEVLITE_WALLPAPER] * 4:
        raise ValueError('Wallpaper XFCE DevLite não foi aplicado aos quatro monitores')
    return rendered


def render_os_release(document):
    lines = document.splitlines()
    if lines.count('ID=ubuntu') != 1 or lines.count('LOGO=ubuntu-logo') != 1:
        raise ValueError('Identidade técnica ou logo OS release ausente ou ambíguo')
    return document.replace('LOGO=ubuntu-logo', 'LOGO=devlite', 1)


def render_install_catalog(document, base_size, visual_size):
    if type(base_size) is not int or type(visual_size) is not int or min(base_size, visual_size) < 0:
        raise ValueError('Tamanho de camada inválido')
    required_patterns = (
        r'(?m)^- default: true$',
        r'(?m)^  id: xubuntu-desktop-minimal$',
        r'(?m)^  locale_support: langpack$',
        r'(?m)^  type: fsimage-layered$',
        r'(?m)^  variant: desktop$',
    )
    for pattern in required_patterns:
        if len(re.findall(pattern, document)) != 1:
            raise ValueError('Identificador técnico do catálogo ausente ou ambíguo')

    replacements = (
        (
            r'(?m)^  description:\n    en: A minimal installation of the Xubuntu Desktop\.$',
            '  description:\n    en: A minimal installation of DevLite OS 1.0.',
        ),
        (
            r'(?m)^  name:\n    en: Xubuntu Minimal$',
            '  name:\n    en: DevLite OS 1.0',
        ),
        (
            r'(?m)^  path: minimal\.squashfs$',
            f'  path: {INSTALL_LAYER}',
        ),
    )
    rendered = document
    for pattern, replacement in replacements:
        rendered, count = re.subn(pattern, replacement, rendered)
        if count != 1:
            raise ValueError('Campo visível ou camada do catálogo ausente ou ambíguo')

    size_pattern = re.compile(r'(?m)^  size: ([0-9]+)$')
    size_matches = list(size_pattern.finditer(rendered))
    if len(size_matches) != 1 or int(size_matches[0].group(1)) != base_size:
        raise ValueError('Tamanho Base do catálogo diverge do artefato aprovado')
    return size_pattern.sub(
        '  size: ' + str(base_size + visual_size), rendered, count=1,
    )


def layer_stack(top_layer):
    path = PurePosixPath(top_layer)
    if (path.name != top_layer or path.suffix != '.squashfs'
            or not path.stem or any(not part for part in path.stem.split('.'))):
        raise ValueError('Nome de camada inválido')
    parts = path.stem.split('.')
    return tuple(
        '.'.join(parts[:index]) + '.squashfs'
        for index in range(1, len(parts) + 1)
    )


def remove_md5_entries(document, paths):
    removed = set(paths)
    counts = {path: 0 for path in removed}
    kept = []
    for line in document.splitlines():
        try:
            checksum, raw_name = line.split(maxsplit=1)
        except ValueError as error:
            raise ValueError('Manifesto MD5 inválido') from error
        name = raw_name.lstrip('* ').removeprefix('./')
        if len(checksum) != 32 or any(char not in '0123456789abcdefABCDEF' for char in checksum):
            raise ValueError('Checksum MD5 inválido no manifesto')
        if name in removed:
            counts[name] += 1
        else:
            kept.append(line)
    if any(count != 1 for count in counts.values()):
        raise ValueError('Caminho removido ausente ou ambíguo no manifesto MD5')
    return '\n'.join(kept) + '\n'


def preflight_visual_sources(base_image, live_image):
    base_image = Path(base_image)
    live_image = Path(live_image)
    for image in (base_image, live_image):
        if image.is_symlink() or not image.is_file():
            raise BuildError('Camada aprovada ausente ou não regular: ' + str(image))

    def read_member(image, member):
        result = subprocess.run(
            ['unsquashfs', '-cat', str(image), member],
            capture_output=True, text=True, env=dict(os.environ, LC_ALL='C'),
        )
        if result.returncode != 0:
            raise BuildError(
                f'Não foi possível ler {member} de {image}: '
                f'{result.stderr.strip()}'
            )
        return result.stdout

    source_xml = read_member(base_image, XFCE_CONFIG)
    wallpaper = read_member(base_image, WALLPAPER_FILE)
    os_release = read_member(base_image, OS_RELEASE)
    devlite_icon = read_member(base_image, DEVLITE_ICON)
    alias_result = subprocess.run(
        ['unsquashfs', '-ll', str(base_image), *PLYMOUTH_ALIASES],
        capture_output=True, text=True, env=dict(os.environ, LC_ALL='C'),
    )
    if alias_result.returncode != 0:
        raise BuildError(
            'Não foi possível inspecionar os aliases Plymouth da Base: '
            + alias_result.stderr.strip()
        )
    try:
        _validate_wallpaper_asset(wallpaper)
        rendered = render_wallpaper_xml(source_xml)
        rendered_os_release = render_os_release(os_release)
        _validate_wallpaper_asset(devlite_icon)
    except (ET.ParseError, ValueError) as error:
        raise BuildError(str(error)) from error
    source_aliases = _read_symlink_targets(alias_result.stdout, PLYMOUTH_ALIASES)
    if source_aliases != XUBUNTU_PLYMOUTH_ALIASES:
        raise BuildError('Aliases Plymouth da Base divergem do perfil Xubuntu aprovado')

    protected_live_paths = (
        XFCE_CONFIG, OS_RELEASE, DEVLITE_ICON,
        *PLYMOUTH_ALIASES, *PLYMOUTH_THEME_FILES,
    )
    for member in protected_live_paths:
        live_result = subprocess.run(
            ['unsquashfs', '-cat', str(live_image), member],
            capture_output=True, text=True, env=dict(os.environ, LC_ALL='C'),
        )
        missing = re.search(r'no matches for (/[^\n]+)', live_result.stderr.lower())
        valid_missing_paths = {
            '/' + '/'.join(Path(member).parts[:index])
            for index in range(1, len(Path(member).parts) + 1)
        }
        if (live_result.returncode != 2 or missing is None
                or missing.group(1).strip() not in valid_missing_paths):
            raise BuildError(
                'A camada Live sobrescreve ou não prova ausência do arquivo visual: '
                + member
            )

    return {
        'base_config_sha256': hashlib.sha256(source_xml.encode()).hexdigest(),
        'wallpaper_sha256': hashlib.sha256(wallpaper.encode()).hexdigest(),
        'visual_config_sha256': hashlib.sha256(rendered.encode()).hexdigest(),
        'base_os_release_sha256': hashlib.sha256(os_release.encode()).hexdigest(),
        'visual_os_release_sha256': hashlib.sha256(rendered_os_release.encode()).hexdigest(),
        'devlite_icon_sha256': hashlib.sha256(devlite_icon.encode()).hexdigest(),
        'plymouth_default_source': source_aliases['etc/alternatives/default.plymouth'],
        'plymouth_text_source': source_aliases['etc/alternatives/text.plymouth'],
        'plymouth_theme_sha256': hashlib.sha256(
            ''.join(PLYMOUTH_THEME_FILES.values()).encode()
        ).hexdigest(),
        'live_config_override': False,
        'live_plymouth_override': False,
    }


def _validate_wallpaper_asset(document):
    root = ET.fromstring(document)
    if root.tag.rsplit('}', 1)[-1] != 'svg':
        raise ValueError('Wallpaper DevLite no Base não é um SVG')


def _read_symlink_targets(listing, paths):
    targets = {}
    for path in paths:
        matches = [
            line for line in listing.splitlines()
            if line.split(' -> ', 1)[0].rstrip().endswith('/' + path)
        ]
        if (len(matches) != 1 or not matches[0].lstrip().startswith('lrwx')
                or ' -> ' not in matches[0]):
            raise BuildError('Link simbólico Plymouth ausente ou ambíguo: ' + path)
        targets[path] = matches[0].rsplit(' -> ', 1)[1]
    return targets


def _expected_overlay_entries(file_paths, link_paths):
    entries = set()
    for name in (*file_paths, *link_paths):
        parts = Path(name).parts
        entries.update('/'.join(parts[:index]) for index in range(1, len(parts) + 1))
    return entries


def build_visual_layer(base_image, output, workspace, run, epoch):
    base_image = Path(base_image)
    output = Path(output)
    workspace = Path(workspace)
    if (base_image.is_symlink() or not base_image.is_file()
            or output.exists() or output.is_symlink()
            or workspace.is_symlink() or not workspace.is_dir()):
        raise BuildError('Entrada, saída ou workspace da camada visual inválidos')

    source_xml = run(
        'read-xfce-default',
        ['unsquashfs', '-cat', str(base_image), XFCE_CONFIG],
    )
    wallpaper = run(
        'verify-devlite-wallpaper',
        ['unsquashfs', '-cat', str(base_image), WALLPAPER_FILE],
    )
    os_release = run(
        'read-os-release',
        ['unsquashfs', '-cat', str(base_image), OS_RELEASE],
    )
    devlite_icon = run(
        'verify-devlite-icon',
        ['unsquashfs', '-cat', str(base_image), DEVLITE_ICON],
    )
    alias_listing = run(
        'read-plymouth-aliases',
        ['unsquashfs', '-ll', str(base_image), *PLYMOUTH_ALIASES],
    )
    try:
        _validate_wallpaper_asset(wallpaper)
        _validate_wallpaper_asset(devlite_icon)
        rendered = render_wallpaper_xml(source_xml)
        rendered_os_release = render_os_release(os_release)
    except (ET.ParseError, ValueError) as error:
        raise BuildError(str(error)) from error
    if _read_symlink_targets(alias_listing, PLYMOUTH_ALIASES) != XUBUNTU_PLYMOUTH_ALIASES:
        raise BuildError('Aliases Plymouth da Base divergem do perfil Xubuntu aprovado')

    overlay_root = workspace / 'visual-overlay-root'
    if overlay_root.exists() or overlay_root.is_symlink():
        raise BuildError('Workspace da camada visual já existe')
    config = overlay_root / XFCE_CONFIG
    config.parent.mkdir(parents=True, mode=0o755)
    config.write_text(rendered, encoding='utf-8')
    config.chmod(0o644)
    os_release_path = overlay_root / OS_RELEASE
    os_release_path.parent.mkdir(parents=True, mode=0o755, exist_ok=True)
    os_release_path.write_text(rendered_os_release, encoding='utf-8')
    os_release_path.chmod(0o644)
    for name, contents in PLYMOUTH_THEME_FILES.items():
        target = overlay_root / name
        target.parent.mkdir(parents=True, mode=0o755, exist_ok=True)
        target.write_text(contents, encoding='utf-8')
        target.chmod(0o644)
    for name, target in PLYMOUTH_ALIASES.items():
        link = overlay_root / name
        link.parent.mkdir(parents=True, mode=0o755, exist_ok=True)
        os.symlink(target, link)
    for path in sorted(overlay_root.rglob('*'), key=lambda item: len(item.parts), reverse=True):
        if not path.is_symlink():
            path.chmod(0o755 if path.is_dir() else 0o644)
    for path in [overlay_root, *overlay_root.rglob('*')]:
        os.utime(path, (epoch, epoch), follow_symlinks=False)
    overlay_root.chmod(0o755)

    if not output.parent.is_dir() or output.parent.is_symlink():
        raise BuildError('Diretório de saída da camada visual inválido')
    run('build-visual-layer', [
        'mksquashfs', str(overlay_root), str(output),
        '-noappend', '-no-recovery', '-comp', 'xz', '-b', str(BLOCK_SIZE),
        '-processors', '1', '-mem', '256M', '-no-progress', '-exit-on-error',
        '-all-root',
    ])
    if (output.is_symlink() or not output.is_file()
            or output.stat().st_size > LAYER_MAX_BYTES):
        raise BuildError('Camada visual ausente ou acima do limite selado')

    metadata = run('verify-visual-layer-metadata', ['unsquashfs', '-s', str(output)])
    if 'Compression xz' not in metadata or f'Block size {BLOCK_SIZE}' not in metadata:
        raise BuildError('Formato da camada visual diverge das camadas aprovadas')

    extracted = workspace / 'visual-layer-verified'
    if extracted.exists() or extracted.is_symlink():
        raise BuildError('Destino de round-trip da camada visual já existe')
    run('roundtrip-visual-layer', [
        'unsquashfs', '-strict-errors', '-processors', '1',
        '-d', str(extracted), str(output),
    ])
    actual = {
        path.relative_to(extracted).as_posix()
        for path in extracted.rglob('*')
    }
    file_contents = {
        XFCE_CONFIG: rendered,
        OS_RELEASE: rendered_os_release,
        **PLYMOUTH_THEME_FILES,
    }
    expected = _expected_overlay_entries(file_contents, PLYMOUTH_ALIASES)
    if actual != expected:
        raise BuildError('Camada visual contém caminhos extras ou ausentes')
    for name, contents in file_contents.items():
        copied = extracted / name
        if (copied.is_symlink() or not copied.is_file()
                or copied.read_text(encoding='utf-8') != contents
                or stat.S_IMODE(copied.stat().st_mode) != 0o644):
            raise BuildError('Round-trip do arquivo visual divergiu: ' + name)
    for name, target in PLYMOUTH_ALIASES.items():
        copied = extracted / name
        if not copied.is_symlink() or os.readlink(copied) != target:
            raise BuildError('Round-trip do link Plymouth divergiu: ' + name)
    listing = run('list-visual-layer', ['unsquashfs', '-ll', str(output)])
    for name in file_contents:
        target_lines = [
            line for line in listing.splitlines()
            if line.split(' -> ', 1)[0].rstrip().endswith('/' + name)
        ]
        if (len(target_lines) != 1 or 'root/root' not in target_lines[0]
                or not target_lines[0].lstrip().startswith('-rw-r--r--')):
            raise BuildError(
                f'Proprietário ou modo do arquivo visual incorreto: {name}: '
                f'{target_lines!r}'
            )
    for name, target in PLYMOUTH_ALIASES.items():
        target_lines = [
            line for line in listing.splitlines()
            if line.split(' -> ', 1)[0].rstrip().endswith('/' + name)
        ]
        if (len(target_lines) != 1 or 'root/root' not in target_lines[0]
                or not target_lines[0].lstrip().startswith('lrwxrwxrwx')
                or not target_lines[0].rstrip().endswith(name + ' -> ' + target)):
            raise BuildError(
                f'Proprietário ou alvo do link Plymouth incorreto: {name}: '
                f'{target_lines!r}'
            )
    return allocated_usage(extracted)
