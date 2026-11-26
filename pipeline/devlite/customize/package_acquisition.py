"""Manifesto e aquisição de debs por hash; modo de download bloqueado por padrão."""
import hashlib
import json
import os
import pwd
import re
import shutil
import ssl
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime,timezone
from email.utils import parsedate_to_datetime
from pathlib import Path,PurePosixPath
from .installation import sha,control,snapshot_indexes,INDEX
from .manifest import resolve,SpecError
from .executor_contract import ROOT,confined,validate_plan
from ..runtime import owned_directory

HOSTS={'archive.ubuntu.com','security.ubuntu.com'}
RESERVE=12*1024**3
CODE=('scripts/pacotes-controlados.py','pipeline/devlite/customize/package_acquisition.py',
      'pipeline/devlite/customize/installation.py','pipeline/devlite/customize/manifest.py',
      'pipeline/devlite/customize/executor_contract.py','pipeline/devlite/runtime.py')


def normal_user():
    if os.geteuid()==0 or pwd.getpwuid(os.getuid()).pw_name!='magaton':
        raise SpecError('Executar como magaton, sem sudo')


def save(path,value):
    with path.open('x') as stream:json.dump(value,stream,ensure_ascii=False,indent=2);stream.write('\n')


def valid_url(url):
    parsed=urllib.parse.urlsplit(url)
    if parsed.scheme!='https' or parsed.hostname not in HOSTS or parsed.username or parsed.password or parsed.port not in (None,443) or parsed.query or parsed.fragment or not parsed.path.startswith('/ubuntu/pool/'):
        raise SpecError('URL de pacote não permitida: '+url)
    decoded=urllib.parse.unquote(parsed.path)
    if '..' in PurePosixPath(decoded).parts or not decoded.endswith('.deb'):
        raise SpecError('Caminho de pacote inseguro')
    return url


class OfficialRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,msg,headers,newurl):
        valid_url(newurl)
        if getattr(request,'devlite_redirects',0)>=3: raise SpecError('Redirecionamentos excessivos')
        result=super().redirect_request(request,fp,code,msg,headers,newurl)
        result.devlite_redirects=getattr(request,'devlite_redirects',0)+1
        return result


def opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}),OfficialRedirect(),urllib.request.HTTPSHandler(context=ssl.create_default_context()))


def stanzas(path):
    block=[]
    with path.open() as stream:
        for line in stream:
            if line.strip():block.append(line)
            elif block:
                yield control(''.join(block))[0];block=[]
    if block:yield control(''.join(block))[0]


def entries(plan,workspace,evidence):
    selected={}
    for target,data in plan['targets'].items():
        for item in data['changes']:
            key=(item['package'].split(':')[0],item['version'],item['architecture'])
            copy={k:item[k] for k in ('version','architecture','sha256','filename','download_bytes')};copy['package']=key[0]
            if key in selected:
                if any(selected[key][field]!=value for field,value in copy.items()):raise SpecError('Artefato conflitante entre base/live')
                selected[key]['targets'].append(target)
            else:selected[key]=dict(copy,targets=[target],origins=[])
    releases={item['suite']:item for item in evidence if 'suite' in item}
    for meta in evidence:
        if 'index' not in meta:continue
        match=INDEX.fullmatch(meta['index'])
        if not match:raise SpecError('Índice não autorizado')
        _,suite,component=match.groups()
        path=workspace/'lists'/meta['index']
        if sha(path)!=meta['sha256']:raise SpecError('Índice mudou durante planejamento')
        for record in stanzas(path):
            key=(record.get('Package'),record.get('Version'),record.get('Architecture'))
            if key not in selected:continue
            item=selected[key]
            if any(str(item[field])!=record.get(name) for field,name in (('sha256','SHA256'),('filename','Filename'),('download_bytes','Size'))):
                raise SpecError('Transação diverge do índice assinado')
            filename=PurePosixPath(item['filename'])
            if filename.is_absolute() or '..' in filename.parts or not str(filename).startswith('pool/') or filename.suffix!='.deb':raise SpecError('Filename inseguro')
            host='security.ubuntu.com' if suite=='noble-security' else 'archive.ubuntu.com'
            url=valid_url('https://'+host+'/ubuntu/'+urllib.parse.quote(str(filename),safe='/+~.-'))
            origin={'suite':suite,'component':component,'index':meta['index'],'index_sha256':meta['sha256'],
                    'inrelease_sha256':releases[suite]['inrelease_sha256'],'signer':releases[suite]['signer'],'url':url}
            if origin not in item['origins']:item['origins'].append(origin)
    result=[];filenames={}
    for key,item in sorted(selected.items()):
        if not item['origins']:raise SpecError('Pacote sem origem Ubuntu assinada: '+item['package'])
        filename=Path(item['filename']).name
        if filename in filenames and filenames[filename]!=item['sha256']:raise SpecError('Colisão de nome de deb')
        filenames[filename]=item['sha256']
        item['urls']=sorted({origin['url'] for origin in item['origins']});item['targets']=sorted(item['targets'])
        result.append(item)
    return result


