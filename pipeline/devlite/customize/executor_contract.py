"""Contrato, inventários e revisão do executor; nenhum privilégio nesta preparação."""
import hashlib
import json
import os
import re
import shutil
import stat
from pathlib import Path
from .installation import NAME, PROTECTED, installed, sha, compatibility
from .manifest import SpecError
from ..runtime import owned_directory

ROOT=Path(__file__).resolve().parents[3]
VERSION=re.compile(r'[0-9][A-Za-z0-9.+:~\-]*')
FORBIDDEN={'nodejs','npm','node-typescript','docker-ce','docker-ce-cli','containerd.io','docker-compose-plugin'}
CODE=('scripts/executar-programas.py','pipeline/devlite/customize/executor_contract.py',
      'pipeline/devlite/customize/executor.py','pipeline/devlite/customize/executor_worker.py',
      'pipeline/devlite/customize/isolation_validation.py','pipeline/devlite/customize/guest_runner.py','pipeline/devlite/customize/reconcile.py','pipeline/devlite/customize/installation.py',
      'pipeline/devlite/customize/service_profiles.py','pipeline/devlite/customize/manifest.py','pipeline/devlite/runtime.py')
TOOLS=('systemd-run','systemctl','unshare','mount','umount','mkfs.ext4','e2fsck','cp','gpgv','python3')
LIMITS={'image_bytes':12*1024**3,'reserve_bytes':12*1024**3,'memory_bytes':2560*1024**2,
        'swap_bytes':1024**3,'tasks':128,'seconds':3600,'cpu_percent':100,'file_bytes':2*1024**3}


def dump(path,value):
    temporary=path.with_name(path.name+'.new')
    with temporary.open('w') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    temporary.replace(path)


def confined(path):
    path=Path(path).absolute()
    if path.is_symlink() or not path.resolve().is_relative_to(ROOT/'work'):
        raise SpecError('Caminho deve ficar em work sem symlink')
    for parent in (path,*path.parents):
        if parent==ROOT: break
        if parent.is_symlink(): raise SpecError('Ancestral symlink recusado')
    return path


def validate_plan(plan):
    if plan.get('status')!='dependencias_resolvidas_offline' or set(plan.get('targets',{}))!={'base','live'}:
        raise SpecError('Plano não resolvido nos dois alvos')
    for target in plan['targets'].values():
        if not re.fullmatch('[0-9a-f]{64}',target.get('status_sha256','')):
            raise SpecError('Hash do estado dpkg ausente')
        seen=set()
        for item in target['changes']:
            name=item['package']
            if not NAME.fullmatch(name) or name in seen or name.split(':')[0] in FORBIDDEN or PROTECTED.match(name):
                raise SpecError('Pacote proibido/protegido/duplicado')
            seen.add(name)
            if not VERSION.fullmatch(item['version']) or item.get('architecture') not in ('amd64','all') or item.get('origin')!='Ubuntu':
                raise SpecError('Versão/arquitetura/origem inválida')
            if not re.fullmatch('[0-9a-f]{64}',item.get('sha256','')):
                raise SpecError('SHA-256 inválido')
            filename=Path(item['filename'])
            if not str(filename).startswith('pool/') or '..' in filename.parts or filename.suffix!='.deb':
                raise SpecError('Caminho de deb inválido')
            if target['final_versions'].get(name.split(':')[0])!=item['version']:
                raise SpecError('Versão final diverge da transação')
    compared=compatibility(plan['targets']['base'],plan['targets']['live'])
    if compared['base_packages_missing_live'] or compared['common_version_conflicts']:
        raise SpecError('Base/live incompatíveis')


def command(job,spec,target,probe=False):
    unit='devlite-'+job.name.removeprefix('phase4b3-')+'-'+target+('-probe' if probe else '')
    limits=spec['limits']
    return ['systemd-run','--unit='+unit,'--wait','--pipe','--collect','--service-type=exec',
            '--property=MemoryMax='+str(limits['memory_bytes']),'--property=MemorySwapMax='+str(limits['swap_bytes']),
            '--property=TasksMax='+str(limits['tasks']),'--property=CPUQuota=100%',
            '--property=RuntimeMaxSec='+str(limits['seconds']),'--property=KillMode=control-group',
            '--property=OOMPolicy=kill','--property=TimeoutStopSec=15',
            'unshare','--mount','--propagation','private','--pid','--fork','--kill-child=KILL',
            '--net','--ipc','--uts','--cgroup','/usr/bin/python3',str(ROOT/'pipeline/devlite/customize/executor_worker.py'),
            '--job',str(job),'--target',target]+(['--probe'] if probe else [])


