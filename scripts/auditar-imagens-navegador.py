#!/usr/bin/env python3
"""Read-only post-install audit. No package manager, target executable or ISO."""
import argparse,hashlib,json,os,shlex,shutil,stat,subprocess,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pipeline.devlite.runtime import owned_directory
from pipeline.devlite.customize.executor_contract import confined
from pipeline.devlite.minimal_root import member,allocated_usage
from pipeline.devlite.public_execution import filesystem_proof
from pipeline.devlite.customize.isolation_validation import critical_files,cgroup_limits

ENTRY='scripts/auditar-imagens-navegador.py'
SOURCE=ROOT/'work/release-browser-2f24tvsg'
APPROVAL='743d4a621b1a2837ffa6612257842c591283abebff64f8faef0ad5886c8073b1'
LIMITS={'memory_bytes':1024**3,'swap_bytes':512*1024**2,'tasks':64}
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def load(path,expected=None):
    p=confined(path)
    if p.is_symlink():raise ValueError('Symlink input')
    raw=p.read_bytes()
    if expected is not None and hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('Input changed')
    return json.loads(raw)
def source_receipt(verify_pair=False):
    p=SOURCE/'browser-result.json';s=p.lstat()
    if s.st_uid!=0 or s.st_mode&0o022 or not stat.S_ISREG(s.st_mode):raise ValueError('Untrusted browser receipt')
    d=load(p)
    if d['status']!='browser_full_views_verified' or d['contract_sha256']!=APPROVAL or not d['host_critical_unchanged'] or not d['host_config_unchanged']:raise ValueError('Browser pair not accepted')
    if verify_pair:
        pair=load(SOURCE/'attempt/accepted-pair.json');state=load(SOURCE/'attempt/state.json')
        if state!={'state':'accepted','job_sha256':APPROVAL} or pair['job_sha256']!=APPROVAL or pair['results']!=d['results']:raise ValueError('Pair not accepted atomically')
    return d

def verify_entries(root,manifest,owner=(0,0)):
    checked=0
    for name,item in manifest.items():
        try:p=member(root,name)
        except RuntimeError as error:raise ValueError(str(error)) from error
        s=p.lstat()
        kind=item['type']
        if (s.st_uid,s.st_gid)!=owner or (kind!='dir' and stat.S_IMODE(s.st_mode)!=int(item['mode'],8)):raise ValueError('Metadata differs: '+name)
        if kind=='dir' and not stat.S_ISDIR(s.st_mode):raise ValueError('Not a directory')
        elif kind=='file':
            if not stat.S_ISREG(s.st_mode) or s.st_size!=item['size'] or sha(p)!=item['sha256']:raise ValueError('File differs: '+name)
            checked+=1
        elif kind=='symlink':
            if not stat.S_ISLNK(s.st_mode) or os.readlink(p)!=item['target']:raise ValueError('Link differs')
        elif kind not in ('dir','file','symlink'):raise ValueError('Unexpected entry type')
    return checked

def argv(job,approval):
    props=['ProtectSystem=strict','ProtectHome=read-only','ReadWritePaths='+str(job),
      'PrivateNetwork=yes','PrivateMounts=yes','NoNewPrivileges=yes','ProtectKernelTunables=yes',
      'ProtectKernelModules=yes','ProtectControlGroups=yes','MemoryMax=1073741824',
      'MemorySwapMax=536870912','TasksMax=64','CPUQuota=100%','RuntimeMaxSec=1800',
      'KillMode=control-group','OOMPolicy=kill','RestrictAddressFamilies=AF_UNIX',
      'CapabilityBoundingSet=CAP_SYS_ADMIN CAP_CHOWN CAP_DAC_OVERRIDE CAP_DAC_READ_SEARCH']
    return ['sudo','systemd-run','--unit=devlite-'+job.name,'--wait','--pipe','--collect']+['--property='+x for x in props]+[
      'unshare','--mount','--propagation','private','--pid','--fork','--kill-child=KILL','--mount-proc',
      '--net','--ipc','--uts','/usr/bin/python3',str(ROOT/ENTRY),'--job',str(job),
      '--approval-sha256',approval,'--execute-authorized']

def prepare():
    if os.geteuid()==0:raise ValueError('Prepare as magaton')
    r=source_receipt();old=load(SOURCE/'browser-contract.json',APPROVAL)
    public=load(ROOT/'work/release-cezaiofx/public-contract.json',old['source_application_sha256'])
    report_path=confined(Path(public['payload_job'])/'payload-report.json')
    payload=load(report_path,public['payload_report_sha256'])
    if shutil.disk_usage(ROOT).free<20*1024**3:raise ValueError('Disk reserve')
    job=owned_directory(ROOT/'work','browser-final-audit-')
    (job/'manifest.json').write_text(json.dumps(payload['manifest'],sort_keys=True,indent=2)+'\n')
    d={'job':str(job),'source_receipt_sha256':sha(SOURCE/'browser-result.json'),
      'manifest_sha256':sha(job/'manifest.json'),'source_images':{n:r['results'][n]['image'] for n in ('base','live')},
      'code_sha256':{**old['code_sha256'],ENTRY:sha(ROOT/ENTRY)},'host_critical_files':critical_files(),
      'host_namespaces':{n:os.readlink('/proc/self/ns/'+n) for n in ('mnt','pid','net','ipc','uts')},
      'limits':LIMITS,'reserve_bytes':20*1024**3,'operation':'read-only-prefix-and-space-audit'}
    (job/'audit-contract.json').write_text(json.dumps(d,indent=2)+'\n');h=sha(job/'audit-contract.json')
    (job/'command.json').write_text(json.dumps({'command':argv(job,h),'approval_sha256':h,'executed':False},indent=2)+'\n')
    print(job);print(h)

