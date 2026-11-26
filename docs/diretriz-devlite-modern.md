# Diretriz definitiva — DevLite Modern (Opção C)

Decisão expressa do usuário: identidade única DevLite Modern, escura, moderna, minimalista e profissional. Não implementar múltiplas opções visuais nem seletor claro/escuro.

## Requisitos para o futuro plano

- Manter XFCE; usar preferencialmente o painel nativo como dock inferior.
- Azul tecnológico, grafite e elementos discretos; conjunto consistente de ícones leves.
- Personalizar wallpaper, menu, painel e tela de login, preservando atalhos e funcionalidades.
- Não instalar Plank, Cairo-Dock ou outros docks adicionais.
- Evitar animações, transparências, sombras pesadas e efeitos desnecessários.
- Não adicionar serviços residentes para efeitos visuais.
- Compatibilidade pretendida com hardware antigo e 6 GB de RAM no sistema de destino. Isso não altera os limites da VM de construção nem comprova desempenho sem testes.
- A aplicação futura deve funcionar na sessão Live e no sistema instalado; respeitar a reconciliação Base/Live e não presumir dois SquashFS independentes.

## Sequência obrigatória

1. Concluir a correção do navegador: resolver armazenamento, adquirir e verificar os pacotes após o procedimento autorizado, preparar/aprovar a execução isolada, aplicar em cópias das visões completas, auditar e validar o lançamento gráfico real.
2. Somente depois analisar a implementação visual existente à luz desta diretriz e apresentar o plano DevLite Modern para aprovação. O mapa de caminhos existente é apenas inventário; não constitui autorização nem plano aprovado.
3. Aplicar mudanças visuais somente após aprovação expressa desse plano. Preservar programas homologados, instalador, idioma, teclado, BIOS/UEFI e persistência.
4. Gerar uma única ISO final candidata somente após as aprovações necessárias; não gerar ISO intermediária nesta preparação. Homologar apenas o que for efetivamente testado.

## Situação ao registrar a diretriz

Navegador escolhido: GNOME Web/Epiphany, .deb Ubuntu. Planejamento de 10 pacotes novos e configurações Base/Live preparado; instalação e lançamento gráfico ainda não executados. Última suíte: 372 testes aprovados, incluindo 25 do navegador. Nenhuma mudança de código nesta atualização documental exige repetir essa suíte.

Espaço observado: aproximadamente 38,16 GiB livres; mínimo existente de instalação 56 GiB, com déficit de cerca de 17,84 GiB. O mínimo não será reduzido. Não foram autorizadas novas exclusões nem operações privilegiadas nesta diretriz; não foram executadas.

Nenhum asset, tema, painel ou configuração visual foi alterado. Não foi gerada ISO. O plano de implementação visual permanece pendente até concluir o navegador.
