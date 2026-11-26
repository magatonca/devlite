# Fase 4A — mecanismo declarativo de personalização

Desenvolvido em 16/11/2026, como magaton. A fase prepara seleção, configurações, integridade e estratégia das camadas. **Não existe modo de aplicação ou instalação neste planejador.** Nenhum pacote foi instalado no host ou em chroot, nenhum repositório foi adicionado, nenhuma SquashFS foi modificada e nenhuma ISO foi gerada nesta fase. Boot e instalação reais continuam pendentes por decisão do usuário.

## Arquitetura e implementação

| Componente | Responsabilidade |
|---|---|
| packages/selection.json | seleção declarativa de 47 itens em cinco categorias, dependências lógicas, escopos e conflitos |
| packages/sources.json | origem Ubuntu e três origens externas desabilitadas |
| config/customization.json | pt-BR, ABNT2, fuso, XFCE, identidade e política de serviços |
| config/customization-lock.json | modelo ainda não resolvido de versões, dependências e hashes |
| pipeline/devlite/customize/manifest.py | validação, fechamento e ordenação das dependências lógicas |
| pipeline/devlite/customize/settings.py | geração de arquivos e operações futuras necessárias |
| pipeline/devlite/customize/layers.py | auditoria de sobreposições e plano de etapas das camadas |
| pipeline/devlite/customize/planner.py | composição do plano, consulta opcional do cache APT e exportação isolada |
| pipeline/devlite/customize/integrity.py | verificação local SHA-256, SRI SHA-512 e integridade do overlay preparado |
| scripts/planejar-personalizacao.py | interface de planejamento, exportação e verificação; sem opção --apply |

A revisão da 3B confirmou uma separação necessária: seu construtor preserva a árvore original e rejeita alterações internas. A 4A acrescenta módulos independentes; não enfraquece essas comparações nem os conecta ao caminho que gera ISOs. Na 4B, uma estratégia própria precisará validar mudanças permitidas nas camadas, manifests e configurações de boot, preservando GRUB/EFI. A reconstrução da 3B permanece uma referência sem personalização.

## Uso seguro nesta fase

Na raiz do projeto:

```sh
python3 scripts/planejar-personalizacao.py
python3 scripts/planejar-personalizacao.py --check-apt-cache --audit-layers --export
python3 scripts/planejar-personalizacao.py --verify-export work/PASTA_GERADA
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 scripts/verificar-projeto.py
```

O comando padrão apenas lê arquivos e imprime JSON. A consulta APT opcional executa somente `apt-cache policy` e `apt-cache show`, sem atualizar índices e sem simular instalações no estado do host. A auditoria lê listagens da Fase 2. A exportação cria uma pasta nova `work/phase4a-*`, com overlay, plan.json e overlay-manifest.json; não recebe um target-root e não escreve fora do projeto. Deve ser executada como magaton. O verificador só aceita exportações dentro de work. Não apaga exportações anteriores.

Código de saída 0 significa plano válido ou overlay íntegro, **não prontidão para instalar**. `ready_to_apply` permanece false e o plano enumera os bloqueios. Falhas de esquema, dependências lógicas, hashes ou caminhos retornam erro. UID/GID 0 nos manifests expressam a propriedade futura desejada; os arquivos preparados continuam pertencendo a magaton, sem chown privilegiado.

## Pacotes, dependências e origens

A seleção contém 44 pacotes com candidatos Ubuntu no cache local e três itens de origem externa: Node LTS, TypeScript e VS Code. A [lista detalhada](pacotes-origens.md) registra categorias, nomes, origens e versões observadas. GH e Compose v2 estão no Ubuntu; não há necessidade de adicionar os repositórios GitHub CLI ou Docker CE para satisfazer esses requisitos.

