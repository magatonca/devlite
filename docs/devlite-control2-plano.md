# DevLite Control 2.0 — arquitetura proposta e protótipo para aprovação

## Resultado e escopo

Protótipo Python/GTK3 separado em `prototypes/control2`, com backend exclusivamente simulado. Prévia de layout autocontida em `preview.html`; aplicação interativa em `app.py`. Não substitui o Control homologado, não chama pkexec/systemctl/journalctl, não instala policy e não modifica Base/Live. Dados de versões, métricas, rede e serviços são fictícios e identificados como tal. A prévia HTML não é uma screenshot GTK.

## Implementação atual examinada

- `overlay/final-candidate/usr/bin/devlite-control`: interface de terminal, consulta seis units via systemctl; request valida três identificadores e start/stop/restart, invocando pkexec por vetor fixo. Comentários antigos de “somente consulta” não descrevem todas as funcionalidades existentes.
- `usr/libexec/devlite-service-control`: helper Python isolado (-I), exige root e identidade DevLite, allowlist fixa, timeout, ambiente controlado e chamadas sem shell. Desmascara para iniciar/reiniciar e restaura máscaras ao final. MariaDB inclui mysql.service; Docker inclui containerd.service e docker.socket.
- `org.devlite.services.policy`: autenticação auth_admin em sessão ativa; nega usuários inativos/outros. Sem sudoers ou concessão administrativa geral.
- `devlite-control.desktop`: abre terminal e preserva Icon=devlite. Nenhum desses quatro arquivos foi alterado.

Reutilizar a separação UI/cliente/helper, identidade do alvo, allowlists, timeout e Polkit. Não reutilizar cegamente a política de remáscara: autostart explícito exige distinguir a escolha persistente do usuário do estado momentâneo do serviço. O helper 2.0 só será implementado após aprovação, com migração controlada e preservação do backend atual como referência.

## Arquitetura definitiva proposta

1. **UI GTK3 não privilegiada:** abas Serviços e Sistema/rede, português brasileiro, seleção e confirmação, apresentação de erros e logs como texto puro. Nunca iniciar a janela por pkexec. Sem Electron, dock, daemon novo ou servidor HTTP.
2. **Modelo/controle:** estado imutável por serviço, fila de operações e consultas assíncronas, atualização após toda tentativa (sucesso, erro ou cancelamento). GLib entrega resultados na thread principal. Uma operação por serviço/alteração de boot por vez; desabilitar controles enquanto pendente, sem congelar janela.
3. **Leitura sem privilégios:** systemctl show com propriedades fixas LoadState, ActiveState, SubState, UnitFileState e Result; executáveis/argv absolutos, sem pager e timeout. Consultar unidades principais apache2.service, mariadb.service e docker.service; dependências aparecem como detalhes, sem novas ações genéricas.
4. **Administração mínima:** cliente invoca `/usr/bin/pkexec /usr/libexec/devlite-control2-helper OP SERVIÇO`. Helper root:root, sem escrita por usuários, Python -I, valida novamente identidade DevLite, euid, aridade, serviço e operação; ambiente fixo. Não confiar na validação da UI nem aceitar nomes de unit, caminhos, comandos ou argumentos systemctl livres.
5. **Leitura de logs:** tentar journalctl sem privilégios, unit fixa, limite de 100 linhas e 64 KiB; sem pager, cores, follow ou filtros livres. Em acesso negado, oferecer autenticação para um helper de logs separado, com política e argv específicos ainda a implementar. Não adicionar usuário a adm/systemd-journal nem conceder leitura global do journal.

O `model.admin_argv()` é apenas contrato de vetor, sem executor. `policy-proposal.xml` propõe a ação de administração, auth_admin para sessão ativa, sem auth_admin_keep, allow_any ou allow_inactive. Não instalar a proposta nesta fase; a política específica de logs ainda precisa ser preparada com seu helper. Manter paths distintos para evitar associação ambígua de ações pkexec.

## Estado, operações e boot

Mapear loaded+active → Ativo, loaded+inactive → Parado, loaded+failed → Falhou. Ausência, erro, timeout e estados transitórios → Desconhecido, com detalhe “iniciando/parando/consulta indisponível” sem inventar sucesso. Não confundir retorno zero do cliente com estado final da unit. Estado do boot real deve representar enabled/disabled/masked/static/indirect/unknown; o booleano do mock é simplificação deliberada.

