> Atualização 17/11/2026: integração encerrada em quarentena no limite de duas horas. Base/Live aceitas preservadas; nenhuma ISO nova. [Retomada preparada, 178 testes e comando para autorização](fase4b8-retomada-verificacao.md). O conteúdo abaixo preserva o histórico anterior.

# Fase 4B.8 — integração do par aceito, proposta para aprovação

17/11/2026 (America/Sao_Paulo). **Limpeza dos sete arquivos autorizada e concluída; integração autorizada em execução. Nenhuma ISO gerada.** O plano abaixo é o registro revisado antes da autorização. O par Base/Live foi instalado e auditado; não é necessário reinstalar pacotes nem repetir o probe para a integração com o código atual. Todos os gates permanecem false.

## Entradas e espaço

Par aceito: work/phase4b3-wnej6dpv/attempt/accepted-pair.json, journal accepted e installation-result.json root-owned no release-ku78mn3t. Código/contrato atual conferidos; imagens Base/Live preservadas, fsck/SHA e 477/43.701 itens protegidos aprovados. A leitura via debugfs confirmou configurações e links dentro das imagens, sem montagem ou escrita. O host permaneceu íntegro e sem recursos residuais. 168 testes passaram novamente. [Resultados](evidencias/instalacao-4b7-tentativa5.json), [configurações](evidencias/configuracoes-par-instalado.json).

Livre medido: **41.27 GiB**. Estimativa conservadora da integração: **51.37 GiB**, usando a fórmula existente 3×Base+5×Live+10 GiB sobre a ocupação total reportada por fsck. O valor real será recalculado pelo backend com allocated_usage após montar os inputs RO. Não se reduzirá esse guard, a margem inicial de 32 GiB nem os limites de RAM/CPU. O mínimo de 56 GiB para iniciar probes permanece inalterado; o probe desta versão já terminou e esta proposta não inicia outro.

## Limpeza proposta — sete arquivos antigos, sem tocar no par aceito

| Caminho completo | GiB recuperáveis | Justificativa |
|---|---:|---|
| `/home/magaton/DevLite-OS/work/phase4b3-nuuyxpa1/attempt/base.ext4` | 2.371 | Imagem de tentativa antiga em quarentena; substituída para construção pelo par atual aceito. |
| `/home/magaton/DevLite-OS/work/phase4b3-yqj_nck2/probe-attempt/base.ext4` | 2.307 | Imagem de probe concluído; atestado/recibos preservados. |
| `/home/magaton/DevLite-OS/work/phase4b3-yqj_nck2/attempt/base.ext4` | 3.784 | Imagem de tentativa antiga em quarentena; substituída para construção pelo par atual aceito. |
| `/home/magaton/DevLite-OS/work/phase4b3-yqj_nck2/probe-attempt/layers/minimal.squashfs` | 0.638 | Cópia SquashFS idêntica por SHA-256 à fonte preservada. |
| `/home/magaton/DevLite-OS/work/phase4b3-yqj_nck2/probe-attempt/layers/minimal.live.squashfs` | 1.212 | Cópia SquashFS idêntica por SHA-256 à fonte preservada. |
| `/home/magaton/DevLite-OS/work/phase4b3-yqj_nck2/attempt/layers/minimal.squashfs` | 0.638 | Cópia SquashFS idêntica por SHA-256 à fonte preservada. |
| `/home/magaton/DevLite-OS/work/phase4b3-yqj_nck2/attempt/layers/minimal.live.squashfs` | 1.212 | Cópia SquashFS idêntica por SHA-256 à fonte preservada. |

Recuperação estimada: **12.16 GiB**. Livre projetado: **53.43 GiB**, cerca de **2.06 GiB acima da estimativa conservadora**. A projeção não substitui a checagem real após a limpeza e o guard do backend.

As quatro cópias SquashFS e suas duas fontes foram lidas e conferidas por SHA-256. Os sete arquivos são regulares, nlink=1, com device/inode/UID/tamanho/mtime/ctime registrados; jobs em probe_passed/quarantined, sem par aceito antigo, arquivos abertos, unidades ativas, mounts ou loops. Antes de remover, conferir novamente essas condições e o manifesto. Se houver divergência, parar sem substituir candidatos ou apagar diretórios.

**Risco explícito:** as três imagens ext4 históricas serão removidas, inclusive a Base da falha anterior de /run/lock. Isso elimina a inspeção binária posterior dessas cópias. Seus logs, hashes, journals, planos e configurações-fonte serão mantidos; o par Base/Live atual aceito fica intacto e passa a ser a referência da construção. Não se promete regeneração bit a bit dos ext4 antigos. Nenhuma dessas imagens em quarentena será retomada in-place.

Preservados: código/Git; ISO original autenticada; todas as ISOs experimentais; cache dos 243 debs; manifests, assinaturas, recibos/evidências; fontes SquashFS 4B.1; diretórios dos jobs antigos; **ambas as imagens aceitas e seus insumos privados**. Nenhum arquivo fora dos sete listados será removido. Não fazer limpeza recursiva/globs nem baixar pacotes.

Comandos de limpeza propostos, ainda não executados:

