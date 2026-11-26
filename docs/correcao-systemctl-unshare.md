# Correção pontual: systemctl dentro do unshare

> Probe autorizado concluído com retorno 0: [erro reproduzido, handoff aprovado e hashes Base/Live conferidos](probe-systemctl-unshare-aprovado.md). Não repetir o probe. Aplicação continua aguardando autorização própria.

**Correção preparada; nenhum job foi executado novamente, nenhum namespace real foi criado nesta investigação.**

## Causa comprovada e limite forense

No release-g_ezd8xj, isolation-systemd.json registra propriedades efetivas corretas e filesystem aprovado. isolation-unshare.json registra outros namespaces e falha de systemctl com retorno 1, antes da criação de attempt. A consulta ao manager foi repetida no contexto interno e tratada como pré-requisito de segurança, apesar de a configuração já ter sido consultada fora.

A implementação antiga usava check=True e persistia apenas str(error): **stdout/stderr originais não foram salvos**. O journal retém início e status 1, sem mensagem do transporte. Portanto, não há base para provar se o erro de baixo nível foi D-Bus, credenciais entre namespaces ou permissões. A causa comprovada na auditoria é essa dependência indevida e a perda dos diagnósticos. Não atribuir a uma mensagem como “No data available” ou “Permission denied” que não foi observada.

PrivateNetwork=yes, UID 0 e as demais propriedades já estavam presentes na fase externa bem-sucedida; isso não basta para classificar o erro interno, que tinha novos namespaces PID/rede/IPC/UTS/mounts. A nova coleta somente leitura obterá o erro concreto sem habilitar rede ou D-Bus.

## Correção implementada

A consulta efetiva permanece **somente na auditoria externa**. service_properties agora usa check=False e grava argv, stdout, stderr e retorno; timeout ou falha local também preservam saída parcial e tipo de erro. A verificação VFS ocorre mesmo se uma consulta falhar, para não perder o diagnóstico dos mounts.

A evidência externa aprovada é serializada diretamente do objeto retornado pelo coletor em **memfd root-owned**, com seals WRITE/GROW/SHRINK/SEAL. É passado somente esse descritor ao filho via pass_fds. O filho recusa arquivos normais e memfds não selados, de proprietário diferente ou fora do limite de 2 MiB.

SHA-256 do conteúdo e nonce aleatório de 256 bits são transmitidos pelo launcher confiável. O envelope também vincula job, hash do contrato, InvocationID do serviço, boot ID, cgroup e transição dos cinco namespaces. As propriedades são revalidadas e devem corresponder ao stdout original bem-sucedido, inclusive MainPID e InvocationID. O hash fornece integridade; a origem confiável decorre do descritor herdado, da propriedade root, dos seals e do código selado do launcher, sem confiar em um JSON substituível no job.

Na fase interna, **capture não consulta systemctl e não faz fallback para o relatório em disco**. Revalida o handoff e observa namespaces/VFS diretamente, incluindo /home, /root, /run/user, fontes protegidas e job. Prova ausente, incompleta, adulterada, de outro contrato ou execução bloqueia antes das imagens. As propriedades ProtectSystem=strict, ProtectHome=read-only, PrivateMounts e a única entrada ReadWritePaths permanecem.

O modo diagnóstico contém uma consulta interna explícita apenas para recuperar stdout/stderr do erro antigo, **sem usá-la para aprovar o isolamento**. Ela não é executada pelo fluxo normal de aplicação corrigido.

## Testes e imagens

**333 testes aprovados**, incluindo 23 regressões novas: retorno não zero e streams, timeout, arquivo comum recusado, seals reais impedindo escrita, proprietário, digest, nonce/contrato/job/execução incorretos, dados incompletos, namespaces, VFS inválido apesar de handoff válido e ausência de fallback. Testado o descritor passado ao filho e seu fechamento pelo launcher.

Apenas fixtures e mocks; os testes de memfd usam objetos reais de memória como magaton. Nenhum serviço, namespace, APT ou imagem real foi utilizado pelos testes.

O job falhou antes de criar attempt/pack-attempt, copiar ou montar Base/Live. Essas saídas continuam ausentes. Assim, o controlador não alterou as imagens. Os hashes físicos das fontes privadas **não foram relidos com root nesta investigação**: essa confirmação bit a bit está preparada no probe abaixo, não declarada concluída. Arquivos críticos do host, flags false, contratos e relatórios antigos foram preservados.

