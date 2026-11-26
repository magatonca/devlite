"""Supported installer whitelabel overrides; never patch the signed snap."""
import hashlib
import subprocess
from v5.image import confined, put


def whitelabel(document):
    if document.count("flavor: xubuntu\n")!=1 or "app-name:" in document or document.count('image: "mascot.png"')!=3:
        raise ValueError("Unexpected inherited whitelabel")
    return document.replace("flavor: xubuntu\n",'flavor: xubuntu\napp-name: "Instalar DevLite OS 1.0"\n',1).replace('image: "mascot.png"','image: "devlite.png"')


def welcome(document):
    if document.count("Welcome to Xubuntu")!=1 or document.count('src="mascot.svg"')!=1:
        raise ValueError("Unexpected inherited welcome slide")
    return document.replace("Welcome to Xubuntu","Welcome to DevLite OS").replace('src="mascot.svg"','src="devlite.svg"')


def apply(root):
    relative="usr/share/desktop-provision/whitelabel.yaml"
    source=confined(root,relative)
    if not source.is_file():raise ValueError("Missing installer whitelabel")
    put(root,relative,whitelabel(source.read_text()))
    icon=confined(root,"usr/share/icons/hicolor/scalable/apps/devlite.svg")
    if icon.is_symlink() or not icon.is_file():raise ValueError("Missing inherited DevLite identity")
    svg=icon.read_text()
    put(root,"usr/share/desktop-provision/images/devlite.svg",svg)
    put(root,"usr/share/desktop-provision/slides/1/devlite.svg",svg)
    slide="usr/share/desktop-provision/slides/1/slide_en_US.html"
    put(root,slide,welcome(confined(root,slide).read_text()))
    put(root,"usr/share/desktop-provision/slides/1/slide_pt_BR.html",'''<html><body style="background:#17202b;color:#f0f6fc;font-family:sans-serif;padding:60px"><h1>Bem-vindo ao DevLite OS</h1><img src="devlite.svg" width="180" height="180"><p>Developer + Network Edition</p><p>Use o DevControl 2.0 para gerenciar os serviços de desenvolvimento.</p><p>Baseado no Xubuntu 24.04 LTS, com ambiente XFCE. As licenças e atribuições dos projetos originais foram preservadas.</p></body></html>''')
    output=confined(root,"usr/share/desktop-provision/images/devlite.png")
    if output.exists() or output.is_symlink():raise ValueError("Unexpected PNG target")
    # Existing target SVG loader; no host dependency or package installation.
    script='''import gi
 gi.require_version("GdkPixbuf","2.0")
 from gi.repository import GdkPixbuf
 p=GdkPixbuf.Pixbuf.new_from_file_at_scale("/usr/share/desktop-provision/images/devlite.svg",256,256,True)
 p.savev("/usr/share/desktop-provision/images/devlite.png","png",[],[])
'''
    script="\n".join(line[1:] if line.startswith(" ") else line for line in script.splitlines())
    result=subprocess.run(["/usr/sbin/chroot",str(root),"/usr/bin/python3","-I","-c",script],capture_output=True,text=True,timeout=30)
    if result.returncode:raise ValueError("Target SVG rasterization failed: "+result.stderr[-2000:])
    if output.is_symlink() or not output.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):raise ValueError("Invalid rendered identity")
    output.chmod(0o644)
    return {"whitelabel_app_name":"Instalar DevLite OS 1.0","image_sha256":hashlib.sha256(output.read_bytes()).hexdigest(),"technical_flavor":"xubuntu","signed_snap_modified":False,"upstream_support_and_licenses_preserved":True,"runtime_installer_review_required":True}
