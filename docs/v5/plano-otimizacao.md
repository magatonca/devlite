# Plano de otimização da v5

Estado: proposta; nenhuma configuração aplicada. Priorizar correção de serviços e integração segura antes de perseguir segundos de boot.

## Estratégia de construção

Manter v3, v4, ISO oficial e candidate pack selado somente leitura. Criar contratos/áreas v5 novos, com preimages e allowlist, sem alterar os módulos históricos nesta fase. Usar o estado v4 como referência funcional, não reconstruir tudo indiscriminadamente.

É possível manter as cinco camadas atuais e criar overlays incrementais distintos para instalado e Live. Exemplo de nomes a validar no mecanismo existente: `minimal.visual.fix.v5.squashfs` para o instalado; `minimal.visual.live.fix.v5.squashfs` para o Live. O encadeamento deve ser calculado/testado, nunca inferido só pelos nomes. Reconstituir cada visão completa (inclusive por overlay copy-on-write com inferiores somente leitura, sem obrigatoriamente clonar imagens inteiras), aplicar operações autorizadas, calcular diff e materializar whiteouts/metadata; provar round-trip e composição pelo kernel. Atualizar catálogo, manifests, tamanhos, checksums e GRUB apenas em novas saídas.

A remoção de uma máscara herdada exige esconder o link inferior de maneira correta (por exemplo whiteout no overlay calculado); colocar um arquivo vazio não equivale a desmascarar. Se houver remoção de pacote, usar o APT/dpkg isolado para atualizar também o banco e arquivos de manutenção, não editar status à mão.

## Snap: conservar Live, avaliar instalado

**Confirmado:** o Live tem seed, assertions e três snaps do instalador; seu launcher depende de `/snap/bin/ubuntu-desktop-bootstrap`. Preservar snapd, socket, seeded, conexões e atualizações do instalador nesse ambiente. Não desligar `snapd.seeded.service` globalmente nem remover `/var/lib/snapd` da camada compartilhada.

**Instalado:** o Base contém o daemon mas não os snaps do instalador. É candidato a uma variante sem Snap, condicionado a:

1. Simulação APT em cópia/fixture do banco alvo com índices autenticados correspondentes. Remoção esperada explicitamente limitada a snapd; abortar se incluir metapacotes, bibliotecas compartilhadas, AppArmor, NetworkManager, resolved, Polkit ou qualquer item fora da lista aprovada. Não executar `autoremove` genérico.
2. Conferir ainda arquivos do metapacote, ganchos curtin/Subiquity, seeds e expectativas do primeiro boot. O grafo instalado por nomes não substitui o resolver nem o teste do instalador.
3. Preferir alteração apenas na visão instalada e overlay final exclusivo dela. Dessa maneira o Live conserva seus arquivos/banco atuais. Se a alteração ocorrer no Base compartilhado, regenerar também o delta Live para restaurar arquivos e estado necessários; nunca reutilizar o delta antigo cegamente.
4. Verificar instalado sem unidades/ativadores Snap residuais pendurados e Live com instalador funcional offline e online, inclusive atualização oferecida pelo instalador e cenário de drivers quando suportado. Não aplicar a opção a instalações com TPM-FDE/recursos dependentes de Snap sem uma análise específica.

O planejador histórico protege snapd e rejeita remoções. A v5 precisa de um plano separado, versionado e restrito à visão instalada; não afrouxar globalmente `PROTECTED` ou as barreiras que protegem o Live. Se os gates falharem, manter Snap na v5 e documentar o custo; não comprometer instalação por uma métrica.

## Cloud-init: primeiro provar onde ele é necessário

