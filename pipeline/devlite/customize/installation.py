"""Planejamento APT real, offline e sem privilégios. Não contém instalador."""
import hashlib
import json
import os
import pwd
import re
import shutil
import subprocess
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from .manifest import resolve, SpecError
from ..runtime import owned_directory

ARCHIVE_KEY = 'F6ECB3762474EDA9D21B7022871920D1991BC93C'
SUITES = ('noble', 'noble-updates', 'noble-security')
INDEX = re.compile(r'(br\.archive\.ubuntu\.com_ubuntu|archive\.ubuntu\.com_ubuntu|security\.ubuntu\.com_ubuntu)_dists_(noble(?:-updates|-security)?)_(main|universe)_binary-amd64_Packages$')
PROTECTED = re.compile(r'^(?:linux-|grub|shim|casper|snapd$|subiquity|ubuntu-desktop|xubuntu-desktop)')
NAME = re.compile(r'[a-z0-9][a-z0-9+.-]*(?::amd64)?')


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def control(text):
    records = []
    for block in text.strip().split('\n\n'):
        fields, current = {}, None
        for line in block.splitlines():
            if line.startswith((' ', '\t')) and current:
                fields[current] += '\n' + line[1:]
            elif ': ' in line:
                current, value = line.split(': ', 1)
                if current in fields:
                    raise SpecError('Campo Debian duplicado: ' + current)
                fields[current] = value
            elif line.endswith(':'):
                current = line[:-1]; fields[current] = ''
        if fields:
            records.append(fields)
    return records


def installed(text):
    result = {}
    for record in control(text):
        status = record.get('Status', '')
        if status == 'deinstall ok config-files':
            continue
        if status != 'install ok installed':
            raise SpecError('Estado dpkg incompleto: ' + record.get('Package', '?') + ': ' + status)
        name = record['Package']
        if not NAME.fullmatch(name) or record.get('Architecture') not in ('amd64', 'all') or name in result:
            raise SpecError('Nome/arquitetura/duplicação dpkg não suportado: ' + name)
        result[name] = record['Version']
    if not result:
        raise SpecError('Banco dpkg vazio')
    return result


def parse_transaction(text, forbidden):
    changes = []
    for line in text.splitlines():
        if line.startswith('Remv '):
            raise SpecError('APT propôs remoção')
        if not line.startswith('Inst '):
            continue
        match = re.fullmatch(r'Inst (\S+)(?: \[([^\]]+)\])? \((\S+)(?: [^)]*)?\)(?: \[[^\]]*\])*', line)
        if not match or not NAME.fullmatch(match[1]):
            raise SpecError('Transação APT não reconhecida: ' + line)
        name, previous, version = match.groups()
        plain = name.split(':')[0]
        if plain in forbidden or PROTECTED.match(plain):
            raise SpecError('Transação altera provider proibido ou boot/instalador: ' + name)
        if any(item['package'] == name for item in changes):
            raise SpecError('Instalação duplicada no plano')
        changes.append({'package': name, 'previous': previous, 'version': version})
    return changes


def apt_config(work, status, preferences=None):
    # APT_CONFIG é lido antes dos fragmentos; impede hooks/configuração do host.
    values = {
        'Dir::Etc::parts': work / 'empty', 'Dir::Etc::main': work / 'empty.conf',
        'Dir::Etc::sourcelist': work / 'sources.list', 'Dir::Etc::sourceparts': work / 'empty',
        'Dir::Etc::preferences': preferences or work / 'preferences', 'Dir::Etc::preferencesparts': work / 'empty',
        'Dir::State::status': status, 'Dir::State::lists': work / 'lists',
        'Dir::State::extended_states': work / 'extended_states',
        'Dir::Cache': work / 'cache', 'Dir::Cache::archives': work / 'cache/archives',
        'Dir::Cache::pkgcache': '', 'Dir::Cache::srcpkgcache': '',
        'Dir::Log': work / 'logs', 'Dir::Bin::dpkg': '/bin/false',
        'APT::Architecture': 'amd64', 'APT::Install-Recommends': 'false',
        'APT::Install-Suggests': 'false', 'APT::Get::AllowUnauthenticated': 'false',
        'Acquire::AllowInsecureRepositories': 'false', 'Debug::NoLocking': 'true',
    }
    for value in values.values():
        if any(c in str(value) for c in ('"', '\\', '\n')):
            raise SpecError('Caminho incompatível com configuração APT')
    return '\n'.join(f'{key} "{value}";' for key, value in values.items()) + '\nAPT::Architectures { "amd64"; };\n'


def run(work, label, args, env=None, allowed=(0,)):
    result = subprocess.run(args, env=env, capture_output=True, text=True, timeout=180)
    (work / 'logs' / (label + '.json')).write_text(json.dumps({'argv': args, 'apt_config': (env or {}).get('APT_CONFIG'), 'returncode': result.returncode}, indent=2)+'\n')
    (work / 'logs' / (label + '.stdout')).write_text(result.stdout)
    (work / 'logs' / (label + '.stderr')).write_text(result.stderr)
    if result.returncode not in allowed:
        raise SpecError(label + ': falha; consultar logs locais')
    return result


