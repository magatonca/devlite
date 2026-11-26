# Progresso da v6

## 25/11/2026 — pré-voo e primeiros ajustes

- Plano recebido. ISO anterior, camadas, recibos e arquivos históricos seguem em seus destinos existentes. Backup histórico conferido.
- ext4 com cerca de 50,54 GiB livres. O pack incremental foi orçado em 8 GiB com base no pipeline v5. Montagem com imagem e árvore de referência foi orçada em 8,80 GiB. Extração e verificação, em 4,40 GiB. Pico incremental acumulado de 21,20 GiB mantendo os temporários. Com reserva de 10 GiB, o pré-voo exige 31,20 GiB. O orçamento presume duas folhas incrementais e precisa ser recalculado se o plano exigir uma árvore Live completa, expansão do snap ou disco de VM no host.
- `python3 -B -m v6.storage all` calcula o orçamento. Para etapas não privilegiadas no filesystem do projeto, `python3 -B -m v6.storage ETAPA -- COMANDO` verifica a próxima operação e monitora o espaço durante a execução. O monitor inicia a parada preventiva a 10,5 GiB. Integrar verificações internas nas operações volumosas antes da montagem.
- Overlay inicial criado para Apache e slide pt-BR. Ainda não empacotado. Resultados e lacunas em `validacao.md`.
- Retomar pela reprodução AppArmor em XFCE/X11 representativo e pelo rastreamento das traduções incorporadas ao instalador. Avançar DevControl, cURL e política de serviços em paralelo com a validação do guest. Selar pack, executar a suíte completa e só iniciar a ISO após os gates críticos. Nenhum build v6 iniciado.
- Integridade da ISO v5 verificada por leitura completa. SHA-256 corresponde ao valor informado no plano. Três testes de regressão do pré-voo passaram.

## 25/11/2026 — candidata e validações no host

- A validação XFCE/X11 real foi transferida para o Hyper-V. Continua necessária para distribuição e deixou de ser condição para iniciar a candidata.
- Perfil AppArmor candidato em `config/v6/epiphany.apparmor`. Sintaxe compilada em modo somente leitura, sem carga de política. Script de coleta em `v6/hyperv-diagnostics.sh`.
- Overlay v6 aplicável a raízes descartáveis por `v6.payload.apply`. Inclui Apache, quatro slides pt-BR, DevControl 3.0 em desenvolvimento e link oficial do VS Code. Aplicação testada em diretórios temporários para Base e Live, sem composição de imagem.
- cURL e duas bibliotecas 8.5.0-2ubuntu10.16 adquiridos em `work/v6-curl-noble-security`. Assinatura InRelease, hash do índice amd64 e hashes dos três pacotes conferidos. Simulação com o estado dpkg extraído de cada folha v5 concordou em instalar um pacote e atualizar dois, sem remoções. Nenhuma instalação de pacote ocorreu.
- Janela GTK abriu e fechou em Xvfb. O aviso AT-SPI confirma que o ensaio não representa a sessão XFCE completa. Seis testes v6 aprovados. Suíte completa em `work/v6-validation/suite.log` e `suite.json`: 651 executados, 646 aprovados, 1 falha, 4 erros, 0 skips. As cinco divergências estão em testes históricos de ownership de checkpoint/atestado ou da baseline v3. Verificador do projeto retornou 0 erros.
- Bloqueio de build confirmado: `sudo -n` exige senha, `unshare -m` foi recusado e `unshare -Um` não pôde privatizar a propagação. O pack precisa de namespace isolado, montagens SquashFS/overlay e execução do dpkg exclusivamente no guest. Nenhuma camada v6 nem ISO foi gerada e não houve novas exclusões.
- Retomar com um executor autorizado para o pack. Resolver as cinco falhas no ambiente compatível com os testes históricos. Integrar a aplicação do payload e a transação cURL ao pack v6 com recibos próprios, comparar a composição Base/Live, conferir instalador e serviços, e só então montar e verificar a candidata. Manter a reserva de 10 GiB.

