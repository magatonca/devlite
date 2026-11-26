# Correções e decisões

- O overlay v6 contém a configuração global `ServerName localhost` com o vínculo usual do Apache. O empacotamento e o teste HTTP/PHP no guest estão pendentes.
- O primeiro slide pt-BR usa o logo do slide herdado, idioma declarado, largura de leitura limitada e espaçamento adaptável. A v5 lista `ubuntu-desktop-bootstrap` no manifesto. Falta rastrear no guest os recursos efetivamente renderizados pelo snap e validar todas as telas, inclusive o slide da comunidade. Preservar a assinatura do snap e os créditos.
- A inclusão de cURL segue pendente. Resolver a versão candidata e as dependências contra índices oficiais assinados usando as composições base e Live. Verificar o resultado nos manifestos de ambas.
- Node.js 26 está em LTS. Priorizar a linha já homologada e verificar a versão corrigida e a compatibilidade com NPM e TypeScript antes de selar o pack. [Calendário oficial](https://nodejs.org/en/about/previous-releases)
- O VS Code pode usar instalação sob demanda pelas instruções oficiais para Debian/Ubuntu enquanto a redistribuição do produto não estiver autorizada. A integração no DevControl está pendente. [Instalação oficial](https://code.visualstudio.com/docs/setup/linux) · [Licença do produto](https://code.visualstudio.com/docs/supporting/faq)
- Diagnóstico de serviços no guest deve comparar o estado após instalação, após o primeiro boot e após atualizações. Usar diário, dependências, presets, scripts de manutenção e estado efetivo. Preservar escolhas manuais e atualizações. Medir o caminho crítico de boot antes de alterar Snapd, AppArmor ou cloud-init.

## Retomada

- Quatro slides pt-BR disponíveis no caminho de customização do instalador, com créditos ao Xubuntu e Ubuntu. `app-name` muda o título da janela e o nome da distribuição em textos internos deriva de `flavor`. Corrigir os textos do assistente exige solução no instalador de origem e validação dos recursos compilados. O snap assinado herdado foi preservado. [Configuração do Ubuntu Desktop Provision](https://github.com/canonical/ubuntu-desktop-provision#configuration)
- cURL e duas bibliotecas Ubuntu Noble Security 8.5.0-2ubuntu10.16 foram baixados com verificação de assinatura e hashes. O teste APT em modo simulado sobre Base e Live previu uma instalação e duas atualizações. O link do VS Code abre instruções oficiais sob demanda. Nenhum binário Microsoft foi incluído.
- Arquivos herdados conferidos por inspeção das camadas. MariaDB escuta em `127.0.0.1` e SSH mantém `PermitRootLogin no` e `PermitEmptyPasswords no`. Os estados reais após instalação e a integração Apache/PHP precisam do guest.

## Identidade visual no instalador v6

A revisão 572 do snap presente no Live contém Ubuntu Desktop Bootstrap 24.04.4.1. O overlay v6 configura o título da janela, paleta Modern em tema claro e escuro, botões primários e o logotipo DevLite herdado. O catálogo da ISO passa a apresentar nome e descrição em pt-BR, conservando o ID, o formato e o fluxo de seleção. O overlay do assistente entra na composição Live. O logotipo é o mesmo da identidade já presente no sistema instalado.

| Tela | Ajuste aplicado | Conferir no Hyper-V |
|---|---|---|
| Idioma e boas-vindas | Título da janela e imagem DevLite | Texto interno do cabeçalho, pt-BR e ação de experimentar o Live |
| Teclado e rede | Imagem DevLite e paleta comum | ABNT2, rede conectada e offline, estados padrão e foco |
| Atualização e seleção de fonte | Branding e descrição pt-BR da fonte | Seleção, quebra de linha, contraste e caminho de atualização |
| Particionamento e confirmação | Logo em disco, ícone da distribuição e confirmação | Layout guiado e manual, avisos, textos que interpolam o nome da distribuição |
| Criação do usuário | Imagem DevLite e botões comuns | Rótulos pt-BR, erros de validação e foco |
| Progresso | Quatro slides revistos em pt-BR e fallback en-US, com layout de uma coluna | Corte, espaçamento, contraste e créditos |
| Conclusão | Imagem DevLite e paleta comum | Texto interno, reinício e consistência com a sessão instalada |

A configuração externa não expõe os textos internos compilados nem a tipografia e o layout global do assistente. A revisão 572 contém em `libapp.so` textos de boas-vindas, escolha do tipo de instalação e opções de disco que recebem o nome do flavor. O título da janela e a descrição da fonte são independentes desses textos. Para mudar esse conteúdo mantendo o fluxo do instalador, falta portar as alterações ao código-fonte correspondente, gerar um frontend suportado e validar a integração com o Subiquity. Flutter e Dart não estão instalados no servidor. O snap e suas assertions foram preservados. [Configuração do Ubuntu Desktop Provision](https://github.com/canonical/ubuntu-desktop-provision#configuration) · [Seleção de fontes no Subiquity](https://github.com/canonical/subiquity/blob/main/subiquity/server/controllers/source.py)

A visualização já preparada foi autorizada para a v6 candidata. A manutenção dos textos internos que interpolam Xubuntu e o refinamento da tipografia e do layout do Flutter ficam como melhorias da v7. O snap oficial assinado permanece como componente da v6.
