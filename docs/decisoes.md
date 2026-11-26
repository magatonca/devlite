# Decisões e pendências

- D001: usar Xubuntu 24.04 LTS Minimal AMD64 como base candidata; não Ubuntu Server como filesystem de origem.
- D002: remasterização em laboratório isolado; comprovar preservação de boot e instalador antes de adicionar software.
- D003: Fase 1 somente documentação e scripts de leitura; sem implementação operacional de build.
- D004: manter serviços de desenvolvimento sob ativação explícita e DevLite Control com permissões mínimas.
- Pendências: versão Node LTS mantida no momento da implementação; origem do Docker e Compose v2; distribuição de VS Code e GitHub CLI; variantes PHP; licença do código original e uso de marcas; suporte e manutenção próprios; layout real do instalador; Secure Boot; expansão de disco/RAM; design original e escopo inicial do DevLite Control.
- Versões e fontes externas serão fixadas após consulta aos mantenedores oficiais, nunca inferidas desta lista de requisitos.

## Decisões da Fase 2

- D005: base 24.04.5 adquirida e autenticada; identidade e hash fixados em `docs/evidencias/iso-oficial.json`.
- D006: manter hierarquia minimal → minimal.live; personalizações persistentes na base e regeneração coerente da folha live.
- D007: preservar EFI anexada e boot híbrido; compatibilidade de boot observada estruturalmente, ainda sem ensaio de VM.
- D008: primeiro build será uma reconstrução sem alterações de pacotes, após autorização.
- Pendências resolvidas: número de squashfs, seleção da camada pelo initrd, fonte padrão do instalador e identificação de Desktop Bootstrap/Subiquity. Pendências restantes: boot real, instalação, Secure Boot e política de assinatura dos componentes modificados.

## Decisões da Fase 3A

- D009: recomendar Workstation diretamente no Windows; QEMU/KVM não disponível no guest observado e RAM insuficiente para uma VM aninhada de 4 GiB.
- D010: duas VMs e discos independentes para BIOS e UEFI, com instalação manual e teste de reboot sem mídia.
- D011: automação limitada a diagnóstico e validação documental; nenhum lançador de VM, instalador ou comando de particionamento.
- Identificação de hipervisor divergente entre lscpu e DMI impede concluir a topologia do Windows; não alterar Hyper-V/VBS a partir desses sinais.

## Decisões da Fase 3B

- D012: usuário adiou os testes manuais e autorizou desenvolver e gerar a reconstrução experimental sem customização. Isso substitui a porta de boot/instalação para este experimento; esses ensaios continuam não executados.
- D013: reconstrução nativa da árvore carregada, com replay de filesystem/boot e auditoria por extração separada; sem reimportar ownership do host.
- D014: nenhum arquivo de trabalho é apagado pelo pipeline. Saídas recebem nomes exclusivos e permanecem parciais até validação.

## Decisões da Fase 4A

- D015: planejador declarativo separado do construtor estrito 3B; sem executor de instalação ou --apply.
- D016: GH e Docker/Compose provenientes do Ubuntu; Node LTS por artefato oficial, TypeScript por npm isolado e VS Code por origem Microsoft ainda desabilitada.
- D017: configurações persistentes na base, com rebase da folha live e reconciliação do estado dpkg/APT; não copiar status antigo.
- D018: defaults pt-BR/ABNT2/America/Sao_Paulo preparados junto com argumentos do Casper. Alterações reais, rede e privilégios exigem autorização para 4B.

## Decisões da Fase 4B.1

- D019: aplicar somente idioma, teclado, fuso e identidade; preservar ID Ubuntu e todos os estados de pacotes/instalador.
- D020: extração/recompressão convencional com três comandos root autorizados em workspace fixo, após falha do exportador pseudo rootless com security.capability. Nenhuma montagem ou chroot.
- D021: aplicar à base e reconciliar a folha por presença/máscaras/ancestrais; nesta fonte a folha herda todos os payloads da base e permanece semanticamente idêntica.
- D022: arquivar assinatura/checksums upstream como proveniência e recalcular checksums experimentais sem alegar assinatura Ubuntu. Preservar verificações Casper e boot replay.
- D023: validação estática integral não aprova boot, instalação ou persistência. Não publicar nem criar commit automaticamente.

