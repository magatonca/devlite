"""Integração futura em namespace privado; nunca chamada pela preparação."""
import json
import os
import shutil
from pathlib import Path
from .customize.executor_contract import ROOT,confined,accepted_pair
from .customize.installation import installed
from .customize.manifest import SpecError
from .minimal_root import snapshot,allocated_usage,EPOCH
from .release_layers import recipe,materialize,clean_snapshot,manifests
from .runtime import Runner
from .structure import digest


def compress_args(source,output,root):
    return ['mksquashfs',str(source),str(output),'-noappend','-no-recovery','-comp','xz','-b','131072','-processors','1','-mem','256M','-no-progress','-exit-on-error',
            '-mkfs-time',str(EPOCH),'-root-time',str(root['mtime']),'-root-mode',format(root['mode'],'o'),'-root-uid',str(root['uid']),'-root-gid',str(root['gid'])]


def contract(job,approval):
    from .release_contract import read
    return read(job,approval)


def run(job,approval):
    if os.geteuid()!=0:raise SpecError('Integração exige root autorizado separadamente')
    job,data=contract(job,approval)
    if json.loads((ROOT/'config/projeto.json').read_text()).get('integracao_camadas_autorizada') is not True:raise SpecError('Integração não autorizada')
    if os.readlink('/proc/self/ns/mnt')==data['host_mount_namespace']:raise SpecError('Exige namespace mount privado')
    if 'resume_packed' in data:
        from .release_resume import run as resume
        return resume(job,data,approval)
    attempt=confined(Path(data['executor_job'])/'attempt')
    if attempt.is_symlink() or attempt.stat().st_uid!=0:raise SpecError('Tentativa de instalação não confiável')
    pair=accepted_pair(attempt)
    if pair['job_sha256']!=data['executor_sha256']:raise SpecError('Par pertence a outro executor')
    target=job/'pack-attempt'
    if target.exists():raise SpecError('Não sobrescrever tentativa de integração')
    if shutil.disk_usage(job).free<32*1024**3:raise SpecError('Integração requer 32 GiB de margem inicial')
    target.mkdir(mode=0o700);(target/'logs').mkdir();runner=Runner(target/'logs',EPOCH)
    runner.env.pop('SOURCE_DATE_EPOCH',None)
    report={'status':'running','iso_generated':False}
    try:
        runner.run('private',['mount','--make-rprivate','/'])
        trees={};states={}
        for name in ('base','live'):
            image=attempt/(name+'.ext4');record=pair['results'][name]['image']
            if record['file']!=str(image) or digest(image)!=record['sha256']:raise SpecError('Imagem instalada mudou')
            mount=target/name;mount.mkdir()
            runner.run('mount-'+name,['mount','-t','ext4','-o','loop,ro,noload,nodev,nosuid',str(image),str(mount)])
            states[name]=installed((mount/'var/lib/dpkg/status').read_text())
            if states[name]!=json.loads((Path(data['executor_job'])/'plan.json').read_text())['targets'][name]['final_versions']:raise SpecError('Estado instalado não coincide com lock')
            trees[name]=clean_snapshot(snapshot(mount))
        if states['base'].keys()-states['live'].keys() or any(states['base'][p]!=states['live'][p] for p in states['base']):raise SpecError('Versões base/live incompatíveis')
        # Limite conservador por bytes efetivamente alocados nas views, sem presumir taxa xz.
        required=3*allocated_usage(target/'base')+5*allocated_usage(target/'live')+10*1024**3
        if shutil.disk_usage(job).free<required:raise SpecError('Margem insuficiente para delta, packs e reextrações; preservar inputs')
        delta=recipe(trees['base'],trees['live'])
        (target/'delta-recipe.json').write_text(json.dumps(delta,ensure_ascii=False,indent=2)+'\n')
        delta_root=target/'delta';delta_snapshot=materialize(target/'live',delta_root,delta,EPOCH)
        packed=target/'packed';packed.mkdir();verified={}
        sources={'minimal.squashfs':target/'base','minimal.live.squashfs':delta_root}
        expected={'minimal.squashfs':trees['base'],'minimal.live.squashfs':delta_snapshot}
        for name,source in sources.items():
            output=packed/name;args=compress_args(source,output,expected[name]['.'])
            if name=='minimal.squashfs':args+=['-e','var/lib/devlite-executor']
            runner.run('pack-'+name,args)
            extracted=target/('verify-'+name)
            runner.run('extract-'+name,['unsquashfs','-strict-errors','-processors','1','-data-queue','64','-frag-queue','64','-d',str(extracted),str(output)])
            if snapshot(extracted)!=expected[name]:raise SpecError('Round-trip SquashFS alterou bytes/metadados/hardlinks')
            verified[name]={'sha256':digest(output),'uncompressed_bytes':allocated_usage(extracted),'entries':len(expected[name])}
        # Prova pelo kernel, além da prova por inventários e do round-trip.
        for name in ('base','delta','merged'):(target/('mounted-'+name)).mkdir()
        for name,file in (('base','minimal.squashfs'),('delta','minimal.live.squashfs')):
            runner.run('mount-new-'+name,['mount','-t','squashfs','-o','loop,ro,nodev,nosuid',str(packed/file),str(target/('mounted-'+name))])
        runner.run('mount-new-merged',['mount','-t','overlay','overlay','-o','ro,lowerdir='+str(target/'mounted-delta')+':'+str(target/'mounted-base'),str(target/'mounted-merged')])
        from .release_resume import absent_xattrs
        delta_absence=absent_xattrs(packed/'minimal.live.squashfs',delta_snapshot)
        merged_absence=frozenset(p for p in delta_absence if p in trees['live'] and not trees['live'][p].get('xattrs'))
        if snapshot(target/'mounted-merged',xattr_absence=merged_absence)!=trees['live']:raise SpecError('Base + novo delta não reproduz live integralmente')
        original=ROOT/'work/phase4b1-dhzezpnz/original-casper'
        values=manifests(states['base'],states['live'],(original/'filesystem.manifest').read_text())
        values.update({'minimal.size':str(verified['minimal.squashfs']['uncompressed_bytes'])+'\n','minimal.live.size':str(verified['minimal.live.squashfs']['uncompressed_bytes'])+'\n',
                       'filesystem.size':str(sum(v['uncompressed_bytes'] for v in verified.values()))+'\n'})
        catalog=(original/'install-sources.yaml').read_text()
        import re
        catalog,count=re.subn(r'^  size: [0-9]+$', '  size: '+str(verified['minimal.squashfs']['uncompressed_bytes']),catalog,flags=re.M)
        if count!=1 or 'type: fsimage-layered' not in catalog or 'path: minimal.squashfs' not in catalog:raise SpecError('Catálogo incompatível')
        values['install-sources.yaml']=catalog
        published=job/'published-casper';published.mkdir(mode=0o755)
        for name in verified:shutil.copyfile(packed/name,published/name);(published/name).chmod(0o444)
        for name,value in values.items():(published/name).write_text(value);(published/name).chmod(0o444)
        report.update(status='layers_verified',job_sha256=approval,layers=verified,
                      published=str(published),files={p.name:digest(p) for p in sorted(published.iterdir())},
                      kernel_composition_verified=True,roundtrip_verified=True,reproducibility='recipe determinística sobre inputs selados; segunda construção ainda pendente')
        (job/'layers-ready.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');(job/'layers-ready.json').chmod(0o444)
    except BaseException as error:
        report.update(status='quarantined',error=str(error));raise
    finally:(target/'pack-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return job/'layers-ready.json'
