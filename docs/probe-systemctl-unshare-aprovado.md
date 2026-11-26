# Probe do isolamento aprovado — release-4i4yb2kf

**Execução autorizada concluída com retorno 0**, sem repetir o job. Duração 11min51s; CPU 2min14s; pico de memória informado pelo systemd-run 1,3G; swap 0B. O bloqueio de uso afetou somente uma consulta de acompanhamento: o probe continuou e foi retomada a leitura da mesma sessão, sem reiniciar a operação.

## Resultado real

- Consulta externa efetiva aprovada com ProtectSystem=strict, ProtectHome=read-only, PrivateMounts e único ReadWritePaths no job.
- Handoff root-owned selado, SHA-256 e vínculos ao contrato/execução aprovados na fase interna real.
- Namespaces e VFS validados diretamente, incluindo /home, /root e /run/user.
- Limites cgroup efetivos aprovados: 2,5 GiB RAM, 1 GiB swap, uma CPU e 128 tarefas.
- Nenhum clone, aplicação, empacotamento, pacote instalado ou ISO gerada. attempt permanece ausente.
- Hospedeiro íntegro, flags false e consultas posteriores sem unidades DevLite, loops ou mounts do projeto residuais.

## Erro reproduzido e preservado

A consulta legada interna retornou **1**, com stdout vazio e este stderr:

```text
Failed to connect to bus: No data available
```

O diagnóstico foi registrado sem usá-lo para aprovar ou reprovar o isolamento. A consulta externa funciona; a auditoria interna corrigida usa somente a evidência externa autenticada e as observações locais.

Explicação por análise de fonte: o systemd 255, ao consultar como root, tenta o socket local do manager e valida as credenciais do peer. O helper retorna ENODATA quando o PID recebido não é válido após tradução entre namespaces. Isso é consistente com o manager fora do namespace PID interno e a mensagem reproduzida. Essa análise não é um strace nem uma leitura direta do SO_PEERCRED nesta execução.

Referências primárias: [bus_check_peercred/bus_connect_system_systemd](https://github.com/systemd/systemd/blob/v255/src/shared/bus-util.c#L167-L214), [getpeercred](https://github.com/systemd/systemd/blob/v255/src/basic/socket-util.c#L807-L828) e [PID namespaces](https://man7.org/linux/man-pages/man7/pid_namespaces.7.html). Não foi habilitado D-Bus, rede ou acesso extra para fazer a consulta funcionar.

## Integridade das fontes confirmada

| Fonte | SHA-256 efetivamente relido | Resultado |
|---|---|---|
| base | 1afd8b0caba906a555099faca6066acf4826e9de14867358f9d908be6679f30b | Igual ao aceito |
| live | b69ca4b77ef71470aec0deb74b9bad54bbc1d25a83ae574ab318f6c03d288394 | Igual ao aceito |

Os dois hashes conferem com as imagens aceitas antes desta investigação. Assim, a confirmação bit a bit que estava pendente agora foi executada e aprovada, sem modificar as fontes.

[Relatório root-owned](../work/release-4i4yb2kf/isolation-diagnostic-result.json), [fase externa](../work/release-4i4yb2kf/isolation-systemd.json), [fase interna](../work/release-4i4yb2kf/isolation-unshare.json) e [verificação posterior](evidencias/probe-systemctl-unshare-execucao.json).

Código sem alterações após os 333 testes e a selagem; não houve repetição desnecessária da suíte. O contrato futuro continua válido.

## Próximo bloqueio real

Aplicação e integração exigem autorização própria. O probe de leitura não autorizou essas operações.

[Comando já selado para aplicação e empacotamento das camadas](autorizacao-aplicacao-apos-probe.md). ISO e testes de boot/instalação permanecem pendentes.
