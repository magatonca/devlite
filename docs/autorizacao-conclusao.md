# Próxima autorização — limpeza delimitada e três arquivos públicos

> Atualização: a tentativa de limpeza parou sem exclusões. Para nova execução, usar a [correção do diagnóstico e os hashes revisados](limpeza-correcao-diagnostico.md). Os hashes históricos abaixo não autorizam o código corrigido. Aquisição não faz parte da nova solicitação pontual.

**Proposta, não executada.** A aprovação solicitada abrange somente as duas operações abaixo em sequência. Qualquer falha de segurança interrompe a operação; não ampliar a lista, atualizar versões ou buscar outra origem automaticamente.

## 1. Limpeza delimitada

Lista exata: os 21 caminhos completos da [proposta de limpeza](limpeza-final-proposta.md), fixados em [plano JSON](evidencias/plano-limpeza-final.json). Nenhum diretório pai faz parte da autorização. Estimativa de 49,88 GiB alocados; livre atual aproximadamente 21,25 GiB. A recuperação real será medida após exclusão, não garantida pela soma dos tamanhos.

Comando proposto:

```sh
sudo env PYTHONDONTWRITEBYTECODE=1 python3 /home/magaton/DevLite-OS/scripts/limpeza-controlada-final.py --plan /home/magaton/DevLite-OS/docs/evidencias/plano-limpeza-final.json --plan-sha256 c0b96d65c99c175f7ccb0d2869579717dc700a7eb80b5625a66df0c083458c90 --execute-authorized
```

Root é necessário para ler todos os namespaces/processos e remover somente os arquivos privados root-owned já listados. O controlador:
- Revalida o hash do plano e exige a lista exata de 21 caminhos.
- Recusa candidatos/ancestrais symlink, filesystem diferente, hardlinks externos, alterações posteriores ao inventário e alvos em uso.
- Consulta todos os mountinfo e descritores/cwd/root legíveis dos processos, loops e jobs DevLite; visibilidade incompleta é falha, não aprovação.
- Revalida contrato, atestados, ISO original e igualdade das cópias antes da primeira exclusão.
- Usa remoção confinada por descritor de diretório, sem glob e sem seguir symlinks; registra progresso e eventual interrupção.
- Preserva ISOs canônicas, imagens Base/Live aceitas, cache, packed referenciado, código e evidências fora dos caminhos exatos.

A operação é irreversível para as cópias removidas: regeneráveis a partir das fontes preservadas. Inclui duas ISOs duplicadas; perde-se a segunda cópia física, preservando canônica e provas. Se interromper depois de algum caminho, registrar lista parcial e não alegar rollback. Não há instalação, montagem ou geração de ISO nessa operação. O preflight integral privilegiado ainda não foi executado.

## 2. Aquisição controlada, como magaton

Somente após a limpeza aprovada, bem-sucedida e nova conferência do orçamento, adquirir exatamente:

| Arquivo | URL oficial fixada |
|---|---|
| node-v26.13.1-linux-x64.tar.xz | https://nodejs.org/dist/v26.13.1/node-v26.13.1-linux-x64.tar.xz |
| typescript-7.0.2.tgz | https://registry.npmjs.org/typescript/-/typescript-7.0.2.tgz |
| typescript-linux-x64-7.0.2.tgz | https://registry.npmjs.org/@typescript/typescript-linux-x64/-/typescript-linux-x64-7.0.2.tgz |

```sh
env PYTHONDONTWRITEBYTECODE=1 python3 /home/magaton/DevLite-OS/scripts/adquirir-payload-publico.py --plan-sha256 2c1be7aae26b6e4969480dafdfaf01dd949a97ecc6ab4d0d95b1bf82762bd261 --download-authorized
```

Sem sudo; no ambiente do agente, o comando será executado por runuser como magaton. O plano fixa os hashes/SRI autenticados anteriormente. Node tem 34.093.052 bytes; tamanhos comprimidos TypeScript não publicados nos metadados. Limite agregado de 128 MiB. Sem redirects, proxy herdado, scripts remotos, versões novas, repositórios ou instalação. Divergência de origem/tamanho/hash interrompe e põe a tentativa em quarentena; não usar arquivos parciais.

Depois dos hashes/SRI válidos, a preparação local não privilegiada poderá continuar automaticamente: inspecionar arquivos, conferir identidades internas/licenças e materializar o payload em work/public-payload-* com o adaptador testado. Nenhum arquivo será aplicado à Base/Live por essa preparação.

## Fora desta autorização

Instalação/aplicação privilegiada às imagens, novas montagens/namespaces/chroot, geração de ISO e execução de VMs continuam bloqueadas. A próxima operação privilegiada será apresentada com comandos e contrato próprios após inspeção dos arquivos reais. A ISO candidata solicitada é **única**; não gerar uma segunda reprodução automaticamente.

## Código e planos revisados

Conferir estes SHA-256 antes de executar. Qualquer alteração exige nova revisão, sem reutilizar aprovação do código anterior.

| Arquivo | SHA-256 |
|---|---|
| scripts/limpeza-controlada-final.py | 390ff9320c562abe8344f0f0999e430ce96c9b82c69093b0e8fbb3c99dea57de |
| pipeline/devlite/final_cleanup.py | 2c692e05c1a77f71596f90ccafd11ed7ac1e4278337dd05febf8e55c46885b29 |
| scripts/adquirir-payload-publico.py | 446249d125c191c8b8bdc7ebcb7acce2d390c6aebda7827ffc7b1794bb314dab |
| pipeline/devlite/final_acquisition.py | 559a8280989d7ae46b1cb458df0685cf82796ded134415ef0641f9f60fb24821 |
| scripts/preparar-payload-publico.py | a9bdff5f7d7f2c021e243111ef6ba2e11f38102df59910b5353fa7c30ca384b3 |
| pipeline/devlite/final_payload.py | a84ec4fdec0b742a2dbfe9e64a22b56a785ffa00f282f6f54f1bae4ddd6ebb4b |
| docs/evidencias/plano-limpeza-final.json | c0b96d65c99c175f7ccb0d2869579717dc700a7eb80b5625a66df0c083458c90 |
| packages/final-external-plan.json | 2c1be7aae26b6e4969480dafdfaf01dd949a97ecc6ab4d0d95b1bf82762bd261 |

Testes: **259 aprovados**, incluindo 8 casos do payload, 8 de limpeza e 6 de aquisição, todos com fixtures. Isso não aprova exclusões reais, download real, aplicação em imagem, boot ou instalação.
