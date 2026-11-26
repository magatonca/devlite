#!/usr/bin/env python3
"""Single non-root candidate from verified Modern layers; explicit approval required."""
import argparse,hashlib,json,os,shutil,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pipeline.devlite.runtime import owned_directory,Runner
from pipeline.devlite.public_iso import REQUIRED,ready_layers,audit_iso
from pipeline.devlite.minimal_root import EPOCH
from pipeline.devlite.build import EXPECTED,NAME,detect
from pipeline.devlite.minimal_build import update_grub,make_md5
ENTRY='scripts/gerar-iso-modern-controlada.py'
RESERVE=20*1024**3
REFS=['work/phase4b1-dhzezpnz/original-md5sum.txt','work/phase4b1-dhzezpnz/original-casper/SHA256SUMS','work/phase4b1-dhzezpnz/original-casper/SHA256SUMS.gpg','sources/verification/trustedkeys.gpg','work/release-cezaiofx/public-contract.json']
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ordinary():
 if os.getuid()!=1000 or os.geteuid()==0:raise ValueError('Run as magaton')
def save(p,value):
 with p.open('x') as f:json.dump(value,f,indent=2);f.write('\n')
def layers(job,approval):
 from pipeline.devlite.customize.executor_contract import confined
 job=confined(job)
 if job.parent!=ROOT/'work' or not job.name.startswith('modern-pack-') or sha(job/'contract.json')!=approval:raise ValueError('Pack contract mismatch')
 d=json.loads((job/'contract.json').read_text())
 if d.get('operation')!='modern-layered-pack-v1':raise ValueError('Wrong pack profile')
 if any(sha(ROOT/n)!=h for n,h in d['code_sha256'].items()):raise ValueError('Pack code changed')
 receipt=ready_layers(job,approval)
 if receipt.get('host_critical_unchanged') is not True or receipt.get('source_metadata_unchanged') is not True or receipt.get('iso_generated') is not False:raise ValueError('Incomplete pack evidence')
 report=job/'pack-report.json';s=report.lstat();r=json.loads(report.read_text())
 if report.is_symlink() or s.st_uid!=0 or s.st_mode&0o022 or r.get('status')!='layers_verified' or r.get('cleanup_errors'):raise ValueError('Pack cleanup incomplete')
 return job,d,receipt

def prepare(pack,approval):
 ordinary();pack,d,receipt=layers(pack,approval)
 job=owned_directory(ROOT/'work','modern-iso-')
 refs=REFS+[str(p.relative_to(ROOT)) for p in (ROOT/'work/phase4b1-dhzezpnz/original-grub').glob('*.cfg')]
 contract={'operation':'single-modern-candidate-v1','job':str(job),'pack_job':str(pack),'pack_sha256':approval,
 'layers_receipt_sha256':sha(pack/'layers-ready.json'),'files_sha256':receipt['files'],'code_sha256':{**d['code_sha256'],ENTRY:sha(ROOT/ENTRY)},
 'references_sha256':{n:sha(ROOT/n) for n in refs},'source_sha256':EXPECTED,'build_count':1,'reserve_bytes':RESERVE,'root_operations':False,'vm_execution':False}
 save(job/'contract.json',contract);h=sha(job/'contract.json');print(job);print(h)

