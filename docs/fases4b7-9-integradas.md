# DevLite OS — Fases 4B.7 a 4B.9 integradas

Estado atualizado em 18/11/2026 UTC: **duas ISOs geradas, estruturalmente verificadas e idênticas bit a bit**. Base/Live e integração aprovadas; 197 testes passaram após a geração. Host íntegro, gates false, nenhuma VM executada. [Artefatos, hashes e evidências](fase4b8-isos-geradas.md); [roteiro de aceitação pendente](fase4b9-validacao-pratica.md).

A referência do usuário a 4B.6 concluída foi preservada como informação de entrada. Este checkout ainda estava configurado como B.5 e não contém um relatório 4B.6 separado; não inventamos evidências. O cache real, o recibo da aquisição e o atestado root-owned do probe foram conferidos diretamente.

## Resultado consolidado

| Fase | Implementado/verificado | Ainda pendente |
|---|---|---|
| 4B.7 | APT Base/Live, auditorias dpkg/APT, perfis/máscaras, componentes protegidos, fsck/SHA, journal accepted e host íntegro | Não inclui boot ou instalação em disco de VM |
| 4B.8 | Camadas integradas; duas ISOs estruturalmente verificadas, EFI/boot/instalador preservados e reprodução bit a bit aprovada | Evolução futura da edição completa |
| 4B.9 | Checklist BIOS/UEFI, perfil ubuntu-experimental, verificação dos arquivos de configuração nas imagens e validador de evidências | Boot, interface/aplicativos e instalação/reinicialização/persistência reais |


Job integrado atual: `/home/magaton/DevLite-OS/work/release-63m6oz2_`. Registros anteriores abaixo permanecem como histórico. 
Contrato atual: `bc32e0ce9fb1a95d4b0170c1130f46ec523ddee0871b9fd3915e8f126a91d19d`.
[Evidências atuais](evidencias/pipeline-integrado-atual.json). Os [registros da preparação inicial](evidencias/pipeline-integrado-4b7-9.json) e seus [comandos históricos](evidencias/pipeline-integrado-comandos.json) permanecem preservados. O cache e o executor usados para instalar são os já aprovados, não um substituto do host.

## 4B.7 — cache, isolamento e instalação preparada

Foram conferidos os 243 arquivos (338.284.668 bytes), o manifesto/receipt da aquisição, o plano do executor, seu código congelado e atestado root-owned probe_passed. As versões de ambos os alvos continuam compatíveis: base 227 novos + 13 atualizações (240 operações), live 223 novos + 16 atualizações (239 operações), sem remoções/downgrades/componentes protegidos.

O primeiro preflight bloqueou uma divergência de proveniência. O cache adquirido usa índices assinados mais recentes que os do job do probe. A correção não ignorou hashes: os dois snapshots foram reautenticados separadamente e os artefatos comparados por pacote, versão, arquitetura, Filename, tamanho, SHA-256, destinos e URLs. Os bytes dos pacotes são iguais; ambas as proveniências foram preservadas nos logs. A regressão correspondente recusa qualquer SHA/tamanho/versão diferente. Nenhum índice remoto foi atualizado nesta rodada.

Os arquivos foram disponibilizados em `work/phase4b3-1ibq_emz/debs/` por hardlinks verificados/reuso, sem alterar o manifesto, o código ou o atestado do probe. Não são instalação e não foram copiados para um rootfs do hospedeiro. O executor posteriormente fará cópias privadas root-owned e verificará novamente os hashes. O preparo recusa cache extra/corrompido, symlinks e tentativa de instalação pré-existente.

`dpkg-deb --field` e `--ctrl-tarfile` foram executados **somente como leitores no host**, sem instalar/extrair no host e sem executar scripts. Foram inspecionados 313 scripts/triggers; oito pacotes apresentam tokens de serviços/privilégios que exigem atenção: apache2, containerd, docker.io, iperf3, libc6, mariadb-server, openvpn e php-common. A presença desses tokens é uma triagem estática, não prova de incompatibilidade ou malícia. Registro completo: `maintainer-audit.json` do job.

A instalação real reutilizará o executor congelado pelo probe: unidades/cgroups separados, Base e Live sequenciais, namespaces de mount/PID/rede/IPC/UTS/cgroup, fontes RO, imagens ext4 descartáveis de 12 GiB por alvo, dev mínimo, sem sockets do host, supervisor/guest em chroot e bounding set reduzido/no_new_privs. APT usa debs locais, sem downloads; simulação precisa coincidir exatamente com o lock. O destino é a cópia de cada imagem, nunca `/` do Ubuntu Server.

Durante manutenção: policy-rc.d temporário restaurável, máscaras persistentes de Apache/MariaDB/Docker/containerd/iperf3, sem grupos docker/wireshark automáticos. Os perfis são aplicados à cópia e validados sem iniciar os servidores. As 13/16 atualizações incluem libc/locales/Perl e fazem parte da operação revisada; não é uma instalação puramente aditiva.

Exigir dpkg --audit vazio, apt --simulate check íntegro, versões/conjunto finais exatos, listas dpkg presentes, configurações válidas, serviços mascarados, ausência de daemons órfãos e inventários do instalador/boot/snap inalterados. O host é monitorado por hashes de arquivos críticos. Erros de pacote, OOM, timeout, sinal, espaço ou auditoria encerram apenas unidades do job e deixam imagens em quarentena, sem dpkg --configure -a automático nem rollback in-place. Só o par completo aceito pode seguir.

Limites: 2,5 GiB RAM, 1 GiB swap, 128 tarefas, CPUQuota=100%, worker de até uma hora por alvo e reserva de 12 GiB. A instalação futura exige aproximadamente 41,22 GiB adicionais pelo orçamento existente; livre no preflight: 67.59 GiB. Repetir a verificação antes de executar. Hashes/cópias do controlador podem prolongar o tempo total além do timeout do worker.

