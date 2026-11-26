# Fase 3A — preparação dos testes da ISO original

Data: 16/11/2026. **Preparação concluída; testes de boot e instalação ainda não executados.** Todas as operações desta fase foram de leitura ou criação de documentação/testes no projeto como magaton. Nenhuma VM, disco virtual, instalação, pacote, módulo KVM ou reconstrução foi criado/iniciado. O estado Git anterior foi preservado; nenhum commit foi criado.

Atualização posterior: o usuário adiou os testes manuais e autorizou a reconstrução experimental da [Fase 3B](fase3b-pipeline.md). Os estados abaixo registram a preparação da 3A, não impedem o experimento autorizado e não constituem aprovação de boot.

## Revisão das Fases 1 e 2

Revisados README, arquitetura, plano, decisões, recursos, segurança, documentação da base e camadas, scripts e matriz de aceitação. A autenticação fixa a impressão digital oficial e exige hash correto antes da inspeção. O inspetor abre a ISO como entrada e extrai cópias para work, não usa chroot nem executa conteúdo extraído. Não foi reexecutado nesta fase: já existem cópias e ele ocupa espaço, além de não testar boot.

A hierarquia `minimal.squashfs` → `minimal.live.squashfs` é selecionada no initrd; a fonte instalada é `minimal.squashfs`. O instalador é Desktop Bootstrap/Subiquity e a EFI é uma partição anexada. A matriz geral continua válida para o produto futuro; esta fase testa somente a base original, sem exigir ferramentas DevLite ainda não incorporadas. A indicação antiga de 37 GiB livres foi histórica: o filesystem atual tem 97 GiB.

Os validadores anteriores continuam aplicáveis; o estado atual acrescenta a subfase 3A sem autorizar build. A autenticação e o hash foram revalidados por leitura nesta fase; saída local em `reports/phase3a/validacao-iso.txt`. Os testes unitários não substituem o laboratório.

## Diagnóstico observado

| Verificação | Resultado em 16/11/2026 |
|---|---|
| Usuário de trabalho | magaton, UID 1000 |
| Arquitetura | x86_64 |
| CPU | 2 CPUs apresentadas, somente CPU 0 online |
| Extensões de virtualização visíveis | nem vmx nem svm |
| `/dev/kvm` | ausente |
| Parâmetros nested de kvm_intel/kvm_amd | indisponíveis; módulos não carregados |
| QEMU, qemu-img, virsh e virt-host-validate | executáveis ausentes |
| qemu-system-x86, qemu-utils, ovmf, libvirt-daemon-system | dpkg-query não encontrou pacotes instalados |
| Firmware OVMF nos caminhos usuais | não encontrado |
| RAM / disponível na medição | 3,8 GiB / aproximadamente 2,7 GiB |
| Swap | 3,8 GiB |
| Espaço livre | aproximadamente 78 GiB (79 GiB no arredondamento de df) |

Conclusão: **KVM aninhado não está utilizável no ambiente acessível**. Não é possível confirmar daqui a opção de virtualização do Workstation, o firmware físico ou a causa da ausência das extensões. A ausência do parâmetro nested isoladamente também não provaria que a opção está desligada. Não houve modprobe nem abertura/ioctl de `/dev/kvm` para testar aceleração.

Há sinais de identificação distintos: lscpu informa hipervisor Microsoft; DMI informa Xen / HVM domU. Isso limita a identificação da topologia real a partir deste acesso. Não concluir automaticamente que Hyper-V/VBS esteja ativo no Windows do usuário; confirmar no host, se necessário. Evidências reproduzíveis em `reports/phase3a/diagnostico-virtualizacao.json`.

## Ambiente recomendado

**VMware Workstation diretamente no Windows**, com duas VMs novas e independentes. Evita a camada de virtualização dentro do Ubuntu e permite dedicar RAM à VM de teste. A capacidade do Windows não foi inspecionada: confirmar espaço e memória antes de criar qualquer VM. Se necessário, desligar manualmente a VM Ubuntu Server antes do ensaio, após salvar o trabalho; não há desligamento automático neste projeto.

| Alternativa | Avaliação |
|---|---|
| Workstation no Windows | recomendada; já faz parte do ambiente informado; validar versão e recursos do host |
| QEMU/KVM no Ubuntu | bloqueada por ausência de ferramentas, extensões e /dev/kvm; RAM atual insuficiente para VM de teste de 4 GiB mais host |
| QEMU com emulação TCG | pode operar sem VT-x/AMD-V, mas ferramentas ausentes e custo de CPU/memória tornam a alternativa inadequada agora |

