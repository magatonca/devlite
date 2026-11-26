# Diagnóstico da v4 — preparação da v5

Auditoria de 24/11/2026. Escopo executado: leitura, documentação e testes existentes não privilegiados. Nenhuma instalação/remoção de pacote do host, mudança de serviço, montagem, chroot, ação na VM Hyper-V ou construção de ISO. As pequenas imagens SquashFS dos testes são fixtures temporárias; não são uma distribuição nova.

## Integridade e preservação

| Artefato | Resultado desta auditoria |
|---|---|
| `artifacts/modern-release-owcgr3mg/devlite-os-1.0-amd64.iso` | 3.645.308.928 bytes; SHA-256 `4adf369ea22ef5dd6c49da2db9fd70ea5620219d4636489a0933a2bb57bb5564`, igual ao solicitado |
| v3: `artifacts/modern-release-vz4edu99/devlite-os-1.0-amd64.iso` | SHA-256 `7373cb9be11ebda5218f20795fec87eab20c2cebef3c763ae6e5c63d4e7cd7bd`, igual à referência usada na v4 |
| Candidate pack | `work/modern-candidate-pack-4cnl99z8`, contrato `babdc55e0604d96180f7df8c2a89d6cd3712934ee7442b60216f9e66f00b25b1`; preservado, sem reempacotamento |
| Cinco camadas da v4 | Cópias de inspeção conferidas contra `/casper/SHA256SUMS`, lido da ISO cujo hash foi verificado |

O Git está em `main`, commit mais recente `fd6c719`. Há nove arquivos rastreados modificados e grande quantidade de fontes/documentos não versionados, anteriores a esta auditoria. Nada foi revertido, adicionado ao índice ou commitado. `git check-ignore` confirmou que ISOs, pack e ISO fonte estão ignorados; os diretórios aparecerem como não versionados no status não significa que seus arquivos grandes serão incluídos. O README ainda descreve 259 testes e fases anteriores: é documentação histórica desatualizada, não o estado da v4. Não foi sobrescrito.

As evidências ficam em [evidencias/](evidencias/): preservação inicial/final, integridade, camadas, componentes e saída dos testes. A preservação compara conteúdo das fontes e metadados dos artefatos; leituras podem atualizar atime, que não é usado como sinal de alteração. Nenhuma cópia grande foi criada.

## Resultados reais informados pelo usuário

Hyper-V Generation 2: instalação e XFCE funcionais; 3,8 GiB RAM, 814 MiB usados, 3,0 GiB disponíveis, swap 0 B; 9,7 GiB de disco; inicialização total 23,170 s e marco gráfico informado de 18,237 s em userspace. DevControl 1.0 e Epiphany funcionam. Apache, MariaDB e Docker funcionaram após desmascaramento/início manual das dependências. OpenSSH Server foi instalado manualmente depois.

São resultados externos fornecidos pelo usuário; não houve repetição nesta auditoria. O `release-report.json` original continua com `vm_tested: false`, como emitido pelo build: não foi adulterado para incorporar o relato posterior. BIOS real da v4 e Secure Boot não foram comprovados por esse relato Gen2.

## Estrutura real e transferência ao instalado

O catálogo lido diretamente da ISO é `fsimage-layered`, ID `xubuntu-desktop-minimal`, caminho `minimal.visual.fix.squashfs`. O GRUB aponta o Live para `layerfs-path=minimal.visual.live.fix.squashfs`.

Ordem abaixo: inferior → superior, conforme composição implementada e catálogo/GRUB:

- Instalado: `minimal.squashfs` → `minimal.visual.squashfs` → `minimal.visual.fix.squashfs`.
- Live: `minimal.squashfs` → `minimal.visual.squashfs` → `minimal.visual.live.squashfs` → `minimal.visual.live.fix.squashfs`.

O Live não inclui automaticamente a camada instalada `minimal.visual.fix`. Uma correção só nela não corrige o Live; uma remoção no Base compartilhado pode quebrar o instalador. As duas camadas `fix` corrigem o DevControl; a Live também personaliza atalhos do instalador em `/var/lib/snapd/desktop/applications`, mas não corrige serviços.

## Causas confirmadas

1. `pipeline/devlite/customize/service_profiles.py` define sete máscaras persistentes: Apache, MariaDB, alias MySQL, Docker, socket Docker, containerd e iperf3. A exportação declara `masks_persistent: true`.
2. `customize/executor_worker.py::inside()` cria links em `/etc/systemd/system/<unit>` para `/dev/null` antes do APT. O `service_guard()` restaura apenas `policy-rc.d`; não remove essas máscaras no final. A documentação 4B.2 e os testes mostram que a persistência era uma política histórica deliberada para impedir ativação no boot, não apenas um guard temporário esquecido. Essa política é incompatível com o requisito v5 de disponibilidade manual sem máscaras.
3. As sete máscaras estão de fato no `minimal.squashfs` e no delta `minimal.visual.live.squashfs`. As três camadas visuais não as ocultam/corrigem. Assim chegam ao instalado e ao Live. Não é necessário supor que o instalador tenha criado as máscaras; eventual ação adicional dele não foi investigada em execução.
4. O helper antigo `/usr/libexec/devlite-service-control`, presente no Base e no overlay histórico, faz `unmask`, executa a ação e chama `mask` em `finally`. Também remascara após falha. Isso pode reintroduzir o problema mesmo depois de uma correção apenas nas imagens.
5. Docker instalado usa `Requires=docker.socket`, `Wants=containerd.service`, `After=containerd.service` e `--containerd=/run/containerd/containerd.sock`. `Wants` não garante sucesso do runtime. A máscara de containerd impede sua inicialização; desmascarar só Docker não resolve o grupo.
6. Existem dois frontends: `devlite-control`/atalho terminal antigo e DevControl 1.0 GTK (`/usr/lib/devlite/devcontrol`). O coletor gráfico é somente leitura, com hash igual ao protótipo nas duas camadas fix. Ele não é quem aplica/remova máscaras.

