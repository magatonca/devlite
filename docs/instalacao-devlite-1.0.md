# Instalação e validação do DevLite OS 1.0

Estado: ISO pública candidata gerada e estruturalmente verificada; homologação prática pendente. Ver [caminho, tamanho e SHA-256](iso-publica-candidata-concluida.md). Usar somente laboratório descartável até concluir BIOS e UEFI. Nenhuma instalação foi executada nesta rodada.

## Preparar o laboratório

No Windows VMware Workstation, usar a ISO principal indicada em [roteiro prático](fase4b9-validacao-pratica.md), conferir tamanho e SHA-256 após transferência. Criar duas VMs independentes (BIOS e UEFI), com 4 GiB RAM, duas CPUs e disco virtual novo de 40 GiB cada. Executar uma VM por vez. Não anexar discos físicos ou o disco da VM Ubuntu Server. Secure Boot permanece fora do escopo inicial.

Antes de iniciar, registrar nome da VM, firmware e caminho do disco virtual. Não alterar firmware durante o ensaio. Interromper se checksum, firmware ou destino não coincidirem.

## Live, instalação e primeiro login

1. Inicializar pela ISO e registrar a tela de boot, firmware e ausência de erros críticos.
2. Abrir sessão Live. Testar XFCE, pt-BR, caracteres ABNT2 (ç, acentos e símbolos), fuso America/Sao_Paulo, conexão e aplicativos. Registrar valores observados, não apenas a configuração solicitada.
3. Abrir o instalador original. Selecionar português brasileiro, teclado brasileiro ABNT2 e fuso São Paulo. Quando pedir destino, confirmar que é exclusivamente o disco virtual descartável da VM de teste. Criar usuário de teste sem credenciais pessoais.
4. Finalizar, desligar, remover a ISO e reiniciar pelo disco. Confirmar login XFCE, idioma, teclado, horário, rede, escritório e ferramentas de desenvolvimento.
5. Reiniciar novamente e conferir persistência. Testar serviços somente no guest: permanecer desativados no boot; ações explícitas do Control devem exigir autenticação administrativa. Confirmar Apache/PHP, MariaDB e Docker Compose conforme checklist; não expor portas no host.
6. Repetir em outra VM com o segundo firmware. Guardar screenshots, logs e resultados com hashes. Qualquer falha deixa o critério pendente/reprovado.

## Coleta auxiliar dentro do guest

Copiar apenas scripts/coletar-evidencias-guest.py para a VM; conferir seu SHA-256 contra collector_sha256 de [final-release-plan.json](../config/final-release-plan.json). Executar como usuário comum DevLite, nunca no Ubuntu Server:

```sh
python3 coletar-evidencias-guest.py --context live --firmware bios --run-version-checks --output "$HOME/bios-live.json"
```

Depois de instalado, usar --context installed e arquivo bios-installed.json. Na outra VM, --firmware uefi, com arquivos uefi-live.json e uefi-installed.json. Os arquivos de saída devem ser novos. A opção --run-version-checks executa apenas consultas de versões no guest; não instala programas.

O coletor rejeita contexto/firmware/identidade inesperados. Ele não testa visualmente teclado, instalador, login ou aplicativos e não declara aprovação prática. Guardar JSON e SHA-256 gerados; revisar resultados manualmente.

## Aceitação pública

A ISO experimental histórica não contém Node.js/TypeScript nem o novo overlay. A candidata pública já foi gerada com essas integrações. Realizar todos os ensaios com o hash da candidata, usando `work/public-iso-1gj6j0xt/acceptance-public.json`; os resultados reais continuam pendentes.

Usar [modelo público](../config/acceptance-public-template.json), mantendo o modelo histórico intacto. Preencher evidências de todos os 148 critérios, inclusive Node/TypeScript, personalização, autenticação Control e licenças. VS Code oficial é opcional após instalação; a ISO pública contém apenas acesso às instruções oficiais.

O validador scripts/validar-aceitacao-publica.py exige --report, --iso-sha256 e --evidence-root. No modelo atual ele deve falhar, pois todos os ensaios permanecem pendentes. Completude documental não substitui revisão e execução reais.

Não utilizar ainda esta documentação como autorização para instalar em máquina física ou apagar discos.
