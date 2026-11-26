"""Offline native browser planning. No installer, network, mounts or ISO builder."""
import configparser
import copy
import re
import subprocess
import hashlib
import json
import os
import shutil
import shlex
from pathlib import Path
from .runtime import owned_directory
from .structure import digest
from .release_contract import ROOT
from .customize.manifest import SpecError
from .customize.installation import snapshot_indexes, run, installed, compatibility, estimate, apt_config, parse_transaction, control

DESKTOP = 'org.gnome.Epiphany.desktop'
MIMES = ('text/html', 'application/xhtml+xml', 'x-scheme-handler/http', 'x-scheme-handler/https')
HELPERS = ('etc/xdg/xfce4/helpers.rc', 'etc/xdg/xdg-xubuntu/xfce4/helpers.rc',
           'etc/skel/.config/xfce4/helpers.rc')
MIME_FILES = ('etc/xdg/xfce-mimeapps.list', 'etc/xdg/xdg-xubuntu/xfce-mimeapps.list',
              'etc/skel/.config/mimeapps.list')
FILES = HELPERS + MIME_FILES
REQUIRED_PACKAGES = {'epiphany-browser', 'epiphany-browser-data', 'ca-certificates', 'dbus-user-session'}
FORBIDDEN = {'firefox', 'chromium-browser', 'nodejs', 'npm', 'node-typescript',
             'docker-ce', 'docker-ce-cli', 'containerd.io', 'docker-compose-plugin'}

def validate(spec):
    expected = {'schema': 1, 'suite': 'noble', 'architecture': 'amd64', 'provider': 'ubuntu',
                'package': 'epiphany-browser', 'scope': 'installed-and-live', 'native_deb': True,
                'snap_required': False, 'desktop_id': DESKTOP, 'xfce_helper': 'epiphany',
                'visual_changes': False, 'generate_iso': False, 'install_authorized': False,
                'download_authorized': False}
    if any(type(spec.get(k)) is not type(v) or spec[k] != v for k, v in expected.items()):
        raise SpecError('Perfil do navegador incompatível ou execução habilitada')
    if len(spec.get('requested', [])) != len(REQUIRED_PACKAGES) or set(spec['requested']) != REQUIRED_PACKAGES:
        raise SpecError('Solicitação do navegador incompleta ou ampliada')
    source = Path(spec.get('input_job', ''))
    if source.is_absolute() or source.parts[:1] != ('work',) or '..' in source.parts or len(source.parts) != 2:
        raise SpecError('Fonte deve ser um job do projeto')



def selection_with_browser(selection, spec):
    """Compose a new logical recipe; never overwrite the historical 47-item selection."""
    validate(spec)
    from .customize.manifest import resolve
    resolve(selection)
    result = copy.deepcopy(selection)
    known = {p['id']: p for p in resolve(result)}
    for package in ('dbus-user-session', 'epiphany-browser-data', 'epiphany-browser'):
        if package in known:
            if known[package]['provider'] != 'ubuntu' or known[package]['package'] != package:
                raise SpecError('Colisão de provider de navegador')
            continue
        dependencies = ['ca-certificates','dbus-user-session','epiphany-browser-data'] if package == 'epiphany-browser' else []
        item = {'id': package, 'provider': 'ubuntu', 'package': package,
                'depends_on': dependencies, 'scope': 'installed-and-live'}
        result['categories']['interface'].append(item); known[package] = item
    resolve(result)
    return result

def replace_keys(text, updates, section=None):
    """Change only named keys, retaining other sections, keys and comments."""
    lines = text.splitlines(keepends=True)
    output, seen, active, found = [], set(), section is None, section is None
    def add_missing():
        for key, value in updates.items():
            if key not in seen:
                if output and not output[-1].endswith('\n'): output[-1] += '\n'
                output.append(key + '=' + value + '\n'); seen.add(key)
    for line in lines:
        stripped = line.strip()
        if section is not None and stripped.startswith('[') and stripped.endswith(']'):
            if active: add_missing()
            active = stripped == '[' + section + ']'
            if active and found: raise SpecError('Seção duplicada: ' + section)
            found |= active
        if active and '=' in line and not stripped.startswith(('#', ';')):
            key = line.split('=', 1)[0].strip()
            if key in updates:
                if key in seen: raise SpecError('Chave duplicada: ' + key)
                output.append(key + '=' + updates[key] + '\n'); seen.add(key); continue
        output.append(line)
    if not found:
        if output and not output[-1].endswith('\n'): output[-1] += '\n'
        output.append('[' + section + ']\n')
    add_missing()
    return ''.join(output)


