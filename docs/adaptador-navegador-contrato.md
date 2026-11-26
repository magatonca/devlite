# Navegador — contrato de aplicação isolada para aprovação

Job `release-browser-2f24tvsg`. Contrato SHA-256: `743d4a621b1a2837ffa6612257842c591283abebff64f8faef0ad5886c8073b1`.

O adaptador está implementado em `pipeline/devlite/browser_executor.py`, `pipeline/devlite/browser_guest.py` e `scripts/executar-navegador.py`. Testes em `tests/test_browser_executor.py`. Nenhum módulo histórico selado foi alterado. O novo contrato sela **51 arquivos Python**, plano derivado, plano de origem, recibos e estado atual do hospedeiro. Sua preparação não executa operações privilegiadas.

## Dependências e aquisição pendente

Plano revalidado: `/home/magaton/DevLite-OS/work/browser-g2xb9f0m/browser-plan.json`. Base/Live têm os mesmos dez pacotes novos, sem upgrades, remoções ou conflitos. Os dez registros foram conferidos contra índices Ubuntu autenticados, em `work/release-browser-2f24tvsg/preflight/authentication.json`. Simulações usam estado dpkg das imagens e configuração APT de planejamento, sem dpkg real.

Download previsto **36.661.522 bytes (34,96 MiB)**; aumento bruto instalado **136,59 MiB por visão**.

| Pacote | Versão fixa |
| --- | --- |
| epiphany-browser | 46.5-0ubuntu1 |
| epiphany-browser-data | 46.5-0ubuntu1 |
| libadwaita-1-0 | 1.5.0-1ubuntu2 |
| libgee-0.8-2 | 0.20.6-1build2 |
| libgranite-7-7 | 7.4.0-1build3 |
| libgranite-7-common | 7.4.0-1build3 |
| libjavascriptcoregtk-6.0-1 | 2.52.6-0ubuntu0.24.04.2 |
| libportal-gtk4-1 | 0.7.1-5build5 |
| libportal1 | 0.7.1-5build5 |
| libwebkitgtk-6.0-4 | 2.52.6-0ubuntu0.24.04.2 |

**Nenhum deb novo adquirido.** URLs HTTPS oficiais, tamanhos, hashes e destinos exatos estão em `work/release-browser-2f24tvsg/command-review.json`, campo `acquisition_pending`. Aquisição ainda exige aprovação; não alterar versões automaticamente. Validar origem final oficial, tamanho e SHA-256. A autenticidade usa InRelease assinado → índice Packages → SHA-256 do deb, não GPG individual obrigatório de cada pacote. O executor reautentica essa cadeia e trabalha offline.

**Cache incompleto bloqueia antes de unshare/mount.** Não executar o comando abaixo antes de adquirir e conferir os dez debs.

## Comando privilegiado exato — NÃO EXECUTADO

```bash
sudo \
  systemd-run \
  --unit=devlite-public-browser-2f24tvsg \
  --wait \
  --pipe \
  --collect \
  --property=ProtectSystem=strict \
  --property=ProtectHome=read-only \
  --property=ReadWritePaths=/home/magaton/DevLite-OS/work/release-browser-2f24tvsg \
  --property=PrivateNetwork=yes \
  --property=PrivateMounts=yes \
  --property=NoNewPrivileges=yes \
  --property=MemoryMax=2684354560 \
  --property=MemorySwapMax=1073741824 \
  --property=CPUQuota=100% \
  --property=TasksMax=128 \
  --property=RuntimeMaxSec=10800 \
  --property=TimeoutStopSec=60 \
  --property=KillMode=control-group \
  --property=OOMPolicy=kill \
  --property=ProtectKernelTunables=yes \
  --property=ProtectKernelModules=yes \
  --property=ProtectControlGroups=yes \
  --property=RestrictRealtime=yes \
  --property=RestrictAddressFamilies=AF_UNIX \
  '--property=CapabilityBoundingSet=CAP_SYS_ADMIN CAP_SYS_CHROOT CAP_SETPCAP CAP_KILL CAP_CHOWN CAP_DAC_OVERRIDE CAP_DAC_READ_SEARCH CAP_FOWNER CAP_FSETID CAP_SETGID CAP_SETUID CAP_SETFCAP' \
  /usr/bin/python3 \
  /home/magaton/DevLite-OS/scripts/executar-navegador.py \
  --outer \
  --job \
  /home/magaton/DevLite-OS/work/release-browser-2f24tvsg \
  --approval-sha256 \
  743d4a621b1a2837ffa6612257842c591283abebff64f8faef0ad5886c8073b1 \
  --execute-authorized
```