def run(job,approval,authorized):
    if not authorized or os.geteuid()!=0 or os.getpid()!=1:raise ValueError('Explicit root PID namespace execution required')
    job=confined(job)
    if job.parent!=ROOT/'work' or not job.name.startswith('browser-final-audit-'):raise ValueError('Invalid job')
    d=load(job/'audit-contract.json',approval)
    if d['job']!=str(job) or d['limits']!=LIMITS or d['operation']!='read-only-prefix-and-space-audit':raise ValueError('Invalid profile')
    if any(sha(ROOT/n)!=v for n,v in d['code_sha256'].items()):raise ValueError('Code changed')
    if any(os.readlink('/proc/self/ns/'+n)==v for n,v in d['host_namespaces'].items()):raise ValueError('Namespaces not isolated')
    group=Path('/sys/fs/cgroup')/Path('/proc/self/cgroup').read_text().strip().split('::',1)[1].lstrip('/')
    if group.name!='devlite-'+job.name+'.service':raise ValueError('Wrong cgroup')
    cgroup_limits(group,LIMITS)
    if 'NoNewPrivs:\t1' not in Path('/proc/self/status').read_text():raise ValueError('NoNewPrivileges not effective')
    filesystem_proof(Path('/proc/self/mountinfo').read_text(),job,tuple(d['host_critical_files'])+(str(SOURCE),))
    if critical_files()!=d['host_critical_files'] or sha(SOURCE/'browser-result.json')!=d['source_receipt_sha256']:raise ValueError('Baseline changed')
    receipt=source_receipt(verify_pair=True);manifest=load(job/'manifest.json',d['manifest_sha256'])
    if d['source_images']!={n:receipt['results'][n]['image'] for n in ('base','live')}:raise ValueError('Source images differ')
    lock=job/'execution.lock'
    with lock.open('x') as f:f.write(approval)
    os.chown(job,0,0);job.chmod(0o700)
    results={};mounted=[];identities={}
    def call(args):subprocess.run(args,check=True,stdin=subprocess.DEVNULL,env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LC_ALL':'C'})
    try:
        call(['mount','--make-rprivate','/'])
        for name,image in d['source_images'].items():
            source=confined(image['file']);s=source.lstat()
            if source!=SOURCE/'attempt'/(name+'.ext4') or not stat.S_ISREG(s.st_mode) or s.st_uid!=0 or s.st_mode&0o022 or s.st_size!=image['bytes']:raise ValueError('Unexpected source image')
            identities[name]=(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
            root=job/name;root.mkdir()
            call(['mount','-t','ext4','-o','loop,ro,noload,nodev,nosuid,noexec',str(source),str(root)]);mounted.append(root)
            if not os.statvfs(root).f_flag & os.ST_RDONLY:raise ValueError('Image is writable')
            checked=verify_entries(root,manifest)
            results[name]={'protected_files_verified':checked,'allocated_bytes':allocated_usage(root)}
            call(['umount',str(root)]);mounted.remove(root)
            s=source.stat()
            if identities[name]!=(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns):raise ValueError('Source metadata changed')
        if critical_files()!=d['host_critical_files']:raise ValueError('Host changed')
        required=3*results['base']['allocated_bytes']+5*results['live']['allocated_bytes']+10*1024**3
        report={'status':'readonly_audit_passed','results':results,'required_pack_bytes_existing_formula':required,
          'free_bytes':shutil.disk_usage(job).free,'pack_budget_sufficient':shutil.disk_usage(job).free>=required,
          'source_metadata_unchanged':True,'source_raw_hashes_recomputed':False,'host_critical_unchanged':True,
          'target_programs_executed':False,'images_modified':False,'iso_generated':False,'contract_sha256':approval}
        (job/'result.json').write_text(json.dumps(report,indent=2)+'\n');(job/'result.json').chmod(0o444)
    finally:
        for path in reversed(mounted):call(['umount',str(path)])
        job.chmod(0o755)
    print(job/'result.json')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true');p.add_argument('--job',type=Path);p.add_argument('--approval-sha256');p.add_argument('--execute-authorized',action='store_true');a=p.parse_args()
    try:
        if a.prepare:prepare()
        else:run(a.job,a.approval_sha256,a.execute_authorized)
    except (OSError,ValueError,RuntimeError) as error:raise SystemExit(str(error))
