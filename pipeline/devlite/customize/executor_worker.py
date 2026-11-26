"""Worker de namespace. Não invocar diretamente; exige tentativa root e revisão."""
import argparse
import ctypes
import contextlib
import json
import os
import resource
import shutil
import stat
import subprocess
import sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from pipeline.devlite.customize.executor_contract import confined,protected_inventory,require_equal,assert_final,LIMITS
from pipeline.devlite.customize.installation import sha,audit_database
from pipeline.devlite.customize.service_profiles import FILES,MASKS,DEBCONF
from pipeline.devlite.customize.manifest import SpecError
from pipeline.devlite.customize.isolation_validation import cgroup_limits

ENV={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LC_ALL':'C'}
KEEP_CAPS={0,1,3,4,5,6,7,8,31}


def call(args):
    subprocess.run(args,env=ENV,stdin=subprocess.DEVNULL,check=True,close_fds=True)


def safe(root,relative,directory=False):
    path=root/relative
    if '..' in Path(relative).parts or Path(relative).is_absolute(): raise SpecError('Path inseguro')
    for parent in path.parents:
        if parent==root: break
        if parent.is_symlink(): raise SpecError('Ancestral symlink no alvo: '+str(path))
    if path.is_symlink(): raise SpecError('Destino symlink inesperado: '+str(path))
    if directory: path.mkdir(parents=True,exist_ok=True)
    else: path.parent.mkdir(parents=True,exist_ok=True)
    return path


def runtime_directories(root):
    # /var/lock é link para /run/lock; o tmpfs novo não recebe systemd-tmpfiles.
    for name in ('var/lib/devlite-executor/lists/partial','run/apache2','run/lock'):
        path=safe(root,name,True)
        if name=='run/lock': path.chmod(0o1777)


def restrict_caps():
    libc=ctypes.CDLL(None,use_errno=True)
    # Bounding set não recuperável após exec; remove SYS_ADMIN, SYS_CHROOT, PTRACE, MKNOD etc.
    last=int(Path('/proc/sys/kernel/cap_last_cap').read_text())
    if last>63: raise SpecError('Kernel possui capabilities não suportadas')
    for cap in range(last+1):
        if cap not in KEEP_CAPS and libc.prctl(24,cap,0,0,0)!=0: raise OSError(ctypes.get_errno(),'PR_CAPBSET_DROP')
    if libc.prctl(38,1,0,0,0)!=0: raise OSError(ctypes.get_errno(),'NO_NEW_PRIVS')
    class Header(ctypes.Structure): _fields_=[('version',ctypes.c_uint32),('pid',ctypes.c_int)]
    class Data(ctypes.Structure): _fields_=[('effective',ctypes.c_uint32),('permitted',ctypes.c_uint32),('inheritable',ctypes.c_uint32)]
    header=Header(0x20080522,0);data=(Data*2)()
    for cap in KEEP_CAPS:
        data[cap//32].effective |= 1<<(cap%32);data[cap//32].permitted |= 1<<(cap%32)
    if libc.capset(ctypes.byref(header),ctypes.byref(data))!=0: raise OSError(ctypes.get_errno(),'capset')
    os.setgroups([])


def apt_config():
    return '''Dir::Etc::parts "/run/devlite/empty";
Dir::Etc::main "/run/devlite/empty.conf";
Dir::Etc::sourcelist "/run/devlite/sources.list";
Dir::Etc::sourceparts "/run/devlite/empty";
Dir::Etc::preferences "/run/devlite/empty.conf";
Dir::Etc::preferencesparts "/run/devlite/empty";
Dir::State::status "/var/lib/dpkg/status";
Dir::State::lists "/var/lib/devlite-executor/lists";
Dir::Cache::pkgcache "";
Dir::Cache::srcpkgcache "";
Dir::Cache::archives "/var/cache/apt/archives";
DPkg::Use-Pty "false";
APT::Architecture "amd64";
APT::Architectures { "amd64"; };
APT::Install-Recommends "false";
APT::Install-Suggests "false";
APT::Get::Download "false";
DPkg::Options { "--force-confold"; };
'''


def profiles():
    for name,value in FILES.items():
        path=safe(Path('/'),name);path.write_text(value);path.chmod(0o644)
    for folder in Path('/etc/php').glob('*/cli/conf.d'):
        version=folder.parts[3]
        if not all(c.isdigit() or c=='.' for c in version): raise SpecError('Versão PHP inesperada')
        for sapi in ('cli','apache2'):
            destination=Path('/etc/php')/version/sapi/'conf.d'
            if destination.is_dir():
                path=safe(Path('/'),str((destination/'99-devlite.ini').relative_to('/')))
                path.write_text(FILES['usr/share/devlite-os/profiles/php-devlite.ini'])
    enabled=safe(Path('/'),'etc/apache2/conf-enabled/devlite-local.conf')
    if enabled.exists(): raise SpecError('Conf Apache já existe')
    enabled.symlink_to('../conf-available/devlite-local.conf')


def run_guest(validate_only=False,probe=False):
    if ctypes.CDLL(None,use_errno=True).prctl(4,0,0,0,0)!=0:
        raise SpecError('Falha ao proteger memória/fds do supervisor')
    pid=os.fork()
    if pid==0:
        try:
            restrict_caps()
            os.closerange(3,resource.getrlimit(resource.RLIMIT_NOFILE)[0])
            os.execve('/usr/bin/python3',['python3','-I','/run/devlite/guest.py']+(['--validate-only'] if validate_only else [])+(['--probe-only'] if probe else []),ENV)
        except BaseException:
            os._exit(120)
    _,status=os.waitpid(pid,0)
    if not os.WIFEXITED(status) or os.WEXITSTATUS(status): raise SpecError('Instalação/auditoria isolada falhou')
    while True:
        try:
            child,_=os.waitpid(-1,os.WNOHANG)
            if child==0: break
        except ChildProcessError: break
    # /proc foi montado para este PID namespace e ambos os processos já fizeram chroot.
    unexpected=[p.name for p in Path('/proc').iterdir() if p.name.isdigit() and int(p.name)!=os.getpid()]
    if unexpected: raise SpecError('Processos remanescentes: '+','.join(unexpected))


@contextlib.contextmanager
def service_guard(root):
    policy=safe(root,'usr/sbin',True)/'policy-rc.d'
    backup=safe(root,'var/lib/devlite-executor/policy.original')
    if backup.exists() or backup.is_symlink(): raise SpecError('Backup de policy já existe')
    metadata=policy.lstat() if policy.exists() or policy.is_symlink() else None
    attrs={k:os.getxattr(policy,k,follow_symlinks=False) for k in os.listxattr(policy,follow_symlinks=False)} if metadata else {}
    if metadata:
        if not (stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode)): raise SpecError('Policy não é arquivo/link')
        shutil.copy2(policy,backup,follow_symlinks=False)
        policy.unlink()
    try:
        policy.write_text('#!/bin/sh\nexit 101\n');policy.chmod(0o755)
        yield
    finally:
        if policy.exists() or policy.is_symlink(): policy.unlink()
        if metadata:
            shutil.copy2(backup,policy,follow_symlinks=False)
            os.chown(policy,metadata.st_uid,metadata.st_gid,follow_symlinks=False)
            for key,value in attrs.items(): os.setxattr(policy,key,value,follow_symlinks=False)
            os.utime(policy,ns=(metadata.st_atime_ns,metadata.st_mtime_ns),follow_symlinks=False)
            backup.unlink()


def inside(root,target,plan,host_namespaces,probe=False,host_sentinel=None,actual_limits=None):
    runtime=safe(root,'run/devlite',True)
    shutil.copyfile(ROOT/'pipeline/devlite/customize/guest_runner.py',runtime/'guest.py')
    (runtime/'transaction.json').write_text(json.dumps({'changes':plan['targets'][target]['changes'],'requested':plan['requested_ubuntu'],'host_namespaces':host_namespaces,
                                                      'file_bytes':LIMITS['file_bytes'],'masks':MASKS,'host_sentinel':host_sentinel['path'],'allowed_caps':sorted(KEEP_CAPS)}))
    (runtime/'apt.conf').write_text(apt_config());(runtime/'debconf.selections').write_text(DEBCONF)
    for file in ('empty.conf','sources.list'): (runtime/file).write_text('')
    (runtime/'empty').mkdir()
    call(['mount','-o','remount,ro,nosuid,nodev',str(runtime)])
    # Pai também entra no alvo antes de criar o filho: /proc/1/root nunca aponta para o host.
    os.closerange(3,resource.getrlimit(resource.RLIMIT_NOFILE)[0])
    os.chroot(root);os.chdir('/')
    before=protected_inventory(Path('/'))
    if sha(Path('/var/lib/dpkg/status'))!=plan['targets'][target]['status_sha256']: raise SpecError('Banco fonte não corresponde ao plano')
    if probe:
        run_guest(probe=True)
        require_equal(before,protected_inventory(Path('/')))
        if sha(Path('/var/lib/dpkg/status'))!=plan['targets'][target]['status_sha256']: raise SpecError('Probe alterou dpkg')
        print('DEVLITE_RESULT='+json.dumps({'target':target,'status':'probe_validated','actual_cgroup_limits':actual_limits}),flush=True)
        return
    with service_guard(Path('/')):
        for unit in MASKS:
            path=Path('/etc/systemd/system')/unit
            if path.is_symlink() and os.readlink(path)=='/dev/null': continue
            if path.exists() or path.is_symlink(): raise SpecError('Máscara substituiria unidade existente: '+unit)
            path.parent.mkdir(parents=True,exist_ok=True);path.symlink_to('/dev/null')
        run_guest()
        profiles()
        run_guest(validate_only=True)
        assert_final(Path('/var/lib/dpkg/status').read_text(),plan['targets'][target])
        audit_database(Path('/'))
    require_equal(before,protected_inventory(Path('/')))
    # Nenhuma ferramenta do alvo é executada pelo pai com capabilities completas.
    result={'target':target,'status':'validated','protected_entries':len(before),
            'final_status_sha256':sha(Path('/var/lib/dpkg/status')),'base_live_reconciliation':'full views; delta ainda não gerado'}
    print('DEVLITE_RESULT='+json.dumps(result),flush=True)


def main(job,target,probe=False):
    job=confined(job);attempt=job/('probe-attempt' if probe else 'attempt')
    if os.geteuid()!=0 or os.getpid()!=1 or attempt.stat().st_uid!=0 or stat.S_IMODE(attempt.stat().st_mode)!=0o700:
        raise SpecError('Worker exige PID 1 do namespace e tentativa root 0700')
    config=json.loads((ROOT/'config/projeto.json').read_text())
    if config.get('probe_autorizado' if probe else 'executor_autorizado') is not True: raise SpecError('Não autorizado')
    plan=json.loads((attempt/'plan.json').read_text())
    spec=json.loads((attempt/'spec.json').read_text())
    # Comparar com namespaces do controlador do host capturados antes de unshare.
    host=spec['host_namespaces']
    for name,value in host.items():
        if os.readlink('/proc/self/ns/'+name)==value: raise SpecError('Namespace ausente: '+name)
    for name,item in spec['layers'].items():
        if sha(attempt/'layers'/name)!=item['sha256']: raise SpecError('Camada alterada')
    if sha(Path(spec['host_sentinel']['path']))!=spec['host_sentinel']['sha256']: raise SpecError('Sentinela ausente ou alterada antes do chroot')
    unit='devlite-'+job.name.removeprefix('phase4b3-')+'-'+target+('-probe' if probe else '')
    actual_limits=cgroup_limits(Path('/sys/fs/cgroup/system.slice')/(unit+'.service'),LIMITS)
    folder=attempt/target;folder.mkdir()
    for name in ('base','live','merged','root'): (folder/name).mkdir()
    call(['mount','--make-rprivate','/'])
    for name,image in (('base','minimal.squashfs'),('live','minimal.live.squashfs')):
        call(['mount','-t','squashfs','-o','loop,ro,nodev,nosuid',str(attempt/'layers'/image),str(folder/name)])
    call(['mount','-t','overlay','overlay','-o','ro,lowerdir='+str(folder/'live')+':'+str(folder/'base'),str(folder/'merged')])
    image=attempt/(target+'.ext4')
    with image.open('xb') as stream: stream.truncate(LIMITS['image_bytes'])
    call(['mkfs.ext4','-q','-F','-m','0',str(image)])
    root=folder/'root';call(['mount','-t','ext4','-o','loop,nodev,nosuid',str(image),str(root)])
    (root/'lost+found').rmdir()  # Diretório vazio criado pelo mkfs desta tentativa, sem remoção genérica.
    source=folder/('base' if target=='base' else 'merged')
    call(['cp','-a','--preserve=all',str(source)+'/.',str(root)])
    for directory in ('proc','dev','sys','run','tmp'):
        safe(root,directory,True)
    call(['mount','-t','proc','-o','ro,nosuid,nodev,noexec','proc',str(root/'proc')])
    for directory,size in (('dev','4m'),('sys','1m'),('run','64m'),('tmp','128m')):
        call(['mount','-t','tmpfs','-o','nosuid,nodev,size='+size+(',mode=1777' if directory=='tmp' else ',mode=755'),'tmpfs',str(root/directory)])
    for name in ('null','zero','random','urandom'):
        path=root/'dev'/name;path.touch();call(['mount','--bind','/dev/'+name,str(path)])
    for name,target_link in (('fd','/proc/self/fd'),('stdin','/proc/self/fd/0'),('stdout','/proc/self/fd/1'),('stderr','/proc/self/fd/2')):
        (root/'dev'/name).symlink_to(target_link)
    runtime=safe(root,'run/devlite',True)
    call(['mount','-t','tmpfs','-o','size=16m,nosuid,nodev','tmpfs',str(runtime)])
    (runtime/'debs').mkdir()
    call(['mount','--bind',str(attempt/'debs'),str(runtime/'debs')])
    call(['mount','-o','remount,bind,ro,nosuid,nodev,noexec',str(runtime/'debs')])
    runtime_directories(root)
    for path in ('usr/bin/python3','usr/bin/apt-get','usr/bin/dpkg','usr/bin/dpkg-deb','usr/bin/debconf-set-selections'):
        if not (root/path).is_file(): raise SpecError('Ferramenta ausente no alvo: '+path)
    inside(root,target,plan,host,probe,spec['host_sentinel'],actual_limits)
    # Saída do PID 1 desmonta o namespace e libera os loops autoclear; nenhuma montagem é exportada.

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--job',type=Path,required=True);parser.add_argument('--target',choices=('base','live'),required=True)
    parser.add_argument('--probe',action='store_true')
    args=parser.parse_args();main(args.job,args.target,args.probe)
