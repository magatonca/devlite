# Recuperação definitiva de espaço — proposta para aprovação

17/11/2026 (America/Sao_Paulo). **Limpeza explicitamente autorizada e concluída: somente os 14 arquivos listados foram removidos. Nenhuma imagem ext4 nova criada.** A tabela e o manifesto abaixo registram a proposta anterior à execução. Auditoria somente leitura, com acesso root para ler arquivos privados; documentos gravados como magaton. Código e contratos não foram alterados.

## Proposta: 14 arquivos de tentativas encerradas

Livre medido: **51.94 GiB**. Recuperação estimada por blocos realmente alocados: **15.72 GiB** (16,876,486,656 bytes). Livre projetado: **67.66 GiB**, acima da meta de 60 GiB. Confirmar df após a operação; outros consumidores podem alterar a projeção. Cada candidato é um arquivo regular com um único hardlink, portanto esta soma não duplica blocos compartilhados do cache APT.

| Caminho completo | GiB recuperáveis | Justificativa |
|---|---:|---|
| `/home/magaton/DevLite-OS/work/phase4b3-1ibq_emz/probe-attempt/layers/minimal.squashfs` | 0.638 | Cópia SquashFS idêntica por SHA-256 à fonte preservada. |
| `/home/magaton/DevLite-OS/work/phase4b3-1ibq_emz/probe-attempt/layers/minimal.live.squashfs` | 1.212 | Cópia SquashFS idêntica por SHA-256 à fonte preservada. |
| `/home/magaton/DevLite-OS/work/phase4b3-1ibq_emz/attempt/layers/minimal.squashfs` | 0.638 | Cópia SquashFS idêntica por SHA-256 à fonte preservada. |
| `/home/magaton/DevLite-OS/work/phase4b3-1ibq_emz/attempt/layers/minimal.live.squashfs` | 1.212 | Cópia SquashFS idêntica por SHA-256 à fonte preservada. |
| `/home/magaton/DevLite-OS/work/phase4b3-bklz27i4/probe-attempt/layers/minimal.squashfs` | 0.638 | Cópia SquashFS idêntica por SHA-256 à fonte preservada. |
| `/home/magaton/DevLite-OS/work/phase4b3-bklz27i4/probe-attempt/layers/minimal.live.squashfs` | 1.212 | Cópia SquashFS idêntica por SHA-256 à fonte preservada. |
| `/home/magaton/DevLite-OS/work/phase4b3-bklz27i4/attempt/layers/minimal.squashfs` | 0.638 | Cópia SquashFS idêntica por SHA-256 à fonte preservada. |
| `/home/magaton/DevLite-OS/work/phase4b3-bklz27i4/attempt/layers/minimal.live.squashfs` | 1.212 | Cópia SquashFS idêntica por SHA-256 à fonte preservada. |
| `/home/magaton/DevLite-OS/work/phase4b3-nuuyxpa1/probe-attempt/layers/minimal.squashfs` | 0.638 | Cópia SquashFS idêntica por SHA-256 à fonte preservada. |
| `/home/magaton/DevLite-OS/work/phase4b3-nuuyxpa1/probe-attempt/layers/minimal.live.squashfs` | 1.212 | Cópia SquashFS idêntica por SHA-256 à fonte preservada. |
| `/home/magaton/DevLite-OS/work/phase4b3-nuuyxpa1/attempt/layers/minimal.squashfs` | 0.638 | Cópia SquashFS idêntica por SHA-256 à fonte preservada. |
| `/home/magaton/DevLite-OS/work/phase4b3-nuuyxpa1/attempt/layers/minimal.live.squashfs` | 1.212 | Cópia SquashFS idêntica por SHA-256 à fonte preservada. |
| `/home/magaton/DevLite-OS/work/phase4b3-bklz27i4/attempt/base.ext4` | 2.309 | Imagem da segunda instalação abortada; manter registros e a imagem da falha mais recente. |
| `/home/magaton/DevLite-OS/work/phase4b3-nuuyxpa1/probe-attempt/base.ext4` | 2.307 | Imagem do terceiro probe concluído; atestado, fsck, hashes e logs preservados. |

As 12 cópias SquashFS foram lidas integralmente e comparadas ao SHA-256 contratado e às duas fontes atuais em work/phase4b1-dhzezpnz/result-iso-tree/casper. Essas fontes também foram lidas e validadas; seus dados permanecem disponíveis. Os seis jobs/tentativas internos estão em estado probe_passed ou quarantined, sem accepted-pair, sem recuperação em andamento, unidades inativas e sem mounts/loops/arquivos abertos. Os campos device/inode/UID/tamanho/links/mtime/ctime e hashes foram registrados para conferir novamente antes de qualquer remoção.

