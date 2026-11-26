#!/usr/bin/env python3
"""Fixed PHP8.3 version/lint in a read-only rootfs; never execute Adminer application."""
import argparse,ctypes,hashlib,json,os,resource,shutil,signal,stat,subprocess,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pipeline.devlite.runtime import owned_directory
from pipeline.devlite.customize.executor_contract import confined
from pipeline.devlite.customize.isolation_validation import critical_files,cgroup_limits
from pipeline.devlite.public_execution import filesystem_proof
SOURCE=ROOT/'work/release-browser-2f24tvsg'
CANDIDATE=ROOT/'work/adminer-review-11po9k_l/adminer-6.3.0-mysql.php'
EXPECTED='33af3816a08213ae7579f8416e66d7d70054d6bcd70516d4ad3124f4b8b5c1e0'
ENTRY='scripts/verificar-php-adminer.py'
LIMITS={'memory_bytes':1024**3,'swap_bytes':512*1024**2,'tasks':64}
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def load(p,expected=None):
    p=confined(p)
    if p.is_symlink():raise ValueError('Symlink JSON input')
    raw=p.read_bytes()
    if expected and hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('Input changed')
    return json.loads(raw)
def commands():
    return [['/usr/bin/php8.3','-n','-v'],['/usr/bin/php8.3','-n','-l','/run/adminer-check/adminer.php']]
def check_candidate(p):
    if p.is_symlink() or not p.is_file() or sha(p)!=EXPECTED:raise ValueError('Adminer source hash mismatch')
def command(job,approval):
    props=['ProtectSystem=strict','ProtectHome=read-only','ReadWritePaths='+str(job),'PrivateNetwork=yes','PrivateMounts=yes','NoNewPrivileges=yes',
      'ProtectKernelTunables=yes','ProtectKernelModules=yes','ProtectControlGroups=yes','MemoryMax=1073741824','MemorySwapMax=536870912','TasksMax=64','CPUQuota=100%',
      'RuntimeMaxSec=300','KillMode=control-group','OOMPolicy=kill','RestrictAddressFamilies=AF_UNIX',
      'CapabilityBoundingSet=CAP_SYS_ADMIN CAP_SYS_CHROOT CAP_SETPCAP CAP_SETUID CAP_SETGID CAP_KILL CAP_CHOWN CAP_DAC_OVERRIDE CAP_DAC_READ_SEARCH']
    return ['sudo','systemd-run','--unit=devlite-'+job.name,'--wait','--pipe','--collect']+['--property='+v for v in props]+[
      'unshare','--mount','--propagation','private','--pid','--fork','--kill-child=KILL','--mount-proc','--net','--ipc','--uts',
      '/usr/bin/python3',str(ROOT/ENTRY),'--job',str(job),'--approval-sha256',approval,'--execute-authorized']
def prepare():
    if os.geteuid()==0:raise ValueError('Prepare without root')
    check_candidate(CANDIDATE)
    receipt=SOURCE/'browser-result.json';s=receipt.lstat();r=load(receipt)
    if s.st_uid!=0 or s.st_mode&0o022 or r['status']!='browser_full_views_verified':raise ValueError('Untrusted accepted rootfs')
    old=load(SOURCE/'browser-contract.json',r['contract_sha256'])
    job=owned_directory(ROOT/'work','adminer-php-check-')
    spec={'job':str(job),'source_receipt_sha256':sha(receipt),'source_image':r['results']['base']['image'],
      'candidate_sha256':EXPECTED,'code_sha256':{**old['code_sha256'],ENTRY:sha(ROOT/ENTRY)},'host_critical_files':critical_files(),
      'host_namespaces':{n:os.readlink('/proc/self/ns/'+n) for n in ('mnt','pid','net','ipc','uts')},
      'limits':LIMITS,'commands':commands(),'operation':'php-version-and-lint-only'}
    (job/'contract.json').write_text(json.dumps(spec,indent=2)+'\n');approval=sha(job/'contract.json')
    (job/'command.json').write_text(json.dumps({'command':command(job,approval),'approval_sha256':approval},indent=2)+'\n')
    print(job);print(approval)
def compile_child(argv):
    # Parent is namespace PID1 and already chrooted. Never inherit host job descriptors.
    read_fd,write_fd=os.pipe();pid=os.fork()
    if pid==0:
        try:
            os.close(read_fd);os.dup2(write_fd,1);os.dup2(write_fd,2)
            os.closerange(3,resource.getrlimit(resource.RLIMIT_NOFILE)[0])
            libc=ctypes.CDLL(None,use_errno=True)
            os.setgroups([])
            for cap in range(int(Path('/proc/sys/kernel/cap_last_cap').read_text())+1):
                if libc.prctl(24,cap,0,0,0)!=0:raise RuntimeError('Capability drop failed')
            os.setgid(65534);os.setuid(65534)
            if libc.prctl(38,1,0,0,0)!=0:raise RuntimeError('NoNewPrivileges failed')
            status=Path('/proc/self/status').read_text()
            for line in status.splitlines():
                if line.startswith(('CapEff:','CapPrm:','CapBnd:','CapInh:','CapAmb:')) and int(line.split()[1],16):raise RuntimeError('Capability retained')
            if 'NoNewPrivs:\t1' not in status:raise RuntimeError('Missing NNP')
            resource.setrlimit(resource.RLIMIT_CPU,(10,10));resource.setrlimit(resource.RLIMIT_FSIZE,(1024**2,1024**2))
            os.execve(argv[0],argv,{'PATH':'/usr/bin:/bin','LC_ALL':'C','HOME':'/tmp'})
        except BaseException:os._exit(120)
    os.close(write_fd);data=bytearray()
    try:
        while True:
            block=os.read(read_fd,4096)
            if not block:break
            data.extend(block)
            if len(data)>32768:os.kill(pid,signal.SIGKILL);raise ValueError('Unexpected compiler output volume')
    finally:os.close(read_fd)
    _,status=os.waitpid(pid,0)
    if not os.WIFEXITED(status) or os.WEXITSTATUS(status):raise ValueError('Fixed PHP command failed: '+data.decode(errors='replace'))
    return data.decode(errors='replace')