## 4B.8 — integração e ISO implementadas, execução bloqueada

`release_layers.py` valida inventários completos, rejeita caminhos e xattrs OverlayFS obsoletos, calcula whiteouts sem recriar filhos de diretórios removidos, trata troca de tipos e força copiar todo grupo hardlink alterado. A prova de modelo exige que base + receita reproduza integralmente a visão live. O materializador só aceita destino novo, verifica payloads e preserva UID/GID/modos/mtime/xattrs/symlinks/hardlinks. Devices/whiteouts requerem root autorizado, nunca foram criados nos testes desta rodada.

`release_pack.py` só aceita o par root-owned e journal accepted do executor esperado. Em namespace mount privado e com autorização própria, verificará hashes das imagens ext4, montará inputs RO/noload, removerá apenas da visão lógica os diretórios operacionais vazios conhecidos do executor, gerará delta e SquashFS, reextrairá e comparará os inventários e montará base+novo delta RO para provar equivalência pelo kernel. A raiz original não é modificada. A presença de outro conteúdo em var/lib/devlite-executor bloqueia a operação, em vez de apagá-lo.

Compressão xz sequencial, blocos 128 KiB, um processador/cache 256 MiB, mkfs-time fixo e metadados dos inputs preservados; sem all-root/all-time. O comando de integração é envolvido em unidade systemd com limites de memória/CPU/tarefas e timeout de duas horas. O preflight começa com 32 GiB mínimos e calcula outra margem conservadora usando o tamanho alocado dos inputs reais antes de materializar/reextrair. Inputs maiores podem bloquear a etapa; não se apagam artefatos anteriores para liberar espaço.

A inspeção confirmou formatos diferentes: minimal.manifest e minimal.live.manifest são deltas com cabeçalhos ---/+++ sem hunks/contexto; filesystem.manifest é a lista completa live com três entradas snap. O gerador preserva essa semântica e as entradas snap originais, pois o executor impede alterar o instalador/snap. Tamanhos e catálogo fsimage-layered com fonte minimal.squashfs são regenerados.

`release_iso.py` exige receipt root-owned layers_verified, round-trip e composição pelo kernel, arquivos esperados e hashes exatos. Monta a ISO como magaton, com fonte/saída distintas, xorriso nativo e replay de boot. Preserva MBR, GPT/BIOS/UEFI, EFI anexada, kernel/initrd/instalador; mantém UUID temporal do volume e atualiza apenas payloads autorizados, GRUB regional, manifests, tamanhos e checksums. Assinatura Ubuntu original fica arquivada como proveniência; checksums personalizados continuam não assinados.

A auditoria futura compara árvores e metadados completos, EFI/MBR/El Torito, hashes mapeados e manifests MD5/SHA-256 antes de promover .iso.partial. Nesta rodada, somente a ISO **existente da 4B.1** foi inspecionada: estrutura BIOS/UEFI/MBR e EFI iguais à oficial e catálogo/layout corretos. Isso não valida uma ISO nova ainda inexistente.

A reprodução é implementada para duas construções do mesmo contrato e camadas seladas; exige referência íntegra e compara SHA-256 bit a bit. O teste não privilegiado comprovou reprodução de uma SquashFS pequena. Não há prova de reprodução da ISO completa, nem de duas instalações frescas: relógios de logs, inicialização MariaDB e outros dados podem variar durante instalação. Não anunciar reprodutibilidade total antes do ensaio correspondente.

## 4B.9 — laboratório e aceitação

Modelo gerado: `acceptance-template.json`. Tem VMs/discos independentes BIOS e UEFI, critérios pendentes e provas por arquivos com SHA-256. O validador não aceita campos vazios, mesmo disco, firmware errado, ISO/hash diferente, prova ausente/alterada ou programas faltantes. Ele valida documentos e hashes; não comprova sozinho que uma captura/log veio realmente da VM. Revisão humana continua necessária.

Usar VMware Workstation diretamente no Windows conforme laboratório 3A, evitando VM aninhada nesta máquina de 3,8 GiB. Reservar, como ponto inicial, 2 vCPU, 4 GiB RAM e disco virtual novo de 40 GiB por modo, com identificação exclusiva, sem passthrough dos discos do Ubuntu Server, pastas compartilhadas ou credenciais reais. Não criar nem iniciar VMs automaticamente. Executar instalação somente em discos descartáveis autorizados. Testar reboot sem ISO e ao menos outro reboot para persistência. Secure Boot é uma capacidade separada; preservação de binários EFI não equivale à sua aprovação.

Para cada firmware e para live/instalado:

- [ ] disco descartavel
- [ ] hash iso
- [ ] boot live
- [ ] firmware live
- [ ] xfce live
- [ ] pt br live
- [ ] abnt2 live
- [ ] timezone live
- [ ] programas live
- [ ] servicos bloqueados live
- [ ] instalador preservado
- [ ] instalacao
- [ ] boot sem iso
- [ ] firmware instalado
- [ ] xfce instalado
- [ ] pt br instalado
- [ ] abnt2 instalado
- [ ] timezone instalado
- [ ] programas instalados
- [ ] servicos bloqueados instalado
- [ ] persistencia reboot
- [ ] desligamento
- [ ] writer calc impress
- [ ] pdf visual
- [ ] remmina visual
- [ ] vpn networkmanager
- [ ] wireshark capture policy
- [ ] docker ativacao manual
- [ ] php extensoes