A unidade reutiliza o prefixo `devlite-public-` para compatibilidade com o protocolo de atestado já existente. O aplicador público antigo não é executado. Não habilitar flags globais: `config/projeto.json` permanece inalterado com flags false; o novo entrypoint exige autorização explícita e o hash deste contrato.

## Diretórios e montagens propostas

Todos os paths de escrita e mounts de filesystem do alvo ficam sob **`/home/magaton/DevLite-OS/work/release-browser-2f24tvsg`**, única exceção ReadWritePaths.

| Caminho | Acesso e finalidade |
| --- | --- |
| `/home/magaton/DevLite-OS/work/release-cezaiofx/attempt/base.ext4` e `live.ext4` | Fontes aceitas: somente leitura por hash/cópia; nunca montadas ou modificadas |
| `/home/magaton/DevLite-OS/work/release-cezaiofx/published-casper` e recibos | Referências somente leitura da versão com Node.js/TypeScript |
| `/home/magaton/DevLite-OS/work/release-browser-2f24tvsg/debs` | Dez debs previamente adquiridos, verificados e copiados para attempt/debs |
| `/home/magaton/DevLite-OS/work/release-browser-2f24tvsg/attempt/base.ext4` e `live.ext4` | Cópias sparse novas, 12 GiB lógicos cada, sem sobrescrever arquivos existentes |
| `/home/magaton/DevLite-OS/work/release-browser-2f24tvsg/attempt/base-root` e `live-root` | Montagem ext4 RW, nodev/nosuid, uma visão por vez em namespace privado próprio |
| Cada raiz: `/proc`, `/dev`, `/sys`, `/run`, `/tmp` | proc RO e tmpfs limitados; sysfs host oculto; apenas null/zero/random/urandom e links de stdio |
| Cada raiz: `/run/devlite`, `/run/devlite/debs` | Bundle e debs RO, nosuid/nodev; debs também noexec; sem sockets do host |

Durante a execução, o job passa a root:root 0700; ao final torna-se 0755 mantendo dono root para proteger recibos. Não mudar permissões de fontes ou diretórios externos. O kernel desfaz mounts privados e loops autoclear com a saída dos namespaces. Nenhuma ISO, SquashFS, partição ou volume do host é montado para escrita. Não há publicação/reconstrução SquashFS nesta operação.

Dentro das cópias: dpkg/APT aplica a transação exata e seus triggers; a integração mescla somente os seis defaults declarados em browser.py, com hashes de pré-imagem. Mantém helper epiphany e desktop org.gnome.Epiphany para HTML/XHTML/HTTP/HTTPS. O menu usa o desktop entry nativo. Não reaplicar perfis de Apache/MariaDB/PHP/Docker, habilitar serviços ou aplicar arquivos do Modern.

## Recursos e parada

Gate inicial **56 GiB** preservado; estimativa conservadora de **35,60 GiB adicionais**, incluindo margens futuras, não medição de pico. Reserva mínima **20 GiB**; o watchdog verifica a cada segundo e interrompe em **21 GiB**, com margem para parada. Não constitui quota do volume nem impede consumo concorrente por processos externos. Não reduzir limites se faltar espaço.

Limites efetivos exigidos: RAM **2,5 GiB**, swap **1 GiB**, **uma CPU**, **128 tarefas**, máximo **três horas**. Duas imagens sparse de 12 GiB lógicos, sem pré-alocação integral. Logs e cópias parciais ficam preservados em falha.