def run(job,approval,authorized):
    if not authorized or os.geteuid()!=0 or os.getpid()!=1:raise ValueError('Approved root PID namespace required')
    job=confined(job)
    if job.parent!=ROOT/'work' or not job.name.startswith('adminer-php-check-'):raise ValueError('Invalid check job')
    d=load(job/'contract.json',approval)
    if d['job']!=str(job) or d['commands']!=commands() or d['limits']!=LIMITS or d['operation']!='php-version-and-lint-only':raise ValueError('Scope changed')
    if any(sha(ROOT/n)!=h for n,h in d['code_sha256'].items()):raise ValueError('Code changed')
    if critical_files()!=d['host_critical_files'] or sha(SOURCE/'browser-result.json')!=d['source_receipt_sha256']:raise ValueError('Baseline changed')
    check_candidate(CANDIDATE)
    if any(os.readlink('/proc/self/ns/'+n)==v for n,v in d['host_namespaces'].items()):raise ValueError('Namespace missing')
    group=Path('/sys/fs/cgroup')/Path('/proc/self/cgroup').read_text().strip().split('::',1)[1].lstrip('/')
    if group.name!='devlite-'+job.name+'.service':raise ValueError('Wrong cgroup')
    cgroup_limits(group,LIMITS)
    filesystem_proof(Path('/proc/self/mountinfo').read_text(),job,tuple(d['host_critical_files'])+(str(SOURCE),))
    image=confined(d['source_image']['file']);s=image.lstat()
    if image!=SOURCE/'attempt/base.ext4' or s.st_uid!=0 or s.st_mode&0o022 or not stat.S_ISREG(s.st_mode) or s.st_size!=d['source_image']['bytes']:raise ValueError('Wrong source image')
    with (job/'execution.lock').open('x') as f:f.write(approval)
    os.chown(job,0,0);job.chmod(0o700)
    def call(args):subprocess.run(args,check=True,stdin=subprocess.DEVNULL,env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LC_ALL':'C'})
    bundle=job/'adminer.php'
    with CANDIDATE.open('rb') as incoming,bundle.open('xb') as outgoing:shutil.copyfileobj(incoming,outgoing,1024*1024)
    bundle.chmod(0o444);check_candidate(bundle)
    root=job/'root';root.mkdir()
    call(['mount','--make-rprivate','/'])
    call(['mount','-t','ext4','-o','loop,ro,noload,nodev,nosuid',str(image),str(root)])
    if not os.statvfs(root).f_flag & os.ST_RDONLY:raise ValueError('Rootfs not readonly')
    call(['mount','-t','proc','-o','ro,nosuid,nodev,noexec','proc',str(root/'proc')])
    for name,size in [('run','8m'),('tmp','16m')]:
        call(['mount','-t','tmpfs','-o','nodev,nosuid,noexec,size='+size+(',mode=1777' if name=='tmp' else ',mode=755'),'tmpfs',str(root/name)])
    runtime=root/'run/adminer-check';runtime.mkdir();dest=runtime/'adminer.php';dest.touch()
    call(['mount','--bind',str(bundle),str(dest)]);call(['mount','-o','remount,bind,ro,nodev,nosuid,noexec',str(dest)])
    directory=os.open(job,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    output=os.open('result.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=directory)
    try:
        if ctypes.CDLL(None,use_errno=True).prctl(4,0,0,0,0)!=0:raise ValueError('Dumpable guard failed')
        os.chroot(root);os.chdir('/')
        results=[compile_child(args) for args in commands()]
        if not results[0].startswith('PHP 8.3.') or 'No syntax errors detected' not in results[1]:raise ValueError('Unexpected PHP result')
        report={'status':'php83_syntax_passed','outputs':results,'commands':commands(),'candidate_sha256':EXPECTED,
          'application_executed':False,'database_started':False,'http_tested':False,'images_modified':False,'compiler_uid':65534,
          'compiler_capabilities':'all zero','no_new_privileges':True,'rootfs_readonly':True,'contract_sha256':approval}
        raw=(json.dumps(report,indent=2)+'\n').encode()
        offset=0
        while offset<len(raw):offset+=os.write(output,raw[offset:])
        os.fsync(output);os.fchmod(output,0o444)
    finally:
        os.close(output);os.fchmod(directory,0o755);os.close(directory)
    # PID1 exits: all read-only mounts and tmpfs vanish. No target daemon was started.
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true');p.add_argument('--job',type=Path);p.add_argument('--approval-sha256');p.add_argument('--execute-authorized',action='store_true');a=p.parse_args()
    try:
        if a.prepare:prepare()
        else:run(a.job,a.approval_sha256,a.execute_authorized)
    except (ValueError,OSError,RuntimeError) as error:raise SystemExit(str(error))