def settings(existing):
    if set(existing) - set(FILES): raise SpecError('Configuração fora da lista permitida')
    result = {}
    for name in FILES:
        old = existing.get(name, '')
        if '\x00' in old: raise SpecError('Configuração binária inesperada')
        result[name] = replace_keys(old, {'WebBrowser': 'epiphany'}) if name in HELPERS else replace_keys(
            old, {key: DESKTOP + ';' for key in MIMES}, 'Default Applications')
    return result


def audit_transaction(target, before):
    """Browser correction may add dependencies; it cannot upgrade the accepted baseline."""
    after = target['final_versions']
    if any(after.get(k) != v for k, v in before.items()):
        raise SpecError('Correção do navegador alteraria pacote já homologado')
    if not REQUIRED_PACKAGES <= set(after): raise SpecError('Navegador ou suporte obrigatório ausente')
    for item in target['changes']:
        if item['previous'] is not None or item['package'].split(':')[0] in FORBIDDEN | {'snapd'}:
            raise SpecError('Upgrade/provider não permitido nesta correção')
    return True



def audit_configuration(configs, desktop, xfce_helper, status_text, expected_versions):
    """Static gate for future extracted FULL views; never claims graphical success."""
    actual = installed(status_text)
    if actual != expected_versions or not REQUIRED_PACKAGES <= set(actual):
        raise SpecError('Estado dpkg difere do plano de navegador')
    def ini(text):
        p = configparser.ConfigParser(interpolation=None, strict=True)
        p.optionxform = str
        try: p.read_string(text)
        except configparser.Error as error: raise SpecError(str(error)) from error
        return p
    if set(configs) != set(FILES): raise SpecError('Configurações de navegador incompletas')
    for name, text in configs.items():
        if name in HELPERS:
            if ini('[Helpers]\n'+text).get('Helpers','WebBrowser',fallback='') != 'epiphany':
                raise SpecError('Helper padrão incorreto')
        else:
            parsed = ini(text)
            if any(parsed.get('Default Applications', m, fallback='') != DESKTOP+';' for m in MIMES):
                raise SpecError('Associação MIME incompleta')
    entry = ini(desktop)
    if not entry.has_section('Desktop Entry'): raise SpecError('Desktop entry ausente')
    d = entry['Desktop Entry']
    if d.get('Type') != 'Application' or d.get('Hidden','false') != 'false' or d.get('NoDisplay','false') != 'false':
        raise SpecError('Navegador invisível no menu')
    if d.get('Terminal','false') != 'false': raise SpecError('Navegador não gráfico')
    if d.get('OnlyShowIn') and 'XFCE' not in d['OnlyShowIn'].split(';'): raise SpecError('Desktop entry exclui XFCE')
    if 'XFCE' in d.get('NotShowIn','').split(';'): raise SpecError('Desktop entry exclui XFCE')
    try: command = shlex.split(d.get('Exec',''))
    except ValueError as error: raise SpecError('Exec inválido') from error
    if not command or command[0] not in ('epiphany','epiphany-browser','/usr/bin/epiphany','/usr/bin/epiphany-browser'):
        raise SpecError('Exec não inicia navegador nativo diretamente')
    if not {'Network','WebBrowser'} <= set(d.get('Categories','').split(';')):
        raise SpecError('Navegador fora das categorias de menu')
    if not set(MIMES) <= set(d.get('MimeType','').split(';')): raise SpecError('Desktop entry sem MIME esperado')
    helper = ini(xfce_helper)['Desktop Entry']
    if helper.get('X-XFCE-Category') != 'WebBrowser' or 'epiphany' not in helper.get('X-XFCE-Binaries','').split(';'):
        raise SpecError('Helper XFCE ausente ou incompatível')
    return {'static_integration':'passed','graphical_launch':'not_tested','post_install_persistence':'not_tested'}