def prepare(plan_file):
    if os.geteuid()==0: raise SpecError('Preparar como magaton, sem sudo')
    plan_file=confined(plan_file);plan=json.loads(plan_file.read_text());validate_plan(plan)
    job=owned_directory(ROOT/'work','phase4b3-')
    (job/'debs').mkdir()
    evidence=json.loads((ROOT/'docs/evidencias/personalizacao-minima.json').read_text())
    source=confined(Path(evidence['workspace'])/'result-iso-tree/casper')
    spec={'schema':1,'job':str(job),'plan_sha256':sha(plan_file),'source_plan':str(plan_file),
          'layers':{name:{'path':str(source/name),'sha256':data['sha256']} for name,data in evidence['layers'].items()},
          'limits':LIMITS,'code_sha256':{name:sha(ROOT/name) for name in CODE},
          'ubuntu_only':True,'automatic_downloads':False,'policy':'descartar logicamente tentativas falhas; nenhuma exclusão ou retomada in-place',
          'privileged_integration_tested':False}
    shutil.copyfile(plan_file,job/'plan.json');dump(job/'job.json',spec)
    commands={target:command(job,spec,target) for target in ('base','live')}
    approval=sha(job/'job.json')
    dump(job/'command-review.json',{'approval_sha256':approval,'internal':commands,
         'execute':['sudo','/usr/bin/python3',str(ROOT/'scripts/executar-programas.py'),'--execute','--job',str(job),'--approval-sha256',approval],
         'probe':['sudo','/usr/bin/python3',str(ROOT/'scripts/executar-programas.py'),'--probe','--job',str(job),'--approval-sha256',approval],
         'recover':['sudo','/usr/bin/python3',str(ROOT/'scripts/executar-programas.py'),'--recover','--job',str(job),'--approval-sha256',approval],
         'resources':{'free_bytes':shutil.disk_usage(job).free,'whole_sequence_budget_bytes':56*1024**3,'whole_sequence_sufficient':shutil.disk_usage(job).free>=56*1024**3},
         'blocked':['autorizações independentes: probe_autorizado, executor_autorizado e recuperacao_autorizada permanecem false','debs ainda não adquiridos','teste real privilegiado do isolamento pendente','validação atualizada da cadeia assinada e hashes das fontes']})
    return job


def protected_inventory(root):
    paths=set()
    for prefix in ('boot','etc/casper.conf','etc/subiquity','var/lib/snapd','usr/lib/casper','usr/share/casper','usr/lib/grub','usr/lib/shim'):
        path=root/prefix
        if path.is_dir() and not path.is_symlink(): paths.update(path.rglob('*'))
        elif path.exists() or path.is_symlink(): paths.add(path)
    info=root/'var/lib/dpkg/info'
    for path in info.glob('*.list'):
        if PROTECTED.match(path.name.removesuffix('.list').split(':')[0]):
            for line in path.read_text().splitlines():
                if not line.startswith('/') or '..' in Path(line).parts: raise SpecError('Inventário dpkg inseguro')
                candidate=root/line.lstrip('/')
                # Na execução real root=/ após chroot, portanto links absolutos ficam no alvo.
                if candidate.exists() or candidate.is_symlink(): paths.add(candidate)
    result={}
    for path in sorted(paths):
        st=path.lstat()
        if stat.S_ISDIR(st.st_mode): continue  # diretórios compartilhados podem receber pacotes novos
        name=str(path.relative_to(root))
        value={'mode':stat.S_IMODE(st.st_mode),'uid':st.st_uid,'gid':st.st_gid,'mtime_ns':st.st_mtime_ns,'nlink':st.st_nlink,
               'xattrs':{k:os.getxattr(path,k,follow_symlinks=False).hex() for k in os.listxattr(path,follow_symlinks=False)}}
        if path.is_symlink(): value['link']=os.readlink(path)
        elif path.is_file(): value['sha256']=sha(path)
        else: value['device']=st.st_rdev
        result[name]=value
    return result


def require_equal(before,after):
    if before!=after:
        changed=sorted(name for name in before.keys()|after.keys() if before.get(name)!=after.get(name))
        raise SpecError('Instalador/boot/snap alterado: '+', '.join(changed[:15]))


def assert_final(status,target):
    actual=installed(status)
    if actual!=target['final_versions']: raise SpecError('Banco dpkg final diverge do lock (pacote/versão/remoção extra)')
    return actual


def accepted_pair(attempt):
    journal=json.loads((attempt/'state.json').read_text())
    pair=json.loads((attempt/'accepted-pair.json').read_text())
    if journal.get('state')!='accepted' or pair.get('job_sha256')!=journal.get('job_sha256'):
        raise SpecError('Par não aceito atomicamente')
    if set(pair.get('results',{}))!={'base','live'}: raise SpecError('Par incompleto')
    return pair


def worker_result(text,target,probe=False):
    lines=[line for line in text.splitlines() if line.startswith('DEVLITE_RESULT=')]
    if len(lines)!=1: raise SpecError('Resultado ausente ou duplicado')
    result=json.loads(lines[0].split('=',1)[1])
    if result.get('target')!=target or result.get('status')!=('probe_validated' if probe else 'validated'):
        raise SpecError('Resultado de worker inválido')
    return result
