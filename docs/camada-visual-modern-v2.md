# Camada visual Modern v2

Esta versão prepara o padrão estático do wallpaper XFCE sem alterar ou
recompactar as camadas SquashFS aprovadas nem a ISO de referência.

## Camadas e compatibilidade

- O instalador mantém `type: fsimage-layered` e o identificador
  `xubuntu-desktop-minimal`. O nome e a descrição visíveis passam a DevLite OS
  1.0; `path` aponta para `minimal.visual.squashfs`.
- A cadeia do instalador é `minimal.squashfs` + `minimal.visual.squashfs`.
  Curtin deriva essa cadeia a partir dos prefixos separados por pontos e monta
  as camadas superiores antes da base.
- O boot Live passa `layerfs-path=minimal.visual.live.squashfs`. Casper deriva
  `minimal.squashfs`, `minimal.visual.squashfs` e
  `minimal.visual.live.squashfs`, mantendo a camada Live no topo.
- `minimal.visual.squashfs` contém somente o canal estático XFCE. O wallpaper
  SVG já existe no Base. O Live SquashFS aprovado é reutilizado byte a byte sob
  o nome da nova cadeia; a cópia antiga `minimal.live.squashfs` é removida
  apenas da árvore ISO candidata.

As convenções foram conferidas no código de extração do
[Curtin](https://github.com/canonical/curtin/blob/b7cc82a3bcc8c855e80bc62db95a1c9928f3e961/curtin/commands/extract.py)
e no initrd Casper da ISO de origem. O preflight também exige que o canal
XFCE não exista na camada Live, evitando que ela o sobrescreva.

## Integridade e execução

O gerador cria uma nova camada separada com `mksquashfs`, valida formato,
proprietário, modo e round-trip com `unsquashfs`, atualiza os tamanhos e os
manifestos `md5sum.txt` e `casper/SHA256SUMS`, e vincula os insumos ao contrato
`modern-candidate-iso-v2`.
O contrato ISO anterior permanece selado e não é reutilizado. Nenhuma camada,
imagem, relatório ou contrato aprovado é atualizado no lugar.

## Proveniência do pack histórico

O contrato do pack aprovado registra o hash histórico de
`pipeline/devlite/modern_identity.py`, mas esse módulo não é importado nem
executado pelo worker que produz as camadas Base/Live. Ele é usado pelo
gerador da ISO para personalizar títulos GRUB e selecionar a cadeia Live.
Assim, a alteração visual não muda o conteúdo nem a proveniência de nenhuma
camada já produzida.

A leitura de um pack concluído para a montagem ISO valida separadamente o hash
do contrato aprovado, as referências e recibos selados, o relatório de sucesso
e os hashes dos SquashFS. Ela valida também a estrutura do manifesto histórico
de código, sem comparar esses hashes antigos com os arquivos atuais. A
execução de um worker de pack continua usando `read_job()`, que exige a
correspondência integral do código atual com seu contrato. O contrato ISO v2
registra e valida os hashes atuais do código de montagem, inclusive
`modern_identity.py`.

Não foi encontrada cópia histórica do módulo no workspace nem no histórico Git;
ela não é necessária para verificar as camadas, pois o módulo não participou de
sua produção. O hash antigo continua preservado no contrato imutável do pack.

Os testes usam camadas SquashFS descartáveis para verificar a transformação do
catálogo, os quatro monitores, a resolução das cadeias Installer/Live, a
ausência de overrides no delta Live e a preservação da camada Base. A camada
visual derivada do pack aprovado e a montagem ISO não são executadas.
