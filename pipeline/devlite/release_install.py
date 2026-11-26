"""Operação root única: executor aprovado, resumo público e restauração do gate."""
import json
import os
from .release_contract import ROOT,read,save
from .customize.executor import execute
from .customize.executor_contract import accepted_pair,confined
from .customize.manifest import SpecError


def run(job,approval):
    if os.geteuid()!=0:raise SpecError('Instalação exige root e aprovação específica')
    job,data=read(job,approval)
    config=ROOT/'config/projeto.json'
    settings=json.loads(config.read_text())
    if settings.get('executor_autorizado') is not True:raise SpecError('Instalação não autorizada')
    result=job/'installation-result.json'
    if result.exists() or result.is_symlink():raise SpecError('Não sobrescrever resultado anterior')
    executor=confined(data['executor_job'])
    report={'status':'running','iso_generated':False,'rootfs_integration_executed':False,'contract_sha256':approval}
    try:
        receipt=execute(executor,data['executor_sha256'])
        pair=accepted_pair(executor/'attempt')
        if pair['job_sha256']!=data['executor_sha256']:raise SpecError('Receipt de instalação de outro contrato')
        report.update(status='installed_and_audited',receipt=str(receipt),results=pair['results'],rebase_required=True)
    except BaseException as error:
        report.update(status='quarantined',error=str(error));raise
    finally:
        # Nunca habilita gates. Restaura apenas a permissão desta operação.
        current=json.loads(config.read_text());current['executor_autorizado']=False
        config.write_text(json.dumps(current,ensure_ascii=False,indent=2)+'\n')
        save(result,report);result.chmod(0o444)
    return result
