# Correção pontual CAP_FOWNER

Execução aprovada modern-apply-fr800yl6 interrompida após 16min15s, retorno 1. Base: cópia descartável e auditoria inicial de 121536 caminhos concluídas; os sete patches foram escritos, mas a restauração dos timestamps dos diretórios falhou em os.utime com EPERM. Não houve comparação final, e2fsck nem hash final. Live não iniciada. Não apresentar o visual como aplicado e validado. Tentativa preservada em quarentena; nenhuma exclusão.

O CapabilityBoundingSet aprovado não continha CAP_FOWNER. A restauração de timestamps explícitos em diretórios de outros UIDs exige essa capability, mesmo com CAP_DAC_OVERRIDE. A helper minimal_root.apply_to_tree restaura timestamps de todos os diretórios antes de retornar; a chamada falhou nessa etapa. O traceback original não registrou qual diretório: não afirmar um caminho ou UID específico como comprovado. Falha de pré-requisito no executor preparado; não é falha das configurações visuais.

Correção: acrescentar exclusivamente CAP_FOWNER ao bounding set e verificar seu bit efetivo (3) antes de criar lock/cópias. Mantidos ProtectSystem=strict, ProtectHome=read-only, rede privada, única exceção de escrita no job, limite 2,5 GiB RAM/1 GiB swap/128 tarefas/uma CPU/três horas, reserva 20 GiB e allowlist de sete arquivos. Arquivo original preservado em docs/evidencias/modern-fr800yl6-executor-original.py.txt; helper e pipeline anteriores não modificados.

13 testes focados passaram; nove testes adicionais dos controladores futuros também passaram. Suíte anterior de 507 testes não foi repetida. Nova execução exige confirmação porque capability, job e contrato mudaram. Nenhuma nova operação privilegiada iniciada.

Configuração crítica do host conferida após a falha, sem alterações. Imagens originais ficaram fora da exceção RW do serviço e não foram montadas para escrita. Hashes integrais pós-falha das originais não foram recalculados. Não há hashes de saída aceitos nem diff completo. Serviço anterior inativo. Livre: 81.40 GiB. Nova operação mantém gate inicial 76,16 GiB; orçamento adicional conservador 25 GiB deixaria cerca de 56,40 GiB livres. A cópia parcial antiga permanece preservada. Não envolve limpeza, APT, pacotes, serviços convidados, SquashFS ou ISO.

## Comando corrigido exato

```bash
sudo systemd-run --unit=devlite-modern-apply-5w334rzl --wait --pipe --collect --property=ProtectSystem=strict --property=ProtectHome=read-only --property=ReadWritePaths=/home/magaton/DevLite-OS/work/modern-apply-5w334rzl --property=PrivateNetwork=yes --property=PrivateMounts=yes --property=NoNewPrivileges=yes --property=ProtectKernelTunables=yes --property=ProtectKernelModules=yes --property=ProtectControlGroups=yes --property=MemoryMax=2684354560 --property=MemorySwapMax=1073741824 --property=TasksMax=128 --property=CPUQuota=100% --property=RuntimeMaxSec=10800 --property=KillMode=control-group --property=OOMPolicy=kill --property=RestrictAddressFamilies=AF_UNIX '--property=CapabilityBoundingSet=CAP_SYS_ADMIN CAP_SYS_CHROOT CAP_SETPCAP CAP_SETUID CAP_SETGID CAP_KILL CAP_CHOWN CAP_DAC_OVERRIDE CAP_DAC_READ_SEARCH CAP_FOWNER' unshare --mount --propagation private --pid --fork --kill-child=KILL --mount-proc --net --ipc --uts /usr/bin/python3 /home/magaton/DevLite-OS/scripts/aplicar-modern-isolado.py --job /home/magaton/DevLite-OS/work/modern-apply-5w334rzl --approval-sha256 153cd14745cdddb20d1c9f00448b9a4fbcf1376387e9cdcdcc017fdb6e8771e2 --execute-authorized
```

Contrato: 153cd14745cdddb20d1c9f00448b9a4fbcf1376387e9cdcdcc017fdb6e8771e2

## Continuidade preparada

Control homologado mantido na 1.0; Control 2.0 reservado para 1.1. Scripts futuros empacotar-modern-isolado.py e gerar-iso-modern-controlada.py preparados e com testes focados, ainda sem contratos de execução utilizáveis nem autorização. Empacotamento reutilizará receita/delta/round-trip/composição kernel anteriores, reforçando reserva para 20 GiB. Geração única futura reutilizará auditoria BIOS/UEFI/EFI e checksums/proveniência. Exigem respectivas aprovações; não geraram artefatos.
