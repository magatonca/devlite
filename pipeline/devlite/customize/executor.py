"""Controlador root, bloqueado por autorização; nunca executado na fase 4B.3."""
import json
import os
import secrets
import shutil
import subprocess
import time
from pathlib import Path
from .executor_contract import ROOT,CODE,TOOLS,LIMITS,confined,dump,command,validate_plan,worker_result
from .installation import sha,verify_archives,snapshot_indexes,control
from .manifest import SpecError
from .isolation_validation import critical_files

ENV={'PATH':'/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin','LC_ALL':'C','PYTHONDONTWRITEBYTECODE':'1'}


def gate(job,approval,operation="execute"):
    job=confined(job)
    if job.parent!=ROOT/'work' or not job.name.startswith('phase4b3-'): raise SpecError('Job fora do escopo')
    if os.geteuid()!=0: raise SpecError('Execução exige root autorizado separadamente')
    config=json.loads((ROOT/'config/projeto.json').read_text())
    permission={'probe':'probe_autorizado','execute':'executor_autorizado','recover':'recuperacao_autorizada'}[operation]
    if config.get(permission) is not True: raise SpecError('Executor não autorizado; não iniciar operações privilegiadas')
    if sha(job/'job.json')!=approval: raise SpecError('Hash de aprovação incorreto')
    spec=json.loads((job/'job.json').read_text())
    if spec.get('schema')!=1 or spec.get('job')!=str(job) or spec.get('limits')!=LIMITS or spec.get('ubuntu_only') is not True:
        raise SpecError('Contrato de execução inválido')
    if set(spec.get('layers',{}))!={'minimal.squashfs','minimal.live.squashfs'}: raise SpecError('Conjunto de camadas inválido')
    if set(spec.get('code_sha256',{}))!=set(CODE): raise SpecError('Código incompleto no contrato')
    for name,digest in spec['code_sha256'].items():
        if sha(ROOT/name)!=digest: raise SpecError('Código mudou após revisão: '+name)
    if sha(job/'plan.json')!=spec['plan_sha256']: raise SpecError('Plano mudou')
    plan=json.loads((job/'plan.json').read_text());validate_plan(plan)
    for name in TOOLS:
        if not shutil.which(name,path=ENV['PATH']): raise SpecError('Dependência ausente: '+name)
    if Path('/proc/1/comm').read_text().strip()!='systemd' or not Path('/sys/fs/cgroup/cgroup.controllers').is_file():
        raise SpecError('Exige systemd e cgroup v2; sem fallback sem limites')
    return job,spec,plan


def authenticate(attempt,plan,source_plan):
    auth=attempt/'auth';(auth/'lists').mkdir(parents=True);(auth/'logs').mkdir()
    evidence,blockers=snapshot_indexes(auth,confined(Path(source_plan).parent/'lists'))
    if blockers: raise SpecError('; '.join(blockers))
    wanted={(i['package'].split(':')[0],i['version'],i['architecture']):i for t in plan['targets'].values() for i in t['changes']}
    found=set()
    for file in (auth/'lists').glob('*_Packages'):
        with file.open() as stream:
            block=[]
            for line in stream:
                if line.strip(): block.append(line);continue
                if block:
                    record=control(''.join(block))[0];block=[]
                    key=(record.get('Package'),record.get('Version'),record.get('Architecture'))
                    if key in wanted:
                        item=wanted[key]
                        if any(str(item[k])!=record.get(field) for k,field in (('sha256','SHA256'),('filename','Filename'),('download_bytes','Size'))):
                            raise SpecError('Lock diverge do índice assinado')
                        found.add(key)
    if found!=set(wanted): raise SpecError('Lock contém pacote não encontrado em índice Ubuntu autenticado')
    return evidence


def state(attempt,value,**fields):
    dump(attempt/'state.json',{'state':value,**fields})


