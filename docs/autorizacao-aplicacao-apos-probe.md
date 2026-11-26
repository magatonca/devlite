# Autorização de aplicação e integração após probe aprovado

**Executada e aprovada em 18/11/2026.** A operação autorizada terminou com retorno 0 em 2h55min50s. Não repetir este comando. Os recibos `public-result.json` e `layers-ready.json` aprovam as duas camadas, o round-trip e a composição pelo kernel. A geração da ISO não foi executada. Ver evidências em `evidencias/aplicacao-publica-execucao.json`.

Job: `/home/magaton/DevLite-OS/work/release-cezaiofx`
Contrato: `e62d4a700ff770fa24b0afe9b013c3b14eb841db60e5a5c3e9bdfd9d79f9c6b3`
Operação selada: apply-and-pack.

## Operação proposta, em um único serviço

1. Consultar propriedades externas e validar o handoff selado e o isolamento interno já aprovados no probe.
2. Revalidar as fontes aceitas e criar cópias ext4 esparsas novas apenas no job.
3. Copiar Node.js 26.13.1, TypeScript 7.0.2, identidade visual, menu XFCE e DevLite Control, sem executar os programas ou lifecycle scripts.
4. Auditar integralmente os arquivos anteriores, metadados, links e dpkg. Colisões ou qualquer alteração não declarada bloqueiam.
5. Reconciliar Base/Live, gerar delta/whiteouts e atualizar manifests, preservando o instalador.
6. Empacotar SquashFS com um processo e 256 MiB; reextrair, comparar e verificar composição pelo kernel. Publicar somente com aprovação completa.

Sem APT, instalação no hospedeiro, downloads, nova limpeza, chroot, VMs ou geração de ISO. Fontes originais e ISO experimental permanecem preservadas. Qualquer falha deixa a nova tentativa em quarentena, sem retomada automática nem remoção de artefatos.

Root é indispensável para namespaces, montagens apenas das cópias, UID/GID, permissões, atributos e whiteouts. Mantidos ProtectSystem=strict, ProtectHome=read-only e um único ReadWritePaths no job. A flag do empacotador antigo é apenas um bind privado somente leitura de uma cópia; a configuração real permanece false.

Mesmos limites: 2,5 GiB RAM, 1 GiB swap, uma CPU, 128 tarefas e três horas. Exigir 70 GiB livres ao iniciar e manter reserva de 56 GiB, além da fórmula adicional do empacotador. Espaço atual aproximadamente 70,78 GiB; conferir novamente imediatamente antes.

## Comando exato para aprovação

```sh
sudo systemd-run --unit=devlite-public-cezaiofx --wait --pipe --collect --property=MemoryMax=2684354560 --property=MemorySwapMax=1073741824 --property=CPUQuota=100% --property=TasksMax=128 --property=RuntimeMaxSec=10800 --property=TimeoutStopSec=60 --property=KillMode=control-group --property=OOMPolicy=kill --property=ProtectSystem=strict --property=ProtectHome=read-only --property=ReadWritePaths=/home/magaton/DevLite-OS/work/release-cezaiofx --property=PrivateNetwork=yes --property=PrivateMounts=yes --property=NoNewPrivileges=yes --property=ProtectKernelTunables=yes --property=ProtectKernelModules=yes --property=ProtectControlGroups=yes --property=RestrictRealtime=yes --property=RestrictAddressFamilies=AF_UNIX '--property=CapabilityBoundingSet=CAP_SYS_ADMIN CAP_CHOWN CAP_DAC_OVERRIDE CAP_DAC_READ_SEARCH CAP_FOWNER CAP_FSETID CAP_MKNOD CAP_SETFCAP' /usr/bin/python3 /home/magaton/DevLite-OS/scripts/iniciar-publico-isolado-root.py --job /home/magaton/DevLite-OS/work/release-cezaiofx --approval-sha256 e62d4a700ff770fa24b0afe9b013c3b14eb841db60e5a5c3e9bdfd9d79f9c6b3 --execute-authorized -- unshare --mount --propagation private --pid --fork --kill-child --mount-proc --net --ipc --uts /usr/bin/python3 /home/magaton/DevLite-OS/scripts/aplicar-publico-root.py --job /home/magaton/DevLite-OS/work/release-cezaiofx --approval-sha256 e62d4a700ff770fa24b0afe9b013c3b14eb841db60e5a5c3e9bdfd9d79f9c6b3 --execute-authorized
```

[Contrato](../work/release-cezaiofx/public-contract.json), [argv](../work/release-cezaiofx/public-command.json), [333 testes](../reports/testes-correcao-systemctl-unshare.txt) e [probe real aprovado](probe-systemctl-unshare-aprovado.md).

A aprovação solicitada abrange somente aplicação e reconstrução/auditoria das camadas. A geração de **uma única ISO candidata** será uma operação posterior, com inputs e comando próprios. Boot e instalação reais não foram testados.