`program-checks.json` contém comandos de versão/sintaxe, sem executá-los no host. Além deles, validar visualmente Writer/Calc/Impress, PDF, XFCE/Remmina, acentos pt-BR, teclas ABNT2 (ç/acentos), timezone, VPN via NetworkManager, política de captura e ativação manual de serviços. Não iniciar Docker, scans ou VPNs contra redes de terceiros para simular aprovação. Testes de servidor devem usar loopback ou rede de laboratório autorizada.

Perfil ubuntu-experimental verifica os programas Ubuntu. Perfil full-edition exige também Node.js LTS, TypeScript e VS Code; esses três continuam fora do cache/fontes autorizadas. Portanto **a edição completa ainda não está pronta para release**. O pipeline atual produzirá, quando autorizado, uma ISO experimental com os 44 itens Ubuntu e suas dependências. Não habilitamos repositórios ou aquisição externa para ocultar essa pendência.

## Arquivos principais criados

- scripts/devlite-release.py: preflight integrado, futura montagem/reprodução e validação documental.
- scripts/instalar-release-root.py e release_install.py: operação única de instalação, resumo público não sensível e restauração do gate.
- scripts/integrar-release-root.py: backend de integração root, bloqueado.
- pipeline/devlite/release_contract.py, release_flow.py, release_layers.py, release_pack.py, release_iso.py, release_acceptance.py.
- tests/test_release_pipeline.py e este relatório consolidado; evidências JSON e contratos ficam nos caminhos indicados.

README, configuração, verificador, plano e decisões foram atualizados. Nenhum módulo do executor validado pelo probe foi modificado; seu atestado continua vinculado ao código conferido. Todos os modos de execução, integração, ISO, download, recuperação e criação de VMs permanecem false.

## Testes executados e execução permitida agora

**158 testes aprovados** (131 anteriores + 27 novos). Novos casos incluem whiteouts/troca de tipos/ancestrais inseguros, materialização sem remoções com xattrs/hardlinks/symlinks, payload alterado, estado operacional inesperado, formatos de manifest, recursos/UID de compressão, bloqueios root/ISO, staging sem sobrescrever, snapshots assinados equivalentes com hashes divergentes rejeitados, aceitação incompleta/alterada/discos iguais/externos faltantes e reprodução/round-trip real de uma SquashFS pequena sem mount. Relatório: reports/testes-release-integrado.txt.

O preflight real verificou identidade dos debs por dpkg-deb e os 313 scripts apenas como bytes, GPG/índices, cache, atestado/código do probe e referência BIOS/UEFI. Arquivos críticos, mounts e backings de loop do host permaneceram iguais. Nada foi instalado ou iniciado.

```sh
python3 scripts/devlite-release.py --prepare
TMPDIR="$PWD/work/phase4b1-tests-tmp" PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 scripts/verificar-projeto.py
```

O preflight cria novo job e novos hashes para integração; não reutilizar o hash de outro job. Alterar código de integração invalida seu contrato. Alterar o executor invalidaria o probe — não foi feito aqui.

## Única aprovação solicitada agora: instalação Base → Live

Comando exato, **ainda não executado**, como root (sudo no terminal magaton; no executor já root, sem sudo redundante):

```sh
sudo /usr/bin/python3 /home/magaton/DevLite-OS/scripts/instalar-release-root.py --job /home/magaton/DevLite-OS/work/release-zii8eoas --approval-sha256 583f72f05346d2d96fe589e2486a201231ebac62ee02fd33a14987ded0b86f5f
```

Após confirmação, habilitar temporariamente apenas executor_autorizado=true no projeto e executar uma vez. O wrapper valida o contrato novo e chama o executor já aprovado no job antigo; restaura a flag em finally e publica installation-result.json root-owned somente leitura. O assistente também conferirá a restauração se houver falha antes da entrada na operação. As outras permissões continuam false. A operação inclui verificação das fontes/cache, dois rootfs descartáveis, mounts/namespaces/chroots isolados, a instalação offline sequencial de 240/239 operações, perfis/máscaras, auditorias, hashes/fsck e encerramento restrito das unidades em falha. Não inclui rede de aquisição, alteração de partições/LVM, programas no host, integração, compressão real, nova ISO ou VMs.

Riscos: scripts de manutenção e dependências reais ainda não foram exercitados; libc/Perl e outros pacotes existentes serão atualizados dentro das cópias; MariaDB pode inicializar dados específicos de máquina; limites de tempo/memória podem abortar em hardware lento; namespaces compartilham kernel e não são VM para código malicioso. Falhas devem deixar cópias em quarentena, sem afrouxar permissões ou tocar no host. Interrupção/recuperação reais, OOM/reboot ainda não estão aprovados por teste. O probe normal não é uma aprovação de todos os postinst.

Após instalação aprovada e concluída, podem continuar automaticamente as atividades **não privilegiadas**: leitura dos resultados acessíveis, validação de contratos, planejamento, testes e relatório. Não se infere autorização para pack/root ou gerar ISO. O wrapper exporta resumo não sensível para leitura comum; as imagens e logs detalhados continuam root 0700. Nenhuma permissão de imagem privada será afrouxada.

## Comandos posteriores bloqueados

Os comandos anteriores de pack/ISO/reprodução com contrato 583f72f... são registros históricos e não devem ser executados: o código do worker mudou e a tentativa está em quarentena. Após o novo par ser aceito, validar o novo contrato antes de preparar integração/ISO, cada qual com sua autorização. O checklist continua em work/release-zii8eoas/acceptance-template.json como modelo pendente, sem aprovar boot ou instalação.

