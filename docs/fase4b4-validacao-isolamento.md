# Fase 4B.4 — validação do isolamento antes do probe real

Estado em 16/11/2026 (America/Sao_Paulo): **probe real normal autorizado pelo usuário e aprovado**, com retorno 0 e atestado root-owned `probe_passed`. A etapa preparatória e os 116 testes foram executados como magaton. Após a confirmação, somente o comando do probe foi executado como root, sem prefixo sudo redundante no executor já root.

Não houve APT/dpkg no alvo, instalação de pacotes, nova ISO, modificação de partições/volumes, execução de recuperação manual ou commit. `probe_autorizado` foi habilitado temporariamente e restaurado para false. Instalação e recuperação permaneceram false.

## Resultado da execução autorizada

O probe do job `work/phase4b3-1ibq_emz`, revisão `e1bc8013b0a10b8e2eea8884b38d697c51263866eb2d7f4d545b98e6f82203a8`, terminou com exit code 0 e atestado `probe_passed`. O controlador só emite esse atestado após os checks do guest, inventário protegido, banco dpkg intacto, e2fsck somente leitura, hash da imagem e proteção do host passarem.

Os limites foram também observados externamente, como magaton: memory.max=2684354560, memory.swap.max=1073741824, pids.max=128 e cpu.max=100000 100000. A unidade terminou e foi coletada; não restou cgroup ou processo worker do job. Os checkpoints do host confirmaram arquivos críticos, namespace/mountinfo e backings de loop iguais ao estado anterior. OverlayFS foi carregado, como previsto; não se tentou descarregá-lo.

Espaço restante no checkpoint final: aproximadamente **68,77 GiB**. O arquivo ext4 descartável tem limite lógico de 12 GiB e foi preservado com as cópias e evidências. Não houve limpeza automática.

[Evidências públicas da execução](evidencias/probe-real-isolamento.json). O atestado root-owned no diretório do job foi lido e validado como magaton. Registros detalhados do guest, fsck e host-guard ficam preservados dentro de `probe-attempt`, root 0700; não foram exportados nem tiveram suas permissões alteradas. A validação das afirmações internas decorre do retorno 0 e do atestado para o código cujo hash foi conferido; os valores detalhados do guest permanecem nesses registros privados.

Interrupção/recuperação reais, falhas de OOM/reboot e instalação de pacotes **não foram testadas** nesta execução. O probe aprovado não autoriza essas operações nem uma instalação real.


## Resultados confirmados

- A suíte original foi repetida: 105 testes aprovados. Após reforçar o probe, a suíte final tem **116 aprovados, zero falhas**, incluindo 11 novos.
- Sistema de arquivos raiz: 125.68 GiB; livre medido: 73.04 GiB. Supera o orçamento conservador de 56 GiB.
- Memória: aproximadamente 3,8 GiB de RAM e 3,8 GiB de swap. A swap estava sem uso no diagnóstico. MemoryMax do worker será 2,5 GiB, swap até 1 GiB, 128 tarefas e CPUQuota=100%.
- Kernel 6.8.0-149-generic, PID 1 systemd e cgroup v2 com controladores cpu/memory/pids disponíveis. As ferramentas systemd-run/systemctl, unshare, mount/umount, mkfs.ext4, e2fsck, cp, gpgv e Python estão presentes.
- Ext4 e SquashFS aparecem em /proc/filesystems. Antes do probe, OverlayFS não estava carregado, mas overlay.ko.zst existia para o kernel atual. A montagem autorizada carregou esse módulo local; o módulo permanece carregado após o teste.
- Antes/depois da suíte final: hashes dos bancos dpkg/APT, fontes APT, passwd/group e fstab iguais; mesmo namespace de montagem, mesmo mountinfo e mesmos backings de loop observáveis. Nenhum mount ou loop foi criado pelos testes.

Os arquivos completos dos checkpoints ficam em reports/phase4b4/host-reviewed-before.json e host-after.json. O checkpoint inicial, anterior aos reforços, está preservado em host-before.json. [Evidência resumida](evidencias/validacao-isolamento.json).

## Correções da revisão

O probe 4B.3 usava um caminho de sentinela que não era criado. Sua ausência podia produzir um resultado positivo sem demonstrar inacessibilidade de um arquivo existente do host. O controlador agora criará uma sentinela real, aleatória e root-owned dentro da tentativa, verificará seu hash antes do chroot e após o probe e fornecerá o caminho ao guest. As tentativas de abrir a sentinela para leitura e escrita devem falhar; mesmo se a restrição falhar, o teste não grava dados na sentinela.

Outros reforços implementados e testados sem privilégios:

- Verificar CapEff, CapPrm, CapBnd, CapInh, CapAmb e NoNewPrivs, limitando todos os conjuntos à allowlist do worker.
- Exigir EROFS ao abrir o bundle para escrita; arquivo ausente não conta como prova de mount RO.
- Conferir flags efetivas de /, /proc, bundle e debs, devices mínimos, ausência de sockets do host, PIDs visíveis, /proc/1/root e descritores herdados.
- Provar escrita reversível dentro do rootfs descartável, criando arquivo exclusivo em /var/tmp e removendo somente esse arquivo do probe. Não sobrescrever dados existentes.
- Conferir que só existe loopback na rede privada e exigir erro de rede inalcançável. O teste é feito somente depois de validar namespaces/interfaces; não precisa DNS nem deve emitir tráfego externo.
- Ler memory.max, memory.swap.max, pids.max e cpu.max da unidade real, antes do chroot, para comprovar que systemd aplicou os limites. A implementação exige a unidade em system.slice; configuração diferente falha, sem fallback.
- Registrar arquivos críticos do host antes/depois também em falhas, além da sentinela. Emitir PROBE_EVIDENCE estruturado e preservar probe-results.json, logs, journal e host-guard.json.

Arquivos criados: scripts/diagnostico-isolamento.py, pipeline/devlite/customize/isolation_validation.py e tests/test_isolation_validation.py. Foram alterados guest_runner.py, executor.py, executor_worker.py, executor_contract.py, configuração/verificador do projeto e documentação. Os jobs antigos foram preservados, mas seus hashes de código ficaram desatualizados; não reutilizá-los.

## Comando do probe normal executado após confirmação

Novo job: `/home/magaton/DevLite-OS/work/phase4b3-1ibq_emz`.
Hash de revisão: `e1bc8013b0a10b8e2eea8884b38d697c51263866eb2d7f4d545b98e6f82203a8`.

[Argumentos completos, inclusive systemd-run/unshare](evidencias/probe-isolamento-comandos.json). Antes de executar, após confirmação do usuário, habilitar **temporariamente somente probe_autorizado** em config/projeto.json; executor_autorizado e recuperacao_autorizada continuam false. Restaurar probe_autorizado=false ao terminar, inclusive em falha. O hash do job não é uma autorização humana por si só.

Comando revisado e autorizado pelo usuário (no terminal magaton com sudo; no executor já root, sem sudo):

```sh
sudo /usr/bin/python3 /home/magaton/DevLite-OS/scripts/executar-programas.py --probe --job /home/magaton/DevLite-OS/work/phase4b3-1ibq_emz --approval-sha256 e1bc8013b0a10b8e2eea8884b38d697c51263866eb2d7f4d545b98e6f82203a8
```

O executor da sessão já inicia como root: nesse ambiente será usada a mesma linha sem o prefixo sudo, somente após aprovação explícita. Habilitar/restaurar a flag é uma edição no projeto feita como magaton. Somente probe_autorizado foi habilitada após a confirmação e restaurada para false ao terminar.

Operações indiretas incluídas nesse comando e que exigem root:

1. Autenticação local das fontes/índices e cópias protegidas em probe-attempt, root 0700; fontes originais permanecem intactas. Não há download e não é necessário adquirir debs para o probe.
2. Unidade transitória limitada e namespaces mount/PID/network/IPC/UTS/cgroup, com propagação privada.
3. Mounts SquashFS/OverlayFS RO e loop devices temporários; eventual carregamento automático do módulo OverlayFS disponível no kernel.
4. Criação/formatacão de **um arquivo novo base.ext4 de 12 GiB no job**, nunca um dispositivo/partição do host; cópia da base para essa imagem, proc e tmpfs limitados, devices mínimos e binds RO.
5. Chroot do supervisor e guest, redução de capabilities e probe sem APT/dpkg/serviços. A chamada mount feita pelo guest deve ser negada; permissão indevida causa falha do probe.
6. Verificações, término do namespace, e2fsck -f -n e hash da imagem de teste. Arquivos e evidências ficam preservados; não há exclusão automática.

O timeout de uma hora é do worker systemd, não um limite total de todas as cópias/hashes do controlador. O watchdog preserva 12 GiB livres durante o worker. O orçamento de 56 GiB é conservador para a sequência posterior completa; a imagem do probe tem limite lógico de 12 GiB, mais cópias de fontes/índices/logs no projeto. Após a confirmação, o arquivo ext4 limitado do probe foi criado dentro do job.

## Proteção do Ubuntu Server e critérios de aprovação