Foi observado o pacote nas duas visões, mas o usuário relatou desativação por marcador no instalado. O upstream documenta esse marcador como mecanismo suportado de desativação; isso não demonstra quando ele foi criado no caso real. [Referência oficial](https://docs.cloud-init.io/en/latest/howto/disable_cloud_init.html).

A configuração de autoinstall pode ser fornecida por cloud-init. Conservar esse caminho no Live; não acrescentar `cloud-init=disabled` ao GRUB Live nem remover suas etapas apenas para acelerar. [Interação oficial](https://canonical-subiquity.readthedocs-hosted.com/en/latest/explanation/cloudinit-autoinstall-interaction.html).

Plano conservador do instalado:

- Coletar, no mesmo boot, `cloud-init status --long`, `systemd-analyze time`, `critical-chain`, condições das unidades, mtime do marcador e logs do instalador. Separar primeiro boot e boots seguintes.
- Verificar se rede/Netplan/NetworkManager, hostname, usuário/sudo e chaves SSH dependem ainda dos módulos do primeiro boot. Não colocar o marcador numa camada de instalação antes dessa prova.
- Se o instalador já finaliza tudo e mantém o marcador, reaproveitar esse mecanismo e comprovar ausência de execução nos boots seguintes. Não empilhar máscaras redundantes.
- Se ainda há tarefas de primeiro boot, preservá-las. Uma desativação posterior somente no target deve ocorrer depois de conclusão bem-sucedida e permanecer reversível, sem apagar dados de diagnóstico. Não realizar `cloud-init clean` indiscriminadamente, pois pode alterar a determinação de primeiro boot.
- Manter configuração de rede já instalada; não desabilitar renderer nem remover netplan/io indiscriminadamente. Usuários de cloud/NoCloud precisam de perfil separado ou opção explícita.

Os tempos 4,715/3,451/1,094/0,800 s e 10,999/2,537 s de Snap não devem ser somados como ganho potencial. Dependências, esperas e execução paralela exigem o grafo do mesmo boot. O estado disabled atual não prova que todas as durações relatadas pertencem a esse mesmo estado.

## Demais serviços: classificação e decisão inicial

Presença abaixo deriva do banco instalado da imagem, não de serviços do servidor de desenvolvimento. Impactos são qualitativos; não há benchmark individual novo.

| Serviço/componente | Necessidade e impacto possível | Dependências/risco | Proposta inicial |
|---|---|---|---|
| Apport | Coleta de falhas; trabalho sob eventos, com possível disco/CPU em crash | Suporte e diagnóstico; integra handler de core dumps | Opcional por perfil/consentimento, medir; não remover agora |
| Kerneloops | Registro/relato de falhas do kernel; daemon pequeno | Perda de diagnóstico de hardware/kernel | Candidato opcional após verificar configuração e política de reporte |
| ModemManager | WWAN/modems e descoberta de hardware | NetworkManager o recomenda; pode ser necessário em notebooks/modems USB | Preservar padrão; não assumir ausência de WWAN por teste em Hyper-V |
| Avahi | mDNS e descoberta local | CUPS recomenda; impressão sem driver e nomes `.local` podem depender | Preservar; desligamento só em perfil sem descoberta, testado |
| CUPS | Impressão; serviço/socket/path podem ativar sob demanda | Impressoras, filtros e aplicações de escritório | Preservar impressão e ativadores coerentes; não desativar só o `.service` |
| Ubuntu Pro (antigo Advantage) | Assinatura, ESM e manutenção; timers/eventos | Pode fornecer atualizações de segurança estendidas | Preservar infraestrutura de segurança; não cortar ESM para ganhar tempo |
| Sysstat | Histórico de métricas; coleta periódica e escrita em disco | Útil para diagnóstico; serviço e timers precisam ser avaliados juntos | Opcional conforme necessidade; preservar durante comparação de desempenho |
| thermald / kernel térmico | Proteção/gerenciamento dependente de hardware | thermald está no Live, ausente no Base; ausência do daemon não prova ausência de proteção do kernel | Não remover proteções; avaliar necessidade no instalado em hardware físico |

AppArmor, UFW, atualizações de segurança/ESM, NetworkManager, systemd-resolved, sincronização de horário, proteção térmica e Polkit não são candidatos a cortes automáticos. Preservar Bluetooth, VPN, Wi-Fi, impressão e compatibilidade com hardware. `ufw.service` ativo/inativo não é sozinho prova das regras efetivas: validar firewall por sua configuração/estado apropriado na VM autorizada.

## Ordem e critérios de desempenho

1. Corrigir política final das máscaras e seus validadores históricos por perfil novo.
2. Planejar servidor SSH seguro e geração de chaves; evoluir o Control sem privilégios genéricos.
3. Experimento de Snap exclusivamente no instalado e evidências do cloud-init, cada um com rollback para os artefatos v4 preservados.
4. Somente então avaliar serviços opcionais, um grupo por vez, com validação funcional.

Comparar v4/v5 na mesma VM, CPU/RAM, disco e firmware; registrar 3–5 boots por variante, mediana e faixa, primeiro boot separado. Medir RAM após estabilização, swap, disco, `critical-chain` e logs. Os 814 MiB/23,170 s fornecidos são referência, não meta garantida. Nenhuma redução de consumo ou tempo foi comprovada nesta fase. Conferir reserva de disco antes de criar cópias; esta auditoria iniciou com aproximadamente 45,19 GiB livres, sem autorizar limpeza nem nova expansão.

## Recursos antes de executar a Fase 2

A prontidão para codificar não é autorização nem orçamento aprovado para executar instalação/empacotamento. Com aproximadamente 45,19 GiB livres, recalcular o pico do algoritmo v5, incluindo upper/work dirs, debs, overlays, verificação e saída. Não herdar uma estimativa de outro job nem simplesmente reduzir um gate para fazê-lo passar. Manter pelo menos a reserva operacional de 20 GiB e os limites de memória/paralelismo existentes. Se não couber, apresentar nova proposta de limpeza/expansão antes de criar raízes grandes. Não houve limpeza nesta auditoria.