```sh
sudo /usr/bin/unlink -- /home/magaton/DevLite-OS/work/phase4b3-nuuyxpa1/attempt/base.ext4
sudo /usr/bin/unlink -- /home/magaton/DevLite-OS/work/phase4b3-yqj_nck2/probe-attempt/base.ext4
sudo /usr/bin/unlink -- /home/magaton/DevLite-OS/work/phase4b3-yqj_nck2/attempt/base.ext4
sudo /usr/bin/unlink -- /home/magaton/DevLite-OS/work/phase4b3-yqj_nck2/probe-attempt/layers/minimal.squashfs
sudo /usr/bin/unlink -- /home/magaton/DevLite-OS/work/phase4b3-yqj_nck2/probe-attempt/layers/minimal.live.squashfs
sudo /usr/bin/unlink -- /home/magaton/DevLite-OS/work/phase4b3-yqj_nck2/attempt/layers/minimal.squashfs
sudo /usr/bin/unlink -- /home/magaton/DevLite-OS/work/phase4b3-yqj_nck2/attempt/layers/minimal.live.squashfs
```

[Manifesto exato da limpeza](evidencias/limpeza-para-integracao-plano.json), SHA-256 `e158ddd1ab9b2a0eda5b5634d511769dbe70520c7726ec3ecb6b357272028549`. Preservar o manifesto como histórico e escrever novo recibo da remoção; não alterar hashes anteriores.

## Integração privilegiada proposta, condicionada à limpeza e aos guards

Somente depois de autorização explícita desta sequência: remover exclusivamente os sete arquivos acima, confirmar espaço/contrato/par aceito, habilitar somente integracao_camadas_autorizada e executar:

```sh
sudo systemd-run --unit=devlite-pack-ku78mn3t --wait --pipe --collect --property=MemoryMax=2684354560 --property=MemorySwapMax=1073741824 --property=CPUQuota=100% --property=TasksMax=128 --property=RuntimeMaxSec=7200 --property=KillMode=control-group --property=OOMPolicy=kill unshare --mount --propagation private /usr/bin/python3 /home/magaton/DevLite-OS/scripts/integrar-release-root.py --job /home/magaton/DevLite-OS/work/release-ku78mn3t --approval-sha256 9e6ca71886ea6d2ef381267a1380aada2ca6fa8df24329119ea1fc4975ad25b1
```

A necessidade de root é limitada a preservar UID/GID, capabilities/xattrs, devices/whiteouts, montar imagens RO/noload e testar a composição OverlayFS em namespace mount privado. Inputs ext4 são verificados por hash antes de montar. Nenhum chroot, APT/dpkg, daemon, rede ou modificação em volumes/partições do host nesta etapa. O único armazenamento gravável é o job do projeto; inputs aceitos e ISO original não são alterados.

O backend calcula a receita de delta da visão Live completa em relação à Base instalada, materializa whiteouts/hardlinks/metadados, comprime sequencialmente com um processador/cache 256 MiB, reextrai e compara os inventários e prova pelo kernel que Base+delta reproduz a Live. Atualiza manifests, tamanhos e catálogo do instalador preservando suas semânticas. Somente após todos os checks publica published-casper e layers-ready.json root-owned. Não gera ISO. Limites da unidade: 2,5 GiB RAM, 1 GiB swap, uma CPU, 128 tarefas e até duas horas. Uma falha preserva os inputs e a tentativa de pack em quarentena; não afrouxar o guard nem apagar resultados automaticamente.

Restaurar integracao_camadas_autorizada=false em finally, mesmo em falha/sinal. Verificar unidade encerrada, mounts/loops liberados, host e inputs preservados e recibo coerente. Se a limpeza ou a margem falhar, não iniciar pack. A sequência inteira é uma proposta ainda sem autorização; as aprovações anteriores cobriam instalação/limpezas já concluídas.

## ISO e aceitação continuam separadas

Depois de integrar com sucesso, continuar automaticamente inspeções e preparação não privilegiadas. Geração da ISO e VMs exigem autorização própria. O construtor preserva BIOS/UEFI/EFI anexada via replay e só aceita recibo layers-ready válido; sua margem de espaço será recalculada com os tamanhos SquashFS reais. A reprodução binária de nova ISO ainda não foi executada.

Checklist atual: work/release-ku78mn3t/acceptance-ubuntu-experimental.json. Permanece corretamente rejeitado por estar incompleto, sem evidências fictícias. Boot BIOS/UEFI, XFCE, programas, instalação em disco descartável, reinicialização e persistência dependem de testes reais. Node.js LTS/TypeScript/VS Code permanecem fora do perfil Ubuntu instalado. Não declarar a edição completa pronta.

## Execução autorizada em andamento

Usuário autorizou a sequência. Removidos somente os sete arquivos, após repetir as verificações de identidade e uso: recuperação de 12,16 GiB e 53,44 GiB livres. Par aceito preservado. [Recibo](evidencias/limpeza-para-integracao-executada.json). Contrato/recibo/espaço conferidos, somente a flag de integração habilitada e comando systemd/unshare aprovado iniciado. Um controlador externo restaurará a flag em finally e encerrará somente a unidade nomeada em interrupção.

Última observação: hashes e inventários dos inputs Base/Live concluídos; receita ainda em prova lógica de composição, com uso de CPU. O algoritmo atual percorre repetidamente o inventário por alteração e está lento; não alterar o código/contrato enquanto o processo aprovado está executando. Ainda não houve aceite das novas camadas, round-trip, composição pelo kernel ou ISO. [Estado observado](evidencias/integracao-em-execucao.json).
