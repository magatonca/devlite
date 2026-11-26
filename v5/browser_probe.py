"""Graphical browser probe in fresh COW roots and a disposable AppArmor namespace.

Never loads into the host's default policy namespace. Never publishes test roots.
"""
import ctypes
import hashlib
import json
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path
from pipeline.devlite.minimal_root import EPOCH, snapshot
from pipeline.devlite.runtime import Runner
from pipeline.devlite.structure import digest
from v5.execution import ROOT, CASPER, STACKS, RESERVE, save
from v5.image import put

HTML="""<!doctype html><html><head><meta charset="utf-8"><title>DevLite Browser PASS</title></head>
<body style="background:#17202b;color:#fff;font:32px sans-serif;padding:50px"><h1 style="color:#45b6ff">DevLite OS v5</h1>
<p>EPIPHANY — RENDERIZAÇÃO OK</p><p id="js">JavaScript pendente</p><script>document.getElementById('js').textContent='JAVASCRIPT OK';</script>
<p>AppArmor restrito • WebKit sandbox</p></body></html>"""

def inventory_digest(root):
    return hashlib.sha256(json.dumps(snapshot(root),sort_keys=True,separators=(",",":")).encode()).hexdigest()

def child_setup(root,logfile=None):
    def setup():
        # CLONE_NEWUSER is forbidden by the kernel from a plain chroot.
        # Give this process a genuine private mount-namespace root instead.
        os.setsid()
        if os.uname().machine!="x86_64":raise ValueError("Unsupported pivot_root syscall ABI")
        libc=ctypes.CDLL(None,use_errno=True)
        before=os.readlink("/proc/self/ns/mnt")
        if libc.unshare(0x00020000):raise OSError(ctypes.get_errno(),"private mount namespace")
        if os.readlink("/proc/self/ns/mnt")==before:raise ValueError("Mount namespace not isolated")
        if libc.mount(None,b"/",None,ctypes.c_ulong(16384|262144),None):
            raise OSError(ctypes.get_errno(),"private mount propagation")
        old=root/(".probe-oldroot-"+str(os.getpid()));old.mkdir(mode=0o700)
        if libc.syscall(ctypes.c_long(155),ctypes.c_char_p(os.fsencode(root)),ctypes.c_char_p(os.fsencode(old))):
            raise OSError(ctypes.get_errno(),"private pivot_root")
        os.chdir("/");old_name="/"+old.name
        if libc.umount2(os.fsencode(old_name),2):raise OSError(ctypes.get_errno(),"detach old namespace root")
        os.rmdir(old_name)
        # A procfs carrying locked overmounts cannot be mounted again by
        # bwrap in a descendant user namespace (mount_too_revealing). Keep
        # the supervisor's guarded procfs intact. This test-only child gets
        # a fresh PID-namespace procfs; the enforced browser policy must deny
        # writes to every global tunable, including disconnected aliases.
        if libc.mount(b"proc",b"/proc",b"proc",ctypes.c_ulong(2|4|8),None):
            raise OSError(ctypes.get_errno(),"private browser procfs")
        if logfile is not None:
            fd=os.open(logfile,os.O_WRONLY|os.O_APPEND|os.O_NOFOLLOW)
            os.dup2(fd,1);os.dup2(fd,2);os.close(fd)
        os.setgroups([]);os.setgid(1000);os.setuid(1000)
    return setup

def stop(process):
    if process is None:return
    try:os.killpg(process.pid,signal.SIGKILL)
    except ProcessLookupError:pass
    process.wait(timeout=15)

def screenshot(path,display):
    # GTK initializes visuals in a child, never in the PID-1 supervisor.
    script="""import gi,sys
 gi.require_version('Gtk','3.0')
 from gi.repository import Gtk,Gdk
 if not Gtk.init_check()[0]:raise SystemExit('No X display')
 w=Gdk.get_default_root_window()
 p=Gdk.pixbuf_get_from_window(w,0,0,w.get_width(),w.get_height())
 if p is None:raise SystemExit('No pixbuf')
 p.savev(sys.argv[1],'png',[],[])
"""
    script="\n".join(line[1:] if line.startswith(' ') else line for line in script.splitlines())
    subprocess.run(["/usr/bin/python3","-c",script,str(path)],env={"PATH":"/usr/bin:/bin","LC_ALL":"C","DISPLAY":display,"GDK_BACKEND":"x11"},capture_output=True,text=True,check=True,timeout=20)

