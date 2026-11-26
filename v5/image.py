"""Target-only v5 payload: must run inside the validated private mount namespace.

No host operations, package installation, or mount creation in this module.
The caller provides a disposable merged overlay root, never an accepted image.
"""
import hashlib
import json
import os
import stat
import subprocess
from pathlib import Path

UNITS = ("apache2.service", "mariadb.service", "mysql.service", "docker.service",
         "docker.socket", "containerd.service", "ssh.service", "ssh.socket", "iperf3.service")
DISABLED = tuple(u for u in UNITS if u != "mysql.service")

def confined(root, relative):
    root = Path(root)
    if root == Path("/") or not root.is_absolute() or root.is_symlink() or root.resolve() != root:
        raise ValueError("Disposable absolute root required")
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ValueError("Relative target path required")
    path = root / relative
    for parent in path.parents:
        if parent == root:
            break
        if parent.is_symlink():
            raise ValueError("Symlink ancestor: " + str(parent))
    return path

def put(root, relative, content, mode=0o644):
    path = confined(root, relative)
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError("Unexpected target: " + relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Replace rather than truncate a potentially shared inode in a COW target.
    temporary = path.with_name(path.name + ".v5-new")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(content)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()

def finalize(root, runner=subprocess.run):
    root = Path(root)
    identity = confined(root, "usr/share/devlite-os/identity.json")
    if json.loads(identity.read_text()).get("name") != "DevLite OS":
        raise ValueError("Wrong target identity")
    for unit in DISABLED:
        vendor = confined(root, "usr/lib/systemd/system/" + unit)
        if not vendor.exists():
            raise ValueError("Required installed unit absent: " + unit)
    removed = []
    for unit in UNITS:
        path = confined(root, "etc/systemd/system/" + unit)
        if path.is_symlink() and os.readlink(path) == "/dev/null":
            path.unlink()
            removed.append(str(path.relative_to(root)))
    # systemctl --root manipulates target unit-file links only, never host daemons.
    result = runner(["/usr/bin/systemctl", "--root=" + str(root), "disable", "--", *DISABLED],
                    capture_output=True, text=True, timeout=60, check=False,
                    env={"PATH":"/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL":"C"})
    if result.returncode:
        raise ValueError("Offline unit disable failed: " + result.stderr[:2000])
    for unit in UNITS:
        path = confined(root, "etc/systemd/system/" + unit)
        if path.is_symlink() and os.readlink(path) == "/dev/null":
            raise ValueError("Persistent mask: " + unit)
    for directory in ("etc/systemd/system", "usr/lib/systemd/system"):
        base = confined(root, directory)
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_symlink() and path.parent.name.endswith((".wants", ".requires")) and path.name in DISABLED:
                raise ValueError("Unexpected automatic activation link: " + str(path))
    # postinst may generate keys even with policy-rc.d. Remove only exact key names
    # from the disposable overlay. Never touch authorized_keys/user credentials.
    keys = []
    for algorithm in ("rsa", "ecdsa", "ed25519"):
        for suffix in ("", ".pub"):
            path = confined(root, "etc/ssh/ssh_host_" + algorithm + "_key" + suffix)
            if path.is_symlink() or (path.exists() and not path.is_file()):
                raise ValueError("Unexpected SSH host-key object")
            if path.exists():
                path.unlink()
                keys.append(str(path.relative_to(root)))
    return {"removed_factory_masks": removed, "removed_generated_host_keys": keys,
            "boot_disabled": list(DISABLED), "host_systemctl": False}

def payload_manifest(source):
    result = {}
    for path in sorted(Path(source).rglob("*")):
        if path.is_symlink():
            raise ValueError("Symlink payload forbidden")
        if path.is_file():
            result[str(path.relative_to(source))] = {
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "mode": stat.S_IMODE(path.stat().st_mode)}
    return result
