"""Public candidate assembly; private backend called only by a sealed one-shot controller."""
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
    if after_boot['volume_id']!='DevLite OS 1.0 Candidate':raise BuildError('Rótulo do candidato público incorreto')
    if before_boot['timestamp']!=after_boot['timestamp']:raise BuildError('UUID de volume mudou')
    if region_digest(source,before_boot['efi_offset'],before_boot['efi_bytes'])!=region_digest(candidate,after_boot['efi_offset'],after_boot['efi_bytes']):raise BuildError('EFI anexada alterada')
    source_tree=workspace/'source-tree';result_tree=workspace/'result-tree'
    for image,target,label in ((source,source_tree,'source'),(candidate,result_tree,'candidate')):
        runner.xorriso(label+'-tree','-osirrox','on','-indev',image,'-extract','/',target)
        validate_layout(target)
    before,after=inventory(source_tree),inventory(result_tree)
    additions=set(provenance)|{'casper/devlite-provenance','casper/devlite-release.json','casper/devlite-base.manifest.full','casper/devlite-components.json'}
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


def assemble(job,approval,public_approval):
    if os.geteuid()==0:raise SpecError('Montar ISO como magaton, sem root')
    job,data=read(job,approval)
    public,public_spec=public_inputs(job,public_approval)
    if public['derived_pack_contract_sha256']!=approval:raise SpecError('Contrato de pack diferente do aprovado')
    receipt=ready_layers(job,approval)
    source=ROOT/'sources/xubuntu-24.04.5-minimal-amd64.iso'
    if source.is_symlink() or digest(source)!=EXPECTED:raise SpecError('ISO oficial não confere')
    total=sum((job/'published-casper'/name).stat().st_size for name in ('minimal.squashfs','minimal.live.squashfs'))
    if shutil.disk_usage(job).free<2*source.stat().st_size+3*total+10*1024**3:raise SpecError('Sem margem para ISO e auditoria')
    work=owned_directory(job,'iso-');(work/'logs').mkdir();runner=Runner(work/'logs',EPOCH)
    original=ROOT/'work/phase4b1-dhzezpnz/original-casper';grub=ROOT/'work/phase4b1-dhzezpnz/original-grub'
    mapped={'casper/'+name:job/'published-casper'/name for name in sorted(REQUIRED)}
    generated=work/'updates';generated.mkdir()
    checksum=generated/'SHA256SUMS';checksum.write_text(''.join(receipt['layers'][name]['sha256']+' *'+name+'\n' for name in sorted(receipt['layers'])))
    mapped['casper/SHA256SUMS']=checksum
    notice=generated/'devlite-release.json';save(notice,{'profile':'public-release-candidate','external_tools_pending':[],
            'vscode':'optional official documentation entry; binary not bundled',
            'build_contract_sha256':approval,'application_contract_sha256':public_approval,
            'signature':'customized checksums unsigned; original signatures archived','boot_installation':'not tested','release_approved':False})
    mapped['casper/devlite-release.json']=notice
    components=generated/'devlite-components.json';save(components,public_spec['components'])
    mapped['casper/devlite-components.json']=components
    for file in sorted(grub.glob('*.cfg')):
        text=file.read_text()
        if 'linux /casper/vmlinuz' in text or '\tlinux\t/casper/vmlinuz' in text:
            rendered,count=update_grub(text);output=generated/file.name;output.write_text(rendered);mapped['boot/grub/'+file.name]=output
    if not {'boot/grub/grub.cfg','boot/grub/loopback.cfg'}<=mapped.keys():raise SpecError('Entradas GRUB incompletas')
    provenance={'casper/devlite-provenance/original-SHA256SUMS':original/'SHA256SUMS','casper/devlite-provenance/original-SHA256SUMS.gpg':original/'SHA256SUMS.gpg'}
    md5=generated/'md5sum.txt';md5.write_text(make_md5((ROOT/'work/phase4b1-dhzezpnz/original-md5sum.txt').read_text(),mapped,provenance));mapped['md5sum.txt']=md5
    output=owned_directory(ROOT/'artifacts','release-');candidate=output/'devlite-os-1.0-amd64.iso.partial'
    boot=detect(runner,source,'original')
    args=['-indev',str(source),'-outdev',str(candidate),'-overwrite','on','-mkdir','/casper/devlite-provenance','--',
          '-mv','/casper/SHA256SUMS.gpg','/casper/devlite-provenance/original-SHA256SUMS.gpg','--']
    for name,file in {**mapped,**provenance}.items():
        args+=['-map',str(file),'/'+name,'-chown','0','/'+name,'--','-chgrp','0','/'+name,'--','-chmod','0444','/'+name,'--','-alter_date','m','='+str(EPOCH),'/'+name,'--']
    args+=['-chown','0','/casper/devlite-provenance','--','-chgrp','0','/casper/devlite-provenance','--','-chmod','0755','/casper/devlite-provenance','--',
           '-alter_date','m','='+str(EPOCH),'/casper/devlite-provenance','--','-assess_indev_features','replay','-boot_image','any','replay',
           '-volid','DevLite OS 1.0 Candidate','-volume_date','uuid',boot['timestamp'],'-end']
    runner.xorriso('assemble',*args)
    validation=audit_iso(runner,source,candidate,work,mapped,provenance)
    if digest(source)!=EXPECTED:raise SpecError('Fonte oficial mudou durante a montagem')
    final=candidate.with_suffix('');candidate.rename(final)
    report={'status':'iso_structurally_verified','iso':str(final),'bytes':final.stat().st_size,'sha256':digest(final),
            'contract_sha256':approval,'validation':validation,'reproducibility':'not tested in this single-candidate operation','profile':'public-release-candidate','application_contract_sha256':public_approval,'release_approved':False}
    save(output/'release-report.json',report);(output/'SHA256SUMS').write_text(report['sha256']+'  '+final.name+'\n')
    return output/'release-report.json'



def trusted_report(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_uid!=0 or path.stat().st_mode&0o022:
        raise SpecError('Exige recibo root-owned não gravável por outros: '+path.name)
    return json.loads(path.read_text())

def public_inputs(job,approval):
    from .public_execution import read as public_read
    job,spec=public_read(job,approval)
    if spec['operation']!='apply-and-pack':raise SpecError('Não aceitar job de diagnóstico como aplicação')
    report=trusted_report(job/'public-result.json')
    if report.get('status')!='public_layers_verified' or report.get('public_contract_sha256')!=approval:
        raise SpecError('Aplicação pública não aprovada')
    if report.get('host_critical_unchanged') is not True or report.get('host_permissions_unchanged') is not True or report.get('cleanup_errors')!=[]:
        raise SpecError('Host ou limpeza da aplicação não comprovados')
    if report.get('target_programs_executed') is not False or report.get('iso_generated') is not False:
        raise SpecError('Receipt excedeu escopo autorizado')
    if set(report.get('results',{}))!={'base','live'}:raise SpecError('Par público incompleto')
    for name,value in report['results'].items():
        if value.get('status')!='validated' or value.get('file_audit',{}).get('only_declared_additions') is not True:
            raise SpecError('Auditoria pública não aprovada: '+name)
    expected=job/'layers-ready.json'
    if report.get('layers_receipt')!=str(expected) or digest(expected)!=report.get('layers_receipt_sha256'):
        raise SpecError('Receipt de camadas diverge da aplicação')
    derived=report['derived_pack_contract_sha256'];read(job,derived);ready_layers(job,derived)
    return report,spec
