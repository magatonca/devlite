# Fase 4B.2 — preparação da instalação dos programas

Estado em 16/11/2026: **preparação e duas simulações APT reais concluídas, sem instalação**. Foram executados 75 testes, todos aprovados. Nenhum pacote instalado no host ou na imagem, nenhuma operação root de imagem, nenhum chroot, montagem, download de pacotes, nova ISO, remoção de artefatos ou commit. As operações do projeto foram executadas como magaton. O mecanismo de instalação real e geração do delta continuam bloqueados e exigem implementação/revisão e autorização próprias.

## Catálogo e escopo

Os 47 itens da 4A foram analisados: 44 Ubuntu e três externos. Todos os 44 Ubuntu pertencem ao sistema instalado **e** ao ambiente live. A seleção declarativa não representa o fechamento transitivo: o APT escolhe dependências, alternativas, versões e Pre-Depends usando o banco real de cada alvo.

- **sistema**: `ca-certificates`, `locales`, `keyboard-configuration`, `console-setup`, `tzdata`, `language-pack-pt`, `language-pack-pt-base`, `network-manager`, `openssh-client`.
- **desenvolvimento**: `php-cli`, `php-mysql`, `php-xml`, `php-mbstring`, `php-curl`, `php-zip`, `apache2`, `libapache2-mod-php`, `composer`, `mariadb-server`, `git`, `gh`, `docker.io`, `docker-compose-v2`.
- **redes**: `nmap`, `wireshark`, `tcpdump`, `iperf3`, `remmina`, `remmina-plugin-rdp`, `remmina-plugin-vnc`, `openvpn`, `network-manager-openvpn`, `network-manager-openvpn-gnome`.
- **escritorio**: `libreoffice-writer`, `libreoffice-calc`, `libreoffice-impress`, `libreoffice-l10n-pt-br`, `libreoffice-help-pt-br`, `atril`.
- **interface**: `xfce4`, `xubuntu-default-settings`, `language-pack-gnome-pt`, `greybird-gtk-theme`, `elementary-xfce-icon-theme`.

Node.js LTS, TypeScript e VS Code ficam excluídos da transação e bloqueados. Não substituir automaticamente por nodejs/npm/node-typescript do Ubuntu nem adicionar Microsoft/NodeSource/Docker CE. A versão candidata de Node registrada na 4A é histórica e deverá ser conferida novamente quando sua aquisição for autorizada. Docker usa docker.io/docker-compose-v2 Ubuntu; GH usa gh Ubuntu.

## Arquitetura implementada

- `pipeline/devlite/customize/installation.py`: extração somente de leitura do status dpkg, autenticação de índices locais, configuração APT isolada, resolução real, detecção de mudanças proibidas, comparação base/live, estimativa e verificadores de debs/banco dpkg.
- `pipeline/devlite/customize/service_profiles.py`: exportação de perfis Apache/MariaDB/PHP/Docker, debconf e política de serviços, sem aplicação.
- `scripts/preparar-programas.py`: interface somente preparatória, sem opção de instalar, atualizar índices ou construir ISO.
- `scripts/auditar-programas.py`: auditoria somente leitura de cópias dpkg/debs dentro de work.
- `tests/test_installation_plan.py`: 15 casos novos, incluindo teste integrado com APT e dependências transitivas/alternativas reais sobre uma fixture local.
- `config/projeto.json` e `scripts/verificar-projeto.py`: subfase B.2, build, personalização aplicada, privilégios e instalação de pacotes desabilitados.

A interface usa `unsquashfs -cat` para ler o banco de `minimal.squashfs` e `minimal.live.squashfs` extraídas da ISO 4B.1. Não reutiliza o banco do hospedeiro nem modifica os rootfs root-owned da fase anterior. O relatório referencia os hashes verificados na 4B.1; a imagem inteira não foi novamente autenticada nesta preparação e deverá sê-lo antes da execução real.

A simulação usa APT_CONFIG próprio, Dir::Etc::parts/main/sourceparts/preferencesparts isolados, status, preferências/pins por alvo e índices copiados, caches/logs próprios, arquitetura amd64 e dpkg apontado para /bin/false. Isso impede herdar hooks do APT do servidor e impede usar esta configuração para instalação. Só são invocados apt-get -s check e apt-get -s --no-remove --no-install-recommends install, além de apt-cache show e dpkg --compare-versions. Não é executado apt-get update nem qualquer modo de instalação real.

São admitidos apenas noble, noble-updates e noble-security, main/universe, amd64. Os índices uncompressed locais foram copiados e seus tamanhos/SHA-256 conferidos contra InRelease autenticado por gpgv com a chave Ubuntu Archive 2018 `F6ECB3762474EDA9D21B7022871920D1991BC93C`, ancorada no ubuntu-archive-keyring instalado. Essa chave é diferente da chave de assinatura de ISOs Ubuntu. Backports, restricted, multiverse e terceiros não são importados. Metadados comprimidos não reconhecidos são recusados, sem instalação de descompressores.