O Node do Noble é da série 18. Ele não satisfaz a exigência de uma linha LTS atualmente mantida pelo upstream; isso não é uma afirmação sobre a política de correções do pacote Ubuntu. A preparação usa distribuição binária oficial Node, com candidato consultado 26.13.1 LTS, ainda sem download ou lock aprovado. O tarball deve ter SHASUMS autenticado por chave de release previamente conferida. Não é usado script NodeSource/nvm nem adicionado repositório para Node. Referências: [Node disponível no Noble](https://packages.ubuntu.com/noble/nodejs), [downloads Node](https://nodejs.org/en/download) e [verificação oficial](https://github.com/nodejs/node#verifying-binaries).

TypeScript existe no Ubuntu como node-typescript, mas foi planejado via artefato npm isolado para não puxar nodejs 18 como dependência Debian ao combinar com Node upstream em /opt. Versão exata, engines, lock npm e SRI estão pendentes. O payload será preparado para instalação offline sem scripts de ciclo de vida. SHA/SRI conferem bytes; não dispensam revisão da identidade do pacote, origem TLS e, quando disponível, assinatura/proveniência. Referência: [distribuição oficial TypeScript](https://www.typescriptlang.org/download/).

VS Code depende de artefato/repositório Microsoft ou outra forma oficial de distribuição. O catálogo declara a origem APT Microsoft como desabilitada, sem fingerprint aprovado. Foi preparada a intenção debconf `code/add-microsoft-repo=false` para evitar inclusão automática; o comportamento da versão do .deb precisa ser conferido antes da instalação. Chave, metadados assinados, versão, hash e revisão de redistribuição permanecem pendentes. Nenhuma source.list é emitida no overlay. Referência: [instalação Microsoft](https://code.visualstudio.com/docs/setup/linux).

As verificações atuais validam formato, arquitetura declarada, duplicatas, dependências lógicas, ciclos, escopos e conflito entre providers. O lock proíbe nodejs/npm/node-typescript do Ubuntu e a mistura Docker CE com docker.io. A resolução APT completa deve ocorrer no contexto descartável do alvo, com seus índices e estado, nunca inferida de uma simulação no host. Congelar também dependências transitivas, origens e hashes. O cache consultado não foi atualizado nem autenticado novamente e não constitui lock.

## Configurações implementadas como preparação

- `/etc/default/locale`: LANG pt_BR.UTF-8 e LANGUAGE pt_BR:pt, sem impor LC_ALL global.
- `/etc/default/keyboard`: modelo abnt2, layout br, variante vazia.
- `/etc/timezone` e symlink relativo `/etc/localtime`: America/Sao_Paulo, dependente de tzdata no alvo.
- MariaDB: configuração separada em `99-devlite.cnf` com bind-address 127.0.0.1.
- XFCE: XML de xsettings e keyboard-layout em /etc/xdg e /etc/skel, com Greybird, ícones elementary-xfce-dark e uso do teclado do sistema. Os respectivos pacotes de tema foram incluídos.
- Identidade inicial: /etc/devlite-release e /usr/share/devlite-os/identity.json. Os arquivos Ubuntu os-release/lsb-release são preservados para compatibilidade; identidade visual completa, menu e DevLite Control continuam para etapas posteriores.

A geração real do locale exige incluir `pt_BR.UTF-8 UTF-8` em locale.gen sem apagar outras entradas e executar locale-gen no alvo autorizado. A seleção debconf de timezone/teclado deve ser reconciliada após instalação dos pacotes. Gerar XML não testa uma sessão XFCE; o resultado gráfico exige ensaio em VM. A [documentação Xfconf](https://docs.xfce.org/xfce/xfconf/start) descreve a persistência XML e o [teclado XFCE](https://docs.xfce.org/xfce/xfce4-settings/keyboard) permite herdar padrões do sistema.

O código original do initrd foi apenas lido: o hook 14locales reconhece locale na linha do kernel, e 19keyboard começa com teclado us. Para o live foram preparados `locale=pt_BR.UTF-8`, `keyboard-configuration/layoutcode=br` e `keyboard-configuration/modelcode=abnt2`. Na 4B, aplicar de maneira equivalente às entradas normais e safe graphics de BIOS/UEFI, preservando os demais argumentos; não houve edição de GRUB nesta fase. O instalador ainda pode substituir idioma, teclado e fuso por escolhas do usuário, o que precisa ser testado.

Apache, MariaDB, Docker/socket/containerd e iperf3 permanecerão sem ativação automática. Os presets debconf planejam iperf3 sem daemon, Wireshark sem captura privilegiada automática e nenhuma inclusão no grupo docker. Um policy-rc.d temporário só poderá ser usado no alvo isolado durante instalações e terá de ser restaurado; não é emitido como configuração permanente. NetworkManager deve continuar funcional.

## Mecanismos oficiais investigados e decisão

O catálogo real aponta `minimal.squashfs` como fonte instalada. A folha `minimal.live.squashfs` é selecionada pelo initrd para o live. A [documentação Curtin](https://curtin.readthedocs.io/en/latest/topics/config.html#sources) descreve a hierarquia fsimage-layered por nomes; a [documentação Casper](https://manpages.ubuntu.com/manpages/noble/man7/casper.7.html) descreve a seleção da folha no boot. A escolha do projeto é preservar essa divisão e personalizar a base para que os aplicativos também persistam após instalar.

Subiquity oferece [packages](https://canonical-subiquity.readthedocs-hosted.com/en/latest/reference/autoinstall-reference.html#packages) no sistema alvo e late-commands após a instalação. Isso é uma alternativa para perfis conectados, mas não resolve sozinho a presença dos programas no live e pode criar dependência de rede na instalação. Não foi gerado autoinstall.yaml nem presumido suporte irrestrito da interface Desktop Bootstrap a todo fluxo documentado. O instalador embarcado é preservado; nenhum hook baixado é executado.

## Modificação das camadas na futura 4B

1. Reautenticar fonte e camadas. Reservar área exclusiva e ambiente descartável; medir disco e memória.
2. Resolver e baixar artefatos aprovados; fixar versões, assinaturas, hashes e transação. Não atualizar tudo, não remover pacotes e proteger kernel, módulos, GRUB, shim, Casper, snapd e instalador.
3. Extrair a base preservando proprietários, modos, xattrs e capabilities. Compor visão original live em montagem somente de leitura, dentro de namespace/laboratório isolado, para classificar pacotes e arquivos exclusivamente live.
4. Instalar offline no alvo autorizado a seleção resolvida, aplicar os arquivos preparados e finalizar locale/teclado/fuso/serviços. Nunca aplicar no Ubuntu Server ou bind-mount de seu home.
5. Criar a visão live sobre a nova base e reaplicar o conjunto exclusivamente live. Preservar Desktop Bootstrap/Subiquity, snaps, seeds, assertions e serviços necessários. Reconciliar estado dpkg/APT; não copiar integralmente status ou extended_states antigos sobre a nova base.
6. Capturar uma folha coerente, tratando removidos, whiteouts, diretórios opacos, UID/GID e xattrs. A 4A implementa auditoria e plano de etapas, não um algoritmo de delta genérico não validado. O formato deve ser comprovado no laboratório antes de empacotar.
7. Gerar as duas SquashFS sequencialmente, inicialmente com um processo. Regenerar manifests completos e deltas nos formatos observados, .size, catálogo e checksums. Assinaturas oficiais antigas não autenticam camadas modificadas: definir assinatura DevLite e sua integração de verificação antes de distribuir.
8. Integrar ao empacotamento com replay de boot, preservar EFI anexada e validar mudanças por allowlist específica da personalização. Não desativar verificações para contornar diferenças esperadas. Testar live e instalado, com BIOS e UEFI, quando autorizado.

A auditoria das listagens históricas encontrou 80.893 entradas na base, 64.655 no live e 50 sobreposições não diretório. Incluem dpkg/status, diversions e apt/extended_states. Os 11 destinos de configuração preparados não apareceram diretamente na folha antiga; isso não dispensa verificar ancestrais, whiteouts, atributos opacos, hooks de boot e scripts do instalador. As listagens não comprovam igualdade de bytes nem preservação de xattrs; o plano mantém essa limitação explícita.

## Recursos e estado de validação

Há aproximadamente 67 GiB livres; esta fase só adicionou arquivos pequenos. Com 3,8 GiB RAM, não usar tmpfs para rootfs, não comprimir duas camadas em paralelo e não iniciar VM de teste junto ao build. A 4B terá de medir expansão, caches e espaço temporário antes de começar; os arquivos anteriores não foram removidos. Não criar swap ou ampliar recursos automaticamente.

47 testes automatizados passaram no conjunto atual (29 anteriores e 18 de personalização). Eles cobrem seleção e fechamento, ciclos, providers, arquitetura, configurações/XML, sobreposição de camadas, bloqueios de lock, SHA/SRI adulterados, caminhos inseguros, exportação isolada e recusa de --apply. Os 11 arquivos de preparação passaram na verificação de integridade. Não foram testados instalação APT, rebase real, locale-gen, sessão XFCE, boot ou instalação do sistema.

## Operações pendentes e autorização para 4B

| Operação futura | Privilégio / rede | Condição |
|---|---|---|
| Revisar catálogo, renderizar configurações, hashes e testes locais | sem sudo; sem rede | já implementado |
| Atualizar índices do alvo, baixar .deb, Node, TypeScript, VS Code e chaves/metadados | rede; sudo apenas se o mecanismo no alvo exigir | aprovação de downloads/origens; não usar apt update no host |
| Adicionar origem Microsoft | root no alvo + rede | aprovação específica, fingerprint confiável e signed-by limitado; nunca automática |
| Extrair/restaurar UID/GID, devices, capabilities e xattrs; montar camadas/overlay/namespaces | root/sudo no laboratório descartável | autorização explícita; não realizar sobre volumes do host |
| Instalar em chroot/alvo isolado, gerar locales, reconciliar timezone/teclado e desativar serviços | root/sudo no alvo; preferir instalação offline | executor ainda a implementar após autorização e locks aprovados |
| Gerar SquashFS com metadados privilegiados e integrar imagem personalizada | root conforme estratégia de preservação; sem rede após aquisição | aprovação de construção personalizada, recursos medidos e verificação de assinaturas definida |
| Criar/iniciar VMs e instalar para validar BIOS/UEFI | autorização separada | testes continuam adiados; não há aprovação automática |

Antes da execução 4B, ainda faltam resolver a transação APT completa, selecionar/fixar TypeScript e VS Code, autenticar artefatos e chaves externas, conferir compatibilidade ABI/CPU/engines de Node/TypeScript, comprovar o rebase e definir assinatura própria. A consulta oficial de Node é candidata de planejamento, não aprovação permanente de versão ou suporte. Implementar o executor não autoriza executá-lo: mudanças privilegiadas, rede, fontes externas e construção personalizada precisam de escopo explícito.

## Artefatos de preparação

Exportação final: `work/phase4a-m4cmg7q9`, contendo os 11 arquivos/links preparados, plan.json e overlay-manifest.json. As duas exportações anteriores foram preservadas. Resumo em [evidencias/fase4a-preparacao.json](evidencias/fase4a-preparacao.json) e candidatos em [evidencias/pacotes-cache-apt.json](evidencias/pacotes-cache-apt.json). Esses arquivos não são evidência de instalação ou de boot.
