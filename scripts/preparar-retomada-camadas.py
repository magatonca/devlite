#!/usr/bin/env python3
"""Prepara novo contrato sem repetir instalação, probe, mounts ou compressão."""
import argparse
import json
import os
import sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pipeline.devlite.release_contract import CODE,save
from pipeline.devlite.runtime import owned_directory
from pipeline.devlite.structure import digest
from pipeline.devlite.customize.executor_contract import confined
from pipeline.devlite.customize.installation import verify_archives
from pipeline.devlite.customize.manifest import SpecError
from pipeline.devlite.release_flow import ordinary


def prepare(seals):
    ordinary();resume=json.loads(seals.read_text());source=confined(Path(resume['job']))
    if source.parent!=ROOT/'work' or not source.name.startswith('release-'):raise SpecError('Job fonte inválido')
    if digest(source/'release-contract.json')!=resume['contract_sha256']:raise SpecError('Contrato histórico mudou')
    old=json.loads((source/'release-contract.json').read_text());receipt=source/'installation-result.json'
    if receipt.is_symlink() or receipt.stat().st_uid!=0 or receipt.stat().st_mode & 0o022:raise SpecError('Instalação sem atestado protegido')
    installed=json.loads(receipt.read_text())
    if installed.get('status')!='installed_and_audited' or installed.get('contract_sha256')!=resume['contract_sha256'] or installed.get('receipt')!=str(Path(old['executor_job'])/'attempt/accepted-pair.json'):raise SpecError('Instalação não aceita ou de outro contrato')
    executor=confined(old['executor_job']);spec=json.loads((executor/'job.json').read_text())
    if digest(executor/'job.json')!=old['executor_sha256']:raise SpecError('Contrato do executor mudou')
    for name,sha in spec['code_sha256'].items():
        if digest(ROOT/name)!=sha:raise SpecError('Executor mudou: '+name)
    plan=json.loads((executor/'plan.json').read_text())
    if digest(executor/'plan.json')!=spec['plan_sha256']:raise SpecError('Plano mudou')
    cache=ROOT/'work/phase4b5-g78yd2oc/debs';count=verify_archives(plan,cache)
    job=owned_directory(ROOT/'work','release-')
    contract={**old,'job':str(job),'host_mount_namespace':os.readlink('/proc/self/ns/mnt'),
              'code_sha256':{name:digest(ROOT/name) for name in CODE},'resume_packed':resume}
    save(job/'release-contract.json',contract);approval=digest(job/'release-contract.json')
    unit='devlite-pack-'+job.name.removeprefix('release-')
    cmd=['sudo','systemd-run','--unit='+unit,'--wait','--pipe','--collect',
         '--property=MemoryMax=2684354560','--property=MemorySwapMax=1073741824','--property=CPUQuota=100%',
         '--property=TasksMax=128','--property=RuntimeMaxSec=10800','--property=KillMode=control-group',
         '--property=OOMPolicy=kill','unshare','--mount','--propagation','private',
         '/usr/bin/python3',str(ROOT/'scripts/integrar-release-root.py'),'--job',str(job),'--approval-sha256',approval]
    save(job/'command-review.json',{'pack':cmd,'stop':['sudo','systemctl','stop',unit+'.service'],'scope':'Montagens privadas RO + auditoria + publicação; sem APT/extração/compressão/limpeza/ISO',
                                  'cache_files_verified':count,'flags_enabled':False})
    return job,approval

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--seals',type=Path,required=True);a=p.parse_args()
    try:
        job,sha=prepare(a.seals);print(job);print(sha)
    except (SpecError,OSError,ValueError) as error:raise SystemExit(str(error))
