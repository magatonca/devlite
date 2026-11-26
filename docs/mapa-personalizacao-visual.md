# Mapa da próxima personalização visual

Somente inventário. Diretriz definitiva: [DevLite Modern, Opção C](diretriz-devlite-modern.md), única aparência escura. Concluir o navegador antes de elaborar e apresentar o plano visual. Nenhuma alteração visual foi aplicada nesta etapa. A existência dos caminhos do alvo foi conferida por `unsquashfs -l`, sem mounts: `docs/evidencias/mapa-visual-inventario.json`.

## Pontos de configuração

| Área | Fonte no projeto / configuração atual | Caminho ou propriedade no sistema convidado |
| --- | --- | --- |
| Papel de parede DevLite | `overlay/final-candidate/usr/share/backgrounds/devlite/devlite-wallpaper.svg` | `/usr/share/backgrounds/devlite/devlite-wallpaper.svg` |
| Aplicação do wallpaper por monitor | `overlay/final-candidate/usr/libexec/devlite-first-session` | canal xfconf `xfce4-desktop`, propriedades `/backdrop/.../last-image`; precisa dos monitores da sessão real |
| Wallpaper Xubuntu herdado | pacote xubuntu-default-settings | `/etc/xdg/xdg-xubuntu/xfce4/xfconf/xfce-perchannel-xml/xfce4-desktop.xml` |
| Tema GTK do XFCE | `config/customization.json`, `pipeline/devlite/customize/settings.py` e `devlite-first-session` | canal `xsettings`, `/Net/ThemeName`; `/etc/xdg/xfce4/xfconf/xfce-perchannel-xml/xsettings.xml`, variantes em `xdg-xubuntu`, e cópia em `/etc/skel/.config/...` |
| Arquivos do tema | pacote greybird-gtk-theme | `/usr/share/themes/Greybird` |
| Decoração de janelas/compositor | padrões Xubuntu e `devlite-first-session` | canal `xfwm4`, `/general/theme`, `/general/use_compositing`; `/etc/xdg/xdg-xubuntu/xfce4/xfconf/xfce-perchannel-xml/xfwm4.xml` |
| Ícones | `config/customization.json`, renderizador e primeiro login | `/usr/share/icons/elementary-xfce-dark`; canal `xsettings`, `/Net/IconThemeName` |
| Cursores | tema instalado DMZ-White; ainda sem override DevLite dedicado | `/usr/share/icons/DMZ-White`; canal `xsettings`, `/Gtk/CursorThemeName` e `/Gtk/CursorThemeSize`; LightDM possui configuração própria |
| Painel, lançadores e Whisker | padrões do pacote; nenhum layout DevLite novo nesta etapa | `/etc/xdg/xdg-xubuntu/xfce4/panel/default.xml`, fallback `/etc/xdg/xfce4/panel/default.xml`; depois `~/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-panel.xml` e `~/.config/xfce4/panel/` |
| Menu DevLite | `overlay/final-candidate/etc/xdg/menus/xfce-applications-merged/devlite.menu` | mesmo caminho sob `/etc`; diretórios em `/usr/share/desktop-directories/devlite*.directory`; aplicações em `/usr/share/applications/` |
| Navegador no menu | pacote epiphany-browser, sem launcher duplicado | `/usr/share/applications/org.gnome.Epiphany.desktop`; categorias Network e WebBrowser entram no menu existente |
| Tela de login | pacote lightdm-gtk-greeter; não há override visual DevLite novo | `/etc/lightdm/lightdm-gtk-greeter.conf`; defaults do display manager `/usr/share/lightdm/lightdm.conf.d/60-xubuntu.conf`; conferir theme-name, icon-theme-name, background, font-name no greeter |
| Logo/ícone DevLite | `overlay/final-candidate/usr/share/icons/hicolor/scalable/apps/devlite.svg` | `/usr/share/icons/hicolor/scalable/apps/devlite.svg`; desktop launchers usam `Icon=devlite` |
| Nome/identidade | `config/customization.json`; `pipeline/devlite/customize/settings.py` | `/etc/devlite-release`, `/usr/share/devlite-os/identity.json`; preservar identificação técnica Ubuntu e compatibilidade do instalador |
| Splash de boot | pacote plymouth-theme-xubuntu-logo; ainda não personalizado | `/usr/share/plymouth/themes/xubuntu-logo/`, `logo.png`, `xubuntu-logo.plymouth`, `xubuntu-logo.script`; seleção `default.plymouth`/alternatives precisa ser examinada no alvo autorizado |
| Menu de boot da ISO | renderizador `pipeline/devlite/minimal_build.py`; originais somente leitura em `work/phase4b1-dhzezpnz/original-grub` | `/boot/grub/grub.cfg` e `loopback.cfg`; não alterar EFI, kernel ou replay híbrido nesta preparação |
| Tela inicial DevLite Control | `overlay/final-candidate/usr/bin/devlite-control`, função `interactive()` | aplicação atual em terminal: títulos, mensagens e ordem dos serviços são strings Python; ainda não há tema GTK ou CSS próprio de uma janela gráfica |
| Lançador e ícone do Control | `overlay/final-candidate/usr/share/applications/devlite-control.desktop` | desktop entry, `Exec`/`Terminal`/`Icon`; não mudar as permissões administrativas |
| Backend administrativo do Control | `overlay/final-candidate/usr/libexec/devlite-service-control` e `usr/share/polkit-1/actions/org.devlite.services.policy` | lógica de serviços e autenticação, fora do escopo visual; preservar integralmente |

## Precedência e arquivos vinculados

As preferências já gravadas em `~/.config` prevalecem sobre os padrões de `/etc/xdg`. A sessão Xubuntu usa também `/etc/xdg/xdg-xubuntu`. `/etc/skel` só é copiado na criação do usuário; não migra contas existentes. O script de primeira sessão exige identidade DevLite, XFCE/D-Bus e o marcador `~/.config/devlite/apply-initial-defaults`; respeita `keep-user-settings` e usa `initial-defaults-v1.json` para execução única.

Para trocar Greybird/ícones no futuro, alinhar a declaração em `config/customization.json`, a validação/renderização em `settings.py`, os valores fixos do script `devlite-first-session` e os testes. Alterar apenas o SVG ou um XML não garante aplicação no Live e em contas novas. GTK4/libadwaita do navegador tem comportamento de estilo próprio: validar a aparência escura única e sua legibilidade, sem criar alternância de temas, forçar hacks de tema ou remover sandbox.

`config/final-branding-plan.json` contém hashes do overlay atual; contratos históricos também selam código e inputs. Preservar esses arquivos como evidência. A próxima identidade deve usar inputs e contrato novos, com aprovação antes de aplicar, em vez de modificar silenciosamente um payload já aprovado.

## Ordem vigente

A [diretriz definitiva](diretriz-devlite-modern.md) substitui a sequência de preparação anterior:

1. Concluir o navegador, incluindo aplicação isolada e teste gráfico real, preservando o instalador e os programas homologados. Resolver o bloqueio de espaço sem reduzir limites.
2. Depois apresentar o plano DevLite Modern: apenas uma aparência escura, painel nativo inferior e nenhum dock ou serviço visual adicional.
3. Aguardar aprovação do plano antes de criar/aplicar alterações visuais nas visões completas Base/Live.
4. Reconciliar o delta e executar round-trip/composição, com testes de sessão Live e instalada.
5. Gerar a única ISO final candidata somente após autorização específica, preservando BIOS/UEFI e EFI; não declarar homologação sem testes reais.

Este mapa não inicia a personalização visual. O plano de implementação permanece em espera pela conclusão do navegador.