def stop(unit):
    if not unit.startswith('devlite-') or not all(c.isalnum() or c in '-_' for c in unit): raise SpecError('Unidade inválida')
    for args in (['systemctl','kill','--kill-whom=all','--signal=KILL',unit],['systemctl','stop',unit]):
        subprocess.run(args,env=ENV,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30,check=False)


def supervise(args,attempt,unit,reserve):
    with (attempt/(unit+'.log')).open('w') as log:
        process=subprocess.Popen(args,env=ENV,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,close_fds=True)
        try:
            while process.poll() is None:
                if shutil.disk_usage(attempt).free<reserve: raise SpecError('Reserva de disco atingida')
                time.sleep(1)
            if process.returncode: raise SpecError('Worker falhou: '+unit)
        except BaseException:
            stop(unit)
            try: process.wait(timeout=30)
            except subprocess.TimeoutExpired: process.kill();process.wait()
            raise


def verify_probe(job,approval):
    receipt=job/'probe-attestation.json'
    if receipt.is_symlink() or not receipt.is_file() or receipt.stat().st_uid!=0 or receipt.stat().st_mode & 0o022:
        raise SpecError('Exige probe privilegiado aprovado para este job')
    if json.loads(receipt.read_text())!={'job_sha256':approval,'status':'probe_passed'}: raise SpecError('Probe não corresponde ao job')

def validate_image(attempt,target):
    image=attempt/(target+'.ext4')
    if image.is_symlink() or image.stat().st_size!=LIMITS['image_bytes']: raise SpecError('Imagem não é a saída limitada esperada')
    result=subprocess.run(['e2fsck','-f','-n',str(image)],env=ENV,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=180)
    (attempt/(target+'-fsck.log')).write_text(result.stdout+result.stderr)
    if result.returncode: raise SpecError('Filesystem resultante não passou em e2fsck somente leitura')
    return {'file':str(image),'bytes':image.stat().st_size,'sha256':sha(image)}


def host_guard(attempt,before,critical_before=None):
    after=sha(Path('/var/lib/dpkg/status'))
    critical_after=critical_files()
    dump(attempt/'host-guard.json',{'before':before,'after':after,'unchanged':before==after,'critical_before':critical_before,'critical_after':critical_after})
    if critical_before is not None and critical_before!=critical_after: raise SpecError('Arquivos críticos do host mudaram durante o probe')
    if before!=after: raise SpecError('Banco dpkg do host mudou durante a janela; investigar antes de aceitar')


