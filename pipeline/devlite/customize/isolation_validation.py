"""Diagnóstico somente leitura e checkpoints do hospedeiro; sem namespaces/mounts."""
import hashlib
import os
import platform
import shutil
from datetime import datetime,timezone
from pathlib import Path

TOOLS=('systemd-run','systemctl','unshare','mount','umount','mkfs.ext4','e2fsck','cp','gpgv','python3')


def digest(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest()


def critical_files():
    paths=[Path(p) for p in ('/var/lib/dpkg/status','/var/lib/apt/extended_states','/etc/passwd','/etc/group','/etc/fstab','/etc/apt/sources.list')]
    paths += list(Path('/etc/apt/sources.list.d').glob('*'))
    return {str(p):digest(p) for p in paths if p.is_file() and not p.is_symlink()}


def loop_backings():
    result={}
    for path in Path('/sys/block').glob('loop*/loop/backing_file'):
        try: result[path.parents[1].name]=path.read_text().strip()
        except OSError as error: result[path.parents[1].name]={'unreadable':type(error).__name__}
    return result


def collect(root):
    usage=shutil.disk_usage(root)
    memory={line.split(':')[0]:int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.split(':')[0] in ('MemTotal','MemAvailable','SwapTotal','SwapFree')}
    kernel=platform.release()
    modules=list(Path('/lib/modules',kernel).glob('kernel/fs/overlayfs/overlay.ko*'))
    return {'captured_utc':datetime.now(timezone.utc).isoformat(),'uid':os.getuid(),'kernel':kernel,
            'disk':{'total_bytes':usage.total,'free_bytes':usage.free,'probe_budget_bytes':56*1024**3,'sufficient':usage.free>=56*1024**3},
            'memory':memory,'pid1':Path('/proc/1/comm').read_text().strip(),
            'namespaces':{n:os.readlink('/proc/self/ns/'+n) for n in ('mnt','pid','net','ipc','uts','cgroup')},
            'controllers':Path('/sys/fs/cgroup/cgroup.controllers').read_text().split(),
            'filesystems':Path('/proc/filesystems').read_text().split(),
            'overlay_module_files':[str(p) for p in modules],
            'tools':{name:shutil.which(name) for name in TOOLS},'critical_files_sha256':critical_files(),
            'mountinfo_sha256':digest(Path('/proc/self/mountinfo')),'loop_backings':loop_backings(),
            'probe_executed':False,'compatibility':'indicadores por leitura; namespaces/cgroups/loops não exercitados'}


def compare(before,after):
    differences={p:{'before':before['critical_files_sha256'].get(p),'after':after['critical_files_sha256'].get(p)} for p in before['critical_files_sha256'].keys()|after['critical_files_sha256'].keys() if before['critical_files_sha256'].get(p)!=after['critical_files_sha256'].get(p)}
    return {'critical_files_unchanged':not differences,'differences':differences,'same_mount_namespace':before['namespaces']['mnt']==after['namespaces']['mnt'],'mountinfo_unchanged':before['mountinfo_sha256']==after['mountinfo_sha256'],'loop_backings_unchanged':before.get('loop_backings')==after.get('loop_backings')}


def cgroup_limits(group,expected):
    values={name:(group/name).read_text().strip() for name in ('memory.max','memory.swap.max','pids.max','cpu.max')}
    for key,field in (('memory.max','memory_bytes'),('memory.swap.max','swap_bytes'),('pids.max','tasks')):
        if values[key]!=str(expected[field]): raise ValueError('Limite cgroup não aplicado: '+key)
    quota,period=values['cpu.max'].split()
    if quota=='max' or int(quota)!=int(period): raise ValueError('CPUQuota 100% não aplicado')
    return values
