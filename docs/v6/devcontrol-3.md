# DevControl 3.0

Implementação ainda pendente. Reutilizar a interface GTK, o coletor em segundo plano e a separação entre cliente, Polkit e helper da v5.

A lógica v5 já para o socket antes de parar o Docker e separa ações de execução das ações de boot. Ela mantém o containerd em execução e a interface agrupa dependências do Docker e SSH. A divergência observada no Hyper-V precisa ser reproduzida com o estado efetivo e seu histórico. A ação de parar o Docker deve verificar o fechamento do socket. Preservar containerd se houver consumidores ou se a exclusividade não puder ser demonstrada.

Evoluir para cartões de sistema, CPU/memória/swap/disco, rede e resumo de serviços. Mostrar unidades Docker/SSH e dependências separadamente, estado transitório, persistência e resultado real por operação. Restringir ações por estado e pelas opções de instalação das unidades. Testar autorização, negação, cancelamento, timeouts e ações fora da lista. Exibir versões reais e a opção oficial de VS Code sob demanda. Conferir 1024×768 e temas claro/escuro.

## Implementação da retomada

A interface v6 acrescenta CPU por amostras de procfs, uptime, kernel, arquitetura e swap ao coletor herdado de memória, disco e rede. O tema segue o GTK e o painel mostra estado atual, estado de boot traduzido e resultado por serviço. Docker, Docker Socket, Containerd e SSH Socket têm linhas próprias. O helper v6 usa Polkit de administração ativa, allowlist e ações assíncronas. A parada do Docker inclui o socket. A parada direta de Containerd permanece bloqueada enquanto a exclusividade de consumo não puder ser comprovada. Abertura da janela em Xvfb confirmada. Persistência, descrições completas, layout final e execução administrativa real ainda exigem trabalho.

## Fechamento para a candidata v6

O DevControl 3.0 substitui os módulos no diretório instalado `/usr/lib/devlite/devcontrol`, tanto em Base quanto em Live. O overlay descartável retira o segundo atalho, o comando antigo, os helpers anteriores e suas políticas Polkit. Sobra um lançador `devcontrol.desktop`, um helper v6 e sua política para autenticação administrativa em sessão ativa. O empacotamento compara a composição final com os deltas e portanto verifica também essas remoções.

O dashboard usa cartões que se reorganizam conforme a largura, barras nas métricas de uso e linhas criadas somente para dados presentes. Reúne CPU, memória, swap, disco, uptime, kernel, arquitetura, rede e resumo dos serviços. A página de desenvolvimento consulta versões e mantém o link oficial de instalação do VS Code. A página de serviços separa ações de execução do controle de inicialização. O interruptor só muda após nova leitura do systemd. As mensagens distinguem cancelamento e recusa Polkit. A interface usa a paleta Modern sobre o tema GTK, com descrições e controles em pt-BR.

A verificação local abriu a janela a 640×440 sob Xvfb, exercitou o controle de inicialização com um serviço simulado e confirmou a substituição sem duplicidade em árvores de teste de Base e Live. A homologação no Hyper-V permanece obrigatória para inspeção visual e testes reais de Polkit, persistência, Docker, OpenVPN e serviços.
