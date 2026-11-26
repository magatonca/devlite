"""Preflight integrado 4B.7–9. Não executa instalação, mounts, chroot, ISO ou VM."""
import errno
import hashlib
import json
import os
import pwd
import re
import shutil
import subprocess
import tarfile
from pathlib import Path
from .release_contract import ROOT,CODE,save,read
from .release_acceptance import template,PROGRAMS
from .customize.executor_contract import confined,command,LIMITS
from .customize.installation import verify_archives,sha,snapshot_indexes,control

from .customize.executor_contract import validate_plan
from .customize.package_acquisition import fresh_metadata,entries
from .customize.isolation_validation import collect,compare
from .runtime import owned_directory,Runner
from .build import detect,validate_layout
from .structure import compare_boot_metadata,region_digest
from .minimal_root import EPOCH
from .customize.manifest import SpecError

ENV={'PATH':'/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin','LC_ALL':'C','PYTHONDONTWRITEBYTECODE':'1'}
RISK_WORDS=('systemctl','invoke-rc.d','deb-systemd','start-stop-daemon','mysql_install_db','mariadb-install-db','update-initramfs','update-grub','modprobe','mount ')


def ordinary():
    if os.geteuid()==0 or pwd.getpwuid(os.getuid()).pw_name!='magaton':raise SpecError('Preparar como magaton, sem sudo')


