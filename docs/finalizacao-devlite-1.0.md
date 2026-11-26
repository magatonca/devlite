# Finalização do DevLite OS 1.0 — preparação consolidada

Preparação concluída nesta rodada; **versão pública ainda não liberada**. A ISO experimental existente permanece preservada. Nenhuma nova ISO, instalação, montagem, VM ou exclusão foi executada. A única operação privilegiada desta rodada foi a auditoria de metadados autorizada (du/find, com detalhamento du no mesmo subtree). Downloads nesta rodada restringiram-se a metadados/chaves; nenhum programa foi adquirido.

## Resultados verificáveis

- **237 testes automatizados aprovados**, sem testes práticos de boot/instalação: [saída integral](../reports/testes-finalizacao-consolidada.txt).
- Metadados dos programas autenticados; hashes dos programas serão conferidos somente após download autorizado.
- Inventário dos manifests publicados: os **44 pacotes Ubuntu diretos** constam tanto na Base quanto na Live. Isso comprova inventário, não funcionamento: [evidência](evidencias/programas-inventario-publico.json).
- Arquivos críticos do hospedeiro continuam iguais à referência; contrato experimental selado preservado, permissões de execução desabilitadas: [estado](evidencias/finalizacao-acelerada-estado.json).
- Espaço livre medido: aproximadamente **21,25 GiB**. Proposta de limpeza: **49,88 GiB alocados**, projeção de **71,13 GiB livres**, sujeita a hardlinks/referências e medição posterior. Nada apagado: [21 caminhos completos, tamanhos, motivos e riscos](limpeza-final-proposta.md).

ISO principal: `/home/magaton/DevLite-OS/artifacts/release-c0srssh8/devlite-os-1.0-ubuntu-experimental.iso`, **3.550.609.408 bytes**. SHA-256 confirmado na geração:

```text
7f49f8b03ad0201f70c5deed4879ffedb79bf7b7a3f1f105ca8380be8da3e4db
```

As duas construções históricas são idênticas bit a bit. Isso não aprova boot, instalador, interface ou persistência. A ISO existente **ainda não contém** as novas personalizações de interface/Control, Node.js ou TypeScript preparadas nesta rodada.

## Validação prática preparada

Recomendado: **VMware Workstation no Windows**, reutilizando o laboratório descrito na Fase 3A. QEMU/qemu-img/virsh não estão disponíveis e /dev/kvm/virtualização aninhada não foram detectados no Ubuntu Server; nada instalado para contornar isso.

Usar duas VMs independentes, BIOS e UEFI, com 4 GiB RAM, duas CPUs e disco virtual novo de 40 GiB cada, sequencialmente. Sem discos físicos, compartilhamento do disco de desenvolvimento ou Secure Boot neste primeiro ensaio. Instruções: [instalação e validação](instalacao-devlite-1.0.md) e [roteiro experimental](fase4b9-validacao-pratica.md).

O novo coletor guest verifica identidade DevLite, usuário não root e contexto/firmware antes de consultar programas. Gera JSON e SHA-256, sempre com aprovação prática falsa e itens manuais pendentes. Não executar no hospedeiro. Cobrir Live e sistema instalado nos dois firmwares; reinstalação, login, XFCE, entrada ABNT2, idioma, aplicativos gráficos e reinicialização exigem evidência humana.

O perfil público em [acceptance-public-template.json](../config/acceptance-public-template.json) tem **148 critérios pendentes**, exige Node/TypeScript e mantém VS Code opcional. Validação documental verifica integridade/completude dos registros, sem substituir execução real. O modelo experimental anterior continua preservado.

## Programas pendentes e distribuição pública

