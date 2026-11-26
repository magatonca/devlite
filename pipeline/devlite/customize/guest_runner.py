"""Programa local copiado ao alvo. Somente chamado pelo worker após isolamento."""
import hashlib
import contextlib
import errno
import json
import os
import re
import resource
import sys
import socket
import shlex
import subprocess
from pathlib import Path


def run(args):
    print('GUEST',json.dumps(args),flush=True)
    result=subprocess.run(args,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,check=False,
                          env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','HOME':'/root','LC_ALL':'C','DEBIAN_FRONTEND':'noninteractive',
                               'APT_CONFIG':'/run/devlite/apt.conf','SYSTEMD_OFFLINE':'1','NEEDRESTART_MODE':'l'})
    print(result.stdout,flush=True)
    if result.returncode: raise RuntimeError('Falha no alvo: '+args[0])
    return result.stdout


def changes(text):
    result={}
    for line in text.splitlines():
        if line.startswith('Remv '): raise RuntimeError('Remoção inesperada')
        if line.startswith('Inst '):
            match=re.fullmatch(r'Inst (\S+)(?: \[[^\]]+\])? \((\S+)(?: [^)]*)?\)(?: \[[^\]]*\])*',line)
            if not match: raise RuntimeError('Saída APT não reconhecida')
            if match[1] in result: raise RuntimeError('Pacote duplicado')
            result[match[1]]=match[2]
    return result


def denied_open(path,mode,allowed_errors):
    try:
        with open(path,mode): pass  # Nunca escreve, mesmo se a restrição estiver ausente.
    except OSError as error:
        if error.errno in allowed_errors: return error.errno
        raise
    raise RuntimeError('Acesso indevido permitido: '+str(path))


def capabilities(status,allowed):
    result={name:int(re.search(r'^'+name+r':\s*(\w+)',status,re.M)[1],16) for name in ('CapEff','CapPrm','CapBnd','CapInh','CapAmb')}
    mask=sum(1<<number for number in allowed)
    if any(value & ~mask for value in result.values()) or result['CapInh'] or result['CapAmb'] or 'NoNewPrivs:\t1' not in status:
        raise RuntimeError('Capabilities/no_new_privs inseguros')
    return result


def mount_flags(text,path):
    for line in text.splitlines():
        fields=line.split()
        if len(fields)>6 and fields[4]==path: return set(fields[5].split(','))
    raise RuntimeError('Mount esperado ausente: '+path)


