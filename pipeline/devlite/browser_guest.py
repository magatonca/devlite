"""Copied into /run/devlite. Execute ONLY after chroot and capability reduction."""
import errno,hashlib,json,os,resource,runpy,socket,subprocess,sys
from pathlib import Path

def network_denied(socket_factory=socket.socket):
    try: connection=socket_factory()
    except OSError as error:
        if error.errno not in (errno.EAFNOSUPPORT,errno.EPERM,errno.EACCES):raise
        return {'socket_denied_errno':error.errno}
    with connection:
        connection.settimeout(1)
        try: connection.connect(('1.1.1.1',443))
        except OSError as error:
            if error.errno not in (errno.ENETUNREACH,errno.EHOSTUNREACH,errno.ENETDOWN,errno.EPERM,errno.EACCES):raise
            return {'connect_denied_errno':error.errno}
        raise RuntimeError('External network accessible')

def probe(config,legacy):
    evidence={}
    try:os.chroot('/')
    except PermissionError:evidence['chroot_denied']=True
    else:raise RuntimeError('CAP_SYS_CHROOT retained')
    denied=legacy['denied_open']
    evidence['sentinel_read']=denied(config['host_sentinel'],'rb',{errno.ENOENT,errno.EACCES,errno.EPERM})
    evidence['sentinel_write']=denied(config['host_sentinel'],'r+b',{errno.ENOENT,errno.EACCES,errno.EPERM})
    evidence['bundle_readonly']=denied('/run/devlite/transaction.json','r+b',{errno.EROFS})
    for name in ['/run/systemd/private','/run/dbus/system_bus_socket','/var/run/docker.sock']:
        if Path(name).exists():raise RuntimeError('Host socket exposed')
    if list(Path('/sys').iterdir()):raise RuntimeError('sysfs exposed')
    devices={p.name for p in Path('/dev').iterdir()}
    if devices-{'null','zero','random','urandom','fd','stdin','stdout','stderr'}:raise RuntimeError('Unexpected device')
    mounts=Path('/proc/self/mountinfo').read_text()
    required={'/':{'nodev','nosuid'},'/proc':{'ro','nodev','nosuid','noexec'},
      '/run/devlite':{'ro','nodev','nosuid'},'/run/devlite/debs':{'ro','nodev','nosuid','noexec'}}
    evidence['mounts']={}
    for name,flags in required.items():
        actual=legacy['mount_flags'](mounts,name)
        if not flags<=actual:raise RuntimeError('Unsafe mount: '+name)
        evidence['mounts'][name]=sorted(actual)
    marker=Path('/var/tmp/devlite-browser-probe')
    with marker.open('xb') as stream:stream.write(b'DevLite browser probe')
    try:
        if marker.read_bytes()!=b'DevLite browser probe':raise RuntimeError('Target write failed')
    finally:marker.unlink()
    interfaces={line.split(':')[0].strip() for line in Path('/proc/net/dev').read_text().splitlines() if ':' in line}
    if interfaces-{'lo'}:raise RuntimeError('Host network interface exposed')
    evidence['network']={**network_denied(),'interfaces':sorted(interfaces)}
    result=subprocess.run(['/usr/bin/mount','-t','tmpfs','tmpfs','/mnt'],capture_output=True)
    if result.returncode==0:raise RuntimeError('CAP_SYS_ADMIN retained')
    evidence['mount_denied']=result.returncode
    pids={int(p.name) for p in Path('/proc').iterdir() if p.name.isdigit()}
    if pids-{1,os.getpid()}:raise RuntimeError('Unexpected visible processes')
    try:parent=os.stat('/proc/1/root');own=os.stat('/')
    except PermissionError:evidence['parent_root']='denied'
    else:
        if (parent.st_dev,parent.st_ino)!=(own.st_dev,own.st_ino):raise RuntimeError('Parent root is outside target')
        evidence['parent_root']='same_target'
    for fd in Path('/proc/self/fd').iterdir():
        if int(fd.name)>2:
            try:os.readlink(fd)
            except FileNotFoundError:continue
            raise RuntimeError('Extra inherited descriptor')
    evidence['capabilities']=legacy['capabilities'](Path('/proc/self/status').read_text(),config['allowed_caps'])
    print('PROBE_EVIDENCE='+json.dumps(evidence,sort_keys=True),flush=True)
    return evidence

def main():
    legacy=runpy.run_path('/run/devlite/legacy_guest.py')
    config=json.loads(Path('/run/devlite/transaction.json').read_text())
    for name,host in config['host_namespaces'].items():
        if os.readlink('/proc/self/ns/'+name)==host:raise RuntimeError('Guest namespace not isolated')
    legacy['capabilities'](Path('/proc/self/status').read_text(),config['allowed_caps'])
    resource.setrlimit(resource.RLIMIT_FSIZE,(config['file_bytes'],config['file_bytes']))
    # Always fail closed before APT if network, mounts, devices, fds or capabilities differ.
    probe(config,legacy)
    run=legacy['run'];paths=[];expected={}
    for item in config['changes']:
        path=Path('/run/devlite/debs')/Path(item['filename']).name
        with path.open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=item['sha256']:raise RuntimeError('Deb hash differs')
        output=run(['/usr/bin/dpkg-deb','--field',str(path)])
        fields={line.split(': ',1)[0]:line.split(': ',1)[1] for line in output.splitlines() if ': ' in line and not line[0].isspace()}
        if (fields.get('Package'),fields.get('Version'),fields.get('Architecture'))!=(item['package'].split(':')[0],item['version'],item['architecture']):raise RuntimeError('Deb identity differs')
        paths.append(str(path));expected[item['package']]=item['version']
    previous_auto=run(['/usr/bin/apt-mark','showauto']).splitlines()
    common=['--no-download','--no-remove','--no-install-recommends']
    if legacy['changes'](run(['/usr/bin/apt-get','-s',*common,'install',*paths]))!=expected:raise RuntimeError('Unexpected APT transaction')
    legacy['install_local'](paths,config['changes'],common)
    auto=legacy['automatic_packages'](previous_auto,config['changes'],config['requested'])
    if auto:run(['/usr/bin/apt-mark','auto',*auto])
    if config['requested']:run(['/usr/bin/apt-mark','manual',*config['requested']])
    if run(['/usr/bin/dpkg','--audit']).strip():raise RuntimeError('dpkg audit not empty')
    run(['/usr/bin/apt-get','-s','check'])
    for package in [i['package'] for i in config['changes']]:
        if run(['/usr/bin/dpkg','--verify',package]).strip():raise RuntimeError('Installed package integrity differs')
    binary=next((str(p) for p in [Path('/usr/bin/epiphany'),Path('/usr/bin/epiphany-browser')] if p.is_file()),None)
    if binary is None:raise RuntimeError('Browser executable absent')
    libs=run(['/usr/bin/ldd',binary])
    if 'not found' in libs:raise RuntimeError('Browser library unresolved')
    run(['/usr/bin/glib-compile-schemas','--strict','--dry-run','/usr/share/glib-2.0/schemas'])
    schemas=run(['/usr/bin/gsettings','list-schemas']).splitlines()
    if 'org.gnome.Epiphany' not in schemas:raise RuntimeError('Epiphany GSettings schema absent')
    # No --version or launch is treated as a GUI test. Never disable WebKit sandbox.
    print('BROWSER_GUEST_AUDIT='+json.dumps({'status':'static_validated','graphical_launch':'not_tested'}),flush=True)

if __name__=='__main__':main()
