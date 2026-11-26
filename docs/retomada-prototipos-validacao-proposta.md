# Retomada — validação isolada proposta

497 testes Python aprovados; reports/testes-retomada-prototipos.txt. Sem alterações nas imagens aceitas, serviços ou ISO. As fontes e contratos históricos permanecem preservados. A limpeza e expansão já concluídas não foram repetidas.

## Alterações de desenvolvimento

- Adminer policy.php: parâmetros presentes com null são rejeitados, sem permitir contornar a política via isset. test-policy.php ampliado para destinos, usuários reservados, IPv6, Host e caminhos.
- Control 2.0: aba Serviços em ScrolledWindow para telas pequenas. Backend permanece simulado; testes no alvo conferirão operações do modelo e importação GTK3, não a renderização nem administração real.
- Modern: nova versão isolada de usr/libexec/devlite-first-session no payload do protótipo. Greybird-dark, wallpaper por propriedades de monitor descobertas, decorações escuras, animações desabilitadas e cursor DMZ. Marcadores existentes e keep-user-settings preservados. Arquivo histórico não substituído.
- Novo scripts/validar-prototipos-isolados.py: reutiliza verificador PHP aprovado e isolamento de leitura, com contrato específico. Novos testes em tests/test_prototype_review.py. Manifest Modern agora contém sete arquivos; os seis anteriores foram reutilizados sem regeneração.

## Operação proposta, aguardando aprovação

Montar sequencialmente as imagens aceitas Base e Live com loop,ro,noload,nodev,nosuid, dentro de namespaces privados. Mountpoints somente em /home/magaton/DevLite-OS/work/prototype-review-wt6wd6a1/base e /live. Montar proc somente leitura e tmpfs efêmeros run (8 MiB) e tmp (16 MiB) nas visões isoladas. Nenhuma escrita nas imagens originais. Escrita permanente exclusivamente neste job, com ProtectSystem=strict e ProtectHome=read-only.

Dentro das raízes somente leitura: PHP 8.3 versão/lint para os wrappers e artefato, execução somente do harness puro test-policy.php (sem incluir ou executar a aplicação Adminer), teste do modelo simulado de serviços e importação GTK3. Comandos de teste como UID/GID 65534, sem capabilities, NoNewPrivileges e limite CPU. Coletar configurações efetivas XFCE/LightDM/dconf/primeira sessão/Apache e integração do navegador nos dois contextos. Nenhum APT, pacote, daemon, autenticação de banco, servidor HTTP, rede externa, interface gráfica, compressão ou ISO.

Limites: 1 GiB RAM, 512 MiB swap, 64 tarefas, uma CPU, cinco minutos. Reserva mínima 20 GiB. Consumo persistente inferior a 16 MiB previsto; sem cópias de imagens. Se falhar: parar, preservar resultado e logs do job, sem retry automático; encerramento do namespace libera montagens. Não há alteração de dados para reverter nas imagens aceitas. Riscos remanescentes: uso privilegiado de mount/chroot e execução dos interpretadores do guest; imagens aceitas, comandos fechados, hashes e restrições reduzem o escopo, sem substituir os testes reais posteriores.

Contrato: 5458597739a4c73ee02fbf8ad544a79a75403e5ad7c5fc0f0af42f2e319552ed

## Comando exato

```bash
sudo systemd-run --unit=devlite-prototype-review-wt6wd6a1 --wait --pipe --collect --property=ProtectSystem=strict --property=ProtectHome=read-only --property=ReadWritePaths=/home/magaton/DevLite-OS/work/prototype-review-wt6wd6a1 --property=PrivateNetwork=yes --property=PrivateMounts=yes --property=NoNewPrivileges=yes --property=ProtectKernelTunables=yes --property=ProtectKernelModules=yes --property=ProtectControlGroups=yes --property=MemoryMax=1073741824 --property=MemorySwapMax=536870912 --property=TasksMax=64 --property=CPUQuota=100% --property=RuntimeMaxSec=300 --property=KillMode=control-group --property=OOMPolicy=kill --property=RestrictAddressFamilies=AF_UNIX '--property=CapabilityBoundingSet=CAP_SYS_ADMIN CAP_SYS_CHROOT CAP_SETPCAP CAP_SETUID CAP_SETGID CAP_KILL CAP_CHOWN CAP_DAC_OVERRIDE CAP_DAC_READ_SEARCH' unshare --mount --propagation private --pid --fork --kill-child=KILL --mount-proc --net --ipc --uts /usr/bin/python3 /home/magaton/DevLite-OS/scripts/validar-prototipos-isolados.py --job /home/magaton/DevLite-OS/work/prototype-review-wt6wd6a1 --approval-sha256 5458597739a4c73ee02fbf8ad544a79a75403e5ad7c5fc0f0af42f2e319552ed --execute-authorized
```

## Próximos gates

A leitura das configurações dará as preimages corretas para preparar patches Base/Live e contrato de aplicação. Ainda falta concluir o adaptador Modern de escrita e reconciliar as camadas. Adminer requer testes HTTP IPv4/IPv6, rejeição externa e banco reais em sandbox; Control 2.0 requer backend/Polkit efetivo e sessão GTK. Os testes propostos não os homologam. Não integrar esses componentes na candidata enquanto falharem os gates; manter Control homologado e Adminer opcional se necessário.

Antes de empacotar: aprovar operação específica de aplicação, validar todo o diff permitido, preservar instalador e software homologado, verificar delta/kernel/round-trip e espaço atualizado. Antes de gerar uma única ISO: suíte completa e aprovação específica. Espaço após expansão remove o bloqueio anterior, mas orçamento deverá ser medido novamente após os artefatos da aplicação.
