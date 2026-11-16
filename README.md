# DevLite OS 1.0 — Developer + Network Edition

Distribuição planejada sobre Xubuntu 24.04 LTS Minimal AMD64, com XFCE em português brasileiro. Fase atual: **1 — estrutura e planejamento**. Nenhuma ISO foi baixada ou construída.

## Navegação

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

Instalações, downloads de ISO, operações privilegiadas, partições e construção aguardam aprovação específica. Não há scripts de build executáveis nesta fase. Todos os arquivos foram criados do zero, sem reaproveitar projeto anterior.
