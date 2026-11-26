# Proposta de aplicação e integração pública — aprovação necessária

> Revisão substituída após falha de isolamento, sem aplicação às imagens. Usar o [novo perfil com ProtectHome=read-only e contrato revisado](correcao-isolamento-publico.md). Não executar este comando antigo.

**Preparada, não executada.** Solicitação de uma única operação privilegiada, reunindo aplicação mínima e reconstrução das camadas, sem gerar ISO.

Job: `/home/magaton/DevLite-OS/work/release-iy8j5anl`
SHA-256 de public-contract.json: `74c4ba25154ab0c50d9da658e35bec39173359c284571104e969807bae0eff9d`

## Escopo exato

1. Confirmar código, planos, payload e recibo root-owned das imagens Base/Live aceitas de work/phase4b3-wnej6dpv/attempt. Validar seus hashes antes da cópia.
2. Criar novas cópias ext4 esparsas somente em `/home/magaton/DevLite-OS/work/release-iy8j5anl/attempt`, sem alterar fontes aceitas. A cópia de segurança é a fonte preservada; falha põe a tentativa nova em quarentena, sem excluir artefatos anteriores.
3. Montar somente as cópias graváveis em namespace privado, com nodev/nosuid/noexec/noatime. Copiar os 243 MiB preparados e gerar proveniência externa determinística; UID/GID/modos/xattrs exigem root. Colisões com arquivos existentes falham antes de escrever.
4. Provar por inventários completos que todos os arquivos anteriores, suas permissões, links e atributos continuam iguais. Restaurar timestamps nanosegundos dos diretórios existentes. Confirmar dpkg inalterado. Nenhum APT, chroot, maintainer script ou programa adquirido será executado; serviços não serão iniciados.
5. Desmontar as cópias, e2fsck somente leitura e aceitar o par apenas após aprovação de ambas.
6. Usar o backend de empacotamento já selado para reconciliar Base/Live, whiteouts e manifests, reconstruir SquashFS, reextrair, comparar integralmente e provar composição pelo kernel. Preservar instalador original. A ISO e o boot não são reconstruídos nessa operação.
7. Publicar layers-ready.json/public-result.json somente com sucesso. O consumidor futuro deve exigir public-result status public_layers_verified e conferir os hashes dos dois contratos e recibos, não apenas a existência dos SquashFS.

## Isolamento e limites

Filesystem do hospedeiro somente leitura (ProtectSystem=strict), comprovado pelo VFS; única exceção gravável é o job. Namespaces de mounts, PID, rede, IPC e UTS privados; sem interfaces externas, NoNewPrivileges e capabilities limitadas aos metadados/mounts necessários. Limites efetivos cgroup: **2,5 GiB RAM, 1 GiB swap, uma CPU, 128 tarefas, até três horas**. Compressão existente: um processo e 256 MiB.

A flag exigida pelo empacotador antigo será true **somente em uma cópia do config ligada por bind privado somente leitura**. A configuração real do projeto permanece false; nenhum grant global é habilitado. Se o processo morrer, o namespace se encerra e o bind privado desaparece. Mounts/loops da tentativa são limitados às suas cópias e liberados no encerramento do namespace; conferir ausência residual após o retorno do serviço.

Exigir **70 GiB livres ao iniciar**, mantendo o mínimo de **56 GiB** entre as operações e a fórmula conservadora adicional do empacotador. Não baixar outros arquivos, instalar pacotes, apagar artefatos, criar VMs ou modificar partições/LVM.

A operação usa kernel e ferramentas privilegiadas do hospedeiro, com código confiável selado; não equivale a uma VM de segurança. O runner novo foi validado em testes não privilegiados, mas sua compatibilidade real com estas propriedades systemd só será comprovada na execução autorizada. Se algum guard falhar, não afrouxar opções nem retomar automaticamente com outro contrato.

## Comando exato proposto

```sh
sudo systemd-run --unit=devlite-public-iy8j5anl --wait --pipe --collect --property=MemoryMax=2684354560 --property=MemorySwapMax=1073741824 --property=CPUQuota=100% --property=TasksMax=128 --property=RuntimeMaxSec=10800 --property=TimeoutStopSec=60 --property=KillMode=control-group --property=OOMPolicy=kill --property=ProtectSystem=strict --property=ReadWritePaths=/home/magaton/DevLite-OS/work/release-iy8j5anl --property=PrivateNetwork=yes --property=PrivateMounts=yes --property=NoNewPrivileges=yes --property=ProtectKernelTunables=yes --property=ProtectKernelModules=yes --property=ProtectControlGroups=yes --property=RestrictRealtime=yes --property=RestrictAddressFamilies=AF_UNIX '--property=CapabilityBoundingSet=CAP_SYS_ADMIN CAP_CHOWN CAP_DAC_OVERRIDE CAP_DAC_READ_SEARCH CAP_FOWNER CAP_FSETID CAP_MKNOD CAP_SETFCAP' unshare --mount --propagation private --pid --fork --kill-child --mount-proc --net --ipc --uts /usr/bin/python3 /home/magaton/DevLite-OS/scripts/aplicar-publico-root.py --job /home/magaton/DevLite-OS/work/release-iy8j5anl --approval-sha256 74c4ba25154ab0c50d9da658e35bec39173359c284571104e969807bae0eff9d --execute-authorized
```

Root é indispensável para os namespaces, montagens das cópias, UID/GID, xattrs/capabilities, devices/whiteouts de delta e auditoria das fontes privadas. Não autoriza downloads, instalação por gerenciador, execução de programas nas imagens ou geração de ISO.

## Verificação antes da execução

```sh
sha256sum /home/magaton/DevLite-OS/work/release-iy8j5anl/public-contract.json
```

O comando read(job, hash) revalida todos os hashes de código e planos, além do payload e dos metadados do instalador. Contrato: [public-contract.json](../work/release-iy8j5anl/public-contract.json). Lista argv: [public-command.json](../work/release-iy8j5anl/public-command.json). [296 testes aprovados](../reports/testes-aplicacao-publica-preparada.txt); nenhuma validação prática de boot, instalação, Control/polkit ou persistência aprovada.

Após a operação, continuar automaticamente verificações e preparação não privilegiadas. A geração de **uma única ISO candidata** exigirá aprovação específica com seus inputs e comando; não gerar uma reprodução adicional.
