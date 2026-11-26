"""Browser-only sealed adapter. Preparation is unprivileged; execution is explicit."""
import copy,hashlib,json,os,re,shutil,signal,stat,subprocess,time
from pathlib import Path
from .release_contract import ROOT,save
from .runtime import owned_directory,Runner
from .structure import digest
from .browser import audit_transaction,REQUIRED_PACKAGES,FILES,settings,audit_configuration
from .customize.installation import installed,verify_archives,audit_database
from .customize.executor_contract import confined,validate_plan,protected_inventory,require_equal,assert_final,dump
from .customize.isolation_validation import critical_files,cgroup_limits
from .public_attestation import POLICY

SOURCE=ROOT/'work/release-cezaiofx'
ENTRY='scripts/executar-navegador.py'
GIB=1024**3
LIMITS={'memory_bytes':2560*1024**2,'swap_bytes':GIB,'tasks':128}
RESERVE=20*GIB
INITIAL=56*GIB
ENV={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LC_ALL':'C','PYTHONDONTWRITEBYTECODE':'1'}
CAPS='CAP_SYS_ADMIN CAP_SYS_CHROOT CAP_SETPCAP CAP_KILL CAP_CHOWN CAP_DAC_OVERRIDE CAP_DAC_READ_SEARCH CAP_FOWNER CAP_FSETID CAP_SETGID CAP_SETUID CAP_SETFCAP'

def code_files():
    return sorted([str(p.relative_to(ROOT)) for p in (ROOT/'pipeline').rglob('*.py')]+[ENTRY])

def root_receipt(path):
    path=confined(path);s=path.lstat()
    if not stat.S_ISREG(s.st_mode) or s.st_uid!=0 or s.st_mode&0o022:raise ValueError('Untrusted source receipt')
    return json.loads(path.read_text())

def checked_plan(plan):
    if plan.get('status')!='dependencies_resolved_offline' or plan.get('source')!=str(SOURCE):raise ValueError('Wrong browser source/plan')
    if set(plan.get('targets',{}))!={'base','live'}:raise ValueError('Both views required')
    for name,target in plan['targets'].items():
        before=dict(target['final_versions'])
        for item in target['changes']:
            if item.get('previous') is not None:raise ValueError('Browser may not upgrade accepted packages')
            before.pop(item['package'].split(':')[0],None)
        audit_transaction(target,before)
    converted=copy.deepcopy(plan);converted['status']='dependencias_resolvidas_offline'
    converted['requested_ubuntu']=sorted(REQUIRED_PACKAGES)
    validate_plan(converted)
    a={i['package']:i for i in converted['targets']['base']['changes']}
    b={i['package']:i for i in converted['targets']['live']['changes']}
    if a!=b or not a:raise ValueError('Browser dependencies differ between views')
    if any(i.get('previous') is not None for i in a.values()):raise ValueError('Upgrade forbidden')
    if len({Path(i['filename']).name for i in a.values()})!=len(a):raise ValueError('Deb name collision')
    if sorted(plan.get('artifacts',[]),key=lambda i:i['package'])!=sorted(a.values(),key=lambda i:i['package']):raise ValueError('Artifact list differs from exact transaction')
    if set(plan.get('settings_preview',{}))!={'base','live'} or any(set(v)!=set(FILES) for v in plan['settings_preview'].values()):raise ValueError('Browser settings allowlist incomplete')
    return converted

def budget(free,additional=0,initial=False):
    required=max(INITIAL if initial else 0,RESERVE+additional)
    if free<required:raise ValueError('Insufficient disk reserve: '+str(required))
    return required

def namespace_command(job,approval):
    return ['unshare','--mount','--propagation','private','--pid','--fork','--kill-child=KILL',
      '--mount-proc','--net','--ipc','--uts','/usr/bin/python3',str(ROOT/ENTRY),
      '--inner','--job',str(job),'--approval-sha256',approval,'--execute-authorized']

def command(job,approval):
    unit='devlite-public-'+job.name.removeprefix('release-')
    props=['ProtectSystem=strict','ProtectHome=read-only','ReadWritePaths='+str(job),
      'PrivateNetwork=yes','PrivateMounts=yes','NoNewPrivileges=yes','MemoryMax=2684354560',
      'MemorySwapMax=1073741824','CPUQuota=100%','TasksMax=128','RuntimeMaxSec=10800',
      'TimeoutStopSec=60','KillMode=control-group','OOMPolicy=kill','ProtectKernelTunables=yes',
      'ProtectKernelModules=yes','ProtectControlGroups=yes','RestrictRealtime=yes',
      'RestrictAddressFamilies=AF_UNIX','CapabilityBoundingSet='+CAPS]
    return ['sudo','systemd-run','--unit='+unit,'--wait','--pipe','--collect']+[
      '--property='+p for p in props]+['/usr/bin/python3',str(ROOT/ENTRY),'--outer',
      '--job',str(job),'--approval-sha256',approval,'--execute-authorized']

def prepare(plan_file):
    if os.geteuid()==0:raise ValueError('Prepare as magaton')
    plan_file=confined(plan_file);plan=json.loads(plan_file.read_text());converted=checked_plan(plan)
    extra=plan['resources']['additional_required_bytes']
    budget(shutil.disk_usage(ROOT).free,extra,initial=True)
    # root-owned public result identifies the CURRENT accepted Node/TS full views.
    receipt=root_receipt(SOURCE/'public-result.json')
    if receipt.get('status')!='public_layers_verified' or receipt.get('cleanup_errors')!=[]:raise ValueError('Source not accepted')
    images={name:receipt['results'][name]['image'] for name in ('base','live')}
    for name,item in images.items():
        if item['file']!=str(SOURCE/'attempt'/(name+'.ext4')) or item['bytes']!=12*GIB:raise ValueError('Unexpected source image')
    spec=json.loads((ROOT/'packages/browser.json').read_text())
    job=owned_directory(ROOT/'work','release-browser-');(job/'debs').mkdir()
    save(job/'plan.json',converted)
    data={'schema':1,'profile':'browser-only-offline-v1','job':str(job),'plan_sha256':digest(job/'plan.json'),
      'source_plan':str(plan_file),'source_plan_sha256':digest(plan_file),
      'source_receipt_sha256':digest(SOURCE/'public-result.json'),'source_images':images,
      'source_application_sha256':spec['application_sha256'],
      'project_config_sha256':digest(ROOT/'config/projeto.json'),'host_critical_files':critical_files(),
      'host_namespaces':{n:os.readlink('/proc/self/ns/'+n) for n in ('mnt','pid','net','ipc','uts')},
      'limits':LIMITS,'reserve_bytes':RESERVE,'initial_bytes':INITIAL,'additional_budget_bytes':extra,
      'isolation_attestation':POLICY,'code_sha256':{n:digest(ROOT/n) for n in code_files()},
      'download_allowed':False,'visual_changes':False,'iso_generation':False,'pack_layers':False,
      'operations':['verify authenticated lock and offline debs','clone accepted raw Base/Live sequentially',
        'probe restricted guest before APT','install exact browser debs offline','merge XFCE browser defaults',
        'audit and accept full views only; no SquashFS publication'],
      'recovery':'quarantine failure; no in-place dpkg retry or deletion; stop only this service'}
    save(job/'browser-contract.json',data);approval=digest(job/'browser-contract.json')
    save(job/'command-review.json',{'command':command(job,approval),'approval_sha256':approval,'executed':False,
      'acquisition_pending':[{'url':'https://archive.ubuntu.com/ubuntu/'+i['filename'],
        'sha256':i['sha256'],'bytes':i['download_bytes'],'destination':str(job/'debs'/Path(i['filename']).name)} for i in plan['artifacts']],
      'blocked':['ten verified debs must be acquired separately before root command','specific privileged approval required'],
      'free_bytes':shutil.disk_usage(ROOT).free,'required_bytes':max(INITIAL,RESERVE+extra)})
    return job,approval

def read(job,approval):
    job=confined(job)
    if job.parent!=ROOT/'work' or not job.name.startswith('release-browser-'):raise ValueError('Unexpected browser job')
    if not re.fullmatch('[0-9a-f]{64}',approval or '') or digest(job/'browser-contract.json')!=approval:raise ValueError('Browser seal differs')
    d=json.loads((job/'browser-contract.json').read_text())
    if d.get('schema')!=1 or d.get('profile')!='browser-only-offline-v1' or d.get('job')!=str(job):raise ValueError('Invalid browser contract')
    if d.get('limits')!=LIMITS or d.get('reserve_bytes')!=RESERVE or d.get('initial_bytes')!=INITIAL or d.get('isolation_attestation')!=POLICY:raise ValueError('Limits/isolation changed')
    if any(d.get(k) is not False for k in ('download_allowed','visual_changes','iso_generation','pack_layers')):raise ValueError('Operation exceeds scope')
    if set(d.get('code_sha256',{}))!=set(code_files()) or any(digest(ROOT/n)!=v for n,v in d['code_sha256'].items()):raise ValueError('Reviewed code changed')
    if digest(job/'plan.json')!=d['plan_sha256']:raise ValueError('Plan changed')
    plan=json.loads((job/'plan.json').read_text())
    original=confined(d['source_plan'])
    if digest(original)!=d['source_plan_sha256'] or checked_plan(json.loads(original.read_text()))!=plan:raise ValueError('Source/derived plan mismatch')
    if d['additional_budget_bytes']!=plan['resources']['additional_required_bytes']:raise ValueError('Budget changed')
    if digest(SOURCE/'public-result.json')!=d['source_receipt_sha256']:raise ValueError('Source receipt changed')
    receipt=root_receipt(SOURCE/'public-result.json')
    if d.get('source_images')!={n:receipt['results'][n]['image'] for n in ('base','live')}:raise ValueError('Accepted source images differ')
    if digest(ROOT/'config/projeto.json')!=d['project_config_sha256'] or critical_files()!=d['host_critical_files']:raise ValueError('Host baseline changed; review new contract')
    if any(v for v in json.loads((ROOT/'config/projeto.json').read_text()).values() if isinstance(v,bool)):raise ValueError('Host gates must remain false')
    return job,d,plan

def isolation_spec(data):
    result=copy.deepcopy(data)
    # Bind the existing attestation protocol to the browser's CURRENT sources too.
    result['host_critical_files']={**data['host_critical_files'],str(SOURCE):'readonly-directory',
      str(SOURCE/'public-result.json'):data['source_receipt_sha256'],
      **{i['file']:i['sha256'] for i in data['source_images'].values()}}
    return result

def source_image(path,record):
    path=confined(path);s=path.lstat()
    if path!=Path(record['file']) or not stat.S_ISREG(s.st_mode) or s.st_uid!=0 or s.st_mode&0o022 or s.st_size!=record['bytes'] or digest(path)!=record['sha256']:raise ValueError('Accepted image integrity failed')
    return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]