## Como provar restrição ao ambiente isolado

1. Fase externa consulta propriedades efetivas systemd, preservando stdout/stderr/retorno; fase interna usa memfd root-owned selado e vinculado por hash, nonce, contrato, boot, invocation e cgroup. Não consultar D-Bus dentro do unshare nem habilitar rede.
2. Provar VFS/statvfs somente leitura do host, incluindo /home, /root, /run/user e fontes atuais; única exceção de escrita é o job. Manter ProtectSystem=strict, ProtectHome=read-only, PrivateMounts, PrivateNetwork e NoNewPrivileges.
3. Validar namespaces, cgroup, dono/mode root 0700 e clone privado antes de montar. O pai faz chroot antes de criar o instalador, fecha FDs e protege memória; o filho perde capabilities administrativas.
4. Probe obrigatório **antes do APT** verifica acesso negado à sentinela, rede, mounts, devices, processos, FDs e capabilities. AF_INET pode ser negada na criação por RestrictAddressFamilies=AF_UNIX: registrar negação sem relaxar essa política. Timeout não é aceito como prova.
5. APT sem download/remoção/recommends: comparar simulação e preflight dos paths dpkg com o lock. policy-rc.d temporário bloqueia start e é restaurado com metadados. Preservar inventários boot/instalador/snap e /etc/systemd.
6. Conferir dpkg final exato, audit/APT check, integridade dos novos pacotes, bibliotecas e schemas. Comandos do alvo somente após chroot/redução de privilégios. Após sair cada namespace, e2fsck -f -n verifica a cópia desmontada; fontes são novamente hasheadas.
7. Aceitar o par somente após ambas as visões passarem; revalidar arquivos críticos do host e hash da configuração. Evidências futuras: namespace.log, isolation-systemd.json, isolation-unshare.json, browser-result.json, attempt/state.json e accepted-pair.json. Não tratar estado isolado de um único recibo como homologação da GUI.

## Riscos e recuperação

A primeira execução real deste adaptador ainda não foi validada. Scripts de manutenção podem falhar com mounts/capabilities reduzidas; dependências ou schemas podem divergir; rede/arquivos ausentes, falta de espaço ou timeout devem bloquear. Não desativar sandbox WebKit, AppArmor ou outras proteções para contornar erro.

Em falha: quarentena e nenhuma publicação do par; manter logs e imagens. Recuperação por diagnóstico e job novo revisado, sem retomar dpkg in-place ou remover arquivos automaticamente. Para parar **somente esta unidade**, sujeito à autorização correspondente:

```bash
sudo systemctl stop devlite-public-browser-2f24tvsg.service
```

KillMode=control-group, OOMPolicy=kill e a saída dos PID namespaces encerram filhos; conferir unidade, mounts e loops do job antes de outra tentativa. Não executar detach genérico de loops ou limpeza automática.

## Host, testes e pendências

**430 testes aprovados**, incluindo **28 novos**: `reports/testes-adaptador-navegador-final.txt`. Validação adicional sem privilégios: leitura do selo final, autenticação dos dez registros, ferramentas disponíveis, configurações/overlay históricos inalterados e metadados acessíveis preservados. As quatro imagens privadas só terão hash revalidado na futura execução root; nenhuma foi modificada nesta preparação.

O banco dpkg do host difere do recibo antigo de limpeza. Logs confirmam atualizações automáticas anteriores via unattended-upgrade de needrestart e libgstreamer1.0-0. O contrato usa o baseline atual, estável nesta preparação; evidência em preflight/host-prior-updates.json. Se o host atualizar novamente, o contrato falhará e exigirá revisão, sem desativar serviços do host.

Pendências: aprovar aquisição dos dez debs e o comando privilegiado delimitado acima. A execução real deve comprovar o isolamento antes do primeiro unpack. Lançamento gráfico, sandbox, MIME/HTTP/HTTPS/HTML e persistência no XFCE Live e instalado continuam pendentes; presença do pacote não os comprova. Sem Modern, ISO ou commits nesta etapa.
