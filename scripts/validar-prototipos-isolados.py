#!/usr/bin/env python3
"""Sealed read-only Base/Live review. No package install, service or ISO operations."""
import argparse,hashlib,importlib.util,json,os,resource,shlex,shutil,stat,subprocess,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pipeline.devlite.runtime import owned_directory
from pipeline.devlite.minimal_root import member
from pipeline.devlite.public_execution import filesystem_proof
from pipeline.devlite.customize.isolation_validation import critical_files,cgroup_limits
spec=importlib.util.spec_from_file_location('php_review',ROOT/'scripts/verificar-php-adminer.py')
legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)
ENTRY='scripts/validar-prototipos-isolados.py'
SOURCE=ROOT/'work/release-browser-2f24tvsg'
LIMITS=legacy.LIMITS
INPUTS={'policy.php':'prototypes/adminer/policy.php','index.php':'prototypes/adminer/index.php',
 'test-policy.php':'prototypes/adminer/test-policy.php','model.py':'prototypes/control2/model.py',
 'adminer-6.3.0-mysql.php':'work/adminer-review-11po9k_l/adminer-6.3.0-mysql.php'}
INSPECT=('etc/xdg/xdg-xubuntu/xfce4/panel/default.xml',
 'etc/xdg/xdg-xubuntu/xfce4/xfconf/xfce-perchannel-xml/xsettings.xml',
 'etc/xdg/xdg-xubuntu/xfce4/xfconf/xfce-perchannel-xml/xfwm4.xml',
 'etc/xdg/xfce4/xfconf/xfce-perchannel-xml/xsettings.xml',
 'etc/xdg/xfce4/xfconf/xfce-perchannel-xml/xfwm4.xml',
 'etc/lightdm/lightdm-gtk-greeter.conf','etc/dconf/profile/user',
 'usr/libexec/devlite-first-session','etc/xdg/autostart/devlite-first-session.desktop',
 'etc/skel/.config/devlite/apply-initial-defaults',
 'usr/share/themes/Greybird-dark/index.theme','usr/share/themes/Greybird-dark/xfwm4/themerc',
 'usr/share/icons/elementary-xfce-dark/index.theme','usr/share/icons/DMZ-White/index.theme',
 'etc/apache2/ports.conf','etc/apache2/apache2.conf',
 'usr/share/applications/org.gnome.Epiphany.desktop','usr/share/xfce4/helpers/epiphany.desktop')

def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def commands():
 folder='/run/prototype-review/'
 result=[['/usr/bin/php8.3','-n','-v']]
 result += [['/usr/bin/php8.3','-n','-l',folder+name] for name in ('policy.php','index.php','test-policy.php','adminer-6.3.0-mysql.php')]
 result += [['/usr/bin/php8.3','-n',folder+'test-policy.php']]
 code="import sys;sys.path.insert(0,'/run/prototype-review');from model import SimulatedBackend,OperationError;b=SimulatedBackend();b.operate('mariadb','enable');assert b.status('mariadb').state=='inactive';b.operate('mariadb','start');b.operate('mariadb','disable',confirmed=True);assert b.status('mariadb').state=='active' and not b.status('mariadb').autostart;import gi;gi.require_version('Gtk','3.0');from gi.repository import Gtk;assert Gtk.MAJOR_VERSION==3;print('CONTROL_MOCK_GTK3_OK')"
 result += [['/usr/bin/python3','-I','-B','-c',code]]
 return result

def command(job,approval):
 legacy.ENTRY=ENTRY
 return legacy.command(job,approval)

