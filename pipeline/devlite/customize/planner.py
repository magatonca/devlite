"""Plano offline/exportação de configurações; não contém executor de instalação."""
import hashlib
import json
import os
import posixpath
import re
import subprocess
from pathlib import PurePosixPath
from ..runtime import owned_directory
from .manifest import SpecError, resolve
from .settings import render
from .layers import strategy


def read_json(path):
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise SpecError(f'Objeto JSON esperado: {path}')
    return value


def apt_metadata(entries):
    names = sorted(item['package'] for item in entries if item['provider'] == 'ubuntu')
    env = dict(os.environ, LC_ALL='C')
    policy = subprocess.run(['apt-cache', 'policy', *names], capture_output=True, text=True, env=env, check=True).stdout
    shown = subprocess.run(['apt-cache', 'show', *names], capture_output=True, text=True, env=env, check=True).stdout
    blocks, current = {}, None
    for line in policy.splitlines():
        if line and not line[0].isspace() and line.endswith(':'):
            current = line[:-1]
            blocks[current] = []
        elif current:
            blocks[current].append(line)
    records = {}
    for block in shown.split('\n\n'):
        fields = {}
        for line in block.splitlines():
            if line and not line[0].isspace() and ': ' in line:
                key, value = line.split(': ', 1)
                fields[key] = value
        if 'Package' in fields and 'Version' in fields:
            records[(fields['Package'], fields['Version'])] = fields
    result = {}
    for name in names:
        text = '\n'.join(blocks.get(name, []))
        candidate = next((line.split(':', 1)[1].strip() for line in text.splitlines() if line.strip().startswith('Candidate:')), None)
        fields = records.get((name, candidate), {})
        result[name] = {'candidate': candidate, 'architecture': fields.get('Architecture'),
                        'section': fields.get('Section'), 'depends': fields.get('Depends', ''),
                        'pre_depends': fields.get('Pre-Depends', ''),
                        'noble_archive_visible': bool(re.search(r'\bnoble(?:-updates|-security)?/(?:main|universe)\b', text)),
                        'evidence': text,
                        'limit': 'Cache local; sem refresh, sem autenticação nova e sem resolução transitiva do alvo.'}
    return result


def lock_blockers(lock, entries, sources, forbidden):
    if lock.get('schema') != 1 or lock.get('suite') != 'noble' or lock.get('architecture') != 'amd64':
        raise SpecError('Lock incompatível com a base')
    apt = lock.get('apt_packages', {})
    artifacts = lock.get('external_artifacts', {})
    if not isinstance(apt, dict) or not isinstance(artifacts, dict):
        raise SpecError('Mapas de lock inválidos')
    if set(apt) & set(forbidden):
        raise SpecError('Lock introduz provider APT proibido/conflitante')
    blockers = []
    if lock.get('resolved') is not True or lock.get('dependency_resolution_verified') is not True:
        blockers.append('Resolver e congelar a transação APT completa no contexto do alvo, incluindo dependências transitivas.')
    missing = []
    for item in entries:
        if item['provider'] == 'ubuntu':
            value = apt.get(item['package'], {})
            if (not isinstance(value, dict) or not value.get('version') or
                    not re.fullmatch(r'[0-9a-f]{64}', str(value.get('sha256', ''))) or
                    value.get('architecture') not in ('amd64', 'all') or value.get('origin') != 'Ubuntu'):
                missing.append(item['package'])
        else:
            source = sources['sources'].get(item['provider'], {})
            value = artifacts.get(item['id'], {})
            if not isinstance(value, dict):
                raise SpecError(f"Lock externo inválido: {item['id']}")
            if source.get('enabled') is not True:
                blockers.append(f"Origem externa não autorizada/habilitada: {item['provider']}.")
            if (not isinstance(value, dict) or not value.get('version') or
                    not re.fullmatch(r'[0-9a-f]{64}', str(value.get('sha256', '')))):
                blockers.append(f"Fixar versão, origem e SHA-256 do artefato externo: {item['id']}.")
            if item['id'] == 'typescript':
                if not re.fullmatch(r'sha512-[A-Za-z0-9+/]+={0,2}', str(value.get('integrity', ''))):
                    blockers.append('TypeScript requer dist.integrity SHA-512 e lock npm; nenhum script de ciclo de vida autorizado.')
            elif not re.fullmatch(r'[0-9A-Fa-f]{40}', str(value.get('signer_fingerprint', ''))):
                blockers.append(f"Conferir chave/fingerprint e assinatura de origem: {item['id']}.")
    if missing:
        blockers.append('Lock APT ainda incompleto: ' + ', '.join(sorted(missing)))
    return blockers


