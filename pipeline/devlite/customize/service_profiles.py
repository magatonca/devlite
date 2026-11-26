"""Perfis exportáveis; nenhum arquivo de um rootfs ou do host é alterado."""
import hashlib
import json

MASKS = ['apache2.service','mariadb.service','mysql.service','docker.service','docker.socket','containerd.service','iperf3.service']
FILES = {
    'etc/apache2/ports.conf': 'Listen 127.0.0.1:80\n',
    'etc/apache2/conf-available/devlite-local.conf': '<Directory /var/www/html>\n    Require local\n</Directory>\n',
    'etc/mysql/mariadb.conf.d/99-devlite.cnf': '[mysqld]\nbind-address = 127.0.0.1\n',
    'usr/share/devlite-os/profiles/php-devlite.ini': 'expose_php = Off\ndisplay_errors = Off\nlog_errors = On\nmemory_limit = 128M\n',
    'etc/docker/daemon.json': json.dumps({'log-driver':'local','log-opts':{'max-size':'10m','max-file':'3'}},indent=2)+'\n',
}
DEBCONF = 'wireshark-common wireshark-common/install-setuid boolean false\niperf3 iperf3/start_daemon boolean false\n'


def export(work):
    manifest = {}
    for name, content in FILES.items():
        path = work/'payloads'/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(content)
        manifest[name] = {'sha256':hashlib.sha256(content.encode()).hexdigest(),'mode':420,'uid':0,'gid':0}
    guards=work/'guards';guards.mkdir()
    (guards/'policy-rc.d').write_text('#!/bin/sh\n# Temporário, somente no alvo autorizado.\nexit 101\n')
    (guards/'debconf.selections').write_text(DEBCONF)
    plan={'files':manifest,'unit_masks':MASKS,'masks_persistent':True,
          'temporary_service_start_guard':'policy-rc.d exit 101; preservar/restaurar qualquer arquivo preexistente em finally',
          'php':'detectar versão/SAPIs após resolução; copiar perfil e habilitar somente CLI/Apache presentes; não presumir versão ou instalar FPM',
          'apache':'validar apache2ctl -t no alvo; ativar conf devlite-local; não iniciar daemon',
          'mariadb':'validar configuração no alvo; preservar autenticação unix_socket; sem senha pré-configurada',
          'docker':'sem TCP, sem associação automática de usuários ao grupo docker; socket e daemon mascarados',
          'network':'preservar NetworkManager/SSH cliente e perfis existentes; não criar túneis, servidor SSH ou captura privilegiada automática',
          'acceptance':['dpkg --audit vazio','apt-get --simulate check sem erros','serviços mascarados sem sockets/timers de ativação remanescentes','nenhum daemon em execução no namespace','configurações validadas sem iniciar serviços'],
          'applied':False}
    (work/'service-plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
    return plan
