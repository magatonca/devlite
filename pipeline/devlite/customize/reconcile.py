"""Plano de delta entre visões completas; não monta, remove ou gera SquashFS."""
from pathlib import PurePosixPath
from .manifest import SpecError


def plan_delta(base,live,base_versions,live_versions):
    if base_versions.keys()-live_versions.keys() or any(base_versions[p]!=live_versions[p] for p in base_versions):
        raise SpecError('Bancos base/live não reconciliados')
    for tree in (base,live):
        for name,value in tree.items():
            path=PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts or name in ('','.'): raise SpecError('Path de delta inseguro')
            if value.get('type') not in ('file','dir','symlink','char','block','fifo'): raise SpecError('Tipo de delta inválido')
            if any(key.startswith(('trusted.overlay.','user.overlay.')) for key in value.get('xattrs',{})):
                raise SpecError('Atributos privados OverlayFS devem ser regenerados')
    removals=sorted(base.keys()-live.keys(),key=lambda p:(-len(PurePosixPath(p).parts),p))
    puts=[{'path':p,'entry':live[p],'replace_type':p in base and base[p]['type']!=live[p]['type']} for p in sorted(live) if base.get(p)!=live[p]]
    return {'schema':1,'whiteouts_required':removals,'put':puts,'requires_overlay_capture':True,
            'regenerate_private_xattrs':True,'hardlinks_require_group_validation':True,
            'apply_implemented':False,'acceptance':'nova base + delta deve reproduzir integralmente a visão live e seu banco dpkg; preservar snapshots do instalador'}
