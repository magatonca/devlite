# Pacotes e origens — Fase 4A

Consulta em 16/11/2026. São 47 itens declarativos: 44 candidatos do Ubuntu no cache local e três itens externos preparados. As versões abaixo são observações do cache, sem refresh e sem novo teste de autenticidade; **não são versões travadas para build**. Dependências transitivas e compatibilidade final serão resolvidas no alvo isolado da 4B.

| Categoria | Item / pacote | Origem | Candidato observado |
|---|---|---|---|
| sistema | `ca-certificates` | Ubuntu (misc) | 20260816ubuntu0.24.04.2 |
| sistema | `locales` | Ubuntu (libs) | 2.39-0ubuntu8.12 |
| sistema | `keyboard-configuration` | Ubuntu (utils) | 1.226ubuntu1.1 |
| sistema | `console-setup` | Ubuntu (utils) | 1.226ubuntu1.1 |
| sistema | `tzdata` | Ubuntu (libs) | 2026e-0ubuntu0.24.04.1 |
| sistema | `language-pack-pt` | Ubuntu (translations) | 1:24.04+20260905 |
| sistema | `language-pack-pt-base` | Ubuntu (translations) | 1:24.04+20260905 |
| sistema | `network-manager` | Ubuntu (net) | 1.46.0-1ubuntu2.8 |
| sistema | `openssh-client` | Ubuntu (net) | 1:9.6p1-3ubuntu13.20 |
| desenvolvimento | `php-cli` | Ubuntu (php) | 2:8.3+93ubuntu2 |
| desenvolvimento | `php-mysql` | Ubuntu (php) | 2:8.3+93ubuntu2 |
| desenvolvimento | `php-xml` | Ubuntu (php) | 2:8.3+93ubuntu2 |
| desenvolvimento | `php-mbstring` | Ubuntu (universe/php) | 2:8.3+93ubuntu2 |
| desenvolvimento | `php-curl` | Ubuntu (php) | 2:8.3+93ubuntu2 |
| desenvolvimento | `php-zip` | Ubuntu (universe/php) | 2:8.3+93ubuntu2 |
| desenvolvimento | `apache2` | Ubuntu (web) | 2.4.58-1ubuntu8.19 |
| desenvolvimento | `libapache2-mod-php` | Ubuntu (php) | 2:8.3+93ubuntu2 |
| desenvolvimento | `composer` | Ubuntu (universe/php) | 2.7.1-2 |
| desenvolvimento | `mariadb-server` | Ubuntu (universe/database) | 1:10.11.14-0ubuntu0.24.04.1 |
| desenvolvimento | `git` | Ubuntu (vcs) | 1:2.43.0-1ubuntu7.4 |
| desenvolvimento | `gh` | Ubuntu (universe/utils) | 2.45.0-1ubuntu0.3 |
| desenvolvimento | `docker.io` | Ubuntu (universe/admin) | 29.1.3-0ubuntu3~24.04.2 |
| desenvolvimento | `docker-compose-v2` | Ubuntu (universe/admin) | 2.40.3+ds1-0ubuntu1~24.04.1 |
| desenvolvimento | `node-lts` | Node.js oficial, tarball assinado | 26.13.1 LTS, candidato não travado |
| desenvolvimento | `typescript` | npm, pacote oficial TypeScript | a fixar e autenticar |
| desenvolvimento | `code` | Microsoft, code (.deb/APT externo) | a fixar e autenticar |
| redes | `nmap` | Ubuntu (universe/net) | 7.94+git20230807.3be01efb1+dfsg-3build2 |
| redes | `wireshark` | Ubuntu (universe/net) | 4.2.2-1.1build3 |
| redes | `tcpdump` | Ubuntu (net) | 4.99.4-3ubuntu4.24.04.1 |
| redes | `iperf3` | Ubuntu (universe/net) | 3.16-1build2 |
| redes | `remmina` | Ubuntu (gnome) | 1.4.43+dfsg-0ubuntu0.24.04.2 |
| redes | `remmina-plugin-rdp` | Ubuntu (gnome) | 1.4.43+dfsg-0ubuntu0.24.04.2 |
| redes | `remmina-plugin-vnc` | Ubuntu (gnome) | 1.4.43+dfsg-0ubuntu0.24.04.2 |
| redes | `openvpn` | Ubuntu (net) | 2.6.19-0ubuntu0.24.04.5 |
| redes | `network-manager-openvpn` | Ubuntu (net) | 1.10.2-4ubuntu0.2 |
| redes | `network-manager-openvpn-gnome` | Ubuntu (net) | 1.10.2-4ubuntu0.2 |
| escritorio | `libreoffice-writer` | Ubuntu (editors) | 4:24.2.7-0ubuntu0.24.04.7 |
| escritorio | `libreoffice-calc` | Ubuntu (editors) | 4:24.2.7-0ubuntu0.24.04.7 |
| escritorio | `libreoffice-impress` | Ubuntu (editors) | 4:24.2.7-0ubuntu0.24.04.7 |
| escritorio | `libreoffice-l10n-pt-br` | Ubuntu (localization) | 4:24.2.7-0ubuntu0.24.04.7 |
| escritorio | `libreoffice-help-pt-br` | Ubuntu (doc) | 4:24.2.7-0ubuntu0.24.04.7 |
| escritorio | `atril` | Ubuntu (universe/x11) | 1.26.2-3build2 |
| interface | `xfce4` | Ubuntu (universe/x11) | 4.18 |
| interface | `xubuntu-default-settings` | Ubuntu (universe/x11) | 24.04.4 |
| interface | `language-pack-gnome-pt` | Ubuntu (translations) | 1:24.04+20260905 |
| interface | `greybird-gtk-theme` | Ubuntu (universe/x11) | 3.23.3-1 |
| interface | `elementary-xfce-icon-theme` | Ubuntu (universe/x11) | 0.19-1 |

PHP usa os metapacotes Noble da linha 8.3 e inclui extensões comuns para Composer, Apache e MariaDB. Docker usa docker.io + docker-compose-v2 do Ubuntu; não mistura Docker CE/containerd.io. SSH significa cliente OpenSSH, sem ativar servidor. Remmina inclui plugins RDP/VNC, e OpenVPN inclui integração gráfica NetworkManager. LibreOffice seleciona Writer, Calc, Impress e traduções pt-BR; Atril é o leitor PDF.

Alternativas Ubuntu não selecionadas: nodejs 18.19.1, npm 9.2 e node-typescript 4.8.4 foram encontrados no cache. A opção Node upstream LTS evita tratar a linha 18 como LTS atual; TypeScript via npm evita instalar outro Node via dependência APT. A versão exata e os requisitos de engine do TypeScript ainda serão fixados.

GitHub CLI está disponível como gh, e Compose v2 como docker-compose-v2: não exigem repositórios extras. O [catálogo oficial Compose](https://packages.ubuntu.com/noble/docker-compose-v2) também confirma sua presença no Noble. VS Code está fora dos repositórios Ubuntu selecionados; sua origem está documentada pela [Microsoft](https://code.visualstudio.com/docs/setup/linux). Somente VS Code foi planejado com repositório APT externo; Node e TypeScript usam artefatos de seus distribuidores, sujeitos a aprovação e verificação.

As origens externas estão desabilitadas em packages/sources.json. Não executar apt install usando diretamente esta tabela ou concatenando toda a seleção: itens de outros providers não são nomes de pacotes Ubuntu. A lista executável da 4B dependerá de lock completo, metadados assinados e resolução de dependências validada.

Ver [arquitetura e autorizações](fase4a-personalizacao.md).
