#!/usr/bin/env python3
"""Autentica somente metadados oficiais. Nunca adquire ou instala programas."""
import argparse,base64,gzip,hashlib,json,os,re,subprocess,sys,urllib.request
from datetime import datetime,timezone
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pipeline.devlite.runtime import owned_directory
from pipeline.devlite.customize.installation import control

NODE_FPR='5BE8A3F6C8A5C01D106C0AD820B1A390B168D356'
MS_FPR='BC528686B50D79E339D3721CEB3E94ADBE1229CF'
URLS={
 'node-key':'https://raw.githubusercontent.com/nodejs/release-keys/HEAD/keys/'+NODE_FPR+'.asc',
 'node-sums':'https://nodejs.org/dist/v26.13.1/SHASUMS256.txt.asc',
 'ms-key':'https://packages.microsoft.com/keys/microsoft.asc',
 'ms-release':'https://packages.microsoft.com/repos/code/dists/stable/InRelease',
 'ms-index':'https://packages.microsoft.com/repos/code/dists/stable/main/binary-amd64/Packages.gz'}
ALLOWED=set(URLS.values())
class Redirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):
  if newurl not in ALLOWED:raise ValueError('Redirecionamento fora dos metadados permitidos')
  return super().redirect_request(req,fp,code,msg,headers,newurl)
def fetch(name,work):
 url=URLS[name];limit=8*1024**2 if name=='ms-index' else 256*1024
 with urllib.request.build_opener(Redirect()).open(url,timeout=30) as response:
  if response.geturl() not in ALLOWED:raise ValueError('Origem inesperada')
  data=response.read(limit+1)
 if len(data)>limit:raise ValueError('Limite de metadados excedido')
 path=work/name
 with path.open('xb') as stream:stream.write(data)
 return path
def cmd(args,work,label):
 result=subprocess.run(args,capture_output=True,text=True,timeout=60)
 (work/(label+'.log')).write_text(result.stdout+result.stderr)
 if result.returncode:raise ValueError(label+': retorno '+str(result.returncode))
 return result.stdout

def verify_gpg(work,label,key,signed,fpr):
 home=work/(label+'-gpg');home.mkdir(mode=0o700);ring=work/(label+'.gpg')
 cmd(['gpg','--batch','--no-options','--homedir',str(home),'--dearmor','--output',str(ring),str(key)],work,label+'-dearmor')
 listing=cmd(['gpg','--batch','--no-options','--homedir',str(home),'--with-colons','--show-keys',str(ring)],work,label+'-key')
 actual=next(line.split(':')[9] for line in listing.splitlines() if line.startswith('fpr:'))
 if actual!=fpr:raise ValueError('Fingerprint não confere')
 verified=work/(label+'-verified.txt')
 status=cmd(['gpgv','--homedir',str(home),'--status-fd','1','--keyring',str(ring),'--output',str(verified),str(signed)],work,label+'-signature')
 if '[GNUPG:] VALIDSIG ' not in status or any(s in status for s in ('BADSIG','ERRSIG','EXPSIG','EXPKEYSIG','REVKEYSIG')):raise ValueError('Assinatura não aprovada')
 return verified