def run(job,approval,authorized):
 ordinary()
 if not authorized or os.environ.get('PYTHONHASHSEED')!='0':raise ValueError('Explicit approval and PYTHONHASHSEED=0 required')
 from pipeline.devlite.customize.executor_contract import confined
 job=confined(job)
 if job.parent!=ROOT/'work' or not job.name.startswith('modern-iso-') or sha(job/'contract.json')!=approval:raise ValueError('ISO contract mismatch')
 d=json.loads((job/'contract.json').read_text())
 if d['job']!=str(job) or d['operation']!='single-modern-candidate-v1' or d['build_count']!=1 or d['reserve_bytes']!=RESERVE or d['root_operations'] is not False or d['vm_execution'] is not False or d['source_sha256']!=EXPECTED:raise ValueError('ISO scope changed')
 if any(sha(ROOT/n)!=h for n,h in d['code_sha256'].items()) or any(sha(ROOT/n)!=h for n,h in d['references_sha256'].items()):raise ValueError('Code/references changed')
 pack,packdata,receipt=layers(Path(d['pack_job']),d['pack_sha256'])
 if sha(pack/'layers-ready.json')!=d['layers_receipt_sha256'] or receipt['files']!=d['files_sha256']:raise ValueError('Published layers changed')
 original=ROOT/'sources'/NAME
 if original.is_symlink() or sha(original)!=EXPECTED:raise ValueError('Original ISO differs')
 total=sum((pack/'published-casper'/n).stat().st_size for n in ('minimal.squashfs','minimal.live.squashfs'))
 required=2*original.stat().st_size+3*total+RESERVE
 if shutil.disk_usage(job).free<required:raise ValueError('ISO budget insufficient')
 gates=(ROOT/'config/projeto.json').read_bytes()
 if any(x for x in json.loads(gates).values() if isinstance(x,bool)):raise ValueError('Conflicting gates active')
 save(job/'single-build-claimed.json',{'contract_sha256':approval,'build_count':1})
 (job/'logs').mkdir();runner=Runner(job/'logs',EPOCH);updates=job/'updates';updates.mkdir()
 output=owned_directory(ROOT/'artifacts','modern-release-');candidate=output/'devlite-os-1.0-amd64.iso.partial'
 report={'status':'running','contract_sha256':approval,'build_count':1,'root_operations':False,'release_approved':False}
 try:
  mapped={'casper/'+n:pack/'published-casper'/n for n in REQUIRED}
  checksum=updates/'SHA256SUMS';checksum.write_text(''.join(receipt['layers'][n]['sha256']+' *'+n+'\n' for n in sorted(receipt['layers'])));mapped['casper/SHA256SUMS']=checksum
  notice=updates/'devlite-release.json';save(notice,{'profile':'modern-single-candidate','modern_contract_sha256':receipt['modern_contract_sha256'],'pack_contract_sha256':d['pack_sha256'],'iso_contract_sha256':approval,'browser':'native Epiphany','control':'homologated 1.0; 2.0 deferred to 1.1','adminer':'deferred to 1.1 per user decision','vscode':'optional; binary excluded','boot_installation':'not tested for this composition','release_approved':False,'customized_checksums':'unsigned; original signatures preserved separately'});mapped['casper/devlite-release.json']=notice
  components=updates/'devlite-components.json';save(components,{'previous_public_components':json.loads((ROOT/'work/release-cezaiofx/public-contract.json').read_text())['components'],'modern':True,'browser':'native Epiphany','control2':False,'adminer':False,'vscode_binary':False});mapped['casper/devlite-components.json']=components
  grub=ROOT/'work/phase4b1-dhzezpnz/original-grub'
  for file in grub.glob('*.cfg'):
   text=file.read_text()
   if 'linux /casper/vmlinuz' in text or '\tlinux\t/casper/vmlinuz' in text:
    value,count=update_grub(text);dest=updates/file.name;dest.write_text(value);mapped['boot/grub/'+file.name]=dest
  if not {'boot/grub/grub.cfg','boot/grub/loopback.cfg'}<=set(mapped):raise ValueError('GRUB entries incomplete')
  source=ROOT/'work/phase4b1-dhzezpnz/original-casper';provenance={'casper/devlite-provenance/original-SHA256SUMS':source/'SHA256SUMS','casper/devlite-provenance/original-SHA256SUMS.gpg':source/'SHA256SUMS.gpg'}
  md5=updates/'md5sum.txt';md5.write_text(make_md5((ROOT/REFS[0]).read_text(),mapped,provenance));mapped['md5sum.txt']=md5
  boot=detect(runner,original,'original')
  args=['-indev',str(original),'-outdev',str(candidate),'-overwrite','on','-mkdir','/casper/devlite-provenance','--','-mv','/casper/SHA256SUMS.gpg','/casper/devlite-provenance/original-SHA256SUMS.gpg','--']
  for name,file in {**mapped,**provenance}.items():args+=['-map',str(file),'/'+name,'-chown','0','/'+name,'--','-chgrp','0','/'+name,'--','-chmod','0444','/'+name,'--','-alter_date','m','='+str(EPOCH),'/'+name,'--']
  args+=['-chown','0','/casper/devlite-provenance','--','-chgrp','0','/casper/devlite-provenance','--','-chmod','0755','/casper/devlite-provenance','--','-alter_date','m','='+str(EPOCH),'/casper/devlite-provenance','--','-assess_indev_features','replay','-boot_image','any','replay','-volid','DevLite OS 1.0 Candidate','-volume_date','uuid',boot['timestamp'],'-end']
  runner.xorriso('assemble',*args)
  checks=audit_iso(runner,original,candidate,job,mapped,provenance)
  if sha(original)!=EXPECTED or (ROOT/'config/projeto.json').read_bytes()!=gates:raise ValueError('Source/config changed')
  layers(pack,d['pack_sha256']);final=candidate.with_suffix('');candidate.rename(final)
  report.update(status='iso_structurally_verified',iso=str(final),bytes=final.stat().st_size,sha256=sha(final),validation=checks,free_bytes=shutil.disk_usage(job).free)
  save(output/'release-report.json',report);(output/'SHA256SUMS').write_text(report['sha256']+'  '+final.name+'\n')
 except BaseException as e:report.update(status='failed_preserved',error=str(e));raise
 finally:save(job/'execution.json',report)
 return job/'execution.json'
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--prepare',action='store_true');ap.add_argument('--pack-job',type=Path);ap.add_argument('--pack-sha256');ap.add_argument('--job',type=Path);ap.add_argument('--approval-sha256');ap.add_argument('--execute-authorized',action='store_true');a=ap.parse_args()
 if a.prepare:prepare(a.pack_job,a.pack_sha256)
 else:print(run(a.job,a.approval_sha256,a.execute_authorized))
