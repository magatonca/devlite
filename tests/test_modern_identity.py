import json
import re
import unittest
from pathlib import Path

from pipeline.devlite.modern_identity import (
    INSTALLER_DESKTOP_ENTRY,
    INSTALLER_SERVICE_DROPIN,
    TITLE_MAP,
    brand_grub_titles,
    set_grub_layer_path,
)


ROOT = Path(__file__).resolve().parents[1]

GRUB = '''set timeout=30
menu_color_normal=white/black
menuentry "Try or Install Xubuntu" {
\tset gfxpayload=keep
\tlinux /casper/vmlinuz locale=pt_BR.UTF-8 --- quiet splash
\tinitrd /casper/initrd
}
menuentry "Xubuntu (safe graphics)" {
\tset gfxpayload=keep
\tlinux /casper/vmlinuz nomodeset --- quiet splash
\tinitrd /casper/initrd
}
'''


class ModernIdentityTests(unittest.TestCase):
    def test_grub_changes_only_the_two_visible_titles(self):
        result = brand_grub_titles(GRUB)
        expected = GRUB.replace(
            '"Try or Install Xubuntu"', '"Try or Install DevLite OS 1.0"',
        ).replace('"Xubuntu (safe graphics)"', '"DevLite OS 1.0 (safe graphics)"')
        self.assertEqual(result, expected)

    def test_grub_branding_is_idempotent(self):
        first = brand_grub_titles(GRUB)
        self.assertEqual(brand_grub_titles(first), first)

    def test_grub_rejects_missing_or_ambiguous_menu_entries(self):
        with self.assertRaisesRegex(ValueError, 'Entrada GRUB'):
            brand_grub_titles(GRUB.replace('Xubuntu (safe graphics)', 'Xubuntu (safe)'))
        with self.assertRaisesRegex(ValueError, 'Entrada GRUB'):
            brand_grub_titles(GRUB + 'menuentry "Try or Install Xubuntu" {\n}\n')

    def test_single_quote_and_loopback_style_entries_are_supported(self):
        loopback = GRUB.replace('"Try or Install Xubuntu"', "'Try or Install Xubuntu'")
        result = brand_grub_titles(loopback)
        self.assertIn("'Try or Install DevLite OS 1.0'", result)
        self.assertEqual(result.count('/casper/vmlinuz'), 2)

    def test_grub_layer_path_is_added_to_every_live_kernel_line_and_is_idempotent(self):
        rendered = set_grub_layer_path(GRUB)
        kernel_lines = [
            line for line in rendered.splitlines()
            if '/casper/vmlinuz' in line
        ]
        self.assertEqual(len(kernel_lines), 2)
        self.assertTrue(all(
            'layerfs-path=minimal.visual.live.squashfs ---' in line
            for line in kernel_lines
        ))
        self.assertEqual(set_grub_layer_path(rendered), rendered)

    def test_grub_layer_path_rejects_missing_or_unexpected_existing_values(self):
        with self.assertRaisesRegex(ValueError, 'Nenhuma entrada GRUB'):
            set_grub_layer_path('menuentry "Other" {\\n}\\n')
        changed = GRUB.replace(
            'locale=pt_BR.UTF-8',
            'locale=pt_BR.UTF-8 layerfs-path=minimal.live.squashfs',
        )
        with self.assertRaisesRegex(ValueError, 'inesperado'):
            set_grub_layer_path(changed)

    def test_installer_dropin_changes_only_description(self):
        self.assertEqual(INSTALLER_SERVICE_DROPIN.splitlines(), [
            '[Unit]', 'Description=Instalador do DevLite OS 1.0',
        ])
        self.assertNotIn('ExecStart', INSTALLER_SERVICE_DROPIN)
        self.assertNotIn('ExecStop', INSTALLER_SERVICE_DROPIN)

    def test_installer_shortcut_calls_existing_user_service_without_privilege_escalation(self):
        self.assertIn('Name[pt_BR]=Instalar DevLite OS 1.0', INSTALLER_DESKTOP_ENTRY)
        self.assertIn(
            'Exec=/usr/bin/systemctl --user start xubuntu-installer.service',
            INSTALLER_DESKTOP_ENTRY,
        )
        self.assertIn('Terminal=false', INSTALLER_DESKTOP_ENTRY)
        self.assertNotIn('sudo', INSTALLER_DESKTOP_ENTRY)
        self.assertNotIn('pkexec', INSTALLER_DESKTOP_ENTRY)

    def test_overlay_payload_matches_branding_constants(self):
        overlay = ROOT / 'overlay/modern-release-v1'
        desktop = (overlay / 'usr/share/applications/devlite-installer.desktop').read_text()
        dropin = (
            overlay / 'etc/systemd/user/xubuntu-installer.service.d/10-devlite-branding.conf'
        ).read_text()
        self.assertEqual(desktop, INSTALLER_DESKTOP_ENTRY)
        self.assertEqual(dropin, INSTALLER_SERVICE_DROPIN)

    def test_new_plan_keeps_approved_baseline_and_storage_gate(self):
        plan = json.loads((ROOT / 'config/modern-finalization-v2.json').read_text())
        self.assertEqual(
            plan['baseline']['sha256'],
            '7373cb9be11ebda5218f20795fec87eab20c2cebef3c763ae6e5c63d4e7cd7bd',
        )
        self.assertFalse(plan['capacity_gate']['build_started'])
        self.assertFalse(plan['reuse']['vscode']['binary_in_iso'])
        self.assertGreater(
            plan['capacity_gate']['current_free_bytes'],
            plan['capacity_gate']['existing_pack_preflight_required_bytes'],
        )
        self.assertEqual(set(TITLE_MAP), {
            'Try or Install Xubuntu',
            'Xubuntu (safe graphics)',
        })


if __name__ == '__main__':
    unittest.main()