## 25/11/2026 — suíte corrigida e executor manual

| Resultado anterior | Teste | Causa |
|---|---|---|
| Falha | `test_public_attestation.AttestationTests.test_readonly_diagnostic_blocks_changed_image` | A imagem de teste herdava modo 0664 da umask 0002. A validação de metadados rejeitava a fixture antes da comparação de integridade que o teste pretendia exercitar. |
| Erro | `test_public_attestation.AttestationTests.test_readonly_diagnostic_preserves_query_error_and_image_bytes` | A mesma fixture de imagem era gravável pelo grupo. |
| Erro | `test_modern_candidate.ModernCandidateTests.test_checkpoint_validation_pins_contract_report_lock_and_clone_hashes` | Os diretórios e arquivos da fixture herdavam escrita por grupo. O primeiro erro ocorreu no diretório do job. |
| Erro | `test_modern_candidate.ModernCandidateTests.test_packer_creates_resume_reference_only_for_matching_failed_job` | Recibos da fixture graváveis pelo grupo. |
| Erro | `test_modern_candidate.ModernCandidateTests.test_host_baseline_v3_accepts_only_the_authorized_gtk_xvfb_transition` | O teste unitário lia o host real. `/var/lib/dpkg/status` e `/var/lib/apt/extended_states` divergiam do baseline histórico selado. |

Os quatro problemas de permissões foram corrigidos nas fixtures com modos explícitos 0700/0600. As verificações de propriedade e integridade da produção foram preservadas. O teste de baseline passou a reproduzir o estado histórico selado e continua verificando a rejeição de divergências de execução e de mudanças não autorizadas na transição. Nenhuma das cinco ocorrências foi uma regressão funcional da v6. Nenhum arquivo do APT, baseline ou artefato histórico foi alterado. Cinco testes afetados e dez testes v6 passaram na execução direcionada. A suíte final executada uma vez em Xvfb teve 655 aprovados, zero falhas, zero erros, zero ignorados. Verificador do projeto com 0 erros. Recibo em `work/v6-validation/final-suite.json` e log em `work/v6-validation/final-suite.log`.

O DevControl 3.0 passou a mostrar barras de CPU, memória, swap e disco, conectividade informada pelo NetworkManager, resumo de serviços e descrições. A parada só é confirmada quando o estado real de cada unidade afetada é parado ou falhou. Polkit, controle de boot separado e restrição do Containerd permanecem integrados. O uso real no guest segue pendente.

### Execução manual

Somente após autorização administrativa, em uma sessão SSH interativa como magaton, com revisão prévia do código que o serviço privilegiado carregará do workspace:

```bash
bash /home/magaton/DevLite-OS/v6/build-manual.sh --execute-authorized
```

O lançador exige o recibo de testes correspondente ao código atual. A autenticação sudo é interativa. O serviço systemd isola rede, montagem, PID, IPC e UTS, limita memória, CPU e tarefas, protege o sistema e escreve no estado exclusivo `/var/lib/devlite-v6`. O worker confere hashes da ISO e das camadas, autentica o payload cURL, executa APT offline com capacidades reduzidas no guest, valida a composição Base/Live e desmonta em ordem inversa antes de publicar recibo. Logs ficam no journal, em `work/v6-manual-*/pack.log` e, para o administrador, no diretório do pack. Ante uma falha, examinar o último `audit.json` e preservar a tentativa. A montagem posterior roda como magaton e publica uma nova ISO apenas depois da verificação estrutural. A reserva é de 10 GiB, com pré-voo de 31,20 GiB e 50,53 GiB disponíveis na última medição.

O executor passou nas verificações estáticas e em testes não privilegiados de caminhos, limpeza e metadados. A execução privilegiada completa permanece sem teste. Nenhum empacotamento foi iniciado. Depois do pack, validar no Hyper-V o Epiphany em enforce, os textos e os slides realmente renderizados pelo instalador, Polkit e persistência dos serviços. Os textos internos do assistente herdado continuam pendentes de solução no instalador de origem.

