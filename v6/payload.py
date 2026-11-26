"""Apply the v6 text assets to the disposable guest overlay."""
import os
import stat
from pathlib import Path

from v5.image import confined, put

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "v6/overlay"
DEVCONTROL = "usr/lib/devlite/devcontrol"
RETIRED = (
    "usr/share/applications/devlite-control.desktop",
    "usr/bin/devlite-control",
    "usr/libexec/devlite-service-control",
    "usr/libexec/devlite-services-v5",
    "usr/share/polkit-1/actions/org.devlite.services.policy",
    "usr/share/polkit-1/actions/org.devlite.v5.services.policy",
)
HELPER = "usr/libexec/devlite-services-v6"
POLICY = "usr/share/polkit-1/actions/org.devlite.v6.services.policy"
# Guest metadata for the two privileged entry points is fixed independently of
# the checkout umask. Other payload files retain their existing install modes.
PRIVILEGED_MODES = {HELPER: 0o755, POLICY: 0o644}
APACHE_LINK = "etc/apache2/conf-enabled/devlite-servername.conf"


def prepare_parent(root, relative):
    path = confined(root, relative)
    for parent in reversed(path.parents):
        if parent == root or not parent.is_relative_to(root):
            continue
        if not parent.exists():
            parent.mkdir()
            parent.chmod(0o755)
    return path


def apply(root, target):
    if target not in {"base", "live"}:
        raise ValueError("Target must be base or live")
    written = []
    for relative in RETIRED:
        path = confined(root, relative)
        if path.exists() or path.is_symlink():
            if path.is_symlink() or not path.is_file():
                raise ValueError(f"Unexpected inherited DevControl path: {relative}")
            path.unlink()
    for source in sorted(OVERLAY.rglob("*")):
        relative = source.relative_to(OVERLAY).as_posix()
        if relative in RETIRED:
            continue
        if target == "base" and relative.startswith("usr/share/desktop-provision/"):
            continue
        if source.is_dir() and not source.is_symlink():
            continue
        prepare_parent(root, relative)
        if source.is_symlink():
            link = "../conf-available/devlite-servername.conf"
            if relative != APACHE_LINK or os.readlink(source) != link:
                raise ValueError(f"Unexpected overlay symlink: {relative}")
            path = confined(root, relative)
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.is_symlink() or os.readlink(path) != link:
                path.symlink_to(link)
        elif source.is_file():
            mode = PRIVILEGED_MODES.get(relative, stat.S_IMODE(source.stat().st_mode))
            put(root, relative, source.read_text(), mode)
        else:
            continue
        written.append(relative)
    modules = [ROOT / "v5/devcontrol/collector.py",
               *sorted((ROOT / "v6/devcontrol").glob("*.py"))]
    for source in modules:
        relative = f"{DEVCONTROL}/{source.name}"
        prepare_parent(root, relative)
        put(root, relative, source.read_text())
        written.append(relative)
    # On the image all import and authorization paths must be controlled by root.
    if os.geteuid() == 0:
        for name in (HELPER, POLICY, f"{DEVCONTROL}/services.py", f"{DEVCONTROL}/app.py",
                     f"{DEVCONTROL}/collector.py", f"{DEVCONTROL}/metrics.py"):
            path = confined(root, name)
            for item in (path, *path.parents):
                info = item.lstat()
                if item.is_symlink() or info.st_uid != 0 or info.st_mode & 0o022:
                    raise ValueError(f"Untrusted DevControl path: {item}")
                if item == root:
                    break
    relative = "etc/apparmor.d/epiphany"
    prepare_parent(root, relative)
    put(root, relative, (ROOT / "config/v6/epiphany.apparmor").read_text())
    written.append(relative)
    return written