Os testes antigos de `test_final_preparation.py` inclusive exigem remascaramento; passaram porque validam a política histórica. Não validam a correção proposta da v5.

## Pacotes e dependências observados

Bancos dpkg: 1.403 pacotes instalados no Base e 1.544 no estado completo armazenado no delta Live. Camadas visuais superiores não contêm outro dpkg/status.

| Componente | Base instalado / Live |
|---|---|
| snapd | ambos `2.76.3+ubuntu24.04` |
| cloud-init | ambos `26.1-0ubuntu1~24.04.1` |
| openssh-client | ambos `1:9.6p1-3ubuntu13.20` |
| openssh-server / php8.3-fpm | ausentes em ambos |
| docker.io / containerd | ambos `29.1.3-0ubuntu3~24.04.2` / `2.2.1-0ubuntu1~24.04.4` |
| thermald | ausente no Base; presente no Live |
| ubuntu-advantage-tools | ausente; existe `ubuntu-pro-client` em ambos |

O metapacote `xubuntu-desktop-minimal` recomenda snapd e cloud-init. O grafo por nomes dos pacotes instalados não encontrou `Depends`/`Pre-Depends` reversos diretos desses dois; há recomendações/sugestões. Isso não é uma simulação APT completa: não resolve provedores virtuais nem ações de manutenção, e não prova que o instalador dispense esses componentes.

O Base não contém snaps instalados em `/var/lib/snapd/snaps` além de `partial`; o delta Live contém core22, snapd e ubuntu-desktop-bootstrap nas áreas de seed/snaps, com assertions. A unidade de usuário `xubuntu-installer.service` executa `/snap/bin/ubuntu-desktop-bootstrap --try-or-install`. O relato `snap list` vazio no instalado não se aplica ao Live.

## Limites e testes

`cloud-init.service` e outras etapas verificam o marcador `/etc/cloud/cloud-init.disabled`; ele não foi encontrado nas camadas. Sua presença no sistema instalado relatado deve ser correlacionada com logs do instalador e boot. Não foi confirmado quando nem por qual processo ele foi criado. A unidade de rede do cloud-init pede `sshd.service`; `cc_set_passwords` inspecionado só reinicia SSH em systemd quando ele já está ativo/ativando/recarregando. É necessário testar aliases/ativação ao adicionar o servidor.

588 testes existentes passaram sob Xvfb, sem skips no resumo; GTK testado com coletor simulado, sem operações administrativas reais. `scripts/verificar-projeto.py`: zero erros. Não houve nova homologação do boot, da VM ou da correção v5. Matriz e pendências: [checklist-validacao.md](checklist-validacao.md).

## Arquivos e evidências analisados

- README, `.gitignore`, `docs/arquitetura.md`, `seguranca-validacao.md`, planos 4B.2/4B.3, `devlite-control2-plano.md`, `camada-visual-modern-v3.md`, READMEs de pipeline/overlay/testes.
- `pipeline/devlite/customize/{service_profiles,executor_worker,guest_runner,installation,executor_contract,settings}.py`, `browser_executor.py`, módulos `modern_{catalog,layers,integration,identity,validation}_v4.py` e `modern_visual.py`.
- `scripts/gerar-iso-modern-v4.py`, geração/empacotamento existentes, verificador de projeto; contrato da v4 e recibos do candidate pack.
- Overlay `final-candidate` (CLI, helper, policy Polkit, desktop), overlay `modern-release-v1` e protótipos `devcontrol`, `control2` e Modern. O planejamento antigo Control2 ainda previa remascaramento em alguns fluxos; a arquitetura v5 substitui essa política, sem modificar a referência histórica.
- `tests/test_{executor,installation_plan,final_preparation,devcontrol,devcontrol_gtk,apt_local_archives,...}.py`, saída integral dos 588 testes e relatórios de integridade da ISO.
- ISO v4: catálogo, GRUB e checksums lidos diretamente; cinco SquashFS inspecionados com `unsquashfs -cat/-lln`; units vendor, máscaras, bancos dpkg, seeds/launcher do instalador, código cloud-init e DevControl efetivamente embarcado.

Limite: não há journal, critical-chain completo ou logs curtin da instalação Hyper-V nesta auditoria. Não foram executados diagnóstico de serviços no host como substituto, purge simulado de Snap em nova raiz, start/stop de serviços ou testes administrativos reais da v5.