def native_sandbox_proven(parent,renderer):
    try:
        def fields(s):return dict(line.split(":",1) for line in s["status"].splitlines() if ":" in line)
        state=fields(renderer);prior=fields(parent)
        return (all(renderer["namespaces"][n]!=parent["namespaces"][n] for n in ("user","mnt","pid"))
            and state.get("Seccomp","").strip()=="2" and state.get("NoNewPrivs","").strip()=="1"
            and int(state.get("Seccomp_filters","0"))>int(prior.get("Seccomp_filters","0"))
            and all(int(state.get(k,"1"),16)==0 for k in ("CapEff","CapPrm","CapAmb")))
    except (KeyError,TypeError,ValueError):return False

def run(job,data,approval):
    diagnostic=data["phase"]=="browser-audit-only"
    expected_mode="complain" if diagnostic else "enforce"
    source=Path(data["browser"]["applied_job"])
    if digest(source/"application-result.json")!=data["browser"]["result_sha256"]:
        raise ValueError("Applied receipt changed")
    for target,expected in data["browser"]["upper_inventory_sha256"].items():
        if inventory_digest(source/"application"/target/"upper")!=expected:raise ValueError("Applied COW input changed")
    profile=job/"browser-profile.bin"
    if digest(profile)!=data["browser"]["profile_binary_sha256"]:raise ValueError("Profile changed")
    attempt=job/"browser-probe";attempt.mkdir(mode=0o700);(attempt/"logs").mkdir()
    runner=Runner(attempt/"logs",EPOCH);runner.env.pop("SOURCE_DATE_EPOCH",None)
    mounts=[];namespace=None;created_namespace=False;original_profiles=None;aa=None
    report={"status":"running","kernel_global_profiles_modified":False,"results":{},"iso_generated":False}
    def call(label,args):
        if shutil.disk_usage(job).free<RESERVE:raise ValueError("20 GiB reserve")
        return runner.run(label,args)
    def mount(label,args,path):call(label,args);mounts.append(path)
    def unmount(path):runner.run("umount-"+str(len(mounts)),["umount",str(path)]);mounts.remove(path)
    try:
        call("private",["mount","--make-rprivate","/"])
        aa=attempt/"securityfs";aa.mkdir()
        mount("securityfs-private-access",["mount","-t","securityfs","-o","nosuid,nodev,noexec","securityfs",str(aa)],aa)
        aa=aa/"apparmor"
        original_profiles=(aa/"profiles").read_text()
        namespace_name="devlite-v5-"+job.name.removeprefix("release-v5-")
        namespace=aa/"policy/namespaces"/namespace_name
        if namespace.exists():raise ValueError("Never reuse an existing policy namespace")
        save(job/"namespace-planned.json",{"namespace":namespace_name,"contract_sha256":approval})
        namespace.mkdir();created_namespace=True
        call("load-private-policy",["apparmor_parser","-K","-B","-a","-f",str(aa),str(profile)])
        private_profiles="".join((p/"name").read_text().strip()+" ("+(p/"mode").read_text().strip()+")\n" for p in (namespace/"profiles").iterdir())
        if "epiphany ("+expected_mode+")" not in private_profiles or "unconfined" in private_profiles or (not diagnostic and "complain" in private_profiles):
            raise ValueError("Policy not confined/enforced")
        save(attempt/"profile-state.json",{"namespace":namespace_name,"profiles":private_profiles,"binary_sha256":digest(profile)})
        lowers={}
        for name in sorted({n for names in STACKS.values() for n in names}):
            image=CASPER/name
            if digest(image)!=data["lowers"][str(image)]:raise ValueError("v4 lower changed")
            path=attempt/("lower-"+name);path.mkdir()
            mount("lower-"+name,["mount","-t","squashfs","-o","loop,ro,nodev,nosuid",str(image),str(path)],path);lowers[name]=path
        shared_tmp=attempt/"x11-tmp";shared_tmp.mkdir(mode=0o1777);shared_tmp.chmod(0o1777)
        mount("private-tmp",["mount","--bind",str(shared_tmp),"/tmp"],Path("/tmp"))
        for target in ("base","live"):
            stage=attempt/target;stage.mkdir();upper=stage/"upper";upper.mkdir();work=stage/"work";work.mkdir();root=stage/"root";root.mkdir()
            layers=[source/"application"/target/"upper"]+[lowers[n] for n in reversed(STACKS[target])]
            options="lowerdir="+":".join(map(str,layers))+",upperdir="+str(upper)+",workdir="+str(work)+",index=off,metacopy=off,redirect_dir=off,xino=off"
            mount("overlay-"+target,["mount","-t","overlay","overlay","-o",options,str(root)],root)
            ephemeral=[]
            for directory in ("run","tmp","var/tmp","dev","sys","home"):
                p=root/directory
                mount("tmpfs-"+target+"-"+directory.replace("/","-"),["mount","-t","tmpfs","-o","nosuid,nodev,mode=0755,size=128m","tmpfs",str(p)],p);ephemeral.append(p)
                if directory in ("tmp","var/tmp"):p.chmod(0o1777)
            # Same private X socket namespace, no TCP and no host session socket.
            unmount(root/"tmp");ephemeral.remove(root/"tmp")
            mount("session-tmp-"+target,["mount","--bind",str(shared_tmp),str(root/"tmp")],root/"tmp");ephemeral.append(root/"tmp")
            for name,major,minor in (("null",1,3),("zero",1,5),("full",1,7),("random",1,8),("urandom",1,9),("tty",5,0)):
                os.mknod(root/"dev"/name,0o666|__import__("stat").S_IFCHR,os.makedev(major,minor));(root/"dev"/name).chmod(0o666)
            call("dev-"+target,["mount","-o","remount,dev,nosuid",str(root/"dev")])
            for name,dest in (("fd","/proc/self/fd"),("stdin","/proc/self/fd/0"),("stdout","/proc/self/fd/1"),("stderr","/proc/self/fd/2")):(root/"dev"/name).symlink_to(dest)
            (root/"dev/shm").mkdir(mode=0o1777);(root/"dev/shm").chmod(0o1777)
            mount("proc-"+target,["mount","-t","proc","-o","nosuid,nodev,noexec","proc",str(root/"proc")],root/"proc");ephemeral.append(root/"proc")
            # AppArmor transitions and bwrap uid/gid maps require writable
            # per-process proc attributes; global kernel tunables stay read-only.
            for relative in ("sys","sysrq-trigger","irq","bus","fs"):
                guarded=root/"proc"/relative
                if guarded.exists():
                    mount("guard-proc-"+target+"-"+relative,["mount","--bind",str(guarded),str(guarded)],guarded)
                    call("readonly-proc-"+target+"-"+relative,["mount","-o","remount,bind,ro",str(guarded)])
                    ephemeral.append(guarded)
            if (root/"att/devlite-epiphany").exists():raise ValueError("Reserved disconnected prefix exists on disk")
            for relative in ("block","bus","class","dev","devices"):
                hardware=root/"sys"/relative;hardware.mkdir()
                mount("hardware-"+target+"-"+relative,["mount","--bind","/sys/"+relative,str(hardware)],hardware)
                call("readonly-hardware-"+target+"-"+relative,["mount","-o","remount,bind,ro",str(hardware)])
                ephemeral.append(hardware)
            home=root/"home/devlite";home.mkdir();os.chown(home,1000,1000)
            runtime=root/"run/user/1000";runtime.mkdir(parents=True);runtime.chmod(0o700);os.chown(runtime,1000,1000)
            passwd=(root/"etc/passwd").read_text();group=(root/"etc/group").read_text()
            if any(line.split(":")[2]=="1000" for line in passwd.splitlines() if len(line.split(":"))>2):raise ValueError("Unexpected preexisting user 1000")
            put(root,"etc/passwd",passwd+"devlite:x:1000:1000:Browser test:/home/devlite:/bin/bash\n")
            put(root,"etc/group",group+"devlite:x:1000:\n")
            probe=root/"run/devlite-probe";probe.mkdir()
            shutil.copyfile("/usr/bin/Xvfb",probe/"Xvfb");(probe/"Xvfb").chmod(0o755)
            put(root,"usr/share/devlite-os/browser-probe.html",HTML)
            env={"PATH":"/usr/sbin:/usr/bin:/sbin:/bin","HOME":"/home/devlite","USER":"devlite","LOGNAME":"devlite","LANG":"pt_BR.UTF-8","DISPLAY":":77","XDG_RUNTIME_DIR":"/run/user/1000","GDK_BACKEND":"x11","LIBGL_ALWAYS_SOFTWARE":"1"}
            xvfb=browser=None;runtime_log=runtime/"browser.log"
            try:
                with (attempt/"logs"/(target+"-xvfb.log")).open("w") as xlog,runtime_log.open("w") as blog:
                    os.chown(runtime_log,1000,1000);runtime_log.chmod(0o600)
                    xvfb=subprocess.Popen(["/run/devlite-probe/Xvfb",":77","-screen","0","1024x768x24","-nolisten","tcp","-ac"],env=env,stdin=subprocess.DEVNULL,stdout=xlog,stderr=xlog,preexec_fn=child_setup(root))
                    time.sleep(2)
                    if xvfb.poll() is not None:raise ValueError("Xvfb failed; inspect log")
                    browser=subprocess.Popen(["/usr/bin/aa-exec","-n",namespace_name,"-p","unconfined","--","/usr/bin/dbus-run-session","--","/usr/bin/aa-exec","-p","epiphany","--","/usr/bin/epiphany","--private-instance","file:///usr/share/devlite-os/browser-probe.html"],env=env,stdin=subprocess.DEVNULL,stdout=blog,stderr=blog,preexec_fn=child_setup(root,"/run/user/1000/browser.log"))
                    time.sleep(45)
                    states=[];process_diagnostics=[]
                    for p in Path("/proc").iterdir():
                        if not p.name.isdigit():continue
                        try:
                            process_diagnostics.append({"pid":int(p.name),"cmdline":(p/"cmdline").read_bytes().replace(b"\0",b" ").decode(errors="replace"),"wchan":(p/"wchan").read_text().strip(),"status":(p/"status").read_text(),"namespaces":{n:os.readlink(p/"ns"/n) for n in ("user","mnt","pid","net")}})
                            exe=os.readlink(p/"exe");label=(p/"attr/current").read_text().strip()
                        except (FileNotFoundError,ProcessLookupError):continue
                        except PermissionError as error:
                            process_diagnostics.append({"pid":int(p.name),"inspection_error":str(error)});continue
                        if "epiphany" in exe or "WebKit" in exe or "bwrap" in exe:states.append({"pid":int(p.name),"exe":exe,"label":label,"namespaces":{n:os.readlink(p/"ns"/n) for n in ("user","mnt","pid","net")},"status":(p/"status").read_text()})
                    save(stage/"processes.json",states)
                    save(stage/"process-diagnostics.json",process_diagnostics)
                    if browser.poll() is not None:raise ValueError("Browser exited; inspect log")
                    screenshot(attempt/(target+"-browser.png"),":77")
                    if not any("epiphany" in s["exe"] and namespace_name in s["label"] and "("+expected_mode+")" in s["label"] for s in states):raise ValueError("Confined Epiphany not running")
                    parent=next(s for s in states if "/usr/bin/epiphany" in s["exe"])
                    renderers=[s for s in states if "WebKitWebProcess" in s["exe"] and namespace_name in s["label"] and "("+expected_mode+")" in s["label"]]
                    if not any(native_sandbox_proven(parent,s) for s in renderers):
                        raise ValueError("Native WebKit sandbox namespaces/seccomp/capabilities not proven")
                    report["results"][target]={"states":states,"screenshot":str(attempt/(target+"-browser.png")),"visual_review_required":True}
            finally:
                stop(browser);stop(xvfb)
                # Only processes in the attested private PID namespace are visible.
                for p in Path("/proc").iterdir():
                    if p.name.isdigit() and int(p.name)!=os.getpid():
                        try:os.kill(int(p.name),signal.SIGKILL)
                        except ProcessLookupError:pass
                while True:
                    try:
                        if os.waitpid(-1,os.WNOHANG)[0]==0:break
                    except ChildProcessError:break
                if runtime_log.exists():shutil.copyfile(runtime_log,attempt/"logs"/(target+"-browser.log"))
            for p in reversed(ephemeral):unmount(p)
            unmount(root)
        report["status"]="diagnostic_only_not_approved" if diagnostic else "confined_processes_running_visual_review_required"
    except BaseException as error:
        report.update(status="blocked",error=str(error));raise
    finally:
        failures=[]
        try:
            journal=subprocess.run(["journalctl","-k","-n","500","--no-pager","-o","cat"],capture_output=True,text=True,timeout=15)
            (attempt/"logs/apparmor-denials.log").write_text("\n".join(line for line in journal.stdout.splitlines() if job.name.removeprefix("release-v5-") in line)+"\n")
        except Exception as e:report["kernel_log_error"]=str(e)
        if created_namespace:
            try:namespace.rmdir()
            except Exception as e:failures.append("namespace cleanup: "+str(e))
        try:
            if original_profiles is not None and (aa/"profiles").read_text()!=original_profiles:failures.append("Default namespace profile list changed")
        except Exception as e:failures.append(str(e))
        for p in reversed(mounts[:]):
            try:unmount(p)
            except Exception as e:failures.append(str(e))
        report["cleanup_errors"]=failures
        if failures:report["status"]="blocked"
        save(job/"browser-result.json",report)
    return report
