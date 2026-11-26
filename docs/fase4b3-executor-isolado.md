# Fase 4B.3 — executor isolado de pacotes

Estado: **implementado e validado por 105 testes automatizados, sem execução privilegiada**. Não foi executado chroot, unshare, mount, mkfs, probe, APT/dpkg de instalação ou controle real de serviços. Não houve download de pacotes, alteração de repositórios, nova ISO, remoção de artefatos anteriores ou commit. As edições, a geração do job e os testes ocorreram como magaton. O sistema de testes mantém as chamadas privilegiadas mockadas; o teste APT existente usa apenas simulação sobre fixture file:.

A implementação não é uma aprovação de segurança em runtime: integração com kernel/systemd, limites cgroup, loop devices, chroot e maintainer scripts permanece pendente de probe autorizado. Os comandos preparados não devem ser executados nesta fase.

## Arquitetura e arquivos

| Arquivo | Responsabilidade |
|---|---|
| scripts/executar-programas.py | preparar job; entradas separadas de probe, execução e recuperação, todas bloqueadas |
| pipeline/devlite/customize/executor_contract.py | validar transações Ubuntu, confinar paths, fixar hashes de código/plano/fontes, gerar comandos e inventários protegidos |
| pipeline/devlite/customize/executor.py | reautenticar índices, conferir debs/fontes, criar tentativa privada, supervisionar cgroups/disco, validar ext4 e aceitar o par |
| pipeline/devlite/customize/executor_worker.py | namespaces, fontes RO, cópia fiel em ext4 limitado, ambiente mínimo, chroot dos dois processos, capabilities, serviços e auditoria |
| pipeline/devlite/customize/guest_runner.py | programa local do alvo: probe ou transação offline exata, debconf, dpkg/APT, locale e validadores de configuração |
| pipeline/devlite/customize/reconcile.py | planejar diferenças entre duas visões completas e whiteouts, sem aplicação |
| tests/test_executor.py | 30 testes novos de bloqueios, falhas, metadados, serviços, APT e reconciliação |

Também foram atualizados config/projeto.json, scripts/verificar-projeto.py, README, plano/decisões e documentação de testes. A fixture APT da fase anterior foi corrigida para codificar underscores dos caminhos como %5f, evitando uma falha intermitente de descoberta do índice. Não foi adicionada dependência ao projeto.

## Contrato e preflight

O job copia o plano 4B.2 para um destino novo em work e fixa seu SHA-256, os hashes das duas SquashFS e os arquivos de implementação. Rejeita versões/arquiteturas/origens indevidas, nomes/caminhos inseguros, duplicações, providers proibidos, pacotes protegidos de boot/instalador e divergências de versões base/live. Só admite a transação Ubuntu; os três fornecedores externos permanecem bloqueados.

Antes da execução real, as cópias de InRelease/Packages são novamente autenticadas com a chave Ubuntu Archive fixada da 4B.2, incluindo validade/frescor. Cada operação do lock precisa existir nesses índices com versão, arquitetura, Filename, Size e SHA-256 exatos. Cada deb é conferido antes e depois da cópia para tentativa root 0700; sua identidade é novamente inspecionada dentro do alvo, sem executar scripts do arquivo no host. Metadata antiga, pacote ausente ou hash incorreto bloqueiam. Não há refresh, aquisição ou exceção de autenticação automática.

O backend exige root autorizado, systemd PID 1, cgroup v2, ferramentas presentes, hash do job correto e código ainda igual ao revisado. Não há fallback para rodar sem isolamento ou limites. Autorizações são independentes: probe_autorizado, executor_autorizado e recuperacao_autorizada. Todas estão false. A autorização da 4B.1 não se estende a nenhum desses modos. O hash na linha de comando identifica o material revisado; não substitui autorização humana nem uma assinatura criptográfica de terceiros.

## Isolamento de filesystem, processos e rede

Cada alvo roda sequencialmente em unidade systemd transitória e cgroup limitado. unshare cria namespaces mount, PID, network, IPC, UTS e cgroup com propagação privada. A base e a folha live são cópias verificadas montadas como SquashFS somente leitura; a visão live original é composta por OverlayFS RO na ordem live:base. Não há binds do rootfs, /run, D-Bus, socket Docker, SSH agent ou credenciais do host para dentro do alvo.

