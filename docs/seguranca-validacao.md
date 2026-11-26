# Segurança, testes e validação

## Políticas

- Não executar `curl | sh`; usar fontes oficiais e repositórios com assinatura e chave limitada por signed-by, após revisão. Fixar a versão LTS de Node e revisar suporte na fase de implementação.
- Apache, MariaDB, SSH server, Docker e OpenVPN não devem iniciar serviços de rede automaticamente no live. No instalado, ativação explícita via administrador; validar estado efetivo. OpenSSH client é padrão planejado; servidor opcional.
- MariaDB não deve escutar externamente por padrão. Nenhuma senha padrão, chave privada ou conta do construtor na ISO.
- Sem inclusão automática nos grupos docker ou wireshark; docker concede privilégios equivalentes a root. Captura Wireshark requer decisão explícita sobre grupo/capabilities; interface nunca executada inteira como root.
- DevLite Control terá interface sem privilégios e backend mínimo autorizado por polkit, com lista fixa de serviços e operações. Proibir shell arbitrário, argumentos livres e senhas armazenadas. Solicitar autenticação para mudanças e registrar falhas sem segredos.
- Preservar atualizações de segurança e confiança APT; inventariar licenças e marcas. Revisar redistribuição de VS Code, extensões e fontes externas antes de entrega.

## Portas de qualidade

Fase 1: estrutura consistente, JSON válido, diagnósticos sem efeitos externos e revisão Git sem artefatos grandes ou segredos. Fases seguintes: assinatura e hash da base válidos, zero instalação de fonte desconhecida, ausência de credenciais e identidade do host, nenhum serviço exposto inesperado.

A matriz detalhada está em [tests/aceitacao.md](../tests/aceitacao.md). Falhas bloqueantes: boot ou instalação falha, perda de localização após instalar, elevação arbitrária de privilégio, pacote essencial quebrado, segredo embarcado ou porta inesperada. Publicação exige registro de evidências e aprovação de todas as linhas obrigatórias. Segurança não equivale a garantia de ausência de vulnerabilidades.

`config/projeto.json` é registro de estado, não autorização operacional. O
validador exige `build_habilitado: false` em todas as fases; texto histórico em
`autorizacao_build` não libera build. Cada preparação ou execução exige sua
aprovação específica e os contratos próprios do pipeline.