## 25/11/2026 — prioridade visual do instalador

- Inspecionada a revisão 572 existente no Live. Overlay oficial de whitelabel estendido às telas configuráveis, com logo DevLite, temas claro/escuro, botões contrastados, nome e descrição pt-BR no catálogo e quatro slides revistos em pt-BR e en-US. A montagem existente inclui esses recursos na mesma candidata quando autorizada.
- Verificações estáticas aprovadas no YAML, no catálogo herdado, nos formatos do logo, nos slides e no contraste dos pares configurados. Suíte com 657 aprovados, zero falhas, erros ou ignorados. Verificador do projeto com zero erros. Recibo separado em `work/v6-validation/installer-visual-suite.json`, com preservação do recibo anterior.
- **Candidata em espera.** Temas, imagens e catálogo foram implementados. Os cabeçalhos e textos internos do assistente que interpolam Xubuntu, a tipografia e problemas de layout do código Flutter seguem pendentes. O snap original, as assinaturas, os créditos e as ISOs anteriores foram preservados. Não operar o executor manual enquanto vigorar a prioridade de concluir essa personalização antes da candidata. O checklist visual e os limites por tela ficam em `validacao.md` e `correcoes.md`.

## 25/11/2026 — candidata liberada para construção manual

- A etapa visual existente foi autorizada para homologação. O snap oficial continua assinado e o frontend Flutter permanece intacto. Textos internos que ainda mencionam Xubuntu, ajustes finos de fontes, espaçamento e layout foram encaminhados para a v7. Esta decisão substitui a suspensão visual do checkpoint anterior.
- O overlay de identidade do instalador entra somente na composição Live. O empacotador verifica as duas composições, e a montagem usa o catálogo pt-BR e as referências Base/Live atualizadas. Os renderizadores foram conferidos com o catálogo e GRUB reais da v5, sem montagem.
- DevControl 3.0, Polkit, perfil Epiphany e Apache entram em Base e Live. O código contém as métricas, os estados independentes de boot e execução, as ações assíncronas e as proteções de dependências do Docker e do Containerd. O comportamento no sistema convidado permanece na homologação Hyper-V.
- cURL e as duas bibliotecas de versão fixada estão disponíveis com os hashes esperados. O executor aplica e confere a transação offline em Base e Live; a inclusão no artefato será confirmada pelo recibo do pack. Os manifestos v5 contêm PHP, Composer, Apache, MariaDB, Git, Docker, Compose, Python, OpenVPN, SSH, Impress e ferramentas de rede. Node.js, NPM e TypeScript foram localizados na camada herdada. VS Code por link oficial para instalação sob demanda.
- Conferidos sintaxe Bash e Python, parâmetros de isolamento do serviço, paths autorizados, escopo e ordem de desmontagem no código e a validade do recibo existente de 657 testes com zero erros no verificador. Nenhum teste já aprovado foi reexecutado. Nenhum comando privilegiado, exclusão ou montagem foi executado.
- Espaço livre no pré-voo: 54.131.515.392 bytes (50,41 GiB). Pico incremental estimado: 22.763.601.920 bytes (21,20 GiB). Reserva 10 GiB. Mínimo do pré-voo: 31,20 GiB.
- Para gerar a candidata, o administrador deve executar em sessão SSH interativa como magaton: `bash /home/magaton/DevLite-OS/v6/build-manual.sh --execute-authorized`. Saída esperada em `artifacts/devlite-v6-*/devlite-os-1.0-v6-amd64.iso` com `SHA256SUMS` e `validation.json`. A execução completa e o resultado no Hyper-V permanecem pendentes. A ISO resultante será candidata de homologação.

## 25/11/2026 — requisito DevControl 3.0 atendido no host

