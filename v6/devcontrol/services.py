"""Fixed service IDs, read-only queries and authenticated administration."""
import json,os,re,stat,subprocess,time
from pathlib import Path
ACTIONS=frozenset(('start','stop','restart','enable','disable'))
FIXED={'apache':('Apache2','apache2.service'),'mariadb':('MariaDB','mariadb.service'),'docker':('Docker','docker.service'),'ssh':('SSH','ssh.service'),'docker-socket':('Socket Docker','docker.socket'),'containerd':('Containerd','containerd.service'),'ssh-socket':('Socket SSH','ssh.socket')}
ENV={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LANG':'C.UTF-8','LC_ALL':'C.UTF-8','SYSTEMD_PAGER':'cat','SYSTEMD_COLORS':'0'}
class ServiceError(ValueError):pass

def identity(root):
 try:data=json.loads((root/'usr/share/devlite-os/identity.json').read_text())
 except (ValueError,OSError) as e:raise ServiceError('Somente no DevLite OS') from e
 if data.get('name')!='DevLite OS':raise ServiceError('Identidade não reconhecida')

def trusted_profile(p,root):
 try:
  if not stat.S_ISREG(p.lstat().st_mode):return False
  for q in [p,*p.parents]:
   if q==root:break
   s=q.lstat()
   if s.st_uid!=0 or s.st_mode&0o022 or stat.S_ISLNK(s.st_mode):return False
  return True
 except OSError:return False

def catalog(root=Path('/')):
 rows=[{'id':key,'label':label,'unit':unit} for key,(label,unit) in FIXED.items()]
 for p in sorted((root/'etc/openvpn/client').glob('*.conf')):
  name=p.stem
  if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}',name) and '..' not in name and trusted_profile(p,root):rows.append({'id':'openvpn:'+name,'label':'OpenVPN: '+name,'unit':'openvpn-client@'+name+'.service'})
 try:text=(root/'var/lib/dpkg/status').read_text()
 except OSError:text=''
 for block in text.split('\n\n'):
  fields=dict(line.split(': ',1) for line in block.splitlines() if ': ' in line and not line.startswith(' '));m=re.fullmatch(r'php([0-9]+\.[0-9]+)-fpm',fields.get('Package',''))
  if m and fields.get('Status')=='install ok installed':rows.append({'id':'php:'+m[1],'label':'PHP '+m[1]+' FPM','unit':'php'+m[1]+'-fpm.service'})
 return rows

def resolve(service,root):
 for row in catalog(root):
  if row['id']==service:return row['unit']
 raise ServiceError('Serviço/perfil não instalado ou fora da lista permitida')

def call(args,runner=subprocess.run):
 try:p=runner(['/usr/bin/systemctl','--no-ask-password',*args],capture_output=True,text=True,timeout=15 if args[0]=="show" else 60,env=ENV,shell=False,stdin=subprocess.DEVNULL)
 except subprocess.TimeoutExpired as e:raise ServiceError('Tempo limite excedido; consultar estado antes de repetir') from e
 except OSError as e:raise ServiceError('Systemd indisponível') from e
 if p.returncode:raise ServiceError(f'O systemd recusou a operação (código {p.returncode}).')
 return p.stdout[:16384]

def query(unit,runner=subprocess.run):
 try:return dict(line.split('=',1) for line in call(['show',unit,'--property=LoadState,ActiveState,SubState,UnitFileState,Result','--no-pager'],runner).splitlines() if '=' in line)
 except ServiceError as e:return {'LoadState':'unknown','ActiveState':'unknown','UnitFileState':'unknown','error':str(e)}

def snapshot(root=Path('/'),runner=subprocess.run):
 identity(root);return [dict(row,**query(row['unit'],runner)) for row in catalog(root)]

