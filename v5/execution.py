"""Sealed v5 incremental jobs; immutable v4 lowers, private target-only writes."""
import hashlib
import ctypes
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
from pathlib import Path
from pipeline.devlite.runtime import owned_directory
from pipeline.devlite.structure import digest
from pipeline.devlite.customize.installation import verify_archives
from v5.image import payload_manifest
from pipeline.devlite.customize.isolation_validation import critical_files, cgroup_limits
from pipeline.devlite.public_attestation import seal
from pipeline.devlite.public_isolation import capture
from pipeline.devlite.minimal_root import EPOCH
ROOT = Path(__file__).resolve().parents[1]
RESERVE = 20 * 1024**3
# Incremental upper budget, not the old full-ext4-clone budget.
UPPER_LIMIT = 2 * 1024**3
LIMITS = {"memory_bytes":2684354560,"swap_bytes":1073741824,"tasks":128}
CASPER = ROOT / "work/modern-candidate-iso-2_8rwz4j/assembly-d84643em/result-tree/casper"
STACKS = {
 "base":("minimal.squashfs","minimal.visual.squashfs","minimal.visual.fix.squashfs"),
 "live":("minimal.squashfs","minimal.visual.squashfs","minimal.visual.live.squashfs","minimal.visual.live.fix.squashfs")}

def code_paths():
    # Seal all local Python dependencies, including transitive root imports.
    return sorted([p for p in (ROOT/"v5").rglob("*") if p.is_file() and "__pycache__" not in p.parts] +
                  list((ROOT/"pipeline").rglob("*.py")))


def save(path,data):
    path.write_text(json.dumps(data,sort_keys=True,indent=2)+"\n")

def prepare(plan_path):
    plan_path = Path(plan_path).resolve()
    if plan_path.parent.parent != ROOT / "work" or not plan_path.parent.name.startswith("v5-ssh-plan-"):
        raise ValueError("Unexpected plan")
    plan=json.loads(plan_path.read_text())
    if plan.get("installed") or plan.get("host_modified"):
        raise ValueError("Unexpected plan state")
    receipt=plan_path.parent / "acquisition.json"
    if receipt.is_symlink() or not receipt.is_file():raise ValueError("Verified archive receipt required")
    verify_archives(plan,plan_path.parent / "debs")
    work=owned_directory(ROOT / "work","release-v5-")
    evidence=json.loads((ROOT / "docs/v5/evidencias/sha256-camadas-v4.json").read_text())
    # Pin the exact already-audited lowers; worker rechecks on first use.
    lowers={str(CASPER/name):evidence[name]["actual"] for names in STACKS.values() for name in names}
    data={"schema":1,"job":str(work),"plan":str(plan_path),"plan_sha256":digest(plan_path),"acquisition_sha256":digest(receipt),
          "code_sha256":{str(p.relative_to(ROOT)):digest(p) for p in code_paths()},"payload_manifest":payload_manifest(ROOT/"v5/overlay"),
          "lowers":lowers,"stacks":STACKS,"host_critical_files":critical_files(),
          "host_namespaces":{n:os.readlink("/proc/self/ns/"+n) for n in ("mnt","pid","net","ipc","uts")},
          "limits":LIMITS,"reserve_bytes":RESERVE,"upper_limit_bytes":UPPER_LIMIT,
          "required_initial_bytes":RESERVE+2*UPPER_LIMIT+4*1024**3,
          "phase":"target-application-only","iso_generation":False}
    save(work / "contract.json",data)
    approval=digest(work / "contract.json")
    save(work / "command.json",{"argv":command(work,approval),"contract_sha256":approval,"executed":False})
    return work,approval

