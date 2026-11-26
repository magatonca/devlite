"""Resolve SSH against pinned v4 status and authenticated Ubuntu indexes; no install."""
import hashlib
import json
import os
import subprocess
from pathlib import Path
from pipeline.devlite.customize.installation import snapshot_indexes, resolve_target, compatibility, installed
from pipeline.devlite.runtime import owned_directory
ROOT = Path(__file__).resolve().parents[1]
CASPER = ROOT / "work/modern-candidate-iso-2_8rwz4j/assembly-d84643em/result-tree/casper"

def prepare():
    evidence = json.loads((ROOT / "docs/v5/evidencias/sha256-camadas-v4.json").read_text())
    work = owned_directory(ROOT / "work", "v5-ssh-plan-")
    for folder in ("empty", "lists", "cache/archives/partial", "logs"):
        (work / folder).mkdir(parents=True, exist_ok=True)
    for name in ("empty.conf", "preferences", "sources.list"):
        (work / name).write_text("")
    indexes, blockers = snapshot_indexes(work)
    if blockers:
        (work / "blockers.json").write_text(json.dumps(blockers, indent=2))
        raise ValueError("Authenticated indexes not current; see " + str(work))
    targets = {}
    for target, layer in (("base", "minimal.squashfs"), ("live", "minimal.visual.live.squashfs")):
        source = CASPER / layer
        with source.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != evidence[layer]["actual"]:
            raise ValueError("Source layer changed")
        result = subprocess.run(["unsquashfs", "-cat", str(source), "var/lib/dpkg/status"],
                                capture_output=True, text=True, check=True, timeout=120)
        targets[target] = resolve_target(work, target, result.stdout, ["openssh-server"],
                                         {"snapd", "cloud-init", "apparmor", "ufw"})
        # Adding a server does not authorize unrelated upgrades.
        previous = installed(result.stdout)
        upgrades = [c["package"] for c in targets[target]["changes"] if c["package"].split(":")[0] in previous]
        if upgrades:
            raise ValueError("Review required for existing package upgrades: " + str(upgrades))
    plan = {"targets":targets, "indexes":indexes, "compatibility":compatibility(targets["base"], targets["live"]),
            "installed":False, "downloaded":False, "host_modified":False}
    path = work / "plan.json"; path.write_text(json.dumps(plan, indent=2)+"\n")
    print(path)
    print(json.dumps({name:{"new_packages":len(target["changes"]), "download_bytes":target["download_bytes"],
                             "gross_installed_bytes":target["gross_installed_bytes"]} for name,target in targets.items()}, indent=2))
    return path
if __name__ == "__main__": prepare()
