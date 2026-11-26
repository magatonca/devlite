"""Generate isolated DevLite Modern prototypes. No apply/install/mount/network API."""
import copy
import hashlib
import json
import os
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from .runtime import owned_directory
from .browser import read_member, replace_keys

RESERVE = 20 * 1024**3
PANEL = 'etc/xdg/xdg-xubuntu/xfce4/panel/default.xml'
CHANNEL = 'etc/xdg/xdg-xubuntu/xfce4/xfconf/xfce-perchannel-xml/'
THEME = 'Greybird-dark'
ICONS = 'elementary-xfce-dark'
WALLPAPER = '/usr/share/backgrounds/devlite/devlite-modern.svg'

def check_space(free):
    if free < RESERVE + 16*1024**2:
        raise ValueError('Reserva de 20 GiB mais orçamento de 16 MiB não atendida')

def prop(parent, name, kind, value):
    nodes = parent.findall("property[@name='" + name + "']")
    if len(nodes) > 1: raise ValueError('Propriedade duplicada: '+name)
    node = nodes[0] if nodes else ET.SubElement(parent, 'property', name=name)
    node.set('type', kind); node.set('value', str(value))
    return node

def render_channel(text, expected, changes):
    root = ET.fromstring(text)
    if root.tag != 'channel' or root.get('name') != expected:
        raise ValueError('Canal XFCE inesperado')
    for path, kind, value in changes:
        names = path.strip('/').split('/'); parent = root
        for name in names[:-1]:
            nodes = parent.findall("property[@name='"+name+"']")
            if len(nodes)>1: raise ValueError('Grupo duplicado')
            parent = nodes[0] if nodes else ET.SubElement(parent,'property',name=name,type='empty')
        prop(parent, names[-1], kind, value)
    return ET.tostring(root, encoding='unicode')+'\n'

def panel(text):
    root=ET.fromstring(text)
    if root.tag!='channel' or root.get('name')!='xfce4-panel': raise ValueError('Painel inválido')
    panels=root.findall("property[@name='panels']")
    if len(panels)!=1: raise ValueError('Lista de painéis ambígua')
    ids=panels[0].findall('value')
    if len(ids)!=1 or ids[0].get('value')!='1': raise ValueError('Layout diferente do painel homologado')
    nodes=panels[0].findall("property[@name='panel-1']")
    if len(nodes)!=1: raise ValueError('Painel principal ausente')
    p=nodes[0]
    for name,kind,value in [('position','string','p=10;x=0;y=0'),('size','uint','40'),
        ('length','uint','90'),('length-adjust','bool','false'),('position-locked','bool','true'),
        ('autohide-behavior','uint','0'),('span-monitors','bool','false'),
        ('enter-opacity','uint','100'),('leave-opacity','uint','100')]: prop(p,name,kind,value)
    return ET.tostring(root,encoding='unicode')+'\n'

def wallpaper():
    return '\n'.join(['<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">',
      '<rect width="1920" height="1080" fill="#171c24"/>',
      '<path d="M0 820 H1920 M1280 0 V1080" stroke="#263342" stroke-width="2"/>',
      '<path d="M260 450 V620 H430" fill="none" stroke="#348bd6" stroke-width="8"/>',
      '<text x="470" y="550" font-family="sans-serif" font-size="64" fill="#e3e9f0">DevLite OS</text>',
      '<text x="474" y="600" font-family="sans-serif" font-size="24" fill="#91a3b7">Developer + Network Edition</text>',
      '</svg>',''])

def prepare(root):
    if os.geteuid()==0: raise ValueError('Preparar sem root')
    root=Path(root).resolve();check_space(shutil.disk_usage(root).free)
    source=root/'work/release-cezaiofx/published-casper/minimal.squashfs'
    job=owned_directory(root/'work','modern-preview-');(job/'logs').mkdir()
    original={}
    names=[PANEL,CHANNEL+'xsettings.xml',CHANNEL+'xfwm4.xml',
      'etc/lightdm/lightdm-gtk-greeter.conf','usr/share/themes/Greybird-dark/index.theme',
      'usr/share/themes/Greybird-dark/xfwm4/themerc','usr/share/icons/elementary-xfce-dark/index.theme',
      'usr/share/icons/DMZ-White/index.theme',CHANNEL+'xfce4-keyboard-shortcuts.xml']
    for i,name in enumerate(names):
        text=read_member(job,source,name,'source-'+str(i))
        original[name]=text
        dest=job/'sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(text)
    output={PANEL:panel(original[PANEL]),
      CHANNEL+'xsettings.xml':render_channel(original[CHANNEL+'xsettings.xml'],'xsettings',[
        ('Net/ThemeName','string',THEME),('Net/IconThemeName','string',ICONS),
        ('Gtk/CursorThemeName','string','DMZ-White'),('Gtk/CursorThemeSize','int','24'),
        ('Gtk/EnableAnimations','bool','false')]),
      CHANNEL+'xfwm4.xml':render_channel(original[CHANNEL+'xfwm4.xml'],'xfwm4',[
        ('general/theme','string',THEME),('general/use_compositing','bool','false')]),
      'etc/lightdm/lightdm-gtk-greeter.conf':replace_keys(original['etc/lightdm/lightdm-gtk-greeter.conf'],{
        'theme-name':THEME,'icon-theme-name':ICONS,'cursor-theme-name':'DMZ-White',
        'background':WALLPAPER,'user-background':'false','transition-duration':'0','transition-type':'none'},'greeter'),
      'etc/dconf/db/devlite.d/00-modern':"[org/gnome/desktop/interface]\ncolor-scheme='prefer-dark'\nenable-animations=false\n",
      WALLPAPER.lstrip('/'):wallpaper()}
    hashes={}
    for name,text in output.items():
        check_space(shutil.disk_usage(root).free)
        dest=job/'preview-only'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(text)
        hashes[name]=hashlib.sha256(dest.read_bytes()).hexdigest()
    report={'schema':1,'status':'prototype_only','applied':False,'browser_dependency':'blocked_pending_privileged_contract',
      'source':str(source),'source_content_hashes':{n:hashlib.sha256(t.encode()).hexdigest() for n,t in original.items()},
      'preview_sha256':hashes,'reserve_bytes':RESERVE,'free_bytes':shutil.disk_usage(root).free,
      'new_packages':[],'new_services':[],'theme':THEME,'icons':ICONS,'additional_dock':False,
      'keyboard_shortcuts':'original stored unchanged; not included in patch',
      'menu':'retain existing DevLite merged menu and Whisker plugin',
      'live_and_installed':'future merge into full views; never copy directly into delta',
      'runtime_validation':'not_tested','gtk4_dark':'dconf draft; profile, schemas and sandbox need guest validation',
      'first_session':'future adapter must replace Greybird hardcode only in a new payload; current script unchanged'}
    (job/'preview.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return job/'preview.json'
