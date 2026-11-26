"""Perfil público: Node/TS obrigatórios; VS Code apenas entrada opcional."""
import copy,hashlib
from pathlib import Path
from .release_acceptance import template as baseline_template,validate as baseline_validate
PUBLIC_CHECKS=('branding_xfce','vscode_optional_entry','devlite_control_admin','licenses_and_notices')

def template():
    data=baseline_template();data['profile']='public-release';data['iso']['experimental']=False;data['release_state']='candidate_not_generated';data['release_policy']={'vscode_binary_bundled':False,'vscode_entry':'official installation documentation; explicit user click','node_typescript_bundled':True}
    for run in data['runs'].values():
        for name in PUBLIC_CHECKS:run['checks'][name]={'status':'pending','evidence':[]}
    return data

def proof(items,root):
    if not isinstance(items,list) or not items:return False
    for item in items:
        if not isinstance(item,dict) or not isinstance(item.get('path'),str):return False
        relative=Path(item['path']);path=root/relative
        if relative.is_absolute() or path.is_symlink() or not path.resolve().is_relative_to(root.resolve()) or not path.is_file():return False
        try:
            with path.open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
        except OSError:return False
        if actual!=item.get('sha256'):return False
    return True

def validate(report,iso_sha256,evidence_root):
    if not isinstance(report,dict) or report.get('profile')!='public-release':return ['Perfil public-release obrigatório']
    policy=report.get('release_policy',{})
    if not isinstance(policy,dict) or policy.get('vscode_binary_bundled') is not False or policy.get('node_typescript_bundled') is not True:return ['Política pública incompatível']
    base=copy.deepcopy(report);base['profile']='ubuntu-experimental'
    errors=baseline_validate(base,iso_sha256,evidence_root)
    runs=report.get('runs',{})
    if not isinstance(runs,dict):return errors
    for firmware,run in runs.items():
        if not isinstance(run,dict):continue
        for name in PUBLIC_CHECKS:
            value=run.get('checks',{}).get(name,{}) if isinstance(run.get('checks'),dict) else {}
            if not isinstance(value,dict) or value.get('status')!='passed' or not proof(value.get('evidence'),evidence_root):errors.append(firmware+'/'+name+': pendente')
        for context in ('live','installed'):
            programs=run.get('programs',{});values=programs.get(context,{}) if isinstance(programs,dict) else {}
            if not isinstance(values,dict):values={}
            for name in ('node','typescript'):
                value=values.get(name,{})
                if not isinstance(value,dict) or value.get('status')!='passed' or not value.get('version') or not proof(value.get('evidence'),evidence_root):errors.append(firmware+'/'+context+'/'+name+': pendente')
    return errors