def effective_status(base_text, live_text, base_manifest, live_manifest):
    def manifest(text):
        result = {}
        for line in text.splitlines():
            parts = line.split()
            if not parts or parts[0].startswith('snap:'): continue
            if len(parts) != 2 or parts[0] in result: raise SpecError('Manifest inválido')
            result[parts[0]] = parts[1]
        return result
    base = installed(base_text)
    if base != manifest(base_manifest): raise SpecError('Status Base difere do manifest publicado')
    live_text = base_text if live_text is None else live_text
    if installed(live_text) != manifest(live_manifest):
        raise SpecError('Status Live ausente/divergente; não tratar delta como rootfs independente')
    return {'base': base_text, 'live': live_text}


def read_member(work, image, name, label, optional=False):
    listing = run(work, label + '-list', ['unsquashfs', '-processors', '1', '-l', str(image), name]).stdout
    if 'squashfs-root/' + name not in listing:
        if optional: return None
        raise SpecError('Arquivo obrigatório ausente na camada: ' + name)
    return run(work, label, ['unsquashfs', '-processors', '1', '-cat', str(image), name]).stdout


def resolve_browser(work, name, status, requested, forbidden):
    state = installed(status)
    path = work / (name + '.status'); path.write_text(status)
    preferences = work / (name + '.preferences')
    conf = work / (name + '.apt.conf'); conf.write_text(apt_config(work, path, preferences))
    preferences.write_text(''.join(f'Package: {pkg}\nPin: version {ver}\nPin-Priority: 1001\n\n' for pkg, ver in state.items()))
    env = dict(os.environ, APT_CONFIG=str(conf), LC_ALL='C', LANG='C')
    check = run(work, name + '-check', ['apt-get', '-s', 'check'], env, allowed=(0, 100))
    if check.returncode:
        raise SpecError(name + ': dependências iniciais quebradas; ver logs')
    result = run(work, name + '-resolve', ['apt-get', '-s', '--no-remove', '--no-install-recommends', 'install', *requested], env, allowed=(0, 100))
    if result.returncode:
        raise SpecError(name + ': APT não encontrou solução; nenhuma instalação executada')
    changes = parse_transaction(result.stdout, forbidden)
    records = {}
    if changes:
        shown = run(work, name + '-records', ['apt-cache', 'show', *[item['package'] + '=' + item['version'] for item in changes]], env)
        for record in control(shown.stdout):
            if 'Package' in record and 'Version' in record:
                records[(record['Package'], record['Version'])] = record
    for item in changes:
        record = records.get((item['package'].split(':')[0], item['version']), {})
        if record.get('Architecture') not in ('amd64', 'all') or not re.fullmatch('[0-9a-f]{64}', record.get('SHA256','')):
            raise SpecError('Metadados incompletos: ' + item['package'])
        filename = record.get('Filename','')
        if not filename.startswith('pool/') or '..' in Path(filename).parts:
            raise SpecError('Caminho de pacote inválido')
        if item['previous'] and subprocess.run(['dpkg','--compare-versions',item['version'],'lt',item['previous']]).returncode == 0:
            raise SpecError('Downgrade recusado: ' + item['package'])
        item.update(architecture=record['Architecture'], sha256=record['SHA256'], filename=filename,
                    download_bytes=int(record['Size']), installed_bytes=int(record.get('Installed-Size','0'))*1024,
                    depends=record.get('Depends',''), pre_depends=record.get('Pre-Depends',''), origin='Ubuntu')
    final = dict(state)
    final.update({item['package'].split(':')[0]: item['version'] for item in changes})
    if any(pkg not in final for pkg in requested):
        raise SpecError('Pacote solicitado ausente da solução')
    return {'status_sha256': hashlib.sha256(status.encode()).hexdigest(), 'installed_count':len(state),
            'changes':changes, 'requested_already_satisfied':sorted(set(requested)-{i['package'].split(':')[0] for i in changes}),
            'final_versions':final, 'download_bytes':sum(i['download_bytes'] for i in changes),
            'gross_installed_bytes':sum(i['installed_bytes'] for i in changes)}