A opção “Virtualize Intel VT-x/EPT or AMD-V/RVI” seria necessária para investigar um hipervisor aninhado, não para iniciar um Xubuntu comum diretamente no Workstation. Não modificar essa opção ou recursos de segurança do Windows nesta fase. A [documentação Broadcom](https://knowledge.broadcom.com/external/article/389469/) descreve conflitos possíveis; ela não é prova de que ocorram neste host. A [documentação QEMU](https://www.qemu.org/docs/master/system/invocation.html) distingue aceleradores KVM e TCG.

## Dependências

No caminho recomendado: Workstation funcional com BIOS e UEFI, PowerShell com Get-FileHash e um meio de copiar a ISO (scp do Windows, se disponível, ou SFTP). Sem necessidade de instalar pacotes no Ubuntu Server. Reservar 4 GiB de RAM para a VM de teste e margem para o Windows; 8 GiB totais no host é uma referência inicial, 16 GiB oferece mais folga. Ajustar apenas após conferir o host.

Cada VM terá 2 vCPU quando disponíveis, 4 GiB RAM, um único disco virtual novo de 40 GiB, CD/DVD virtual com a ISO e placa de rede NAT. Discos dinâmicos crescem com uso; reservar orçamento de até 40 GiB por VM mais ISO e logs, sem contar snapshots. Executar uma VM de teste por vez; nunca usar o disco da VM de desenvolvimento ou disco físico/raw. Sem pastas compartilhadas, USB automático, clipboard compartilhado ou passthrough de dispositivos nesta linha de base.

Para considerar QEMU futuramente: aprovação para instalar `qemu-system-x86`, `qemu-utils` e `ovmf`, firmware BIOS disponível, VT-x/AMD-V exposto, KVM funcional e permissões adequadas, mais RAM e console gráfico acessível. Libvirt/virt-manager são opcionais e não necessários a um comando QEMU direto. Não foram preparados lançadores QEMU porque o ambiente atual não atende aos requisitos.

## Execução permitida agora: verificações de leitura

Na raiz do projeto, como magaton:

```sh
python3 scripts/diagnostico-virtualizacao.py
python3 scripts/verificar-projeto.py
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 scripts/validar-iso.py
```

O diagnóstico não inicia processos de virtualização nem altera permissões. A validação do hash pode levar minutos em armazenamento lento. Interromper o procedimento se a validação da base falhar.

## Procedimento futuro — somente após autorização para criar/iniciar VMs e instalar

### Transferir e conferir a cópia

Copiar a ISO intacta para um diretório de laboratório no Windows; manter a original em `sources/`. Exemplo manual em PowerShell, substituindo IP_DO_UBUNTU e criando previamente o diretório de destino:

```powershell
scp "magaton@IP_DO_UBUNTU:/home/magaton/DevLite-OS/sources/xubuntu-24.04.5-minimal-amd64.iso" "C:\DevLite-Lab\xubuntu-24.04.5-minimal-amd64.iso"
$isoTeste = "C:\DevLite-Lab\xubuntu-24.04.5-minimal-amd64.iso"
$hashTeste = (Get-FileHash -LiteralPath $isoTeste -Algorithm SHA256).Hash.ToLowerInvariant()
if ($hashTeste -ne "9d47f975696ce496b8be882b6d7cc9079c1ea89fb625ac2c86caa63a4f180033") { throw "SHA-256 divergente: interromper" }
```

Não é necessário baixar outra ISO. Registrar o hash da cópia utilizada e não apontar o teste para uma imagem personalizada.

### Criar o laboratório manualmente

1. No Workstation, criar `DevLite-Original-BIOS`, escolhendo instalação do sistema operacional depois. Evitar Easy Install e qualquer resposta automática, para observar o instalador original.
2. Selecionar Linux / Ubuntu 64-bit, recursos acima e disco **novo** de 40 GiB na pasta exclusiva dessa VM. Conferir que há somente um disco, sem reaproveitar VMDK nem usar disco físico.
3. Com a VM desligada, selecionar firmware BIOS nas opções avançadas. Os nomes exatos dos menus variam com a versão do Workstation. Registrar versão, hardware virtual, controlador do disco, RAM, CPU, rede e pasta da VM.
4. Repetir para `DevLite-Original-UEFI`, com outro disco novo e firmware UEFI; Secure Boot desligado para a linha de base. Não converter a VM BIOS nem reaproveitar seu disco. Um ensaio UEFI com Secure Boot ativado é adicional e não substitui esse caso.
5. Anexar a cópia conferida da ISO ao CD/DVD virtual. Antes do primeiro power-on, revisar hardware e disco. A criação, o power-on e a instalação dependem de autorização; nada disso é feito por script.

### Inicializar e observar o live

Para cada VM, separadamente:

1. Iniciar pelo CD/DVD virtual e selecionar a entrada normal de experimentar/instalar. Registrar tempo até o desktop, eventuais erros, tela e entrada usada. Se precisar de “safe graphics”, registrar como limitação; não aprovar silenciosamente o boot normal.
2. No terminal do **guest de teste**, executar comandos somente de leitura:

```sh
test -d /sys/firmware/efi && echo UEFI || echo BIOS
cat /proc/cmdline
printf '%s\n' "$XDG_CURRENT_DESKTOP"
pgrep -a xfce4-session
locale
findmnt -no SOURCE,FSTYPE /
free -h
```

3. Confirmar XFCE com painel, menu, gerenciador de arquivos, terminal, mouse e teclado. Digitar acentos e ç em editor sem salvar no host. Registrar o idioma efetivo: o live original pode iniciar em inglês. Não exigir a identidade DevLite nesta ISO.
4. Abrir o instalador Desktop Bootstrap e selecionar português brasileiro e teclado brasileiro, verificando a prévia. Registrar a revisão com `snap list ubuntu-desktop-bootstrap` se o comando estiver disponível. Não atualizar o instalador quando houver opção de continuar com o embarcado; se atualizar automaticamente, registrar a revisão e repetir uma linha de base controlada antes de atribuir o resultado apenas à ISO.

### Instalar somente no disco descartável do guest

1. O teste obrigatório inicial usa NAT, com idioma pt-BR e sem seleção de software de terceiros ou atualizações opcionais durante instalação. A rede pode fornecer traduções; registrar isso. Não executar apt, snap refresh ou instalar ferramentas extras manualmente nesta linha de base. A futura autorização de instalação deve abranger o que o instalador baixar dentro do guest.
2. Na seleção do disco, conferir que existe um único disco vazio de aproximadamente 40 GiB, com modelo virtual e tamanho iguais aos configurados. Se houver disco extra ou tamanho inesperado, cancelar e revisar o hardware da VM.
3. A opção de apagar disco só será usada **dentro dessa VM descartável autorizada**, para seu disco novo. Nunca executar o instalador no Ubuntu Server ou anexar volumes do host. Deixar o instalador criar as partições automaticamente; sem comandos manuais de particionamento.
4. Criar uma conta exclusiva de laboratório, com senha temporária não reutilizada; não registrar a senha em arquivos ou capturas. Manter escolhas iguais entre BIOS e UEFI. Registrar modo de instalação, acesso à rede, mudanças automáticas do instalador, duração e erros.
5. Ao terminar, desligar quando solicitado ou usar o fluxo de reinicialização do instalador. Desconectar o CD/DVD virtual ou desmarcar sua conexão no próximo boot. Confirmar no Workstation que a ISO não está mais conectada.

### Validar o sistema instalado

1. Iniciar **sem ISO**, no mesmo firmware do ensaio. Entrar com a conta de laboratório e confirmar o XFCE e pt-BR. Registrar também a resolução e funcionamento de teclado/mouse.
2. Executar somente no guest instalado:

```sh
test -d /sys/firmware/efi && echo UEFI || echo BIOS
findmnt -no SOURCE,FSTYPE /
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS
printf '%s\n' "$XDG_CURRENT_DESKTOP"
pgrep -a xfce4-session
locale
cat /etc/os-release
dpkg --audit
systemctl --failed --no-pager
```

3. A raiz deve estar no disco virtual instalado, sem squashfs/overlay de live. Revisar falhas de serviços: erros que afetem boot, sessão ou instalação bloqueiam aprovação; mensagens sem impacto exigem justificativa, não descarte automático.
4. Criar manualmente um pequeno arquivo de teste no home **do guest**, salvar, reiniciar mais uma vez sem ISO e conferir o conteúdo e as configurações de idioma/teclado. Essa escrita faz parte do ensaio futuro autorizado, não é executada nesta fase.
5. Desligar pelo menu XFCE e confirmar que a VM encerra normalmente. Preservar evidências antes de descartar o laboratório. Remover apenas arquivos da pasta exclusiva da VM após revisão manual; nenhum script de limpeza foi criado.

### Casos adicionais

Depois da linha de base, testar instalação sem rede em disco novo ou VM descartável independente, quando a base permitir. Registrar separadamente limitações de pacotes de idioma offline. Falha offline não pode ser declarada sucesso; ela bloqueia qualquer alegação de instalação offline, mas não transforma um teste NAT aprovado em teste offline. Secure Boot e safe graphics também têm resultados separados. Não reutilizar o resultado de um cenário para aprovar outro.

## Critérios de aprovação obrigatórios para BIOS e UEFI

| ID do relatório | Resultado esperado |
|---|---|
| isolamento_disco | VM exclusiva e único disco virtual novo de 40 GiB conferidos antes de instalar |
| hash_iso | SHA-256 da cópia usada corresponde à base autenticada |
| boot_live | boot normal chega ao desktop sem panic, shell de emergência ou travamento |
| firmware_live | /sys/firmware/efi corresponde ao BIOS ou UEFI previsto |
| xfce_live | sessão XFCE, painel, menu, terminal e arquivos utilizáveis |
| teclado_live | entrada, acentos e layout selecionado funcionam; idioma original registrado |
| instalador | Desktop Bootstrap abre e oferece a fonte Xubuntu Minimal sem falha crítica |
| instalacao | instalação termina no disco descartável e no modo de rede registrado |
| boot_sem_iso | login após remoção da ISO, com raiz no disco instalado |
| firmware_instalado | firmware confirmado e mantido após instalar |
| xfce_instalado | XFCE funcional após instalação e login |
| locale_instalado | pt_BR.UTF-8 e teclado brasileiro funcionam; faltas de tradução são identificadas e resolvidas ou mantêm o critério pendente |
| persistencia_reboot | segundo boot sem ISO preserva arquivo e configurações do guest |
| desligamento | desligamento da VM pelo sistema ocorre normalmente |

Registrar duração e memória observada; não impor desempenho de produção com base em uma execução. Mais de 10 minutos sem progresso visível exige investigação e registro, não aprovação automática; o limite não prova que a ISO está defeituosa. Erro de hash, firmware errado, disco inesperado, kernel panic, falha de instalação ou boot instalado falhando interrompem o respectivo caso.

Cada critério exige status `aprovado` e evidência textual (saída relevante, captura ou caminho de log sanitizado). `pendente`, `falhou` e critério ausente impedem aprovação documental. Logs/capturas ficam em `reports/phase3a/`, sem senhas, tokens ou dados pessoais. Consultar o modelo [tests/modelo-relatorio-iso.json](../tests/modelo-relatorio-iso.json), que vem integralmente pendente.

Copiar o modelo para `reports/phase3a/resultado-iso.json`, preencher as execuções reais e validar:

```sh
python3 scripts/validar-relatorio-iso.py reports/phase3a/resultado-iso.json
```

O comando apenas lê o relatório. Retorna 1 em erro/pendência e 0 quando o preenchimento declara todos os critérios aprovados para ambas as VMs. Não executa ensaios, não autentica capturas e não substitui revisão humana. Os campos data, operador, versão do Workstation/Windows, VM, CPU/RAM/disco, rede, Secure Boot, modo de instalação, revisão/atualização do instalador e idioma live são obrigatórios.

## Resultados e próximos passos

| Atividade | Estado |
|---|---|
| Revisão e diagnóstico do Ubuntu | concluídos |
| QEMU/KVM aninhado utilizável | não disponível no ambiente observado |
| Plano BIOS/UEFI e instalação descartável | preparado |
| Testes automatizados dos scripts | 15 aprovados no conjunto das Fases 2 e 3A |
| Boot BIOS / instalação / reinicialização | pendentes de autorização e execução manual |
| Boot UEFI / instalação / reinicialização | pendentes de autorização e execução manual |
| Secure Boot / offline adicional | não executados |
| Reconstrução personalizada | não iniciada; continua sem autorização |

Próxima ação: confirmar os recursos do Windows e autorizar a criação/execução do laboratório e instalação nos discos descartáveis descritos. Após evidências reais aprovadas de BIOS e UEFI, solicitar autorização específica para a Fase 3B de reconstrução mínima. Aprovação de testes não autoriza automaticamente build.
