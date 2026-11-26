# Correção pontual do isolamento — release-iy8j5anl

> Esta revisão parou na consulta interna systemctl, antes das imagens. Usar a [correção do handoff e os novos contratos](correcao-systemctl-unshare.md); não repetir o comando antigo.

**Código corrigido e novo contrato preparados. Nenhuma aplicação, serviço de teste, montagem ou namespace real foi iniciado nesta investigação.**

## Causa e limites da evidência

Instalado: systemd 255 (255.4-1ubuntu8.18). O perfil original tinha ProtectSystem=strict, PrivateMounts=yes e ReadWritePaths somente no job, mas **não configurava ProtectHome**.

A implementação do [systemd 255, namespace.c](https://github.com/systemd/systemd/blob/v255/src/core/namespace.c#L190-L203) deixa /home, /root e /run/user graváveis para que ProtectHome os controle separadamente. Portanto, o perfil original tinha uma lacuna real na proteção do projeto em /home. O erro é consistente com essa lacuna; não há base para classificar o detector como falso positivo. Não foram gravados os caminhos individuais da falha, por isso não se pode afirmar que um caminho específico foi observado gravável naquela execução.

A unidade antiga foi coletada: systemctl show retorna LoadState=not-found. ProtectSystem=no, PrivateMounts=no e campos vazios exibidos agora são defaults de uma unidade inexistente, **não opções efetivas da execução anterior**. O journal confirma status 1; os mounts do processo encerrado não foram preservados.

PrivateMounts e unshare --mount criam/copiam namespaces e controlam propagação; não convertem mounts graváveis em somente leitura. O namespace filho herda o layout do serviço. Fonte complementar: [systemd.exec 255](https://www.freedesktop.org/software/systemd/man/255/systemd.exec.html). As permissões do namespace normal do Ubuntu Server continuam independentes: ele não deve ser remontado globalmente como readonly.

## Correção sem afrouxar isolamento

- Acrescentado **ProtectHome=read-only**. Mantidos ProtectSystem=strict, PrivateMounts=yes e todas as opções do unshare.
- ReadWritePaths continua com **um único caminho**, o diretório do novo job. Não foi adicionado /home, o projeto inteiro, work/ ou o job antigo.
- Verificação VFS somente leitura mantida e estendida a /home, /root e /run/user. Exceções de acesso e caminhos não comprovados continuam bloqueando.
- Erros de filesystem passam a conter os caminhos graváveis/não comprovados e suas observações.
- Novo entrypoint registra propriedades efetivas do serviço e mountinfo **antes do unshare**. O worker repete a captura **depois do unshare**, antes de criar attempt ou tocar em imagens.
- A coleta confere LoadState, ProtectSystem, ProtectHome, único ReadWritePaths, PrivateMounts, PrivateNetwork, NoNewPrivileges e limites. Divergência bloqueia; não executar fallback com menos proteção.

Na futura execução, isolation-systemd.json e isolation-unshare.json ficarão no novo job, contendo namespaces, mountinfo completo, flags VFS, paths resolvidos e propriedades retornadas pelo manager. A configuração real só estará comprovada após essas capturas aprovadas. A coleta é leitura, exceto por esses relatórios dentro do job; não tenta escrever fora do job para testar permissões.

As APIs /dev, /proc e /sys seguem suas restrições próprias; a exceção regular de ReadWritePaths é exclusivamente o job. Nenhuma mudança global no filesystem do hospedeiro é proposta.

## Imagens e integridade

O erro ocorreu antes da criação de attempt. Conferidos: o job antigo não contém attempt/pack-attempt nem imagens de saída, e o novo job também não. Pela ordem do código e pelo ponto da exceção, o controlador **não chegou a copiar, montar ou modificar Base/Live**.

Os hashes físicos das fontes privadas não foram relidos com sudo nesta investigação. Não declarar nova comparação bit a bit que não foi executada. Os hashes aceitos continuam vinculados ao novo contrato; a operação autorizada os verificará antes da cópia. Arquivos críticos do hospedeiro, contrato experimental histórico e o JSON do contrato antigo conferidos e preservados.

## Testes

**310 testes passaram**, incluindo 14 regressões novas: home gravável apesar de strict bloqueia; home readonly com job gravável passa; escopo único ReadWritePaths; opções do unshare preservadas; propriedades de unidade coletada não aceitas; captura nas duas fases; erro com paths persistido; nenhum namespace filho invocado após preflight bloqueado; comando diferente do contrato recusado.

[Saída integral](../reports/testes-correcao-isolamento-publico.txt). Testes usam fixtures e mocks; não são homologação real do isolamento corrigido.

## Novo contrato e comando exato — aprovação necessária

Job: `/home/magaton/DevLite-OS/work/release-g_ezd8xj`

SHA-256 de public-contract.json: `c598d14fd3b4d4d19135c89d2593be80d669cac83958e2bf4c01d1cef636d23a`

```sh
sudo systemd-run --unit=devlite-public-g_ezd8xj --wait --pipe --collect --property=MemoryMax=2684354560 --property=MemorySwapMax=1073741824 --property=CPUQuota=100% --property=TasksMax=128 --property=RuntimeMaxSec=10800 --property=TimeoutStopSec=60 --property=KillMode=control-group --property=OOMPolicy=kill --property=ProtectSystem=strict --property=ProtectHome=read-only --property=ReadWritePaths=/home/magaton/DevLite-OS/work/release-g_ezd8xj --property=PrivateNetwork=yes --property=PrivateMounts=yes --property=NoNewPrivileges=yes --property=ProtectKernelTunables=yes --property=ProtectKernelModules=yes --property=ProtectControlGroups=yes --property=RestrictRealtime=yes --property=RestrictAddressFamilies=AF_UNIX '--property=CapabilityBoundingSet=CAP_SYS_ADMIN CAP_CHOWN CAP_DAC_OVERRIDE CAP_DAC_READ_SEARCH CAP_FOWNER CAP_FSETID CAP_MKNOD CAP_SETFCAP' /usr/bin/python3 /home/magaton/DevLite-OS/scripts/iniciar-publico-isolado-root.py --job /home/magaton/DevLite-OS/work/release-g_ezd8xj --approval-sha256 c598d14fd3b4d4d19135c89d2593be80d669cac83958e2bf4c01d1cef636d23a --execute-authorized -- unshare --mount --propagation private --pid --fork --kill-child --mount-proc --net --ipc --uts /usr/bin/python3 /home/magaton/DevLite-OS/scripts/aplicar-publico-root.py --job /home/magaton/DevLite-OS/work/release-g_ezd8xj --approval-sha256 c598d14fd3b4d4d19135c89d2593be80d669cac83958e2bf4c01d1cef636d23a --execute-authorized
```

Verificação não privilegiada dos arquivos revisados:

```sh
cd /home/magaton/DevLite-OS
sha256sum --check config/public-isolation-review.sha256
```

O entrypoint valida todo o código selado antes de continuar. Os novos relatórios não sobrescrevem os antigos. A aprovação anterior vinculada ao código antigo não é reutilizada.

Escopo proposto: preflight real das propriedades/mounts corrigidos; somente se aprovado, aplicação aditiva em novas cópias Base/Live e reconstrução/auditoria das camadas. Mesmos limites: 2,5 GiB RAM, 1 GiB swap, uma CPU, 128 tarefas, três horas, 70 GiB iniciais e reserva de 56 GiB. Sem APT, instalação no hospedeiro, execução dos programas adquiridos, nova limpeza ou ISO.

A execução não foi repetida automaticamente. [Evidências e hashes](evidencias/correcao-isolamento-publico.json), [contrato](../work/release-g_ezd8xj/public-contract.json) e [argv](../work/release-g_ezd8xj/public-command.json).