Um arquivo regular novo base.ext4/live.ext4, dentro da tentativa, recebe tamanho lógico fixo de 12 GiB e mkfs.ext4 exclusivamente nesse arquivo. Mount loop nodev/nosuid e cp -a --preserve=all criam a cópia descartável da base ou da visão live completa. Não se formata /dev, partição ou volume do servidor. O uso de loop devices e mounts é uma operação privilegiada futura, explicitamente sujeita à aprovação. O diretório vazio lost+found criado pelo próprio mkfs na nova imagem é removido especificamente antes da cópia; não existe limpeza genérica de diretórios.

proc é montado RO no PID namespace. /sys é vazio; /dev contém apenas null/zero/random/urandom e links fd, sem discos/loop/control devices. /run e /tmp usam tmpfs pequenos, limitados a 64/128 MiB; não armazenam rootfs. O bundle local e os debs são RO. A rede privada fica sem interfaces configuradas para acesso externo. A ausência de rede não depende de o APT respeitar um proxy.

O supervisor também faz chroot antes de criar o filho: /proc/1/root não aponta para o host. Os descritores acima de stderr são fechados; stdin é /dev/null e stdout/stderr são apenas logs da tentativa. O supervisor protege seu estado com dumpable=0. No filho, o bounding set é reduzido e no_new_privs é obrigatório antes de exec do Python da imagem. Não são retidas SYS_ADMIN, SYS_CHROOT, SYS_PTRACE, SYS_MODULE, SYS_RAWIO, MKNOD, SYS_BOOT ou capacidades de administração de rede. Permanecem apenas capacidades necessárias para ownership, permissões, usuários/grupos e file capabilities dos pacotes. As chamadas reais de redução de capabilities não foram executadas nesta fase.

Isso reduz a superfície de alteração do host, mas compartilha o kernel. Não é uma fronteira de segurança equivalente a uma VM contra pacotes maliciosos ou vulnerabilidades de kernel. A confiança depende de pacotes oficiais autenticados e de um teste real do isolamento. Qualquer incompatibilidade de maintainer script provoca quarentena, sem ampliar permissões automaticamente.

## APT/dpkg, scripts e serviços

O programa do alvo recebe ambiente mínimo e APT_CONFIG próprio: não herda hooks da imagem ou do host; listas e arquivos de fontes são vazios, estado dpkg/extended_states é o da cópia e downloads ficam desabilitados. Os debs locais da transação completa são fornecidos explicitamente ao APT. Uma simulação dentro do alvo deve produzir exatamente os pares pacote=versão travados antes de rodar apt-get -y --no-download --no-remove --no-install-recommends install. Não há upgrade geral, remoção, instalação externa ou apt-get update.

A marcação auto/manual é preservada: estados automáticos existentes são restaurados, dependências novas ficam automáticas e os 44 itens selecionados ficam manuais. Isso evita marcar todas as dependências como manuais só porque foram apresentadas como debs locais. Dpkg recebe --force-confold para preservar conffiles e as configurações 4B.1; mudanças incompatíveis devem falhar nos validadores, não ser aceitas silenciosamente.

policy-rc.d temporário retorna 101. Conteúdo ou symlink original, ownership, modo, timestamps e xattrs são restaurados em finally; não se segue o link anterior para gravar fora do destino. A falta de espaço durante restauração deixa a tentativa em quarentena, e nunca altera a fonte. Máscaras persistentes cobrem Apache, MariaDB/mysql, Docker/socket, containerd e iperf3. Uma unidade personalizada existente não é sobrescrita automaticamente. Os scripts de manutenção ainda executam no alvo para configurar pacotes; a política de serviços não tenta simular a instalação com dpkg --unpack apenas.

O guest aplica debconf não privilegiando Wireshark nem iniciando iperf3, executa a transação, locale-gen, dpkg --audit vazio e apt-get --simulate check. Em seguida o supervisor aplica os perfis 4B.2 à cópia e um segundo guest valida a configuração final: Apache -t, PHP/ini, MariaDB --verbose --help, Docker --validate, locale e máscaras systemd. Os validadores não iniciam os servidores. Processos órfãos terminados são recolhidos; qualquer daemon remanescente bloqueia aceitação e será encerrado com o namespace/cgroup.

## Integridade e proteção do instalador