def guard_job(job):
    lock=job/'execution.lock'
    fd=os.open(lock,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400);os.close(fd)
    os.chown(job,0,0);job.chmod(0o700)

def outer(job,approval,authorized=False):
    if not authorized or os.geteuid()!=0:raise ValueError('Specific root approval required')
    job,d,plan=read(job,approval)
    budget(shutil.disk_usage(job).free,d['additional_budget_bytes'],initial=True)
    verify_archives(plan,job/'debs') # Fail BEFORE namespaces/mounts if cache incomplete.
    from .public_isolation import capture
    from .public_attestation import seal
    import secrets
    guard_job(job)
    try:
        evidence=capture(job,isolation_spec(d),'systemd',approval_sha256=approval)
        nonce=secrets.token_hex(32);fd,sha=seal(evidence,job,approval,nonce)
        args=namespace_command(job,approval)+['--external-evidence-fd',str(fd),'--external-evidence-sha256',sha,'--execution-nonce',nonce]
        try:
            with (job/'namespace.log').open('x') as log:
                child=subprocess.Popen(args,env=dict(ENV,INVOCATION_ID=os.environ.get('INVOCATION_ID','')),stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,pass_fds=(fd,),start_new_session=True)
                try:
                    while child.poll() is None:
                        budget(shutil.disk_usage(job).free,GIB);time.sleep(1)
                    if child.returncode:raise ValueError('Namespace failed; see namespace.log')
                except BaseException:
                    for sig in (signal.SIGTERM,signal.SIGKILL):
                        try:os.killpg(child.pid,sig)
                        except ProcessLookupError:pass
                        try:child.wait(timeout=15);break
                        except subprocess.TimeoutExpired:pass
                    raise
        finally:os.close(fd)
    finally:
        job.chmod(0o755)
    return job/'browser-result.json'

