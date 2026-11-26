# Fase 4B.5 — preparação dos pacotes Ubuntu

Estado em 16/11/2026 (America/Sao_Paulo): **preparação e aquisição autorizada concluídas; instalação permanece bloqueada**. Após o usuário aprovar exclusivamente o comando do manifesto congelado, os 243 debs foram baixados como magaton, sem sudo, sem atualização dos índices remotos e sem APT/dpkg no alvo. A permissão de download foi temporária e voltou a false.

## Resultado da aquisição autorizada

- Processo retornou 0; receipt com status download_verificado.
- 243 arquivos novos, nenhum reutilizado de cache; **338.284.668 bytes (322,61 MiB)**.
- Auditoria independente após o download: conjunto exato de arquivos, tamanhos, SHA-256, origens/URLs e recibo conferidos contra o manifesto. Nenhum parcial ou lock remanescente.
- Término registrado: `2026-11-16T20:05:11.205332-03:00`.
- Espaço livre após a aquisição: aproximadamente **68.13 GiB**.
- Arquivos críticos, namespace/mountinfo e backings de loop do host permaneceram iguais nos checkpoints antes/depois. Nenhuma instalação, nova ISO, teste real de falha ou commit.
- download_pacotes_autorizado, downloads_autorizados, executor_autorizado, probe_autorizado e recuperacao_autorizada estão false.

Cache: `work/phase4b5-g78yd2oc/debs/`.
Receipt: `work/phase4b5-g78yd2oc/acquisition-1cqnoodi/receipt.json`.
SHA-256 do receipt: `ad354b3c463c1d766a40735e9c31d3ed4bed893c532aa76b39ec51e48aa89839`.
[Evidências da aquisição real](evidencias/aquisicao-pacotes.json). Checkpoints: reports/phase4b5/download-authorized-before.json e download-authorized-after.json.

O manifesto original não foi alterado: seu status descreve a preparação sem download e seu hash de autorização continua válido. O resultado da execução fica no receipt e nas evidências, sem reescrever o documento aprovado.


O probe root-owned probe_passed foi revisto e seus hashes de código continuam válidos. Os módulos aprovados do executor não foram alterados; aquisição é um módulo separado. O plano novo foi comparado ao plano do job do probe: transações dos dois alvos idênticas nesta execução. Isso não autoriza instalação nem conecta automaticamente o cache novo ao job antigo.

## Seleção e simulação

O catálogo 4A continua com 47 itens: **44 Ubuntu**, destinados ao instalado e ao live; Node LTS, TypeScript e VS Code permanecem desabilitados. Os nomes foram revalidados pelo validador declarativo e precisam corresponder exatamente aos 44 solicitados na simulação. As dependências lógicas do catálogo não substituem a resolução transitiva do APT.

Simulação nova: `work/phase4b2-oo4lx4r7/installation-plan.json`, com apt-get --simulate check e --simulate --no-remove --no-install-recommends install, status/preferences/caches próprios e dpkg apontado para /bin/false no config de simulação. Nenhum hook/configuração APT do host foi herdado. Não houve apt-get update.

| Alvo | Operações | Novos | Atualizações | Pacotes finais | Volume por alvo |
|---|---:|---:|---:|---:|---:|
| base | 240 | 227 | 13 | 1393 | 320.5 MiB |
| live | 239 | 223 | 16 | 1534 | 316.2 MiB |

Não houve remoções, downgrades ou alteração proposta em pacote protegido de boot/instalador. Não há pacotes base ausentes no live nem conflitos de versões compartilhadas. Permanecem 141 pacotes exclusivamente live após a transação, que não devem ser copiados indiscriminadamente para a base.

A união deduplicada contém **243 arquivos .deb**, dos quais 236 atendem aos dois alvos. São 37 artefatos dos itens diretamente selecionados e 206 artefatos de dependências transitivas; sete dos 44 itens diretos já estão satisfeitos nos dois ambientes. Total: **338.284.668 bytes (322,61 MiB)**. Somar as transações sem deduplicar daria 636,74 MiB.

As atualizações existentes incluem libc/locales, Perl, certificados, tzdata e openssh-client; a futura instalação não será puramente aditiva. Nenhuma delas foi aplicada nesta etapa.

## Repositórios: disponibilidade e limite da atualização

Foram feitas **somente consultas HTTPS HEAD**, sem corpo e sem gravar índice remoto, a:

- https://archive.ubuntu.com/ubuntu/dists/noble/InRelease — HTTP 200.
- https://archive.ubuntu.com/ubuntu/dists/noble-updates/InRelease — HTTP 200.
- https://security.ubuntu.com/ubuntu/dists/noble-security/InRelease — HTTP 200.

As respostas estão em reports/phase4b5/repositories-head.json. Essa checagem prova acesso aos endpoints via TLS; não autentica o conteúdo de um índice remoto nem garante que cada deb individual esteja disponível.