def read(job,approval):
    job=Path(job)
    if job.is_symlink() or job.resolve()!=job or job.parent!=ROOT / "work" or not re.fullmatch(r"release-v5-[a-z0-9_]{8}",job.name):
        raise ValueError("Unexpected v5 job")
    if digest(job / "contract.json")!=approval:raise ValueError("Contract changed")
    data=json.loads((job / "contract.json").read_text())
    if data["job"]!=str(job) or data["limits"]!=LIMITS or data["reserve_bytes"]!=RESERVE or data["upper_limit_bytes"]!=UPPER_LIMIT:
        raise ValueError("Contract policy differs")
    if data.get("payload_manifest")!=payload_manifest(ROOT/"v5/overlay"):raise ValueError("Payload permissions/content changed")
    paths=code_paths()
    if set(data["code_sha256"])!={str(p.relative_to(ROOT)) for p in paths}:raise ValueError("Code set changed")
    if any(digest(ROOT/p)!=h for p,h in data["code_sha256"].items()):raise ValueError("Sealed code changed")
    if digest(Path(data["plan"]))!=data["plan_sha256"]:raise ValueError("Plan changed")
    return job,data

def command(job,approval,browser=False):
    props=["MemoryMax=2684354560","MemorySwapMax=1073741824","CPUQuota=100%","TasksMax=128",
      "RuntimeMaxSec=10800","LimitCORE=0","TimeoutStopSec=60","KillMode=control-group","OOMPolicy=kill",
      "ProtectSystem=strict","ProtectHome=read-only","ReadWritePaths="+str(job),
      "PrivateNetwork=yes","PrivateMounts=yes","NoNewPrivileges=yes","ProtectKernelTunables=yes",
      "ProtectKernelModules=yes","ProtectControlGroups=yes","RestrictRealtime=yes",
      "RestrictAddressFamilies=AF_UNIX",
      "CapabilityBoundingSet=CAP_SYS_ADMIN CAP_SYS_CHROOT CAP_KILL CAP_CHOWN CAP_DAC_OVERRIDE CAP_DAC_READ_SEARCH CAP_FOWNER CAP_FSETID CAP_MKNOD CAP_SETFCAP CAP_SETPCAP CAP_SETUID CAP_SETGID"]
    if browser:
        props[-1]+=" CAP_MAC_ADMIN CAP_SYS_PTRACE CAP_NET_ADMIN"
        props[props.index("RestrictAddressFamilies=AF_UNIX")]="RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6 AF_NETLINK"
        props.append("ExecStopPost=/usr/bin/python3 -B -m v5.execution cleanup-browser "+str(job)+" "+approval)
    return ["sudo","systemd-run","--unit=devlite-public-"+job.name.removeprefix("release-"),"--wait","--pipe","--collect","--working-directory="+str(ROOT)]+[
      "--property="+p for p in props]+["/usr/bin/python3","-B","-m","v5.execution","outer",str(job),approval]

def outer(job,approval):
    job,data=read(job,approval)
    if os.geteuid()!=0:raise ValueError("Root isolated service required")
    if ctypes.CDLL(None).prctl(4,0,0,0,0):raise ValueError("Cannot protect supervisor memory")
    if shutil.disk_usage(job).free<data["required_initial_bytes"]:raise ValueError("Insufficient incremental budget")
    if critical_files()!=data["host_critical_files"]:raise ValueError("Host changed")
    report=capture(job,data,"systemd",approval_sha256=approval)
    os.chown(job,0,0);job.chmod(0o700)
    nonce=secrets.token_hex(32);fd,sha=seal(report,job,approval,nonce)
    try:
        args=["/usr/bin/unshare","--mount","--pid","--net","--ipc","--uts","--fork","--kill-child","--mount-proc",
              "/usr/bin/python3","-B","-m","v5.execution","inner",str(job),approval,str(fd),sha,nonce]
        return subprocess.call(args,pass_fds=(fd,),stdin=subprocess.DEVNULL)
    finally:
        os.close(fd)
        if data["phase"] in ("browser-runtime","browser-audit-only"):cleanup_browser(job,approval)