def prepare():
 if os.geteuid()==0:raise ValueError('Prepare as magaton')
 if shutil.disk_usage(ROOT).free<20*1024**3+16*1024**2:raise ValueError('Reserve insufficient')
 receipt=SOURCE/'browser-result.json';s=receipt.lstat();r=legacy.load(receipt)
 if s.st_uid!=0 or s.st_mode&0o022 or r['status']!='browser_full_views_verified':raise ValueError('Untrusted accepted pair')
 old=legacy.load(SOURCE/'browser-contract.json',r['contract_sha256'])
 legacy.check_candidate(ROOT/INPUTS['adminer-6.3.0-mysql.php'])
 code={**old['code_sha256'],'scripts/verificar-php-adminer.py':sha(ROOT/'scripts/verificar-php-adminer.py'),ENTRY:sha(ROOT/ENTRY)}
 if any(sha(ROOT/n)!=h for n,h in code.items()):raise ValueError('Accepted source code differs')
 job=owned_directory(ROOT/'work','prototype-review-');(job/'inputs').mkdir()
 for name,source in INPUTS.items():shutil.copyfile(ROOT/source,job/'inputs'/name)
 d={'operation':'read-only-prototypes-v1','job':str(job),'source_receipt_sha256':sha(receipt),
  'source_images':{n:r['results'][n]['image'] for n in ('base','live')},
  'code_sha256':code,'inputs_sha256':{n:sha(job/'inputs'/n) for n in INPUTS},
  'host_critical_files':critical_files(),'limits':LIMITS,'commands':commands(),
  'host_namespaces':{n:os.readlink('/proc/self/ns/'+n) for n in ('mnt','pid','net','ipc','uts')},
  'inspect':list(INSPECT),'reserve_bytes':20*1024**3,'images_modified':False}
 (job/'contract.json').write_text(json.dumps(d,indent=2)+'\n');approval=sha(job/'contract.json')
 (job/'command.json').write_text(json.dumps({'command':command(job,approval),'approval_sha256':approval},indent=2)+'\n')
 print(job);print(approval);print(shlex.join(command(job,approval)))

def inspect(root):
 result={}
 for name in INSPECT:
  p=member(root,name)
  if not p.exists():result[name]=None;continue
  s=p.lstat()
  if not stat.S_ISREG(s.st_mode) or s.st_size>1024**2:raise ValueError('Unexpected configuration '+name)
  result[name]={'sha256':sha(p),'mode':stat.S_IMODE(s.st_mode),'uid':s.st_uid,'gid':s.st_gid,'text':p.read_text()}
 result['dpkg_status_sha256']=sha(member(root,'var/lib/dpkg/status'))
 # Existing profiles are evidence, never changed. No recursive home walk.
 users=[]
 for line in member(root,'etc/passwd').read_text().splitlines():
  parts=line.split(':')
  if len(parts)==7 and parts[5].startswith('/home/'):
   users.append({'user':parts[0],'home':parts[5],'uid':parts[2]})
 result['home_accounts']=users
 return result

def guest_checks(root):
 read_fd,write_fd=os.pipe();pid=os.fork()
 if pid==0:
  try:
   os.close(read_fd)
   for fd in list(Path('/proc/self/fd').iterdir()):
    if int(fd.name)>2 and int(fd.name)!=write_fd:
     try:os.close(int(fd.name))
     except OSError:pass
   os.chroot(root);os.chdir('/')
   outputs=[legacy.compile_child(args) for args in commands()]
   if not outputs[0].startswith('PHP 8.3.') or not all('No syntax errors detected' in s for s in outputs[1:5]) or 'verificações PHP aprovadas' not in outputs[5] or 'CONTROL_MOCK_GTK3_OK' not in outputs[6]:raise ValueError('Guest checks incomplete')
   raw=json.dumps({'status':'passed','outputs':outputs}).encode()
  except BaseException as e:raw=json.dumps({'status':'failed','error':str(e)}).encode()
  try:
   offset=0
   while offset<len(raw):offset+=os.write(write_fd,raw[offset:])
  finally:os._exit(0)
 os.close(write_fd);raw=bytearray()
 try:
  while block:=os.read(read_fd,4096):
   raw.extend(block)
   if len(raw)>65536:os.kill(pid,9);raise ValueError('Guest output limit')
 finally:os.close(read_fd);os.waitpid(pid,0)
 result=json.loads(raw)
 if result['status']!='passed':raise ValueError('Isolated checks failed: '+result.get('error','unknown'))
 return result

