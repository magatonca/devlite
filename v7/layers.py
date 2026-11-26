"""Apply v7 changes to a disposable Base or Live overlay root."""
from pathlib import Path
import shutil

from pipeline.devlite.customize.installation import installed
from v5.image import confined
from v6.storage import require_space
from v7 import adminer, browser, desktop, seed

SEED = 'var/lib/snapd/seed'
REMOVED = {'epiphany-browser', 'epiphany-browser-data'}


def apply(root, target, directory, run, *, installer=None, local=False):
    """The caller supplies the offline chroot runner and owns overlay cleanup."""
    if target not in ('base', 'live') or (target == 'live') != bool(installer):
        raise ValueError('Expected Base or Live with the DevLite installer')
    if root == Path('/') or root.resolve() != root or not root.is_dir():
        raise ValueError('Expected an absolute disposable guest root')
    seed.validate(directory, installer, local=local)
    status = confined(root, 'var/lib/dpkg/status')
    before = installed(status.read_text())
    destination = confined(root, SEED)
    if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
        raise ValueError('Unexpected inherited Snap seed')
    if destination.parent.resolve() != destination.parent or not destination.parent.is_dir():
        raise ValueError('Unexpected snapd state directory')
    require_space(root, sum(item.stat().st_size for item in directory.rglob('*') if item.is_file()))
    staging = destination.with_name('seed.devlite-v7')
    shutil.copytree(directory, staging)
    seed.validate(staging, installer, local=local)
    browser.remove_epiphany(run)
    after = installed(status.read_text())
    if after != {name: version for name, version in before.items() if name not in REMOVED}:
        raise ValueError('Unexpected change in installed packages')
    if destination.exists():
        shutil.rmtree(destination)
    staging.rename(destination)
    browser.apply(root)
    desktop.apply(root, live=target == 'live')
    desktop.apply_devcontrol(root)
    adminer.apply(root, after, run)