Decisão do usuário: distribuição pública; **binário oficial do VS Code fora da ISO**. Apenas uma entrada opcional abre as instruções oficiais quando acionada. Não baixa, instala ou adiciona repositório. A decisão considera as restrições de compartilhamento do [contrato do VS Code](https://code.visualstudio.com/license); eventual instalação ocorre posteriormente por escolha do usuário.

| Programa | Versão fixada e origem | Autenticação realizada | Ainda pendente |
|---|---|---|---|
| Node.js LTS | 26.13.1, linux-x64, nodejs.org | SHASUMS OpenPGP válido; chave oficial conferida | Download do arquivo de 34.093.052 bytes, hash dos bytes, inspeção e teste no guest |
| TypeScript | 7.0.2, npm; pacote principal + @typescript/typescript-linux-x64 | Assinaturas ECDSA dos dois metadados verificadas; SRI fixado | Dois arquivos, verificação SHA-512/SRI e inspeção; tamanhos comprimidos não informados |
| VS Code opcional | 1.146.0-1794340865, repositório Microsoft | InRelease GPG, checksum do índice e SHA da API concordantes | Fora da ISO pública; eventual download posterior autorizado pelo usuário |

Node LTS foi conferido na [publicação oficial](https://nodejs.org/en/blog/release/v26.13.1), com chave `5BE8A3F6C8A5C01D106C0AD820B1A390B168D356`. Pré-requisitos declarados GNU/Linux x64 (kernel/glibc/libstdc++) cobertos pelos metadados da imagem; execução real permanece pendente. Referências: [plataformas Node](https://github.com/nodejs/node/blob/v26.13.1/BUILDING.md), [chaves oficiais](https://github.com/nodejs/release-keys).

TypeScript possui cerca de **29,0 MiB descompactados** somando os dois pacotes. O provedor nativo Linux x64 deve acompanhar o principal; não presumir que o pacote genérico sozinho basta. A chave do registry é identificada por `SHA256:DhQ8wR5APBvFHLF/+Tc+AYvPOdTpcIDqOhxsBHRwC7U`. Referências: [TypeScript](https://www.typescriptlang.org/download/) e [assinaturas npm](https://docs.npmjs.com/verifying-registry-signatures/).

A chave Microsoft conferida foi `BC528686B50D79E339D3721CEB3E94ADBE1229CF`; 38 grupos de dependências do Code têm cobertura nos manifests Base/Live, sem transação APT. O .deb tem 291.523.322 bytes; tamanho instalado declarado de aproximadamente 1,06 GiB, excluído do orçamento público. Referências: [chaves Microsoft](https://learn.microsoft.com/en-us/linux/packages), [instalação oficial](https://code.visualstudio.com/docs/setup/linux).

Provas e planos: [autenticação](evidencias/autenticacao-metadados-externos.json), [revisão de dependências](evidencias/dependencias-vscode-revisao.json), [plano dos três arquivos públicos](../packages/final-external-plan.json), [VS Code opcional](../packages/optional-vscode-plan.json). Catálogo público: 44 Ubuntu + Node + TypeScript = **46 itens**; catálogo histórico de 47 preservado.

## Personalização preparada, ainda não aplicada

[overlay/final-candidate](../overlay/final-candidate/) contém identidade vetorial original, wallpaper, menu XFCE por categorias, inicialização de preferências apenas para novos usuários e entradas DevLite Control/VS Code opcional. SVGs são locais, sem referências externas. A inicialização respeita configurações do usuário, detecta monitor dinamicamente, mantém Greybird/ícones já disponíveis e desativa composição para economizar recursos. Mecanismo XFCE baseado no [xfconf oficial](https://docs.xfce.org/xfce/xfconf/start); estrutura real da imagem foi consultada sem montagem.

DevLite Control tem consulta de serviços sem privilégios e helper preparado para ações explícitas Apache/MariaDB/Docker. O helper requer autenticação administrativa via polkit, identidade DevLite e lista fixa de comandos; não habilita serviços no boot. Após ação, restaura máscaras e trata falha de ativação. Testado com mocks, **não executado como root nem aplicado à imagem**. A autenticação e o funcionamento real dos serviços ainda exigem testes no guest.

O [plano de branding](../config/final-branding-plan.json) fixa hashes, destinos, modos e UID/GID para a aplicação futura. Preparação de arquivos não equivale a instalação. Verificar licença/avisos dos componentes antes da publicação; não alterar recibos históricos.

## Pipeline final e recursos

[Plano executável como dados](../config/final-release-plan.json): todas as permissões permanecem false. Reutilizar as imagens Base/Live aceitas como fontes imutáveis, personalizar cópias descartáveis e só publicar após auditoria.

Node/TypeScript serão prefixos versionados em /opt/devlite, separados do inventário dpkg e com licenças preservadas. Preparados verificadores locais de hashes/cache e inspeção de tar sem extração/execução, com rejeição de travessia, links perigosos, devices, setuid e excesso de tamanho. Não executar lifecycle scripts durante aquisição.

**Pendência de código real:** o adaptador de aplicação dos prefixos/overlay e o perfil público de construção precisam ser concluídos após inspeção dos arquivos reais. O executor Ubuntu existente continua selado e não será enfraquecido para aceitar programas externos. Publicar manifesto de proveniência separado dos pacotes dpkg.

A aplicação futura deve reconciliar Base e visão Live completas, recriar o delta e whiteouts, preservar permissões/xattrs/instalador, atualizar metadados e provar equivalência antes da ISO. Preservar BIOS/UEFI e imagem EFI anexada com o mecanismo já validado; não tratar os dois SquashFS como raízes independentes.

Orçamento conservador: até 512 MiB adicionais por visão, 11 GiB de cópias descartáveis e 56 GiB de margem de empacotamento; estimativa sequencial de 67 GiB, recomendação de **70 GiB livres**. Recalcular os guards com tamanhos reais. O mínimo existente de 56 GiB não foi reduzido. RAM 2,5 GiB, swap 1 GiB, uma CPU, 128 tarefas, compressão com um processo e 256 MiB; sem compilar Node no servidor. Imagens ext4 já são esparsas: tamanho lógico não representa espaço recuperável.

## Menor caminho para liberar

1. Autorizar limpeza dos caminhos exatos escolhidos, após conferências do plano; medir espaço. A lista completa pode evitar expansão do disco.
2. Autorizar aquisição dos três arquivos Node/TypeScript; verificar bytes, inspecionar e concluir adaptador/perfil público com novos testes e contrato selado.
3. Autorizar uma operação isolada claramente delimitada nas cópias Base/Live, com comandos e hashes apresentados previamente. Aplicar programas e overlay, reconciliar delta, auditar instalador/dpkg e serviços.
4. Autorizar geração de candidato público e reprodução; preservar a ISO experimental principal.
5. Testar candidato em BIOS e UEFI: Live, instalação em disco descartável, login, programas, Control/polkit, configurações e reboot sem ISO. Corrigir e repetir quando necessário.
6. Publicar somente o mesmo hash aprovado, acompanhado de checksums, proveniência, avisos/licenças e documentação.

As aprovações de limpeza, programas, operações privilegiadas, ISO e laboratório não foram inferidas da autorização de auditoria. Nenhuma etapa prática pendente está declarada aprovada.
