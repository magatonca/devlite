# Recuperação de espaço — auditoria e plano de limpeza

Auditoria de 17/11/2026 (America/Sao_Paulo). **Limpeza autorizada e concluída: somente os três arquivos listados foram removidos.** O inventário abaixo é o registro anterior à limpeza. Leituras dos diretórios privados foram realizadas com privilégios apenas para a auditoria; documentos foram gravados como magaton.

## Recomendação mínima

A medição usa blocos realmente alocados (`st_blocks × 512`), não o tamanho lógico de arquivos esparsos. Cada ext4 tem tamanho lógico de 12 GiB, mas ocupa aproximadamente 2,31 GiB reais. Cada candidato tem um único hardlink. O plano exclui somente três arquivos regulares, sem remover diretórios, fontes ou outros membros dos jobs.

| Arquivo completo | Espaço recuperável (GiB) | Justificativa | Risco |
|---|---:|---|---|
| `/home/magaton/DevLite-OS/work/phase4b3-1ibq_emz/probe-attempt/base.ext4` | 2.307 | imagem descartável de probe concluído; preservar atestado, logs, recibos e hashes | Perda da inspeção binária desta cópia; logs/hashes preservados. |
| `/home/magaton/DevLite-OS/work/phase4b3-bklz27i4/probe-attempt/base.ext4` | 2.307 | imagem descartável de probe concluído; preservar atestado, logs, recibos e hashes | Perda da inspeção binária desta cópia; logs/hashes preservados. |
| `/home/magaton/DevLite-OS/work/phase4b3-1ibq_emz/attempt/base.ext4` | 2.310 | imagem da primeira instalação abortada; preservar evidências e imagem da falha mais recente | Perda da inspeção binária desta cópia; logs/hashes preservados. |

Livre medido: **53.94 GiB**. Recuperação estimada: **6.92 GiB** (7,434,719,232 bytes alocados). Livre projetado: **60.86 GiB**. A projeção depende de não haver outros consumidores durante a operação; confirmar espaço real após unlink. O mínimo do probe continua 56 GiB e a meta da limpeza é pelo menos 60 GiB.

## Segurança e recuperação

Os dois probes estão em estado terminal probe_passed. A primeira instalação está quarantined, sem erro no guard do host; não há par instalado aceito. Nenhum candidato está aberto, montado ou associado a loop na auditoria. Os atestados, recibos, journals, logs, inventários e hashes continuam nos jobs originais. A exclusão das imagens remove a possibilidade de repetir a inspeção dos mesmos bytes; sua geração pode ser refeita das entradas preservadas, sem prometer reprodução bit a bit de ext4 com UUID/metadados variáveis.

Nenhuma tentativa será retomada in-place. O executor bloqueia tentativas existentes e o pack exige um par Base/Live accepted, que ainda não existe. O executor verifica atestados JSON root-owned, mas não usa a imagem ext4 do probe como input da instalação. Os probes antigos são evidências históricas; a versão atual corrigida exige seu próprio probe. A imagem da falha mais recente permanece em `work/phase4b3-bklz27i4/attempt/base.ext4` para investigação.

Preservados: código/Git; ISO original autenticada; ISOs experimentais 3B e 4B.1; entradas SquashFS 4B.1; cache único dos 243 debs e seus hardlinks; manifestos e assinaturas; relatórios/evidências; imagens e camadas restantes; contrato/cache da próxima tentativa `work/release-qqkumja7` e executor `work/phase4b3-nuuyxpa1`. Não se alterarão limites, partições, LVM ou programas do host.

## Comandos propostos — NÃO executados

Os diretórios pais são root 0700; somente a remoção desses arquivos exigirá sudo. Antes de remover: conferir novamente caminhos/ancestrais sem symlink, arquivos regulares, UID, device/inode/tamanho/links registrados na evidência, estados terminais, ausência de accepted-pair, mounts/loops e arquivos abertos. Se qualquer condição divergir, interromper sem substituir candidatos. Não usar rm -rf, globs, limpeza de diretórios ou deleção recursiva.

```sh
sudo /usr/bin/unlink -- /home/magaton/DevLite-OS/work/phase4b3-1ibq_emz/probe-attempt/base.ext4
sudo /usr/bin/unlink -- /home/magaton/DevLite-OS/work/phase4b3-bklz27i4/probe-attempt/base.ext4
sudo /usr/bin/unlink -- /home/magaton/DevLite-OS/work/phase4b3-1ibq_emz/attempt/base.ext4
```

Após autorização e remoção: confirmar pelo menos 60 GiB livres, preservar o registro de quais arquivos foram removidos, revalidar contrato/cache e executar somente testes necessários. Preparar/revisar os comandos atuais de probe/instalação e solicitar a autorização privilegiada separada pedida pelo usuário. Não gerar ISO nem instalar pacotes automaticamente com a autorização de limpeza.

