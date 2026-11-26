"""COW v5 target application, using existing isolation attestation and service guard."""
import ctypes
import json
import os
import resource
import shutil
import signal
import stat
import subprocess
import time
from pathlib import Path
from pipeline.devlite.customize.executor_worker import service_guard, restrict_caps
from pipeline.devlite.customize.installation import installed, verify_archives
from pipeline.devlite.structure import digest
from pipeline.devlite.runtime import Runner
from pipeline.devlite.minimal_root import EPOCH, allocated_usage
from v5.image import put, finalize, payload_manifest, confined
from v5.execution import ROOT, CASPER, STACKS, RESERVE, UPPER_LIMIT, save
APT_CONF = '''Dir::Etc::parts "/run/devlite-v5/empty";
Dir::Etc::main "/run/devlite-v5/empty.conf";
Dir::Etc::sourcelist "/run/devlite-v5/empty.conf";
Dir::Etc::sourceparts "/run/devlite-v5/empty";
Dir::State::lists "/run/devlite-v5/lists";
Dir::State::extended_states "/var/lib/apt/extended_states";
Dir::Cache::pkgcache "";
Dir::Cache::srcpkgcache "";
Dir::Cache::archives "/var/cache/apt/archives";
Dir::Log "/var/log/apt";
APT::Install-Recommends "false";
APT::Install-Suggests "false";
APT::Get::AllowUnauthenticated "false";
DPkg::Use-Pty "false";
'''

def apply_payload(root):
    # Every ancestor of the authenticated helper/module/policy must be root-only writable.
    for name in (".","usr","usr/lib","usr/lib/devlite","usr/lib/devlite/devcontrol","usr/libexec","usr/share","usr/share/polkit-1","usr/share/polkit-1/actions"):
        path=confined(root,name)
        if path.is_symlink():raise ValueError("Helper path symlink")
        path.mkdir(exist_ok=True,parents=True);os.chown(path,0,0);path.chmod(0o755)
    payload=ROOT / "v5/overlay"
    before=payload_manifest(payload)
    for name,item in before.items():
        source=payload / name
        put(root,name,source.read_text(),item["mode"])
    for name in ("app.py","collector.py","services.py"):
        put(root,"usr/lib/devlite/devcontrol/"+name,(ROOT / "v5/devcontrol" / name).read_text())
    if payload_manifest(payload)!=before:raise ValueError("Payload changed during application")
    return before

def live_allocated_usage(root):
    """Monitor only: ENOENT is normal while maintscripts rename/remove files.

    The real filesystem free-space gate remains authoritative, including open
    unlinked files. Final stable inventories still fail on unexpected errors.
    """
    total=0;seen=set()
    def traversal_error(error):
        if not isinstance(error,FileNotFoundError):raise error
    for directory,dirs,files in os.walk(root,followlinks=False,onerror=traversal_error):
        for path in [Path(directory),*(Path(directory)/n for n in files),*(Path(directory)/n for n in dirs)]:
            try:info=path.lstat()
            except FileNotFoundError:continue
            key=(info.st_dev,info.st_ino)
            if key not in seen:seen.add(key);total+=info.st_blocks*512
    return total

