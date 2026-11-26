# Navegador gráfico — correção preparada, aplicação pendente

O usuário relatou testes positivos da candidata atual no Hyper-V em BIOS Legacy e UEFI, incluindo instalação, programas, XFCE, idioma/teclado e persistência, mas ausência de navegador gráfico funcional. O relato está preservado em `docs/evidencias/relato-hyperv-navegador.json`; não foi transformado em uma execução automática de todos os critérios antigos.

## Escolha técnica

**GNOME Web/Epiphany 46.5-0ubuntu1**, pacote `epiphany-browser` do Ubuntu noble-updates/universe AMD64, acompanhado de `epiphany-browser-data`. É um navegador GTK/WebKitGTK nativo: não é metapacote de transição para Snap e não necessita de instalador na primeira execução. Os componentes são instalados pelo dpkg no alvo antes do empacotamento. Dependências transitivas foram resolvidas nas duas visões reais; ca-certificates e dbus-user-session já estão presentes.

A escolha evita repositório externo e usa GTK4 já existente no sistema. O incremento medido pelo APT é de cerca de **136,59 MiB por visão**; isso não é medição de RAM nem benchmark de desempenho. Não afirmar que este seja o navegador mais leve. Falkon está disponível como .deb, mas usa QtWebEngine/KDE; Firefox e Chromium do arquivo Ubuntu Noble são pacotes de transição para Snap. Firefox do repositório Mozilla seria outra opção nativa, exigindo nova origem, chave e revisão; não é necessário para esta correção.

