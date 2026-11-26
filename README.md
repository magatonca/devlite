# DevLite OS 1.0 — Developer + Network Edition

Distribuição experimental sobre Xubuntu 24.04 LTS Minimal AMD64, com XFCE em português brasileiro. Duas ISOs históricas idênticas bit a bit; preparação consolidada com **259 testes aprovados**. Boot e instalação reais permanecem pendentes. Node.js LTS/TypeScript e identidade visual estão preparados, ainda não aplicados; VS Code será opcional na distribuição pública.

## Navegação

- [Conclusão acelerada e próxima autorização](docs/conclusao-acelerada.md)

- [Finalização consolidada, resultados e pendências](docs/finalizacao-devlite-1.0.md)
- [Instalação e validação no laboratório](docs/instalacao-devlite-1.0.md)
- [Proposta de limpeza: caminhos, tamanhos e riscos](docs/limpeza-final-proposta.md)

- [ISOs geradas, SHA-256 e validações](docs/fase4b8-isos-geradas.md)
- [Roteiro prático BIOS/UEFI e instalação](docs/fase4b9-validacao-pratica.md)

- [Integração aprovada e evidências](docs/fase4b8-integracao-aprovada.md)
- [Proposta de geração da ISO e reprodução](docs/fase4b8-geracao-iso-proposta.md)

- [Relatório consolidado 4B.7–4B.9](docs/fases4b7-9-integradas.md)

- [Preparação dos pacotes — Fase 4B.5](docs/fase4b5-preparacao-pacotes.md)

- [Validação do isolamento — Fase 4B.4](docs/fase4b4-validacao-isolamento.md)

- [Executor isolado — Fase 4B.3](docs/fase4b3-executor-isolado.md)

- [Preparação dos programas — Fase 4B.2](docs/fase4b2-preparacao-programas.md)

- [Primeira personalização mínima — Fase 4B.1](docs/fase4b1-personalizacao-minima.md)

- [Personalização da Fase 4A](docs/fase4a-personalizacao.md)
- [Lista de pacotes e origens](docs/pacotes-origens.md)

- [Pipeline experimental da Fase 3B](docs/fase3b-pipeline.md)

- [Laboratório e testes BIOS/UEFI da Fase 3A](docs/fase3a-testes-iso.md)

- [Resultados da Fase 2](docs/fase2-aquisicao-validacao.md)
- [Estratégia para as camadas SquashFS](docs/estrategia-camadas.md)
- [Reproduzir validações](tests/README.md)

- [Arquitetura do pipeline](docs/arquitetura.md)
- [Plano por fases](docs/plano.md)
- [Segurança e validação](docs/seguranca-validacao.md)
- [Recursos e diagnóstico](docs/recursos.md)
- [Base oficial](docs/iso-base.md)
- [Decisões e pendências](docs/decisoes.md)
- [Contribuição e Git](CONTRIBUTING.md)

## Estrutura

```text
config/          intenção declarativa, versões e seleção de ferramentas
packages/        grupos de software (planejamento, ainda não instaláveis)
overlay/         futuros arquivos de personalização do sistema
scripts/         diagnósticos locais sem privilégios
pipeline/        contrato das etapas futuras de construção
tests/           matriz de aceitação
docs/            decisões e documentação
assets/          futura identidade visual original
reports/         relatórios locais ignorados pelo Git
sources/         futuras entradas verificadas, ignoradas pelo Git
work/            área temporária futura, ignorada pelo Git
artifacts/       saídas futuras, ignoradas pelo Git
```

## Diagnóstico

Execute `python3 scripts/diagnostico.py` e `python3 scripts/verificar-projeto.py` na raiz. Ambos apenas leem informações e imprimem resultados; não acessam a rede, não instalam pacotes e não iniciam builds. Para salvar um relatório local, redirecione a saída explicitamente para `reports/`.

## Escopo

Desenvolvimento: PHP, Composer, Apache, MariaDB, Node.js LTS, TypeScript, Git, GitHub CLI, VS Code e Docker Compose. Redes: Nmap, Wireshark, tcpdump, iperf3, Remmina, SSH e OpenVPN via NetworkManager. Escritório: Writer, Calc, Impress e leitor PDF. Personalização: identidade DevLite OS, menu XFCE e DevLite Control.

A aquisição, reconstrução experimental e personalização mínima 4B.1 foram concluídas. A preparação integrada 4B.7–4B.9 permite código, auditorias e testes não privilegiados: não instalar pacotes, executar root/chroot, baixar artefatos ou gerar outra ISO. Os scripts de build anteriores permanecem no projeto, sem execução nesta etapa. Não há commits automáticos.
