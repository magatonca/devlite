# Validações da Fase 2

Executar da raiz:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 scripts/verificar-projeto.py
python3 scripts/validar-iso.py
```

Os testes usam amostras temporárias e não alteram a ISO: entrada ausente/duplicada, hash inválido, signatário inesperado, alteração de conteúdo e rejeição GPG de uma cópia alterada de SHA256SUMS. O teste GPG integrado requer a chave/metadados locais adquiridos; sem eles é marcado como ignorado.

O validador real exige GPG válido com a impressão digital fixada, entrada única no arquivo assinado e SHA-256 correspondente. Não acessa rede, não instala ferramentas e não escreve na ISO. A chave dedicada deve estar em sources/verification/trustedkeys.gpg; sua identidade foi conferida no tutorial oficial Ubuntu.

`python3 scripts/inspecionar-iso.py` primeiro revalida a base, gera relatórios em reports/phase2 e extrai cópias de casper, GRUB e .disk para work/phase2. A original é aberta como entrada pelo xorriso, sem -outdev; nenhuma montagem é realizada. O destino casper não pode existir para evitar sobrescrever inspeção anterior. Há uma segunda verificação integral ao final. A extração ocupa aproximadamente o tamanho de casper; conferir espaço antes de executar novamente. O initrd também é inventariado com lsinitramfs e extraído com unmkinitramfs, ferramentas já instaladas. Não executar os arquivos extraídos.

Estes ensaios não são testes de boot nem instalação. Esses permanecem pendentes para o laboratório da Fase 3.

## Preparação da Fase 3A

`python3 scripts/diagnostico-virtualizacao.py` lê CPU, memória, presença de ferramentas, firmware OVMF e /dev/kvm; não instala, carrega módulos ou executa hipervisor. O relatório local foi salvo em reports/phase3a/diagnostico-virtualizacao.json.

`python3 scripts/validar-relatorio-iso.py CAMINHO_JSON` valida os campos obrigatórios do relatório manual para BIOS e UEFI, sem iniciar testes. O [modelo](modelo-relatorio-iso.json) é pendente e deve retornar código 1 até ser preenchido com evidências reais; não alterar o modelo para simular aprovação.

`test_fase3a.py` testa extensões ocultas, permissões KVM, orçamento de memória, rejeição de relatórios incompletos, firmware ausente, hash incorreto, VM duplicada, evidência vazia e JSON inválido. Os casos positivos usam dados fictícios somente em memória. A suíte contém 15 testes no total, todos aprovados. Nenhum resultado sintético aprova a ISO. Ver [procedimento](../docs/fase3a-testes-iso.md).

## Pipeline da Fase 3B

`test_pipeline.py` usa amostras e subprocessos Python controlados para verificar falhas e preservação de logs, sem reconstruir ISOs reais. Cobre boot/GPT/EFI, saídas inseguras, mudanças em SquashFS e no código BIOS, metadados Unix e rejeição de manifests adulterados. Ver [pipeline](../docs/fase3b-pipeline.md). O mesmo comando unittest discovery executa todas as fases.

## Personalização da Fase 4A

`test_customization.py` acrescenta 18 testes; a suíte completa contém 47. Cobre dependências e ciclos, duplicações, conflito de providers, arquitetura e suite, perfis de idioma/ABNT2, XML, camadas, queries APT somente de leitura, integridade SHA/SRI e exportações confinadas. Os testes usam fixtures e amostras temporárias; não instalam pacotes ou criam imagens/VMs.

Para conferir uma exportação: `python3 scripts/planejar-personalizacao.py --verify-export work/PASTA_GERADA`. Para gerar outra: `python3 scripts/planejar-personalizacao.py --check-apt-cache --audit-layers --export`. Ver [limites e procedimento](../docs/fase4a-personalizacao.md).

## Personalização mínima da Fase 4B.1

A suíte padrão contém 60 testes após a implementação mínima. Os 13 casos adicionais cobrem confinamento de caminhos, whitelist de configurações, preservação de xattrs/hardlinks, reconciliação live, argumentos de boot, identidade Ubuntu, checksums e recusa de payload adulterado.

```sh
TMPDIR="$PWD/work/phase4b1-tests-tmp" PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py' -v
```

A aceitação da imagem real fica separada do discovery padrão; requer montagem concluída e auditada. Não monta nem executa a imagem. Lê as SquashFS extraídas da ISO resultante para conferir configurações, links, locale binário, identidade, estado dpkg de ambas as camadas e o snap original do instalador.

```sh
DEVLITE_MINIMAL_WORKSPACE="$PWD/work/phase4b1-dhzezpnz" TMPDIR="$PWD/work/phase4b1-tests-tmp" PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'acceptance_minimal_image.py' -v
```

Ver [procedimento, limites e resultados](../docs/fase4b1-personalizacao-minima.md). Esses testes não aprovam boot, instalação nem persistência pós-instalação.

Resultado desta execução 4B.1: 60 testes da suíte e cinco testes da imagem real aprovados, sem falhas. Relatórios locais em reports/testes-ate-fase4b1.txt e reports/aceitacao-fase4b1.txt.

## Preparação da Fase 4B.2

A suíte padrão tem 75 testes aprovados (15 novos em test_installation_plan.py). Inclui APT real sobre fixture file: com dependências transitivas/alternativas, recusa de remoções/boot/provider proibido, isolamento APT, assinatura/hash inválidos, arquivos deb e banco dpkg incompleto, perfis inativos e recursos. Não instala pacotes nem acessa rede. Os cinco ensaios da ISO 4B.1 são históricos e não foram repetidos nesta fase. Ver [resultados e reprodução](../docs/fase4b2-preparacao-programas.md).

## Executor da Fase 4B.3

105 testes aprovados: 75 anteriores e 30 novos em test_executor.py. Chamadas de mount, chroot, systemd, capabilities e instalação não são executadas: os testes usam fixtures/mocks e validação de contratos, além da simulação APT já existente. Cobrem rollback lógico, quarentena, restauração de policy, namespaces/limites declarados, proteção de arquivos e hardlinks, auto/manual do APT e plano de delta. Probe real e cenários reais de cgroup/disco/reboot dependem de autorização separada. Ver [resultados](../docs/fase4b3-executor-isolado.md).

## Validação da Fase 4B.4

A suíte original de 105 testes passou novamente; após os reforços do probe, 116 testes passaram. Os 11 novos em test_isolation_validation.py cobrem checkpoints, cgroups em fixture, capabilities, negação de acesso sem escrita, mounts, ausência de APT/dpkg no modo probe e interrupção/recuperação com mocks. Não executam namespaces, chroot ou mounts. Arquivos críticos, mountinfo e backings de loop do host permaneceram iguais durante a suíte final. [Resultados e comandos para aprovação](../docs/fase4b4-validacao-isolamento.md).

## Preparação dos pacotes 4B.5

131 testes aprovados: 116 anteriores e 15 novos em test_package_acquisition.py. Os testes de download usam somente bytes/respostas fictícias e não transferem pacotes. Cobrem origens/redirects, índices, validade, deduplicação, gates, hash/tamanho, parciais, cache, reserva e indisponibilidade. Os repositórios foram consultados separadamente apenas por HTTPS HEAD sem corpo. [Resultados](../docs/fase4b5-preparacao-pacotes.md).

## Fluxo integrado 4B.7–4B.9

158 testes de suíte aprovados, incluindo 27 novos em test_release_pipeline.py; cinco verificações estáticas da referência 4B.1 foram executadas separadamente. A fixture pequena SquashFS foi reconstruída duas vezes com igualdade de bytes e round-trip de metadados, sem mounts. Não houve boot, instalação, integração root ou ISO nova. O modelo de aceitação real continua pendente e seu validador retorna 1, como esperado. [Resultados consolidados](../docs/fases4b7-9-integradas.md).

## Correções do cache APT após execução real

162 testes aprovados em reports/testes-release-cache-isolado.txt. Os quatro testes em test_apt_local_archives.py reproduzem o erro de caminho relativo de --no-download, a necessidade de partial/lock fora do bundle RO, e verificam links transitórios/limpeza sem sobrescrever arquivos existentes. Usam debs vazios locais, APT em diretórios de fixture, dpkg=/bin/false e Debug::pkgDPkgPM=true: nenhuma instalação, script de manutenção, mount ou rede de aquisição é executado. A simulação RO usa permissões 0555/0444 como magaton; não monta filesystem real. O probe real da tentativa 2 passou, mas sua instalação abortou e não há par aceito. O código corrigido exige novo contrato/probe; o guard de 56 GiB permanece ativo.

## Versões com epoch e barreira anterior ao unpack

166 testes passaram em reports/testes-release-epoch-apt.txt. As novas regressões em test_apt_local_archives.py cobrem epochs (%3a), recusa de identidades inseguras, APT real de fixture e proibição de instalação após preflight incompleto/falho. O preflight separado dos pacotes reais verificou 240 caminhos Base e 239 Live, com dpkg=/bin/false e modo Debug::pkgDPkgPM=true. Não instala pacotes nem executa scripts; os bancos de fixture e os arquivos críticos do host permaneceram iguais. O primeiro coletor foi refinado para não agrupar caminhos em --recursive. Isso valida montagem dos comandos/cache, sem aprovar scripts de manutenção ou uma instalação completa. A terceira instalação real já havia falhado parcialmente na Base e permanece em quarentena.

## Runtime privado do Apache

168 testes aprovados em reports/testes-runtime-apache.txt. As duas regressões de test_runtime_directories.py reproduzem o mktemp de lock com diretório pai ausente, verificam sua preparação com modo 1777 e rejeitam escape por symlink. Usam apenas diretórios de fixture/coreutils como magaton, sem instalar ou executar Apache, montar ou criar namespaces. A quarta instalação real concluiu APT e passou em dpkg/APT, mas falhou na checagem Apache porque /run/lock não existia; o aceite completo e a Live ainda não foram exercitados. A correção exige novo probe e instalação com contrato atualizado.