def probe(config):
    evidence={}
    try:
        os.chroot('/')
    except PermissionError: evidence['chroot_denied']=True
    else: raise RuntimeError('CAP_SYS_CHROOT ainda disponível')
    evidence['host_sentinel_read_errno']=denied_open(config['host_sentinel'],'rb',{errno.ENOENT,errno.EACCES,errno.EPERM})
    evidence['host_sentinel_write_open_errno']=denied_open(config['host_sentinel'],'r+b',{errno.ENOENT,errno.EACCES,errno.EPERM})
    evidence['bundle_write_errno']=denied_open('/run/devlite/transaction.json','r+b',{errno.EROFS})
    forbidden={'/run/systemd/private','/run/dbus/system_bus_socket','/var/run/docker.sock'}
    if any(Path(p).exists() for p in forbidden): raise RuntimeError('Socket do host exposto')
    if list(Path('/sys').iterdir()): raise RuntimeError('sysfs exposto')
    devices={p.name for p in Path('/dev').iterdir()}
    if devices-{'null','zero','random','urandom','fd','stdin','stdout','stderr'}: raise RuntimeError('Device inesperado')
    evidence['devices']=sorted(devices)
    mounts=Path('/proc/self/mountinfo').read_text()
    required={'/':{'nodev','nosuid'},'/proc':{'ro','nodev','nosuid','noexec'},'/run/devlite':{'ro','nodev','nosuid'},'/run/devlite/debs':{'ro','nodev','nosuid','noexec'}}
    evidence['mount_flags']={}
    for path,flags in required.items():
        actual=mount_flags(mounts,path)
        if not flags<=actual: raise RuntimeError('Mount sem restrição: '+path)
        evidence['mount_flags'][path]=sorted(actual)
    # Escrita reversível somente dentro da cópia descartável, sem sobrescrever dados.
    marker=Path('/var/tmp/devlite-isolation-probe')
    with marker.open('xb') as stream: stream.write(b'DevLite probe\n')
    try:
        if marker.read_bytes()!=b'DevLite probe\n': raise RuntimeError('Falha de escrita no alvo')
        evidence['target_write_verified']=True
    finally: marker.unlink()
    interfaces={line.split(':')[0].strip() for line in Path('/proc/net/dev').read_text().splitlines() if ':' in line}
    if interfaces-{'lo'}: raise RuntimeError('Interface de rede inesperada')
    evidence['network_interfaces']=sorted(interfaces)
    with socket.socket() as connection:
        connection.settimeout(1)
        try: connection.connect(('1.1.1.1',443))
        except OSError as error:
            if error.errno not in (errno.ENETUNREACH,errno.EHOSTUNREACH,errno.ENETDOWN): raise
            evidence['network_denied_errno']=error.errno
        else: raise RuntimeError('Rede externa acessível')
    output=subprocess.run(['/usr/bin/mount','-t','tmpfs','tmpfs','/mnt'],capture_output=True)
    if output.returncode==0: raise RuntimeError('CAP_SYS_ADMIN ainda disponível')
    evidence['mount_denied_returncode']=output.returncode
    pids={int(p.name) for p in Path('/proc').iterdir() if p.name.isdigit()}
    if pids-{1,os.getpid()}: raise RuntimeError('Processo fora do conjunto esperado')
    evidence['visible_pids']=sorted(pids)
    try:
        parent=os.stat('/proc/1/root'); own=os.stat('/')
    except PermissionError: evidence['parent_root']='access_denied'
    else:
        if (parent.st_dev,parent.st_ino)!=(own.st_dev,own.st_ino): raise RuntimeError('/proc/1/root fora do alvo')
        evidence['parent_root']='same_target_root'
    for fd in Path('/proc/self/fd').iterdir():
        if int(fd.name)>2:
            try: os.readlink(fd)
            except FileNotFoundError: continue
            raise RuntimeError('Descritor extra herdado')
    evidence['capabilities']=capabilities(Path('/proc/self/status').read_text(),config['allowed_caps'])
    evidence['namespaces']={name:os.readlink('/proc/self/ns/'+name) for name in config['host_namespaces']}
    print('PROBE_EVIDENCE='+json.dumps(evidence,sort_keys=True),flush=True)


def apt_archive_name(item):
    """Nome do cache APT: pacote_versão-com-epoch-escapado_arquitetura.deb."""
    name=item['package'].split(':')[0];version=item['version'];arch=item['architecture']
    if not re.fullmatch(r'[a-z0-9][a-z0-9+.-]+',name) or not re.fullmatch(r'[0-9][A-Za-z0-9.+:~\-]*',version) or arch not in ('amd64','all'):
        raise RuntimeError('Identidade inválida para nome do cache APT')
    return name+'_'+version.replace(':','%3a')+'_'+arch+'.deb'


@contextlib.contextmanager
def archive_cache(paths,cache=Path('/var/cache/apt/archives'),changes=None):
    """Cache APT gravável no alvo, com payloads no bundle imutável."""
    cache=Path(cache)
    if not cache.is_absolute() or cache.is_symlink(): raise RuntimeError('Cache APT inseguro')
    cache.mkdir(parents=True,exist_ok=True)
    partial=cache/'partial'
    if partial.is_symlink(): raise RuntimeError('Cache partial é symlink')
    partial.mkdir(exist_ok=True)
    created=[]
    try:
        if changes is not None and len(changes)!=len(paths): raise RuntimeError('Cache e lock têm quantidades diferentes')
        for index,value in enumerate(paths):
            source=Path(value)
            if not source.is_absolute() or source.is_symlink() or not source.is_file(): raise RuntimeError('Arquivo local inválido')
            names={source.name}
            if changes is not None:
                item=changes[index]
                if source.name!=Path(item['filename']).name: raise RuntimeError('Arquivo diverge do lock do cache')
                names.add(apt_archive_name(item))
            for name in sorted(names):
                target=cache/name
                if target.exists() or target.is_symlink(): raise RuntimeError('Não sobrescrever arquivo de cache: '+target.name)
                target.symlink_to(source);created.append((target,source))
        yield
    finally:
        for target,source in reversed(created):
            if target.is_symlink() and os.readlink(target)==str(source): target.unlink()
            elif target.exists() or target.is_symlink(): raise RuntimeError('Cache local alterado inesperadamente: '+target.name)


