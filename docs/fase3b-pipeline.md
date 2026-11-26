# Fase 3B — pipeline experimental de reconstrução

A solicitação do usuário autoriza a primeira reconstrução sem alterações de pacotes, desktop ou configurações internas, e adia expressamente os testes manuais da Fase 3A. Essa decisão substitui a porta de testes anterior para este experimento. Não significa boot ou instalação aprovados. Nenhuma VM será iniciada pelo pipeline.

A mensagem de requisitos terminou em “Não apagar”. Foi adotada a interpretação conservadora: nenhuma rotina apaga arquivos, nem em sucesso ou falha. Áreas de trabalho e saídas parciais ficam preservadas. Não foi implementada remoção automática ou comando de limpeza destrutiva.

## Uso

Como magaton, na raiz do projeto:

```sh
python3 scripts/construir-iso.py
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 scripts/construir-iso.py --build
```

Sem `--build`, apenas verifica usuário, dependências, entrada, diretórios e espaço. Cada construção recebe diretórios novos `work/phase3b-*` e `artifacts/phase3b-*`. Nenhuma entrada ou saída existente é sobrescrita. Não executar como root. Não há downloads, instalações de pacotes ou necessidade de sudo.

Dependências já disponíveis: Python 3.12, xorriso, gpgv e unsquashfs. A consulta `unsquashfs -version` admite seu retorno 1 e exige a identificação de versão; as demais operações exigem sucesso.

## Módulos e contratos

| Módulo | Responsabilidade |
|---|---|
| scripts/construir-iso.py | interface explícita, preflight e códigos de saída |
| pipeline/devlite/runtime.py | comandos sem shell, logs, diretórios exclusivos e preservação de evidências |
| pipeline/devlite/structure.py | PVD ISO9660, boot El Torito, MBR/GPT e hash da EFI anexada |
| pipeline/devlite/validation.py | manifests, inventários, metadados e comparação do conteúdo |
| pipeline/devlite/build.py | autenticação, inspeção, extração, reconstrução, validação e promoção |

A entrada é fixada na ISO oficial autenticada em `sources/`. O preflight exige execução como magaton, arquivos regulares e diretórios sem symlink, ferramentas presentes e pelo menos quatro vezes o tamanho da ISO mais 10 GiB livres. Não altera RAM, swap, permissões, partições ou módulos.

## Estratégia de reconstrução

1. Revalidar GPG e SHA-256 com o validador da Fase 2. Falha interrompe antes da extração.
2. Detectar PVD, volume, timestamp, imagens El Torito BIOS/UEFI e partição EFI GPT; conferir correspondência de offsets e tamanhos. Layout desconhecido é recusado em vez de reconstruído por suposição.
3. Extrair a árvore inteira em pasta exclusiva para auditoria; identificar exatamente as duas SquashFS e catálogo `fsimage-layered`. Confirmar manifests, kernel, initrd, GRUB, EFI e Desktop Bootstrap. Nenhum arquivo extraído é executado.
4. Carregar a árvore **da ISO original** no xorriso e escrever outra imagem, com entrada e saída distintas. A extração serve à auditoria; não é reimportada, evitando trocar proprietários e permissões da árvore ISO pelos do usuário construtor.
5. Usar `-assess_indev_features replay` e `-boot_image any replay` para preservar características reconhecidas do filesystem e boot, inclusive EFI anexada. Não executar como shell o relatório de comandos do xorriso e não fixar offsets da ISO original na saída.
6. Reabrir e extrair a saída para comparar conteúdo, metadados, camadas e manifests. Comparar a EFI anexada por hash usando seus offsets detectados independentemente em cada ISO. Conferir novamente SHA-256 da original.
7. Somente após validações, renomear a saída `.iso.partial` para `.iso` e gerar SHA256SUMS e build-report.json. Em falha, o resultado permanece parcial; não há promoção ou exclusão.

