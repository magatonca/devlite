"""ISO de pacotes: montagem futura não privilegiada e auditoria estrita."""
import json
import os
import shutil
from pathlib import Path
from .release_contract import ROOT,read,save
from .runtime import Runner,owned_directory,BuildError
from .build import detect,validate_layout,EXPECTED
from .structure import digest,region_digest,compare_boot_metadata
from .validation import inventory,iso_metadata,verify_manifest
from .minimal_build import update_grub,make_md5,compare_iso_trees
from .minimal_root import EPOCH
from .customize.manifest import SpecError

REQUIRED={'minimal.squashfs','minimal.live.squashfs','minimal.size','minimal.live.size','filesystem.size','install-sources.yaml',
          'minimal.manifest','minimal.live.manifest','filesystem.manifest','devlite-base.manifest.full'}


def ready_layers(job,approval):
    file=job/'layers-ready.json'
    if file.is_symlink() or not file.is_file() or file.stat().st_uid!=0 or file.stat().st_mode & 0o022:raise SpecError('Receipt de camadas deve ser root-owned e não gravável por outros')
    receipt=json.loads(file.read_text())
    if receipt.get('job_sha256')!=approval or receipt.get('status')!='layers_verified' or receipt.get('kernel_composition_verified') is not True or receipt.get('roundtrip_verified') is not True:raise SpecError('Camadas sem provas completas')
    published=job/'published-casper'
    if receipt.get('published')!=str(published) or published.is_symlink() or set(receipt.get('files',{}))!=REQUIRED:raise SpecError('Lista de payloads não autorizada')
    for name,sha in receipt['files'].items():
        file=published/name
        if file.is_symlink() or not file.is_file() or digest(file)!=sha:raise SpecError('Payload alterado: '+name)
    return receipt


def audit_iso(runner,source,candidate,workspace,mapped,provenance):
    before_boot=detect(runner,source,'source');after_boot=detect(runner,candidate,'candidate')
    compare_boot_metadata(source,candidate,before_boot,after_boot)
    if after_boot['volume_id']!='DevLite OS 1.0 Experimental':raise BuildError('Rótulo experimental incorreto')
    if before_boot['timestamp']!=after_boot['timestamp']:raise BuildError('UUID de volume mudou')
    if region_digest(source,before_boot['efi_offset'],before_boot['efi_bytes'])!=region_digest(candidate,after_boot['efi_offset'],after_boot['efi_bytes']):raise BuildError('EFI anexada alterada')
    source_tree=workspace/'source-tree';result_tree=workspace/'result-tree'
    for image,target,label in ((source,source_tree,'source'),(candidate,result_tree,'candidate')):
        runner.xorriso(label+'-tree','-osirrox','on','-indev',image,'-extract','/',target)
        validate_layout(target)
    before,after=inventory(source_tree),inventory(result_tree)
    additions=set(provenance)|{'casper/devlite-provenance','casper/devlite-release.json','casper/devlite-base.manifest.full'}
    compare_iso_trees(before,after,source_tree,result_tree,set(mapped),additions,{'casper/SHA256SUMS.gpg'})
    for name,file in {**mapped,**provenance}.items():
        if digest(result_tree/name)!=digest(file):raise BuildError('Arquivo ISO diverge do payload: '+name)
    old=iso_metadata(runner.xorriso('source-metadata','-indev',source,'-find','/','-exec','lsdl','--'))
    new=iso_metadata(runner.xorriso('candidate-metadata','-indev',candidate,'-find','/','-exec','lsdl','--'))
    for name in old.keys() & new.keys():
        if name.lstrip('/') not in set(mapped)|additions|{'boot.catalog'} and old[name]!=new[name]:raise BuildError('Metadados ISO inesperados: '+name)
    for name in set(mapped)|set(provenance):
        value=new['/'+name]
        if value[0]!='-r--r--r--' or value[2:4]!=['0','0']:raise BuildError('UID/GID/modo ISO incorreto')
    md5=verify_manifest(result_tree,Path('md5sum.txt'),'md5');layers=verify_manifest(result_tree,Path('casper/SHA256SUMS'),'sha256')
    runner.run('original-provenance',['gpgv','--homedir',str(ROOT/'sources/verification'),'--keyring',str(ROOT/'sources/verification/trustedkeys.gpg'),
               str(result_tree/'casper/devlite-provenance/original-SHA256SUMS.gpg'),str(result_tree/'casper/devlite-provenance/original-SHA256SUMS')])
    return {'boot_structure':after_boot,'md5_entries':md5,'layer_checksums':layers,'boot_vm':'not_tested','installation_vm':'not_tested'}


