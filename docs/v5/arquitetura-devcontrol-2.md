# Arquitetura proposta — DevControl 2.0

Status: análise e planejamento; nenhum backend ou privilégio foi implementado nesta fase.

## Reuso correto

A v4 inclui o dashboard GTK3 em `/usr/lib/devlite/devcontrol/{app,collector}.py`, com launcher `devcontrol.desktop`. O código das camadas fix corresponde ao protótipo `prototypes/devcontrol`. Há sete abas, atualização assíncrona com um worker, timeout das consultas e mensagens de indisponibilidade. Reutilizar esse frontend e seu coletor, mantendo a interface como usuário comum.

Separadamente existe o frontend terminal `devlite-control`, o helper `devlite-service-control` e uma policy Polkit histórica. O helper remascara unidades em finally; essa lógica não pode ser reutilizada na v5. O protótipo `prototypes/control2` contém um modelo simulado útil para testes, não um controlador real homologado. Evitar dois atalhos contraditórios; preparar migração do launcher/CLI legado para o novo backend, com compatibilidade explícita.

## Componentes e fronteiras

| Componente | Privilégio | Responsabilidade |
|---|---|---|
| GTK3/PyGObject | usuário | Estado, confirmação, progresso, cancelamento e erros em pt-BR; tema Modern; nenhuma GUI root |
| Coletor/parser | usuário | Consultas systemd/D-Bus ou argv fixo, versões e recursos; sem mutação |
| Coordenador assíncrono | usuário | Uma operação por serviço/grupo, JobID/request ID e refresh após sucesso ou erro |
| Helper one-shot | root após Polkit | Validar enums e executar apenas operações/unidades aprovadas; sair ao terminar |
| Polkit + agente da sessão XFCE | sistema/sessão | Autenticar administrador ativo; negar sessão inativa/remota não autorizada |

Preferir o helper one-shot já familiar ao projeto, em vez de novo daemon residente. Invocação por pkexec com caminho absoluto fixo e policy própria. Defaults: `allow_any=no`, `allow_inactive=no`, `allow_active=auth_admin`; sem retenção ampla de autorização e sem regra sudoers. O binário/script e todos os seus pais devem ser root-owned, sem escrita por usuários; Python isolado, ambiente sanitizado, sem módulos carregados de diretórios graváveis.

Alternativa D-Bus on-demand só se houver necessidade comprovada; não conceder genericamente `org.freedesktop.systemd1.manage-units/manage-unit-files` ao usuário. Algumas APIs de enable/disable não fornecem os mesmos detalhes para filtragem que uma operação de unidade; não assumir que uma regra genérica restringe todos os métodos.

## API fechada

O frontend envia identificador de serviço e ação enum, nunca nome arbitrário de unidade, caminho, comando ou conteúdo shell. Backend mapeia ids para allowlist root confiável. Operações futuras: query, start, stop, restart, enable-autostart e disable-autostart. Leituras não precisam de root salvo logs protegidos, que exigem um endpoint de leitura restrito e autenticado.

- Apache → apache2.service.
- MariaDB → mariadb.service; mysql.service apenas alias validado.
- Docker → docker.service, docker.socket e estado de containerd.service; orchestrar segundo [plano-servicos.md](plano-servicos.md), sem interromper runtime compartilhado silenciosamente.
- SSH → ssh.service e ssh.socket, modos explícitos; verificar chaves e política efetiva antes de ativar. Confirmar risco de desconectar uma sessão remota ao parar.
- OpenVPN → distinguir NetworkManager de unidades openvpn-client@.service. Instâncias somente de uma lista de configurações root-owned aprovada; validar basename, symlinks e escape systemd. Não aceitar `@...` ou UUID livre como forma de executar serviço arbitrário; não importar/executar scripts de VPN automaticamente.
- PHP-FPM → descobrir versões/unidades realmente fornecidas pelos pacotes instalados e oferecer somente essa allowlist. Se ausente, informar indisponível, sem instalar. PHP CLI é informação de versão, nunca unidade systemd.

Usar argv fixos e `shell=False` ou API D-Bus tipada; `--` onde suportado. Nenhuma concatenação de entrada do usuário em comandos. Enable/disable sem `--now`, preservando separação entre estado atual e próximo boot. Start/stop/restart não devem mudar boot policy nem máscara.

## Estado e operação

Reaproveitar parser do coletor: LoadState, ActiveState, SubState e UnitFileState separados. Mostrar ativo/parado/falhou/desconhecido ou não instalado, além de enabled/disabled/static/alias/indirect/masked. Masked deve aparecer como bloqueio explícito; o Control não desmascara políticas intencionais do usuário ao iniciar. Corrigir máscaras de fábrica durante a construção v5 é responsabilidade distinta.

Consultar dependências e conclusão real do job systemd; retorno da solicitação não é prova de serviço pronto. Validar containerd/socket e, quando necessário, teste de disponibilidade local específico. Erros estruturados: não instalado, unidade inválida, acesso negado, autenticação cancelada, timeout, dependência falhou, conflito de socket e erro do daemon. Exibir mensagem útil e estado atualizado; não iniciar laço de tentativas nem remascarar como recuperação.

Confirmação antes de stop/restart e mudanças que afetem contêineres, banco ou acesso remoto. Atualizar status após todas as saídas, inclusive falha. Se a janela fechar, uma solicitação já entregue ao systemd pode continuar: rastrear JobID e reconciliar estado ao reabrir; não prometer cancelamento/rollback instantâneo.

Preservar um worker ou concorrência estritamente limitada, timeout por consulta e sem sobreposição de refresh. O coletor atual corta stdout depois de capture_output; para endurecer o backend, limitar também a leitura durante a captura, não só a string final. Atualizações apenas enquanto a janela estiver aberta, sem agente residente adicional.

## Logs, credenciais e validação de segurança

Logs somente das unidades allowlisted, quantidade/tamanho limitados, sem `--follow` permanente. Não adicionar usuário a systemd-journal ou docker para contornar permissões. Não ler/copiar senhas, ambientes completos, VPN secrets, chaves SSH ou credenciais SQL. Exportação de logs deve ser explícita, pois o próprio serviço pode escrever dados sensíveis.

Testar o helper com manager simulado e sessão Polkit negada/cancelada/inativa. Cobrir injeção, caminhos relativos, aliases maliciosos, unidades ausentes, instâncias VPN inválidas, PHP-FPM ausente e enum inválido. Depois testar Polkit real numa VM autorizada com usuário sem e com papel administrativo. Nunca validar chamando start/stop no Ubuntu Server hospedeiro.

Os 588 testes atuais são baseline. A abertura GTK com coletor fixo passou nesta auditoria; não prova autenticação administrativa ou controle real. Implementação e policy nova ficam para a Fase 2, com revisão e autorização própria para sua execução privilegiada.