Start/stop/restart nunca alteram silenciosamente a preferência de inicialização. Enable/disable são operações separadas e **sem --now**: ativar boot não inicia; desativar boot não para. Parar e reiniciar exigem confirmação com impacto sobre conexões, bancos e contêineres. O mock também confirma desativação do boot. Cancelar autenticação ou confirmação não muda estado; sempre reconsultar depois de uma tentativa real.

O helper futuro deve registrar e verificar estado anterior de máscaras/links e política de autostart. Para boot desativado, preservar o modelo seguro atual de liberação controlada e restauração das máscaras originais, sem apagar overrides de terceiros. Para boot explicitamente ativado, não remascar depois de toda ação. Alterações persistentes exigem confirmação independente e recibo local limitado aos serviços gerenciados. Não restaurar arquivo de terceiro por aproximação ou sobrescrever links desconhecidos.

**Docker merece tratamento próprio**, confirmado pela leitura das units publicadas: docker.service Requires=docker.socket e Wants=containerd.service. containerd é um runtime separado e pode servir outros workloads. Proposta: parar Docker junto do socket que poderia reativá-lo, sem parar containerd compartilhado automaticamente; mostrar o estado dessas dependências. A diferença em relação ao helper antigo precisa ser aprovada e testada. Habilitar boot de Docker exige liberar dependências mascaradas, habilitando apenas a unit principal necessária, sem automaticamente habilitar todas as dependências no boot. Se um socket/override externo impedir desativação efetiva, apresentar conflito e bloquear mudança incompleta, em vez de exibir “desativado” incorretamente. Não adicionar usuário ao grupo docker.

Allowlist administrativa proposta: três serviços principais; docker.socket/containerd.service somente como dependências fixas da política Docker, não como unidades arbitrárias. Resolver mysql.service como alias apenas após confirmar a unit canônica MariaDB; não assumir que exista em toda instalação.

## Informações e desempenho

- Versões: comandos fixos sem shell e com ambiente saneado; PHP/Composer/Git em seus paths de pacote e Node/TypeScript nos wrappers versionados DevLite (`/usr/local/bin/node` e `tsc`). Não usar PATH/flags fornecidos pelo usuário, executar como root ou instalar algo para consultar versão. O manifesto de componentes fornece proveniência, mas não substitui a verificação do executável presente. Remover variáveis de injeção como NODE_OPTIONS; limitar saída e tempo.
- CPU: delta de /proc/stat com relógio monotônico; primeira amostra “calculando”. Memória: MemTotal/MemAvailable de /proc/meminfo. Disco: statvfs, diferenciando espaço disponível ao usuário de reservado. No Live, identificar overlay/camada gravável para não apresentar a capacidade da ISO como disco de instalação.
- Rede: leitura das informações do NetworkManager/systemd-resolved e de endereços/rotas; suportar múltiplas interfaces, IPv4/IPv6, rotas e métricas. Exibir o resolvedor local separadamente do DNS upstream; não apresentar 127.0.0.53 como servidor externo. Erro de permissão ou ausência do serviço retorna indisponível, sem root genérico.
- Identidade: arquivos /etc/devlite-release e /usr/share/devlite-os/identity.json, validados e somente lidos; nenhuma consulta remota.
- Atualização proposta a cada 2–5 segundos enquanto a janela estiver visível, pausada/reduzida quando oculta; cancelar timers e processos na saída. Métodos reais com timeout e limite de stdout/stderr, sem fila ilimitada. Um timeout do cliente não garante que systemd cancelou o job: marcar resultado pendente e reconsultar antes de permitir nova tentativa.

Não há necessidade prevista de psutil, Electron ou serviço residente. GTK3 já está no alvo. Não foi feito benchmark de memória/CPU ou renderização: medir em guest com 6 GiB, sem aceleração e em 1024x768/HiDPI. A página HTML é só revisão de composição; o aplicativo final permanece GTK.

## DevLite Modern e protótipo

Aparência única escura: grafite #171c24, azul #348bd6, textos claros, botões nativos e ícones DevLite/XFCE existentes. CSS restrito à classe da janela do protótipo; sem mudar tema global, painel ou greeter. Sem animações e sem alternância claro/escuro. Layout padrão 820×560, estados também em texto e confirmação modal antes de operações de interrupção. Revisar contraste, foco, acessibilidade, escalonamento e layout compacto em sessão real.