def build(job,approval):
    if os.geteuid()==0:raise SpecError('Montar ISO como magaton, sem root')
    job,data=read(job,approval)
    if json.loads((ROOT/'config/projeto.json').read_text()).get('iso_final_autorizada') is not True:raise SpecError('Geração da ISO não autorizada')
    receipt=ready_layers(job,approval)
    source=ROOT/'sources/xubuntu-24.04.5-minimal-amd64.iso'
    if source.is_symlink() or digest(source)!=EXPECTED:raise SpecError('ISO oficial não confere')
    total=sum((job/'published-casper'/name).stat().st_size for name in ('minimal.squashfs','minimal.live.squashfs'))
    if shutil.disk_usage(job).free<2*source.stat().st_size+3*total+10*1024**3:raise SpecError('Sem margem para ISO e auditoria')
    work=owned_directory(job,'iso-');(work/'logs').mkdir();runner=Runner(work/'logs',EPOCH)
    original=ROOT/'work/phase4b1-dhzezpnz/original-casper';grub=ROOT/'work/phase4b1-dhzezpnz/original-grub'
    mapped={'casper/'+name:job/'published-casper'/name for name in REQUIRED}
    generated=work/'updates';generated.mkdir()
    checksum=generated/'SHA256SUMS';checksum.write_text(''.join(receipt['layers'][name]['sha256']+' *'+name+'\n' for name in sorted(receipt['layers'])))
    mapped['casper/SHA256SUMS']=checksum
    notice=generated/'devlite-release.json';save(notice,{'profile':'ubuntu-experimental','external_tools_pending':['Node.js LTS','TypeScript','VS Code'],
            'build_contract_sha256':approval,'signature':'customized checksums unsigned; original signatures archived','boot_installation':'not tested'})
    mapped['casper/devlite-release.json']=notice
    for file in grub.glob('*.cfg'):
        text=file.read_text()
        if 'linux /casper/vmlinuz' in text or '\tlinux\t/casper/vmlinuz' in text:
            rendered,count=update_grub(text);output=generated/file.name;output.write_text(rendered);mapped['boot/grub/'+file.name]=output
    if not {'boot/grub/grub.cfg','boot/grub/loopback.cfg'}<=mapped.keys():raise SpecError('Entradas GRUB incompletas')
    provenance={'casper/devlite-provenance/original-SHA256SUMS':original/'SHA256SUMS','casper/devlite-provenance/original-SHA256SUMS.gpg':original/'SHA256SUMS.gpg'}
    md5=generated/'md5sum.txt';md5.write_text(make_md5((ROOT/'work/phase4b1-dhzezpnz/original-md5sum.txt').read_text(),mapped,provenance));mapped['md5sum.txt']=md5
    output=owned_directory(ROOT/'artifacts','release-');candidate=output/'devlite-os-1.0-ubuntu-experimental.iso.partial'
    boot=detect(runner,source,'original')
    args=['-indev',str(source),'-outdev',str(candidate),'-overwrite','on','-mkdir','/casper/devlite-provenance','--',
          '-mv','/casper/SHA256SUMS.gpg','/casper/devlite-provenance/original-SHA256SUMS.gpg','--']
    for name,file in {**mapped,**provenance}.items():
        args+=['-map',str(file),'/'+name,'-chown','0','/'+name,'--','-chgrp','0','/'+name,'--','-chmod','0444','/'+name,'--','-alter_date','m','='+str(EPOCH),'/'+name,'--']
    args+=['-chown','0','/casper/devlite-provenance','--','-chgrp','0','/casper/devlite-provenance','--','-chmod','0755','/casper/devlite-provenance','--',
           '-alter_date','m','='+str(EPOCH),'/casper/devlite-provenance','--','-assess_indev_features','replay','-boot_image','any','replay',
           '-volid','DevLite OS 1.0 Experimental','-volume_date','uuid',boot['timestamp'],'-end']
    runner.xorriso('assemble',*args)
    validation=audit_iso(runner,source,candidate,work,mapped,provenance)
    if digest(source)!=EXPECTED:raise SpecError('Fonte oficial mudou durante a montagem')
    final=candidate.with_suffix('');candidate.rename(final)
    report={'status':'iso_structurally_verified','iso':str(final),'bytes':final.stat().st_size,'sha256':digest(final),
            'contract_sha256':approval,'validation':validation,'reproducibility':'requires second build of same sealed inputs','full_edition':False}
    save(output/'release-report.json',report);(output/'SHA256SUMS').write_text(report['sha256']+'  '+final.name+'\n')
    return output/'release-report.json'


def reproduce(job,approval,reference_report):
    job,data=read(job,approval)
    reference_report=Path(reference_report)
    if reference_report.is_symlink() or not reference_report.resolve().is_relative_to(ROOT/'artifacts'):raise SpecError('Relatório de referência fora de artifacts')
    reference=json.loads(reference_report.read_text())
    if reference.get('status')!='iso_structurally_verified' or reference.get('contract_sha256')!=approval:raise SpecError('Referência de outro contrato ou não validada')
    original=Path(reference['iso'])
    if original.is_symlink() or not original.resolve().is_relative_to(ROOT/'artifacts') or digest(original)!=reference['sha256']:raise SpecError('Artefato de referência alterado')
    generated=build(job,approval)
    result=json.loads(generated.read_text())
    if result['sha256']!=reference['sha256']:raise SpecError('Reconstrução não foi bit a bit idêntica; preservar saídas para diagnóstico')
    save(generated.parent/'reproducibility.json',{'status':'bit_identical','reference':str(original),'result':result['iso'],'sha256':result['sha256']})
    return generated.parent/'reproducibility.json'