def fresh_metadata(evidence,now=None):
    now=now or datetime.now(timezone.utc)
    for item in evidence:
        if 'suite' not in item:continue
        date=parsedate_to_datetime(item['date'])
        if date>now:raise SpecError('Metadados com data futura')
        if item['suite']!='noble' and (now-date).total_seconds()>7*86400:
            raise SpecError('Metadados com mais de sete dias; renovar sob autorização')
        if item.get('valid_until') and parsedate_to_datetime(item['valid_until'])<now:
            raise SpecError('Metadados expirados')


def prepare(plan_path):
    normal_user();plan_path=confined(plan_path);plan=json.loads(plan_path.read_text());validate_plan(plan)
    selection=json.loads((ROOT/'packages/selection.json').read_text());catalog=resolve(selection)
    requested=sorted(i['package'] for i in catalog if i['provider']=='ubuntu')
    if len(requested)!=44 or requested!=sorted(plan['requested_ubuntu']):raise SpecError('Seleção Ubuntu difere dos 44 itens revisados')
    sources=json.loads((ROOT/'packages/sources.json').read_text())
    if any(v.get('enabled') is True for k,v in sources['sources'].items() if k!='ubuntu'):raise SpecError('Provider externo habilitado')
    work=owned_directory(ROOT/'work','phase4b5-')
    for folder in ('logs','lists','debs'):(work/folder).mkdir()
    evidence,blockers=snapshot_indexes(work,confined(plan_path.parent/'lists'))
    if blockers:raise SpecError('; '.join(blockers))
    fresh_metadata(evidence)
    artifacts=entries(plan,work,evidence)
    shutil.copyfile(plan_path,work/'installation-plan.json')
    total=sum(i['download_bytes'] for i in artifacts)
    manifest={'schema':1,'status':'preparado_sem_download','workspace':str(work),'simulation_sha256':sha(work/'installation-plan.json'),
              'selection_sha256':sha(ROOT/'packages/selection.json'),'requested_ubuntu':requested,'artifacts':artifacts,'indexes':evidence,
              'total_bytes':total,'unique_artifacts':len(artifacts),'reserve_bytes':RESERVE,'download_required_bytes':total+RESERVE,
              'code_sha256':{name:sha(ROOT/name) for name in CODE},'network_used_to_prepare':False,'install_allowed':False,
              'indexes_note':'snapshot local autenticado; não é uma atualização dos índices remotos',
              'installation_required_bytes':plan['resources']['additional_required_bytes']}
    save(work/'download-plan.json',manifest)
    approval=sha(work/'download-plan.json')
    save(work/'command-review.json',{'approval_sha256':approval,'download':['python3',str(ROOT/'scripts/pacotes-controlados.py'),'--download',str(work/'download-plan.json'),'--approval-sha256',approval],
         'permission':'download_pacotes_autorizado permanece false; autorização específica necessária; nenhuma instalação habilitada'})
    return work