def merge_browser(root,preview):
    from .customize.executor_worker import safe
    existing={}
    for name in FILES:
        p=safe(root,name)
        if p.exists():existing[name]=p.read_text()
        expected=preview[name]['source_sha256']
        actual=hashlib.sha256(existing[name].encode()).hexdigest() if name in existing else None
        if actual!=expected:raise ValueError('Browser configuration preimage differs: '+name)
    rendered=settings(existing)
    for name,text in rendered.items():
        if hashlib.sha256(text.encode()).hexdigest()!=preview[name]['sha256']:raise ValueError('Rendered browser settings differ')
        p=safe(root,name);p.write_text(text);p.chmod(0o644);os.chown(p,0,0)
    return rendered

def guest_in_root(root,target,plan,host,job,limits):
    from .customize.executor_worker import safe,call,apt_config,runtime_directories,run_guest,service_guard,KEEP_CAPS
    runtime=safe(root,'run/devlite',True)
    shutil.copyfile(ROOT/'pipeline/devlite/browser_guest.py',runtime/'guest.py')
    shutil.copyfile(ROOT/'pipeline/devlite/customize/guest_runner.py',runtime/'legacy_guest.py')
    config={'changes':plan['targets'][target]['changes'],'requested':sorted(REQUIRED_PACKAGES),
      'host_namespaces':host,'host_sentinel':str(job/'host-sentinel'),'allowed_caps':sorted(KEEP_CAPS),
      'file_bytes':2*GIB,'masks':[]}
    (runtime/'transaction.json').write_text(json.dumps(config))
    (runtime/'apt.conf').write_text(apt_config())
    for name in ('empty.conf','sources.list','debconf.selections'):(runtime/name).write_text('')
    (runtime/'empty').mkdir()
    call(['mount','-o','remount,ro,nosuid,nodev',str(runtime)])
    import resource
    os.closerange(3,resource.getrlimit(resource.RLIMIT_NOFILE)[0]);os.chroot(root);os.chdir('/')
    before=protected_inventory(Path('/'))
    if digest(Path('/var/lib/dpkg/status'))!=plan['targets'][target]['status_sha256']:raise ValueError('Source dpkg differs from browser plan')
    # Original systemd files must remain unchanged; do not mask/profile services again.
    from .minimal_root import snapshot
    units=snapshot(Path('/etc/systemd'))
    with service_guard(Path('/')):run_guest()
    require_equal(before,protected_inventory(Path('/')))
    if snapshot(Path('/etc/systemd'))!=units:raise ValueError('Systemd service configuration changed')
    assert_final(Path('/var/lib/dpkg/status').read_text(),plan['targets'][target]);audit_database(Path('/'))
    configs=merge_browser(Path('/'),plan['settings_preview'][target])
    result=audit_configuration(configs,Path('/usr/share/applications/org.gnome.Epiphany.desktop').read_text(),
      Path('/usr/share/xfce4/helpers/epiphany.desktop').read_text(),Path('/var/lib/dpkg/status').read_text(),plan['targets'][target]['final_versions'])
    # This root is the clone; immutable runtime holds audit inputs. No host path is opened here.
    print('BROWSER_VIEW_RESULT='+json.dumps({'target':target,'status':'validated','final_status_sha256':digest(Path('/var/lib/dpkg/status')),**result}),flush=True)