def admin(action,service,root=Path('/'),runner=subprocess.run):
 if os.geteuid()!=0:raise ServiceError('Autorização administrativa necessária')
 identity(root)
 original_runner=runner;deadline=time.monotonic()+120
 def bounded_runner(*args,**kwargs):
  remaining=deadline-time.monotonic()
  if remaining<=0:raise subprocess.TimeoutExpired(args[0],120)
  kwargs['timeout']=min(kwargs.get('timeout',60),remaining)
  return original_runner(*args,**kwargs)
 runner=bounded_runner
 if action not in ACTIONS:raise ServiceError('Ação fora da lista permitida')
 unit=resolve(service,root)
 deps=['containerd.service','docker.socket',unit] if service=='docker' else ['ssh.service','ssh.socket'] if service=='ssh' else [unit]
 for u in deps:
  state=query(u,runner)
  if state.get('LoadState')=='masked' or state.get('UnitFileState','').startswith('masked'):raise ServiceError(u+' mascarado; não será desmascarado automaticamente')
  if state.get('LoadState')!='loaded':raise ServiceError(u+' indisponível: '+state.get('error',state.get('LoadState','unknown')))
 def op(verb,units):return call([verb,'--',*units],runner)
 if service=='containerd' and action in ('stop','restart'):
  raise ServiceError('A parada direta do Containerd pode interromper consumidores externos.')
 if service=='docker-socket' and action in ('stop','restart') and query('docker.service',runner).get('ActiveState') not in ('inactive','failed'):
  raise ServiceError('Pare o Docker antes de alterar o socket em execução.')
 if action in ('enable','disable'):
  targets=['docker.service','docker.socket'] if service=='docker' and action=='disable' else deps if service=='ssh' and action=='disable' else [unit]
  op(action,targets)
 elif service=='docker':
  if action in ('stop','restart'):op('stop',['docker.socket','docker.service'])
  if action!='stop':
   op('start',['containerd.service'])
   if query('containerd.service',runner).get('ActiveState')!='active':raise ServiceError('containerd não ficou ativo; Docker não foi iniciado')
   op('start',['docker.service'])
 elif service=='ssh' and action=='stop':op('stop',['ssh.socket','ssh.service'])
 else:op(action,[unit])
 states={u:query(u,runner) for u in deps}
 if action in ('start','restart') and states[unit].get('ActiveState')!='active':raise ServiceError('O serviço não ficou ativo após a operação.')
 if action=='stop' and any(states[u].get('ActiveState') not in ('inactive','failed') for u in (['docker.service','docker.socket'] if service=='docker' else deps if service=='ssh' else [unit])):raise ServiceError('Parada não concluída')
 if action in ('enable','disable'):
  for u in targets:
   boot=states[u].get('UnitFileState','unknown')
   if action=='enable' and boot != 'enabled':raise ServiceError('Inicialização automática não confirmada para '+u)
   if action=='disable' and boot not in ('disabled','static','indirect','alias'):raise ServiceError('Desativação da inicialização não confirmada para '+u)
 return {'status':'success','states':states,'message':'Operação concluída; inicialização automática e execução atual são controles separados.'}

class ServiceClient:
 def snapshot(self):return snapshot()
 def operate(self,service,action):
  if action not in ACTIONS:raise ServiceError('Ação inválida')
  resolve(service,Path('/'))
  try:p=subprocess.run(['/usr/bin/pkexec','/usr/libexec/devlite-services-v6',action,service],capture_output=True,text=True,timeout=180,shell=False,stdin=subprocess.DEVNULL,env=ENV)
  except subprocess.TimeoutExpired as e:raise ServiceError('Autorização/operação excedeu prazo; atualizar estado') from e
  except OSError as e:raise ServiceError('Autorização administrativa indisponível') from e
  if p.returncode == 126:raise ServiceError('Autenticação cancelada')
  if p.returncode == 127:raise ServiceError('Autorização administrativa negada ou indisponível')
  try:data=json.loads(p.stdout)
  except ValueError:raise ServiceError('Autorização negada/cancelada ou helper indisponível')
  if not isinstance(data,dict):raise ServiceError('Resposta inválida do helper')
  if p.returncode or data.get('status')!='success':raise ServiceError(data.get('message','Operação não concluída'))
  return data

def main():
 import argparse
 p=argparse.ArgumentParser();p.add_argument('action',choices=sorted(ACTIONS));p.add_argument('service');a=p.parse_args()
 try:print(json.dumps(admin(a.action,a.service),ensure_ascii=False))
 except (ServiceError,OSError) as e:print(json.dumps({'status':'error','message':str(e)},ensure_ascii=False));raise SystemExit(1)
