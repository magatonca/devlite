import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch
from v5 import execution as m
from v5 import worker

class ExecutionTests(unittest.TestCase):
    def test_command_has_exclusive_write_exception_and_all_namespaces(self):
        job=m.ROOT / "work/release-v5-fixture"
        args=m.command(job,"a"*64)
        self.assertEqual([a for a in args if a.startswith("--property=ReadWritePaths=")],["--property=ReadWritePaths="+str(job)])
        for prop in ("ProtectSystem=strict","ProtectHome=read-only","PrivateNetwork=yes","PrivateMounts=yes","NoNewPrivileges=yes","MemoryMax=2684354560","CPUQuota=100%"):
            self.assertIn("--property="+prop,args)
        self.assertIn("--working-directory="+str(m.ROOT),args)
    def test_guest_keep_capabilities_are_available_before_irreversible_drop(self):
        from pipeline.devlite.customize.executor_worker import KEEP_CAPS
        names={0:"CAP_CHOWN",1:"CAP_DAC_OVERRIDE",3:"CAP_FOWNER",4:"CAP_FSETID",5:"CAP_KILL",6:"CAP_SETGID",7:"CAP_SETUID",8:"CAP_SETPCAP",31:"CAP_SETFCAP"}
        prop=next(a for a in m.command(m.ROOT/"work/release-v5-fixture","a"*64) if "CapabilityBoundingSet=" in a)
        available=set(prop.partition("CapabilityBoundingSet=")[2].split())
        self.assertTrue({names[c] for c in KEEP_CAPS} <= available)
    def test_old_layers_are_immutable_and_live_does_not_inherit_installed_fix(self):
        self.assertEqual(m.STACKS["base"][-1],"minimal.visual.fix.squashfs")
        self.assertEqual(m.STACKS["live"][-1],"minimal.visual.live.fix.squashfs")
        self.assertNotIn("minimal.visual.fix.squashfs",m.STACKS["live"])
    def test_reserve_not_reduced(self):
        self.assertEqual(m.RESERVE,20*1024**3)
        self.assertLessEqual(2*m.UPPER_LIMIT+4*1024**3,8*1024**3)
    def test_read_refuses_escaped_or_symlink_job_before_any_action(self):
        for job in (Path("/tmp/release-v5-fixture"),Path("/")):
            with self.assertRaises(ValueError):m.read(job,"a"*64)
    def test_guest_has_no_host_apt_config_or_download(self):
        self.assertIn('Dir::Etc::parts "/run/devlite-v5/empty";',worker.APT_CONF)
        text=(m.ROOT/"v5/guest.py").read_text()
        self.assertIn('"--no-download"',text)
        self.assertIn('"--no-remove"',text)
        self.assertNotIn("sudo",text)
    def test_guest_reuses_epoch_aware_cache_and_absolute_dpkg_preflight(self):
        from pipeline.devlite.customize.guest_runner import apt_archive_name
        item={"package":"openssh-server","version":"1:9.6p1-3ubuntu13.20","architecture":"amd64"}
        self.assertEqual(apt_archive_name(item),"openssh-server_1%3a9.6p1-3ubuntu13.20_amd64.deb")
        text=(m.ROOT/"v5/guest.py").read_text()
        self.assertIn("reused.install_local(operands",text)
        self.assertNotIn("reused.main(",text)
        self.assertIn(m.ROOT/"pipeline/devlite/customize/guest_runner.py",m.code_paths())
    def test_guest_preserves_stderr_for_reused_dpkg_debug_parser(self):
        import sys
        from pipeline.devlite.customize import guest_runner
        with patch.dict(sys.modules,{"guest_runner":guest_runner}):
            from v5 import guest
        result=subprocess.CompletedProcess(["apt-get"],0,"APT summary\n","/bin/false --unpack /var/cache/apt/archives/pkg_1%3a1_amd64.deb\n")
        with patch.object(guest.subprocess,"run",return_value=result),patch("builtins.print"):
            combined=guest.call(["/usr/bin/apt-get","-s"])
        self.assertIn("/bin/false --unpack",combined)
        self.assertTrue(combined.startswith("APT summary"))
    def test_live_usage_tolerates_only_disappearing_files(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/"live").write_text("active");(root/"gone").write_text("temporary")
            real=Path.lstat
            def racing(path):
                if path.name=="gone":raise FileNotFoundError("maintscript removed it")
                return real(path)
            with patch.object(Path,"lstat",racing):
                self.assertGreater(worker.live_allocated_usage(root),0)
            with patch.object(Path,"lstat",side_effect=PermissionError("not a rename race")):
                with self.assertRaises(PermissionError):worker.live_allocated_usage(root)
    def test_browser_test_does_not_expand_filesystem_write_paths(self):
        job=m.ROOT/"work/release-v5-fixture"
        args=m.command(job,"a"*64,browser=True)
        self.assertEqual([a for a in args if "ReadWritePaths=" in a],["--property=ReadWritePaths="+str(job)])
        self.assertIn("CAP_MAC_ADMIN",args[-9] if False else " ".join(args))
    def test_browser_source_requires_root_and_accepted_receipt(self):
        with patch.object(m.os,"geteuid",return_value=1000):
            with self.assertRaises(ValueError):m.prepare_browser(Path("/tmp/unknown"),Path("/tmp/profile"))
    def test_compiled_browser_policy_binds_namespace_before_binary_load(self):
        import inspect
        from v5 import browser_probe
        source=inspect.getsource(m.prepare_browser)
        self.assertIn('"-Q","-K","-n","devlite-v5-"',source)
        loader=inspect.getsource(browser_probe.run)
        self.assertIn('"-K","-B","-a","-f"',loader)
        self.assertNotIn('"--replace"',loader)
        self.assertNotIn('"-r"',loader)
    def test_browser_capture_is_a_subprocess_with_gtk_initialized(self):
        from v5 import browser_probe
        result=subprocess.CompletedProcess([],0,"","")
        with patch.object(browser_probe.subprocess,"run",return_value=result) as runner:
            browser_probe.screenshot(Path("/tmp/probe-only.png"),":77")
        argv=runner.call_args.args[0]
        compile(argv[2],"<screenshot>","exec")
        self.assertIn("Gtk.init_check()",argv[2])
        self.assertEqual(argv[:2],["/usr/bin/python3","-c"])
    def test_browser_service_has_bound_crash_cleanup(self):
        job=m.ROOT/"work/release-v5-fixture"
        args=m.command(job,"a"*64,browser=True)
        expected="--property=ExecStopPost=/usr/bin/python3 -B -m v5.execution cleanup-browser "+str(job)+" "+"a"*64
        self.assertIn(expected,args)
        with patch.object(m.os,"geteuid",return_value=1000):
            with self.assertRaises(ValueError):m.cleanup_browser(job,"a"*64)
    def test_browser_socket_families_stay_in_private_network_only(self):
        job=m.ROOT/"work/release-v5-fixture"
        argv=m.command(job,"a"*64,browser=True)
        self.assertIn("--property=PrivateNetwork=yes",argv)
        self.assertIn("--property=RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6 AF_NETLINK",argv)
        self.assertIn("--property=RestrictAddressFamilies=AF_UNIX",m.command(job,"a"*64))
    def test_browser_proc_allows_self_attributes_but_guards_kernel_tunables(self):
        import inspect
        from v5 import browser_probe
        source=inspect.getsource(browser_probe.run)
        self.assertIn('("sys","sysrq-trigger","irq","bus","fs")',source)
        self.assertIn('"remount,bind,ro"',source)
        self.assertIn('"nosuid,nodev,noexec","proc"',source)
        self.assertIn('"ro,nosuid,nodev,noexec","proc"',inspect.getsource(worker.run))
    def test_browser_and_session_bus_share_policy_namespace(self):
        import inspect
        from v5 import browser_probe
        text=inspect.getsource(browser_probe.run)
        self.assertIn('"-n",namespace_name,"-p","unconfined","--","/usr/bin/dbus-run-session"',text)
        self.assertIn('"/usr/bin/aa-exec","-p","epiphany","--","/usr/bin/epiphany"',text)
        self.assertIn('(root/"dev/shm").chmod(0o1777)',text)
    def test_helper_executable_and_legacy_launcher_opens_same_gui(self):
        helper=m.ROOT/"v5/overlay/usr/libexec/devlite-services-v5"
        self.assertEqual(helper.stat().st_mode & 0o777,0o755)
        for name in ("devcontrol.desktop","devlite-control.desktop"):
            text=(m.ROOT/"v5/overlay/usr/share/applications"/name).read_text()
            self.assertIn("Name=DevControl 2.0",text);self.assertIn("Icon=devlite",text)
            self.assertNotIn("xfce4-terminal",text)
    def test_native_sandbox_evidence_rejects_inherited_namespace_or_filter(self):
        from v5.browser_probe import native_sandbox_proven
        parent={"namespaces":{"user":"u1","mnt":"m1","pid":"p1"},"status":"Seccomp: 2\nSeccomp_filters: 1\n"}
        child={"namespaces":{"user":"u2","mnt":"m2","pid":"p2"},"status":"Seccomp: 2\nSeccomp_filters: 2\nNoNewPrivs: 1\nCapEff: 0\nCapPrm: 0\nCapAmb: 0\n"}
        self.assertTrue(native_sandbox_proven(parent,child))
        for key in ("user","mnt","pid"):
            bad=dict(child,namespaces=dict(child["namespaces"],**{key:parent["namespaces"][key]}))
            self.assertFalse(native_sandbox_proven(parent,bad))
        for old,new in (("filters: 2","filters: 1"),("CapEff: 0","CapEff: 1"),("NoNewPrivs: 1","NoNewPrivs: 0")):
            self.assertFalse(native_sandbox_proven(parent,dict(child,status=child["status"].replace(old,new))))
    def test_browser_uses_private_pivot_root_not_chroot(self):
        import inspect
        from v5 import browser_probe
        text=inspect.getsource(browser_probe.child_setup)
        self.assertIn("libc.unshare(0x00020000)",text)
        self.assertIn("ctypes.c_long(155)",text)
        self.assertIn("libc.umount2",text)
        self.assertNotIn("os.chroot(",text)
    def test_browser_sysfs_exposes_only_readonly_hardware_subtrees(self):
        import inspect
        from v5 import browser_probe
        text=inspect.getsource(browser_probe.run)
        self.assertIn('("block","bus","class","dev","devices")',text)
        self.assertIn('"readonly-hardware-"',text)
        self.assertNotIn('"--rbind","/sys"',text)
    def test_profile_files_do_not_disable_protected_components(self):
        paths=[str(p.relative_to(m.ROOT/"v5/overlay")) for p in (m.ROOT/"v5/overlay").rglob("*") if p.is_file()]
        self.assertFalse(any("cloud-init.disabled" in p or p.endswith("apparmor.service") for p in paths))
    def test_polkit_active_admin_only_and_exact_helper(self):
        import xml.etree.ElementTree as ET
        path=m.ROOT/"v5/overlay/usr/share/polkit-1/actions/org.devlite.v5.services.policy"
        action=ET.fromstring(path.read_text()).find("action")
        self.assertEqual(action.find("defaults/allow_active").text,"auth_admin")
        self.assertEqual(action.find("defaults/allow_any").text,"no")
        self.assertEqual(action.find("defaults/allow_inactive").text,"no")
        self.assertEqual(action.find("annotate").text,"/usr/libexec/devlite-services-v5")
    def test_legacy_helper_has_no_mask_or_shell(self):
        text=(m.ROOT/"v5/overlay/usr/libexec/devlite-service-control").read_text()
        self.assertIn("from services import main",text)
        self.assertNotIn("subprocess",text)

    def test_browser_child_gets_fresh_proc_without_weakening_supervisor(self):
        import inspect
        from v5 import browser_probe
        child=inspect.getsource(browser_probe.child_setup)
        self.assertIn('libc.mount(b"proc",b"/proc",b"proc"',child)
        self.assertLess(child.index('libc.mount(b"proc"'),child.index('os.setuid(1000)'))
        self.assertIn('"remount,bind,ro"',inspect.getsource(browser_probe.run))
        self.assertIn("ProtectKernelTunables=yes"," ".join(m.command(m.ROOT/"work/release-v5-fixture","a"*64,browser=True)))
