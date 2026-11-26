# Retomada concluída — aplicação pública e camadas

Em 18/11/2026 o job `release-cezaiofx` terminou com retorno 0, em 2h55min50,872s, CPU 53min52,039s, pico de RAM 2,5 GiB e swap 26,1 MiB. O recibo root-owned, modo 0444, registrou `public_layers_verified`.

## Concluído

- Node.js 26.13.1, TypeScript 7.0.2, identidade visual, menu XFCE e DevLite Control aplicados nas cópias Base e Live: 6.407 novos caminhos em cada visão; todos os 113.889 caminhos anteriores da Base e 176.566 da Live preservados. Bancos dpkg não alterados. Nenhum programa do alvo executado.
- Base e delta comprimidos com um processo e limite de memória do compressor. Reextração comparada integralmente, incluindo bytes, metadados, atributos e hardlinks; composição Base + delta pelo kernel igual à Live esperada. Manifests, tamanhos e catálogo do instalador publicados em `work/release-cezaiofx/published-casper`.
- Handoff selado e auditorias externas/internas do isolamento aprovados. Arquivos críticos do host e configuração conferidos ao final; gates false, serviço inativo/coletado, nenhum mount ou loop residual desse job. Sem APT, downloads, nova limpeza ou geração de ISO.
- Controlador da candidata preparado em `pipeline/devlite/public_iso.py`, `pipeline/devlite/public_iso_control.py` e `scripts/gerar-iso-publica.py`; 14 testes adicionais aprovados em `tests/test_public_iso.py`. Evidência dos testes: `reports/testes-preparacao-iso-publica.txt`. Os 333 testes anteriores permanecem documentados, sem alegação de nova execução conjunta.

## Hashes das camadas publicadas

| Camada | SHA-256 |
| --- | --- |
| minimal.squashfs | f5bd9dfb6d4c8244c04f6a048a6fdaf7801c9ba09ac6e69d7b106d32ca12e7cc |
| minimal.live.squashfs | fae422b8d9dfc13b354947aee23f5088220dd3f843de29b30a92cc7a86c6eee5 |

Recibo público SHA-256: `7fe382bd2bf97ce6a4a61ffaeade45b72dc32385e9c08182c88fd2d86f72a27f`.
Recibo das camadas SHA-256: `a59afe3fe6c85378e343d81e16d2f324c9f49d0817eff6a04feeb1ef723e1771`.
Evidência consolidada: `docs/evidencias/aplicacao-publica-execucao.json`.

## Bloqueado e caminho curto

A nova ISO ainda não foi gerada. A proposta de autorização está em `docs/autorizacao-iso-publica-candidata.md`, com job `public-iso-1gj6j0xt`, comando exato e contrato selado. Espaço disponível aproximadamente 48,07 GiB; orçamento conservador 22,64 GiB. Não há necessidade de limpeza adicional para essa geração.

Após aprovação: gerar uma única candidata como magaton, auditar boot/EFI/instalador e integridade, registrar caminho/tamanho/SHA-256 e seguir com testes práticos em VMware BIOS e UEFI. Os testes reais de boot, instalação, login, XFCE, idioma, teclado e programas continuam pendentes; a igualdade estrutural não é aprovação funcional nem de persistência pós-instalação. VS Code permanece opcional e fora da ISO pública. Sem commits automáticos.
