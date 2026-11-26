> Atualização: geração e reprodução autorizadas e concluídas com sucesso. [Artefatos, hashes e resultados](fase4b8-isos-geradas.md). O conteúdo abaixo preserva o plano aprovado.

# Proposta — primeira ISO Ubuntu experimental e reprodução

**Preparada; não executada. Requer autorização específica para gerar as ISOs.**

As camadas já possuem recibo root-owned válido, contrato conferido e todos os hashes publicados verificados. [Integração aprovada](fase4b8-integracao-aprovada.md).

## Comando exato, como magaton, sem sudo

```sh
env PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 /home/magaton/DevLite-OS/scripts/gerar-isos-controladas.py --job /home/magaton/DevLite-OS/work/release-63m6oz2_ --approval-sha256 bc32e0ce9fb1a95d4b0170c1130f46ec523ddee0871b9fd3915e8f126a91d19d --two-builds --execute-authorized
```

SHA-256 do controlador scripts/gerar-isos-controladas.py: `3b71fac66711c846327fc87996536c8c852f3a4d12d35586657b4f985a356bc8`. Contrato do pipeline permanece `bc32e0ce9fb1a95d4b0170c1130f46ec523ddee0871b9fd3915e8f126a91d19d`. A nova ferramenta chama apenas os backends congelados existentes; seus seis testes usam mocks e nenhuma ISO foi gerada por eles.

A execução habilitará somente iso_final_autorizada e restaurará false em finally. O controlador exige magaton e PYTHONHASHSEED=0, recusa outros gates ativos e registra execução/falhas em diretório novo iso-control-* dentro do job. A seed fixa a ordem de iteração no processo entre as duas construções. Não usa root, namespaces, mounts, chroot, APT/dpkg, rede ou instalação de pacotes. Não apaga arquivos existentes nem cria commits.

## Escopo delimitado da aprovação

1. Construir uma ISO a partir da ISO oficial autenticada e das camadas publicadas, em diretório novo artifacts/release-*.
2. Auditar estrutura BIOS/UEFI híbrida, EFI anexada, UUID de volume, arquivos do instalador, árvore externa, metadados, checksums e proveniência GPG original. Só renomear .iso.partial para .iso após aprovação estrutural.
3. Construir novamente com as mesmas entradas seladas, preservando ambas as saídas, e exigir SHA-256 idêntico. O segundo comando é chamado pelo controlador usando exatamente o release-report.json retornado pela primeira construção, sem localizar arquivos por glob ou adivinhar diretórios.
4. Emitir relatórios, checksums e prova de reprodução. Se houver erro ou divergência, interromper e preservar os arquivos para diagnóstico, restaurando o gate false. Não declarar reprodução aprovada antes da comparação real.

O nome será devlite-os-1.0-ubuntu-experimental.iso em diretórios de saída distintos. O caminho completo, tamanho e SHA-256 só existirão depois da execução. A primeira ISO estruturalmente aprovada será preservada mesmo se a segunda falhar.

## Recursos

Livre medido: **41.18 GiB**. Guard existente por construção: **22.50 GiB**. Estimativa conservadora para duas saídas, suas árvores de auditoria e reserva final de 10 GiB: **36.57 GiB**; orçamento suficiente na medição atual. Cada construção revalida seu próprio guard; a proposta não reduz limites nem depende de limpeza automática.

A estimativa usa limite superior da ISO candidata = tamanho da ISO original + soma dos novos packs, sem descontar os packs substituídos. Por construção considera ISO candidata + árvore extraída oficial + árvore extraída candidata. A memória permanece limitada pelo ambiente; não há recompressão SquashFS nem VM neste comando. O ritmo de I/O atual pode prolongar a operação.

## Limites da entrega

Esta é a edição **ubuntu-experimental**, com pacotes Ubuntu e personalização básica. Node.js LTS, TypeScript e VS Code continuam pendentes. Validação estrutural/reprodutibilidade não aprovam boot, instalação ou persistência. O modelo BIOS/UEFI preparado está em work/release-63m6oz2_/acceptance-ubuntu-experimental.json, com todos os itens pendentes; o validador rejeitou corretamente o modelo vazio. O plano de laboratório existente permanece em fase3a-testes-iso.md. Nenhuma VM será criada ou iniciada nesta autorização.