A simulação foi atualizada/reexecutada usando **snapshot local assinado**: noble de 25/04/2024, updates de 16/11/2026 11:35:59 UTC e security de 16/11/2026 11:16:59 UTC. Os cabeçalhos remotos indicam publicações posteriores (updates 17:32:24 e security 16:10:32 UTC). Portanto, este é um plano de versões congeladas autenticadas, não uma alegação de resolver os índices remotos mais recentes. Não transferi novos índices porque a instrução exige autorização antes de downloads reais.

O comando proposto baixa somente as versões deste manifesto. Se o objetivo mudar para resolver o último snapshot remoto, será necessária autorização para obter e validar os novos metadados, refazer a simulação e apresentar outro manifesto antes de baixar pacotes. Não atualizar índices ou substituir versões silenciosamente.

## Autenticidade, integridade e rastreabilidade

O preparador copiou e autenticou novamente três InRelease e seis índices Packages main/universe para noble, noble-updates e noble-security. A chave esperada é Ubuntu Archive 2018, `F6ECB3762474EDA9D21B7022871920D1991BC93C`, ancorada no keyring Ubuntu instalado. Cada Packages precisa ter SHA-256/tamanho exatos do InRelease assinado. Metadados futuros, expirados ou updates/security com mais de sete dias são rejeitados antes de aquisição.

Cada artefato é relacionado ao registro assinado por Package, Version, Architecture, Filename, Size e SHA-256. O manifesto inclui alvos, suite/componente, índice e seu hash, InRelease/hash, signer e URLs oficiais. Uma divergência entre base/live ou índice aborta. A cadeia é **InRelease assinado → SHA-256 de Packages → SHA-256 do deb**; não há alegação de assinatura individual de cada deb.

A autenticidade dos metadados e os hashes esperados foram verificados. A aquisição autorizada verificou os bytes de todos os debs antes da publicação; uma segunda auditoria independente confirmou SHA-256 e tamanhos do cache completo.

Manifesto: `work/phase4b5-g78yd2oc/download-plan.json`. São 330981 bytes de JSON, não um pacote. [Evidências e totais](evidencias/preparacao-pacotes.json).

## Aquisição controlada implementada e executada após autorização

Arquivos novos:

- scripts/pacotes-controlados.py — --prepare e --download, sem modo de instalação.
- pipeline/devlite/customize/package_acquisition.py — manifesto, autenticação, deduplicação e streaming controlado.
- tests/test_package_acquisition.py — 15 testes offline novos.

O download exige usuário magaton sem sudo, download_pacotes_autorizado=true especificamente autorizado, SHA-256 exato do manifesto e hashes de código/plano/seleção ainda iguais aos revisados. A flag permanece **false** e não é habilitada pelo programa. executor_autorizado, probe_autorizado, recuperacao_autorizada e permissões genéricas também permanecem false.

Antes da primeira conexão de aquisição, o downloader reautentica as cópias locais de InRelease/Packages e recompõe a lista para conferir igualdade com o manifesto. Não instala, não faz apt-get update, não modifica o host e não executa arquivos transferidos. O código do downloader tem hashes próprios; alterar esse código invalida o manifesto de aquisição, sem invalidar automaticamente o executor antigo que não foi modificado.

