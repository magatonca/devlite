#!/usr/bin/env python3
"""Geração não privilegiada explicitamente autorizada; restaura o gate em finally."""
import argparse
import json
import os
import signal
import sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pipeline.devlite.release_contract import read
from pipeline.devlite.release_iso import build,reproduce,ready_layers
from pipeline.devlite.release_flow import ordinary
from pipeline.devlite.customize.manifest import SpecError
from pipeline.devlite.runtime import owned_directory


def gate(value):
    path=ROOT/'config/projeto.json';data=json.loads(path.read_text());data['iso_final_autorizada']=value
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')


def run(job,approval,two_builds=False):
    ordinary()
    if os.environ.get('PYTHONHASHSEED')!='0':raise SpecError('Iniciar o processo com PYTHONHASHSEED=0 para ordem determinística')
    job,data=read(job,approval);ready_layers(job,approval)
    flags=json.loads((ROOT/'config/projeto.json').read_text())
    if any(flags.get(k) for k in ('iso_final_autorizada','integracao_camadas_autorizada','executor_autorizado','probe_autorizado')):
        raise SpecError('Há outro gate ativo; não alterar permissões concorrentes')
    control=owned_directory(job,'iso-control-')
    result={'status':'running','job':str(job),'contract_sha256':approval,'two_builds':two_builds,'root_operations':False,'vm_executed':False}
    gate(True)
    try:
        report=build(job,approval);result['first_report']=str(report)
        if two_builds:result['reproducibility_report']=str(reproduce(job,approval,report))
        result['status']='completed'
    except BaseException as error:
        result.update(status='failed_preserved',error=str(error));raise
    finally:
        gate(False);result['iso_gate_restored_false']=True
        (control/'execution.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return control/'execution.json'


def interrupted(signum,frame):raise SpecError('Geração interrompida pelo sinal '+str(signum))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--job',type=Path,required=True);p.add_argument('--approval-sha256',required=True)
    p.add_argument('--two-builds',action='store_true');p.add_argument('--execute-authorized',action='store_true');a=p.parse_args()
    if not a.execute_authorized:p.error('Exige autorização específica do usuário e --execute-authorized')
    signal.signal(signal.SIGTERM,interrupted);signal.signal(signal.SIGHUP,interrupted)
    try:print(run(a.job,a.approval_sha256,a.two_builds))
    except (SpecError,OSError,ValueError) as error:raise SystemExit(str(error))
