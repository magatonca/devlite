"""Retomada sem APT, extração, compressão ou remoção: audita SquashFS existentes."""
import copy
import json
import os
import shutil
import stat
import struct
import traceback
from pathlib import Path
from .customize.executor_contract import ROOT,confined,accepted_pair
from .customize.installation import installed
from .customize.manifest import SpecError
from .minimal_root import snapshot,allocated_usage,EPOCH
from .release_layers import recipe,clean_snapshot,manifests
from .structure import digest
from .runtime import Runner

LAYERS=('minimal.squashfs','minimal.live.squashfs')


def sealed(path,sha):
    path=confined(Path(path))
    for parent in (path,*path.parents):
        if parent==ROOT:break
        if parent.is_symlink():raise SpecError('Ancestral symlink no input selado')
    info=path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or info.st_mode & 0o022 or digest(path)!=sha:
        raise SpecError('Input root-owned alterado: '+str(path))
    return path


def delta_inventory(plan):
    expected=copy.deepcopy({**plan['directories'],**plan['put']})
    for name in plan['whiteouts']:
        expected[name]={'type':'char','mode':0,'uid':0,'gid':0,'mtime':EPOCH,'xattrs':{},'device':[0,0]}
    return expected


def absent_xattrs(image,expected):
    # SquashFS 4.0 superblock: xattr_id_table_start is little-endian u64 at 56.
    with image.open('rb') as stream:header=stream.read(96)
    if len(header)!=96 or struct.unpack_from('<I',header)[0]!=0x73717368 or struct.unpack_from('<HH',header,28)!=(4,0):
        raise SpecError('Superbloco SquashFS 4.0 inválido')
    used=struct.unpack_from('<Q',header,40)[0];table=struct.unpack_from('<Q',header,56)[0]
    if used<96 or used>image.stat().st_size:raise SpecError('Tamanho de superbloco inválido')
    if table==0xffffffffffffffff:
        if any(value.get('xattrs') for value in expected.values()):raise SpecError('Tabela xattr ausente mas atributos esperados')
        return frozenset(expected)
    if not 96<=table<used:raise SpecError('Offset da tabela xattr inválido')
    return frozenset()


def checked_snapshot(path,expected,label,absence=frozenset()):
    actual=snapshot(path,xattr_absence=absence) if absence else snapshot(path)
    if actual!=expected:
        differences=[p for p in actual.keys()|expected.keys() if actual.get(p)!=expected.get(p)]
        raise SpecError(label+': divergências de conteúdo/metadados: '+str(sorted(differences)[:15]))
    return actual


