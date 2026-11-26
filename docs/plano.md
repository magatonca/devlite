# Plano de desenvolvimento

| Fase | Entregas | Critério de saída |
|---|---|---|
| 1 — Planejamento | Estrutura, diagnósticos, arquitetura e critérios | Revisão dos documentos e dos recursos |
| 2 — Base e laboratório | Aprovação de download, autenticidade da ISO, inventário e VMs de teste | Base autenticada e live/instalador originais funcionando |
| 3 — Pipeline mínimo | Automação de extração e reconstrução sem customizações | ISO reconstruída inicia e instala em BIOS e UEFI |
| 4 — Software e idioma | Pacotes de desenvolvimento, redes, escritório e pt-BR | Ferramentas e idioma funcionam live e após instalação |
| 5 — Personalização | Arte original, menu XFCE e DevLite Control | Interface consistente e ações administrativas restritas |
| 6 — Qualidade e segurança | Auditoria de serviços, recursos, atualização e licenças | Matriz de aceitação aprovada e nenhuma falha crítica aberta |
| 7 — Release 1.0 | ISO, hashes, documentação de uso e recuperação | Instalação limpa reproduzida e entrega revisada |

Aprovações necessárias: baixar ISO e metadados; instalar dependências adicionais; executar operações privilegiadas na VM de build; iniciar cada construção; publicar artefatos. Alterações de disco ou partições permanecem fora do escopo sem autorização específica. Instalações de teste serão exclusivamente em discos virtuais descartáveis autorizados.

## Estado após Fase 2

Aquisição, autenticação, hash e inspeção estrutural concluídos. Boot live e instalação da base original ainda não foram executados em VM, portanto o critério completo de laboratório da Fase 2 permanece pendente antes de promover a reconstrução da Fase 3. Nenhuma autorização de build foi concedida.

## Fase 3A — preparação do laboratório

Procedimento e diagnósticos concluídos em [fase3a-testes-iso.md](fase3a-testes-iso.md). Execução manual dos testes BIOS/UEFI ainda pendente; esta é a porta anterior à Fase 3B de reconstrução. As restrições de criação de VMs, instalação e build permanecem ativas.

## Fase 3B — exceção experimental autorizada

Por decisão explícita do usuário, os testes manuais da 3A foram adiados e a reconstrução sem customizações foi autorizada. A execução e as verificações estruturais são descritas em [fase3b-pipeline.md](fase3b-pipeline.md). Resultado não equivale à aprovação de boot ou instalação.

## Fase 4A — preparação da personalização

Seleção declarativa, arquivos de configuração, auditoria de camadas e verificações implementadas sem aplicação. Ver [fase4a-personalizacao.md](fase4a-personalizacao.md). A 4B dependerá de aprovação para aquisições, operações privilegiadas no laboratório e execução do instalador de pacotes; não há autorização para gerar ISO personalizada completa nesta fase.

## Fase 4B.1 — personalização mínima experimental

Configurações básicas aplicadas e camadas reconstruídas, sem pacotes adicionais. ISO gerada e validada estruturalmente conforme [relatório](fase4b1-personalizacao-minima.md). A execução real de BIOS/UEFI, instalação e persistência permanece pendente e não foi substituída pelos testes estáticos. A ampliação para pacotes exige planejamento e autorizações específicas.

## Fase 4B.2 — preparação dos programas

Simulações APT nos dois alvos, perfis inativos, auditorias e recursos documentados em [fase4b2-preparacao-programas.md](fase4b2-preparacao-programas.md). Instalação/chroot/rebase, aquisições e nova ISO continuam bloqueados. Próxima fase: materializar backend isolado e comandos exatos para autorização, revalidar fontes e recursos, instalar somente após aprovação.

## Fase 4B.3 — executor isolado

Implementação concluída com 105 testes sem operações privilegiadas; [arquitetura e comandos concretos](fase4b3-executor-isolado.md). Próxima porta: espaço suficiente e probe real autorizado, sem pacotes. Aquisição e instalação exigem autorizações próprias. A aplicação/captura do delta live e uma nova ISO continuam fora desta etapa.

## Fase 4B.4 — validação prévia ao probe

105 testes originais repetidos e 116 aprovados na suíte ampliada. Expansão observada: cerca de 73 GiB livres; pré-requisitos atendidos por leitura. Probe reforçado, com comando concreto e aprovação pendente. [Relatório](fase4b4-validacao-isolamento.md). Próxima porta: confirmação explícita para probe normal sem pacotes; interrupção real e instalações exigem decisões separadas.

Após confirmação do usuário, o probe normal foi executado e aprovado (exit 0, probe_passed). Host e resíduos foram conferidos; flags restauradas. Instalação, interrupção/recuperação reais e rebase seguem pendentes.

## Fase 4B.5 — preparação dos pacotes

Simulação repetida sobre snapshot local autenticado; 243 debs únicos, 322,61 MiB, sem remoções ou conflitos. [Plano e comando de aquisição](fase4b5-preparacao-pacotes.md). Nenhum pacote baixado; rede de aquisição e instalação têm autorizações independentes, ainda false. Metadados remotos mais recentes existem: resolver o último snapshot exige obtenção/validação sob autorização e outro manifesto.

Aquisição do manifesto 4B.5 autorizada e concluída: 243 debs, 322,61 MiB, todos revalidados. Índices remotos não atualizados; instalação e testes reais de falha continuam bloqueados. Evidência: [aquisicao-pacotes.json](evidencias/aquisicao-pacotes.json).

## Fluxo acelerado 4B.7–4B.9

Desenvolvimento integrado preparado; cache staged e code/probe preservados. Aguardando aprovação única da instalação Base/Live. Integração root, ISO e VMs permanecem bloqueados separadamente. [Relatório consolidado](fases4b7-9-integradas.md) registra resultados executados e pendências, inclusive três ferramentas externas ausentes.