A remoção dos SquashFS não perde conteúdo único: são cópias verificadas. A remoção das duas imagens ext4 perde a inspeção binária dessas cópias específicas; sua geração é repetível pelas entradas preservadas, mas não se promete o mesmo hash ext4 por causa de UUID/metadados variáveis. Guardar atestados, hashes, logs e journals e registrar explicitamente a remoção em novo recibo, sem reescrever evidências antigas. A imagem parcialmente modificada mais recente, work/phase4b3-nuuyxpa1/attempt/base.ext4, não entra na limpeza.

## Essenciais e regeneráveis

Preservar código/Git; sources/xubuntu-24.04.5-minimal-amd64.iso e sua autenticação; cache completo dos 243 debs; manifestos, assinaturas, índices autenticados, recibos e logs; todas as ISOs experimentais e a reprodução 3B; fontes e metadados SquashFS da 4B.1; imagem da falha mais recente; próxima preparação release-o9fx0a_a e executor phase4b3-yqj_nck2. Nenhum diretório será apagado.

O inventário anterior do projeto foi reaproveitado para evitar percorrer novamente árvores inalteradas: work/phase4b1-dhzezpnz ocupa cerca de 18,06 GiB em arquivos e work/phase3b-frka50es cerca de 5,94 GiB. São árvores intermediárias, parcialmente regeneráveis, mas preservadas para manter entradas e acelerar a reconstrução. ISOs preservadas: sources/xubuntu-24.04.5-minimal-amd64.iso; artifacts/phase3b-9adp_k5i/devlite-os-1.0-experimental-rebuild.iso; artifacts/phase4b1-lgpa3zc7/devlite-os-1.0-basic-experimental.iso; work/phase3b-reproduction-jvzarclv/reproduced.iso (aproximadamente 2,97 GiB cada). Relatórios/temporários pequenos de preflight e índices continuam preservados, pois sua remoção não é necessária à meta.

A medição atual dos três jobs antigos, numa única chamada du com deduplicação dos hardlinks compartilhados, foi: phase4b3-1ibq_emz 4.881.317.888 bytes; phase4b3-bklz27i4 7.022.309.376 bytes; phase4b3-nuuyxpa1 9.565.597.696 bytes. A atribuição dos hardlinks entre pastas depende da ordem; o espaço recuperável do plano foi calculado separadamente com nlink=1, sem essa ambiguidade.

## Otimização investigada, sem mudar o executor

**As imagens já são esparsas.** executor_worker.py cria arquivo novo com open('xb') seguido de truncate(12 GiB); não usa fallocate nem grava zeros para reservar integralmente o tamanho lógico. As imagens existentes ocupam aproximadamente 2,3 GiB de blocos, não 12 GiB. mkfs.ext4 e a cópia dos payloads alocam os blocos necessários. Não há economia adicional de 12 GiB por imagem a obter apenas mudando a criação para sparse, nem se deve contar tamanho lógico como recuperável. Não foram criadas imagens de teste, nem usados punch-hole/compactação sobre evidências.

A reserva monitorada de 12 GiB e o mínimo de 56 GiB para iniciar probe permanecem intactos. Ser esparso não elimina o orçamento de crescimento do filesystem nem substitui a verificação do espaço livre.

**Base e Live já são sequenciais e compartilham insumos privados.** O controlador copia layers/debs uma vez para a tentativa root-owned, valida os hashes e os disponibiliza RO para os dois workers; não mantém duas execuções concorrentes. Processos, mounts, tmpfs, loops e cgroups são encerrados entre os workers. Os diretórios vazios remanescentes são pequenos e ficam como registro. Reutilizar o mesmo ext4 apagando a Base antes de terminar a Live perderia o par necessário à auditoria, rollback lógico e construção do delta; essa alteração não é recomendada. É necessário manter Base e Live completas até o aceite do par e sua integração.

Uma cache privada imutável entre jobs poderia ser uma otimização futura, mas exigiria revisar confiança/propriedade, isolamento e contratos e testar outro executor. Não substituir as cópias privadas por hardlinks de fontes graváveis por magaton. Para esta retomada, manter o executor atual e seus contratos evita invalidar o trabalho existente. O acúmulo observado vem principalmente da retenção das tentativas antigas; limpar somente após estados terminais, evidências preservadas e aprovação explícita evita repetir esse acúmulo, sem habilitar exclusão automática.

## Comandos exatos aprovados e executados

Os pais dos candidatos são root 0700; a remoção exige sudo. Após autorização, revalidar a lista, identidades, estados e ausência de uso. Interromper se algo divergir. Executar somente os unlink individuais, sem globs, recursão, rm -rf ou remoção de diretórios:

```sh
sudo /usr/bin/unlink -- /home/magaton/DevLite-OS/work/phase4b3-1ibq_emz/probe-attempt/layers/minimal.squashfs
sudo /usr/bin/unlink -- /home/magaton/DevLite-OS/work/phase4b3-1ibq_emz/probe-attempt/layers/minimal.live.squashfs
sudo /usr/bin/unlink -- /home/magaton/DevLite-OS/work/phase4b3-1ibq_emz/attempt/layers/minimal.squashfs
sudo /usr/bin/unlink -- /home/magaton/DevLite-OS/work/phase4b3-1ibq_emz/attempt/layers/minimal.live.squashfs
sudo /usr/bin/unlink -- /home/magaton/DevLite-OS/work/phase4b3-bklz27i4/probe-attempt/layers/minimal.squashfs
sudo /usr/bin/unlink -- /home/magaton/DevLite-OS/work/phase4b3-bklz27i4/probe-attempt/layers/minimal.live.squashfs
sudo /usr/bin/unlink -- /home/magaton/DevLite-OS/work/phase4b3-bklz27i4/attempt/layers/minimal.squashfs
sudo /usr/bin/unlink -- /home/magaton/DevLite-OS/work/phase4b3-bklz27i4/attempt/layers/minimal.live.squashfs
sudo /usr/bin/unlink -- /home/magaton/DevLite-OS/work/phase4b3-nuuyxpa1/probe-attempt/layers/minimal.squashfs
sudo /usr/bin/unlink -- /home/magaton/DevLite-OS/work/phase4b3-nuuyxpa1/probe-attempt/layers/minimal.live.squashfs
sudo /usr/bin/unlink -- /home/magaton/DevLite-OS/work/phase4b3-nuuyxpa1/attempt/layers/minimal.squashfs
sudo /usr/bin/unlink -- /home/magaton/DevLite-OS/work/phase4b3-nuuyxpa1/attempt/layers/minimal.live.squashfs
sudo /usr/bin/unlink -- /home/magaton/DevLite-OS/work/phase4b3-bklz27i4/attempt/base.ext4
sudo /usr/bin/unlink -- /home/magaton/DevLite-OS/work/phase4b3-nuuyxpa1/probe-attempt/base.ext4
```

## Continuidade depois da aprovação

Após remover apenas esses arquivos: registrar resultado e espaço real, exigir pelo menos 60 GiB livres; revalidar contrato, 243 pacotes e preflight dos 240/239 caminhos; executar os testes necessários e reaproveitar a preparação atual, sem criar outra se os contratos permanecerem válidos. Solicitar autorização separada para probe/instalação privilegiados e manter integrações/ISO/VMs bloqueadas até seus comandos e aprovações próprios. Continuar automaticamente preparação e análises não privilegiadas das fases 4B.8–4B.9. Os 166 testes e o preflight citados são os resultados existentes; não foram repetidos durante esta auditoria sem mudança de código.

[Manifesto de auditoria](evidencias/auditoria-espaco-definitiva.json). SHA-256 desse manifesto para vincular a lista aprovada: `0d8f2515f28a9ae03c6e3d69f1035b968e6c1745fb9f6e1ef63d069a50cee763`. Não houve exclusão, instalação, novo namespace/mount/chroot, mudança de flags ou commit nesta auditoria.

## Resultado autorizado e preparação da retomada

O usuário autorizou exclusivamente os 14 arquivos. Identidades (device/inode/UID/tamanho/links/mtime/ctime), estados, ancestrais sem symlink e ausência de arquivos abertos/mounts/loops foram novamente conferidos. Executados apenas os 14 unlink listados; nenhum diretório ou arquivo adicional removido. Recuperação real: **15,72 GiB**; livre após a operação: **67,66 GiB**. Fontes preservadas e imagem da falha parcial mais recente continuam presentes. [Recibo da limpeza](evidencias/limpeza-definitiva-autorizada.json). O manifesto original continua histórico: seus arquivos selecionados não estão mais presentes, sem reescrever os hashes anteriores.

Após a limpeza: contratos/código/plano atuais conferidos; cache-fonte e cache do executor passaram nos 243 arquivos; 166 testes passaram novamente. O preflight sem dpkg com os pacotes reais validou todos os 240 caminhos da Base (55 versões com epoch) e 239 da Live (51 com epoch), com simulações exatas e status/arquivos críticos do host inalterados. Nenhum novo download, instalação ou montagem foi feito para essas verificações. [Retomada revalidada](evidencias/retomada-apos-limpeza-definitiva.json).

Reaproveitados release-o9fx0a_a e phase4b3-yqj_nck2, sem criar outros jobs de instalação/ext4. A preparação da integração e do checklist BIOS/UEFI permanece disponível; sua execução depende de par Base/Live realmente aceito. Todas as permissões continuam false. Instalação real, integração, ISO e VMs não foram executadas nesta retomada.
