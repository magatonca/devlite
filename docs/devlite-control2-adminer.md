# Adminer no DevLite Control 2.0 — integração planejada

## Decisão

**Adminer é o candidato preferencial pelo reaproveitamento de Apache/PHP e pequeno incremento de disco, mas ainda não está aprovado como padrão da ISO pública.** O candidato Ubuntu Noble autenticado é 4.8.1-2 (universe/all); o rastreador oficial mantém pendências de avaliação de segurança. Não instalar essa versão automaticamente, nem trocar silenciosamente para upstream/latest ou outro repositório.

Fontes oficiais consultadas: [Adminer](https://www.adminer.org/), [pacote Noble](https://packages.ubuntu.com/noble/adminer), [arquivos do pacote](https://packages.ubuntu.com/noble/all/adminer/filelist), [CVE-2025-43960](https://ubuntu.com/security/CVE-2025-43960), [CVE-2026-56705](https://ubuntu.com/security/CVE-2026-56705). A primeira envolve Monolog em determinadas condições; a segunda trata injeção de parâmetros PDO/ODBC em versões anteriores a 5.4.3. O status Noble é Needs evaluation. A presença no rastreador não prova exploração nesta configuração: é necessário revisar código, backports, drivers e aplicabilidade. Até lá, segurança bloqueia a inclusão padrão. Bind local reduz exposição, mas não substitui correção.

Se o Ubuntu não fornecer correção comprovada, apresentar decisão separada: aguardar pacote corrigido ou avaliar artefato upstream versionado, com origem, assinatura quando disponível, hash, licença e política de atualização próprios. Nenhum download de Adminer upstream ou uso de URL latest foi feito. Não escolher versão final por comparação numérica isolada: backports precisam ser examinados.

## Disponibilidade, autenticidade e custo medidos

Plano `work/adminer-plan-j1x_gycp/adminer-plan.json`, com índices locais Ubuntu copiados e autenticados por GPG/InRelease e hashes Packages. Reutilizou-se o APT de planejamento com status Base/Live separados, dpkg desabilitado e --simulate/--no-install-recommends; nenhum pacote do host ou alvo foi instalado. PHP8.3-mysql e Apache já satisfazem as dependências, sem instalar PostgreSQL, SQLite, FPM ou outro servidor web.

| Item | Resultado |
| --- | --- |
| Pacote | adminer 4.8.1-2, arquitetura all |
| Origem | Ubuntu noble/universe, registro de índice assinado |
| Transação Base/Live | um pacote novo em cada visão; nenhum upgrade, remoção ou conflito |
| Download único previsto | 798.606 bytes, cerca de 780 KiB |
| Installed-Size previsto | 2.949.120 bytes, 2,81 MiB por visão completa |
| SHA-256 esperado | `78f71ebaefe916be6a7cb7bab722f80c1964e36cba68fac5042e0a5a97611d4f` |
| Origem para futura aquisição | https://archive.ubuntu.com/ubuntu/pool/universe/a/adminer/adminer_4.8.1-2_all.deb |

Foi realizado **somente HEAD HTTPS**, resposta 200 e Content-Length 798606, sem corpo: `work/adminer-plan-j1x_gycp/availability.json`. Não há deb local adquirido; portanto **o SHA-256 do arquivo real e a inspeção de maintainer scripts/conffiles ainda não foram realizados**. Autenticidade do registro assinado não equivale à integridade de um arquivo não adquirido. A etapa futura deve conferir tamanho/hash e toda a cadeia novamente, depois de aprovação e revisão de segurança.

Não há daemon Adminer adicional: PHP atende requisições no Apache existente. O incremento de disco foi estimado pelo pacote, não medido em SquashFS; RAM e latência não foram medidas. O memory_limit de PHP é teto de requisição, não consumo reservado. Não prometer que a interface ficará dentro de uma quantidade de RAM sem teste, especialmente com grandes importações e o navegador aberto.

## Compatibilidade

As duas visões atuais registram PHP 8.3.6-0ubuntu0.24.04.13, libapache2-mod-php8.3/php8.3-mysql da mesma versão e MariaDB 10.11.14. O projeto Adminer declara PHP 8 com sessões e MariaDB; o [MariaDB documenta esse cliente](https://mariadb.com/docs/server/clients-and-utilities/graphical-and-enhanced-clients/adminer). Dependências foram resolvidas sem conflito, mas isso é compatibilidade declarada/simulada, **não teste de PHP, login ou consultas reais**.

O pacote distribui /usr/share/adminer/adminer.php, configuração PHP e conf Apache. Depois de adquirir uma versão aprovada, inspecionar esses arquivos, hooks e APIs antes de implementar um wrapper. O wrapper ainda não foi escrito e o Alias da proposta não deve ser ativado enquanto ele não existir e passar nos testes. Nunca servir PHP como texto quando o handler estiver ausente.

## Integração com o Control

A opção **Gerenciar bancos de dados** foi adicionada somente ao protótipo separado, junto ao MariaDB. Ela confere estados simulados de Apache/MariaDB; se algum não estiver ativo, orienta iniciar pelo fluxo já autorizado, sem iniciar, habilitar boot ou desbloquear serviços automaticamente. Se ambos estiverem ativos, mostra a URL que abriria. O protótipo não abre navegador, HTTP, banco ou Polkit real.

Implementação futura: abrir URL constante `http://127.0.0.1/devlite-adminer` por Gio/associação HTTP do navegador padrão, como usuário normal; alternativa de aceitação `http://[::1]/devlite-adminer`. Não receber URL, SQL ou credenciais da UI; sem shell, pkexec para abrir navegador ou parâmetros de autenticação na URL. Um navegador funcional, inclusive no Live, permanece pré-requisito: a integração não resolve por si a aplicação pendente do navegador.

As ações administrativas continuam restritas à allowlist de serviços do Control. Não acrescentar execução de SQL/root ou criação genérica de usuários ao helper de serviços. Abrir a interface web não precisa de privilégio; iniciar Apache/MariaDB continua sujeito a confirmação/autorização previstas no Control.

## HTTP exclusivamente local IPv4/IPv6

Propostas, não instaladas: `work/adminer-plan-j1x_gycp/proposal/ports.conf` e `devlite-adminer-local.conf`.

1. Preservar o listener atual IPv4 e acrescentar somente IPv6 loopback: `Listen 127.0.0.1:80` e `Listen [::1]:80`. Não usar Listen 80, 0.0.0.0, [::] ou endereço da LAN. A [documentação Apache](https://httpd.apache.org/docs/2.4/bind.html) exige colchetes em IPv6 e alerta sobre listeners sobrepostos. Mesclar sem duplicar e abortar se IPv6 estiver desabilitado ou a porta conflitar; não usar wildcard como fallback.
2. Aplicar defesa adicional por `Require ip 127.0.0.1 ::1`, não apenas Require local. O Apache também considera outras condições locais em Require local; a proposta usa os dois endereços explícitos. Ver [mod_authz_host](https://httpd.apache.org/docs/2.4/mod/mod_authz_host.html).
3. Alias dedicado aponta somente para wrapper root-owned fora de /var/www/html, sem dados ou credenciais graváveis nesse diretório. Negar acesso HTTP direto à árvore nativa /usr/share/adminer; PHP pode incluir os arquivos localmente. Desabilitar o Alias global padrão do pacote, se algum maintainer script o habilitar, antes de qualquer start; verificar a configuração efetiva, não só o texto da proposta.
4. Restringir Host ao localhost/IP literal, sem htaccess/Indexes. Não disponibilizar proxy reverso, túnel ou mudança de firewall para Adminer. Auditar mod_remoteip/proxies existentes: não confiar em X-Forwarded-For ou presumir que um teste de modelo Python reproduz a interpretação Apache.
5. O wrapper futuro deve limitar driver a MariaDB/MySQL e destino local, rejeitar root/login vazio e senhas vazias, sem defaults de credenciais ou plugins de passwordless/permanent login. Validar a API da versão aprovada; não copiar hooks incompatíveis de outra versão. Revisar recursos e verificação de versões para que a primeira utilização não instale/baixe componentes.

A configuração atual do projeto escuta só em 127.0.0.1:80; nenhuma porta IPv6 foi habilitada nesta tarefa. Os testes agora são estáticos/de modelo. Só testes reais de sockets e HTTP podem provar isolamento efetivo, incluindo uma requisição externa IPv4 e IPv6 que deve falhar mesmo com Host/X-Forwarded-For forjados. Usuários/processos locais continuam alcançando loopback: ele não substitui autenticação de banco.

## Credenciais e usuário próprio de desenvolvimento

O Control **não solicita, recebe, salva ou registra senha de banco**. Credenciais são digitadas apenas no Adminer; não podem entrar em URL, JSON, configuração de imagem, logs do Control ou chaveiro criado por ele. Adminer usa estado de sessão PHP para login temporário; revisar cookies/sessões e não habilitar login persistente. Não prometer ausência de armazenamento transitório na sessão web nem controlar silenciosamente o gerenciador de senhas do navegador.

Preservar root@localhost com autenticação unix_socket. Não alterar o plugin de root, liberar senha vazia, mapear www-data para root ou embutir credenciais. [MariaDB explica unix_socket](https://mariadb.com/docs/server/reference/plugins/authentication-plugins/authentication-plugin-unix-socket); o usuário do processo web não é o administrador do sistema.

**Procedimento futuro no guest, executado uma vez pelo administrador, não pelo Control nem no Ubuntu Server de build. Não foi executado.** Abrir uma sessão administrativa autorizada e desabilitar histórico dessa sessão do cliente, por exemplo:

```bash
sudo env MYSQL_HISTFILE=/dev/null mariadb
```

Na sessão interativa, definir uma senha forte e exclusiva; o texto abaixo é placeholder de documentação, nunca senha padrão de imagem:

```sql
CREATE DATABASE devlite_dev CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'devlite_admin'@'localhost' IDENTIFIED BY 'SUBSTITUA_POR_SENHA_FORTE_EXCLUSIVA';
GRANT ALL PRIVILEGES ON devlite_dev.* TO 'devlite_admin'@'localhost';
SHOW GRANTS FOR 'devlite_admin'@'localhost';
```

Esse usuário administra **o banco do projeto**, não a instância inteira: sem GRANT OPTION, privilégios globais, FILE ou administração de usuários. Para outro projeto, conceder acesso ao banco nominal correspondente em preparação administrativa separada. Não executar IF NOT EXISTS seguido de alteração automática de senha de uma conta preexistente; revisar conflitos antes.

Usar servidor `localhost` no Adminer para conexão Unix socket e usuário devlite_admin com sua senha. Não trocar por 127.0.0.1 sem revisar o host da conta: no Linux, conta @localhost e conexão TCP loopback não são equivalentes, conforme [CREATE USER](https://mariadb.com/docs/server/reference/sql-statements/account-management-sql-statements/create-user). Não criar conta @% nem alterar bind de MariaDB. O acesso HTTP via IPv6 não obriga a expor MariaDB por TCP IPv6: o PHP pode continuar usando socket local.

## Plano de aplicação futura e aceitação

- Primeiro liberar uma versão após revisão de segurança/origem; adquirir/hash/inspecionar o artefato somente após autorização. Não ampliar nem reutilizar o contrato selado do navegador: Adminer exige lock/contrato novos.
- Revalidar a transação combinada com navegador e Control aprovados, sem upgrades incidentais. Instalar somente em cópias Base/Live completas com serviços bloqueados; auditar dpkg/APT e scripts do pacote. Não gravar usuários, senhas ou bancos de exemplo nas camadas da distribuição.
- Mesclar config e wrapper revisados nas duas visões, preservar demais sites/projetos, idioma, instalador e boot. Reconciliar o delta Live a partir das duas visões efetivas; nenhum pressuposto de SquashFS independentes.
- No guest: apache2ctl -t e inspeção de vhosts/módulos/listeners, PHP mysqli/session e handler efetivo; resposta executada como PHP, sem código-fonte exposto. Abrir ambos os URLs locais; testar Host inesperado, rotas alternativas, acesso direto ao pacote e HTTP externo IPv4/IPv6 negado. Verificar ACL após posterior configuração de outros sites.
- Login com conta de projeto; criar tabela, inserir/consultar/alterar/exportar/importar e encerrar sessão. Rejeitar root, vazio, destino externo/driver não aprovado; verificar cookies, CSRF, nenhum auto-login e nenhuma credencial em logs/URL/Control. Medir RAM/latência com operações pequenas e importação limitada.
- Repetir no Live e instalado, após reinício. Contas/bancos criados no Live sem persistência são efêmeros; avisar, não copiar credenciais da sessão para a instalação. Sem autostart implícito de Apache/MariaDB.

O planejamento não homologa login, SQL, PHP/Apache, HTTP ou persistência. Nenhuma instalação, serviço, camada ou ISO foi alterada.

## Evidência final

**462 testes aprovados**, incluindo **13 novos** do planejamento Adminer. Cobrem listeners fixos, URLs sem credenciais, pré-requisitos, ausência de autostart, barreira de segurança e ausência de executor no mock. Os testes de ACL são de modelo/texto, não testes de rede Apache. Control homologado e código selado do navegador preservados. Evidência: `docs/evidencias/adminer-planejamento.json`.

## Aquisição autorizada e inspeção estática posterior

Após a autorização geral do usuário, o deb Ubuntu 4.8.1-2 foi adquirido para revisão em `work/adminer-review-11po9k_l`, sem instalar ou executar PHP/maintainer scripts. Tamanho e SHA-256 correspondem ao índice assinado: **integridade do artefato agora conferida**. Os registros anteriores de “não adquirido” descrevem a etapa inicial e permanecem como histórico.

A configuração nativa contém `Alias /adminer /etc/adminer` e `Require all granted`; não deve ser habilitada na integração. A proposta foi reforçada para negar `/etc/adminer`, `/usr/share/adminer` e a rota `/adminer`, além de manter o alias próprio restrito. O conf.php nativo habilita AdminerVersionNoverify, desabilitando verificação remota de versão. Não há postinst no arquivo de controle examinado; prerm/postrm foram somente lidos.

O pacote segue **bloqueado para instalação** pela revisão de segurança, compatibilidade dinâmica e wrapper ainda pendentes. A prévia de texto de adminer.php encontrou bytes não UTF-8; o hash foi calculado sobre os bytes originais, sem alterar o arquivo. Evidências: `work/adminer-review-11po9k_l/review.json` e `hardened-apache-proposal.conf`.

## Alternativa upstream versionada adquirida para revisão

Adminer **6.3.0 MySQL multilíngue**, 441.747 bytes, SHA-256 `33af3816a08213ae7579f8416e66d7d70054d6bcd70516d4ad3124f4b8b5c1e0`, adquirido do release oficial GitHub e conferido contra asset.digest da API oficial via HTTPS. Sem URL latest, repositório externo APT, instalação ou execução PHP. O commit informado pela API é unsigned; não foi verificada assinatura GPG independente. Essa proveniência por HTTPS/API não deve ser descrita como assinatura GPG.

Os 22 advisories públicos do repositório foram preservados para revisão, com versões corrigidas declaradas até 6.1.1, e o release 6.3.0 anuncia correção adicional de CSRF. Isso favorece avaliar a variante 6.3.0 em vez de distribuir Noble 4.8.1, mas não prova ausência de falhas nem substitui revisão de wrapper, licença e testes PHP/MariaDB/HTTP. A versão final da integração permanece não aplicada e não homologada.

Evidências em `work/adminer-review-11po9k_l/upstream-acquisition.json`, `upstream-public-advisories.json` e `docs/evidencias/adminer-revisao-autorizada.json`. Suíte após o reforço do alias: **463 testes aprovados**, incluindo 14 de Adminer.

## Compilação verificada no PHP real do alvo

Após autorização, a variante upstream 6.3.0 MySQL passou em `php8.3 -n -l` no PHP 8.3.6 da nova Base. Teste isolado em filesystem somente leitura, UID 65534 e capabilities zero; não executou o PHP como aplicação e não iniciou banco ou HTTP. Evidência: `work/adminer-php-check-w5tie5iq/result.json`. Permanecem pendentes integração Apache, wrapper, autenticação, consultas e IPv4/IPv6 reais. Suíte final com os testes de segurança dos verificadores: **479 testes aprovados**.