- Finalizados o dashboard compacto em pt-BR, as métricas, as versões de ferramentas, a indicação de estado por serviço e o interruptor de inicialização com releitura do systemd. O DevControl 3.0 substitui a aplicação no mesmo caminho instalado. O pack de Base e Live retira o atalho, os helpers e as políticas antigas somente nas árvores descartáveis. A v5, o snap oficial e os demais artefatos históricos foram preservados.
- Sete testes afetados passaram sem falhas ou skips, incluindo substituição Base/Live, ausência de duplicidade, Docker/Containerd, negação e cancelamento Polkit e interface GTK a 640×440. Verificador do projeto com zero erros. O gate confirmou a identidade dos arquivos fora do escopo alterado e vinculou `work/v6-validation/devcontrol-suite.json` ao recibo anterior de 657 testes. A suíte completa anterior não foi reexecutada.
- O gate de código e integração está liberado para execução manual. O executor e a reserva de 10 GiB permanecem como no checkpoint anterior. Nenhum pack ou montagem foi iniciado. A homologação funcional e visual definitiva permanece no Hyper-V.

## 25/11/2026 — identidade do painel XFCE

- Os padrões nativos do Whisker em `/etc/xdg/xfce4/whiskermenu` e `/etc/xdg/xdg-xubuntu/xfce4/whiskermenu` agora apontam para o SVG oficial `/usr/share/icons/hicolor/scalable/apps/devlite.svg`. O botão segue no modo somente ícone, que usa `button-title=Menu DevLite OS` como tooltip. Foram removidas apenas as traduções herdadas do título desse botão, para que o tooltip seja o mesmo em qualquer locale.
- O overlay aplica os padrões à Base e ao Live. Favoritos, comandos, XML do painel, mecanismo de busca e configurações individuais foram preservados. Nos dois layouts de painel inspecionados, nenhuma outra referência a logotipo ou ícone Xubuntu foi encontrada. Nenhum código do XFCE, plugin ou arquivo histórico foi alterado.
- O teste afetado passou para Base, Live e preservação de perfil existente. A verificação do projeto retornou zero erros. O gate validou o encadeamento dos recibos até `work/v6-validation/xfce-suite.json`. Nenhuma montagem, operação privilegiada ou construção foi executada. A mudança segue no mesmo fluxo da candidata v6.

## 25/11/2026 — correção da primeira tentativa manual

- A tentativa `/var/lib/devlite-v6/pack-mbsm_dfu` parou em `apply(root, "base")` após 13 min 06 s. A política v6 no checkout é um arquivo regular `magaton:magaton` em modo 0664. O instalador do overlay copiava o modo e aplicava chmod após criar o arquivo, portanto a umask 0077 do worker não impedia escrita por grupo no destino. A validação privilegiada rejeitou corretamente a política. O destino já constava da lista de caminhos autorizados.
- Apenas os modos dos dois recursos privilegiados foram fixados na instalação: política em 0644 e helper em 0755. O helper estava em 0755 no checkout, mas usava o mesmo mecanismo vulnerável à umask original. Os módulos Python já eram aplicados em 0644. Checagens de propriedade, escrita, links e ancestrais foram preservadas. A política continua exigindo `auth_admin` em sessão ativa e apontando para o helper v6. Não houve alteração no host nem em arquivos históricos.
- Onze testes afetados passaram, incluindo origens 0664/0775, aplicação Base/Live, links rejeitados e ancestral gravável rejeitado. Verificador zero erros. Recibo `work/v6-validation/polkit-fix-suite.json` confirmado pelo gate. Espaço livre observado 48,14 GiB, acima dos 31,20 GiB exigidos com reserva.
- Limpeza observada: journal registra saída do serviço às 13:59:09 UTC. Unidade inativa, sem PID remanescente, sem referência ao job em 117 arquivos mountinfo legíveis e sem backing loop ativo. `audit.json` fica atrás de diretório root:root 0700, sem leitura por magaton. Para confirmar o recibo, o administrador pode executar `sudo cat /var/lib/devlite-v6/pack-mbsm_dfu/audit.json` e verificar `status: quarantined` e `cleanup_errors: []`. O diretório é descartável após essa confirmação e preservação do recibo conforme necessário. Nenhuma exclusão ocorreu.
- Nova tentativa manual em SSH como magaton: `bash /home/magaton/DevLite-OS/v6/build-manual.sh --execute-authorized`. O executor cria um novo pack e não reutiliza a tentativa interrompida. Nenhuma nova operação privilegiada foi iniciada.