As atualizações/security do snapshot são de 16/11/2026. Datas futuras, cache de updates/security com mais de sete dias ou Valid-Until expirado geram bloqueio de execução. O Release noble estável é de 25/04/2024; sua idade sozinha não significa expiração. Assinatura e hash incorretos interrompem a preparação. Antes do lock executável, atualizar metadados assinados com rede autorizada e verificar novamente; o snapshot atual permite análise offline, não garante disponibilidade futura dos debs.

## Dependências reais encontradas

| Alvo | Já instalados antes | Novos | Atualizações necessárias | Download estimado | Pacotes novos/atualizados descomprimidos, bruto |
|---|---:|---:|---:|---:|---:|
| base | 1166 | 227 | 13 | 320.5 MiB | 1.40 GiB |
| live | 1311 | 223 | 16 | 316.2 MiB | 1.38 GiB |

Não há remoções, downgrades ou atualizações de pacotes protegidos de boot/instalador. Versões compartilhadas após a simulação ficaram iguais; nenhum pacote da base ficou ausente do live. Há 141 pacotes exclusivamente live após a transação, incluindo Casper, ferramentas de instalação/armazenamento, kernel/firmware e xubuntu-live-settings. Eles devem permanecer no live, sem serem incorporados indiscriminadamente à base instalada. O instalador também depende do estado snap e de arquivos fora do dpkg.

Exemplos resolvidos: PHP 8.3.6-0ubuntu0.24.04.13, Apache 2.4.58-1ubuntu8.19, MariaDB 10.11.14-0ubuntu0.24.04.1, Docker 29.1.3 e Compose 2.40.3. As versões completas, hashes, Filename, Depends e Pre-Depends de todas as operações estão na [evidência](evidencias/preparacao-programas.json) e no plano completo local. Isso é um **candidato de lock**, não um lock autorizado: não foram baixados/verificados debs.

A base exige atualizar 13 pacotes existentes, entre eles libc6/libc-bin/locales, Perl, certificados, tzdata e openssh-client. Não é uma instalação puramente aditiva; essas atualizações transitivas precisam estar na revisão da execução. Como locales é atualizado, regenerar/verificar pt_BR no alvo depois da instalação, preservando os ajustes da 4B.1.

## Instalação isolada proposta — não executada

1. Revalidar ISO 4B.1, camadas e inventários; criar um novo workspace, sem reutilizar nem alterar as árvores anteriores. Confirmar espaço e ferramentas já disponíveis.
2. Com rede autorizada, atualizar apenas o estado APT isolado e autenticar InRelease/Packages. Resolver novamente nos dois alvos; congelar a transação inteira com versões, origem, arquitetura, SHA-256 e tamanhos. Baixar somente os debs travados para cache do projeto; conferir cada arquivo antes de usar.
3. Com root especificamente autorizado, extrair uma nova base preservando UID/GID, devices, xattrs/capabilities e hardlinks. Compor a visão live original em namespace de montagem privado e somente leitura; copiar sua visão efetiva, não a folha isolada, para um segundo rootfs descartável completo.
4. Executar transações offline separadas na base e na visão live completa, usando seus próprios estados dpkg/APT e o lock de versões comum. O isolamento deve incluir mount/PID/network namespaces, propagação privada, proc do PID namespace, /dev mínimo e /run temporário; não expor /run, D-Bus, sockets Docker ou outros caminhos graváveis do host. Chroot sozinho não é isolamento suficiente. Verificar previamente suporte a namespaces, sem instalar dependências automaticamente.
5. Durante manutenção, policy-rc.d temporário retorna 101; preservar/restaurar qualquer política existente em finally. Máscaras persistentes dos serviços selecionados evitam ativação por unidades/socket após boot; auditar aliases, timers e comandos diretos dos maintainer scripts. Não confiar somente em policy-rc.d para conter scripts arbitrários.
6. Executar APT sem downloads e sem remoções, com a lista completa de package=version do lock. Aplicar apenas perfis revisados, preservar os ajustes 4B.1, gerar locale no alvo e conferir dpkg/APT. Guardar logs e inventários antes/depois, incluindo contas/grupos criados por pacotes.
7. Reconciliar a visão live com a nova base, conforme a estratégia abaixo; só depois considerar compressão e integração com o replay de boot existente, em outra fase autorizada.

## Reconciliação live obrigatória

A simulação confirma que as versões APT são compatíveis, mas não prova que basta substituir minimal.squashfs. A folha antiga contém banco dpkg e arquivos que poderiam ocultar versões novas da base. Instalar numa folha isolada ou copiar apenas dpkg/status produziria banco e conteúdo divergentes.

