"""One authorized public ISO candidate, without persistent gates or root."""
import hashlib,json,os,shutil
from pathlib import Path
from .release_contract import ROOT,save
from .public_execution import CODE as APP_CODE
from .public_iso import public_inputs,assemble,REQUIRED
from .structure import digest
from .runtime import owned_directory
from .build import EXPECTED,NAME
from .customize.executor_contract import confined
from .customize.manifest import SpecError
CODE=tuple(sorted(set(APP_CODE+('pipeline/devlite/public_iso.py','pipeline/devlite/public_iso_control.py','scripts/gerar-iso-publica.py'))))
REFS=('work/phase4b1-dhzezpnz/original-md5sum.txt','work/phase4b1-dhzezpnz/original-casper/SHA256SUMS',
      'work/phase4b1-dhzezpnz/original-casper/SHA256SUMS.gpg','sources/verification/trustedkeys.gpg')
def ordinary():
 if os.getuid()!=1000 or os.geteuid()==0:raise SpecError('ISO pública somente como magaton')
def prepare(application,approval):
 ordinary();application=confined(application)
 public,spec=public_inputs(application,approval)
 original=ROOT/'sources'/NAME
 refs=list(REFS)+[str(p.relative_to(ROOT)) for p in sorted((ROOT/'work/phase4b1-dhzezpnz/original-grub').glob('*.cfg'))]
 job=owned_directory(ROOT/'work','public-iso-')
 contract={'schema':1,'job':str(job),'operation':'single-public-candidate','application_job':str(application),
           'application_sha256':approval,'public_result_sha256':digest(application/'public-result.json'),
           'pack_contract_sha256':public['derived_pack_contract_sha256'],
           'layers_receipt_sha256':digest(application/'layers-ready.json'),
           'payload_sha256':json.loads((application/'layers-ready.json').read_text())['files'],
           'source_sha256':EXPECTED,'source_bytes':original.stat().st_size,
           'reference_sha256':{p:digest(ROOT/p) for p in refs},'code_sha256':{p:digest(ROOT/p) for p in CODE},
           'build_count':1,'root_operations':False,'vm_execution':False,'volume_id':'DevLite OS 1.0 Candidate',
           'target_name':'devlite-os-1.0-amd64.iso'}
 save(job/'iso-contract.json',contract);return job,digest(job/'iso-contract.json')
def read(job,approval):
 job=confined(job)
 if job.parent!=ROOT/'work' or not job.name.startswith('public-iso-') or job.is_symlink():raise SpecError('Job ISO fora do escopo')
 path=job/'iso-contract.json'
 if path.is_symlink() or digest(path)!=approval:raise SpecError('Contrato ISO alterado')
 data=json.loads(path.read_text())
 if data.get('schema')!=1 or data.get('job')!=str(job) or data.get('operation')!='single-public-candidate' or data.get('build_count')!=1:raise SpecError('Contrato não é candidato único')
 if data.get('root_operations') is not False or data.get('vm_execution') is not False or data.get('volume_id')!='DevLite OS 1.0 Candidate' or data.get('target_name')!='devlite-os-1.0-amd64.iso':raise SpecError('Escopo ISO divergente')
 if set(data.get('code_sha256',{}))!=set(CODE) or any(digest(ROOT/p)!=h for p,h in data['code_sha256'].items()):raise SpecError('Código ISO mudou após revisão')
 refs=data.get('reference_sha256',{})
 if not set(REFS)<=set(refs) or any(Path(p).is_absolute() or '..' in Path(p).parts for p in refs) or any(digest(ROOT/p)!=h for p,h in refs.items()):raise SpecError('Referências da ISO alteradas')
 if data.get('source_sha256')!=EXPECTED:raise SpecError('Fonte oficial divergente')
 return job,data
def inputs(data):
 application=confined(data['application_job'])
 public,spec=public_inputs(application,data['application_sha256'])
 if digest(application/'public-result.json')!=data['public_result_sha256'] or digest(application/'layers-ready.json')!=data['layers_receipt_sha256']:raise SpecError('Recibos mudaram após selagem')
 if public['derived_pack_contract_sha256']!=data['pack_contract_sha256']:raise SpecError('Outro contrato de pack')
 files=json.loads((application/'layers-ready.json').read_text())['files']
 if files!=data['payload_sha256'] or set(files)!=REQUIRED:raise SpecError('Outro conjunto de camadas')
 return application,public,spec
def claim(job,approval):
 save(job/'single-build-claimed.json',{'contract_sha256':approval,'build_count':1,'automatic_retry':False})
def run(job,approval,authorized=False):
 ordinary()
 if not authorized:raise SpecError('Exige aprovação específica para gerar a ISO')
 if os.environ.get('PYTHONHASHSEED')!='0':raise SpecError('Exige PYTHONHASHSEED=0')
 job,data=read(job,approval);application,public,spec=inputs(data)
 original=ROOT/'sources'/NAME
 if original.is_symlink() or original.stat().st_size!=data['source_bytes'] or digest(original)!=EXPECTED:raise SpecError('ISO original não confere')
 flags=json.loads((ROOT/'config/projeto.json').read_text())
 if any(value for value in flags.values() if isinstance(value,bool)):raise SpecError('Outro gate ativo')
 # assemble independently checks the same conservative disk formula.
 total=sum((application/'published-casper'/p).stat().st_size for p in ('minimal.squashfs','minimal.live.squashfs'))
 if shutil.disk_usage(job).free<2*original.stat().st_size+3*total+10*1024**3:raise SpecError('Margem de disco insuficiente')
 claim(job,approval)
 report={'status':'running','iso_contract_sha256':approval,'application_contract_sha256':data['application_sha256'],'build_count':1,'root_operations':False,'vm_executed':False,'release_approved':False}
 try:
  generated=assemble(application,data['pack_contract_sha256'],data['application_sha256'])
  inputs(data)
  if digest(original)!=EXPECTED:raise SpecError('ISO fonte mudou')
  report.update(status='candidate_structurally_verified',release_report=str(generated),release_report_sha256=digest(generated))
 except BaseException as error:
  report.update(status='failed_preserved',error=str(error));raise
 finally:
  current=json.loads((ROOT/'config/projeto.json').read_text())
  report['permission_flags_unchanged']=current==flags
  if current!=flags:report.update(status='failed_preserved',error='Project configuration changed during generation')
  save(job/'execution.json',report)
 if not report['permission_flags_unchanged']:raise SpecError('Configuração mudou durante geração; investigar antes de aceitar')
 return job/'execution.json'
