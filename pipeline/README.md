# Pipeline experimental

Implementação modular em `devlite/`, com interface `python3 scripts/construir-iso.py` (preflight) e `python3 scripts/construir-iso.py --build` (execução). Ver [procedimento e limites](../docs/fase3b-pipeline.md).

A Fase 3B reconstrói sem modificar conteúdo interno. Autentica a fonte, extrai cópias para auditoria, preserva a árvore ISO via xorriso nativo, reproduz o boot e compara o resultado antes de promover a saída. Não inicia VMs e não apaga arquivos de trabalho.

A Fase 4B.1 acrescenta `minimal_config.py`, `minimal_root.py` e `minimal_build.py`: prepara configurações isoladas, exige três comandos root previamente autorizados para preservar metadados das camadas e monta/audita a ISO como magaton. Não instala pacotes nem executa chroot. Consulte [personalização mínima](../docs/fase4b1-personalizacao-minima.md). O módulo `pseudo.py` é um experimento rootless não usado na construção real, devido à falha do exportador SquashFS 4.6.1 com capabilities.

A preparação 4B.2 usa customize/installation.py e service_profiles.py, por scripts/preparar-programas.py --resolve-offline: resolução real sem instalar, índices Ubuntu autenticados, bancos dpkg das imagens e perfis exportados inativos. Não há executor de instalação/rebase. Ver [plano](../docs/fase4b2-preparacao-programas.md).

O executor 4B.3 está em customize/executor*.py e guest_runner.py, com scripts/executar-programas.py --prepare PLANO. Probe, instalação e recuperação permanecem bloqueados separadamente. Usa ext4 descartável limitado, namespaces/cgroup e transação offline exata. reconcile.py planeja o delta, sem aplicação. Ver [arquitetura e comandos](../docs/fase4b3-executor-isolado.md).

Na 4B.4, o probe foi reforçado com sentinela real, evidências de processos/mounts/capabilities e leitura dos limites cgroup efetivos. scripts/diagnostico-isolamento.py lê o host sem sudo. Nenhum probe foi executado; ver [revisão e autorização pendente](../docs/fase4b4-validacao-isolamento.md).

O probe real normal da 4B.4 foi autorizado e aprovado no job phase4b3-1ibq_emz. Sem APT/dpkg no alvo. As flags estão novamente false; recuperação/interrupção reais e instalações não foram executadas.

Na 4B.5, scripts/pacotes-controlados.py e customize/package_acquisition.py preparam um manifesto deduplicado e aquisição por hash, sem instalação. Download tem gate próprio, false nesta entrega. O executor aprovado no probe permanece inalterado. Ver [manifesto, comandos e limites](../docs/fase4b5-preparacao-pacotes.md).

A aquisição real da 4B.5 foi autorizada e concluída: 243 debs íntegros no cache work/phase4b5-g78yd2oc/debs. Receipt e auditoria independente registrados. Download e instalação estão novamente bloqueados; nenhuma imagem foi alterada.

Fluxo integrado: `python3 scripts/devlite-release.py --prepare`. Verifica cache/probe/assinaturas, inspeciona scripts sem executar, prepara cache do executor e gera contratos de integração/ISO/aceitação. release_layers/pack/iso/acceptance implementam as próximas etapas com gates separados, sem execução automática. [Relatório único](../docs/fases4b7-9-integradas.md).