O estado desejado live será a visão composta original atualizada com sua transação própria e o mesmo lock das versões comuns. A nova base será atualizada separadamente. Comparar todas as entradas dessas duas árvores completas para gerar um novo delta: bytes, tipos, ownership, modos, timestamps, symlinks, hardlinks e xattrs. Entradas removidas exigem whiteouts; diretórios opacos precisam representar remoções corretamente. Em uma futura implementação validada, operações numa visão OverlayFS descartável sobre a nova base podem produzir whiteouts/opacity pelo próprio kernel. Não reutilizar cegamente trusted.overlay.origin/uuid da folha antiga após reconstruir a base; atributos internos devem ser regenerados e validados no contexto novo.

Validar que nova base + novo delta reproduz exatamente a visão live desejada e um banco dpkg coerente. Preservar Desktop Bootstrap/Subiquity, seed/snaps/assertions, configurações Casper e catálogo fsimage-layered. O snap ubuntu-desktop-bootstrap original e dependências devem ser inventariados e comparados, não instalados ou atualizados implicitamente. Qualquer atualização inevitável de componente protegido bloqueia o plano para revisão.

Regenerar manifests completos da base e do live e seus deltas a partir dos bancos reais pós-instalação, tamanhos, install-sources.yaml e checksums. Manter catálogo, kernel/initrd, BIOS/UEFI e EFI anexada; aplicar as auditorias da 3B/4B.1. Nada disso foi reconstruído nesta fase.

## Configurações e serviços preparados

Perfis exportados apenas em payloads do workspace: Apache escuta 127.0.0.1:80 e recebe conf local; MariaDB bind-address 127.0.0.1, sem credenciais embutidas; PHP usa expose_php/display_errors Off, log_errors On e memory_limit 128M; Docker usa log-driver local com rotação, sem socket TCP. O perfil PHP é genérico: sua ligação às SAPIs presentes será feita após detectar a versão no alvo. Não reaplicar o overlay 4A inteiro sobre os links de locale/os-release preservados na 4B.1.

Máscaras propostas: apache2.service, mariadb.service e alias mysql.service, docker.service/docker.socket, containerd.service e iperf3.service. Não habilitar serviços, adicionar usuários ao grupo docker/wireshark ou iniciar captura automaticamente. Debconf prepara wireshark setuid=false e iperf3 daemon=false. Preservar NetworkManager e SSH cliente; não criar servidor SSH ou perfis VPN com segredos. Futuro DevLite Control poderá oferecer ativação explícita, ainda não implementada.

Validar sintaxe Apache/PHP/MariaDB/Docker sem iniciar daemons, inventariar sockets/timers/aliases, verificar serviços não habilitados e ausência de processos remanescentes no namespace. Essas verificações estão planejadas, não foram executadas contra pacotes ainda não instalados.

## Integridade dpkg/APT