def snapshot_indexes(work, source=Path('/var/lib/apt/lists')):
    releases, sources, evidence, blockers = {}, set(), [], []
    for file in sorted(source.iterdir()):
        match = INDEX.fullmatch(file.name)
        if not match:
            continue
        prefix, suite, component = match.groups()
        key = (prefix, suite)
        if key not in releases:
            name = prefix + '_dists_' + suite + '_InRelease'
            signed = work / 'lists' / name
            shutil.copyfile(source / name, signed)
            release = work / (name + '.verified')
            result = run(work, 'gpg-' + suite, ['gpgv', '--status-fd', '1', '--keyring', '/usr/share/keyrings/ubuntu-archive-keyring.gpg', '--output', str(release), str(signed)])
            if not any(line.startswith('[GNUPG:] VALIDSIG ') and (line.split()[2] == ARCHIVE_KEY or line.split()[-1] == ARCHIVE_KEY) for line in result.stdout.splitlines()):
                raise SpecError('Assinatura não é da chave Ubuntu Archive 2018 esperada')
            fields = control(release.read_text())[0]
            if fields.get('Origin') != 'Ubuntu' or fields.get('Suite') != suite or fields.get('Codename') != 'noble':
                raise SpecError('Release incompatível')
            now = datetime.now(timezone.utc)
            dated = parsedate_to_datetime(fields['Date'])
            if dated > now:
                blockers.append(suite + ': Release datado no futuro')
            if suite != 'noble' and (now - dated).days > 7:
                blockers.append(suite + ': cache local com mais de sete dias; atualizar após autorização')
            if fields.get('Valid-Until') and parsedate_to_datetime(fields['Valid-Until']) < now:
                blockers.append(suite + ': Valid-Until expirado')
            hashes = {}
            for line in fields.get('SHA256', '').splitlines():
                parts = line.split()
                if len(parts) == 3:
                    hashes[parts[2]] = (parts[0], int(parts[1]))
            releases[key] = hashes
            evidence.append({'suite': suite, 'inrelease_sha256': sha(signed), 'date': fields['Date'], 'valid_until': fields.get('Valid-Until'), 'signer': ARCHIVE_KEY})
        destination = work / 'lists' / file.name
        shutil.copyfile(file, destination)
        expected = releases[key].get(component + '/binary-amd64/Packages')
        if expected != (sha(destination), destination.stat().st_size):
            raise SpecError('Índice Packages diverge do InRelease assinado: ' + file.name)
        evidence.append({'index': file.name, 'sha256': expected[0], 'bytes': expected[1]})
        uri = 'http://' + prefix.removesuffix('_ubuntu') + '/ubuntu'
        sources.add(f'deb [arch=amd64 signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] {uri} {suite} main universe')
    for suite in SUITES:
        components = [item for item in evidence if 'index' in item and ('_dists_' + suite + '_') in item['index']]
        if len(components) != 2:
            raise SpecError('Esperados índices main/universe únicos de ' + suite)
    (work / 'sources.list').write_text('\n'.join(sorted(sources)) + '\n')
    return evidence, blockers


def resolve_target(work, name, status, requested, forbidden):
    state = installed(status)
    path = work / (name + '.status'); path.write_text(status)
    preferences = work / (name + '.preferences')
    conf = work / (name + '.apt.conf'); conf.write_text(apt_config(work, path, preferences))
    preferences.write_text(''.join(f'Package: {pkg}\nPin: version {ver}\nPin-Priority: 1001\n\n' for pkg, ver in state.items() if PROTECTED.match(pkg)))
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


def verify_archives(plan, cache):
    """Confere debs já adquiridos; não baixa, extrai ou instala."""
    expected = {}
    for target in plan['targets'].values():
        for item in target['changes']:
            name = Path(item['filename']).name
            if name in expected and expected[name] != item['sha256']:
                raise SpecError('Arquivo deb com hashes conflitantes')
            expected[name] = item['sha256']
    for name, digest in expected.items():
        file = cache / name
        if file.is_symlink() or not file.is_file() or sha(file) != digest:
            raise SpecError('Deb ausente, symlink ou hash inválido: ' + name)
    return len(expected)


def audit_database(rootfs):
    """Auditoria estrutural somente leitura; não substitui dpkg --audit no alvo."""
    database = rootfs / 'var/lib/dpkg'
    for relative in ('var', 'var/lib', 'var/lib/dpkg', 'var/lib/dpkg/status', 'var/lib/dpkg/updates', 'var/lib/dpkg/info'):
        if (rootfs/relative).is_symlink():
            raise SpecError('Banco dpkg com caminho symlink: ' + relative)
    state = installed((database/'status').read_text())
    if not (database/'updates').is_dir() or any(p.name.isdigit() for p in (database/'updates').iterdir()):
        raise SpecError('Journal dpkg ausente ou com transações pendentes')
    missing = [name for name in state if not any((database/'info'/(name+suffix)).is_file() for suffix in ('.list',':amd64.list'))]
    if missing:
        raise SpecError('Pacotes sem inventário dpkg: ' + ', '.join(missing))
    return {'installed':len(state),'structural_audit':'ok','runtime_audit_required':True}