Só aceita HTTPS archive.ubuntu.com/security.ubuntu.com, TLS validado e pool/*.deb. Não usa proxies herdados, downgrade para HTTP, terceiros ou credenciais. Redirects são limitados e precisam permanecer nesses hosts. URLs alternativas são apenas as registradas nos índices autenticados; 404/410 podem tentar a alternativa assinada, mas nunca outra versão. Qualquer indisponibilidade final exige revisão.

Transferências são sequenciais, com buffers de até 1 MiB, timeout de socket de 30 s e limite exato de bytes. Tamanho declarado, SHA-256 e espaço livre são conferidos. Cada arquivo é escrito em temporário exclusivo e só publicado após fsync/hash/tamanho, sem sobrescrever um cache existente. Arquivo inválido/partial fica preservado; cache válido pode ser reutilizado após nova conferência. Não há retomada automática de um parcial. Lock exclusivo impede duas aquisições simultâneas; lock remanescente após falha de gravação ou SIGKILL exige revisão, sem remoção automática de artefatos antigos.

Receipt inclui arquivo, versão/arquitetura, hashes, bytes, origem assinada, URL solicitada/final e horário. Reuso de cache é identificado como cache, sem inventar uma URL de transferência anterior. O comando não copia arquivos para dentro do job root do probe nem habilita --execute.

## Recursos

Espaço livre medido após preparar índices/manifesto: aproximadamente 68.55 GiB, já preservando os artefatos e a imagem do probe. Download único: 322,61 MiB. A aquisição exige esse volume mais reserva de 12 GiB (aproximadamente 12,32 GiB livres), com checagem durante o streaming.

A estimativa conservadora de instalação permanece **44.255.549.770 bytes (41,22 GiB) adicionais**, incluindo cópias e margem; o orçamento mais amplo do executor é 56 GiB. Há espaço para o download e ambos os orçamentos atualmente, mas repetir df antes de instalar. Arquivos temporários de falhas e geração de dados MariaDB podem ampliar consumo. Não apagar probes ou ISOs para ganhar espaço automaticamente.

A instalação futura continua limitada a 2,5 GiB RAM, 1 GiB swap, 128 tarefas, uma CPU, rootfs ext4 de 12 GiB por alvo e execução sequencial. Esses limites foram exercitados pelo probe sem pacotes; o pico real de scripts de manutenção ainda não foi medido.

## Critérios objetivos de interrupção

Aquisição: interromper por assinatura/chave/hash/versão/arquitetura/tamanho divergentes; snapshot expirado/alterado; URL, redirect ou certificado indevido; 404/410 sem alternativa travada; arquivo cache inválido; espaço abaixo da reserva; erro de leitura/escrita ou perda de exclusividade. Não substituir versões nem publicar arquivo parcial como concluído.

Instalação futura: não iniciar sem autorização própria, probe válido para o job/código, todos os debs íntegros e orçamento livre. Interromper/quarentenar se simulação no alvo divergir do lock, houver remoção/downgrade/alteração protegida, pacote extra, estado dpkg incompleto, dpkg --audit não vazio, apt --simulate check quebrado, configuração inválida, serviço não mascarado/daemon remanescente, alteração no instalador/snap/boot ou arquivos críticos do host, OOM/timeout/sinal/disco cheio. Nenhum rollback in-place ou dpkg --configure -a automático; aceitar somente o par completo base/live.

Interrupção/recuperação reais, OOM/reboot e maintainer scripts permanecem pendentes. Os testes do probe normal não aprovam esses cenários nem autorizam instalação.

## Comando exato autorizado e executado

Executar como magaton, sem sudo, após a confirmação específica recebida e habilitação temporária apenas de download_pacotes_autorizado; a flag já foi restaurada. Não habilitar instalação. Somente a permissão de download ficou true durante a operação autorizada; todas estão false ao final.

```sh
python3 /home/magaton/DevLite-OS/scripts/pacotes-controlados.py --download /home/magaton/DevLite-OS/work/phase4b5-g78yd2oc/download-plan.json --approval-sha256 06ac626af9624e3cf228ae9d6becc896b60c3b7b018f95e07ec1e88ee624ca9b
```

Hash do manifesto: `06ac626af9624e3cf228ae9d6becc896b60c3b7b018f95e07ec1e88ee624ca9b`.
Destino exclusivo: `/home/magaton/DevLite-OS/work/phase4b5-g78yd2oc/debs/`.
[Comando estruturado para revisão](evidencias/download-pacotes-comandos.json).

A autorização proposta limita-se aos 243 debs e versões desse manifesto, 338.284.668 bytes esperados, usando as URLs oficiais travadas. Não inclui refresh de índices remotos, instalação, mounts, chroot, sudo, repositório externo ou nova ISO.

## Testes e proteção do host

**131 testes aprovados**, incluindo 15 novos: hosts/HTTPS/redirect, origem assinada, deduplicação, índice alterado, validade exata, bloqueio antes da rede, recusa de root/hash incorreto, streaming de bytes fictícios, SHA errado, dados truncados/excessivos, Content-Length, cache e reserva de disco/404. Os testes não fazem transferência real: usam respostas em memória e arquivos de fixture dentro de work. Relatório em reports/testes-fase4b5.txt.

Os checkpoints do host foram comparados antes/depois da preparação e da aquisição real, sem diferenças nos arquivos e recursos monitorados; resultados nas evidências. Nenhum APT/dpkg foi executado dentro das imagens. O manifesto deixa ready_to_install=false por desenho; a preparação não é uma autorização de instalação.

Reproduzir preparação/testes sem rede de aquisição:

```sh
python3 scripts/preparar-programas.py --resolve-offline
python3 scripts/pacotes-controlados.py --prepare /home/magaton/DevLite-OS/work/phase4b2-oo4lx4r7/installation-plan.json
TMPDIR="$PWD/work/phase4b1-tests-tmp" PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 scripts/verificar-projeto.py
```

Cada preparação cria outro workspace; não reutilizar seu hash de aprovação neste manifesto. A referência oficial da cadeia de confiança é [apt-secure do Ubuntu Noble](https://manpages.ubuntu.com/manpages/noble/man8/apt-secure.8.html).

## Pendências após a aquisição

A integridade dos pacotes não autoriza instalá-los. O código aprovado do executor e seu atestado do probe foram preservados. O cache novo ainda não foi copiado para dentro do job de instalação, nem houve chroot ou execução de maintainer scripts. Instalação, testes reais de interrupção/recuperação/OOM/reboot, rebase live e nova ISO continuam dependendo de escopo e autorização próprios.
