"""Auditoria de sobreposições por listagens, sem extrair ou montar rootfs."""
import hashlib
from .manifest import SpecError

SENSITIVE = ('var/lib/dpkg/', 'var/lib/apt/', 'etc/apt/', 'etc/default/', 'etc/skel/',
             'etc/xdg/', 'var/lib/snapd/', 'etc/subiquity/')


def paths_from_listing(text):
    paths = {}
    for line in text.splitlines():
        marker = 'squashfs-root/'
        if marker not in line:
            continue
        name = line.split(marker, 1)[1].split(' -> ', 1)[0]
        if not name or name.startswith('/') or '..' in name.split('/'):
            raise SpecError('Caminho inseguro na listagem de camada')
        paths[name] = line[0]
    if not paths:
        raise SpecError('Listagem de camada vazia ou inválida')
    return paths


def audit(base_text, live_text):
    base, live = paths_from_listing(base_text), paths_from_listing(live_text)
    overlaps = sorted(name for name in base.keys() & live.keys() if base[name] != 'd' or live[name] != 'd')
    return {'base_entries': len(base), 'live_entries': len(live), 'overlapping_non_directories': len(overlaps),
            'sensitive_overlaps': [name for name in overlaps if name.startswith(SENSITIVE)],
            'live_configuration_paths': sorted(name for name in live if name.startswith(('etc/default/', 'etc/xdg/', 'etc/skel/', 'etc/mysql/')) or name in ('etc/timezone', 'etc/localtime', 'etc/devlite-release')),
            'dpkg_status_shadowed': 'var/lib/dpkg/status' in overlaps,
            'whiteout_entries': sorted(name for name in live if '.wh.' in name or live[name] == 'c'),
            'xattrs_and_opaque_directories_audit_required': True,
            'limits': 'Listagens históricas, sem reautenticação atual dos binários; sobreposição não prova igualdade de bytes, xattrs ou remoções.',
            'listing_sha256': {'base': hashlib.sha256(base_text.encode()).hexdigest(),
                               'live': hashlib.sha256(live_text.encode()).hexdigest()}}


def strategy():
    return [
        {'id': 'verify', 'after': [], 'privileged': False, 'network': False,
         'action': 'Autenticar ISO e verificar hashes das duas camadas; inventariar UID/GID, modos, capabilities e xattrs.'},
        {'id': 'resolve', 'after': ['verify'], 'privileged': False, 'network': True,
         'action': 'Resolver dependências no contexto APT do alvo descartável; congelar versões, origens, hashes e metadados assinados; baixar somente após aprovação.'},
        {'id': 'extract', 'after': ['verify'], 'privileged': True, 'network': False,
         'action': 'Extrair base preservando ownership/xattrs; compor visão original live somente para leitura em namespace isolado; classificar delta de pacotes e estado snap.'},
        {'id': 'customize-base', 'after': ['resolve', 'extract'], 'privileged': True, 'network': False,
         'action': 'Em alvo isolado autorizado: instalar artefatos travados, aplicar configurações, gerar locale, restaurar bloqueio temporário de daemons e desativar serviços selecionados.'},
        {'id': 'rebase-live', 'after': ['customize-base'], 'privileged': True, 'network': False,
         'action': 'Criar live sobre a nova base; reinstalar conjunto exclusivamente live e preservar Bootstrap/Subiquity e snap seeds. Não copiar dpkg/status antigo. Reconciliar arquivos e remoções; capturar upperdir, whiteouts e xattrs corretamente.'},
        {'id': 'pack', 'after': ['rebase-live'], 'privileged': True, 'network': False,
         'action': 'Gerar duas squashfs xz sequencialmente com um processo; preservar metadados. Regenerar manifests completos e deltas, tamanhos, catálogo e hashes; definir assinatura própria antes de distribuir.'},
        {'id': 'validate', 'after': ['pack'], 'privileged': False, 'network': False,
         'action': 'Conferir consistência base/live, instalador preservado e diferenças permitidas; integrar posteriormente ao boot replay da 3B. Boot/instalação requerem VMs autorizadas.'}
    ]
