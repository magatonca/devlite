# Recursos e diagnóstico inicial

Medição em 16/11/2026: volume raiz de 48 GiB, aproximadamente 37 GiB disponíveis; RAM total 3,8 GiB, disponível 2,5 GiB; swap 3,8 GiB. /tmp e projeto compartilham o mesmo filesystem: não somar seus espaços livres. Host x86_64, Ubuntu 24.04.5 LTS; Python 3.12.3, Git 2.43.0, xorriso 1.5.6, squashfs-tools 4.6.1. Repositório main sem commits e sem arquivos anteriores fora de .git.

## Estimativa de engenharia, ainda não medida em build

| Uso simultâneo | Faixa estimada |
|---|---:|
| ISO original | 3–4 GiB |
| Árvore da ISO extraída | 3–5 GiB |
| Rootfs expandido com ferramentas | 12–20 GiB |
| Cache e arquivos temporários | 3–6 GiB |
| Nova squashfs e ISO de saída | 8–14 GiB |
| Total sem discos de teste | 29–49 GiB |

Reservar adicionalmente pelo menos 10 GiB livres para o host. Planejar 60–80 GiB livres para construir com folga; VMs de teste requerem orçamento separado (disco virtual sugerido de 40 GiB por VM; arquivo dinâmico cresce conforme uso). Snapshots também consomem disco. Os 37 GiB atuais são marginais e podem se esgotar; não liberar build com base apenas nessa estimativa. Após adquirir a base, medir expansão e reavaliar antes de construir.

4 GiB de RAM permitem planejamento e podem permitir build sequencial com compressão limitada e swap, com lentidão. Recomendar 8 GiB para construção e testes confortáveis; não executar VM de teste e compressão ao mesmo tempo no orçamento atual. Não criar swap nem alterar RAM automaticamente. O script de diagnóstico alerta abaixo de 60 GiB livres e 8 GiB de RAM total; alerta é planejamento, não autorização para construir.

Meta provisória do sistema instalado: testar em VM com 2 vCPU e 4 GiB, registrar memória em repouso e com cargas representativas. IDE, navegador, Docker e banco simultâneos podem exigir mais RAM. Fixar limites finais apenas após medições.

O runner acessou o diretório por modo alternativo após falha do sandbox. Git detectou dono diferente do processo de execução; inspeção usou safe.directory apenas na invocação, sem alterar configuração global. Não foi executado comando privilegiado.

## Atualização da Fase 2 — 16/11/2026

Filesystem expandido para 97 GiB; 84 GiB disponíveis antes da aquisição. RAM e swap mantidas. Há margem para aquisição e inspeção; build e VMs continuam sujeitos a medição de pico e execução sequencial. A propriedade dos arquivos da Fase 1 foi corrigida para magaton:magaton, excluindo .git, com autorização explícita do usuário. Operações da Fase 2 executadas como magaton.

Após download, cópia de casper e extração de inspeção do initrd: aproximadamente 79 GiB livres. Os tamanhos expandidos declarados pela base são inferiores à estimativa conservadora inicial; o tamanho do DevLite com todos os pacotes ainda não foi medido. Nenhum build foi iniciado.