O modo replay e os campos de endereço da imagem BIOS são documentados no [manual xorriso do Ubuntu](https://manpages.ubuntu.com/manpages/noble/man1/xorriso.1.html). A receita usa os mecanismos reconhecidos pelo próprio xorriso, incluindo ajuste de endereços na reconstrução.

## O que deve permanecer idêntico

Camadas `minimal.squashfs` e `minimal.live.squashfs`, kernel, initrd, pacotes, instalador, snaps e seus manifests/assinaturas são copiados byte a byte. Não há descompactação/recompressão de SquashFS, chroot, customização de arquivos internos ou assinatura DevLite dos componentes originais. O rótulo interno continua Xubuntu; “DevLite experimental” identifica apenas o artefato e seus relatórios nesta fase.

A árvore extraída é comparada por caminho, tipo, destino de symlink, modo, tamanho e SHA-256. O inventário ISO também verifica permissões, UID/GID, tamanhos e timestamps exibidos por xorriso, exceto metadados regenerados do catálogo de boot. Em SquashFS, metadados internos ficam preservados por identidade binária.

Exceções estritas de relocação: `/boot.catalog` é regenerado e validado pela estrutura de boot; em `/boot/grub/i386-pc/eltorito.img`, apenas bytes 8–63 (boot-info-table) e 2548–2555 (endereço GRUB2) podem mudar. Tipo, modo e tamanho dessas imagens também devem conferir. Mudanças fora dessas regiões são falha. O md5sum.txt original não lista esses arquivos regeneráveis; todos os seus membros são verificados, assim como SHA256SUMS e assinatura de casper.

## Reprodutibilidade, recursos e limites

O ambiente dos comandos fixa LC_ALL=C, TZ=UTC e SOURCE_DATE_EPOCH no timestamp original. xorriso ignora arquivos de configuração externos via `-no_rc`; versões, argumentos, inventários e parâmetros de boot ficam registrados. Datas de volume permanecem fixadas ao valor original. Não se promete que o hash da nova ISO seja igual ao da oficial: organização e estruturas ISO podem ser regeneradas.

A reprodução da receita é automatizada. Igualdade binária entre duas execuções deve ser medida, não inferida apenas dos controles de data. Após uma construção validada, executar:

```sh
python3 scripts/construir-iso.py --verify-reproducibility artifacts/PASTA_DA_EXECUCAO/build-report.json
```

Esse modo reautentica a fonte, confere o hash do primeiro artefato, gera outra ISO em workspace exclusivo e compara os hashes. Uma igualdade prova que a segunda imagem compartilha as validações estruturais da primeira; não é necessário extrair tudo de novo. A imagem de reprodução e seus logs são preservados. A prova `reproducibility.json` fica ao lado do artefato, sem alterar o relatório original. Exige espaço adicional e não sobrescreve prova existente. O pipeline não usa compressão paralela, não extrai rootfs e executa etapas sequencialmente, adequando-se aos 3,8 GiB de RAM. Prevê cerca de 9–13 GiB adicionais para duas árvores de auditoria e a saída, além das áreas anteriores. Nenhum arquivo temporário é removido; novas execuções consomem mais disco.

Logs de cada comando e argumentos JSON ficam em `work/phase3b-*/logs`. O relatório permanece em andamento durante as operações, muda para falhou/interrompido em erro e para validado_estruturalmente após sucesso. Ctrl+C preserva os arquivos. Não há montagens ou serviços a desmontar/parar; a finalização segura consiste em fechar subprocessos/arquivos e manter evidências. Em interrupção externa abrupta, um relatório pode permanecer em andamento e requer revisão manual; não retomar automaticamente.

## Testes e condição da entrega

Testes automatizados exercitam boot BIOS/UEFI e correspondência GPT, rejeição de caminhos/saídas inseguros, manifests adulterados, limites de leitura, mudanças fora dos campos de boot, execução como root e preservação de logs em falha. Casos usam amostras pequenas; não constroem ISO grande nem iniciam VMs.

Uma saída validada estruturalmente continua experimental. Boot BIOS/UEFI, Secure Boot e instalação real estão adiados, não aprovados. A próxima validação manual segue [Fase 3A](fase3a-testes-iso.md), primeiro com a original e depois com a reconstruída, registrando o hash de cada uma. O validador de relatório da 3A fixa o hash original e não deve ser usado para declarar a reconstruída aprovada sem adaptação explícita.

## Resultado da execução

Primeira execução validada em 16/11/2026:

- ISO: `artifacts/phase3b-9adp_k5i/devlite-os-1.0-experimental-rebuild.iso`.
- Tamanho: 3.193.634.816 bytes (aproximadamente 2,97 GiB).
- SHA-256: `2e3a6eecf59d535a4825ff41655c542f6ef2017ccce9a9672891ace2672f2bc7`.
- Manifest MD5: 191 membros conferidos; SHA-256 interno: duas camadas conferidas; assinatura interna GPG válida.
- Metadados: 923 nós conferidos; somente boot.catalog e campos de relocação previstos da imagem BIOS diferiram.
- EFI anexada, código MBR e parâmetros de carga BIOS/UEFI conferidos. A ISO original manteve seu SHA-256 autenticado.
- Relatório completo e SHA256SUMS ao lado da ISO; workspace `work/phase3b-frka50es` preservado.
- 29 testes automatizados aprovados. Uma tentativa inicial interrompida na consulta de versão do unsquashfs permanece preservada em `work/phase3b-pol8ebqx`; não chegou a gerar uma ISO.

Resumo versionável em [evidencias/reconstrucao-experimental.json](evidencias/reconstrucao-experimental.json). A prova binária adicional foi concluída: a segunda geração tem exatamente o mesmo SHA-256 e tamanho da primeira. Prova em `artifacts/phase3b-9adp_k5i/reproducibility.json`; segunda imagem e logs preservados em `work/phase3b-reproduction-jvzarclv`. A ISO original foi novamente autenticada e seu hash final conferiu. O relatório inicial descreve o estado anterior a esse ensaio; a prova separada registra sua conclusão.

Restam aproximadamente 67 GiB livres. Nenhum pacote foi instalado, nenhuma VM foi criada/iniciada, nenhum arquivo interno da distribuição foi personalizado e nenhum commit foi criado. As áreas de trabalho foram preservadas.
