import hashlib
import importlib.util
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from pipeline.devlite.modern_visual import (
    DEVLITE_ICON,
    DEVLITE_WALLPAPER,
    INSTALL_LAYER,
    LIVE_LAYER,
    OS_RELEASE,
    PLYMOUTH_ALIASES,
    PLYMOUTH_THEME_FILES,
    WALLPAPER_FILE,
    XFCE_CONFIG,
    XUBUNTU_WALLPAPER,
    XUBUNTU_PLYMOUTH_ALIASES,
    build_visual_layer,
    layer_stack,
    preflight_visual_sources,
    remove_md5_entries,
    render_install_catalog,
    render_os_release,
    render_wallpaper_xml,
)
from pipeline.devlite.runtime import BuildError, Runner


ROOT = Path(__file__).resolve().parents[1]
ISO_SCRIPT = ROOT / 'scripts/gerar-iso-modern-candidata.py'
ISO_SPEC = importlib.util.spec_from_file_location('modern_visual_iso_test', ISO_SCRIPT)
ISO = importlib.util.module_from_spec(ISO_SPEC)
ISO_SPEC.loader.exec_module(ISO)


def file_sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


XML = '''<?xml version="1.0" encoding="UTF-8"?>
<channel name="xfce4-desktop" version="1.0">
  <property name="backdrop" type="empty">
    <property name="screen0" type="empty">
      <property name="monitor0" type="empty">
        <property name="image-path" type="string" value="/usr/share/xfce4/backdrops/xubuntu-wallpaper.png"/>
        <property name="image-style" type="int" value="5"/>
        <property name="image-show" type="bool" value="true"/>
      </property>
      <property name="monitor1" type="empty">
        <property name="image-path" type="string" value="/usr/share/xfce4/backdrops/xubuntu-wallpaper.png"/>
      </property>
      <property name="monitor2" type="empty">
        <property name="image-path" type="string" value="/usr/share/xfce4/backdrops/xubuntu-wallpaper.png"/>
      </property>
      <property name="monitor3" type="empty">
        <property name="image-path" type="string" value="/usr/share/xfce4/backdrops/xubuntu-wallpaper.png"/>
      </property>
    </property>
  </property>
</channel>
'''

CATALOG = '''- default: true
  description:
    en: A minimal installation of the Xubuntu Desktop.
  id: xubuntu-desktop-minimal
  locale_support: langpack
  name:
    en: Xubuntu Minimal
  path: minimal.squashfs
  size: 1000
  type: fsimage-layered
  variant: desktop
'''

SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"/>'
OS_RELEASE_TEXT = (
    'PRETTY_NAME="DevLite OS 1.0"\n'
    'NAME="DevLite OS"\n'
    'ID=ubuntu\n'
    'LOGO=ubuntu-logo\n'
)