O parser recusa estados unpacked/half-configured/triggers-pending, duplicações e arquitetura não suportada; ambas as imagens passaram por apt-get --simulate check antes da simulação. O auditor preparado verifica status, journal updates e arquivos info/*.list, mas não substitui a auditoria runtime. O verificador de debs exige arquivo regular e hash exato do plano, sem symlinks, download ou extração.

Após instalação autorizada, exigir: dpkg --audit sem saída e sem journal pendente; apt-get --simulate check sem dependências quebradas; dpkg-query com estados ii e versões travadas; info/*.list, md5sums, conffiles, diversions, triggers e alternatives consistentes; manifests coerentes com os arquivos efetivos. Conferir locale/identidade, instalador/snap e discrepâncias base/live. md5sums do dpkg ajudam a detectar corrupção de arquivos, mas a autenticação dos debs depende da cadeia InRelease → Packages SHA-256 → arquivo deb.

## Recursos

Downloads: cerca de 320,5 MiB na base e 316,2 MiB no live; o limite somado conservador é 636,7 MiB, antes de deduplicar artefatos iguais. Os pacotes novos/atualizados ocupam cerca de 1,40 GiB brutos na base (não é o crescimento líquido: inclui arquivos substituídos).

Orçamento adicional: quatro cópias de rootfs com até 5 GiB de conteúdo original + o bruto de pacotes por cópia, arquivos deb e 15 GiB para camadas/ISO/árvores/margem. Resultado: **44.255.549.770 bytes, aproximadamente 41,2 GiB adicionais**. O livre medido era 44,8 GiB: passa a estimativa, porém com margem de apenas cerca de 3,6 GiB além do orçamento. Scripts de manutenção, bancos MariaDB, índices e compressão podem aumentar o consumo. Recomenda-se elevar o espaço livre antes da instalação, idealmente a pelo menos 55–60 GiB, sem remover artefatos existentes automaticamente. Conferir du/df antes de cada etapa e interromper se insuficiente.

RAM: manter um processo de compressão, cache de 256 MiB, instalações sequenciais e diretórios em disco; evitar tmpfs e builds paralelos. Orçamento operacional proposto de até 2,5 GiB de RAM, deixando o restante ao host. É uma meta, não medição de um processo de instalação que ainda não ocorreu. Há aproximadamente 3,8 GiB de RAM e 3,8 GiB de swap; swap não substitui margem de memória e deve ser monitorada.

## Reprodução segura e resultados

```sh
python3 scripts/preparar-programas.py --resolve-offline
TMPDIR="$PWD/work/phase4b1-tests-tmp" PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 scripts/verificar-projeto.py
```

A preparação cria um workspace novo e preserva anteriores. Snapshot aprovado: `work/phase4b2-whqtc4yu/installation-plan.json`, com índices, status dos dois alvos, logs de gpgv/APT, service-plan.json, payloads e guards. A primeira tentativa foi interrompida pelo parser ao encontrar anotação legítima de dependência; o formato foi suportado, coberto por regressão e a simulação foi refeita com sucesso em outro workspace. A fixture de teste APT usa somente file: e dados fictícios; trusted=yes aparece exclusivamente nessa fixture, nunca no plano real.

75 testes aprovados (60 anteriores + 15 novos). Incluem solver real transitivo com alternativas/versionamento, hashes/assinatura inválidos, remoções/protected packages/providers, estado dpkg incompleto, isolamento APT, reconciliação, estimativa e perfis inativos. Os cinco testes históricos da ISO 4B.1 não foram reexecutados nem contados nesta suíte. Nenhum teste sintético aprova instalação/boot.

Auditorias opcionais futuras somente sobre cópias existentes em work:

```sh
python3 scripts/auditar-programas.py --rootfs work/NOVO_WORKSPACE/base-root
python3 scripts/auditar-programas.py --plan work/NOVO_WORKSPACE/installation-plan.json --debs work/NOVO_WORKSPACE/debs
```

## Comandos que exigirão autorização na execução real

Os exemplos abaixo são especificações **não executadas**, não um roteiro pronto para colar. Os caminhos finais, hashes do lock e todos os argumentos devem ser materializados e apresentados para aprovação antes de qualquer execução privilegiada. A autorização root da 4B.1 não se estende a esta etapa.

| Operação futura | Comando/classe de comando a revisar | Rede | Root |
|---|---|---|---|
| Refresh/download no estado isolado | APT_CONFIG=NOVO_CONFIG apt-get update; apt-get --download-only com versões travadas | Sim, aprovação de aquisição | Não |
| Extração fiel e visão live original | unsquashfs -strict-errors -processors 1; unshare/mount OverlayFS em namespace privado | Não | Sim |
| Execução isolada | unshare --mount --pid --fork --net; chroot ROOTFS /usr/bin/env DEBIAN_FRONTEND=noninteractive apt-get --no-download --no-remove --no-install-recommends install PACOTES=VERSÕES | Não; namespace sem rede | Sim |
| Debconf/perfis/máscaras | chroot ROOTFS debconf-set-selections; systemctl --root ROOTFS mask UNIDADES; cópias confinadas de perfis | Não | Sim |
| Auditoria runtime | chroot ROOTFS dpkg --audit; apt-get --simulate check; dpkg-query; validadores de configuração | Não | Sim para acessar o rootfs/namespace protegido |
| Rebase fiel e compressão futura | operações OverlayFS do delta; mksquashfs com um processo/cache 256 MiB | Não | Sim para metadados privilegiados; geração de nova ISO exige autorização separada |

O backend instalador/namespace/rebase não é executável nesta fase e não possui --apply. Implementá-lo, testar restauração em falhas e gerar a lista exata de comandos é parte da preparação final da próxima fase, antes de solicitar autorização. Não usar os configs de simulação para instalar: eles apontam dpkg para /bin/false. Não executar comandos de APT sem o ambiente isolado revisado.

## Referências oficiais consultadas

- [APT: simulação, resolução e opções](https://manpages.ubuntu.com/manpages/noble/man8/apt-get.8.html).
- [apt.conf: ordem de leitura e diretórios isolados](https://manpages.ubuntu.com/manpages/noble/man5/apt.conf.5.html).
- [apt-secure: cadeia de confiança e limites](https://manpages.ubuntu.com/manpages/noble/man8/apt-secure.8.html).
- [Debian Policy: inicialização de serviços](https://www.debian.org/doc/debian-policy/ch-opersys.html#starting-system-services).
- [Docker: socket, grupo e inicialização automática](https://docs.docker.com/engine/install/linux-postinstall/).