Referências técnicas: [OverlayFS/whiteouts](https://docs.kernel.org/filesystems/overlayfs.html) e [mksquashfs Noble](https://manpages.ubuntu.com/manpages/noble/man1/mksquashfs.1.html).

## Execução autorizada — tentativa 1 e correção

O usuário autorizou a operação descrita. O executor autenticou índices, verificou/copíou 243 debs e as camadas para uma tentativa root-owned nova. O worker Base montou/copiou o rootfs, verificou os debs, executou debconf e simulou a transação exata (227 novos + 13 atualizações). Na chamada efetiva, APT abortou antes de qualquer mensagem Unpacking/Setting up: `Internal Error, Pathname to install is not absolute 'libperl5.38t64_5.38.2-3.2ubuntu0.7_amd64.deb'`. A presença de mensagens não substitui uma auditoria completa da imagem; não se declara o alvo intocado. Live não foi iniciada, não há accepted-pair e nenhum resultado pode ser usado para pack.

O controlador marcou quarantined, encerrou as unidades e verificou os hashes do banco dpkg e dos arquivos críticos do host, todos inalterados. Unidades Base/Live inactive/dead, nenhum mount nem loop dessa tentativa residual. A permissão executor_autorizado foi restaurada para false. A imagem, os logs privados e o resultado público foram preservados. Evidências: [tentativa 1](evidencias/instalacao-4b7-tentativa1.json).

Correção em pipeline/devlite/customize/executor_worker.py: definir `Dir::Cache::archives "/run/devlite/debs";` para que --no-download encontre arquivos com caminho absoluto no bundle RO, e `DPkg::Use-Pty "false";` para o ambiente sem /dev/pts. Nenhum acesso de rede, capability ou mount foi acrescentado. O teste tests/test_apt_local_archives.py reproduz o erro com um deb vazio criado localmente e confirma a correção com APT real. A instalação é bloqueada por dois meios independentes: `Dir::Bin::dpkg=/bin/false` e `Debug::pkgDPkgPM=true`. O banco de fixture permanece idêntico. A suíte completa passou em **160 testes**, relatório reports/testes-release-correcao-apt.txt.

A mudança de código invalida o contrato anterior e seu probe como autorização para esta versão. Não foram alterados contratos, atestados ou permissões antigos para contornar o gate. Foram preparados novos diretórios e hashes, sem executar probe, mounts, chroot ou nova instalação:

- Executor: `/home/magaton/DevLite-OS/work/phase4b3-bklz27i4`.
- Release: `/home/magaton/DevLite-OS/work/release-00j3px2e`.
- Cache revalidado: 243 debs, sem novo download.
- Espaço livre: 62.79 GiB.

Uma única aprovação é solicitada para a sequência abaixo. Habilitar apenas probe_autorizado durante o probe, restaurar para false em finally; somente com retorno zero e atestado root-owned correspondente, habilitar executor_autorizado para o wrapper e restaurar para false mesmo em falha. Não repetir tentativas nem recuperar dpkg in-place. Se o probe falhar, não iniciar instalação.

```sh
sudo /usr/bin/python3 /home/magaton/DevLite-OS/scripts/executar-programas.py --probe --job /home/magaton/DevLite-OS/work/phase4b3-bklz27i4 --approval-sha256 66d2ff9a40ac8a63a851db8524a690ba188d298a92aad4b0a5c1eee012f147e6
# SOMENTE se o probe passar e o atestado corresponder ao contrato:
sudo /usr/bin/python3 /home/magaton/DevLite-OS/scripts/instalar-release-root.py --job /home/magaton/DevLite-OS/work/release-00j3px2e --approval-sha256 de1ff81e62960adf05cb9079cdb71136e7f75025fff08d4465d805309f4ab8b2
```

Esta nova aprovação é necessária porque a anterior delimitava o comando/job já executado; a correção altera os hashes e requer novo probe privilegiado. A sequência inclui os mesmos limites (2,5 GiB RAM, 1 GiB swap, 128 tarefas, uma CPU) e isolamento. Os riscos de scripts de manutenção, limite de espaço/tempo/memória e kernel compartilhado continuam. Compressão, ISO, VMs, rede e alterações em volumes do host não fazem parte da solicitação.

[Evidência de preparação](evidencias/instalacao-4b7-nova-tentativa.json), [comandos estruturados](evidencias/instalacao-4b7-novos-comandos.json). Não há novo probe_passed, instalação aceita, boot ou persistência pós-instalação aprovados.

## Execução autorizada — tentativa 2, cache isolado e espaço

O usuário autorizou a sequência de novo probe e instalação. O novo probe do executor phase4b3-bklz27i4 terminou com retorno zero, fsck aprovado, atestado root-owned probe_passed e proteção do host confirmada. Os limites efetivos foram 2,5 GiB RAM, 1 GiB swap, 128 tarefas e CPUQuota 100%. Em seguida probe_autorizado foi restaurado para false e a instalação autorizada iniciou no release-00j3px2e.

A Base foi copiada e a simulação manteve 227 novos/13 atualizações. O APT real abortou com `Archives directory /run/devlite/debs/partial is missing - Read-only file system`. Não há mensagem Unpacking/Setting up no log; isso não comprova que o rootfs está intocado (debconf/máscaras já haviam sido aplicados). A Live não iniciou, não há accepted-pair, a tentativa foi colocada em quarentena e o wrapper restaurou executor_autorizado=false. O guard confirmou banco dpkg e arquivos críticos do host idênticos; unidades inativas, sem mounts/loops residuais. Evidências completas não sensíveis: [tentativa 2](evidencias/instalacao-4b7-tentativa2.json). Não houve instalação de programas no host, nova aquisição, integração, ISO ou VM.

O teste anterior comprovava caminhos absolutos em cache gravável e não reproduzia o bundle RO. A nova correção em executor_worker.py e guest_runner.py usa `/var/cache/apt/archives` dentro da cópia descartável. `archive_cache` cria partial e links temporários para os debs autenticados em `/run/devlite/debs`, que continua RO. APT pode gerenciar seu lock/cache no alvo sem escrever no bundle. Os links são removidos em finally somente se ainda apontarem para as fontes esperadas; arquivos preexistentes nunca são substituídos. Não se amplia rede, capabilities ou mounts. Policy-rc.d e máscaras continuam preservados.

Foram adicionadas regressões para o bundle sem permissão de escrita, partial/lock, conservação dos bytes, limpeza em erro e recusa de sobrescrita. O teste com APT real usa permissões 0555/0444 como usuário comum para simular a negação de escrita; não é uma montagem RO real. Dpkg é /bin/false e Debug::pkgDPkgPM=true: nenhuma transação real é executada nos testes. A suíte completa passou em **162 testes**, relatório reports/testes-release-cache-isolado.txt; verificações estáticas/JSON/Git também concluídas.

A correção muda novamente os hashes. O atestado da tentativa 2 permanece válido como evidência daquela versão, não como liberação da versão nova. Todos os contratos/atestados e artefatos antigos foram preservados; não se forjaram recibos, não se baixou o guard de disco e não se retomou dpkg in-place.

Após preservar as tentativas, restam **53,94 GiB livres**. O mínimo explícito do próximo probe é **56 GiB**, déficit de aproximadamente **2,06 GiB**. Deve haver margem adicional; recomenda-se disponibilizar pelo menos 60 GiB. A instalação tem orçamento adicional de 41,22 GiB, reavaliado depois do probe. Não foram apagadas imagens, cópias ou artefatos para liberar espaço; expansão/limpeza não faz parte da sequência de probe/instalação autorizada. Enquanto faltar espaço, não habilitar gates nem iniciar operações privilegiadas. Integração/ISO/boot permanecem pendentes.

Nova preparação bloqueada por espaço: `/home/magaton/DevLite-OS/work/release-qqkumja7`, executor `/home/magaton/DevLite-OS/work/phase4b3-nuuyxpa1`. [Evidência](evidencias/instalacao-4b7-cache-corrigido.json) e [comandos exatos](evidencias/instalacao-4b7-cache-comandos.json). Os novos diretórios têm cache revalidado (243 arquivos) e contratos; ainda não têm probe nem instalação. Nenhuma permissão foi habilitada.

## Auditoria de armazenamento antes da retomada

Em 17/11/2026 foi preparado um [plano de limpeza de três imagens descartáveis](recuperacao-espaco.md), estimando recuperar 6,92 GiB e alcançar 60,86 GiB livres. Nenhum arquivo foi removido; limpeza depende da aprovação da lista exata. A imagem da falha mais recente e todos os artefatos da próxima tentativa são preservados.

## Retomada após limpeza autorizada

Limpeza concluída conforme [plano e resultado](recuperacao-espaco.md). [Evidência de revalidação](evidencias/retomada-apos-limpeza.json). Mantidos os contratos atuais release-qqkumja7 e phase4b3-nuuyxpa1: não foram recriados jobs, baixados pacotes ou refeita a preparação desnecessariamente. O cache-fonte e o cache do executor passaram nos 243 hashes/identidades esperados, código/plano e recibo/manifesto de aquisição conferidos. Não há tentativa/probe nesses diretórios. Todas as permissões permanecem false.

Uma autorização específica é solicitada para a sequência abaixo. Habilitar apenas probe_autorizado durante o probe e restaurar para false ao encerrar; somente com retorno zero, atestado root-owned e espaço ainda suficiente, habilitar executor_autorizado para o wrapper. Restaurar a permissão ao encerrar, inclusive em falha. Qualquer falha interrompe a sequência sem retomar dpkg in-place. Preservar tentativas e evidências.

```sh
sudo /usr/bin/python3 /home/magaton/DevLite-OS/scripts/executar-programas.py --probe --job /home/magaton/DevLite-OS/work/phase4b3-nuuyxpa1 --approval-sha256 a6eb77b71206587013cf3ea28c8d746926982ad23193673cacd8421fba75223c
# SOMENTE se o probe passar e corresponder ao contrato atual:
sudo /usr/bin/python3 /home/magaton/DevLite-OS/scripts/instalar-release-root.py --job /home/magaton/DevLite-OS/work/release-qqkumja7 --approval-sha256 e8e8a0f9ba2427fecdb06cdf8f9055a879542333783c86a9974f79dae7e809a1
```

Escopo: novo probe sem pacotes, seguido de instalação offline sequencial Base → Live em cópias isoladas, auditorias e encerramento/limpeza dos recursos de namespace. Sem pacotes no host, rede de aquisição, alteração de partições/LVM, integração, nova ISO ou VMs. Limites preservados: 2,5 GiB RAM, 1 GiB swap, 128 tarefas, CPUQuota 100%, 56 GiB mínimos para iniciar probe; reavaliar orçamento de instalação de 41,22 GiB depois dele. Scripts de manutenção ainda não exercitados podem falhar; namespaces compartilham kernel e há riscos de timeout/memória/disco. Se aprovado e concluído, continuar automaticamente a análise não privilegiada e a preparação da integração/ISO/testes, respeitando autorizações próprias de execução.

## Execução autorizada — tentativa 3 e nomes APT com epoch

Após autorização específica, o probe phase4b3-nuuyxpa1 passou com retorno zero, fsck/hash e atestado root-owned vinculados ao contrato. Restaurada probe_autorizado=false, iniciou-se a instalação pelo release-qqkumja7, conforme o comando aprovado. As cópias/fontes e os 243 debs foram novamente autenticados/verificados. A Base passou na simulação exata e começou a instalação real. O log registra desempacotamento de Perl/libperl/perl-modules/libc6 e configuração de perl-base/libc6; portanto esta imagem foi **parcialmente modificada**. Não é um sistema instalado validado e não deve ser retomada in-place.

APT abortou procurando `zlib1g_1%3a1.3.dfsg-3.1ubuntu2.3_amd64.deb`. O arquivo da origem omite o epoch no nome, enquanto o cache APT inclui a versão completa com `:` escapado. A etapa anterior criava apenas aliases com o basename da origem e não cobria versões com epoch. A Live não iniciou e não existe accepted-pair. O controlador colocou a tentativa em quarentena e o wrapper restaurou executor_autorizado=false.

A auditoria confirmou banco dpkg e arquivos críticos do Ubuntu Server idênticos, unidades inativas e ausência de mounts/loops residuais. [Evidências da tentativa 3](evidencias/instalacao-4b7-tentativa3.json). As imagens e logs desta tentativa foram preservados. A limpeza anterior permanece limitada aos três arquivos explicitamente autorizados, sem remoções adicionais.

A correção em guest_runner.py gera aliases canônicos `pacote_versão-com-epoch-escapado_arquitetura.deb` para cada item do lock, além do basename original, ambos apontando ao bundle RO. Nenhum deb original é renomeado ou alterado. Os links temporários continuam dentro do alvo e são removidos com conferência de destino. A regra foi conferida com o [código do APT](https://github.com/Debian/apt/blob/main/apt-pkg/acquire-item.cc) e testada com o APT instalado.

Antes de chamar a instalação efetiva, install_local agora chama APT com **Debug::pkgDPkgPM=true e Dir::Bin::dpkg=/bin/false**. Exige que os comandos planejados cubram exatamente todos os caminhos canônicos do lock. O preflight configura recursive::minimum=1000000 somente nessa chamada de diagnóstico para obter caminhos explícitos, pois o APT normalmente agrupa lotes em diretórios temporários --recursive; isso não altera a invocação da instalação real. Se faltar algum caminho, não há primeiro unpack. A simulação de versões continua obrigatória antes desse preflight. Esta barreira verifica a preparação dos comandos, não executa scripts de manutenção e não comprova sucesso da instalação futura.

Testes: **166 aprovados** em reports/testes-release-epoch-apt.txt. As quatro regressões novas cobrem nomes com epoch, identidade insegura, APT real com pacote local contendo epoch, bloqueio após falha do preflight e cobertura incompleta. Foi realizado ainda um preflight separado com os **debs reais e status originais Base/Live**, em diretórios de fixture como magaton, sem chroot/mount/instalação/rede. Simulações coincidiram com os locks; todos os **240 caminhos da Base (55 versões com epoch) e 239 da Live (51 com epoch)** foram validados, com status e arquivos críticos do host inalterados. [Relatório do preflight completo](evidencias/preflight-completo-apt-epoch.json). A validação inicial de coleta contou apenas 12 caminhos porque os demais vinham em grupos --recursive; ela foi preservada no job apt-full-preflight-h34m6wws e substituída por coleta explícita completa, sem executar dpkg.

A alteração do código invalida o atestado anterior para a nova versão. Não se regravaram contratos/atestados para contornar essa verificação. A execução desta rodada terminou após a falha; nenhuma nova instalação ou probe da versão corrigida foi iniciado.

O espaço atual é **51.94 GiB**, abaixo do mínimo de **56 GiB** para outro probe (déficit aproximado de **4.06 GiB**; para retornar à meta de 60 GiB, **8.06 GiB**). Os limites não foram reduzidos. Não foi executada limpeza adicional: qualquer nova remoção exige lista exata e autorização. A integração, ISO e validação de boot/instalação continuam pendentes.

Preparação da versão com epoch: `/home/magaton/DevLite-OS/work/release-o9fx0a_a`, executor `/home/magaton/DevLite-OS/work/phase4b3-yqj_nck2`. [Contrato/cache e bloqueio de espaço](evidencias/instalacao-4b7-epoch-corrigido.json), [comandos preparados, não executados](evidencias/instalacao-4b7-epoch-comandos.json). Novo atestado continua pendente; contratos anteriores não autorizam este código.

## Proposta ampliada de recuperação de espaço

Auditoria somente leitura concluída em 17/11/2026: [14 candidatos exatos, 15,72 GiB recuperáveis](recuperacao-definitiva-espaco.md). Os hashes das 12 cópias SquashFS e suas fontes foram conferidos; nenhuma remoção foi feita. A imagem da falha parcial mais recente, todos os artefatos da próxima tentativa, ISOs e cache dos 243 debs serão preservados. As imagens ext4 já são esparsas; limites de 56 GiB e reserva não foram alterados. Limpeza depende de autorização específica.

## Retomada após limpeza ampliada

[Resultado da limpeza e auditoria](recuperacao-definitiva-espaco.md), [revalidação atual](evidencias/retomada-apos-limpeza-definitiva.json) e [preflight completo atual](evidencias/preflight-apos-limpeza-definitiva.json). Mantidos os contratos da versão corrigida com epoch, sem alterar o executor ou criar novas imagens. A instalação exige o novo probe porque os atestados anteriores não correspondem a este código. O orçamento de 56 GiB e a reserva permanecem inalterados.

Comandos atuais para aprovação específica, ainda não executados:

```sh
sudo /usr/bin/python3 /home/magaton/DevLite-OS/scripts/executar-programas.py --probe --job /home/magaton/DevLite-OS/work/phase4b3-yqj_nck2 --approval-sha256 074b36bf080aed4a177e9d1d9badf0ecd575b48fff12c63d3855a186fbef24dd
# SOMENTE se houver retorno zero e atestado root-owned do contrato atual:
sudo /usr/bin/python3 /home/magaton/DevLite-OS/scripts/instalar-release-root.py --job /home/magaton/DevLite-OS/work/release-o9fx0a_a --approval-sha256 4c26607d67825165b7017993bc0068b0dca26ac02711287a8148f63e2e0667f2
```

Habilitar probe_autorizado somente durante o probe e restaurar para false inclusive em falha. Somente depois de aprovação real, reavaliar espaço e habilitar executor_autorizado para a instalação sequencial Base → Live; o wrapper executa auditorias/exporta resumo e restaura a permissão. Falhas interrompem a sequência e preservam quarentena, sem recuperação dpkg in-place ou exclusão automática. Limites: 2,5 GiB RAM, 1 GiB swap, 128 tarefas, CPUQuota 100%, até uma hora por worker; scripts de manutenção podem falhar, e o isolamento compartilha o kernel. O preflight não executa postinst nem aprova uma instalação completa.

A autorização solicitada compreende somente probe, cópias/mounts/namespaces/chroot do executor, instalação offline nas cópias, auditorias e encerramento dos recursos. Sem rede de aquisição, programas no host, alteração de volumes/partições, integração/pack, ISO ou VMs. Depois de execução aprovada e concluída, continuar automaticamente análise/preparação não privilegiadas das fases 4B.8–4B.9. [Comandos estruturados atuais](evidencias/retomada-comandos-apos-limpeza-definitiva.json).

## Execução autorizada — tentativa 4 e runtime Apache

O usuário autorizou o probe do executor phase4b3-yqj_nck2 e a instalação pelo release-o9fx0a_a. O probe publicou atestado root-owned probe_passed, após verificações de namespaces/capabilities/rede/RO, fsck/hash e guard do host. A permissão do probe foi restaurada para false; com 63,39 GiB disponíveis, iniciou-se a instalação sequencial autorizada.

A Base passou na simulação de versões e no novo preflight de todos os caminhos canônicos antes de unpack. A **chamada real APT concluiu**, e o guest prosseguiu para apt-mark, dpkg --audit vazio e apt-get -s check sem erros. O locale pt_BR.utf8 estava presente. Isso supera os três erros anteriores do cache; não equivale ao aceite final do rootfs. Os perfis posteriores e a verificação completa de componentes protegidos ainda não foram concluídos.

A etapa apache2ctl -t abortou: `mktemp: failed to create directory via template '/var/lock/apache2.XXXXXXXXXX': No such file or directory`. /var/lock aponta para /run/lock; o worker monta um /run tmpfs novo, sem o preenchimento normal do boot/systemd-tmpfiles, e preparava /run/apache2 sem criar seu diretório irmão de locks. A implementação de mkdir_chown no apache2ctl do deb Ubuntu verificado confirmou o uso de mktemp nesse pai. O script foi inspecionado por leitura do archive, sem executá-lo no host.

O controlador colocou a tentativa em **quarantined**. A Live não iniciou, não existe accepted-pair e nenhuma integração/ISO pode usar essa saída. Os pacotes foram efetivamente instalados na cópia Base, mas ela não está aprovada, não será retomada in-place e permanece preservada para auditoria. [Evidências da tentativa 4](evidencias/instalacao-4b7-tentativa4.json). O guard confirmou banco dpkg e arquivos críticos do host idênticos; unidades inativas, nenhum mount/loop residual e executor_autorizado restaurado para false. Não foram removidos artefatos adicionais.

Correção: executor_worker.runtime_directories prepara no alvo var/lib/devlite-executor/lists/partial, run/apache2 e run/lock (modo 1777) antes de chamar o guest. A mudança afeta somente os diretórios do runtime privado, sem novas capabilities, mounts ou rede e sem instalar ou modificar pacotes no host. /run continua tmpfs e essa preparação temporária não se confunde com persistência pós-instalação. Os guards de disco e limites continuam iguais.

**168 testes aprovados** em reports/testes-runtime-apache.txt. Duas novas regressões em tests/test_runtime_directories.py executam mktemp real em fixture: falha quando falta o pai, sucesso depois da preparação, modo sticky correto e recusa de ancestrais symlink. Não executam Apache/daemon, chroot ou montagem no host. O preflight completo de 240/239 caminhos continua como evidência da lógica APT, que não foi alterada por essa correção; não foi repetido sem necessidade. A validação real apache2ctl -t com a correção permanece pendente de execução autorizada.

A mudança de runtime altera o código congelado; o atestado anterior é uma evidência válida daquela versão, mas não libera a nova. Preparar novo contrato/probe sem modificar recibos antigos nem relaxar checks. A nova tentativa usará imagens novas e não recuperará dpkg da quarentena automaticamente. Há espaço acima dos 56 GiB mínimos; reavaliar orçamento de instalação após o probe. A próxima instalação pode ainda encontrar falhas em manutenção/validações não exercitadas, e o isolamento compartilha kernel. Integração/ISO/VMs permanecem fora do escopo da autorização de instalação.

## Próxima tentativa preparada após correção de runtime

[Contrato/cache](evidencias/instalacao-4b7-runtime-corrigido.json), [comandos exatos](evidencias/instalacao-4b7-runtime-comandos.json). Novos diretórios: `/home/magaton/DevLite-OS/work/release-ku78mn3t` e `/home/magaton/DevLite-OS/work/phase4b3-wnej6dpv`, sem probe/instalação. Revalidado cache dos 243 debs; código e plano congelados, gates false. Comandos que exigem autorização específica:

```sh
sudo /usr/bin/python3 /home/magaton/DevLite-OS/scripts/executar-programas.py --probe --job /home/magaton/DevLite-OS/work/phase4b3-wnej6dpv --approval-sha256 f15771792cc7e9c1abdaaf6f223e13002fd7436ab55d76ef4fe58b2eefb5b115
# SOMENTE com retorno zero e atestado root-owned deste contrato:
sudo /usr/bin/python3 /home/magaton/DevLite-OS/scripts/instalar-release-root.py --job /home/magaton/DevLite-OS/work/release-ku78mn3t --approval-sha256 9e6ca71886ea6d2ef381267a1380aada2ca6fa8df24329119ea1fc4975ad25b1
```

Escopo: novo probe e instalação offline sequencial Base → Live em novas cópias, com auditorias e restauração das permissões. Sem integração, ISO, VMs, nova aquisição, mudança de volumes ou exclusões. Os limites e riscos de scripts de manutenção permanecem; após aceite do par, continuar análise/preparação não privilegiada. A autorização anterior delimitava os contratos já executados: a mudança em runtime exige esta nova aprovação, sem modificar o atestado histórico.

## Instalação aceita — tentativa 5

O probe da versão com runtime corrigido terminou com retorno zero e atestado root-owned para phase4b3-wnej6dpv. Restaurada a flag do probe, o wrapper aprovado instalou sequencialmente Base e Live, após validar fontes/cópias e cache local. A simulação e a cobertura de todos os caminhos APT precederam cada instalação real; não houve novos downloads ou pacotes no host.

A Base concluiu 227 pacotes novos e 13 atualizações; a Live, 223 novos e 16 atualizações. Ambas passaram em dpkg --audit vazio, APT check, estados/versões exatos do lock, banco dpkg/manifestos de arquivos, perfis de PHP/MariaDB/Docker, Apache Syntax OK e máscaras dos serviços. O inventário protegido permaneceu idêntico: 477 itens na Base e 43.701 na Live, preservando boot/instalador/snap pertinentes a cada visão. Os workers terminaram com retorno zero. Fsck somente leitura e SHA-256 passaram para as duas imagens; somente após ambos foi publicado accepted-pair e journal accepted. O wrapper exportou installation-result.json root-owned e restaurou executor_autorizado=false.

| Imagem privada preservada | SHA-256 | Tamanho lógico |
|---|---|---:|
| `/home/magaton/DevLite-OS/work/phase4b3-wnej6dpv/attempt/base.ext4` | `1afd8b0caba906a555099faca6066acf4826e9de14867358f9d908be6679f30b` | 12 GiB |
| `/home/magaton/DevLite-OS/work/phase4b3-wnej6dpv/attempt/live.ext4` | `b69ca4b77ef71470aec0deb74b9bad54bbc1d25a83ae574ab318f6c03d288394` | 12 GiB |

Pacotes finais: Base **1393**, Live **1534**. O par é composto por visões completas, e o delta entre elas ainda não foi gerado. Somente esse par aceito pode seguir para integração.

O guard confirmou /var/lib/dpkg/status, APT, passwd/group/fstab/fontes do Ubuntu Server inalterados. Unidades inativas, nenhum mount/loop residual. Todos os gates de probe, instalação, recuperação, integração e ISO estão false. [Evidências/recibos e fsck](evidencias/instalacao-4b7-tentativa5.json). Não houve commits, exclusão adicional, nova ISO ou VM.

Depois da execução, 168 testes passaram novamente em reports/testes-apos-instalacao-aceita.txt. Uma auditoria adicional com debugfs **somente leitura, sem -w/mount/chroot**, confirmou nos dois arquivos ext4: locale LANG=pt_BR.UTF-8/LANGUAGE=pt_BR:pt, teclado br/abnt2, America/Sao_Paulo e link localtime correto, identidade DevLite OS preservando ID=ubuntu e perfis locais de Apache/MariaDB/PHP/Docker. Os links /etc/default/locale e /etc/os-release foram resolvidos dentro da imagem para /etc/locale.conf e /usr/lib/os-release; debugfs cat direto nos links não segue seus destinos. [Evidências das configurações](evidencias/configuracoes-par-instalado.json). Isso não valida comportamento gráfico ou persistência pós-instalação.

A preparação da integração foi atualizada com o recibo real, sem alterar código/contrato: work/release-ku78mn3t/integration-plan.json e [plano público](evidencias/integracao-apos-instalacao.json). O guard existente exige 32 GiB iniciais e, depois de montar inputs RO, recalcula 3×allocated_usage(Base)+5×allocated_usage(Live)+10 GiB. A estimativa de planejamento usa a ocupação total reportada por fsck (3,998/5,875 GiB) e resulta em 51,37 GiB; não é uma autorização nem substitui o cálculo real. Há 41,28 GiB livres após guardar as duas imagens e o probe. Nenhum limite foi reduzido: 56 GiB continua sendo o mínimo para iniciar novos probes; a integração tem seu guard próprio já implementado.

O checklist work/release-ku78mn3t/acceptance-ubuntu-experimental.json foi preparado para o escopo real dos pacotes Ubuntu. Seu relatório incompleto continua corretamente rejeitado pelo validador, sem ISO fornecida ou evidência fictícia. A edição full-edition permanece pendente de Node.js LTS, TypeScript e VS Code. BIOS/UEFI, XFCE, abertura funcional dos programas, instalação em disco descartável e reinicialização sem ISO precisam de testes reais futuros. Nenhuma VM foi criada/iniciada.

## Próxima operação proposta — sem execução

[Plano de integração do par aceito](fase4b8-integracao-par-aceito.md): sete arquivos antigos para recuperar 12,16 GiB, preservando as duas imagens aceitas, todos os insumos e evidências. Projeção de 53,43 GiB livres para estimativa conservadora de 51,37 GiB. Depois da aprovação da lista exata e do comando, integrar SquashFS em namespace privado; nenhuma ISO nesta operação. Ainda não houve exclusão adicional, integração ou construção. Os 56 GiB continuam sendo o guard de início de probes, já concluídos para o código atual.
