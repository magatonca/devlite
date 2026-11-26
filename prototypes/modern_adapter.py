"""Pure Modern patch renderer; accepted rootfs contents arrive from read-only audit."""
import ast,hashlib,json,os,stat
from pathlib import Path
from pipeline.devlite.modern_preview import PANEL,CHANNEL,THEME,ICONS,WALLPAPER,panel,render_channel
from pipeline.devlite.browser import replace_keys
from pipeline.devlite.minimal_root import apply_to_tree,member,check_diff,EPOCH
ROOT=Path(__file__).resolve().parents[1]
REVIEW=ROOT/'work/prototype-review-wt6wd6a1/result.json'
EXPECTED_REVIEW_CONTRACT='5458597739a4c73ee02fbf8ad544a79a75403e5ad7c5fc0f0af42f2e319552ed'
def sha_bytes(raw):return hashlib.sha256(raw).hexdigest()
def render(config):
 def original(name):
  item=config.get(name)
  if not item or sha_bytes(item['text'].encode())!=item['sha256']:raise ValueError('Incomplete/corrupt preimage '+name)
  return item['text']
 if config.get('home_accounts')!=[]:raise ValueError('Existing home profiles require review')
 for path in ('usr/share/themes/Greybird-dark/index.theme','usr/share/themes/Greybird-dark/xfwm4/themerc','usr/share/icons/elementary-xfce-dark/index.theme','usr/share/icons/DMZ-White/index.theme'):original(path)
 changes=[('Net/ThemeName','string',THEME),('Net/IconThemeName','string',ICONS),('Gtk/CursorThemeName','string','DMZ-White'),('Gtk/CursorThemeSize','int','24'),('Gtk/EnableAnimations','bool','false')]
 files={PANEL:panel(original(PANEL)),CHANNEL+'xsettings.xml':render_channel(original(CHANNEL+'xsettings.xml'),'xsettings',changes),
 CHANNEL+'xfwm4.xml':render_channel(original(CHANNEL+'xfwm4.xml'),'xfwm4',[('general/theme','string',THEME),('general/use_compositing','bool','false')]),
 'etc/xdg/xfce4/xfconf/xfce-perchannel-xml/xsettings.xml':render_channel(original('etc/xdg/xfce4/xfconf/xfce-perchannel-xml/xsettings.xml'),'xsettings',changes),
 'etc/lightdm/lightdm-gtk-greeter.conf':replace_keys(original('etc/lightdm/lightdm-gtk-greeter.conf'),{'theme-name':THEME,'icon-theme-name':ICONS,'cursor-theme-name':'DMZ-White','background':WALLPAPER,'user-background':'false','transition-duration':'0','transition-type':'none'},'greeter')}
 original('usr/libexec/devlite-first-session')
 for name in ('usr/libexec/devlite-first-session',WALLPAPER.lstrip('/')):files[name]=(ROOT/'prototypes/devlite-modern/payload'/name).read_text()
 ast.parse(files['usr/libexec/devlite-first-session'])
 return {n:{'kind':'file','text':text,'sha256':sha_bytes(text.encode()),'mode':493 if n=='usr/libexec/devlite-first-session' else 420,'preimage_sha256':config[n]['sha256'] if config.get(n) else None} for n,text in files.items()}
def validate_review(path=REVIEW):
 s=path.lstat();d=json.loads(path.read_text())
 if not stat.S_ISREG(s.st_mode) or s.st_uid!=0 or s.st_mode&0o022 or d.get('status')!='readonly_prototype_checks_passed' or d.get('contract_sha256')!=EXPECTED_REVIEW_CONTRACT or d.get('source_metadata_unchanged') is not True or d.get('host_critical_unchanged') is not True:raise ValueError('Untrusted accepted review')
 if set(d['results'])!={'base','live'}:raise ValueError('Both views required')
 return d

def write_bundle(destination,view,patch):
 folder=destination/view;folder.mkdir()
 for name,item in patch.items():
  p=folder/'configuration'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(item['text'])
 (folder/'patch.json').write_text(json.dumps({n:{k:v for k,v in x.items() if k!='text'} for n,x in patch.items()},indent=2)+'\n')

def apply_patch(root,bundle,before):
 patch=json.loads((bundle/'patch.json').read_text())
 # Every preimage, payload and type must match before the first write.
 for name,item in patch.items():
  p=member(root,name);payload=member(bundle/'configuration',name)
  if payload.is_symlink() or sha_bytes(payload.read_bytes())!=item['sha256']:raise ValueError('Payload changed')
  old=before.get(name)
  if item['preimage_sha256'] is None:
   if old is not None:raise ValueError('New path already exists '+name)
  elif old is None or old['type']!='file' or old['sha256']!=item['preimage_sha256'] or len(old['hardlinks'])!=1:raise ValueError('Preimage differs '+name)
 allowed=apply_to_tree(bundle,root,patch,before)
 for name,item in patch.items():member(root,name).chmod(item['mode'])
 return patch,allowed

def verify_patch(before,after,patch,allowed):
 check_diff(before,after,allowed)
 for name in set(after)-set(before)-set(patch):
  a=after[name]
  if a['type']!='dir' or a['uid']!=0 or a['gid']!=0 or a['mode']!=493 or a['xattrs']:raise ValueError('Unexpected new parent '+name)
 for name,item in patch.items():
  a=after[name]
  if a['sha256']!=item['sha256'] or a['uid']!=0 or a['gid']!=0 or a['mode']!=item['mode'] or a['mtime']!=EPOCH or a['hardlinks']!=[name]:raise ValueError('Patch result differs '+name)