class ModernVisualTests(unittest.TestCase):
    def test_wallpaper_changes_only_the_four_static_monitor_paths(self):
        rendered = render_wallpaper_xml(XML)
        self.assertEqual(rendered.count(DEVLITE_WALLPAPER), 4)
        self.assertNotIn(XUBUNTU_WALLPAPER, rendered)
        self.assertEqual(
            rendered.replace(DEVLITE_WALLPAPER, XUBUNTU_WALLPAPER),
            XML,
        )

    def test_wallpaper_rejects_missing_monitors_and_unapproved_source_values(self):
        with self.assertRaisesRegex(ValueError, 'quatro monitores'):
            render_wallpaper_xml(XML.replace('name="monitor3"', 'name="monitor9"'))
        with self.assertRaisesRegex(ValueError, 'não corresponde'):
            render_wallpaper_xml(XML.replace(XUBUNTU_WALLPAPER, '/tmp/other.png', 1))

    def test_os_release_changes_only_the_display_logo_and_preserves_technical_id(self):
        rendered = render_os_release(OS_RELEASE_TEXT)
        self.assertEqual(rendered, OS_RELEASE_TEXT.replace('LOGO=ubuntu-logo', 'LOGO=devlite'))
        self.assertIn('ID=ubuntu', rendered)
        with self.assertRaisesRegex(ValueError, 'Identidade técnica'):
            render_os_release(OS_RELEASE_TEXT.replace('ID=ubuntu', 'ID=devlite'))

    def test_catalog_changes_visible_brand_and_uses_a_compatible_layer_chain(self):
        rendered = render_install_catalog(CATALOG, 1000, 64)
        self.assertIn('en: DevLite OS 1.0', rendered)
        self.assertIn('en: A minimal installation of DevLite OS 1.0.', rendered)
        self.assertIn(f'path: {INSTALL_LAYER}', rendered)
        self.assertIn('size: 1064', rendered)
        self.assertIn('id: xubuntu-desktop-minimal', rendered)
        self.assertIn('type: fsimage-layered', rendered)
        self.assertIn('variant: desktop', rendered)
        self.assertIn('locale_support: langpack', rendered)
        self.assertIn('default: true', rendered)

    def test_catalog_rejects_technical_identifier_or_size_drift(self):
        with self.assertRaisesRegex(ValueError, 'Identificador técnico'):
            render_install_catalog(
                CATALOG.replace('xubuntu-desktop-minimal', 'devlite-minimal'),
                1000, 64,
            )
        with self.assertRaisesRegex(ValueError, 'Tamanho Base'):
            render_install_catalog(CATALOG, 999, 64)

    def test_installer_and_live_names_resolve_to_the_same_base_and_visual_layer(self):
        self.assertEqual(
            layer_stack(INSTALL_LAYER),
            ('minimal.squashfs', INSTALL_LAYER),
        )
        self.assertEqual(
            layer_stack(LIVE_LAYER),
            ('minimal.squashfs', INSTALL_LAYER, LIVE_LAYER),
        )
        with self.assertRaisesRegex(ValueError, 'Nome de camada'):
            layer_stack('../minimal.visual.squashfs')

    def test_removed_source_layer_is_removed_from_md5_manifest_exactly_once(self):
        manifest = (
            'a' * 32 + '  ./casper/minimal.live.squashfs\n'
            + 'b' * 32 + '  ./casper/minimal.squashfs\n'
        )
        rendered = remove_md5_entries(
            manifest, {'casper/minimal.live.squashfs'},
        )
        self.assertNotIn('minimal.live.squashfs', rendered)
        self.assertIn('minimal.squashfs', rendered)
        with self.assertRaisesRegex(ValueError, 'ausente ou ambíguo'):
            remove_md5_entries(
                manifest + manifest.splitlines()[0] + '\n',
                {'casper/minimal.live.squashfs'},
            )

    @unittest.skipUnless(
        shutil.which('mksquashfs') and shutil.which('unsquashfs'),
        'mksquashfs and unsquashfs are required for the fixture integration test',
    )
    def test_visual_squashfs_is_a_separate_roundtripped_overlay(self):
        with tempfile.TemporaryDirectory(prefix='devlite-visual-test-') as temp:
            root = Path(temp)
            source = root / 'fixture-root'
            config = source / XFCE_CONFIG
            config.parent.mkdir(parents=True)
            config.write_text(XML, encoding='utf-8')
            wallpaper = source / WALLPAPER_FILE
            wallpaper.parent.mkdir(parents=True)
            wallpaper.write_text(SVG, encoding='utf-8')
            icon = source / DEVLITE_ICON
            icon.parent.mkdir(parents=True)
            icon.write_text(SVG, encoding='utf-8')
            os_release = source / OS_RELEASE
            os_release.parent.mkdir(parents=True, exist_ok=True)
            os_release.write_text(OS_RELEASE_TEXT, encoding='utf-8')
            for name, target in XUBUNTU_PLYMOUTH_ALIASES.items():
                link = source / name
                link.parent.mkdir(parents=True, exist_ok=True)
                link.symlink_to(target)
            base = root / 'fixture-base.squashfs'
            subprocess.run(
                [
                    'mksquashfs', str(source), str(base), '-noappend',
                    '-no-recovery', '-comp', 'xz', '-b', '131072',
                    '-processors', '1', '-no-progress',
                ],
                check=True, capture_output=True,
            )
            live_source = root / 'fixture-live-root'
            (live_source / 'etc').mkdir(parents=True)
            (live_source / 'etc/live-only.txt').write_text('live layer\n')
            live = root / 'fixture-live.squashfs'
            subprocess.run(
                [
                    'mksquashfs', str(live_source), str(live), '-noappend',
                    '-no-recovery', '-comp', 'xz', '-b', '131072',
                    '-processors', '1', '-no-progress',
                ],
                check=True, capture_output=True,
            )
            preflight = preflight_visual_sources(base, live)
            self.assertFalse(preflight['live_config_override'])
            self.assertEqual(preflight['visual_config_sha256'],
                             hashlib.sha256(render_wallpaper_xml(XML).encode()).hexdigest())
            override_source = root / 'fixture-live-override-root'
            override_config = override_source / XFCE_CONFIG
            override_config.parent.mkdir(parents=True)
            override_config.write_text(XML, encoding='utf-8')
            live_override = root / 'fixture-live-override.squashfs'
            subprocess.run(
                [
                    'mksquashfs', str(override_source), str(live_override),
                    '-noappend', '-no-recovery', '-comp', 'xz', '-b',
                    '131072', '-processors', '1', '-no-progress',
                ],
                check=True, capture_output=True,
            )
            with self.assertRaisesRegex(BuildError, 'sobrescreve'):
                preflight_visual_sources(base, live_override)

            os_release_override_root = root / 'fixture-live-os-release-root'
            live_os_release = os_release_override_root / OS_RELEASE
            live_os_release.parent.mkdir(parents=True)
            live_os_release.write_text(OS_RELEASE_TEXT, encoding='utf-8')
            live_os_release_override = root / 'fixture-live-os-release.squashfs'
            subprocess.run(
                [
                    'mksquashfs', str(os_release_override_root),
                    str(live_os_release_override), '-noappend', '-no-recovery',
                    '-comp', 'xz', '-b', '131072', '-processors', '1',
                    '-no-progress',
                ],
                check=True, capture_output=True,
            )
            with self.assertRaisesRegex(BuildError, 'sobrescreve'):
                preflight_visual_sources(base, live_os_release_override)

            live_plymouth_override_root = root / 'fixture-live-plymouth-root'
            live_plymouth_override = (
                live_plymouth_override_root
                / 'usr/share/plymouth/themes/devlite/devlite.plymouth'
            )
            live_plymouth_override.parent.mkdir(parents=True)
            live_plymouth_override.write_text('unexpected theme\n', encoding='utf-8')
            live_plymouth_image = root / 'fixture-live-plymouth.squashfs'
            subprocess.run(
                [
                    'mksquashfs', str(live_plymouth_override_root),
                    str(live_plymouth_image), '-noappend', '-no-recovery',
                    '-comp', 'xz', '-b', '131072', '-processors', '1',
                    '-no-progress',
                ],
                check=True, capture_output=True,
            )
            with self.assertRaisesRegex(BuildError, 'sobrescreve'):
                preflight_visual_sources(base, live_plymouth_image)

            base_digest = file_sha256(base)
            workspace = root / 'stage'
            workspace.mkdir()
            logs = workspace / 'logs'
            logs.mkdir()
            output = workspace / INSTALL_LAYER
            uncompressed_size = build_visual_layer(
                base, output, workspace, Runner(logs, 1788856610).run,
                1788856610,
            )
            rendered = render_wallpaper_xml(XML)

            self.assertTrue(output.is_file())
            self.assertGreater(uncompressed_size, 0)
            self.assertEqual(
                file_sha256(base),
                base_digest,
            )
            self.assertEqual(
                subprocess.run(
                    ['unsquashfs', '-cat', str(output), XFCE_CONFIG],
                    check=True, capture_output=True, text=True,
                ).stdout,
                rendered,
            )
            self.assertEqual(
                subprocess.run(
                    ['unsquashfs', '-cat', str(output), OS_RELEASE],
                    check=True, capture_output=True, text=True,
                ).stdout,
                render_os_release(OS_RELEASE_TEXT),
            )
            for name, target in PLYMOUTH_ALIASES.items():
                listing = subprocess.run(
                    ['unsquashfs', '-ll', str(output), name],
                    check=True, capture_output=True, text=True,
                ).stdout
                self.assertIn(f'{name} -> {target}', listing)
            for name, content in PLYMOUTH_THEME_FILES.items():
                self.assertEqual(
                    subprocess.run(
                        ['unsquashfs', '-cat', str(output), name],
                        check=True, capture_output=True, text=True,
                    ).stdout,
                    content,
                )
            self.assertEqual(
                subprocess.run(
                    ['unsquashfs', '-cat', str(base), XFCE_CONFIG],
                    check=True, capture_output=True, text=True,
                ).stdout,
                XML,
            )

    def test_visual_layer_builder_rejects_overwriting_an_existing_output(self):
        with tempfile.TemporaryDirectory(prefix='devlite-visual-existing-') as temp:
            root = Path(temp)
            workspace = root / 'stage'
            workspace.mkdir()
            base = root / 'base.squashfs'
            output = workspace / INSTALL_LAYER
            base.write_bytes(b'not-read-because-output-exists')
            output.write_bytes(b'preserve-me')
            logs = workspace / 'logs'
            logs.mkdir()
            with self.assertRaisesRegex(BuildError, 'inválidos'):
                build_visual_layer(
                    base, output, workspace, Runner(logs, 1788856610).run,
                    1788856610,
                )
            self.assertEqual(output.read_bytes(), b'preserve-me')

    def test_iso_layout_accepts_only_the_existing_pair_or_visual_layer_chain(self):
        required = (
            'casper/initrd', 'casper/vmlinuz', 'casper/filesystem.manifest',
            'casper/minimal.manifest', 'casper/minimal.live.manifest',
            'EFI/boot/bootx64.efi', 'EFI/boot/grubx64.efi', 'boot/grub/grub.cfg',
        )
        with tempfile.TemporaryDirectory(prefix='devlite-layout-test-') as temp:
            tree = Path(temp)
            for name in required:
                path = tree / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    'snap:ubuntu-desktop-bootstrap\n'
                    if name == 'casper/filesystem.manifest' else 'fixture\n',
                    encoding='utf-8',
                )
            casper = tree / 'casper'
            for name in (
                    'minimal.squashfs', 'minimal.visual.squashfs',
                    'minimal.visual.live.squashfs'):
                (casper / name).write_bytes(b'fixture')
            for name, value in (
                    ('minimal.size', 1000), ('minimal.live.size', 2000),
                    ('minimal.visual.size', 64), ('filesystem.size', 3064)):
                (casper / name).write_text(str(value) + '\n', encoding='ascii')
            (casper / 'install-sources.yaml').write_text(
                '- default: true\n'
                '  description:\n    en: A minimal installation of DevLite OS 1.0.\n'
                '  id: xubuntu-desktop-minimal\n'
                '  locale_support: langpack\n'
                '  name:\n    en: DevLite OS 1.0\n'
                f'  path: {INSTALL_LAYER}\n'
                '  size: 1064\n'
                '  type: fsimage-layered\n'
                '  variant: desktop\n',
                encoding='utf-8',
            )
            (casper / 'devlite-release.json').write_text(
                '{"plymouth": {'
                '"rootfs_default_theme": "DevLite OS 1.0", '
                '"rootfs_text_theme": "DevLite OS 1.0", '
                '"live_initramfs": "unchanged; upstream Xubuntu splash remains"'
                '}}',
                encoding='utf-8',
            )
            (tree / 'boot/grub/grub.cfg').write_text(
                'linux /casper/vmlinuz layerfs-path=minimal.visual.live.squashfs ---\n',
                encoding='utf-8',
            )
            (tree / 'boot/grub/loopback.cfg').write_text(
                'linux /casper/vmlinuz layerfs-path=minimal.visual.live.squashfs ---\n',
                encoding='utf-8',
            )
            self.assertEqual(ISO.validate_visual_layout(tree), sorted((
                'minimal.squashfs', INSTALL_LAYER, LIVE_LAYER,
            )))
            (casper / 'unexpected.squashfs').write_bytes(b'not-allowed')
            with self.assertRaisesRegex(BuildError, 'Cadeia SquashFS'):
                ISO.validate_visual_layout(tree)


if __name__ == '__main__':
    unittest.main()
