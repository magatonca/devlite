# Aplicação Modern — proposta delimitada

## Evidências reaproveitadas

Validação read-only prototype-review-wt6wd6a1 concluída em 44 segundos, retorno 0. Base e Live passaram PHP 8.3.6, lint dos quatro arquivos, 25 verificações PHP cada, modelo simulado e importação GTK3. Fontes sem mudanças de metadados e configuração crítica do host preservada. Sem testes gráficos, HTTP ou MariaDB; não é homologação do Adminer ou Control 2.0.

507 testes automatizados aprovados após preparar o adaptador Modern. Fontes históricas e pipeline do navegador não modificados. Mudanças em prototypes/modern_adapter.py, scripts/aplicar-modern-isolado.py, primeira sessão do protótipo e testes correspondentes. Não há aplicação executada.

## Escopo a aprovar

Criar cópias descartáveis das imagens aceitas work/release-browser-2f24tvsg/attempt/{base,live}.ext4 exclusivamente em /home/magaton/DevLite-OS/work/modern-apply-fr800yl6/attempt/{base,live}.ext4. Cada imagem tem 12 GiB lógicos. Cópia esparsa/reflink quando disponível, sem depender disso para o orçamento. Não apagar ou substituir fontes. Montagens privadas RW somente das cópias, em attempt/base-root e attempt/live-root; fontes continuam fora da exceção de escrita do job. Sem chroot, APT, programas do guest, rede externa, pacotes ou serviços novos. e2fsck -f -n nas cópias desmontadas, sem reparos automáticos.

Aplicar exatamente os sete arquivos em cada visão:

- `etc/xdg/xdg-xubuntu/xfce4/panel/default.xml`
- `etc/xdg/xdg-xubuntu/xfce4/xfconf/xfce-perchannel-xml/xsettings.xml`
- `etc/xdg/xdg-xubuntu/xfce4/xfconf/xfce-perchannel-xml/xfwm4.xml`
- `etc/xdg/xfce4/xfconf/xfce-perchannel-xml/xsettings.xml`
- `etc/lightdm/lightdm-gtk-greeter.conf`
- `usr/libexec/devlite-first-session`
- `usr/share/backgrounds/devlite/devlite-modern.svg`


Greybird-dark em ambos os conjuntos de padrões XFCE existentes; plugins/atalhos e configurações não visuais preservados. Wallpaper por monitor descoberto e preferência GTK4 escura via gsettings na primeira sessão opt-in de novos usuários, sem modificar perfil dconf ou compilar banco nesta aplicação. Preservar contas com marcadores anteriores ou keep-user-settings. Os perfis existentes não são migrados automaticamente. O rascunho dconf continua apenas protótipo, excluído da aplicação.

Antes da primeira escrita, validar preimages/payloads. Comparar snapshots completos antes/depois para rejeitar qualquer alteração fora dos sete arquivos e seus diretórios novos. Manter UID/GID, xattrs e metadados das entradas preservadas; recusar hardlinks e IMA/EVM nas entradas alteradas. Validar dpkg status, ext4 e hashes dos resultados. Não iniciar serviços ou executar o novo first-session nessa etapa.

## Recursos e recuperação

Espaço livre atual: 85.52 GiB. Gate inicial: 76,16 GiB; reserva operacional mínima 20 GiB. Novas cópias: cerca de 10,07 GiB físicos estimados, até 24 GiB lógicos; sem baixar componentes. Verificação adicional do orçamento de empacotamento após as duas cópias.

Limites: 2,5 GiB RAM, 1 GiB swap, uma CPU, 128 tarefas e três horas. ProtectSystem=strict e ProtectHome=read-only; única exceção de escrita é o job. Sem sobrescrita, limpeza ou tentativa automática em caso de falha. Quarentena e relatório em result.json; namespace encerra montagens. Fontes aceitas permanecem disponíveis para recuperação.

Risco: montagem privilegiada RW e alteração das cópias; auditoria integral e e2fsck podem demorar. Não são testes de boot/login, aparência real ou persistência. Nenhuma ISO ou SquashFS será gerada por este comando.

## Contrato e comando exato

Contrato: b953235452cb0ab8cbceb3b79a361b0f873576140d5be123adbb8e685e962a77

```bash
sudo systemd-run --unit=devlite-modern-apply-fr800yl6 --wait --pipe --collect --property=ProtectSystem=strict --property=ProtectHome=read-only --property=ReadWritePaths=/home/magaton/DevLite-OS/work/modern-apply-fr800yl6 --property=PrivateNetwork=yes --property=PrivateMounts=yes --property=NoNewPrivileges=yes --property=ProtectKernelTunables=yes --property=ProtectKernelModules=yes --property=ProtectControlGroups=yes --property=MemoryMax=2684354560 --property=MemorySwapMax=1073741824 --property=TasksMax=128 --property=CPUQuota=100% --property=RuntimeMaxSec=10800 --property=KillMode=control-group --property=OOMPolicy=kill --property=RestrictAddressFamilies=AF_UNIX '--property=CapabilityBoundingSet=CAP_SYS_ADMIN CAP_SYS_CHROOT CAP_SETPCAP CAP_SETUID CAP_SETGID CAP_KILL CAP_CHOWN CAP_DAC_OVERRIDE CAP_DAC_READ_SEARCH' unshare --mount --propagation private --pid --fork --kill-child=KILL --mount-proc --net --ipc --uts /usr/bin/python3 /home/magaton/DevLite-OS/scripts/aplicar-modern-isolado.py --job /home/magaton/DevLite-OS/work/modern-apply-fr800yl6 --approval-sha256 b953235452cb0ab8cbceb3b79a361b0f873576140d5be123adbb8e685e962a77 --execute-authorized
```

Depois da aprovação e execução, continuar a preparação não privilegiada da reconciliação/empacotamento. Operações privilegiadas seguintes e geração única da ISO dependem de aprovação específica. Adminer e Control 2.0 continuam fora desta aplicação, sujeitos aos gates reais de compatibilidade/segurança/funcionamento. Preservar o Control homologado.