def compatibility(base, live):
    b, l = base['final_versions'], live['final_versions']
    return {'base_packages_missing_live':sorted(b.keys()-l.keys()),
            'common_version_conflicts':{p:{'base':b[p],'live':l[p]} for p in sorted(b.keys() & l.keys()) if b[p]!=l[p]},
            'live_only_packages':sorted(l.keys()-b.keys())}


def estimate(base, live, free):
    gross = max(base['gross_installed_bytes'], live['gross_installed_bytes'])
    archives = base['download_bytes'] + live['download_bytes']  # Conservador: não deduplica.
    # Duas visões completas + suas reextrações, camadas comprimidas/ISO/árvores e margem.
    required = 4 * (5*1024**3 + gross) + archives + 15*1024**3
    return {'free_bytes':free,'additional_required_bytes':required,'sufficient':free>=required,
            'gross_added_or_upgraded_package_bytes':gross,'archives_upper_bound_bytes':archives,
            'assumptions':'quatro rootfs de até 5 GiB + pacotes brutos por cópia; 15 GiB para ISO/árvores/margem; sem excluir artefatos existentes; scripts de manutenção podem exceder a estimativa',
            'memory':{'processors':1,'squashfs_cache_mib':256,'avoid_tmpfs':True,'guest_ram_gib':3.8,'budget_ram_gib':2.5}}


def prepare(root):
    if os.geteuid()==0 or pwd.getpwuid(os.getuid()).pw_name!='magaton':
        raise SpecError('Executar como magaton, sem sudo')
    selection = json.loads((root/'packages/selection.json').read_text())
    entries = resolve(selection)
    work = owned_directory(root/'work','phase4b2-')
    for folder in ('logs','empty','lists/partial','cache/archives/partial'):
        (work/folder).mkdir(parents=True,exist_ok=True)
    for file in ('empty.conf','preferences','extended_states'):
        (work/file).write_text('')
    report = {'schema':1,'status':'preparando','workspace':str(work),'ready_to_install':False,
              'network_used':False,'root_used':False,'installation_executed':False,
              'catalog_sha256':sha(root/'packages/selection.json'),'catalog_items':len(entries),'external_blocked':[i for i in entries if i['provider']!='ubuntu'],
              'scopes':{i['id']:i['scope'] for i in entries},'blockers':[]}
    try:
        evidence = json.loads((root/'docs/evidencias/personalizacao-minima.json').read_text())
        previous = Path(evidence['workspace'])
        if previous.is_symlink() or previous.resolve().parent != (root/'work').resolve():
            raise SpecError('Workspace fonte fora do projeto')
        casper = previous/'result-iso-tree/casper'
        report['input']='camadas extraídas da ISO 4B.1; referência aos hashes do relatório, sem nova autenticação integral nesta preparação'
        report['source_iso_sha256']=evidence['sha256']
        report['indexes'],report['blockers']=snapshot_indexes(work)
        requested = sorted(i['package'] for i in entries if i['provider']=='ubuntu')
        report['requested_ubuntu']=requested
        from .service_profiles import export
        report['service_plan']=export(work)
        results={}
        for name,image in (('base','minimal.squashfs'),('live','minimal.live.squashfs')):
            status=run(work,name+'-status',['unsquashfs','-processors','1','-data-queue','64','-frag-queue','64','-cat',str(casper/image),'var/lib/dpkg/status']).stdout
            results[name]=resolve_target(work,name,status,requested,set(selection['forbidden_apt']))
        report['targets']=results
        report['reconciliation']=compatibility(results['base'],results['live'])
        report['resources']=estimate(results['base'],results['live'],shutil.disk_usage(root).free)
        report['status']='dependencias_resolvidas_offline'
        if not report['resources']['sufficient']:
            report['blockers'].append('Espaço abaixo da estimativa conservadora; não iniciar instalação')
        if report['reconciliation']['common_version_conflicts'] or report['reconciliation']['base_packages_missing_live']:
            report['blockers'].append('Reconciliar diferenças base/live e resolver novamente sobre visão composta; não copiar banco dpkg antigo')
        report['blockers'] += ['Três providers externos desabilitados; plano Ubuntu parcial.',
            'Reautenticar imagens e atualizar metadados assinados antes do lock de execução.',
            'Instalador isolado e rebase ainda não executáveis; revisão e autorização de comandos root/rede obrigatórias.',
            'Verificar arquivos deb baixados, assinaturas, dpkg/APT, inventários do instalador e testes reais BIOS/UEFI antes de release.']
    except (SpecError,OSError,ValueError,subprocess.SubprocessError) as error:
        report['status']='bloqueado';report['blockers'].append(str(error))
    (work/'installation-plan.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(work/'installation-plan.json')
    return report
