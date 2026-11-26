"""Matriz de aceitação e verificação documental; nunca inicia VM ou executa apps."""
import hashlib
import json
from .customize.manifest import SpecError

CHECKS=('disco_descartavel','hash_iso','boot_live','firmware_live','xfce_live','pt_br_live','abnt2_live','timezone_live',
        'programas_live','servicos_bloqueados_live','instalador_preservado','instalacao','boot_sem_iso','firmware_instalado',
        'xfce_instalado','pt_br_instalado','abnt2_instalado','timezone_instalado','programas_instalados','servicos_bloqueados_instalado','persistencia_reboot','desligamento','writer_calc_impress','pdf_visual','remmina_visual','vpn_networkmanager','wireshark_capture_policy','docker_ativacao_manual','php_extensoes')
PROGRAMS={'php':['php','--version'],'composer':['composer','--version'],'apache':['apache2ctl','-t'],'mariadb':['mariadbd','--version'],
          'docker':['docker','--version'],'compose':['docker','compose','version'],'git':['git','--version'],'gh':['gh','--version'],
          'nmap':['nmap','--version'],'wireshark':['wireshark','--version'],'tcpdump':['tcpdump','--version'],'iperf3':['iperf3','--version'],
          'remmina':['remmina','--version'],'ssh':['ssh','-V'],'openvpn':['openvpn','--version'],'libreoffice':['libreoffice','--version'],
          'pdf':['atril','--version'],'node':['node','--version'],'typescript':['tsc','--version'],'vscode':['code','--version']}
EXTERNAL={'node','typescript','vscode'}


def template():
    return {'schema':1,'iso':{'path':'','sha256':'','experimental':True},'profile':'full-edition',
            'runs':{mode:{'vm_id':'','virtual_disk_id':'','disk_disposable':False,'firmware':mode,'environment':{'operator':'','date':'','hypervisor':'','ram_mib':4096,'cpu':2,'disk_gib':40,'secure_boot':False},
                           'checks':{name:{'status':'pending','evidence':[]} for name in CHECKS},
                           'programs':{context:{name:{'status':'pending','version':'','evidence':[]} for name in PROGRAMS} for context in ('live','installed')}} for mode in ('bios','uefi')}}


def validate(report,iso_hash,evidence_root):
    errors=[]
    if not isinstance(report,dict):return ['Relatório deve ser objeto JSON']
    if report.get('schema')!=1 or report.get('profile') not in ('full-edition','ubuntu-experimental'):return ['Schema/perfil inválido']
    if not isinstance(report.get('iso'),dict) or report['iso'].get('sha256')!=iso_hash:errors.append('ISO/SHA-256 não coincide com artefato revisado')
    runs=report.get('runs',{})
    if not isinstance(runs,dict) or set(runs)!={'bios','uefi'}:return errors+['Execuções BIOS/UEFI independentes obrigatórias']
    def proof(items):
        if not isinstance(items,list) or not items:return False
        for value in items:
            if not isinstance(value,dict):return False
            if not isinstance(value.get('path'),str):return False
            path=evidence_root/value['path']
            if path.is_symlink() or not path.resolve().is_relative_to(evidence_root.resolve()) or not path.is_file():return False
            with path.open('rb') as stream:
                if hashlib.file_digest(stream,'sha256').hexdigest()!=value.get('sha256'):return False
        return True
    for mode,run in runs.items():
        if not isinstance(run,dict):errors.append(mode+': execução inválida');continue
        if not run.get('vm_id') or not run.get('virtual_disk_id') or run.get('disk_disposable') is not True or run.get('firmware')!=mode:errors.append(mode+': VM/disco/firmware não comprovados')
        env=run.get('environment',{})
        if not isinstance(env,dict):env={}
        if any(not env.get(field) for field in ('operator','date','hypervisor')):errors.append(mode+': ambiente incompleto')
        for check in CHECKS:
            checks=run.get('checks',{})
            value=checks.get(check,{}) if isinstance(checks,dict) else {}
            if not isinstance(value,dict):value={}
            if value.get('status')!='passed' or not proof(value.get('evidence')):errors.append(mode+'/'+check+': pendente ou sem arquivo de evidência íntegro')
        required=set(PROGRAMS)-(EXTERNAL if report['profile']=='ubuntu-experimental' else set())
        for context in ('live','installed'):
            for name in required:
                programs=run.get('programs',{})
                values=programs.get(context,{}) if isinstance(programs,dict) else {}
                value=values.get(name,{}) if isinstance(values,dict) else {}
                if not isinstance(value,dict):value={}
                if value.get('status')!='passed' or not value.get('version') or not proof(value.get('evidence')):errors.append(mode+'/'+context+'/'+name+': pendente')
    if not all(isinstance(run,dict) for run in runs.values()):return errors
    if runs['bios'].get('vm_id')==runs['uefi'].get('vm_id') or runs['bios'].get('virtual_disk_id')==runs['uefi'].get('virtual_disk_id'):errors.append('VMs e discos devem ser distintos')
    return errors