def inner(job,approval,fd,sha,nonce):
    job,data=read(job,approval)
    if ctypes.CDLL(None).prctl(4,0,0,0,0):raise ValueError("Cannot protect supervisor memory")
    current=Path("/proc/self/cgroup").read_text().strip().split("::",1)[1]
    cgroup_limits(Path("/sys/fs/cgroup")/current.lstrip("/"),LIMITS)
    capture(job,data,"unshare",approval_sha256=approval,inherited={"fd":int(fd),"sha256":sha,"nonce":nonce})
    if shutil.disk_usage(job).free<data["required_initial_bytes"]:raise ValueError("Insufficient space")
    if critical_files()!=data["host_critical_files"]:raise ValueError("Host changed")
    # unshare --mount-proc hides systemd's nested proc protection; restore it
    # before running target programs, without writing any kernel tunables.
    for path in ("/proc/sys", "/proc/sysrq-trigger"):
        subprocess.run(["mount","--bind",path,path],check=True)
        subprocess.run(["mount","-o","remount,bind,ro",path],check=True)
    if data["phase"] in ("browser-runtime","browser-audit-only"):
        from v5.browser_probe import run
    elif data["phase"]=="verified-layer-pack":
        from v5.layers import run
    elif data["phase"]=="target-application-only":
        from v5.worker import run
    else:raise ValueError("Unknown v5 phase")
    return run(job,data,approval)

def prepare_browser(source,policy,audit_only=False):
    if os.geteuid()!=0:raise ValueError("Root needed only to read protected COW receipts")
    from v5.browser_probe import inventory_digest
    source=Path(source);policy=Path(policy)
    if source.is_symlink() or source.resolve()!=source or source.parent!=ROOT/"work" or not source.name.startswith("release-v5-"):
        raise ValueError("Unexpected source")
    result_path=source/"application-result.json"
    if result_path.stat().st_uid!=0 or result_path.stat().st_mode&0o022:raise ValueError("Untrusted receipt")
    result=json.loads(result_path.read_text())
    if result["status"]!="ssh_services_applied_browser_policy_pending" or result["cleanup_errors"]:
        raise ValueError("Source not accepted for graphical test")
    if policy.is_symlink() or policy.resolve()!=policy or policy.parent!=ROOT/"work" or not policy.name.startswith("v5-browser-policy-"):
        raise ValueError("Unexpected profile source")
    names=subprocess.run(["apparmor_parser","-N","-K",str(policy/"epiphany")],capture_output=True,text=True,check=True).stdout.splitlines()
    if set(names)!={"epiphany"}:raise ValueError("Unexpected profile names")
    old=json.loads((source/"contract.json").read_text())
    job,_=prepare(Path(old["plan"]))
    shutil.copyfile(policy/"epiphany",job/"browser-profile.source")
    if audit_only:
        text=(job/"browser-profile.source").read_text().replace("flags=(attach_disconnected.path=", "flags=(complain,attach_disconnected.path=")
        (job/"browser-profile.source").write_text(text)
    subprocess.run(["apparmor_parser","-Q","-K","-n","devlite-v5-"+job.name.removeprefix("release-v5-"),"-o",str(job/"browser-profile.bin"),str(job/"browser-profile.source")],check=True)
    data=json.loads((job/"contract.json").read_text())
    data["phase"]="browser-audit-only" if audit_only else "browser-runtime"
    data["browser"]={"applied_job":str(source),"result_sha256":digest(result_path),
        "upper_inventory_sha256":{t:inventory_digest(source/"application"/t/"upper") for t in ("base","live")},
        "profile_binary_sha256":digest(job/"browser-profile.bin"),"test_namespace_only":True,
        "default_policy_replacement":False,"target_user_uid":1000,"xvfb_target_only":True}
    save(job/"contract.json",data);approval=digest(job/"contract.json")
    save(job/"command.json",{"argv":command(job,approval,browser=True),"contract_sha256":approval,"executed":False})
    return job,approval