def make_plan(root, check_cache=False, audit_result=None):
    selection = read_json(root / 'packages/selection.json')
    sources = read_json(root / 'packages/sources.json')
    settings = read_json(root / 'config/customization.json')
    lock = read_json(root / 'config/customization-lock.json')
    if sources.get('schema') != 1 or not isinstance(sources.get('sources'), dict):
        raise SpecError('Catálogo de origens inválido')
    expected_kinds = {'ubuntu': 'apt', 'microsoft-vscode': 'apt', 'node-upstream': 'signed-tarball', 'npm-upstream': 'npm-artifact'}
    if set(sources['sources']) != set(expected_kinds):
        raise SpecError('Origens incompletas ou desconhecidas')
    for name, kind in expected_kinds.items():
        value = sources['sources'][name]
        if not isinstance(value, dict) or value.get('kind') != kind or value.get('external') is not (name != 'ubuntu'):
            raise SpecError(f'Origem incompatível: {name}')
    ubuntu = sources['sources']['ubuntu']
    if set(ubuntu.get('suites', [])) != {'noble', 'noble-updates', 'noble-security'} or set(ubuntu.get('components', [])) != {'main', 'universe'}:
        raise SpecError('Suites/componentes Ubuntu incompatíveis com o catálogo')
    if sources['sources']['microsoft-vscode'].get('uri') != 'https://packages.microsoft.com/repos/code':
        raise SpecError('Origem Microsoft inesperada')
    if sources['sources']['npm-upstream'].get('registry') != 'https://registry.npmjs.org/':
        raise SpecError('Registro npm inesperado')
    entries = resolve(selection)
    bundle = render(settings)
    if audit_result is not None:
        audit_result = dict(audit_result, prepared_files_masked_by_old_live=sorted(set(bundle['files']) & set(audit_result.get('live_configuration_paths', []))))
    blockers = lock_blockers(lock, entries, sources, selection['forbidden_apt'])
    blockers += ['Aprovação explícita para operações privilegiadas da Fase 4B ainda necessária.',
                 'Validar extração, whiteouts, diretórios opacos, capabilities e regeneração do delta live em laboratório.',
                 'Definir política de assinatura dos componentes modificados e validar instalador, BIOS e UEFI.',
                 'Executor de instalação/rebase não implementado nesta fase; apenas plano e arquivos preparados.']
    cache = apt_metadata(entries) if check_cache else None
    if cache is not None:
        for name, value in cache.items():
            if value['candidate'] in (None, '(none)') or value['architecture'] not in ('amd64', 'all') or not value['noble_archive_visible']:
                blockers.append(f'Candidato APT local ausente ou incompatível: {name}')
    return {
        'schema': 1, 'status': 'plano_validado_sem_execucao', 'ready_to_apply': False,
        'base': {'suite': 'noble', 'architecture': 'amd64', 'installed_layer': 'minimal.squashfs',
                 'live_leaf': 'minimal.live.squashfs', 'source_type': 'fsimage-layered'},
        'packages': entries, 'apt_cache': cache, 'settings_bundle': bundle,
        'layer_audit': audit_result, 'stages': strategy(), 'blockers': blockers,
        'invariants': ['não modificar ISO original', 'não modificar host', 'preservar instalador e EFI',
                       'nenhuma execução de chroot/montagem/instalação', 'nenhuma exclusão automática'],
        'source_files_sha256': {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in
                                ('packages/selection.json', 'packages/sources.json', 'config/customization.json', 'config/customization-lock.json')}
    }


def export_plan(root, plan):
    # Destino é sempre um diretório novo em work; não há parâmetro target-root.
    workspace = owned_directory(root / 'work', 'phase4a-')
    overlay = workspace / 'overlay'
    overlay.mkdir()
    manifest = {}
    for name, value in plan['settings_bundle']['files'].items():
        relative = PurePosixPath(name)
        if relative.is_absolute() or '..' in relative.parts or not relative.parts:
            raise SpecError(f'Caminho inseguro no overlay: {name}')
        if relative.parts[0] not in ('etc', 'usr'):
            raise SpecError('Destino de configuração não permitido')
        path = overlay / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if value['kind'] == 'text':
            with path.open('x') as stream:
                stream.write(value['content'])
            path.chmod(value['mode'])
            manifest[name] = dict(value, sha256=hashlib.sha256(value['content'].encode()).hexdigest())
            del manifest[name]['content']
        elif value['kind'] == 'symlink':
            target = PurePosixPath(value['target'])
            normalized = posixpath.normpath(str(relative.parent / target))
            if target.is_absolute() or normalized.startswith('../'):
                raise SpecError('Symlink sai da raiz preparada')
            path.symlink_to(value['target'])
            manifest[name] = value
        else:
            raise SpecError('Tipo de entrada de overlay não permitido')
    (workspace / 'plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n')
    (workspace / 'overlay-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    return workspace