O probe deve produzir prova estruturada de namespaces diferentes do host, capabilities restritas, limits cgroup exatos, negação de acesso à sentinela, bundle/debs RO, apenas PIDs do namespace, /proc/1/root inacessível ou igual à raiz do alvo, apenas devices permitidos, escrita apenas na cópia e rede inalcançável. Banco dpkg da cópia, inventário protegido do instalador e sentinela devem permanecer iguais.

No host, repetir o diagnóstico e comparar arquivos críticos, namespace/mountinfo e backing files de loop; conferir ausência da unidade/processos do job e de mounts/loops associados ao seu caminho. Não desmontar/destacar loops preexistentes do servidor. Examinar logs e journal, e só aceitar state=probe_passed com a mesma revisão. Presença de ferramentas e namespace links na inspeção atual é indício de compatibilidade, não aprovação desses mecanismos em runtime.

Para obter um checkpoint sem sudo, antes/depois do probe autorizado:

```sh
python3 scripts/diagnostico-isolamento.py
```

A rotina de comparação está em isolation_validation.compare e foi usada nos checkpoints desta fase. Alterações concorrentes legítimas do host também podem invalidar a comparação; investigar, sem desabilitar atualizações automaticamente.

## Interrupção e recuperação

Os testes não privilegiados verificaram KeyboardInterrupt, encerramento restrito da unidade, preservação de logs, journal e recuperação para quarentena sem mount/dpkg. Isso **não aprova SIGTERM/SIGKILL, OOM, reboot ou liberação de loops no kernel real**.

O comando normal trata falhas/sinais e encerra somente suas próprias unidades. Se o controlador morrer abruptamente, a unidade ainda tem RuntimeMaxSec e KillMode=control-group. Falha mantém imagens em quarentena e não permite retomar a mesma tentativa. Para validar interrupção real, criar depois um segundo job, apresentar seus comandos exatos e pedir autorização específica; não interromper o primeiro probe normal sem uma nova decisão.

Recuperação manual prevista para este job, **não autorizada nesta entrega**, exige confirmação e habilitação temporária própria de recuperacao_autorizada:

```sh
sudo /usr/bin/python3 /home/magaton/DevLite-OS/scripts/executar-programas.py --recover --job /home/magaton/DevLite-OS/work/phase4b3-1ibq_emz --approval-sha256 e1bc8013b0a10b8e2eea8884b38d697c51263866eb2d7f4d545b98e6f82203a8
```

Ela encerra unidades determinísticas deste job e marca quarentena; não instala, repara, apaga ou retoma o filesystem. Não executar se o probe não foi iniciado e não criar receipts artificiais. A liberação de loops/mounts deve ser verificada, não presumida; qualquer resíduo requer revisão, sem cleanup genérico ou umount -l automático.

## Riscos, limites e recomendação

O probe normal sem pacotes foi autorizado e aprovado. Recomendo concluir testes controlados de interrupção/recuperação sob autorização específica antes de avançar à instalação. A instalação real não foi autorizada e permanece desabilitada.

O isolamento compartilha o kernel e usa um supervisor root confiável durante a preparação; não equivale a uma VM para código malicioso. O proprietário administrador do projeto é confiável: hashes de revisão detectam mudanças acidentais, mas não constituem defesa completa contra um administrador malicioso alterando código simultaneamente. O probe será necessário para verificar compatibilidade real de OverlayFS, loops, namespaces, capabilities e cgroups. Falhas devem abortar sem ampliar privilégios ou reduzir restrições. Limites de memória não eliminam toda pressão sobre o host; monitorar a VM, swap e logs.

Mesmo um probe normal aprovado não aprova instalação de pacotes, execução de maintainer scripts, rebase live, BIOS/UEFI ou instalação/persistência do sistema. Esses testes e autorizações continuam separados.

## Reprodução da validação não privilegiada

```sh
TMPDIR="$PWD/work/phase4b1-tests-tmp" PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 scripts/verificar-projeto.py
```

Relatórios: reports/testes-fase4b4-baseline.txt (105) e reports/testes-fase4b4.txt (116). A simulação APT da suíte anterior usa uma fixture local do host dentro de work, sem instalações; não executa APT/dpkg dentro das imagens. Os testes novos usam fixtures/mocks para syscalls, recuperação e limite cgroup.

Referências oficiais: [unshare e propagação privada](https://manpages.ubuntu.com/manpages/noble/man1/unshare.1.html), [limites systemd/cgroup](https://manpages.ubuntu.com/manpages/noble/man5/systemd.resource-control.5.html), [namespaces Linux](https://manpages.ubuntu.com/manpages/noble/man7/namespaces.7.html).
