# Validação

| Verificação | Estado |
|---|---|
| Pré-voo de armazenamento e três testes de regressão | Aprovado |
| Execução de comando inofensivo pelo monitor | Aprovado |
| Sintaxe AppArmor da v5, sem carregamento | Aprovado |
| Integridade do arquivo de backup histórico | Aprovado |
| SHA-256 completo da ISO v5 | Aprovado |
| Epiphany real em XFCE/X11 e sandbox WebKit v6 | Não executado |
| Instalador e recursos finais v6 | Não executado |
| Serviços, ferramentas, Polkit e DevControl 3.0 no guest | Não executado |
| Camadas, verificador estrutural e boot v6 | Não executado |
| Suíte completa v6 | Não executado |

## Checklist Hyper-V

1. Conferir SHA-256. Iniciar Live e instalar em VMs descartáveis de geração 1 (BIOS) e geração 2 (UEFI).
2. Verificar telas pt-BR do instalador, créditos, slides, contraste a 1024×768 e estado após dois reboots.
3. Executar Epiphany pelo menu e como padrão. Conferir HTTPS, HTML, JavaScript, os rótulos de processos e o sandbox em sessão real.
4. Testar DevControl como usuário comum e autorizado. Verificar cancelamento, comandos inválidos e estados Docker, socket e containerd. Repetir após reboot e atualização.
5. Validar Apache HTTP/PHP, MariaDB no localhost, versões das ferramentas, contêiner de teste, VPN real, SSH root negado e fingerprints diferentes em duas instalações.
6. Medir boot, RAM e disco com a mesma configuração da v5.

## Retomada e condições da candidata

| Verificação | Resultado |
|---|---|
| Testes direcionados v6 | 6 aprovados |
| Suite completa (histórica + v5 + v6) | 646 aprovados, 1 falha, 4 erros, nenhum skip |
| Verificador de projeto | 0 erros |
| Compilação do perfil AppArmor candidato | Aprovada, sem carregar política |
| Sintaxe Bash do diagnóstico | Aprovada |
| GTK DevControl v6 em Xvfb | Abertura e fechamento confirmados |
| cURL Ubuntu Noble Security | Três arquivos autenticados, simulação Base e Live aprovada |
| Apache, MariaDB, Docker, SSH e VPN em funcionamento no guest v6 | Não executado |
| Pack e estrutura da ISO | Não executado, namespace de montagem indisponível e suíte sem aprovação |

Os detalhes dos cinco testes históricos estão em `work/v6-validation/suite.log`. Para o checklist externo, executar `bash v6/hyperv-diagnostics.sh` na sessão XFCE do Live e do sistema instalado com o Epiphany aberto ou logo após a tentativa de abrir. A leitura do diário depende das permissões da conta. Revisar a saída antes de compartilhar. Repetir depois de reiniciar e comparar a execução e o boot das unidades.

## Suíte após as correções

A suíte final passou com 655 aprovações, zero falhas, erros ou skips. O verificador do projeto retornou zero erros. O executor manual foi submetido às verificações estáticas e aos testes de escopo dos mounts, ordem de limpeza, recibo e nomes das camadas. O pack, a montagem da ISO e a homologação Hyper-V ainda não foram executados. Ver o último checkpoint em `progresso.md` para o comando manual.

## Validação visual antes da candidata

No Hyper-V, percorrer idioma, Live/instalar, teclado, rede, fonte, particionamento guiado e manual, confirmação, criação do usuário, progresso e conclusão em pt-BR. Repetir em tema claro e escuro a 1024×768, com foco por teclado e escala de texto padrão e ampliada. Registrar tela, escala e texto para qualquer referência indevida, concatenação, corte, sobreposição ou baixo contraste. Conferir os quatro slides, os créditos e a identidade após reiniciar. Usar disco de VM descartável para verificar particionamento e manter os avisos de destruição e atualizações visíveis.

No host, o YAML, o catálogo real, as referências do logo e os pares de contraste de texto e botão foram verificados. A suíte executou 657 testes, todos aprovados. A renderização efetiva do assistente não foi executada.

A revisão visual no Hyper-V integra a homologação da candidata autorizada. O recibo vigente conserva 657 aprovações e zero erros no verificador. A revisão estática final confirmou o caminho dos recursos do instalador e os parâmetros do executor sem repetir a suíte.

## DevControl 3.0

Recibo local com sete testes afetados aprovados, zero erros no verificador e baseline de 657 testes preservada. No Hyper-V, conferir um único atalho em Live e instalado, janela em tema claro/escuro e resolução reduzida, ações reais autorizadas e negadas via Polkit, reconsulta após operações, persistência após reinicialização e comportamento de Docker/Socket/Containerd com consumidores ativos.

## Painel XFCE no Hyper-V

No Live e no primeiro login de um usuário novo no sistema instalado, passar o mouse pelo Whisker Menu e conferir o texto “Menu DevLite OS”. Verificar nitidez e legibilidade do SVG nos temas claro e escuro, a 1024×768 e com painel reduzido. Abrir com clique e pelo atalho, pesquisar e iniciar um aplicativo, testar favoritos e conferir os demais ícones do painel. Em um perfil com ícone e tooltip personalizados, reiniciar a sessão e confirmar que as escolhas individuais prevalecem sobre os padrões. [Histórico de comportamento do tooltip no Whisker Menu](https://gottcode.org/xfce4-whiskermenu-plugin/archive/)
