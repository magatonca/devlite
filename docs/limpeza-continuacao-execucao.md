# Limpeza autorizada: execução privilegiada pendente

Escopo: os 43 candidatos do manifesto já aprovado; cerca de 8,35 GiB. Nenhuma exclusão foi executada. Três caminhos privados impedem o preflight como magaton. O comando exige confirmação específica de sudo.

```bash
sudo /usr/bin/python3 -B /home/magaton/DevLite-OS/scripts/limpar-continuacao-controlado.py --plan /home/magaton/DevLite-OS/work/cleanup-continuacao-iahn9k2h/plan.json --sha256 1bea31ca0c09e5d2dc27a76a1571681cbc129e021ffe03bce1e76395acdcea66 --execute-authorized
```

O preflight verifica namespaces de mounts dos processos, loops, serviços DevLite ativos, cwd/root/descritores/mapeamentos, symlinks, hardlinks externos, inventário e hashes. Verifica ISO oficial, homologada, pares Base/Live aceitos, camadas canônicas e recibos. Índices duplicados são comparados às cópias preservadas. A execução para diante de falhas; execution.json registra itens já removidos. Exclusões são irreversíveis; uma falha durante a execução pode deixar limpeza parcial registrada. Sem instalação, montagem, serviço, navegador ou ISO. Código e plano vinculados por SHA-256.
