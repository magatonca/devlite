"""Contrato imutável da preparação integrada, sem autorização implícita."""
import json
from pathlib import Path
from .customize.executor_contract import ROOT,confined
from .customize.manifest import SpecError
from .structure import digest

CODE=('pipeline/devlite/release_resume.py','scripts/instalar-release-root.py','pipeline/devlite/release_install.py','scripts/devlite-release.py','scripts/integrar-release-root.py',
      'pipeline/devlite/release_contract.py','pipeline/devlite/release_flow.py','pipeline/devlite/release_layers.py',
      'pipeline/devlite/release_pack.py','pipeline/devlite/release_iso.py','pipeline/devlite/release_acceptance.py',
      'pipeline/devlite/minimal_root.py','pipeline/devlite/minimal_build.py','pipeline/devlite/build.py',
      'pipeline/devlite/structure.py','pipeline/devlite/validation.py','pipeline/devlite/runtime.py',
      'pipeline/devlite/customize/executor_contract.py','pipeline/devlite/customize/installation.py',
      'pipeline/devlite/customize/manifest.py','pipeline/devlite/customize/executor.py','pipeline/devlite/customize/executor_worker.py',
      'pipeline/devlite/customize/guest_runner.py','pipeline/devlite/customize/isolation_validation.py','pipeline/devlite/customize/service_profiles.py')


def save(path,value):
    with path.open('x') as stream:json.dump(value,stream,ensure_ascii=False,indent=2);stream.write('\n')


def read(job,approval):
    job=confined(job)
    if job.parent!=ROOT/'work' or not job.name.startswith('release-'):raise SpecError('Job integrado fora do escopo')
    path=job/'release-contract.json'
    if path.is_symlink() or digest(path)!=approval:raise SpecError('Contrato integrado alterado')
    data=json.loads(path.read_text())
    if data.get('schema')!=1 or data.get('job')!=str(job) or set(data.get('code_sha256',{}))!=set(CODE):raise SpecError('Contrato integrado incompleto')
    for name,sha in data['code_sha256'].items():
        if digest(ROOT/name)!=sha:raise SpecError('Código mudou depois da revisão: '+name)
    return job,data