def audit_deb(path,item):
    result=subprocess.run(['dpkg-deb','--field',str(path)],env=ENV,capture_output=True,text=True,timeout=60,check=True)
    record=control(result.stdout)[0]
    if (record.get('Package'),record.get('Version'),record.get('Architecture'))!=(item['package'],item['version'],item['architecture']):raise SpecError('Identidade Debian diverge: '+path.name)
    process=subprocess.Popen(['dpkg-deb','--ctrl-tarfile',str(path)],env=ENV,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    scripts={};total=0
    try:
        with tarfile.open(fileobj=process.stdout,mode='r|') as archive:
            for member in archive:
                name=member.name.removeprefix('./')
                if name not in ('preinst','postinst','prerm','postrm','config','triggers'):continue
                if not member.isfile() or member.size>8*1024**2:raise SpecError('Control archive inesperado')
                total+=member.size
                if total>32*1024**2:raise SpecError('Control archive excessivo')
                data=archive.extractfile(member).read();text=data.decode('utf-8',errors='replace')
                scripts[name]={'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'risk_tokens':[w for w in RISK_WORDS if w in text]}
        while process.stdout.read(65536):pass
        process.stdout.close()
        if process.wait(timeout=60):raise SpecError('Leitura control-tar falhou')
    finally:
        if process.poll() is None:process.kill();process.wait()
    return {'package':item['package'],'version':item['version'],'architecture':item['architecture'],'scripts':scripts,'executed':False}


def stage_cache(cache,destination,artifacts):
    ordinary();cache=confined(cache);destination=confined(destination)
    if not destination.exists():destination.mkdir()
    expected={Path(i['filename']).name:i for i in artifacts}
    if {p.name for p in destination.iterdir()}-expected.keys():raise SpecError('Cache de execução tem arquivos inesperados')
    records=[]
    for name,item in sorted(expected.items()):
        source=cache/name;target=destination/name
        if source.is_symlink() or sha(source)!=item['sha256'] or source.stat().st_size!=item['download_bytes']:raise SpecError('Cache de origem mudou')
        strategy='existing'
        if not target.exists() and not target.is_symlink():
            try:os.link(source,target);strategy='hardlink'
            except OSError as error:
                if error.errno!=errno.EXDEV:raise
                with source.open('rb') as incoming,target.open('xb') as outgoing:shutil.copyfileobj(incoming,outgoing)
                strategy='copy'
        if target.is_symlink() or not target.is_file() or sha(target)!=item['sha256']:raise SpecError('Cache de execução inválido')
        records.append({'name':name,'sha256':item['sha256'],'strategy':strategy})
    return records


def equivalent_artifacts(left,right):
    fields=('package','version','architecture','filename','sha256','download_bytes','targets','urls')
    def canonical(values):
        return sorted([{field:item[field] for field in fields} for item in values],key=lambda i:(i['package'],i['version'],i['architecture']))
    if canonical(left)!=canonical(right):raise SpecError('Conteúdo/versões do cache não corresponde ao plano aprovado')


def prepare():
    ordinary();before=collect(ROOT)
    work=owned_directory(ROOT/'work','release-');(work/'logs').mkdir();(work/'lists').mkdir()
    report={'schema':1,'status':'preparing','workspace':str(work),'executed':{'install':False,'pack':False,'iso':False,'vm':False},'blockers':[]}
    try:
        acquisition=json.loads((ROOT/'docs/evidencias/aquisicao-pacotes.json').read_text())
        cache_manifest=confined(acquisition['manifest']);manifest=json.loads(cache_manifest.read_text())
        if sha(cache_manifest)!=acquisition['manifest_sha256']:raise SpecError('Manifesto de aquisição alterado')
        receipt=confined(acquisition['receipt'])
        if sha(receipt)!=acquisition['receipt_sha256']:raise SpecError('Receipt de aquisição alterado')
        probe=json.loads((ROOT/'docs/evidencias/probe-real-isolamento.json').read_text());executor=confined(probe['job'])
        if (executor/'attempt').exists():raise SpecError('Tentativa de instalação existente: não reusar nem sobrescrever')
        spec=json.loads((executor/'job.json').read_text())
        if sha(executor/'job.json')!=probe['job_sha256']:raise SpecError('Contrato do probe mudou')
        attestation=executor/'probe-attestation.json'
        if attestation.is_symlink() or attestation.stat().st_uid!=0 or attestation.stat().st_mode & 0o022 or json.loads(attestation.read_text())!={'job_sha256':probe['job_sha256'],'status':'probe_passed'}:raise SpecError('Probe não é uma prova root-owned válida')
        if any(sha(ROOT/name)!=digest for name,digest in spec['code_sha256'].items()):raise SpecError('Código aprovado do executor mudou')
        plan=json.loads((executor/'plan.json').read_text());validate_plan(plan)
        if sha(executor/'plan.json')!=spec['plan_sha256']:raise SpecError('Plano do executor mudou')
        count=verify_archives(plan,confined(Path(acquisition['cache'])))
        evidence,blockers=snapshot_indexes(work,confined(Path(spec['source_plan']).parent/'lists'))
        if blockers:raise SpecError('; '.join(blockers))
        fresh_metadata(evidence)
        authenticated=entries(plan,work,evidence)
        equivalent_artifacts(authenticated,manifest['artifacts'])
        acquired=work/'acquired-origin';acquired.mkdir();(acquired/'logs').mkdir();(acquired/'lists').mkdir()
        acquired_evidence,acquired_blockers=snapshot_indexes(acquired,cache_manifest.parent/'lists')
        if acquired_blockers:raise SpecError('; '.join(acquired_blockers))
        fresh_metadata(acquired_evidence)
        if acquired_evidence!=manifest['indexes'] or entries(plan,acquired,acquired_evidence)!=manifest['artifacts']:raise SpecError('Proveniência da aquisição não confere')
        audits=[audit_deb(Path(acquisition['cache'])/Path(item['filename']).name,item) for item in authenticated]
        save(work/'maintainer-audit.json',audits)
        staged=stage_cache(Path(acquisition['cache']),executor/'debs',authenticated)
        save(work/'cache-staging.json',staged)
        runner=Runner(work/'logs',EPOCH)
        source=ROOT/'sources/xubuntu-24.04.5-minimal-amd64.iso'
        previous=ROOT/'artifacts/phase4b1-lgpa3zc7/devlite-os-1.0-basic-experimental.iso'
        original_boot=detect(runner,source,'official');reference_boot=detect(runner,previous,'reference')
        compare_boot_metadata(source,previous,original_boot,reference_boot)
        if region_digest(source,original_boot['efi_offset'],original_boot['efi_bytes'])!=region_digest(previous,reference_boot['efi_offset'],reference_boot['efi_bytes']):raise SpecError('EFI de referência diverge')
        reference=ROOT/'work/phase4b1-dhzezpnz/result-iso-tree';validate_layout(reference)
        for layer in ('minimal.squashfs','minimal.live.squashfs'):
            runner.run('superblock-'+layer,['unsquashfs','-s',str(reference/'casper'/layer)])
        contract={'schema':1,'job':str(work),'executor_job':str(executor),'executor_sha256':probe['job_sha256'],
                  'cache_manifest_sha256':acquisition['manifest_sha256'],'host_mount_namespace':os.readlink('/proc/self/ns/mnt'),
                  'code_sha256':{name:sha(ROOT/name) for name in CODE},'source_date_epoch':EPOCH,'profile':'ubuntu-experimental','external_pending':['Node.js LTS','TypeScript','VS Code']}
        save(work/'release-contract.json',contract);approval=sha(work/'release-contract.json')
        install=['sudo','/usr/bin/python3',str(ROOT/'scripts/instalar-release-root.py'),'--job',str(work),'--approval-sha256',approval]
        pack=['sudo','systemd-run','--unit=devlite-pack-'+work.name.removeprefix('release-'),'--wait','--pipe','--collect',
              '--property=MemoryMax=2684354560','--property=MemorySwapMax=1073741824','--property=CPUQuota=100%','--property=TasksMax=128','--property=RuntimeMaxSec=7200',
              '--property=KillMode=control-group','--property=OOMPolicy=kill','unshare','--mount','--propagation','private',
              '/usr/bin/python3',str(ROOT/'scripts/integrar-release-root.py'),'--job',str(work),'--approval-sha256',approval]
        iso=['python3',str(ROOT/'scripts/devlite-release.py'),'--build-iso',str(work),'--approval-sha256',approval]
        save(work/'command-review.json',{'install':install,'pack':pack,'iso':iso,'install_internal':{t:command(executor,spec,t) for t in ('base','live')},
              'install_scope':'Base → Live, cópias descartáveis, auditoria e quarentena; sem integração/ISO/VM','all_permissions_enabled':False})
        save(work/'acceptance-template.json',template())
        save(work/'program-checks.json',{'commands':PROGRAMS,'executed':False,'needs_guest':'Executar somente em VM/instalado autorizado; checks visuais/funcionais também obrigatórios'})
        report.update(status='prepared_not_executed',cache_files=count,cache_bytes=sum(i['download_bytes'] for i in authenticated),
                      cache_staged_for_executor=True,both_signed_snapshots_verified=True,maintainer_scripts=sum(len(i['scripts']) for i in audits),
                      packages_with_service_or_privilege_tokens=[i['package'] for i in audits if any(s['risk_tokens'] for s in i['scripts'].values())],
                      boot_reference={'bios_uefi_structure':'verified_existing_4B1_only','efi_unchanged':True,'official':original_boot,'reference':reference_boot},
                      contract_sha256=approval,installation_required_bytes=plan['resources']['additional_required_bytes'],
                      phases={'4B.7':'cache verificado e preparado; instalação aguardando aprovação','4B.8':'backend preparado; depende de par instalado e integração root autorizada','4B.9':'matriz/checklist/validador preparados; BIOS/UEFI/instalação reais pendentes'},
                      blockers=['instalação real não autorizada','integração root e geração ISO não autorizadas','Node.js LTS/TypeScript/VS Code fora do cache; não declarar full-edition pronta','rebase kernel e segunda construção só poderão ser validados após inputs reais'])
    except BaseException as error:
        report.update(status='blocked',error=str(error));raise
    finally:
        after=collect(ROOT);report['host_comparison']=compare(before,after);report['free_bytes']=after['disk']['free_bytes']
        save(work/'report.json',report)
    return work