def prepare(root=ROOT):
    if os.geteuid() == 0 or os.getuid() != 1000: raise SpecError('Preparar como magaton')
    spec_path = root / 'packages/browser.json'
    spec = json.loads(spec_path.read_text()); validate(spec)
    # Existing read-only validator checks seals, root-owned receipts and all published file hashes.
    from .public_iso import public_inputs
    source = root / spec['input_job']
    public_inputs(source, spec['application_sha256'])
    work = owned_directory(root / 'work', 'browser-')
    for name in ('logs', 'empty', 'lists/partial', 'cache/archives/partial'):
        (work / name).mkdir(parents=True, exist_ok=True)
    for name in ('empty.conf', 'preferences', 'extended_states'): (work / name).write_text('')
    report = {'schema': 1, 'status': 'preparing', 'workspace': str(work), 'network_used': False,
              'installation_executed': False, 'ready_to_install': False, 'iso_generated': False,
              'source': str(source), 'spec_sha256': digest(spec_path), 'code_sha256': {p: digest(root/p) for p in ('pipeline/devlite/browser.py','scripts/preparar-navegador.py')}, 'blockers': []}
    try:
        selection = selection_with_browser(json.loads((root/'packages/selection.json').read_text()), spec)
        (work/'selection-preview.json').write_text(json.dumps(selection,ensure_ascii=False,indent=2)+'\n')
        report['indexes'], report['blockers'] = snapshot_indexes(work)
        casper = source / 'published-casper'
        base = read_member(work, casper/'minimal.squashfs', 'var/lib/dpkg/status', 'base-status')
        live = read_member(work, casper/'minimal.live.squashfs', 'var/lib/dpkg/status', 'live-status', True)
        statuses = effective_status(base, live, (casper/'devlite-base.manifest.full').read_text(),
                                   (casper/'filesystem.manifest').read_text())
        targets, previews = {}, {}
        for view, status in statuses.items():
            # Pin every accepted package, not only boot/installer, to avoid incidental upgrades.
            target = resolve_browser(work, view, status, sorted(REQUIRED_PACKAGES), FORBIDDEN)
            audit_transaction(target, installed(status)); targets[view] = target
            existing = {}
            for i, name in enumerate(FILES):
                content = None
                if view == 'live': content = read_member(work, casper/'minimal.live.squashfs', name, view+'-config-'+str(i)+'-delta', True)
                if content is None: content = read_member(work, casper/'minimal.squashfs', name, view+'-config-'+str(i)+'-base', True)
                if content is not None: existing[name] = content
            rendered = settings(existing); previews[view] = {}
            for name, text in rendered.items():
                out = work/'settings-preview'/view/name; out.parent.mkdir(parents=True, exist_ok=True); out.write_text(text)
                previews[view][name] = {'source_sha256': hashlib.sha256(existing[name].encode()).hexdigest() if name in existing else None,
                                      'sha256': hashlib.sha256(text.encode()).hexdigest(), 'mode': '0644',
                                      'future_target_uid': 0, 'future_target_gid': 0}
        report['targets'] = targets; report['settings_preview'] = previews
        report['reconciliation'] = compatibility(targets['base'], targets['live'])
        if report['reconciliation']['base_packages_missing_live'] or report['reconciliation']['common_version_conflicts']:
            raise SpecError('Resultados Base/Live incompatíveis')
        unique = {}
        for t in targets.values():
            for p in t['changes']:
                key = p['filename']
                if key in unique and unique[key]['sha256'] != p['sha256']: raise SpecError('Artefato conflitante')
                unique[key] = p
        report['artifacts'] = sorted(unique.values(), key=lambda x: x['package'])
        report['download_bytes_unique'] = sum(p['download_bytes'] for p in unique.values())
        report['resources'] = estimate(targets['base'], targets['live'], shutil.disk_usage(root).free)
        report['status'] = 'dependencies_resolved_offline'
        report['resources']['existing_installation_gate_bytes'] = 56*1024**3
        if shutil.disk_usage(root).free < 56*1024**3:
            report['blockers'].append('Reserva de 56 GiB do instalador existente não atendida; não reduzir o limite.')
        if not report['resources']['sufficient']:
            report['blockers'].append('Estimativa conservadora de disco não atendida; nenhuma limpeza autorizada.')
        report['blockers'] += ['Aquisição dos .deb não autorizada nesta etapa.',
            'Aplicação em cópias Base/Live exige contrato novo e autorização privilegiada; não reutilizar executor aditivo.',
            'Reconciliar delta e testar sessão XFCE real Live e instalada antes da única geração final.',
            'Preservar sandbox WebKit; não desabilitar AppArmor, user namespaces ou sandbox para contornar falhas.']
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        report['status'] = 'blocked'; report['blockers'].append(str(error))
    (work/'browser-plan.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    return work/'browser-plan.json'