def verify_npm(work,metadata):
 keys=metadata['metadata']['npm_keys']['value']['keys'];result={}
 for name in ('typescript','typescript_linux_x64'):
  package=metadata['metadata'][name]['value'];expected_name='typescript' if name=='typescript' else '@typescript/typescript-linux-x64'
  if package.get('name')!=expected_name or package.get('version')!='7.0.2':raise ValueError('Identidade npm não coincide com a versão solicitada')
  dist=package['dist']
  if not dist.get('integrity','').startswith('sha512-') or len(base64.b64decode(dist['integrity'][7:],validate=True))!=64:raise ValueError('SRI npm deve usar SHA-512')
  if name=='typescript_linux_x64' and ('linux' not in package.get('os',[]) or 'x64' not in package.get('cpu',[])):raise ValueError('Plataforma npm divergente')
  if len(dist.get('signatures',[]))!=1:raise ValueError('Conjunto de assinaturas npm exige revisão')
  signature=dist['signatures'][0]
  key=next(k for k in keys if k['keyid']==signature['keyid'])
  if key.get('expires') is not None:raise ValueError('Chave npm com expiração precisa de revisão por data de publicação')
  der=base64.b64decode(key['key'],validate=True)
  # npm selects the registry key by its advertised keyid, then verifies ECDSA.
  # Record our DER fingerprint independently; keyid is not defined as SPKI hash.
  fingerprint=hashlib.sha256(der).hexdigest()
  pem=work/(name+'.pem');pem.write_text('-----BEGIN PUBLIC KEY-----\n'+base64.encodebytes(der).decode()+'-----END PUBLIC KEY-----\n')
  sig=work/(name+'.sig');sig.write_bytes(base64.b64decode(signature['sig'],validate=True))
  message=work/(name+'.message');message.write_bytes((package['name']+'@'+package['version']+':'+dist['integrity']).encode())
  cmd(['openssl','dgst','-sha256','-verify',str(pem),'-signature',str(sig),str(message)],work,name+'-signature')
  result[name]={'name':package['name'],'version':package['version'],'keyid':key['keyid'],'metadata_signature_verified':True,'key_der_sha256':fingerprint,'artifact_sri':dist['integrity'],'payload_acquired':False,'unpacked_bytes':dist['unpackedSize']}
 return result

def main():
 if os.getuid()!=1000 or os.geteuid()==0:raise ValueError('Executar como magaton')
 work=owned_directory(ROOT/'work','final-metadata-');report={'status':'running','captured_utc':datetime.now(timezone.utc).isoformat(),'workspace':str(work),'packages_acquired':False,'repositories_added':False}
 try:
  node=verify_gpg(work,'node',fetch('node-key',work),fetch('node-sums',work),NODE_FPR)
  filename='node-v26.13.1-linux-x64.tar.xz'
  matches=[line.split()[0] for line in node.read_text().splitlines() if line.endswith('  '+filename)]
  if len(matches)!=1 or not re.fullmatch('[0-9a-f]{64}',matches[0]):raise ValueError('Checksum Node ausente/duplicado')
  report['node']={'version':'26.13.1','signer_fingerprint':NODE_FPR,'metadata_signature_verified':True,'filename':filename,'sha256':matches[0],'payload_acquired':False}
  release=verify_gpg(work,'microsoft',fetch('ms-key',work),fetch('ms-release',work),MS_FPR)
  name='main/binary-amd64/Packages.gz';section=release.read_text().split('SHA256:',1)[1].split('\n\n',1)[0]
  expected=next(line.split() for line in section.splitlines() if line.strip().endswith(' '+name))
  index=fetch('ms-index',work);data=index.read_bytes()
  if len(data)!=int(expected[1]) or hashlib.sha256(data).hexdigest()!=expected[0]:raise ValueError('Índice VS Code não confere com InRelease')
  import io
  with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:raw=stream.read(32*1024**2+1)
  if len(raw)>32*1024**2:raise ValueError('Índice descomprimido excede limite')
  metadata=json.loads((ROOT/'docs/evidencias/programas-pendentes-metadados.json').read_text())
  api=metadata['metadata']['vscode_latest']['value']
  versions=[item for item in control(raw.decode()) if item.get('Package')=='code' and item.get('Architecture')=='amd64' and item.get('Version','').split('-')[0]==api['productVersion'] and item.get('SHA256')==api['sha256hash']]
  if len(versions)!=1:raise ValueError('VS Code da API ainda não corresponde ao índice assinado')
  item=versions[0];report['vscode']={k:item.get(k) for k in ('Package','Version','Architecture','Depends','Pre-Depends','Filename','Size','Installed-Size','SHA256')};report['vscode'].update(metadata_signature_verified=True,signer_fingerprint=MS_FPR,payload_acquired=False)
  report['npm']=verify_npm(work,metadata);report['status']='official_metadata_authenticated_payloads_not_acquired'
 except Exception as error:report.update(status='blocked',error=str(error));raise
 finally:
  (work/'metadata-authentication.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
  (ROOT/'docs/evidencias/autenticacao-metadados-externos.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--verify-metadata',action='store_true',required=True);p.parse_args();main()