[Saída da suíte](../reports/testes-correcao-systemctl-unshare.txt), [evidências e hashes](evidencias/correcao-systemctl-unshare.json). Manifesto de revisão:

```sh
cd /home/magaton/DevLite-OS
sha256sum --check config/systemctl-handoff-review.sha256
```

## Próximo comando para aprovação: somente diagnóstico e leitura

Necessário para comprovar o erro de transporte cujo stderr não foi preservado e validar o handoff real antes de aplicar arquivos. **Não executado.**

Job: `/home/magaton/DevLite-OS/work/release-4i4yb2kf`
Contrato: `5407b89b6a297f25e70619185f5c412134200257c52167272d293368f15ed7e9`
Operação selada: isolation-diagnostic.

O serviço aplica o mesmo isolamento, valida a evidência externa e os mounts internos, registra o resultado da consulta legada e relê SHA-256 das duas imagens aceitas. **Não cria clones, não aplica payload e não empacota camadas.** Escreve somente os relatórios no próprio job. Exige root para os namespaces e leitura das fontes privadas.

```sh
sudo systemd-run --unit=devlite-public-4i4yb2kf --wait --pipe --collect --property=MemoryMax=2684354560 --property=MemorySwapMax=1073741824 --property=CPUQuota=100% --property=TasksMax=128 --property=RuntimeMaxSec=10800 --property=TimeoutStopSec=60 --property=KillMode=control-group --property=OOMPolicy=kill --property=ProtectSystem=strict --property=ProtectHome=read-only --property=ReadWritePaths=/home/magaton/DevLite-OS/work/release-4i4yb2kf --property=PrivateNetwork=yes --property=PrivateMounts=yes --property=NoNewPrivileges=yes --property=ProtectKernelTunables=yes --property=ProtectKernelModules=yes --property=ProtectControlGroups=yes --property=RestrictRealtime=yes --property=RestrictAddressFamilies=AF_UNIX '--property=CapabilityBoundingSet=CAP_SYS_ADMIN CAP_CHOWN CAP_DAC_OVERRIDE CAP_DAC_READ_SEARCH CAP_FOWNER CAP_FSETID CAP_MKNOD CAP_SETFCAP' /usr/bin/python3 /home/magaton/DevLite-OS/scripts/iniciar-publico-isolado-root.py --job /home/magaton/DevLite-OS/work/release-4i4yb2kf --approval-sha256 5407b89b6a297f25e70619185f5c412134200257c52167272d293368f15ed7e9 --execute-authorized -- unshare --mount --propagation private --pid --fork --kill-child --mount-proc --net --ipc --uts /usr/bin/python3 /home/magaton/DevLite-OS/scripts/aplicar-publico-root.py --job /home/magaton/DevLite-OS/work/release-4i4yb2kf --approval-sha256 5407b89b6a297f25e70619185f5c412134200257c52167272d293368f15ed7e9 --execute-authorized
```

Mesmos limites: 2,5 GiB RAM, 1 GiB swap, uma CPU, 128 tarefas, três horas. Nenhum ReadWritePaths para diretórios pais; apenas este novo job. Nenhuma rede ou D-Bus é habilitado para a consulta interna.

Resultados esperados: isolation-systemd.json, isolation-unshare.json e isolation-diagnostic-result.json, com stdout/stderr/returncode reais e hashes das fontes. Se qualquer prova crítica falhar, não reduzir os guards nem executar aplicação.

## Aplicação futura também selada, ainda não autorizada

Contrato separado preparado para evitar refazer código após o diagnóstico:

Job: `/home/magaton/DevLite-OS/work/release-cezaiofx`
Contrato: `e62d4a700ff770fa24b0afe9b013c3b14eb841db60e5a5c3e9bdfd9d79f9c6b3`
Operação: apply-and-pack.

[Comando argv](../work/release-cezaiofx/public-command.json) e [contrato](../work/release-cezaiofx/public-contract.json). Exige autorização **separada** da proposta de diagnóstico. Gerará somente as camadas após validação completa; não gera ISO. Não reutilizar a aprovação do job antigo, cujo código não corresponde aos novos hashes.
