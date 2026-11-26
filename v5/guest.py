"""Runs only after chroot, private /run,/dev,/proc and irreversible capability drop."""
import json
import os
import subprocess
import sys
sys.path.insert(0,"/run/devlite-v5")
import guest_runner as reused
from pathlib import Path
ENV={"PATH":"/usr/sbin:/usr/bin:/sbin:/bin","LC_ALL":"C","DEBIAN_FRONTEND":"noninteractive","DEBCONF_NONINTERACTIVE_SEEN":"true"}

def call(args):
    p=subprocess.run(args,env=ENV,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=600)
    print(json.dumps({"argv":args,"returncode":p.returncode,"stdout":p.stdout,"stderr":p.stderr}),flush=True)
    if p.returncode:raise ValueError("Guest command failed")
    return p.stdout+p.stderr

def main():
    request=json.loads(Path("/run/devlite-v5/request.json").read_text())
    if request["target"] not in ("base","live"):raise ValueError("Wrong target")
    names=request["archives"]
    if len(names)!=2 or any(Path(n).name!=n or not n.endswith("_amd64.deb") for n in names):raise ValueError("Archive operands invalid")
    conf=Path("/run/devlite-v5/apt.conf")
    os.environ["APT_CONFIG"]=str(conf);ENV["APT_CONFIG"]=str(conf)
    apt=["/usr/bin/apt-get","--no-download","--no-remove","--no-install-recommends","-y"]
    operands=["/run/devlite-v5/debs/"+n for n in names]
    simulated=call(apt+["-s","install",*operands])
    # Only exact two pinned new packages, never opportunistic upgrades/removals.
    from_guest=[]
    for line in simulated.splitlines():
        if line.startswith("Remv "):raise ValueError("Unexpected removal")
        if line.startswith("Inst "):
            fields=line.split();from_guest.append(fields[1])
            if fields[1] not in request["packages"] or "[" in fields[2]:raise ValueError("Unexpected guest transaction")
    if sorted(from_guest)!=sorted(request["packages"]):raise ValueError("Guest simulation differs")
    # Reuse the already-tested epoch-aware archive cache and dpkg preflight.
    # Only import its functions: legacy main() and mask expectations never run.
    reused.run=call
    reused.install_local(operands,request["changes"],["--no-download","--no-remove","--no-install-recommends"])
    if call(["/usr/bin/dpkg","--audit"]).strip():raise ValueError("dpkg audit not empty")
    call(apt+["-s","check"])
    call(["/usr/sbin/sshd","-t"])
    output=call(["/usr/sbin/sshd","-T"])
    settings=dict(line.split(" ",1) for line in output.splitlines() if " " in line)
    if settings.get("permitrootlogin")!="no" or settings.get("permitemptypasswords")!="no":raise ValueError("SSH effective policy differs")
    Path("/run/devlite-v5/guest-passed.json").write_text(json.dumps({"passed":True,"sshd":settings}))
if __name__=="__main__":main()