O banco final precisa conter exatamente os pacotes/versões previstos, sem extras/remoções; o auditor estrutural exige estado instalado, journal dpkg sem transação pendente e arquivos info/*.list. APT não pode executar uma transação diferente da simulada/travada. Scripts que contornarem APT e modificarem outros estados dpkg são detectados pela comparação final. O hash do banco dpkg do servidor é registrado antes/depois da janela e mudanças impedem aceitação; uma atualização concorrente legítima do host também provocará investigação, sem atribuir automaticamente a mudança ao executor.

Inventários protegidos incluem boot, Casper, Subiquity, todos os dados snap e arquivos pertencentes aos pacotes protegidos. Comparam bytes/SHA-256, links, modos, UID/GID, mtime, xattrs e número de hardlinks antes/depois. Diretórios compartilhados não têm mtime congelado, pois recebem dependências novas. O instalador não deve ser atualizado implicitamente. Após o término do worker e a saída do namespace, e2fsck -f -n valida cada ext4 sem escrita; tamanho e SHA-256 da imagem inteira entram no resultado.

Essas verificações estão implementadas, porém não executadas contra instalações reais. Não alegar preservação runtime do instalador, boot ou instalação sem a integração correspondente.

## Reconciliação base/live

As transações usam bancos próprios e versões compartilhadas compatíveis. A saída é um par de rootfs completos em ext4, não duas SquashFS prontas para substituir a ISO. A folha antiga não é reaplicada sobre a nova base e dpkg/status não é copiado de um ambiente ao outro.

reconcile.plan_delta recebe inventários das visões finais e versões dpkg, recusa versões divergentes e atributos privados OverlayFS antigos, e planeja inclusões, alterações, troca de tipos e remoções que exigirão whiteouts. A aplicação/captura do delta ainda não está implementada: deverá regenerar whiteouts/opacity e atributos internos pelo mecanismo OverlayFS validado, preservar grupos de hardlinks e provar que nova base + delta reproduz integralmente a visão live. Esse limite é intencional nesta etapa de executor, e accepted-pair.json marca rebase_required=true.

Manifests, tamanhos, catálogo, boot replay e SquashFS só serão regenerados em uma fase posterior autorizada. Não há geração de ISO neste executor.

## Rollback e recuperação

Não há rollback in-place de dpkg. As fontes RO permanecem preservadas e cada alvo trabalha em arquivo novo, de tamanho limitado. Se a base passar e o live falhar, nenhum par é aceito. A tentativa parcial permanece root 0700 em quarentena, com imagens, logs e journal; repetir exige um novo job e nova revisão, não dpkg --configure -a automático.

O journal usa arquivo temporário + fsync + rename. A aceitação exige receipt do par e state=accepted com o mesmo hash; um receipt remanescente acompanhado de journal quarantined não é válido. Falha, SIGINT/SIGTERM/SIGHUP, OOM, timeout ou reserva de disco acionam encerramento da unidade/cgroup e preservação da tentativa. Saída do PID 1 desmonta os mounts privados e os loops autoclear; o probe real deverá confirmar esse comportamento no kernel observado. Não existe umount -l genérico, kill arbitrário de processos ou remoção recursiva de artefatos.

--recover exige autorização própria, job/hash correto e journal root-owned. Encerra somente unidades determinísticas desse job e registra quarentena. Não monta, repara, apaga ou retoma as imagens. Após falta de energia, verificar unidades/mounts/loops e estado dos arquivos antes de qualquer nova tentativa. A recuperação pós-reboot ainda não foi testada.

## Limites e recursos

- systemd MemoryMax=2560 MiB, MemorySwapMax=1024 MiB, TasksMax=128, CPUQuota=100%, RuntimeMaxSec=3600, KillMode=control-group e OOMPolicy=kill.
- Instalações sequenciais; sem compressão ou paralelismo de builds nesta fase. Limite de arquivo de 2 GiB para o guest e ext4 de 12 GiB por alvo limitam escritas na cópia.
- Watchdog de espaço livre a cada segundo e reserva de 12 GiB; disco cheio dentro do ext4 aborta sem alcançar outra imagem ou partição. O watchdog não é uma quota global do filesystem hospedeiro.
- Preservando um probe de 12 GiB, os dois alvos de 12 GiB, cópias verificadas das fontes/debs e margem, o orçamento conservador da sequência é **56 GiB livres**, idealmente 60 GiB. É maior que a estimativa 4B.2 porque agora inclui o probe preservado e limites completos das imagens descartáveis.
- Livre observado na preparação: aproximadamente 44,7 GiB. A sequência está abaixo do orçamento; --probe também exige esse orçamento inicial e fica bloqueado por espaço. Não houve expansão, limpeza ou alocação de imagens nesta fase.

systemd-run, systemctl, unshare, mount/umount, mkfs.ext4, e2fsck, cp, gpgv e Python foram encontrados. Cgroup v2 foi observado por leitura. Suporte efetivo a namespaces, OverlayFS com as camadas reais, SquashFS/loop e permissões do systemd ainda não foi exercitado. Mounts futuros podem exigir módulos já disponíveis no kernel; não instalar pacotes ou carregar módulos explicitamente sem aprovação.

## Job e comandos concretos — não executados

Job preparado: `/home/magaton/DevLite-OS/work/phase4b3-8k8e4q49`.
Hash de revisão: `ad2bd28cdaab297cef1034df3a66ecc342989c589fa1a1d80f41ad2da989d1c9`.

[Comandos completos](evidencias/executor-comandos.json) incluem os argumentos internos de systemd-run/unshare para base/live; [evidências](evidencias/executor-isolado.json) registram código, plano, limites e dependências. Se código, plano ou job mudar, gerar novo job e repetir revisão; um probe antigo não habilita código novo.

Ordem futura: ampliar espaço e revisar o job; autorizar somente o probe sem pacotes; validar seus resultados; adquirir debs após autorização de rede; revisar novamente a transação e autorizar a instalação separadamente. Cada modo exige sua própria flag autorizada, todas false nesta entrega. Não executar os exemplos a seguir agora.

```sh
sudo /usr/bin/python3 /home/magaton/DevLite-OS/scripts/executar-programas.py --probe --job /home/magaton/DevLite-OS/work/phase4b3-8k8e4q49 --approval-sha256 ad2bd28cdaab297cef1034df3a66ecc342989c589fa1a1d80f41ad2da989d1c9
```

```sh
sudo /usr/bin/python3 /home/magaton/DevLite-OS/scripts/executar-programas.py --execute --job /home/magaton/DevLite-OS/work/phase4b3-8k8e4q49 --approval-sha256 ad2bd28cdaab297cef1034df3a66ecc342989c589fa1a1d80f41ad2da989d1c9
```

```sh
sudo /usr/bin/python3 /home/magaton/DevLite-OS/scripts/executar-programas.py --recover --job /home/magaton/DevLite-OS/work/phase4b3-8k8e4q49 --approval-sha256 ad2bd28cdaab297cef1034df3a66ecc342989c589fa1a1d80f41ad2da989d1c9
```

O primeiro comando é o probe sem APT/dpkg de instalação; o segundo instala apenas após prova root-owned de probe aprovado para o mesmo job; o terceiro é exclusivamente recuperação. Não foi solicitada nem inferida autorização para nenhum deles nesta fase.

Reprodução permitida, sem root:

```sh
python3 scripts/executar-programas.py --prepare /home/magaton/DevLite-OS/work/phase4b2-whqtc4yu/installation-plan.json
TMPDIR="$PWD/work/phase4b1-tests-tmp" PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 scripts/verificar-projeto.py
```

## Testes e pendências

105 testes passaram (75 anteriores + 30 novos). Cobrem gates sem subprocessos, contrato/paths/providers, namespaces e limites declarados, capabilities permitidas, parser APT, auto/manual, restauração de policy regular/symlink/xattrs em falhas, inventários protegidos e hardlinks, reserva de disco com kill mockado, provas de worker com footer systemd, journal/aceitação do par, falha live após sucesso base e plano de delta/whiteouts. Relatório local: reports/testes-fase4b3.txt.

São testes unitários/fixtures e a simulação APT anterior; não aprovam o isolamento real nem os scripts de manutenção. Os cinco testes históricos da ISO 4B.1 não foram reexecutados. Pendências: probe autorizado; testes reais de namespace/capabilities/cgroup/loops; cenários de OOM/disco/sinais/reboot; debs autenticados; comportamento real dos postinst e configuração MariaDB/Docker; revisão de dados específicos de máquina gerados durante a instalação; implementação/captura do delta e validação equivalente; posteriormente boot BIOS/UEFI, instalação e persistência em VMs descartáveis.

## Referências oficiais

- [unshare: namespaces e propagação](https://manpages.ubuntu.com/manpages/noble/man1/unshare.1.html).
- [systemd-run: unidades e limites](https://manpages.ubuntu.com/manpages/noble/man1/systemd-run.1.html).
- [Linux capabilities](https://manpages.ubuntu.com/manpages/noble/man7/capabilities.7.html).
- [mount: filesystem e loop](https://manpages.ubuntu.com/manpages/noble/man8/mount.8.html).