def view_worker(job,target,approval):
    job,d,plan=read(job,approval)
    if os.geteuid()!=0 or os.getpid()!=1:raise ValueError('Target worker must be namespace PID 1 root')
    attempt=job/'attempt'
    if job.stat().st_uid!=0 or stat.S_IMODE(job.stat().st_mode)!=0o700 or attempt.stat().st_uid!=0 or stat.S_IMODE(attempt.stat().st_mode)!=0o700:raise ValueError('Private root-owned attempt required')
    if any(os.readlink('/proc/self/ns/'+n)==v for n,v in d['host_namespaces'].items()):raise ValueError('View namespace isolation missing')
    group=Path('/sys/fs/cgroup')/Path('/proc/self/cgroup').read_text().strip().split('::',1)[1].lstrip('/')
    if group.name!='devlite-public-'+job.name.removeprefix('release-')+'.service':raise ValueError('Wrong browser service cgroup')
    limits=cgroup_limits(group,LIMITS)
    from .public_execution import filesystem_proof
    filesystem_proof(Path('/proc/self/mountinfo').read_text(),job,tuple(isolation_spec(d)['host_critical_files']))
    from .customize.executor_worker import safe,call,runtime_directories
    attempt=job/'attempt';root=attempt/(target+'-root');root.mkdir()
    image=attempt/(target+'.ext4');info=image.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or stat.S_IMODE(info.st_mode)!=0o600 or info.st_nlink!=1 or info.st_size!=d['source_images'][target]['bytes']:raise ValueError('Clone metadata is not private')
    if digest(image)!=d['source_images'][target]['sha256']:raise ValueError('Clone changed before mount')
    call(['mount','--make-rprivate','/'])
    call(['mount','-t','ext4','-o','loop,rw,noatime,nodev,nosuid',str(image),str(root)])
    for name in ('proc','dev','sys','run','tmp'):safe(root,name,True)
    call(['mount','-t','proc','-o','ro,nosuid,nodev,noexec','proc',str(root/'proc')])
    for name,size in [('dev','4m'),('sys','1m'),('run','64m'),('tmp','128m')]:
        call(['mount','-t','tmpfs','-o','nosuid,nodev,size='+size+(',mode=1777' if name=='tmp' else ',mode=755'),'tmpfs',str(root/name)])
    for name in ('null','zero','random','urandom'):
        (root/'dev'/name).touch();call(['mount','--bind','/dev/'+name,str(root/'dev'/name)])
    for name,dest in [('fd','/proc/self/fd'),('stdin','/proc/self/fd/0'),('stdout','/proc/self/fd/1'),('stderr','/proc/self/fd/2')]:
        (root/'dev'/name).symlink_to(dest)
    runtime=safe(root,'run/devlite',True)
    call(['mount','-t','tmpfs','-o','size=16m,nosuid,nodev','tmpfs',str(runtime)])
    (runtime/'debs').mkdir();call(['mount','--bind',str(job/'attempt/debs'),str(runtime/'debs')])
    call(['mount','-o','remount,bind,ro,nosuid,nodev,noexec',str(runtime/'debs')])
    runtime_directories(root)
    guest_in_root(root,target,plan,d['host_namespaces'],job,limits)