def execute(job,approval,probe=False):
    job,spec,plan=gate(job,approval,'probe' if probe else 'execute')
    if not probe: verify_probe(job,approval)
    attempt=job/('probe-attempt' if probe else 'attempt')
    if attempt.exists(): raise SpecError('Tentativa existente: recuperar e criar novo job, sem retomada in-place')
    required=max(plan['resources']['additional_required_bytes'],2*LIMITS['image_bytes']+LIMITS['reserve_bytes']+3*1024**3)
    if probe: required=max(required,56*1024**3)
    if shutil.disk_usage(job).free<required: raise SpecError('Espaço insuficiente')
    if not probe: verify_archives(plan,job/'debs')
    attempt.mkdir(mode=0o700)
    state(attempt,'validating',job_sha256=approval)
    host_before=sha(Path('/var/lib/dpkg/status'))
    critical_before=critical_files()
    dump(attempt/'host-before.json',{'critical_files':critical_before,'dpkg_status':host_before})
    try:
        auth=authenticate(attempt,plan,spec['source_plan'])
        dump(attempt/'authentication.json',auth)
        (attempt/'layers').mkdir();(attempt/'debs').mkdir()
        for name,item in spec['layers'].items():
            source=confined(item['path'])
            if sha(source)!=item['sha256']: raise SpecError('Fonte SquashFS não confere')
            destination=attempt/'layers'/name;shutil.copyfile(source,destination);destination.chmod(0o444)
            if sha(destination)!=item['sha256']: raise SpecError('Cópia da fonte inválida')
        for target in ([] if probe else plan['targets'].values()):
            for item in target['changes']:
                name=Path(item['filename']).name;destination=attempt/'debs'/name
                if not destination.exists(): shutil.copyfile(job/'debs'/name,destination);destination.chmod(0o444)
        if not probe: verify_archives(plan,attempt/'debs')
        sentinel=attempt/'host-sentinel'
        sentinel.write_bytes(secrets.token_bytes(32));sentinel.chmod(0o400)
        spec=dict(spec,host_sentinel={'path':str(sentinel),'sha256':sha(sentinel)},host_namespaces={name:os.readlink('/proc/self/ns/'+name) for name in ('mnt','pid','net','ipc','uts','cgroup')})
        dump(attempt/'plan.json',plan);dump(attempt/'spec.json',spec)
        results={}
        for target in (('base',) if probe else ('base','live')):
            args=command(job,spec,target,probe);unit=next(x.split('=',1)[1] for x in args if x.startswith('--unit='))
            state(attempt,'running_'+target,unit=unit,job_sha256=approval)
            supervise(args,attempt,unit,LIMITS['reserve_bytes'])
            result=worker_result((attempt/(unit+'.log')).read_text(),target,probe)
            if probe:
                records=[line.split('=',1)[1] for line in (attempt/(unit+'.log')).read_text().splitlines() if line.startswith('PROBE_EVIDENCE=')]
                if len(records)!=1: raise SpecError('Probe sem evidência estruturada única')
                result['checks']=json.loads(records[0])
            result['image']=validate_image(attempt,target)
            results[target]=result
            state(attempt,target+'_done',job_sha256=approval)
        if sha(sentinel)!=spec['host_sentinel']['sha256']: raise SpecError('Sentinela do host mudou')
        host_guard(attempt,host_before,critical_before)
        if probe:
            dump(attempt/'probe-results.json',{'job_sha256':approval,'results':results,'critical_host_unchanged':True,'sentinel_unchanged':True})
            state(attempt,'probe_passed',job_sha256=approval)
            dump(job/'probe-attestation.json',{'job_sha256':approval,'status':'probe_passed'})
            return job/'probe-attestation.json'
        # Commit lógico do par: não há publicação se somente uma imagem passou.
        dump(attempt/'accepted-pair.json',{'job_sha256':approval,'results':results,'rebase_required':True,'iso_generated':False})
        state(attempt,'accepted',job_sha256=approval)
    except BaseException as error:
        for target in (('base',) if probe else ('base','live')):
            unit=next(x.split('=',1)[1] for x in command(job,spec,target,probe) if x.startswith('--unit='))
            try: stop(unit)
            except (OSError,subprocess.SubprocessError): pass  # timeout/cgroup continuam limitados; recuperar depois
        guard_error=None
        try: host_guard(attempt,host_before,critical_before)
        except (SpecError,OSError) as guard_failure: guard_error=str(guard_failure)
        state(attempt,'quarantined',job_sha256=approval,error=str(error),host_guard_error=guard_error)
        raise
    return attempt/'accepted-pair.json'


def recover(job,approval):
    job,spec,plan=gate(job,approval,'recover')
    attempt=job/('attempt' if (job/'attempt').exists() else 'probe-attempt')
    if attempt.is_symlink() or attempt.stat().st_uid!=0: raise SpecError('Tentativa não é root-owned')
    journal=attempt/'state.json'
    if journal.is_symlink() or journal.stat().st_uid!=0: raise SpecError('Journal não confiável')
    value=json.loads(journal.read_text())
    if value.get('job_sha256')!=approval: raise SpecError('Journal de outro job')
    if value['state']=='accepted': raise SpecError('Par aceito não deve ser invalidado automaticamente')
    for target in ('base','live'):
        args=command(job,spec,target,attempt.name=='probe-attempt');unit=next(x.split('=',1)[1] for x in args if x.startswith('--unit='));stop(unit)
    state(attempt,'quarantined',job_sha256=approval,recovery='unidades encerradas; imagens preservadas; não retomar dpkg automaticamente')
