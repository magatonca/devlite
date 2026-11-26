# Proposta de limpeza — nenhuma exclusão executada

Valores em GiB de blocos alocados; caminhos completos. Os totais são estimativas, condicionadas à conferência de hardlinks, referências e duplicatas antes da autorização. Não remover diretórios pais.

| Caminho completo | GiB | Justificativa | Risco |
|---|---:|---|---|
| /home/magaton/DevLite-OS/work/release-63m6oz2_/iso-8szxc4eu/source-tree | 2.969 | Árvore externa de auditoria regenerável pelas ISOs preservadas; logs/relatórios fora do candidato | Perde a cópia extraída; reextrair sob autorização se necessária |
| /home/magaton/DevLite-OS/work/release-63m6oz2_/iso-8szxc4eu/result-tree | 3.301 | Árvore externa de auditoria regenerável pelas ISOs preservadas; logs/relatórios fora do candidato | Perde a cópia extraída; reextrair sob autorização se necessária |
| /home/magaton/DevLite-OS/work/release-63m6oz2_/iso-xoaxo4dp/source-tree | 2.969 | Árvore externa de auditoria regenerável pelas ISOs preservadas; logs/relatórios fora do candidato | Perde a cópia extraída; reextrair sob autorização se necessária |
| /home/magaton/DevLite-OS/work/release-63m6oz2_/iso-xoaxo4dp/result-tree | 3.301 | Árvore externa de auditoria regenerável pelas ISOs preservadas; logs/relatórios fora do candidato | Perde a cópia extraída; reextrair sob autorização se necessária |
| /home/magaton/DevLite-OS/work/phase3b-frka50es/source-tree | 2.969 | Árvore de auditoria antiga 3B, com ISOs/fontes e inventários preservados | Perde cópia extraída; confirmar que nenhum contrato ativo a usa |
| /home/magaton/DevLite-OS/work/phase3b-frka50es/result-tree | 2.969 | Árvore de auditoria antiga 3B, com ISOs/fontes e inventários preservados | Perde cópia extraída; confirmar que nenhum contrato ativo a usa |
| /home/magaton/DevLite-OS/work/phase3b-reproduction-jvzarclv/reproduced.iso | 2.974 | Reprodução histórica 3B; relatório de reprodução e ISO experimental 3B preservados | Remover somente após revalidar a igualdade por SHA-256 com a referência |
| /home/magaton/DevLite-OS/artifacts/release-22snj8_v/devlite-os-1.0-ubuntu-experimental.iso | 3.307 | Segunda ISO bit a bit idêntica; principal e prova de reprodução preservadas | Opcional: perde segunda cópia física; preservar se desejada para auditoria |
| /home/magaton/DevLite-OS/work/phase4b1-dhzezpnz/source-iso-tree | 2.969 | Extração histórica regenerável; ISOs e result-iso-tree preservados | Requer confirmar ausência de referências ativas e hardlinks externos antes de excluir |
| /home/magaton/DevLite-OS/work/phase4b1-dhzezpnz/base-root | 2.221 | Extração histórica regenerável; ISOs e result-iso-tree preservados | Requer confirmar ausência de referências ativas e hardlinks externos antes de excluir |
| /home/magaton/DevLite-OS/work/phase4b1-dhzezpnz/live-root | 1.928 | Extração histórica regenerável; ISOs e result-iso-tree preservados | Requer confirmar ausência de referências ativas e hardlinks externos antes de excluir |
| /home/magaton/DevLite-OS/work/phase4b1-dhzezpnz/verify-base-root | 2.221 | Extração histórica regenerável; ISOs e result-iso-tree preservados | Requer confirmar ausência de referências ativas e hardlinks externos antes de excluir |
| /home/magaton/DevLite-OS/work/phase4b1-dhzezpnz/verify-live-root | 1.928 | Extração histórica regenerável; ISOs e result-iso-tree preservados | Requer confirmar ausência de referências ativas e hardlinks externos antes de excluir |
| /home/magaton/DevLite-OS/work/release-ku78mn3t/pack-attempt/verify-minimal.live.squashfs | 2.069 | Diretório de auditoria/delta regenerável; packed, receitas e logs preservados | Reextração futura pode exigir operação privilegiada |
| /home/magaton/DevLite-OS/work/release-ku78mn3t/pack-attempt/verify-minimal.squashfs | 3.707 | Diretório de auditoria/delta regenerável; packed, receitas e logs preservados | Reextração futura pode exigir operação privilegiada |
| /home/magaton/DevLite-OS/work/release-ku78mn3t/pack-attempt/delta | 2.069 | Diretório de auditoria/delta regenerável; packed, receitas e logs preservados | Reextração futura pode exigir operação privilegiada |
| /home/magaton/DevLite-OS/work/phase4b1-dhzezpnz/rebuilt-casper/minimal.squashfs | 0.638 | Dados de probe encerrado ou cópia SquashFS histórica; atestados e cópias canônicas preservados | Revalidar recibo e igualdade das cópias antes da exclusão |
| /home/magaton/DevLite-OS/work/phase4b1-dhzezpnz/rebuilt-casper/minimal.live.squashfs | 1.212 | Dados de probe encerrado ou cópia SquashFS histórica; atestados e cópias canônicas preservados | Revalidar recibo e igualdade das cópias antes da exclusão |
| /home/magaton/DevLite-OS/work/phase4b3-wnej6dpv/probe-attempt/base.ext4 | 2.307 | Dados de probe encerrado ou cópia SquashFS histórica; atestados e cópias canônicas preservados | Revalidar recibo e igualdade das cópias antes da exclusão |
| /home/magaton/DevLite-OS/work/phase4b3-wnej6dpv/probe-attempt/layers/minimal.squashfs | 0.638 | Dados de probe encerrado ou cópia SquashFS histórica; atestados e cópias canônicas preservados | Revalidar recibo e igualdade das cópias antes da exclusão |
| /home/magaton/DevLite-OS/work/phase4b3-wnej6dpv/probe-attempt/layers/minimal.live.squashfs | 1.212 | Dados de probe encerrado ou cópia SquashFS histórica; atestados e cópias canônicas preservados | Revalidar recibo e igualdade das cópias antes da exclusão |

Total estimado: **49.88 GiB** em 21 caminhos; livre medido: **21.25 GiB**; projeção: **71.13 GiB**.

As seis árvores de auditoria de ISO recuperariam aproximadamente 18,48 GiB. A proposta completa inclui duas cópias de ISO: sua remoção elimina a segunda cópia física, mantendo a ISO principal/canônica e as provas de reprodução. O plano completo pode evitar expansão do disco, mas a suficiência só estará confirmada após limpeza autorizada e nova medição.

Preservar integralmente os caminhos de preserve em [plano JSON](evidencias/plano-limpeza-final.json), incluindo imagens Base/Live aceitas, packed antigo referenciado pelo contrato atual, ISO original, principal experimental, cache 243 .deb, result-iso-tree e todos os relatórios/recibos.

A auditoria encontrou três imagens ext4 já esparsas, com 12 GiB lógicos cada. As duas imagens aceitas permanecem; somente a imagem do probe encerrado é candidata. Nenhum limite de armazenamento será reduzido.

Antes de executar: vincular lista exata e identidades atuais dos arquivos, revalidar hashes de duplicatas e recibos, conferir que não há jobs/montagens/loops/arquivos em uso, verificar hardlinks externos, obter autorização específica e usar limpeza confinada aos caminhos listados. A autorização de du/find não autoriza exclusões.