Referências oficiais: [Epiphany no Ubuntu](https://packages.ubuntu.com/noble/epiphany-browser), [arquivos do pacote em noble-updates](https://packages.ubuntu.com/noble-updates/amd64/epiphany-browser/filelist), [GNOME Web](https://apps.gnome.org/Epiphany/), [Firefox](https://packages.ubuntu.com/noble/firefox), [Chromium](https://packages.ubuntu.com/noble/chromium-browser), [Falkon](https://packages.ubuntu.com/noble/falkon). Versões e hashes precisos desta seleção vêm dos índices locais autenticados, não da página de resumo Noble.

## Dependências e disponibilidade verificadas

Plano final: `work/browser-1kyn499g/browser-plan.json`. GPG dos InRelease, identidade Ubuntu/Noble e SHA-256 dos índices Packages conferidos pelo mecanismo existente. Releases de updates/security datados de 18/11/2026. Nenhum refresh ou download de índice foi executado. **10 pacotes novos na Base e 10 na Live, idênticos; zero upgrades, remoções ou conflitos.** Todas as versões prévias são fixadas com prioridade 1001 durante a simulação e comparadas depois. Boot, instalador e programas existentes permanecem fora da transação.

Download deduplicado planejado: **36.661.522 bytes, aproximadamente 34,96 MiB**. Tamanho bruto instalado: **143.224.832 bytes, aproximadamente 136,59 MiB por visão**.

| Pacote | Versão fixada | Bytes .deb |
| --- | --- | --- |
| epiphany-browser | 46.5-0ubuntu1 | 774314 |
| epiphany-browser-data | 46.5-0ubuntu1 | 1600952 |
| libadwaita-1-0 | 1.5.0-1ubuntu2 | 408094 |
| libgee-0.8-2 | 0.20.6-1build2 | 221192 |
| libgranite-7-7 | 7.4.0-1build3 | 96618 |
| libgranite-7-common | 7.4.0-1build3 | 32504 |
| libjavascriptcoregtk-6.0-1 | 2.52.6-0ubuntu0.24.04.2 | 8157658 |
| libportal-gtk4-1 | 0.7.1-5build5 | 11484 |
| libportal1 | 0.7.1-5build5 | 44704 |
| libwebkitgtk-6.0-4 | 2.52.6-0ubuntu0.24.04.2 | 25314002 |

Os dez URLs HTTPS de `archive.ubuntu.com` responderam HTTP 200 e Content-Length idêntico ao índice assinado. Foram feitas apenas requisições HEAD, sem ler corpos: `docs/evidencias/navegador-disponibilidade.json`. Isso prova disponibilidade naquele instante; não substitui o futuro hash integral de cada arquivo. Nenhum .deb novo foi baixado, extraído ou instalado. Antes de adquirir/aplicar, revalidar a autenticidade e atualidade dos índices; não substituir versões automaticamente se um artefato desaparecer.

## Arquitetura e configurações preparadas

Arquivos novos de implementação: `packages/browser.json`, `pipeline/devlite/browser.py`, `scripts/preparar-navegador.py`, `tests/test_browser.py`, `tests/fixtures/browser-smoke.html`. Não foram alterados os módulos selados, o catálogo histórico `packages/selection.json`, os pacotes do host nem os overlays visuais. O catálogo complementar compõe uma cópia da seleção com os itens Ubuntu necessários, validando categorias e escopo instalado+Live; o histórico permanece intacto.

O planejador verifica os recibos root-owned e hashes das camadas atualmente aprovadas. Lê o dpkg da Base e da Live efetiva e o compara aos manifests publicados. O delta não é tratado como sistema independente: ausência de status na folha só pode herdar a Base se o manifest completo confirmar o mesmo estado.

Prévia das configurações: `work/browser-1kyn499g/settings-preview/{base,live}`. Modificações futuras restritas a `WebBrowser=epiphany` nos helpers e aos quatro tipos HTML/HTTP/HTTPS nos padrões MIME. Outros aplicativos, associações PDF, preferências e comentários são preservados. Caminhos preparados:

- `/etc/xdg/xfce4/helpers.rc` e `/etc/xdg/xdg-xubuntu/xfce4/helpers.rc`;
- `/etc/skel/.config/xfce4/helpers.rc`;
- `/etc/xdg/xfce-mimeapps.list` e `/etc/xdg/xdg-xubuntu/xfce-mimeapps.list`;
- `/etc/skel/.config/mimeapps.list`.

Usa o helper `epiphany` já existente no XFCE, sem criar um launcher duplicado. O menu deve usar o desktop entry nativo `org.gnome.Epiphany.desktop`, fornecido pelo .deb, com categorias Network/WebBrowser. A categoria Network também é incluída pelo menu DevLite já existente. O gate estático preparado rejeita entradas invisíveis, excluídas do XFCE, sem MIME esperado ou que executem downloaders em vez do navegador.

A precedência MIME segue a [especificação freedesktop](https://specifications.freedesktop.org/mime-apps/latest/file.html); a abertura pelo XFCE segue o [helper/exo-open](https://docs.xfce.org/xfce/exo/preferred-applications). Perfis de usuário existentes continuam prevalecendo sobre os padrões; não serão sobrescritos silenciosamente. A conta Live e a conta instalada precisam ser verificadas separadamente.

## Aplicação futura e preservação das camadas

**O navegador ainda não está na ISO ou nos SquashFS publicados.** Esta etapa preparou seleção, resolução, configuração e validação; não executou instalação. A inclusão real exige autorização privilegiada e contrato novo, vinculado às cópias da Base/Live atuais que já contêm Node.js/TypeScript e o overlay homologado.

Reutilizar isolamento validado, offline após aquisição verificada dos dez debs, com dpkg/APT exclusivamente no alvo, serviços bloqueados e host somente leitura. Instalar sequencialmente nas visões completas Base/Live, com as mesmas versões. Mesclar as configurações autorizadas e conferir hashes de pré-imagem no contexto efetivamente montado: a prévia não deve ser copiada cegamente, pois o executor precisa respeitar whiteouts, opacidade, symlinks e as preferências reais. **Não reutilizar diretamente o aplicador aditivo do payload público**, que rejeita colisões e não executa dpkg; adaptar a instalação aos novos inputs e allowlist antes de selar o contrato.

Após instalação, conferir `dpkg --audit`, APT check, versions, ELF/dependências compartilhadas, schemas GSettings, dados/ícones/localização, helper, menu e associações. Não executar ELF do alvo no host para verificar bibliotecas. Preservar sandbox WebKit, AppArmor e políticas de namespaces; falha de sandbox bloqueia a liberação. Reconciliar o delta Live a partir das duas visões completas novas, atualizar manifests/tamanhos/install-sources e repetir round-trip e composição pelo kernel. Só então a presença física nas camadas poderá ser declarada aprovada.

O orçamento conservador calculado do planejamento está no relatório. Há aproximadamente **38,16 GiB livres**, abaixo da reserva de **56 GiB** do instalador existente. Faltam cerca de **17,84 GiB** para esse mínimo, sem contar eventual nova exigência da aplicação visual. Não reduzir o gate; resolver por expansão ou limpeza proposta e autorizada. Nenhum arquivo foi removido.

## Testes realizados e limites

A suíte completa passou: **372 testes**, incluindo **25 novos** de navegador, em `reports/testes-navegador-suite-completa.txt`. Cobrem preservação de versões/associações, pin de todos os pacotes existentes, dpkg do host desabilitado no APT_CONFIG de simulação, status Base/Live, menu/desktop, idempotência e rejeição de configurações incompletas. O gate estático mantém `graphical_launch=not_tested` mesmo quando passa. Nenhuma regressão automatizada encontrada. Arquivos críticos do host e hash de config/projeto.json permaneceram intactos.

Não há evidência de lançamento gráfico do navegador, pois ele não foi instalado. Nem presença no dpkg nem `--version` substituem essa prova. Preparar o registro manual abaixo tanto no Live quanto no sistema instalado, em sessão XFCE de usuário comum e nos dois firmwares já homologados pelo usuário.

| Verificação real | Critério de aprovação |
| --- | --- |
| Menu e lançamento | abrir GNOME Web pelo menu; janela aparece, sem erro de dependência, schema ou sandbox |
| Helper e padrões | `exo-open --launch WebBrowser`, xdg-open HTTP/HTTPS e abertura de HTML iniciam Epiphany; `xdg-mime query default text/html` e os dois handlers retornam org.gnome.Epiphany.desktop |
| Página offline | abrir `tests/fixtures/browser-smoke.html`; acentos corretos, “JavaScript OK”; clicar botão e observar “Interação OK”, sem rede |
| HTTP local | no guest, servir a pasta fixtures com `python3 -m http.server 8765 --bind 127.0.0.1`; abrir http://127.0.0.1:8765/browser-smoke.html por xdg-open, testar DOM e parar o servidor ao final |
| HTTPS | abrir página HTTPS de teste, validar certificado, navegação e download simples, sem instalar componentes na primeira execução |
| Reinício e instalação | repetir como usuário instalado depois de ejetar ISO e reiniciar; padrões persistem; perfis novos não dependem de caches da conta Live |
| Regressão | repetir verificações essenciais de Apache/PHP/MariaDB, Docker/Compose/Git/Node/TypeScript, redes, Control, pt-BR/ABNT2 e instalador |

Guardar screenshots, logs do navegador e resultados por firmware/contexto. Não iniciar navegador como root, não desativar sandbox e não testar a aplicação gráfica no Ubuntu Server hospedeiro. Esta documentação não autoriza criar VMs, montagens ou instalações.

## Próxima etapa visual

O [mapa de personalização visual](mapa-personalizacao-visual.md) identifica wallpaper, GTK/XFCE, ícones, cursores, painel/menu, LightDM, identidade, boot e Control, incluindo suas fontes e precedências. **Diretriz atual: DevLite Modern (Opção C), exclusivamente escura. Concluir primeiro o navegador; depois apresentar o plano visual para aprovação.** Não está liberada aplicação visual nas imagens nem geração final. Ver `docs/diretriz-devlite-modern.md`. Combinar o navegador e o visual aprovado em um novo contrato e manter **uma única geração final candidata**, sem produzir ISO intermediária nesta etapa. Não prometer que testes futuros nunca exigirão correções.