def run(job,approval,authorized):
 if not authorized or os.geteuid()!=0 or os.getpid()!=1:raise ValueError('Approved root namespace PID1 required')
 job=legacy.confined(job)
 if job.parent!=ROOT/'work' or not job.name.startswith('prototype-review-'):raise ValueError('Unexpected job')
 d=legacy.load(job/'contract.json',approval)
 if d['job']!=str(job) or d['operation']!='read-only-prototypes-v1' or d['commands']!=commands() or d['inspect']!=list(INSPECT) or d['limits']!=LIMITS or d['images_modified'] is not False:raise ValueError('Scope differs')
 if any(sha(ROOT/n)!=h for n,h in d['code_sha256'].items()) or any(sha(job/'inputs'/n)!=h for n,h in d['inputs_sha256'].items()) or set(d['inputs_sha256'])!=set(INPUTS):raise ValueError('Sealed code/input changed')
 if critical_files()!=d['host_critical_files'] or sha(SOURCE/'browser-result.json')!=d['source_receipt_sha256']:raise ValueError('Baseline changed')
 receipt=legacy.load(SOURCE/'browser-result.json')
 if d['source_images']!={n:receipt['results'][n]['image'] for n in ('base','live')}:raise ValueError('Accepted images differ')
 if any(os.readlink('/proc/self/ns/'+n)==v for n,v in d['host_namespaces'].items()):raise ValueError('Namespace not isolated')
 group=Path('/sys/fs/cgroup')/Path('/proc/self/cgroup').read_text().strip().split('::',1)[1].lstrip('/')
 if group.name!='devlite-'+job.name+'.service':raise ValueError('Wrong cgroup')
 cgroup_limits(group,LIMITS)
 if 'NoNewPrivs:\t1' not in Path('/proc/self/status').read_text():raise ValueError('NoNewPrivileges missing')
 filesystem_proof(Path('/proc/self/mountinfo').read_text(),job,tuple(d['host_critical_files'])+(str(SOURCE),))
 if shutil.disk_usage(job).free<d['reserve_bytes']:raise ValueError('Disk reserve')
 with (job/'execution.lock').open('x') as f:f.write(approval)
 os.chown(job,0,0);job.chmod(0o700)
 report={'status':'running','results':{},'images_modified':False,'services_started':False,'iso_generated':False,'contract_sha256':approval}
 def call(args):subprocess.run(args,check=True,stdin=subprocess.DEVNULL,env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LC_ALL':'C'})
 try:
  call(['mount','--make-rprivate','/'])
  for target,image in d['source_images'].items():
   source=legacy.confined(image['file']);s=source.lstat()
   if source!=SOURCE/'attempt'/(target+'.ext4') or not stat.S_ISREG(s.st_mode) or s.st_uid!=0 or s.st_mode&0o022 or s.st_size!=image['bytes']:raise ValueError('Unexpected image')
   before=(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
   root=job/target;root.mkdir()
   call(['mount','-t','ext4','-o','loop,ro,noload,nodev,nosuid',str(source),str(root)])
   try:
    if not os.statvfs(root).f_flag & os.ST_RDONLY:raise ValueError('Writable image')
    configs=inspect(root)
    call(['mount','-t','proc','-o','ro,nodev,nosuid,noexec','proc',str(root/'proc')])
    for name,size in [('run','8m'),('tmp','16m')]:call(['mount','-t','tmpfs','-o','nodev,nosuid,noexec,size='+size+(',mode=1777' if name=='tmp' else ',mode=755'),'tmpfs',str(root/name)])
    runtime=root/'run/prototype-review';runtime.mkdir()
    for name in INPUTS:
     p=runtime/name;shutil.copyfile(job/'inputs'/name,p);p.chmod(0o444)
     if sha(p)!=d['inputs_sha256'][name]:raise ValueError('Copied input differs')
    call(['mount','--bind',str(runtime),str(runtime)])
    call(['mount','-o','remount,bind,ro,nodev,nosuid,noexec',str(runtime)])
    report['results'][target]={'configuration':configs,'checks':guest_checks(root)}
   finally:call(['umount','--recursive',str(root)])
   s=source.stat()
   if before!=(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns):raise ValueError('Accepted image metadata changed')
  if critical_files()!=d['host_critical_files']:raise ValueError('Host baseline changed')
  report.update(status='readonly_prototype_checks_passed',host_critical_unchanged=True,source_metadata_unchanged=True,graphical_tested=False,adminer_http_tested=False,adminer_database_tested=False)
 except BaseException as e:report.update(status='failed',error=str(e));raise
 finally:
  p=job/'result.json'
  with p.open('x') as f:json.dump(report,f,indent=2)
  p.chmod(0o444);job.chmod(0o755)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--prepare',action='store_true');ap.add_argument('--job',type=Path);ap.add_argument('--approval-sha256');ap.add_argument('--execute-authorized',action='store_true');a=ap.parse_args()
 if a.prepare:prepare()
 else:run(a.job,a.approval_sha256,a.execute_authorized)
