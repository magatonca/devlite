#!/usr/bin/env python3
"""Coleta dentro do guest DevLite; nunca aprova boot/instalação automaticamente."""
import argparse,hashlib,json,os,pwd,shlex,shutil,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
sys.dont_write_bytecode=True
PROJECT=Path(__file__).resolve().parents[1]
COMMANDS={'php':['php','--version'],'composer':['composer','--no-plugins','--no-scripts','--no-interaction','--version'],
 'apache':['apache2ctl','-t'],'mariadb':['mariadbd','--version'],'docker':['docker','--version'],
 'compose':['docker','compose','version'],'git':['git','--version'],'gh':['gh','--version'],
 'nmap':['nmap','--version'],'wireshark':['wireshark','--version'],'tcpdump':['tcpdump','--version'],
 'iperf3':['iperf3','--version'],'remmina':['remmina','--version'],'ssh':['ssh','-V'],
 'openvpn':['openvpn','--version'],'libreoffice':['libreoffice','--version'],'pdf':['atril','--version'],
 'node':['node','--version'],'typescript':['tsc','--version'],'vscode':['code','--version']}
SERVICES=('apache2.service','mariadb.service','docker.service','docker.socket','containerd.service','iperf3.service')

def identity(root):
    path=root/'usr/share/devlite-os/identity.json'
    if not path.is_file():raise ValueError('Coletor restrito ao guest DevLite; não executar no Ubuntu Server')
    data=json.loads(path.read_text())
    if data.get('name')!='DevLite OS' or data.get('version')!='1.0':raise ValueError('Identidade DevLite 1.0 não confirmada')
    return data

def read(root,name):
    p=root/name
    return p.read_text(errors='replace').strip() if p.is_file() else None

def command(args):
    try:
        p=subprocess.run(args,capture_output=True,text=True,timeout=30)
        return {'argv':args,'returncode':p.returncode,'stdout':p.stdout[-16000:],'stderr':p.stderr[-8000:]}
    except (OSError,subprocess.TimeoutExpired) as error:return {'argv':args,'error':str(error)}

def collect(context,firmware,run_versions=False,root=Path('/')):
    ident=identity(root) # fail before any subprocess on the host
    if os.geteuid()==0:raise ValueError('Executar como usuário normal da sessão XFCE')
    detected='live' if 'boot=casper' in shlex.split(read(root,'proc/cmdline') or '') else 'installed'
    actual='uefi' if (root/'sys/firmware/efi').is_dir() else 'bios'
    if context!=detected or firmware!=actual:raise ValueError('Contexto/firmware inesperado: '+detected+'/'+actual)
    keyboard=read(root,'etc/default/keyboard') or ''
    fields={}
    for line in keyboard.splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            key,value=line.split('=',1);fields[key.strip()]=value.strip().strip('"')
    programs={name:{'binary_present':shutil.which(argv[0]) is not None,'version_check_executed':False} for name,argv in COMMANDS.items()}
    if run_versions:
        for name,argv in COMMANDS.items():
            if programs[name]['binary_present']:programs[name].update(version_check_executed=True,result=command(argv))
    services={name:command(['systemctl','show',name,'--property=LoadState,ActiveState,UnitFileState','--no-pager']) for name in SERVICES}
    return {'schema':1,'captured_utc':datetime.now(timezone.utc).isoformat(),'identity':ident,'context':detected,'firmware':actual,
      'uid':os.getuid(),'user':pwd.getpwuid(os.getuid()).pw_name,'desktop_declared':os.environ.get('XDG_CURRENT_DESKTOP'),
      'language_session':os.environ.get('LANG'),'locale_file':read(root,'etc/locale.conf'),'keyboard_file':fields,
      'timezone_file':read(root,'etc/timezone'),'programs':programs,'services':services,
      'keyboard_actual':command(['setxkbmap','-query']) if shutil.which('setxkbmap') else {'status':'manual_pending'},
      'login_session':command(['loginctl','show-session',os.environ['XDG_SESSION_ID'],'-p','Type','-p','Desktop']) if os.environ.get('XDG_SESSION_ID') else {'status':'manual_pending'},
      'manual_checks':{'boot_observed':'pending_operator_review','installer':'pending','disk_installation':'pending','xfce_visual':'pending','post_install_persistence':'pending','application_functionality':'pending'},
      'practical_approval':False,'service_actions_executed':False,'program_installation_executed':False}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--context',choices=('live','installed'),required=True);p.add_argument('--firmware',choices=('bios','uefi'),required=True)
    p.add_argument('--run-version-checks',action='store_true');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    try:
        data=collect(a.context,a.firmware,a.run_version_checks)
        with a.output.open('x') as stream:json.dump(data,stream,ensure_ascii=False,indent=2);stream.write('\n')
        digest=hashlib.sha256(a.output.read_bytes()).hexdigest()
        with a.output.with_suffix(a.output.suffix+'.sha256').open('x') as stream:stream.write(digest+'  '+a.output.name+'\n')
        print('Coleta registrada; aprovação prática permanece pendente:',a.output)
    except (ValueError,OSError) as error:raise SystemExit(str(error))
