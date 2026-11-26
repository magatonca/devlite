"""Metadata for v5 leaves; preserve inherited manifests and technical source IDs."""
import re
from pipeline.devlite.minimal_build import make_md5
from pipeline.devlite.release_layers import manifests, delta_manifest
INSTALL='minimal.visual.fix.v5.squashfs'
LIVE='minimal.visual.live.fix.v5.squashfs'
OLD_INSTALL='minimal.visual.fix.squashfs'
OLD_LIVE='minimal.visual.live.fix.squashfs'


def render_catalog(document,original_size,added_size):
    if type(original_size) is not int or original_size<=0 or type(added_size) is not int or added_size<=0:
        raise ValueError('Invalid measured layer sizes')
    if len(re.findall(r'(?m)^  path: '+re.escape(OLD_INSTALL)+r'$',document))!=1:
        raise ValueError('Unexpected v4 installation source')
    if len(re.findall(r'(?m)^  size: '+str(original_size)+r'$',document))!=1:
        raise ValueError('Original installation size differs')
    result=document.replace('  path: '+OLD_INSTALL+'\n','  path: '+INSTALL+'\n')
    return re.sub(r'(?m)^  size: '+str(original_size)+r'$', '  size: '+str(original_size+added_size),result)


def render_grub(document):
    lines=document.splitlines(keepends=True);count=0
    for i,line in enumerate(lines):
        if not re.match(r'^\s*linux\s+/casper/vmlinuz(?:\s|$)',line):continue
        tokens=re.findall(r'(?<!\S)layerfs-path=([^\s]+)',line)
        if tokens!=[OLD_LIVE]:raise ValueError('Unexpected Live layer argument')
        if not all(re.search(r'(?<!\S)'+arg+r'(?!\S)',line) for arg in ('username=devlite','hostname=devlite')):
            raise ValueError('Inherited live identity missing')
        lines[i]=line.replace('layerfs-path='+OLD_LIVE,'layerfs-path='+LIVE);count+=1
    if not count:raise ValueError('No Live kernel command')
    return ''.join(lines)


def package_manifests(base,live,old_base,old_live):
    result=manifests(base,live,old_live)
    # Never claim that SSH was in the unchanged minimal.squashfs.
    return {'devlite-base.manifest.full':result['devlite-base.manifest.full'],
      'filesystem.manifest':result['filesystem.manifest'],
      INSTALL.removesuffix('.squashfs')+'.manifest':delta_manifest(old_base,result['devlite-base.manifest.full'],'v4-base.manifest.full','v5-base.manifest.full'),
      LIVE.removesuffix('.squashfs')+'.manifest':delta_manifest(old_live,result['filesystem.manifest'],'v4-live.manifest.full','v5-live.manifest.full')}


def checksum_layers(inherited,new):
    entries={}
    for line in inherited.splitlines():
        fields=line.split()
        if len(fields)!=2 or not re.fullmatch('[a-f0-9]{64}',fields[0]):raise ValueError('Malformed inherited checksum')
        name=fields[1].lstrip('*')
        if name in entries:raise ValueError('Duplicate inherited layer')
        entries[name]=fields[0]
    expected={'minimal.squashfs','minimal.visual.squashfs','minimal.visual.fix.squashfs','minimal.visual.live.squashfs','minimal.visual.live.fix.squashfs'}
    if set(entries)!=expected or set(new)!={INSTALL,LIVE}:raise ValueError('Unexpected seven-layer layout')
    if any(not re.fullmatch('[a-f0-9]{64}',h) for h in new.values()):raise ValueError('Invalid new checksum')
    entries.update(new)
    return ''.join(h+' *'+n+'\n' for n,h in sorted(entries.items()))
