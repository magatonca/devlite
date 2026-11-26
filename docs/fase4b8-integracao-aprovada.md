# Fase 4B.8 — integração aprovada

17/11/2026. **Camadas integradas e verificadas; nenhuma ISO nova gerada.**

Job: `/home/magaton/DevLite-OS/work/release-63m6oz2_`. Contrato: `bc32e0ce9fb1a95d4b0170c1130f46ec523ddee0871b9fd3915e8f126a91d19d`. Recibo root-owned: [layers-ready.json](../work/release-63m6oz2_/layers-ready.json), UID 0, modo 0444.

A unidade devlite-pack-63m6oz2_ terminou com retorno **0**, após 1h06min05s. Pico contabilizado 2,5 GiB RAM; swap zero. A lentidão de I/O foi registrada por leitura dos indicadores PSI, sem mudar o host. Os packs existentes foram reaproveitados: nenhuma instalação, extração ou compressão repetida e nenhum artefato removido.

## Provas executadas

- Hashes das imagens aceitas e dos SquashFS existentes conferidos.
- Inventários completos Base/Live e lock de versões compatíveis.
- Composição lógica da receita; comparação integral do SquashFS Base (113.885 caminhos) e delta (70.459 caminhos) com conteúdo, UID/GID, modos, mtimes, xattrs, hardlinks e devices esperados.
- Composição real pelo kernel via OverlayFS somente leitura: 176.562 caminhos reproduzem a visão Live limpa.
- Leitura de xattrs estrita na Base. No delta sem tabela, ausência comprovada pelo superbloco e inventário esperado vazio; erros de acesso/I/O e atributos esperados continuam bloqueantes.
- Manifests regenerados, preservando exatamente os registros Snap nome/canal/revisão, inclusive Desktop Bootstrap. 1.393 pacotes APT na Base, 1.534 na Live e três Snap preservados.
- Tamanhos e catálogo fsimage-layered atualizados; fonte instalada permanece minimal.squashfs. Dez payloads publicados e hashes conferidos novamente como magaton pelo validador usado pela geração da ISO.

A prova de ida/volta desta retomada é a leitura integral dos SquashFS montados RO comparada às imagens instaladas/receita; não se declara nova reextração. Round-trips por reextração ocorreram na tentativa anterior; os arquivos preservados foram revalidados diretamente agora. A composição no kernel não equivale a boot ou instalação do sistema em VM.

## Arquivos publicados

Diretório: `/home/magaton/DevLite-OS/work/release-63m6oz2_/published-casper`.

| Camada | Bytes comprimidos | SHA-256 |
|---|---:|---|
| minimal.squashfs | 1040076800 | `d33c784d13ea16f99a6e386ffde7bc76fc508806e19a036c10b96ab7ca2f923f` |
| minimal.live.squashfs | 1303134208 | `fae422b8d9dfc13b354947aee23f5088220dd3f843de29b30a92cc7a86c6eee5` |

Metadados: minimal.manifest, minimal.live.manifest, filesystem.manifest, devlite-base.manifest.full, minimal.size, minimal.live.size, filesystem.size e install-sources.yaml. A etapa não alterou kernel, initrd, GRUB ou EFI; a preservação dentro da próxima ISO ainda deverá ser verificada pelo construtor.

## Host, testes e evidências

Hashes críticos do host iguais ao checkpoint, unidade inativa, sem mounts ou loops residuais. Gate de integração restaurado false; instalação e ISO bloqueadas. ISO original, ISOs experimentais anteriores, par ext4 aceito, cache dos 243 debs, contratos e evidências preservados. Nenhum commit.

191 testes passaram novamente após a integração. O controlador não privilegiado da geração seguinte acrescentou seis testes com mocks: **197 testes aprovados** na suíte completa, sem gerar ISO. Verificação do projeto: zero erros; git diff --check aprovado. Relatórios: reports/testes-apos-integracao-aprovada.txt e reports/testes-controlador-iso.txt.

Evidências: [auditoria e recibo validado](evidencias/integracao-manifest-execucao.json), [relatório root e journal](evidencias/integracao-63m6oz2-aprovada.json), [preflight de metadados e espaço](evidencias/preflight-geracao-iso.json), [pressão de I/O](evidencias/pressao-io-integracao-manifest.json).

Arquivos desta rodada: recibos/payloads no job; scripts/gerar-isos-controladas.py e tests/test_iso_control.py; modelo de aceitação e comandos de programas no job; esta documentação, proposta de ISO e relatório consolidado. O código congelado usado na integração não foi alterado depois da preparação do contrato.

## Pendências

Gerar ISO Ubuntu experimental e auditar sua estrutura; construir novamente para verificar identidade bit a bit; executar BIOS/UEFI, instalação, XFCE, programas e persistência em VMs autorizadas. Node.js LTS, TypeScript e VS Code permanecem fora do cache Ubuntu; não declarar edição completa pronta. Não há caminho, tamanho ou SHA-256 de uma ISO nova porque ela ainda não foi gerada.

[Próxima operação proposta, sem sudo: duas construções e validação](fase4b8-geracao-iso-proposta.md).
