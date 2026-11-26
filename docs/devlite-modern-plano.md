# DevLite Modern — plano e protótipos isolados

Esta preparação foi autorizada na execução noturna. Não aplica o visual ao Live, ao sistema instalado ou ao hospedeiro. A instalação do navegador está bloqueada porque o executor requer privilégios explicitamente proibidos nesta execução; prosseguiu-se somente com atividades independentes e seguras. Não é homologação visual nem autorização de ISO.

## Composição única

Greybird-dark GTK e XFWM, elementary-xfce-dark e cursor DMZ-White já confirmados por leitura da Base publicada. Grafite #171c24 e azul #348bd6 no wallpaper SVG estático. Nenhum pacote, dock adicional ou serviço residente proposto. Sem alternância de tema, compositor, animação GTK ou transições do greeter. O estilo GTK4/libadwaita do navegador usa uma proposta de prefer-dark via dconf; não usar GTK_THEME, hacks de CSS ou desativação de sandbox.

Painel XFCE nativo único inferior, posição p=10 (bottom center), altura 40, extensão 90%, opaco, sem ocultação automática. É uma configuração proposta: verificar posição, escala e ajuste em sessão real antes de adotá-la. Preservados os IDs e configurações dos dez plugins originais: Whisker, separadores, tarefas, bandeja, notificações, indicadores, energia, áudio e relógio. A largura pode exigir ajuste em telas antigas de 1024x768; não remover controles para caber. O menu DevLite existente será preservado, incluindo navegador nativo quando instalado. Nenhuma alteração nos atalhos, backend ou permissões do DevLite Control.

## Arquivos de prévia

`work/modern-preview-psowhkmp/preview-only/` contém painel, xsettings, xfwm4, LightDM, proposta dconf e wallpaper. `sources/` guarda os conteúdos originais lidos; `preview.json` registra hashes de origem e saída. Não copiar esse diretório diretamente para o host ou para o delta Live. O gerador `scripts/preparar-devlite-modern.py` cria uma nova prévia, sem opção de aplicação.

As fontes desta prévia são da Base, não uma alegação de configuração efetiva de todas as contas Live. O adaptador futuro precisa examinar a visão Live completa, whiteouts, opacidade, symlinks e preferências do usuário. Não tratar os dois SquashFS como sistemas independentes.

## Integração futura após aprovação

1. Concluir a instalação offline isolada do navegador em cópias das visões completas atuais, com versões fixadas; preservar Base/Live aceitas. Revalidar as assinaturas, hashes e dez debs antes da operação. Não instalar no host.
2. Revisar e aprovar esta proposta. Renderizar alterações mínimas sobre cada visão completa; alinhar `/etc/xdg/xfce4`, `/etc/xdg/xdg-xubuntu`, `/etc/skel` e conta Live quando necessário, preservando preferências explícitas de usuários existentes.
3. O script atual `devlite-first-session` fixa Greybird. Criar uma nova versão em payload novo e marcador versionado, respeitando keep-user-settings, sem alterar o payload histórico ou criar processo residente. Aplicar wallpaper após descoberta real dos monitores; não fixar nomes de saída.
4. Para GTK4, verificar schema e perfil dconf efetivos; mesclar system-db:devlite sem remover bases existentes e compilar somente no alvo autorizado. O arquivo de prévia sozinho não ativa o padrão. Para LightDM, mesclar aparência sem modificar autenticação, sessão, teclado ou acessibilidade.
5. Manter logo atual nesta proposta. A variante de logo e a tela inicial do Control ainda precisam de aprovação editorial; Control permanece em terminal, com backend administrativo intacto. Não alterar Plymouth, GRUB, EFI, kernel ou instalador nesta preparação.
6. Auditar dpkg/APT, arquivos, permissões e serviços; reconstruir delta a partir das visões completas e testar composição/round-trip. Somente depois solicitar a geração única da ISO final candidata.

## Desempenho e aceitação

Sem processos residentes novos e sem compositor proposto. Arquivos pequenos e wallpaper sem imagens externas, scripts, filtros ou animações. Isso não constitui benchmark: RAM, CPU, tempo de login e responsividade ainda não foram medidos em guest. O alvo de 6 GiB deve ser verificado em hardware antigo/VM com aceleração limitada e resolução 1024x768, além de 1366x768 e HiDPI. Comparar memória ociosa e CPU com a ISO homologada nas mesmas condições; investigar regressão sustentada antes de liberar.

A reserva operacional noturna é 20 GiB, além do gate inicial existente de 56 GiB para instalação. Não reduzir nenhum limite. Estimativa conservadora do navegador: 35,60 GiB adicionais, sujeita a scripts de manutenção. Aprovação e monitoramento contínuo continuam necessários antes de criar cópias de imagens.

## Checklist da futura candidata

- [ ] Navegador aplicado Base/Live; banco dpkg/APT íntegro, sem alterações nos pacotes homologados.
- [ ] Desktop org.gnome.Epiphany, helper XFCE e MIME HTTP/HTTPS/HTML conferidos nos dois contextos.
- [ ] Lançamento gráfico como usuário comum, sandbox ativa, teste HTML/JavaScript offline e HTTPS real; repetir após instalação/reinício.
- [ ] Tema escuro GTK3/GTK4, decorações, greeter e wallpaper em todos os monitores, sem flashes claros persistentes.
- [ ] Painel inferior com todos os indicadores, menu e atalhos preservados; contraste, acessibilidade e navegação por teclado.
- [ ] DevLite Control e serviços de desenvolvimento, Node/TypeScript, ferramentas de rede, pt-BR/ABNT2 e persistência sem regressões.
- [ ] Base/Live reconciliadas; manifests, tamanho e integridade SquashFS conferidos.
- [ ] Após autorização da ISO: BIOS/UEFI, instalador, instalação e reinício reais; guardar evidências por firmware/contexto.

Nenhum desses testes práticos foi aprovado nesta execução.