def install_local(paths,changes,common):
    with archive_cache(paths,changes=changes):
        # Exercitar a montagem dos comandos dpkg antes do primeiro unpack real.
        # Duas barreiras: o modo debug não executa dpkg e o binário é /bin/false.
        preview=run(['/usr/bin/apt-get','-y','-o','Debug::pkgDPkgPM=true','-o','Dir::Bin::dpkg=/bin/false','-o','dpkg::install::recursive::minimum=1000000',*common,'install',*paths])
        planned={value for line in preview.splitlines() if line.startswith('/bin/false ') for value in shlex.split(line) if value.endswith('.deb')}
        expected={str(Path('/var/cache/apt/archives')/apt_archive_name(item)) for item in changes}
        if planned!=expected: raise RuntimeError('Preflight dpkg não cobriu todos os caminhos absolutos do lock')
        run(['/usr/bin/apt-get','-y',*common,'install',*paths])


def automatic_packages(previous_auto,changes,requested):
    new={item['package'].split(':')[0] for item in changes if item.get('previous') is None}
    return sorted((set(previous_auto)|new)-set(requested))


def main():
    config=json.loads(Path('/run/devlite/transaction.json').read_text())
    for name,host in config['host_namespaces'].items():
        if os.readlink('/proc/self/ns/'+name)==host: raise RuntimeError('Namespace não isolado: '+name)
    status=Path('/proc/self/status').read_text()
    capabilities(status,config['allowed_caps'])
    resource.setrlimit(resource.RLIMIT_FSIZE,(config['file_bytes'],config['file_bytes']))
    if '--probe-only' in sys.argv:
        probe(config)
        return
    paths=[];expected={}
    for item in config['changes']:
        path=Path('/run/devlite/debs')/Path(item['filename']).name
        with path.open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=item['sha256']: raise RuntimeError('Deb alterado')
        fields=run(['/usr/bin/dpkg-deb','--field',str(path)])
        values={line.split(': ',1)[0]:line.split(': ',1)[1] for line in fields.splitlines() if line and not line[0].isspace() and ': ' in line}
        if (values.get('Package'),values.get('Version'),values.get('Architecture'))!=(item['package'].split(':')[0],item['version'],item['architecture']):
            raise RuntimeError('Identidade do deb diverge do lock')
        paths.append(str(path));expected[item['package']]=item['version']
    if '--validate-only' not in sys.argv:
        previous_auto=run(['/usr/bin/apt-mark','showauto']).splitlines()
        run(['/usr/bin/debconf-set-selections','/run/devlite/debconf.selections'])
        common=['--no-download','--no-remove','--no-install-recommends']
        preview=run(['/usr/bin/apt-get','-s',*common,'install',*paths])
        if changes(preview)!=expected: raise RuntimeError('APT tentou transação diferente do lock')
        install_local(paths,config['changes'],common)
        auto=automatic_packages(previous_auto,config['changes'],config['requested'])
        if auto: run(['/usr/bin/apt-mark','auto',*auto])
        if config['requested']: run(['/usr/bin/apt-mark','manual',*config['requested']])
    audit=run(['/usr/bin/dpkg','--audit'])
    if audit.strip(): raise RuntimeError('dpkg --audit não está vazio')
    run(['/usr/bin/apt-get','-s','check'])
    run(['/usr/sbin/locale-gen','--keep-existing'])
    if 'pt_BR.utf8' not in run(['/usr/bin/locale','-a']): raise RuntimeError('Locale pt_BR ausente')
    # Apenas sintaxe; nenhum daemon é iniciado.
    run(['/usr/sbin/apache2ctl','-t'])
    run(['/usr/bin/php','--ini'])
    if '--validate-only' in sys.argv:
        run(['/usr/bin/php','-r','exit(ini_get("expose_php") || ini_get("display_errors") ? 1 : 0);'])
        run(['/usr/sbin/mariadbd','--verbose','--help'])
        run(['/usr/bin/dockerd','--validate','--config-file=/etc/docker/daemon.json'])
    for name in config['masks']:
        result=subprocess.run(['/usr/bin/systemctl','--root=/','is-enabled',name],capture_output=True,text=True)
        if result.stdout.strip()!='masked': raise RuntimeError('Serviço não está mascarado: '+name)

if __name__=='__main__': main()