## Decisões da Fase 4B.2

- D024: resolver APT real offline com bancos dpkg das duas imagens e cópias de índices Ubuntu autenticados; não usar estado instalado do host.
- D025: manter 44 itens Ubuntu nos dois ambientes e bloquear os três externos; fechar dependências com alternativas/Pre-Depends e sem recomendações, remoções ou boot/instalador.
- D026: base e visão live completa terão transações próprias e versões comuns travadas; regenerar delta e estado coerentes, sem copiar dpkg/status antigo.
- D027: perfis de desenvolvimento locais, máscaras persistentes de daemons/socket e policy-rc.d temporário; sem grupos privilegiados automáticos.
- D028: planejamento não autoriza rede de aquisição, instalação, operações root ou nova ISO; nenhum backend instalador executável nesta etapa.

## Decisões da Fase 4B.3

- D029: rootfs em ext4 novo de 12 GiB por alvo, fontes SquashFS RO e namespaces/cgroup; nenhuma instalação no host.
- D030: supervisor e filho entram no rootfs; child com bounding set reduzido, no_new_privs e rede privada; não expor /proc/1/root do host.
- D031: autorizações separadas de probe/instalação/recuperação, vinculadas ao mesmo job e código; instalação exige probe root-owned aprovado.
- D032: rollback por quarentena de cópias, sem desfazer dpkg in-place nem excluir evidências; aceitação somente do par completo.
- D033: delta live apenas planejado; regeneração de whiteouts/atributos privados e equivalência deverão ser implementadas/testadas antes de reconstruir ISO.

## Decisões da Fase 4B.4

- D034: corrigir falso positivo da sentinela inexistente; exigir arquivo real e intacto no host, acesso negado no guest e evidências estruturadas.
- D035: validar limites cgroup e restrições efetivas no futuro probe, distinguindo inspeção por leitura de aprovação runtime.
- D036: recomendar somente probe normal, com comandos e hash novos; manter autorizações false até confirmação. Recuperação/interrupção reais e instalação continuam separadas.

- D037: probe normal autorizado e aprovado com código fixado; registrar comparações externas do host e atestado root-owned, preservar dados privados da tentativa e restaurar todas as permissões para false. Não ampliar essa autorização para instalação ou injeção de falhas.

## Decisões da Fase 4B.5

- D038: manter o executor e seu probe inalterados; implementar aquisição como módulo separado com gate/hash próprios.
- D039: deduplicar base/live por pacote/versão/arquitetura e conferir a cadeia assinada de cada arquivo; não substituir versão em indisponibilidade.
- D040: verificar repositórios somente por HEAD sem corpo nesta preparação. Registrar que o snapshot local autenticado é anterior aos últimos metadados remotos, sem alegar atualização desses índices.
- D041: download proposto limita-se ao manifesto congelado; nenhum download real de índices/debs ou instalação sem autorização específica.

- D042: aquisição limitada ao manifesto 06ac626af9624e3cf228ae9d6becc896b60c3b7b018f95e07ec1e88ee624ca9b, expressamente autorizada; conferir novamente todos os bytes do cache, preservar receipt/fontes e restaurar permissões. Nenhuma autorização de instalação inferida.

## Decisões do fluxo integrado

- D043: reusar o executor/código já aprovado e preparar seu cache sem alterar o contrato do probe.
- D044: autenticar separadamente snapshots diferentes, aceitando equivalência somente com mesmos pacote/versão/arquitetura/Filename/SHA/tamanho/URLs/alvos.
- D045: delta por inventário + whiteouts e prova real futura por kernel; manifests mantêm formato observado. Não reaplicar a folha antiga nem copiar banco dpkg.
- D046: gates independentes para instalação, integração e ISO; uma aprovação solicitada apenas para a operação de instalação claramente delimitada. Aceitação documental não equivale a boot real.
