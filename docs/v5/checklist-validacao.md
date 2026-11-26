# Checklist da Fase 2 e da futura v5

Esta fase entregou planejamento. Marcação não significa teste de uma ISO v5 inexistente.

## Evidências concluídas nesta auditoria

- [x] README/documentação, scripts de build/geração, módulos de perfis/executor, overlays, protótipos, testes e relatórios examinados.
- [x] Git `main`/`fd6c719` e alterações preexistentes registrados; sem reset, clean, add ou commit.
- [x] SHA-256 v4 confere com `4adf369ea22ef5dd6c49da2db9fd70ea5620219d4636489a0933a2bb57bb5564`.
- [x] v3 confere com referência `7373cb9be11ebda5218f20795fec87eab20c2cebef3c763ae6e5c63d4e7cd7bd`.
- [x] Cinco camadas de inspeção conferem com checksums extraídos da v4 verificada; catálogo e GRUB examinados sem montagem.
- [x] Máscaras persistentes confirmadas na Base e no delta Live; remascaramento do helper legado identificado.
- [x] Bancos dpkg e dependências diretas/reversas por nomes examinados; servidor SSH e PHP-FPM ausentes.
- [x] Dependência Snap do instalador Live confirmada; ausência de snaps do instalador no Base separada do estado Live.
- [x] Condições de desativação do cloud-init inspecionadas; marcador pós-instalação e tempos reais permanecem relato externo.
- [x] 588 testes existentes aprovados via Xvfb; coletor GTK simulado; zero erros no verificador de projeto.
- [x] Conferência final de 427 entradas preexistentes sem divergência; fontes, alterações do usuário, candidate pack e artefatos protegidos preservados.
- [ ] Comprovar os resultados da política v5, que ainda não foi implementada.

## Diagnóstico adicional na VM, somente quando autorizado

Não executado na VM nesta fase. Preferir capturar antes de correções manuais e no mesmo boot:

```bash
systemd-analyze time
systemd-analyze blame
systemd-analyze critical-chain graphical.target
systemd-analyze critical-chain snapd.seeded.service
systemd-analyze critical-chain cloud-init.target
systemctl --failed --no-pager
systemctl show apache2.service mariadb.service docker.service docker.socket containerd.service ssh.service ssh.socket --property=LoadState,ActiveState,SubState,UnitFileState,FragmentPath,Requires,Wants,After,TriggeredBy,Triggers --no-pager
systemctl list-dependencies --reverse snapd.seeded.service --all --no-pager
systemctl list-dependencies --reverse cloud-init.target --all --no-pager
cloud-init status --long
snap list
stat /etc/cloud/cloud-init.disabled
```

Complementar com journal do mesmo boot, boot ID e logs curtin/Subiquity, sem publicar credenciais/user-data privados. Acesso a journal restrito pode exigir autorização administrativa; não executar aqui no host como substituto dos dados da VM. Verificar se o marcador já existia no começo do boot, não inferir por seu estado atual.

## Gates automatizados da implementação

- [ ] Novo perfil/contrato v5: origem e hash fixos, preimages, limite de disco/memória, escrita só em novas raízes, guard de serviços temporário e restauração sob exceção.
- [ ] Fixture: instalar/configurar pacotes não inicia daemon; nenhum comando pode atingir o systemd do host.
- [ ] Finalização: nenhuma máscara DevLite herdada nas duas visões; alias legítimo preservado; unidades vendor existem; boot links de Apache/MariaDB/Docker/socket/containerd/SSH removidos, sem alterar serviços protegidos.
- [ ] Guard `policy-rc.d` anterior restaurado byte a byte/metadados; backups temporários não publicados.
- [ ] `is-enabled` interpretado pelo texto e tipo, não só exit code; offline verify de unidades e APT/dpkg consistentes.
- [ ] Upgrade de pacote não reativa serviços anteriormente desabilitados; presets/helpers Debian compatíveis.
- [ ] Snap: simulação autenticada de remoção apenas no instalado; dependências virtuais/alternativas examinadas; nenhum pacote protegido removido; Live conserva seed, assertions, snapd e bootstrap.
- [ ] Cloud-init: antes de desativar, prova de conclusão de usuário, rede, hostname e chaves. Manter Live/autoinstall funcional e first boot necessário.
- [ ] SSH: pacote servidor presente; nenhuma chave privada/credencial no payload; PermitRootLogin no efetivo, inclusive com Include/Match; ssh.service/ssh.socket não mascarados e sem ativação no boot não solicitada.
- [ ] Host keys diferentes em duas instalações e estáveis após reboot; nenhum conflito entre geração própria e cloud-init.
- [ ] DevControl: allowlist de ações/unidades, grupos Docker, OpenVPN seguro, PHP-FPM opcional e nenhum PHP CLI como daemon.
- [ ] Testes negativos: injeção, sessão inativa, usuário sem privilégio, cancelamento Polkit, timeout e falha de dependência; GUI permanece responsiva e não roda root.
- [ ] Remascaramento legado eliminado da nova implementação; testes novos de política v5, sem adulterar as expectativas históricas para fabricar aprovação.

## Integração e funcionamento real — ainda pendentes