def prepare_pack(source,browser):
    if os.geteuid()!=0:raise ValueError("Protected accepted receipts require root read")
    from v5.layers import require_browser
    from v5.browser_probe import inventory_digest
    source=Path(source);browser=Path(browser)
    for item in (source,browser):
        if item.is_symlink() or item.resolve()!=item or item.parent!=ROOT/"work" or not re.fullmatch(r"release-v5-[a-z0-9_]{8}",item.name):
            raise ValueError("Unexpected accepted job")
    require_browser(browser)
    accepted=source/"application-result.json"
    if accepted.stat().st_uid!=0 or accepted.stat().st_mode&0o022:raise ValueError("Untrusted application receipt")
    result=json.loads(accepted.read_text())
    if result["status"]!="ssh_services_applied_browser_policy_pending" or result["cleanup_errors"]:raise ValueError("Unaccepted source")
    browser_data=json.loads((browser/"contract.json").read_text())
    if browser_data["phase"]!="browser-runtime" or browser_data["browser"]["applied_job"]!=str(source):raise ValueError("Browser tested another source")
    if browser_data["browser"]["result_sha256"]!=digest(accepted):raise ValueError("Browser source receipt differs")
    inventories={t:inventory_digest(source/"application"/t/"upper") for t in ("base","live")}
    if inventories!=browser_data["browser"]["upper_inventory_sha256"]:raise ValueError("Browser source changed")
    old=json.loads((source/"contract.json").read_text())
    job,_=prepare(Path(old["plan"]))
    data=json.loads((job/"contract.json").read_text())
    data["phase"]="verified-layer-pack"
    data["pack"]={"applied_job":str(source),"browser_job":str(browser),"applied_result_sha256":digest(accepted),
        "browser_result_sha256":digest(browser/"browser-result.json"),"browser_review_sha256":digest(browser/"browser-visual-review.json"),
        "upper_inventory_sha256":inventories,"profile_sha256":digest(browser/"browser-profile.source")}
    save(job/"contract.json",data);approval=digest(job/"contract.json")
    save(job/"command.json",{"argv":command(job,approval),"contract_sha256":approval,"executed":False})
    return job,approval

def cleanup_browser(job,approval):
    # Also called by ExecStopPost if the worker/outer process is killed or OOMs.
    if os.geteuid()!=0:raise ValueError("Root isolated cleanup required")
    job,data=read(job,approval)
    if data["phase"] not in ("browser-runtime","browser-audit-only"):raise ValueError("Not a browser probe")
    planned=job/"namespace-planned.json"
    if not planned.exists():return
    marker=json.loads(planned.read_text());name="devlite-v5-"+job.name.removeprefix("release-v5-")
    if marker!={"namespace":name,"contract_sha256":approval} or planned.stat().st_uid!=0:
        raise ValueError("Untrusted namespace cleanup marker")
    path=job/"cleanup-securityfs"
    if path.is_symlink():raise ValueError("Unsafe cleanup mountpoint")
    path.mkdir(exist_ok=True)
    subprocess.run(["mount","-t","securityfs","-o","nosuid,nodev,noexec","securityfs",str(path)],check=True)
    try:
        namespace=path/"apparmor/policy/namespaces"/name
        if namespace.exists():namespace.rmdir()
        save(job/"namespace-cleanup.json",{"namespace":name,"absent":not namespace.exists(),"default_profiles_removed":False})
    finally:subprocess.run(["umount",str(path)],check=True)

if __name__=="__main__":
    if len(sys.argv)==4 and sys.argv[1]=="prepare-pack":
        print(*prepare_pack(Path(sys.argv[2]),Path(sys.argv[3])),sep="\n");raise SystemExit(0)
    if len(sys.argv)==4 and sys.argv[1]=="cleanup-browser":
        cleanup_browser(Path(sys.argv[2]),sys.argv[3]);raise SystemExit(0)
    if len(sys.argv)==4 and sys.argv[1] in ("prepare-browser","prepare-browser-audit"):
        print(*prepare_browser(Path(sys.argv[2]),Path(sys.argv[3]),audit_only=sys.argv[1]=="prepare-browser-audit"),sep="\n");raise SystemExit(0)
    if len(sys.argv)<4:raise SystemExit("Expected outer|inner job contract-sha256")
    phase,job,approval=sys.argv[1:4]
    if phase=="outer":raise SystemExit(outer(Path(job),approval))
    if phase=="inner" and len(sys.argv)==7:inner(Path(job),approval,*sys.argv[4:])
    else:raise SystemExit("Invalid execution phase")
