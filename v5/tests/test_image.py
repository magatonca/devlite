import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from v5.image import finalize, put, confined, DISABLED

class ImageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        identity = self.root / "usr/share/devlite-os/identity.json"
        identity.parent.mkdir(parents=True)
        identity.write_text(json.dumps({"name":"DevLite OS"}))
        (self.root / "etc/systemd/system").mkdir(parents=True)
        vendor=self.root / "usr/lib/systemd/system";vendor.mkdir(parents=True)
        for unit in DISABLED: (vendor / unit).write_text("[Unit]\nDescription=test\n")
        self.calls = []
    def run_offline(self, args, **kwargs):
        self.calls.append(args)
        return SimpleNamespace(returncode=0, stderr="")
    def test_remove_only_factory_mask_and_keep_vendor_alias(self):
        units = self.root / "etc/systemd/system"
        (units / "apache2.service").symlink_to("/dev/null")
        (units / "mysql.service").symlink_to("/lib/systemd/system/mariadb.service")
        result = finalize(self.root, self.run_offline)
        self.assertFalse((units / "apache2.service").is_symlink())
        self.assertTrue((units / "mysql.service").is_symlink())
        self.assertEqual(result["removed_factory_masks"], ["etc/systemd/system/apache2.service"])
        self.assertEqual(self.calls[0][:3], ["/usr/bin/systemctl", "--root="+str(self.root), "disable"])
        self.assertNotIn("--now", self.calls[0])
    def test_missing_installed_unit_blocks_finalization(self):
        (self.root / "usr/lib/systemd/system/ssh.service").unlink()
        with self.assertRaises(ValueError): finalize(self.root,self.run_offline)
        self.assertFalse(self.calls)
    def test_no_parent_escape(self):
        with self.assertRaises(ValueError): confined(self.root, "../outside")
    def test_no_host_root(self):
        with self.assertRaises(ValueError): confined(Path("/"), "etc/os-release")
    def test_symlink_ancestor_rejected(self):
        (self.root / "etc/systemd/system").rmdir()
        (self.root / "etc/systemd/system").symlink_to("/etc")
        with self.assertRaises(ValueError): finalize(self.root, self.run_offline)
        self.assertFalse(self.calls)
    def test_failed_offline_disable_stops(self):
        with self.assertRaises(ValueError): finalize(self.root, lambda *a, **k: SimpleNamespace(returncode=1, stderr="fail"))
    def test_boot_link_remaining_is_error(self):
        wants=self.root / "etc/systemd/system/multi-user.target.wants"
        wants.mkdir(); (wants / "docker.service").symlink_to("/lib/systemd/system/docker.service")
        with self.assertRaises(ValueError): finalize(self.root, self.run_offline)
    def test_only_disposable_generated_keys_removed(self):
        ssh=self.root / "etc/ssh";ssh.mkdir()
        (ssh / "ssh_host_ed25519_key").write_text("temporary postinst key")
        (ssh / "authorized_keys").write_text("preserved")
        finalize(self.root,self.run_offline)
        self.assertFalse((ssh / "ssh_host_ed25519_key").exists())
        self.assertEqual((ssh / "authorized_keys").read_text(),"preserved")
    def test_put_replaces_shared_inode(self):
        first=self.root / "file";first.write_text("old")
        os.link(first,self.root / "canonical")
        put(self.root,"file","new")
        self.assertEqual(first.read_text(),"new")
        self.assertEqual((self.root / "canonical").read_text(),"old")
    def test_ssh_policy_is_deny_root_and_unique_not_prebuilt(self):
        overlay=Path(__file__).resolve().parents[1] / "overlay"
        self.assertIn("PermitRootLogin no",(overlay / "etc/ssh/sshd_config.d/00-devlite-security.conf").read_text())
        self.assertIn("ssh-keygen -A",(overlay / "usr/lib/systemd/system/devlite-ssh-hostkeys.service").read_text())
        self.assertFalse(list(overlay.rglob("ssh_host_*")))