def fetch_one(item,cache,client,reserve=RESERVE):
    cache=Path(cache)
    final=cache/Path(item['filename']).name
    if final.exists() or final.is_symlink():
        if final.is_symlink() or not final.is_file() or final.stat().st_size!=item['download_bytes'] or sha(final)!=item['sha256']:
            raise SpecError('Cache existente inválido; não sobrescrever')
        return {'file':str(final),'sha256':item['sha256'],'bytes':item['download_bytes'],'cached':True}
    part=cache/(final.name+'.part-'+uuid.uuid4().hex)
    for url in item['urls']:
        valid_url(url)
        try:response=client.open(urllib.request.Request(url,headers={'User-Agent':'DevLite-OS/4B.5','Accept-Encoding':'identity'}),timeout=30)
        except urllib.error.HTTPError as error:
            if error.code in (404,410):
                error.close();continue
            raise
        with response:
            final_url=valid_url(response.geturl())
            if response.status!=200:raise SpecError('HTTP inesperado: '+str(response.status))
            length=response.headers.get('Content-Length')
            if length is not None and int(length)!=item['download_bytes']:raise SpecError('Content-Length diverge do índice')
            digest=hashlib.sha256();size=0
            with part.open('xb') as stream:
                while True:
                    chunk=response.read(min(1024*1024,item['download_bytes']-size+1))
                    if not chunk:break
                    size+=len(chunk)
                    if size>item['download_bytes']:raise SpecError('Download excedeu tamanho travado')
                    if shutil.disk_usage(cache).free-len(chunk)<reserve:raise SpecError('Reserva de disco atingida')
                    stream.write(chunk);digest.update(chunk)
                stream.flush();os.fsync(stream.fileno())
            if size!=item['download_bytes'] or digest.hexdigest()!=item['sha256']:raise SpecError('SHA-256/tamanho do deb inválido; parcial preservado')
            os.link(part,final)  # Publicação exclusiva; nunca sobrescreve cache concorrente.
            part.unlink()  # Somente o temporário criado por esta chamada após verificação.
            return {'file':str(final),'sha256':digest.hexdigest(),'bytes':size,'requested_url':url,'final_url':final_url,'cached':False}
    raise SpecError('Pacote indisponível nas URLs assinadas; não substituir versão')


def download(plan_path,approval):
    normal_user()
    config=json.loads((ROOT/'config/projeto.json').read_text())
    if config.get('download_pacotes_autorizado') is not True:raise SpecError('Download não autorizado; nenhuma conexão de aquisição iniciada')
    plan_path=confined(plan_path)
    if sha(plan_path)!=approval:raise SpecError('Hash de aprovação incorreto')
    manifest=json.loads(plan_path.read_text());work=plan_path.parent
    if manifest.get('schema')!=1 or manifest.get('workspace')!=str(work) or manifest.get('install_allowed') is not False:raise SpecError('Contrato de aquisição inválido')
    if set(manifest.get('code_sha256',{}))!=set(CODE):raise SpecError('Contrato de código incompleto')
    for name,digest in manifest['code_sha256'].items():
        if sha(ROOT/name)!=digest:raise SpecError('Código mudou após revisão')
    if sha(work/'installation-plan.json')!=manifest['simulation_sha256'] or sha(ROOT/'packages/selection.json')!=manifest['selection_sha256']:raise SpecError('Plano/seleção mudou')
    cache=confined(work/'debs')
    if not cache.is_dir():raise SpecError('Cache não existe')
    if shutil.disk_usage(work).free<manifest['download_required_bytes']:raise SpecError('Espaço insuficiente antes do download')
    lock=work/'.download.lock';fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    try:attempt=owned_directory(work,'acquisition-')
    except BaseException:
        os.close(fd);lock.unlink();raise
    report={'status':'verificando','downloads':[],'installation_executed':False,'approval_sha256':approval}
    try:
        (attempt/'logs').mkdir();(attempt/'lists').mkdir()
        evidence,blockers=snapshot_indexes(attempt,work/'lists')
        if blockers:raise SpecError('; '.join(blockers))
        fresh_metadata(evidence)
        if evidence!=manifest['indexes']:raise SpecError('Snapshot de metadados mudou')
        simulation=json.loads((work/'installation-plan.json').read_text());validate_plan(simulation)
        if entries(simulation,attempt,evidence)!=manifest['artifacts']:raise SpecError('Manifesto diverge da cadeia assinada')
        client=opener()
        for item in manifest['artifacts']:
            record=fetch_one(item,cache,client);record.update(package=item['package'],version=item['version'],architecture=item['architecture'],origins=item['origins'])
            report['downloads'].append(record)
            print('Verificado:',item['package'],item['version'],flush=True)
        report['status']='download_verificado';report['completed_utc']=datetime.now(timezone.utc).isoformat()
    except BaseException as error:
        report.update(status='interrompido',error=str(error));raise
    finally:
        try:save(attempt/'receipt.json',report)
        finally:os.close(fd)
        lock.unlink()  # Receipt ausente por falha de escrita mantém lock para revisão.
    return attempt/'receipt.json'