- [ ] Composição instalada e Live v5 corretas, com whiteouts e metadados; reextração SquashFS e comparação integral; kernels/EFI/instalador preservados, manifests/tamanhos/checksums corretos.
- [ ] VM BIOS e UEFI: boot, instalação, criação de usuário, rede/DNS, XFCE/pt-BR/ABNT2/fuso/Modern/Epiphany e reinício.
- [ ] Após instalação e segundo boot, serviços desabilitados e sem listeners automáticos inesperados; início/parada/reinício manuais e pelo Control com Polkit real.
- [ ] Docker: containerd disponível, socket correto, contêiner de teste autorizado; parada não interrompe workload compartilhado sem confirmação.
- [ ] SSH: ativação posterior com autenticação; root remoto negado; daemon/socket inativos por padrão; firewall e porta 22 conferidos.
- [ ] Impressão, Bluetooth, Wi-Fi/WWAN, VPN, áudio, térmica, horário, AppArmor, UFW, atualizações e Polkit preservados conforme hardware aplicável.
- [ ] Primeiro boot separado dos seguintes; medir 3–5 boots por variante nas mesmas condições. Não somar blame nem prometer ganho por tempo individual.
- [ ] Nova autorização antes de pacote/repositório/download/build privilegiado, teste de instalação ou ISO; nenhuma nesta Fase 1.

## Decisão de prontidão

Pronto para iniciar a Fase 2 de implementação: causas das máscaras confirmadas, responsabilidades separadas, arquitetura e critérios definidos. Não está pronto para construir/homologar a v5. A desativação/remoção de Snap e cloud-init continua condicionada às evidências e aos gates acima; não bloqueia começar os trabalhos de serviços/Control, mas não pode ser apresentada como otimização aprovada.

Artefatos e fontes protegidos devem passar na conferência final de preservação em `evidencias/preservacao-final.json`. Se houver divergência inesperada, interromper e investigar, sem limpar/restaurar automaticamente arquivos do usuário.

## Atualização da implementação integrada — 24/11/2026

O checklist acima registra o estado histórico da Fase 1. Para o estado atual, consultar `progresso.md` e os recibos dos jobs; não interpretar itens históricos como resultados de boot da v5.

- [x] OpenSSH Server e SFTP autenticados e instalados somente nas visões COW Base/Live; dpkg/APT e sshd -t/-T aprovados no job mostqutz.
- [x] Sete máscaras de fábrica removidas por visão, oito unidades desabilitadas; guard de construção restaurado. Nenhuma reinstalação na integração das folhas.
- [x] DevControl 2.0 GTK com backend restrito, Polkit auth_admin, controles de boot separados, Docker/socket/containerd coordenados; 57 testes direcionados (incluindo metadados/branding) aprovados.
- [x] Epiphany renderizou HTML/JavaScript em Base/Live com AppArmor enforce, sandbox WebKit nativo, usuário não privilegiado, sem negações registradas no probe aceito; namespace privado removido.
- [x] Preservação das 427 entradas originais revalidada sem divergências. Snap/cloud-init retidos; nenhuma otimização de boot quantitativa alegada.
- [x] Duas novas folhas SquashFS compostas e comparadas integralmente com a visão alvo.
- [x] Suíte completa final e verificador de projeto aprovados.
- [x] Uma única ISO v5 gerada e auditada (BIOS, EFI anexada, catálogo, manifests, checksums e cinco camadas antigas intactas).

### Homologação externa obrigatória da v5

Usar duas VMs descartáveis independentes no Hyper-V: Geração 1/BIOS e Geração 2/UEFI. Usar discos virtuais novos, nunca discos do servidor de construção. Registrar configuração de Secure Boot e não declarar suporte validado sem testá-lo.

1. Conferir SHA-256 da ISO, iniciar Live, abrir Epiphany e DevControl pelo menu. Conferir pt-BR, ABNT2, XFCE, Modern e título/imagens do instalador. O whitelabel preserva o flavor técnico Xubuntu e as atribuições upstream; conferir as telas efetivas, pois o instalador assinado não foi recompilado.
2. Instalar, remover a mídia virtual e reiniciar duas vezes. Confirmar login, rede/DNS, navegador HTTPS real, idioma, teclado, fuso e programas existentes.
3. Confirmar `systemctl is-enabled apache2 mariadb docker docker.socket containerd ssh ssh.socket`: desabilitados, sem máscaras. Nenhum listener de desenvolvimento/SSH automático inesperado.
4. Pelo DevControl, iniciar/parar/reiniciar cada serviço disponível; separar o teste de habilitar/desabilitar boot. Cancelar uma autenticação Polkit e confirmar ausência de alteração. A janela deve continuar responsiva. Não oferecer PHP CLI como daemon nem OpenVPN sem configuração de cliente confiável.
5. Parar Docker e comprovar daemon/socket inativos, preservando containerd compartilhado. Testar contêiner apenas com autorização de rede/download apropriada.
6. Iniciar SSH manualmente, conferir `PermitRootLogin no` efetivo e firewall. Comparar fingerprints de host entre as duas instalações (diferentes) e após reboot da mesma instalação (iguais). Não publicar chaves privadas nem senhas nos relatórios.
7. Conferir AppArmor, UFW, horário, VPN, Bluetooth, impressão, áudio e hardware aplicável. Registrar boot/RAM sem prometer melhoria a partir de valores antigos.

O probe gráfico não substitui boot, instalação, Polkit real ou conectividade externa no Hyper-V. A v5 não está homologada para produção antes desses testes.

Whitelabel conforme a [documentação oficial da branch Ubuntu 24.04](https://github.com/canonical/ubuntu-desktop-provision/blob/ubuntu/24.04/README.md). Não foram removidos licenças, atribuições ou suporte técnico da distribuição base.
