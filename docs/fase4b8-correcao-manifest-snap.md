> Atualização: operação autorizada e concluída com retorno 0; camadas publicadas e verificadas. [Resultado consolidado](fase4b8-integracao-aprovada.md). A proposta abaixo é o registro histórico da autorização.

# Fase 4B.8 — correção do manifest Snap e nova proposta

17/11/2026. **191 testes aprovados; execução com o parser corrigido ainda bloqueada. Nenhuma ISO gerada.**

## Operação executada e resultado

A integração autorizada release-mlgwqtyc executou por 42min59s e terminou com retorno 1, em quarentena. A correção de xattrs foi exercitada em montagem real. A Base SquashFS, o delta Live e a visão OverlayFS combinada passaram na comparação integral de conteúdo, metadados, xattrs, hardlinks e devices. O código chegou à geração dos manifests somente após retornar com sucesso da comparação integral do merged; esse é o fundamento da afirmação, registrado junto ao traceback root-owned. Não houve recibo layers-ready.json: a integração completa não foi aprovada nem publicada.

A falha seguinte foi no parser de filesystem.manifest: esperava nome/versão, mas o arquivo oficial contém os registros abaixo, com nome, canal e revisão:

```text
snap:core22	stable	2437
snap:snapd	stable	27738
snap:ubuntu-desktop-bootstrap	24.04/stable/ubuntu-24.04	572
```

[Relatório root, traceback e journal](evidencias/integracao-mlgwqtyc-resultado.json). [Checkpoint e auditoria de encerramento](evidencias/integracao-xattrs-execucao.json).

Pico de memória contabilizado 2,5 GiB, swap zero. Host: hashes críticos iguais ao início, sem montagens ou loops residuais, unidade encerrada. Gate integracao_camadas_autorizada restaurado false; instalação e ISO continuam bloqueadas. Nenhum arquivo removido; Base/Live aceitas, SquashFS, ISOs anteriores e cache preservados. Nenhuma instalação, extração ou compressão repetida.

## Correção e validação antecipada

release_layers.manifests agora preserva nome/canal/revisão; mantém também compatibilidade com registros antigos de dois campos. Duplicatas, campos vazios, quantidade inesperada de campos e formato sem tabulação são rejeitados. Os três registros oficiais permanecem idênticos, incluindo o canal do instalador Desktop Bootstrap.

release_resume realiza uma renderização antecipada com o plano antes de inventariar as imagens. Também registra os estágios de prova concluídos no relatório, mesmo se alguma etapa posterior falhar. Esses registros são evidências de progresso e não substituem o recibo final exigido pela geração da ISO.

**191 testes aprovados**, incluindo o manifest oficial disponível, preservação dos três campos e rejeição de registros inválidos. Resultado: reports/testes-manifest-snap.txt. [Preflight real sem root](evidencias/preflight-metadados-reais.json): 1.393 pacotes APT na Base, 1.534 na Live, três snaps preservados exatamente e catálogo fsimage-layered com um campo de tamanho reconhecido. Não executou APT/dpkg ou instalações.

Cache novamente verificado: 243 debs. Verificação do projeto: zero erros. git diff --check aprovado. O código do executor aceito não mudou e não requer novo probe nem reinstalação. O contrato da integração muda porque inclui o parser e o backend corrigidos; o contrato histórico não será reescrito.

## Nova execução proposta

Job: `/home/magaton/DevLite-OS/work/release-63m6oz2_`.
Contrato SHA-256: `bc32e0ce9fb1a95d4b0170c1130f46ec523ddee0871b9fd3915e8f126a91d19d`.

```sh
sudo systemd-run --unit=devlite-pack-63m6oz2_ --wait --pipe --collect --property=MemoryMax=2684354560 --property=MemorySwapMax=1073741824 --property=CPUQuota=100% --property=TasksMax=128 --property=RuntimeMaxSec=10800 --property=KillMode=control-group --property=OOMPolicy=kill unshare --mount --propagation private /usr/bin/python3 /home/magaton/DevLite-OS/scripts/integrar-release-root.py --job /home/magaton/DevLite-OS/work/release-63m6oz2_ --approval-sha256 bc32e0ce9fb1a95d4b0170c1130f46ec523ddee0871b9fd3915e8f126a91d19d
```

Parada exclusiva se necessária: `sudo systemctl stop devlite-pack-63m6oz2_.service`.

O sudo é necessário para namespace privado e montagens RO ext4/SquashFS/OverlayFS. A proposta repete as auditorias completas porque a tentativa anterior não publicou um atestado final de camadas; não se converte um traceback de falha em recibo de aprovação. Não reinstala pacotes, não extrai ou comprime imagens, não limpa arquivos e não gera ISO. O preflight do formato dos manifests já passou com os dados reais antes desta solicitação.

Somente após aprovação, o controlador como magaton habilitará integracao_camadas_autorizada imediatamente antes e restaurará false em finally. Os demais gates continuam false. Mantidos: 2,5 GiB RAM, 1 GiB swap, uma CPU, 128 tarefas, três horas. O tempo observado da última auditoria foi aproximadamente 43 minutos; a próxima depende do desempenho de I/O.

Livre: **43.36 GiB**. Margem do caminho de auditoria/publicação: 12,18 GiB, incluindo tamanho dos packs e 10 GiB de reserva. Não se reduzem os guards originais de instalação/probe/reconstrução integral. Os packs originais selados continuam os mesmos; publicação acrescentará cerca de 2,18 GiB.

Riscos: nova falha de leitura, de recursos ou publicação mantém a tentativa em quarentena, sem recibo pronto para ISO. A autorização anterior vinculava outro job/hash; este comando não foi executado e requer nova aprovação. Após êxito, concluir auditoria e preparar a geração da ISO, que continua exigindo autorização específica. Boot BIOS/UEFI, instalação real, persistência pós-instalação e segunda construção reproduzível permanecem pendentes. Node.js LTS, TypeScript e VS Code ainda não fazem parte desta edição experimental Ubuntu.
