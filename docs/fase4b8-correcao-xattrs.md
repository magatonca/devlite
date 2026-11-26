> Atualização: comparações reais Base/delta/visão Live passaram; publicação bloqueada por formato Snap no manifest. Parser corrigido, preflight real aprovado e 191 testes. [Resultado e novo comando para autorização](fase4b8-correcao-manifest-snap.md). Nenhuma ISO nova. O conteúdo abaixo preserva o histórico.

# Fase 4B.8 — correção de SquashFS sem tabela de xattrs

17/11/2026. **188 testes aprovados; nova execução privilegiada preparada e ainda não autorizada. Nenhuma ISO gerada.**

## Resultado da operação autorizada

Job release-yqlso8i2, contrato 532cd95a7fb3635101da9b6ccdf95e18928ca134d7815506b271e96963ca094f: iniciado 18:00:21 UTC e encerrado em quarentena após 37min13s. A execução verificou os hashes das imagens aceitas, inventariou Base (113.889 caminhos) e Live (176.566), reconciliou versões e provou logicamente a receita do delta. Comparou integralmente o minimal.squashfs montado com os 113.885 caminhos da Base limpa e aprovou essa camada.

A falha seguinte ocorreu exatamente em os.listxattr na raiz do minimal.live.squashfs montado. **Não foi timeout nesta tentativa.** Retorno do processo: 1. A visão OverlayFS desta retomada não chegou a ser validada. Não houve publicação de layers-ready.json nem publicação dos packs como aprovados. Não se repetiu instalação, extração ou compressão, nem se fez limpeza.

Pico contabilizado: 2,2 GiB, swap zero. As montagens privadas/loops foram liberadas, unidade inativa, gate integracao_camadas_autorizada restaurado false e os demais gates permanecem false. Hashes críticos do host iguais ao checkpoint inicial. Base/Live instaladas continuam aceitas e não precisam de nova instalação ou novo probe.

Evidências: [relatório, traceback, journal e superblocos](evidencias/retomada-yqlso8i2-resultado.json), [checkpoint e encerramento](evidencias/retomada-autorizada-em-execucao.json).

## Causa confirmada e correção

O superbloco 4.0 do delta possui xattr_id_table_start = 0xffffffffffffffff e unsquashfs -s informa zero IDs de xattrs. A receita independente do delta também contém zero entradas com xattrs. O minimal.squashfs Base tem três IDs e continua com leitura estrita.

No Linux 6.8, squashfs_listxattr retorna EOPNOTSUPP quando xattr_id_table é NULL: [código oficial xattr.c](https://raw.githubusercontent.com/torvalds/linux/v6.8/fs/squashfs/xattr.c). O layout do superbloco vem da [estrutura oficial squashfs_super_block](https://raw.githubusercontent.com/torvalds/linux/v6.8/fs/squashfs/squashfs_fs.h).

A correção não altera os arquivos SquashFS. Lê e valida seu cabeçalho, versão, bytes_used e offset da tabela. Somente quando o marcador comprova ausência da tabela **e todos os xattrs esperados dessa camada estão vazios**, gera uma lista exata de caminhos autorizados a interpretar EOPNOTSUPP de listxattr como conjunto vazio. Essa lista não é usada nos ext4 e não abrange caminhos inesperados. Na visão combinada, limita-se aos caminhos presentes no delta sem tabela e com xattrs Live esperados vazios.

Se o superbloco diz que não há tabela mas há qualquer atributo esperado (inclusive capabilities), a verificação falha. Atributos que listxattr efetivamente retorna continuam sendo lidos e comparados; getxattr nunca tem erros ignorados. EIO, EACCES, EPERM, formatos inválidos e caminhos fora da lista continuam fatais. O comportamento padrão de snapshot permanece estrito.

Arquivos alterados: pipeline/devlite/minimal_root.py (leitura com prova explícita); pipeline/devlite/release_resume.py (validação do cabeçalho e lista de caminhos); pipeline/devlite/release_pack.py (mesmo tratamento na composição do caminho de reconstrução integral); tests/test_release_resume.py e novo tests/test_squashfs_xattrs.py.

## Validação e pendências

**188 testes aprovados**, incluindo criação de SquashFS real sem tabela, leitura de cabeçalho, perda de capability esperada, erros de acesso/I/O, erro de getxattr, caminhos desconhecidos, atributo inesperado e preservação dos demais metadados. São fixtures/testes não privilegiados; a correção ainda não foi exercitada em uma montagem real. Resultado: reports/testes-xattrs-retomada.txt. Verificação do projeto: zero erros. git diff --check aprovado.

Cache novamente validado: 243 debs. Código/contrato do executor aceito continuam intactos. Novo contrato de integração incorpora a correção e reaproveita os mesmos packs selados e o mesmo par aceito. Nenhuma nova imagem ext4 é criada. Os gates não foram habilitados pela preparação.

## Nova operação proposta, claramente delimitada

Job: `/home/magaton/DevLite-OS/work/release-mlgwqtyc`. Contrato SHA-256: `ecca6926e6704a1a1c86a123fbc1f42cff2980395fe291d62c56df733aa34337`.

```sh
sudo systemd-run --unit=devlite-pack-mlgwqtyc --wait --pipe --collect --property=MemoryMax=2684354560 --property=MemorySwapMax=1073741824 --property=CPUQuota=100% --property=TasksMax=128 --property=RuntimeMaxSec=10800 --property=KillMode=control-group --property=OOMPolicy=kill unshare --mount --propagation private /usr/bin/python3 /home/magaton/DevLite-OS/scripts/integrar-release-root.py --job /home/magaton/DevLite-OS/work/release-mlgwqtyc --approval-sha256 ecca6926e6704a1a1c86a123fbc1f42cff2980395fe291d62c56df733aa34337
```

O sudo é indispensável para namespace mount privado e montagens loop/ext4/SquashFS/OverlayFS RO. Não executa APT/dpkg, instalação, extração, compressão, rede, limpeza ou ISO. Publicação apenas após comparação integral Base + delta + visão Live e hashes de saída. Inputs originais e tentativas anteriores ficam preservados.

Limites permanecem 2,5 GiB RAM, 1 GiB swap, uma CPU, 128 tarefas e até três horas. Parada delimitada, apenas se necessária: `sudo systemctl stop devlite-pack-mlgwqtyc.service`. O controlador como magaton habilitará somente o gate de integração imediatamente antes e restaurará false em finally; os demais permanecerão false.

Livre medido: **43.37 GiB**. Orçamento deste caminho permanece tamanho dos packs + 10 GiB = 12,18 GiB; publicação acrescenta cerca de 2,18 GiB. Não se reduzem os guards originais de instalação/probe ou reconstrução integral.

A confirmação anterior vinculava comando/job e hash do código anterior; este novo contrato exige aprovação antes de executarmos novamente como root. Até lá, a execução permanece bloqueada.

Após sucesso, auditar recursos e recibos e preparar a geração da ISO, que requer autorização própria. Boot BIOS/UEFI, instalação real, persistência pós-instalação e segunda construção reproduzível continuam pendentes. Node.js LTS, TypeScript e VS Code permanecem fora desta edição experimental Ubuntu.
