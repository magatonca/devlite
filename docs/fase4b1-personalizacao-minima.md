# Fase 4B.1 — primeira personalização mínima

Estado em 16/11/2026: **ISO experimental gerada e validada estruturalmente**. Os três comandos root foram autorizados e concluídos; a montagem e auditoria foram executadas como magaton. A fonte oficial e a reconstrução 3B permanecem intactas. Nenhum pacote foi instalado, nenhum repositório adicionado e nenhum filesystem montado. Não houve chroot ou commit.

Resultado: `artifacts/phase4b1-lgpa3zc7/devlite-os-1.0-basic-experimental.iso`, 3.193.896.960 bytes (aproximadamente 2,975 GiB). SHA-256:

```text
79e8d7e9ed87d1855a574977b409c55f07213daa22b50271b6e85bdb7cbf00b5
```

Há 48.388.116.480 bytes livres após o build (aproximadamente 45,1 GiB). Evidência resumida: [personalizacao-minima.json](evidencias/personalizacao-minima.json). Relatório detalhado e SHA256SUMS acompanham a ISO em artifacts; logs em `work/phase4b1-dhzezpnz/assembly-logs-zyj3o1in`. Boot, instalação e persistência pós-instalação não foram testados.


## Configurações e escopo

O conjunto preparado contém 21 payloads: configurações de idioma, teclado, timezone e identidade, mais os arquivos binários do locale pt_BR.utf8 já compilados no projeto. Não inclui os presets MariaDB, serviços ou tema da 4A.

- LANG=pt_BR.UTF-8 e LANGUAGE=pt_BR:pt em /etc/locale.conf, preservando /etc/default/locale como symlink original.
- pt_BR.UTF-8 habilitado em locale.gen sem apagar outras entradas.
- Locales compilados em /usr/lib/locale/pt_BR.utf8 usando somente as definições/charmap da imagem. O localedef já presente no host tem a mesma versão principal/secundária da glibc alvo; a geração usa --no-archive e destino absoluto no workspace. Não altera o locale do host.
- Teclado br, modelo abnt2; timezone America/Sao_Paulo com symlink /etc/localtime.
- Identidade em /etc/devlite-release e /usr/share/devlite-os/identity.json; NAME/PRETTY_NAME em /usr/lib/os-release e descrição lsb-release. ID=ubuntu, VERSION_ID e codename Noble são preservados para compatibilidade; /etc/os-release mantém seu link.
- Argumentos de locale/modelo/layout são adicionados às entradas normais e safe graphics do GRUB e loopback. As demais opções serão preservadas.

O idioma gráfico depende das traduções já presentes. Foram identificados catálogos pt_BR do XFCE na base; não serão adicionados language packs. Isso não equivale a comprovar tradução completa da interface ou comportamento do instalador.

## Arquivos implementados

| Arquivo | Papel |
|---|---|
| scripts/personalizar-minima.py | preflight, preparação não privilegiada e montagem/validação após as etapas root |
| pipeline/devlite/minimal_config.py | seleção mínima da 4A, charmap/localedef isolados e payloads com SHA-256 |
| scripts/camadas-minimas-root.py | entrada explícita do auxiliar root; não usa sudo automaticamente |
| pipeline/devlite/minimal_root.py | extração com metadados, aplicação confinada, reconciliação, compressão e comparação integral |
| pipeline/devlite/minimal_build.py | checksums, tamanhos, catálogo, GRUB, boot replay, auditoria ISO e promoção da saída |
| tests/test_minimal_customization.py | testes dos limites de paths, payloads, metadados e integridade |
| tests/acceptance_minimal_image.py | cinco testes estáticos sobre as camadas extraídas da ISO final |
| docs/evidencias/personalizacao-minima.json | resumo verificável da execução e resultados |

O pipeline 3B não foi enfraquecido. A estratégia mínima usa módulos separados e uma allowlist própria; qualquer alteração fora dela é falha.

## Investigação rootless e escolha

A fixture pequena com pseudo-arquivos preservou UID/GID, permissões, timestamps, xattrs user.*, symlink e hardlink. Contudo, `unsquashfs -pf` 4.6.1 abortou com buffer overflow na camada real ao serializar security.capability de mtr-packet. A tentativa e logs estão preservados em `work/phase4b1-dhzezpnz/logs`; a exportação parcial não é usada para reconstruir.