## 25/11/2026 — correções do guest após a segunda tentativa

- Apache: `RestrictAddressFamilies=AF_UNIX` impedia abrir o socket do listener IPv4 até no teste de configuração. O executor agora permite exclusivamente `AF_UNIX AF_INET AF_INET6`, conserva `PrivateNetwork=yes` e as demais proteções, sem CAP_NET_ADMIN. O guest exige que apenas `lo` esteja presente e testa bind IPv4/IPv6 em portas efêmeras. A instalação APT continua offline.
- man-db: a raiz do overlay gravável recebia o modo 0700 do diretório upper criado sob umask 0077. O trigger reduz credenciais para `man`, cuja travessia da raiz depende do modo do guest. A biblioteca herdada está em 0644, com `/usr/lib/man-db` em 0755, e esse caminho está no RUNPATH. O cache do loader continuou 0644 no ensaio de umask. A correção copia apenas o modo 0755 da raiz de referência root:root para o upper novo, mantendo o diretório pai do job em 0700. O guest agora exige também retorno zero de `setpriv --reuid man --regid man --init-groups -- /usr/bin/mandb -pq` porque o gatilho original ignora seu retorno. A confirmação no overlay real fica no probe.
- Oito testes afetados passaram, sem skips, e o verificador teve zero erros. Recibo `work/v6-validation/guest-fix-suite.json` aceito pelo gate. Pré-voo com cerca de 45,85 GiB livres, mínimo 31,20 GiB incluindo a reserva de 10 GiB.
- O administrador confirmou `cleanup_errors: []`, sem montagens nem loops associados à segunda tentativa. Os arquivos `audit.json` e `guest.log` ficam em diretório restrito a root e não foram lidos diretamente como magaton. Preservar a tentativa como entrada do probe.
- Validação manual em SSH como magaton: `bash /home/magaton/DevLite-OS/v6/build-manual.sh --validate-guest pack-_kl0txm8`. Monta em leitura as camadas Base já extraídas, copia o upper interrompido para um job privado, registra o modo anterior e os caminhos da biblioteca, executa somente verificações do guest com as mesmas restrições e desmonta. O modo de validação termina antes do pack publicável e da montagem da ISO. Aguardar `guest_checks_passed` e `cleanup_errors: []` antes de repetir `--execute-authorized`. Nenhum comando privilegiado foi executado nesta retomada.

## 25/11/2026 — chave efêmera para validação SSH

- O administrador confirmou no probe isolamento de rede IPv4/IPv6, dpkg, APT, Apache, mandb como `man` e cURL. O único novo bloqueio foi `sshd -t` sem chaves de fábrica, cuja ausência é intencional.
- O guest gera uma chave Ed25519 em diretório privado 0700 no tmpfs `/run`. `sshd -t` e `sshd -T` recebem a configuração real e a chave por `-f` e `-h`; a configuração efetiva é avaliada com contexto de login root. Não há inicialização de daemon. A limpeza do diretório ocorre em sucesso ou erro; o mount de `/run` também termina antes da criação do delta. A verificação de ausência de chaves de fábrica e a desativação offline de ssh.service e ssh.socket permanecem.
- Os demais comandos do guest foram revisados contra os resultados do probe. Eles já usam os recursos efêmeros ou somente leitura adequados e passaram no ensaio do administrador. Cinco testes afetados passaram, com zero erros no verificador. O gate aceitou `work/v6-validation/ssh-fix-suite.json`.
- Repetir apenas o diagnóstico manual em SSH: `bash /home/magaton/DevLite-OS/v6/build-manual.sh --validate-guest pack-_kl0txm8`. Aguardar `guest_checks_passed` e `cleanup_errors: []`. Nenhum comando privilegiado nem build completo foi iniciado nesta retomada.