Mock implementado: três serviços com quatro estados possíveis, ações de runtime e boot separadas, confirmação, logs recentes simulados e recuperação após falha simulada; CPU/memória/disco, versões e rede fictícios. SimulatedBackend é o único backend disponível. Não há flag para conectar serviços reais. A política e os comandos futuros não são executáveis pela interface nesta fase.

## Dependências verificadas e integração futura

Manifests Base e Live atuais registram python3-gi 3.48.2-1, gir1.2-gtk-3.0 3.24.41-4ubuntu1.3, gir1.2-glib-2.0 2.80.0-6ubuntu3.8, policykit-1/polkitd/pkexec 124-2ubuntu1.24.04.3 e policykit-1-gnome 0.105-7ubuntu5. Isso comprova os pacotes declarados nas duas visões, não a sessão gráfica ou agente funcionando.

No Ubuntu Server, o módulo gi existe, mas `gi.require_version('Gtk','3.0')` retorna “Namespace Gtk not available”; também não há DISPLAY/Wayland. A checagem do protótipo terminou com mensagem controlada; nenhum pacote foi instalado. Usar preview.html para revisão e executar app.py somente em sessão gráfica com GTK3.

Após aprovação: preparar payload e helper 2.0 novos, manter launcher/backend atual até aceitação; novo desktop entry gráfico Terminal=false e Icon=devlite. Instalar somente em cópias Base/Live pelo pipeline autorizado, não no Server. Reconciliar delta a partir das visões completas, sem tratar folha Live como rootfs autônomo. Não autoativar serviços durante instalação nem criar defaults de boot diferentes dos aprovados.

No Live, alterações de boot podem ser efêmeras sem persistência: indicar claramente e testar como usuário comum com agente Polkit ativo. No instalado, testar preferência após reinício real sem ISO. Preservar locale/ABNT2, instalador, BIOS/UEFI, aplicações, políticas de segurança e dados do usuário. A identidade de guest é obrigatória no helper; copiar um executável para o host não deve habilitar administração dele.

## Critérios para implementação definitiva

- Aprovar composição GTK, comportamento de confirmação e semântica explícita de máscaras/boot/Docker.
- Implementar backend real e helpers/policies com allowlists duplicadas no lado privilegiado, timeouts, saída limitada, logs sanitizados sem markup/ANSI e erros pt-BR. Logs podem conter segredos: nada de upload/telemetria automática.
- Testar autenticação concedida/negada/cancelada, agente ausente, serviços inexistentes/falhos/transitórios, socket Docker e containerd compartilhado; mudanças externas de estado e falha parcial de boot.
- Recuperação de alterações de boot por snapshot verificado e melhor esforço, sem prometer desfazer parada de banco ou contêineres. Preservar dados; nenhuma ação apt/reboot/particionamento no helper.
- Testar responsividade/foco/acessibilidade e métricas em GUI real Live/instalada; reiniciar e verificar autostart separadamente do estado atual.
- Somente depois integrar ao payload definitivo e solicitar aplicação em imagens/ISO em operação autorizada própria.

O protótipo e o plano aguardam aprovação. Nenhuma homologação gráfica, operação Polkit real ou persistência foi declarada aprovada.

## Evidências desta preparação

Suíte completa: **449 testes aprovados**; **19 testes específicos** passaram novamente após os ajustes de estilo/ícones do protótipo. Logs em `reports/testes-control2-prototipo.txt` e `reports/testes-control2-prototipo-direcionados.txt`. Os hashes dos quatro arquivos do Control atual permanecem idênticos aos do início desta tarefa; os 51 arquivos selados do adaptador do navegador também permanecem intactos. Evidência e hashes dos protótipos em `docs/evidencias/devlite-control2-prototipo.json`. Sem prova de renderização GTK: o host não possui o namespace Gtk nem sessão gráfica; a prévia HTML e os testes de modelo não substituem essa prova.

## Integração MariaDB/Adminer acrescentada

Ver [plano Adminer](devlite-control2-adminer.md). O protótipo inclui “Gerenciar bancos de dados”, somente simulado. Adminer é candidato preferencial pelo baixo incremento, mas a versão Noble 4.8.1-2 permanece bloqueada por revisão de segurança; não houve instalação ou habilitação HTTP.