def guest(root,log,job,upper):
    # Prevent child root from accessing supervisor file descriptors/root via proc.
    if ctypes.CDLL(None,use_errno=True).prctl(4,0,0,0,0):raise OSError("Cannot protect supervisor")
    pid=os.fork()
    if pid==0:
        try:
            os.setsid()
            fd=os.open(log,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            os.dup2(fd,1);os.dup2(fd,2)
            os.chroot(root);os.chdir("/");restrict_caps()
            os.closerange(3,resource.getrlimit(resource.RLIMIT_NOFILE)[0])
            os.execve("/usr/bin/python3",["python3","-I","/run/devlite-v5/guest.py"],{"PATH":"/usr/sbin:/usr/bin:/sbin:/bin","LC_ALL":"C"})
        except BaseException:
            import traceback
            traceback.print_exc()
            os._exit(120)
    deadline=time.monotonic()+1200
    failure=None;reaped=False
    try:
        while True:
            finished,status=os.waitpid(pid,os.WNOHANG)
            if finished:reaped=True;break
            if time.monotonic()>deadline or shutil.disk_usage(job).free<RESERVE or live_allocated_usage(upper)>UPPER_LIMIT:
                failure="Guest time/storage budget exceeded"
                break
            time.sleep(1)
        if failure or not os.WIFEXITED(status) or os.WEXITSTATUS(status):
            raise ValueError(failure or "Isolated guest failed; inspect guest log")
    finally:
        # No mount cleanup while an installation process is still running.
        try:os.killpg(pid,signal.SIGKILL)
        except ProcessLookupError:pass
        if not reaped:os.waitpid(pid,0)
        while True:
            try:
                if os.waitpid(-1,os.WNOHANG)[0]==0:break
            except ChildProcessError:break

    return json.loads((root / "run/devlite-v5/guest-passed.json").read_text())

def run(job,data,approval):
    plan_path=Path(data["plan"]);plan=json.loads(plan_path.read_text())
    cache=plan_path.parent / "debs";verify_archives(plan,cache)
    receipt=plan_path.parent / "acquisition.json"
    if digest(receipt)!=data["acquisition_sha256"]:raise ValueError("Acquisition receipt changed")
    attempt=job / "application"
    attempt.mkdir(mode=0o700);(attempt / "logs").mkdir()
    runner=Runner(attempt / "logs",EPOCH);runner.env.pop("SOURCE_DATE_EPOCH",None)
    mounts=[];report={"status":"applying","results":{},"source_images_modified":False,"iso_generated":False}
    def call(label,args):
        if shutil.disk_usage(job).free<RESERVE:raise ValueError("20 GiB reserve reached")
        runner.run(label,args)
    def mount(label,args,path):
        call(label,args);mounts.append(path)
    def umount(path):
        runner.run("unmount-"+str(len(mounts)),["umount",str(path)]);mounts.remove(path)
    try:
        call("private",["mount","--make-rprivate","/"])
        lowers={}
        for name in sorted({n for names in STACKS.values() for n in names}):
            source=CASPER/name
            if source.is_symlink() or digest(source)!=data["lowers"][str(source)]:raise ValueError("Pinned v4 lower changed")
            path=attempt/("lower-"+name);path.mkdir()
            mount("lower-"+name,["mount","-t","squashfs","-o","loop,ro,nodev,nosuid",str(source),str(path)],path)
            lowers[name]=path
        for target in ("base","live"):
            stage=attempt/target;stage.mkdir()
            upper=stage/"upper";upper.mkdir();work=stage/"work";work.mkdir();root=stage/"root";root.mkdir()
            options="lowerdir="+":".join(str(lowers[n]) for n in reversed(STACKS[target]))+",upperdir="+str(upper)+",workdir="+str(work)+",index=off,metacopy=off,redirect_dir=off,xino=off"
            mount("overlay-"+target,["mount","-t","overlay","overlay","-o",options,str(root)],root)
            before=(root / "var/lib/dpkg/status").read_text()
            import hashlib
            if hashlib.sha256(before.encode()).hexdigest()!=plan["targets"][target]["status_sha256"]:raise ValueError("Composed target package status differs")
            apply_payload(root)
            ephemeral=[]
            for directory in ("run","tmp","var/tmp","dev","sys"):
                path=root/directory
                if not path.is_dir() or path.is_symlink():raise ValueError("Runtime mount target invalid")
                mount("tmpfs-"+target+"-"+directory.replace("/","-"),["mount","-t","tmpfs","-o","nodev,nosuid,mode=0755,size=128m","tmpfs",str(path)],path)
                ephemeral.append(path)
                if directory in ("tmp","var/tmp"):path.chmod(0o1777)
            for name,minor in (("null",3),("zero",5),("random",8),("urandom",9)):
                os.mknod(root/"dev"/name,stat.S_IFCHR|0o666,os.makedev(1,minor))
            for name,target_fd in (("fd","/proc/self/fd"),("stdin","/proc/self/fd/0"),("stdout","/proc/self/fd/1"),("stderr","/proc/self/fd/2")):
                (root/"dev"/name).symlink_to(target_fd)
            (root/"dev/shm").mkdir(mode=0o1777)
            # Device nodes must work; remount only private /dev without nodev.
            call("dev-options-"+target,["mount","-o","remount,dev,nosuid,mode=0755",str(root/"dev")])
            proc=root/"proc"
            mount("proc-"+target,["mount","-t","proc","-o","ro,nosuid,nodev,noexec","proc",str(proc)],proc);ephemeral.append(proc)
            run=root/"run/devlite-v5";run.mkdir();(run/"empty").mkdir();(run/"lists").mkdir();(run/"empty.conf").write_text("")
            (run/"guest_runner.py").write_text((ROOT/"pipeline/devlite/customize/guest_runner.py").read_text())
            (run/"apt.conf").write_text(APT_CONF);(run/"guest.py").write_text((ROOT/"v5/guest.py").read_text())
            (run/"debs").mkdir()
            # Copy tiny verified archives into tmpfs; target cannot write archive cache.
            for file in cache.glob("*.deb"):shutil.copyfile(file,run/"debs"/file.name)
            changes=plan["targets"][target]["changes"]
            save(run/"request.json",{"target":target,"archives":[Path(c["filename"]).name for c in changes],"packages":[c["package"] for c in changes],"changes":changes})
            (root/"run/sshd").mkdir();(root/"run/lock").mkdir(mode=0o1777)
            with service_guard(root):
                guest_report=guest(root,attempt/"logs"/(target+"-guest.jsonl"),job,upper)
            for path in reversed(ephemeral):umount(path)
            final=finalize(root)
            versions=installed((root/"var/lib/dpkg/status").read_text())
            if versions!=plan["targets"][target]["final_versions"]:raise ValueError("Final package database differs")
            if list((root/"etc/ssh").glob("ssh_host_*_key")):raise ValueError("Private host key remains")
            save(stage/"policy.json",final)
            save(stage/"packages.json",versions)
            report["results"][target]={"policy":final,"guest_passed":guest_report["passed"],"upper_allocated_bytes":allocated_usage(upper),"package_count":len(versions)}
            umount(root)
        report["status"]="ssh_services_applied_browser_policy_pending"
    except BaseException as error:
        report.update(status="quarantined",error=str(error));raise
    finally:
        errors=[]
        for path in reversed(mounts[:]):
            try:umount(path)
            except Exception as error:errors.append(str(error))
        report["cleanup_errors"]=errors
        if errors:report["status"]="quarantined"
        save(job/"application-result.json",report)
    return report