def inner(job,approval,authorized=False,external=None):
    if not authorized or os.geteuid()!=0 or os.getpid()!=1:raise ValueError('Approved namespace PID 1 required')
    job,d,plan=read(job,approval)
    from .public_isolation import capture
    capture(job,isolation_spec(d),'unshare',approval_sha256=approval,inherited=external)
    from .customize.executor import authenticate
    budget(shutil.disk_usage(job).free,d['additional_budget_bytes'],initial=True)
    verify_archives(plan,job/'debs')
    attempt=job/'attempt';attempt.mkdir(mode=0o700);(attempt/'logs').mkdir();(attempt/'debs').mkdir()
    runner=Runner(attempt/'logs',0);runner.env.pop('SOURCE_DATE_EPOCH',None)
    report={'status':'running','contract_sha256':approval,'results':{},'iso_generated':False,'visual_changes':False,'layers_published':False}
    try:
        save(attempt/'authentication.json',authenticate(attempt,plan,d['source_plan']))
        from .public_iso import public_inputs
        public_inputs(SOURCE,d['source_application_sha256'])
        for item in plan['artifacts']:
            source=job/'debs'/Path(item['filename']).name;dest=attempt/'debs'/source.name
            shutil.copyfile(source,dest);dest.chmod(0o444)
        verify_archives(plan,attempt/'debs')
        (job/'host-sentinel').write_bytes(os.urandom(32));(job/'host-sentinel').chmod(0o400)
        for target in ('base','live'):
            budget(shutil.disk_usage(job).free,12*GIB+GIB)
            record=d['source_images'][target];source=Path(record['file'])
            identity=source_image(source,record);clone=attempt/(target+'.ext4')
            if clone.exists() or clone.is_symlink():raise ValueError('Never overwrite an existing clone')
            runner.run('clone-'+target,['cp','--sparse=always','--reflink=auto','--no-clobber',str(source),str(clone)])
            clone.chmod(0o600)
            if digest(clone)!=record['sha256']:raise ValueError('Clone integrity mismatch')
            argv=['unshare','--mount','--propagation','private','--pid','--fork','--kill-child=KILL','--mount-proc',
              '/usr/bin/python3',str(ROOT/ENTRY),'--view',target,'--job',str(job),'--approval-sha256',approval,'--execute-authorized']
            log=runner.run('install-'+target,argv)
            records=[json.loads(line.split('=',1)[1]) for line in log.splitlines() if line.startswith('BROWSER_VIEW_RESULT=')]
            if len(records)!=1 or records[0].get('target')!=target or records[0].get('status')!='validated':raise ValueError('Missing unique browser audit')
            runner.run('fsck-'+target,['e2fsck','-f','-n',str(clone)])
            if source_image(source,record)!=identity:raise ValueError('Original accepted image changed')
            budget(shutil.disk_usage(job).free)
            report['results'][target]={**records[0],
              'image':{'file':str(clone),'bytes':clone.stat().st_size,'sha256':digest(clone)}}
        if critical_files()!=d['host_critical_files'] or digest(ROOT/'config/projeto.json')!=d['project_config_sha256']:raise ValueError('Host guard changed')
        report.update(status='browser_full_views_verified',host_critical_unchanged=True)
        save(attempt/'accepted-pair.json',{'job_sha256':approval,'results':report['results'],'rebase_required':True,'iso_generated':False})
        dump(attempt/'state.json',{'state':'accepted','job_sha256':approval})
    except BaseException as error:
        report.update(status='quarantined',error=str(error))
        dump(attempt/'state.json',{'state':'quarantined','job_sha256':approval,'error':str(error)})
        raise
    finally:
        report['host_critical_unchanged']=critical_files()==d['host_critical_files']
        report['host_config_unchanged']=digest(ROOT/'config/projeto.json')==d['project_config_sha256']
        if not report['host_critical_unchanged'] or not report['host_config_unchanged']:
            report['status']='quarantined'
            dump(attempt/'state.json',{'state':'quarantined','job_sha256':approval,'error':'Final host guard differs'})
        save(job/'browser-result.json',report);(job/'browser-result.json').chmod(0o444)
    if report['status']!='browser_full_views_verified':raise ValueError('Browser operation quarantined')
    return job/'browser-result.json'
