# Geração única da ISO pública candidata — proposta para autorização

**Executada; candidata verificada. Não repetir o comando.** Ver [artefato e próximos testes](iso-publica-candidata-concluida.md). A aplicação e integração do job `release-cezaiofx` terminaram com retorno 0. Recibo root-owned: `public_layers_verified`; round-trip Base/delta e composição pelo kernel aprovados. Host e gates íntegros; nenhum mount/loop residual do job.

Contrato de geração: `b47bc900132ada42a80d33892f981e429dd42d2ff341dece185d4734599159fe`.
Job: `/home/magaton/DevLite-OS/work/public-iso-1gj6j0xt`.

## Comando exato, como magaton e sem sudo

```sh
env PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 /home/magaton/DevLite-OS/scripts/gerar-iso-publica.py --job /home/magaton/DevLite-OS/work/public-iso-1gj6j0xt --approval-sha256 b47bc900132ada42a80d33892f981e429dd42d2ff341dece185d4734599159fe --execute-authorized
```

A autorização solicitada cobre somente **uma ISO candidata** dos inputs selados já publicados, mais a auditoria estrutural BIOS/UEFI/EFI, preservação do instalador, árvores, checksums e SHA-256. Não inclui outra construção, novas instalações, downloads, mounts, limpeza ou VMs. Não requer root e não modifica os gates persistentes. Não executar antes de autorização específica.

A imagem recebe o nome `devlite-os-1.0-amd64.iso` em um diretório novo de `artifacts/release-*` somente após a auditoria. O comando imprime o caminho do recibo de execução, que aponta o relatório com caminho, tamanho e SHA-256 reais. Fontes, ISO experimental e demais artefatos serão preservados. Falhas deixam os arquivos para auditoria, sem repetição automática; a reivindicação exclusiva impede reutilizar o contrato para gerar outra imagem.

Orçamento conservador para geração e auditoria: **22.64 GiB**, incluindo extração das duas árvores e margem. Disponível nesta preparação: **48.07 GiB**. O controlador repetirá as verificações relevantes imediatamente antes da geração e recusará inputs alterados, recibos incompletos ou margem insuficiente.

O novo controlador passou em 14 testes unitários adicionais (backend simulado), registrados em `reports/testes-preparacao-iso-publica.txt`; os 333 testes anteriores continuam documentados em `reports/testes-correcao-systemctl-unshare.txt`. Não se trata de uma nova execução conjunta de 347 testes. Nenhuma ISO foi produzida por esses testes.

Node.js 26.13.1 e TypeScript 7.0.2 foram aplicados nas duas visões, junto com identidade visual, menu XFCE e DevLite Control, com adições declaradas e arquivos anteriores preservados. VS Code permanece opcional e fora da imagem pública. Os programas ainda não foram executados no sistema convidado.

A candidata permanece sem aprovação de lançamento. Boot BIOS/UEFI, instalação, login, XFCE, pt-BR, ABNT2 e funcionamento dos programas exigem testes práticos. Não há comprovação de reprodução bit a bit dessa candidata de geração única. Após a geração e auditoria aprovadas, o caminho curto é transferir a candidata ao VMware Workstation e executar o checklist BIOS e UEFI existente.
