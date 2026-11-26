# Próxima autorização — somente três arquivos Node/TypeScript

A limpeza terminou com 71,12 GiB livres. Esta proposta é somente para aquisição como magaton, sem sudo, seguida das verificações e preparação local não privilegiadas. Não autoriza aplicação em imagem, instalação, mounts/chroot, repositórios ou ISO.

Versões fixadas; usar os metadados já autenticados, sem procurar versões novas. Limite agregado de **128 MiB**. Qualquer redirect, origem inesperada, truncamento ou diferença de tamanho/hash interrompe a aquisição e mantém a tentativa em quarentena.

| Arquivo | Origem oficial exata | Tamanho comprimido |
|---|---|---|
| node-v26.13.1-linux-x64.tar.xz | https://nodejs.org/dist/v26.13.1/node-v26.13.1-linux-x64.tar.xz | 34093052 bytes |
| typescript-7.0.2.tgz | https://registry.npmjs.org/typescript/-/typescript-7.0.2.tgz | Não informado; limitado pelo orçamento agregado |
| typescript-linux-x64-7.0.2.tgz | https://registry.npmjs.org/@typescript/typescript-linux-x64/-/typescript-linux-x64-7.0.2.tgz | Não informado; limitado pelo orçamento agregado |

Hashes/SRI fixados em [plano público](../packages/final-external-plan.json), a partir de [metadados autenticados](evidencias/autenticacao-metadados-externos.json). Node: conferir SHA-256 com checksum OpenPGP já autenticado; TypeScript: conferir os dois SHA-512/SRI associados às assinaturas ECDSA verificadas. Nenhum desses programas foi baixado nesta retomada.

Comando exato, como magaton, após autorização:

```sh
env PYTHONDONTWRITEBYTECODE=1 python3 /home/magaton/DevLite-OS/scripts/adquirir-payload-publico.py --plan-sha256 2c1be7aae26b6e4969480dafdfaf01dd949a97ecc6ab4d0d95b1bf82762bd261 --download-authorized
```

O código de aquisição e seu plano foram reconferidos contra os hashes já revisados, sem alterações. Após retorno válido, continuar automaticamente a inspeção e o staging em diretórios novos de work/; nenhum lifecycle script ou programa adquirido será executado nessa preparação. O plano atribui um máximo de 512 MiB ao payload preparado; confirmar novamente espaço antes de qualquer clone/aplicação.

A instalação isolada e a geração de uma única ISO candidata seguem pendentes de comandos/contrato e autorização próprios. VS Code continua opcional, fora da ISO pública.