`pipeline/devlite/pseudo.py` permanece como experimento não utilizado pelo caminho de construção. Não descartar capabilities/xattrs, usar -all-root, desativar erros ou executar pseudo-definições dinâmicas para contornar a falha. A reconstrução real usou extração convencional estrita e comparação de todos os metadados. Referência da capacidade pseudo: [SquashFS 4.6.1](https://raw.githubusercontent.com/plougher/squashfs-tools/4.6.1/README-4.6.1).

## Comandos root autorizados e concluídos

Workspace específico: `/home/magaton/DevLite-OS/work/phase4b1-dhzezpnz`. A preparação não privilegiada, incluindo locale e payloads, já foi executada. Os três comandos abaixo foram apresentados, autorizados explicitamente e executados com sucesso. Uma nova execução em outro workspace exige nova autorização. No terminal magaton, prefixar com sudo; o executor do agente já inicia como root, portanto não precisa de sudo redundante.

```sh
/usr/bin/python3 /home/magaton/DevLite-OS/scripts/camadas-minimas-root.py --workspace /home/magaton/DevLite-OS/work/phase4b1-dhzezpnz extract
/usr/bin/python3 /home/magaton/DevLite-OS/scripts/camadas-minimas-root.py --workspace /home/magaton/DevLite-OS/work/phase4b1-dhzezpnz apply
/usr/bin/python3 /home/magaton/DevLite-OS/scripts/camadas-minimas-root.py --workspace /home/magaton/DevLite-OS/work/phase4b1-dhzezpnz pack
```

- extract: verifica SHA-256 fixado das duas camadas oficiais, extrai em base-root/live-root com erros estritos, preservando UID/GID, modos, devices e xattrs; gera inventários completos de bytes e metadados.
- apply: confere hashes e allowlist dos payloads. Altera apenas as cópias extraídas. O único unlink explícito substitui o symlink /etc/localtime dentro da cópia, nunca um diretório. Preserva xattrs e restaura mtime dos diretórios originais.
- pack: lê arquivos protegidos e atributos privilegiados, comprime com xz, blocos 128 KiB, um processo e cache de 256 MiB. Não usa -all-root. Reextrai ambas as imagens em destinos novos e compara integralmente conteúdo, ownership, modos, timestamps, symlinks, hardlinks, devices e xattrs.

Root é necessário para ler/restaurar arquivos protegidos, capabilities, trusted xattrs e devices. Não é necessário para compilar o locale, construir a árvore externa ISO ou gerar hashes finais; essas etapas são executadas como magaton. Não há modprobe, montagem, chroot, apt, manipulação de discos ou comandos genéricos de limpeza. Todos os caminhos e logs ficam no projeto. Os temporários dos testes desta fase também usam work.

O auxiliar verifica caminho, prefixo, proprietário e marcador do workspace. Rejeita ancestrais symlink e destinos de extração/saída existentes. Não reexecutar sobre destinos parciais sem diagnóstico; não apagar evidências automaticamente. A confirmação autoriza somente as três etapas neste workspace, não um shell root irrestrito ou operações em outro volume.

## Relação base/live

Como não há alteração de pacotes, dpkg/APT e o instalador devem permanecer byte a byte iguais em cada camada. A configuração canônica é aplicada primeiro à base instalada. Para a folha live, cada destino é examinado: se já existe na folha ou algum ancestral é opaco, o payload correspondente é espelhado no upper, sem retirar o atributo opaco. Caso contrário, é herdado da base personalizada. Não copiar o dpkg/status da base sobre o live nem alterar o instalador/snap seeds.

Os inventários completos antes/depois exigem igualdade fora dos destinos de configuração e novos diretórios necessários. A comparação de hardlinks impede romper grupos; alterações de configuração em hardlinks são recusadas. O round-trip de cada SquashFS precisa reproduzir o inventário pós-patch inteiro. A raiz mantém seus metadados originais; não são achatados proprietários para root.

## Montagem e integridade ISO

Como magaton:

```sh
python3 scripts/personalizar-minima.py --assemble /home/magaton/DevLite-OS/work/phase4b1-dhzezpnz
```

O construtor exige os relatórios das três etapas, confere novamente os hashes das SquashFS e usa xorriso nativo com entrada/saída distintas. Atualiza apenas camadas, .size, tamanho da fonte em install-sources.yaml, argumentos de GRUB e checksums. Os tamanhos são medidos no conteúdo reconstruído extraído, incluindo alocação de filesystem e sem contar hardlinks duas vezes; continuam sendo estimativas para o instalador, não medições de uma instalação real.

Manifests de pacotes completos e deltas são preservados: a seleção/versões não mudaram. Uma auditoria de todos os arquivos da ISO valida o conjunto permitido de alterações. GRUB/MBR e EFI anexada são preservados via replay; parâmetros BIOS/UEFI, código MBR e conteúdo EFI são conferidos independentemente. O rótulo da saída é DevLite OS 1.0 Experimental; UUID de volume permanece baseado na data original para não romper referências de boot.

Os checksums personalizados de casper são recalculados. A assinatura Ubuntu não pode autenticar as camadas novas: a dupla SHA256SUMS/SHA256SUMS.gpg original é preservada em /casper/devlite-provenance. Não se mantém assinatura antiga ao lado de checksums modificados. Os checksums novos não são assinados nesta ISO experimental. O md5sum.txt é atualizado e validado; não desabilitar casper-md5check ou inserir fsck.mode=skip. O serviço embarcado usa /cdrom/md5sum.txt; o [controlador upstream Subiquity](https://raw.githubusercontent.com/canonical/subiquity/main/subiquity/server/controllers/integrity.py) consome esse resultado. Isso não substitui testar o instalador embarcado.

A saída permanece .iso.partial até passar nas verificações. O hash da ISO original e da reconstrução 3B é conferido antes de promover a saída. Logs, cópias e tentativas parciais são preservados. Não haverá publicação ou commit automático.

## Testes e estado atual

60 testes automatizados passaram. O charset do locale gerado foi verificado como UTF-8 e os 21 payloads passaram no validador de integridade. As duas camadas foram reconstruídas, reextraídas e comparadas integralmente com os inventários pós-patch: 80.911 caminhos na base e 64.656 na folha live. Conteúdo, modos, UID/GID, timestamps, xattrs, devices e relações de hardlink foram preservados.

A compressão sequencial usou um processador e cache de 256 MiB. Os tamanhos alocados medidos nas árvores reconstruídas são 2.385.051.648 bytes (base) e 2.070.654.976 bytes (live). São estimativas para os metadados do instalador. A preparação exige 40 GiB livres e preserva áreas de trabalho e tentativas anteriores; não usa tmpfs para rootfs.

A auditoria da ISO passou: 193 entradas MD5, duas entradas SHA-256 de camadas, assinatura GPG da proveniência original, comparação de árvores e metadados, replay BIOS/UEFI, MBR e imagem EFI anexada. Quatro entradas GRUB foram atualizadas. Os hashes da ISO oficial e da reconstrução 3B permaneceram iguais. Os cinco testes de aceitação da imagem passaram (65 testes aprovados no total: 60 da suíte e cinco da imagem real). Boot, instalação e persistência pós-instalação permanecem sem teste real.

## Constatações da execução autorizada

O usuário confirmou os três comandos root. A extração e a aplicação passaram: base com 80.894 caminhos antes e 80.911 após o patch, 24 caminhos autorizados (21 payloads e três diretórios novos). A folha live manteve 64.656 caminhos e não precisou de payloads espelhados.

A folha original contém trusted.overlay.impure, trusted.overlay.uuid e trusted.overlay.origin, além de 12 devices de caracteres. Não foram encontrados atributos de metacopy, redirect ou opacidade, nem ancestrais não diretório para os destinos do patch. Os atributos são preservados, sem exclusão para contornar a validação. No initrd observado, o Casper usa as duas SquashFS como lowerdirs e uma upper COW separada; essa constatação estática não aprova a montagem em um boot real. Referência conceitual: [OverlayFS no kernel](https://docs.kernel.org/filesystems/overlayfs.html).

A suíte atualizada tem 60 testes aprovados, incluindo bloqueio de ancestrais live não diretórios. Os cinco testes adicionais em tests/acceptance_minimal_image.py foram executados após a montagem e passaram. Confirmaram os payloads e o locale na imagem final, idioma/teclado/timezone e links, identidade, estado dpkg das duas camadas e snap do instalador preservado. Relatórios locais: reports/testes-ate-fase4b1.txt e reports/aceitacao-fase4b1.txt.

## Tentativa de montagem preservada

A primeira chamada xorriso parou antes da gravação por ausência de delimitadores `--` nos argumentos de lista. A implementação foi corrigida para delimitar mkdir/mv/chown/chgrp/chmod/alter_date; a suíte de 60 testes passou novamente e a montagem real corrigida passou pela auditoria integral. A tentativa e seu relatório foram preservados, sem sobrescrever a ISO original nem a saída 3B. Cada tentativa usa novos diretórios de atualizações, logs e artefatos.

## Próximos passos

Executar a matriz real BIOS/UEFI em VMs descartáveis, validando live, instalador e reboot sem mídia. Confirmar idioma, teclado, timezone e identidade também após instalação, pois o instalador pode ajustar configurações. Verificar tradução gráfica completa e interação dos atributos OverlayFS no boot real. Somente depois ampliar o escopo para pacotes/identidade visual, com autorizações específicas para rede, dependências ou privilégios. Esta ISO não possui assinatura de release DevLite e não foi publicada. Os rootfs temporários ficam preservados; removê-los exigirá revisão e autorização próprias.