[Evidência com caminhos, inodes, tamanhos e projeção](evidencias/auditoria-recuperacao-espaco.json). Nenhuma permissão de probe, instalação, integração ou ISO foi habilitada nesta auditoria.

## Maiores consumidores identificados

A varredura contou arquivos regulares e deduplicou hardlinks dentro de cada pasta. Hardlinks entre pastas (como cache .deb) podem aparecer em mais de uma linha; não somar estas linhas como uso físico único. O plano de remoção usa somente imagens com nlink=1 e contabilização individual.

| Caminho completo | GiB alocados em arquivos | Avaliação |
|---|---:|---|
| `/home/magaton/DevLite-OS/work/phase4b1-dhzezpnz` | 18.06 | Extratos/rootfs, camadas e árvores ISO da personalização mínima; preservar entradas usadas pelo pipeline. |
| `/home/magaton/DevLite-OS/work/phase4b3-1ibq_emz` | 9.16 | Probe e primeira instalação em quarentena; remover somente duas imagens selecionadas. |
| `/home/magaton/DevLite-OS/work/phase4b3-bklz27i4` | 9.16 | Segundo probe e falha mais recente; remover somente a imagem do probe selecionada. |
| `/home/magaton/DevLite-OS/work/phase3b-frka50es` | 5.94 | Árvores intermediárias source/result da reconstrução; regeneráveis, fora da limpeza mínima. |
| `/home/magaton/DevLite-OS/work/phase3b-reproduction-jvzarclv` | 2.97 | Segunda ISO usada para provar reprodução; fora da limpeza mínima. |
| `/home/magaton/DevLite-OS/artifacts/phase4b1-lgpa3zc7` | 2.97 | ISO personalizada mínima de referência; preservar. |
| `/home/magaton/DevLite-OS/artifacts/phase3b-9adp_k5i` | 2.97 | ISO experimental 3B; preservar. |
| `/home/magaton/DevLite-OS/sources/xubuntu-24.04.5-minimal-amd64.iso` | 2.97 | ISO original autenticada; preservar. |
| `/home/magaton/DevLite-OS/work/phase2` | 2.11 | Camadas/inspeções da ISO oficial; regeneráveis, fora da limpeza mínima. |
| `/home/magaton/DevLite-OS/work/phase4b5-g78yd2oc` | 0.53 | Cache de pacotes e metadados autenticados; preservar. |

## Duplicatas e intermediários fora da limpeza proposta

Há cópias independentes das camadas SquashFS em original-casper/source-iso-tree e rebuilt-casper/result-iso-tree na Fase 4B.1, nas árvores source/result da Fase 3B, e em layers de cada tentativa/probe. As camadas de cada job foram autenticadas pelos contratos durante suas execuções; esta auditoria não recalculou SHA-256 de todos esses arquivos. Preservar as entradas da próxima tentativa evita reextração/reconstrução desnecessária. As cópias em jobs antigos são regeneráveis, mas nenhuma foi incluída na solicitação.

A cópia work/phase3b-reproduction-jvzarclv/reproduced.iso tem 3.193.634.816 bytes lógicos (aproximadamente 2,97 GiB alocados), mesmo tamanho da ISO 3B preservada em artifacts. O registro reproducibility.json preservado informa identidade binária e SHA-256 2e3a6eecf59d535a4825ff41655c542f6ef2017ccce9a9672891ace2672f2bc7 para ambas; esta auditoria não recalculou esse hash, portanto revalidá-lo antes de uma futura remoção por duplicidade. Não é necessária à limpeza mínima e será preservada nesta operação.

Não há instalação aceita a recuperar. Todas as evidências e camadas permanecem disponíveis, e a imagem da falha mais recente será mantida. Os manifests registrando imagens removidas devem continuar históricos: marcar a remoção autorizada em um registro novo, sem alterar os hashes antigos nem alegar que as imagens continuam presentes.

## Resultado da limpeza autorizada

Usuário autorizou os três arquivos. Após revalidar caminhos, UID/inode/device/tamanho/links, estados terminais e ausência de mounts/loops/arquivos abertos, foram executados somente os três unlink previstos. Recuperação real: **6,92 GiB**; espaço livre após operação: **60,86 GiB**, meta atingida. Diretórios, fontes, evidências e imagem da falha mais recente foram preservados. [Registro da remoção](evidencias/limpeza-autorizada.json). Os hashes/atestados anteriores continuam históricos, mas suas três imagens não estão mais presentes; não se declara uma nova reprodução deles.

Após a limpeza, contratos/código/plano e ambos os caches de 243 arquivos passaram na revalidação. A suíte completa passou novamente em **162 testes**, sem instalação ou operação privilegiada de imagem. Probe/instalação da versão atual continuam pendentes de autorização específica. [Retomada preparada](evidencias/retomada-apos-limpeza.json). Nenhuma permissão foi habilitada.