def run(job,data,approval):
    # Caller has checked root, current contract, explicit gate and private mount namespace.
    resume=data['resume_packed']
    source=confined(Path(resume['job']))
    if source.parent!=ROOT/'work' or not source.name.startswith('release-') or source==job:
        raise SpecError('Origem de retomada inválida')
    # Historical contracts are user-owned: hash-bind without treating them as attestation.
    if (source/'release-contract.json').is_symlink() or digest(source/'release-contract.json')!=resume['contract_sha256']:
        raise SpecError('Contrato histórico mudou')
    historical=json.loads((source/'release-contract.json').read_text())
    if any(historical.get(k)!=data.get(k) for k in ('executor_job','executor_sha256','profile')):
        raise SpecError('Retomada pertence a outro par instalado')
    old_report=sealed(source/'pack-attempt/pack-report.json',resume['report_sha256'])
    if json.loads(old_report.read_text()).get('status')!='quarantined':raise SpecError('Somente tentativa encerrada em quarentena')
    if set(resume['layers'])!=set(LAYERS):raise SpecError('Retomada exige ambas as camadas')
    inputs={name:sealed(source/'pack-attempt/packed'/name,resume['layers'][name]) for name in LAYERS}
    required=sum(p.stat().st_size for p in inputs.values())+10*1024**3
    if shutil.disk_usage(job).free<required:raise SpecError('Sem margem para publicação e auditoria somente leitura')
    attempt=confined(Path(data['executor_job'])/'attempt')
    if attempt.is_symlink() or attempt.stat().st_uid!=0:raise SpecError('Tentativa de instalação não confiável')
    pair=accepted_pair(attempt)
    if pair['job_sha256']!=data['executor_sha256']:raise SpecError('Par aceito de outro executor')
    target=job/'pack-attempt'
    if target.exists() or target.is_symlink():raise SpecError('Não sobrescrever retomada')
    target.mkdir(mode=0o700);(target/'logs').mkdir();runner=Runner(target/'logs',EPOCH)
    report={'status':'running','iso_generated':False,'resumed_from':str(source),'installation_repeated':False,'compression_repeated':False}
    try:
        runner.run('private',['mount','--make-rprivate','/'])
        trees={};states={};plan=json.loads((Path(data['executor_job'])/'plan.json').read_text())
        original=ROOT/'work/phase4b1-dhzezpnz/original-casper'
        # Fail on metadata formatting before the expensive inventory stage.
        manifests(plan['targets']['base']['final_versions'],plan['targets']['live']['final_versions'],(original/'filesystem.manifest').read_text())
        for name in ('base','live'):
            image=attempt/(name+'.ext4');record=pair['results'][name]['image']
            if record['file']!=str(image) or digest(image)!=record['sha256']:raise SpecError('Imagem aceita mudou')
            mount=target/name;mount.mkdir()
            runner.run('mount-'+name,['mount','-t','ext4','-o','loop,ro,noload,nodev,nosuid',str(image),str(mount)])
            states[name]=installed((mount/'var/lib/dpkg/status').read_text())
            if states[name]!=plan['targets'][name]['final_versions']:raise SpecError('Inventário APT diverge do lock')
            trees[name]=clean_snapshot(snapshot(mount))
        if states['base'].keys()-states['live'].keys() or any(states['base'][p]!=states['live'][p] for p in states['base']):
            raise SpecError('Versões Base/Live incompatíveis')
        delta=recipe(trees['base'],trees['live'])
        expected={LAYERS[0]:trees['base'],LAYERS[1]:delta_inventory(delta)}
        verified={};absence_proofs={}
        report['logical_composition_verified']=True
        for name in LAYERS:
            mount=target/('mounted-'+name);mount.mkdir()
            runner.run('mount-'+name,['mount','-t','squashfs','-o','loop,ro,nodev,nosuid',str(inputs[name]),str(mount)])
            absence_proofs[name]=absent_xattrs(inputs[name],expected[name])
            checked_snapshot(mount,expected[name],name,absence_proofs[name])
            verified[name]={'sha256':resume['layers'][name],'entries':len(expected[name]),'uncompressed_bytes':allocated_usage(mount)}
            report['verified_layers']=dict(verified)
        merged=target/'mounted-merged';merged.mkdir()
        runner.run('mount-merged',['mount','-t','overlay','overlay','-o','ro,lowerdir='+str(target/('mounted-'+LAYERS[1]))+':'+str(target/('mounted-'+LAYERS[0])),str(merged)])
        merged_absence=frozenset(p for p in absence_proofs[LAYERS[1]] if p in trees['live'] and not trees['live'][p].get('xattrs'))
        checked_snapshot(merged,trees['live'],'Visão combinada pelo kernel',merged_absence)
        report.update(kernel_composition_verified=True,roundtrip_verified=True)
        original=ROOT/'work/phase4b1-dhzezpnz/original-casper'
        values=manifests(states['base'],states['live'],(original/'filesystem.manifest').read_text())
        for name in LAYERS:values[name.removesuffix('.squashfs')+'.size']=str(verified[name]['uncompressed_bytes'])+'\n'
        values['filesystem.size']=str(sum(v['uncompressed_bytes'] for v in verified.values()))+'\n'
        import re
        catalog,count=re.subn(r'^  size: [0-9]+$','  size: '+str(verified[LAYERS[0]]['uncompressed_bytes']),(original/'install-sources.yaml').read_text(),flags=re.M)
        if count!=1 or 'type: fsimage-layered' not in catalog or 'path: minimal.squashfs' not in catalog:raise SpecError('Catálogo incompatível')
        values['install-sources.yaml']=catalog
        published=job/'published-casper';published.mkdir(mode=0o755)
        for name in LAYERS:
            # Copy only after all comparisons; validate copied bytes again.
            output=published/name
            with inputs[name].open('rb') as incoming,output.open('xb') as outgoing:shutil.copyfileobj(incoming,outgoing)
            output.chmod(0o444)
            if digest(output)!=resume['layers'][name]:raise SpecError('Publicação diverge do input selado')
        for name,value in values.items():(published/name).write_text(value);(published/name).chmod(0o444)
        report.update(status='layers_verified',job_sha256=approval,layers=verified,published=str(published),
                      files={p.name:digest(p) for p in sorted(published.iterdir())},kernel_composition_verified=True,
                      xattr_absence_proof={name:len(paths) for name,paths in absence_proofs.items()},
                      roundtrip_verified=True,roundtrip_method='SquashFS mounted read-only: complete content, metadata, hardlinks and xattrs compared to installed source/delta recipe',
                      reproducibility='second construction pending')
        receipt=job/'layers-ready.json'
        with receipt.open('x') as stream:json.dump(report,stream,ensure_ascii=False,indent=2);stream.write('\n')
        receipt.chmod(0o444)
    except BaseException as error:
        report.update(status='quarantined',error=str(error),traceback=traceback.format_exc());raise
    finally:(target/'pack-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return job/'layers-ready.json'
