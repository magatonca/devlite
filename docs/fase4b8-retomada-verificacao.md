> Atualização: retomada executada e encerrada em quarentena por delta sem tabela de xattrs. Base SquashFS aprovada; correção preparada com 188 testes. [Resultado, causa e novo comando para aprovação](fase4b8-correcao-xattrs.md). Nenhuma ISO nova. O conteúdo abaixo preserva o histórico.

# Retomada da auditoria das camadas — Fase 4B.8

17/11/2026. **Preparada, não executada. Requer nova autorização privilegiada. Não gera ISO.**

## Resultado da execução anterior

A unidade devlite-pack-ku78mn3t atingiu RuntimeMaxSec=7200 às 15:30:49 UTC (12:30:49 de São Paulo). O relatório privado ficou em quarentena com errno 95 (Operation not supported) na visão mounted-merged. Os logs confirmam duas compressões e reextrações e as montagens RO das duas imagens SquashFS e do OverlayFS. O código só chega à composição após comparar integralmente cada reextração; porém não publicou layers-ready.json. Portanto a integração **não está aprovada**. A origem precisa do erro de metadados no instante do timeout permanece sem confirmação; não se presumiu ausência de xattrs nem se suprimiu a verificação.

Base/Live instaladas e auditadas continuam aceitas no executor phase4b3-wnej6dpv. Nenhuma reinstalação ou novo probe é necessário. Host: hashes críticos iguais ao checkpoint da instalação, sem mounts do projeto e sem loops residuais; gates false. Nenhum arquivo foi excluído nesta retomada.

## Correções e estratégia

- compose usa índice de filhos e percorre somente subárvores efetivamente removidas. Testes com operações sobrepostas comparam o resultado com o algoritmo anterior; teste de 6.000 substituições limita a contagem de varreduras, sem depender da velocidade da máquina.
- Novo backend release_resume valida hashes e propriedade dos packs em quarentena e do relatório, vínculo ao executor aceito e ao lock de versões. Recalcula inventários Base/Live por montagens ext4 RO,noload e a receita do delta.
- Monta os dois SquashFS existentes somente leitura e compara **todos** os bytes, UID/GID, modos, mtimes, xattrs, links e devices com a Base e o delta esperado, incluindo whiteouts. Essa é uma nova verificação direta da representação consumida pelo kernel; não afirma executar outra reextração.
- Confere ainda a visão OverlayFS RO contra o inventário completo Live. Só após todas as provas copia os packs para published-casper, regenera manifests/tamanhos/catálogo e emite recibo root-owned. Divergências ou erros de leitura bloqueiam a publicação.
- Não executa APT/dpkg, extração, compressão, limpeza, instalações, rede ou criação de ISO. Não reduz o guard de 56 GiB da instalação nem o guard da reconstrução integral. A retomada é outro caminho, sem cópias descomprimidas: exige tamanho dos packs + **10 GiB de reserva**.
- O CLI trata TERM/HUP para registrar quarentena. O backend grava traceback no relatório de falha para diagnosticar a operação exata; não ignora errno 95.

## Entradas preservadas

| Arquivo em work/release-ku78mn3t/pack-attempt/packed | Bytes | SHA-256 |
|---|---:|---|
| minimal.squashfs | 1040076800 | `d33c784d13ea16f99a6e386ffde7bc76fc508806e19a036c10b96ab7ca2f923f` |
| minimal.live.squashfs | 1303134208 | `fae422b8d9dfc13b354947aee23f5088220dd3f843de29b30a92cc7a86c6eee5` |

Os packs acima são **candidatos em quarentena**, não produtos aprovados para gerar ISO. São preservados junto com as imagens ext4 aceitas, reextrações anteriores, cache e evidências.

## Verificações e orçamento

**178 testes aprovados**, incluindo fixtures do fluxo de publicação e da quarentena por divergência na composição. Resultado: reports/testes-retomada-integracao.txt. São testes de código; não substituem a auditoria privilegiada proposta nem boot/instalação real. Cache novamente verificado: 243 arquivos. Contrato e código do executor aceito conferidos, sem alterações. git diff --check aprovado.

Livre: 43.37 GiB. Margem exigida para esta auditoria/publicação: 12.18 GiB. Publicação pode acrescentar 2.18 GiB; inventários/logs têm a reserva de 10 GiB. Nenhuma nova ext4 será criada.

## Comando exato proposto

Novo job: `/home/magaton/DevLite-OS/work/release-yqlso8i2`.
Contrato: `532cd95a7fb3635101da9b6ccdf95e18928ca134d7815506b271e96963ca094f`.

```sh
sudo systemd-run --unit=devlite-pack-yqlso8i2 --wait --pipe --collect --property=MemoryMax=2684354560 --property=MemorySwapMax=1073741824 --property=CPUQuota=100% --property=TasksMax=128 --property=RuntimeMaxSec=10800 --property=KillMode=control-group --property=OOMPolicy=kill unshare --mount --propagation private /usr/bin/python3 /home/magaton/DevLite-OS/scripts/integrar-release-root.py --job /home/magaton/DevLite-OS/work/release-yqlso8i2 --approval-sha256 532cd95a7fb3635101da9b6ccdf95e18928ca134d7815506b271e96963ca094f
```

O sudo é necessário para montagens loop/SquashFS/ext4/OverlayFS e namespace mount privado; os inputs ficam RO e não se criam partições. Limites: 2,5 GiB RAM, 1 GiB swap, uma CPU e 128 tarefas. O timeout proposto passa explicitamente para **3 horas**, para comportar a leitura integral sob limitação de CPU/memória. Nenhuma configuração global do systemd será modificada.

Após autorização, o controlador executado como magaton habilitará apenas integracao_camadas_autorizada e restaurará false em finally, inclusive em falha. Se houver interrupção, o único comando de parada previsto é `sudo systemctl stop devlite-pack-yqlso8i2.service`. Todos os demais gates permanecem false. O comando acima e essa parada delimitada ainda **não foram executados**.

Riscos: pressão de I/O e memória; timeout ou erro de xattrs pode voltar a colocar a tentativa em quarentena. O backend não publica recibo antes da comparação integral. Não há promessa de boot, instalação ou persistência pós-instalação. ISO, testes em VMs, segunda construção reproduzível e ferramentas externas (Node.js LTS, TypeScript, VS Code) continuam pendentes.
