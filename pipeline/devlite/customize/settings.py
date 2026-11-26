"""Renderização de padrões do sistema; nenhum arquivo do host é alterado."""
import json
from xml.etree import ElementTree as ET
from .manifest import SpecError


def validate(settings):
    if not isinstance(settings, dict):
        raise SpecError('Configurações devem ser objeto JSON')
    expected = {'schema': 1, 'locale': 'pt_BR.UTF-8', 'language': 'pt_BR:pt',
                'timezone': 'America/Sao_Paulo', 'desktop': 'XFCE',
                'theme': 'Greybird', 'icon_theme': 'elementary-xfce-dark'}
    if any(settings.get(key) != value for key, value in expected.items()):
        raise SpecError('Configuração incompatível com o perfil DevLite 1.0')
    if settings.get('keyboard') != {'model': 'abnt2', 'layout': 'br', 'variant': '', 'options': ''}:
        raise SpecError('Perfil requer teclado brasileiro ABNT2')
    identity = settings.get('identity')
    if identity != {'name': 'DevLite OS', 'version': '1.0', 'edition': 'Developer + Network Edition'}:
        raise SpecError('Identidade inesperada')
    services = settings.get('services', {})
    if not isinstance(services, dict):
        raise SpecError('Política de serviços inválida')
    if services.get('wireshark_non_root_capture') is not False or services.get('automatic_docker_group') is not False:
        raise SpecError('Não habilitar captura privilegiada ou grupo docker automaticamente')
    expected_services = {'apache2.service', 'mariadb.service', 'docker.service', 'docker.socket', 'containerd.service', 'iperf3.service'}
    service_names = services.get('disabled_until_explicit_activation')
    if not isinstance(service_names, list) or any(not isinstance(x, str) for x in service_names):
        raise SpecError('Lista de serviços inválida')
    if set(service_names) != expected_services:
        raise SpecError('Política de serviços incompleta')


def render(settings):
    validate(settings)
    files = {}
    def text(path, content):
        files[path] = {'kind': 'text', 'content': content, 'mode': 0o644, 'uid': 0, 'gid': 0}
    text('etc/default/locale', 'LANG=pt_BR.UTF-8\nLANGUAGE=pt_BR:pt\n')
    text('etc/default/keyboard', 'XKBMODEL="abnt2"\nXKBLAYOUT="br"\nXKBVARIANT=""\nXKBOPTIONS=""\nBACKSPACE="guess"\n')
    text('etc/timezone', 'America/Sao_Paulo\n')
    text('etc/mysql/mariadb.conf.d/99-devlite.cnf', '[mysqld]\nbind-address = 127.0.0.1\n')
    files['etc/localtime'] = {'kind': 'symlink', 'target': '../usr/share/zoneinfo/America/Sao_Paulo', 'uid': 0, 'gid': 0}
    text('etc/devlite-release', 'NAME="DevLite OS"\nVERSION="1.0"\nEDITION="Developer + Network Edition"\nBASE="Xubuntu 24.04 LTS Minimal"\n')
    text('usr/share/devlite-os/identity.json', json.dumps(settings['identity'], ensure_ascii=False, indent=2) + '\n')
    channels = {}
    channel = ET.Element('channel', name='xsettings', version='1.0')
    net = ET.SubElement(channel, 'property', name='Net', type='empty')
    ET.SubElement(net, 'property', name='ThemeName', type='string', value=settings['theme'])
    ET.SubElement(net, 'property', name='IconThemeName', type='string', value=settings['icon_theme'])
    channels['xsettings'] = channel
    keyboard = ET.Element('channel', name='keyboard-layout', version='1.0')
    default = ET.SubElement(keyboard, 'property', name='Default', type='empty')
    ET.SubElement(default, 'property', name='XkbDisable', type='bool', value='true')
    channels['keyboard-layout'] = keyboard
    for name, root in channels.items():
        ET.indent(root)
        content = '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding='unicode') + '\n'
        for prefix in ('etc/xdg/xfce4/xfconf/xfce-perchannel-xml', 'etc/skel/.config/xfce4/xfconf/xfce-perchannel-xml'):
            text(f'{prefix}/{name}.xml', content)
    actions = {
        'locale_gen_ensure_line': 'pt_BR.UTF-8 UTF-8',
        'locale_generation': 'locale-gen --keep-existing (somente no alvo isolado autorizado)',
        'timezone': 'validar tzdata e symlink; reconciliar debconf no alvo',
        'debconf': ['keyboard-configuration keyboard-configuration/modelcode string abnt2',
                    'keyboard-configuration keyboard-configuration/layoutcode string br',
                    'wireshark-common wireshark-common/install-setuid boolean false',
                    'iperf3 iperf3/start_daemon boolean false',
                    'code code/add-microsoft-repo boolean false'],
        'services': settings['services'],
        'live_boot_arguments': ['locale=pt_BR.UTF-8', 'keyboard-configuration/layoutcode=br',
                                'keyboard-configuration/modelcode=abnt2'],
        'apt_policy': {'install_recommends': False, 'allow_removals': False, 'upgrade_all': False,
                       'protected_components': ['kernel', 'modules', 'grub', 'shim', 'casper', 'snapd', 'ubuntu-desktop-bootstrap']},
        'external_runtime_layout': {'node': '/opt/devlite/node', 'typescript': '/opt/devlite/typescript',
                                    'future_entrypoints': ['/usr/local/bin/node', '/usr/local/bin/npm', '/usr/local/bin/tsc'],
                                    'create_entrypoints_only_after_artifact_validation': True},
        'preserve': ['/etc/os-release', '/etc/lsb-release', 'kernel', 'initrd', 'EFI', 'instalador'],
        'requires_future_execution': True
    }
    return {'files': files, 'actions': actions}
