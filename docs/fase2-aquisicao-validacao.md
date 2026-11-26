# Fase 2 — aquisição, autenticidade e estrutura

Concluída em 16/11/2026. Operações executadas como `magaton`, sem instalação de pacotes, montagem, chroot, particionamento ou build. A única operação privilegiada foi a correção de propriedade dos arquivos da Fase 1, explicitamente autorizada, excluindo `.git`. Nenhum commit foi criado. O commit de referência é `fd6c719`.

## Aquisição e autenticação

| Item | Resultado |
|---|---|
| ISO | `xubuntu-24.04.5-minimal-amd64.iso` |
| Tamanho | 3.193.516.032 bytes; aproximadamente 3,19 GB ou 2,97 GiB |
| Origem | [Diretório oficial Ubuntu CD Image](https://cdimage.ubuntu.com/xubuntu/releases/24.04/release/) |
| SHA-256 | `9d47f975696ce496b8be882b6d7cc9079c1ea89fb625ac2c86caa63a4f180033` |
| Assinatura | GPG retornou sucesso, GOODSIG e VALIDSIG para SHA256SUMS |
| Signatário | Ubuntu CD Image Automatic Signing Key (2012), cdimage@ubuntu.com |
| Impressão digital | `8439 38DF 228D 22F7 B374 2BC0 D94A A3F0 EFE2 1092` |
| Data da assinatura | 10/09/2026, 17:13:08 UTC (14:13:08 em São Paulo) |
| Integridade após inspeção | SHA-256 integral novamente conferido; original intacta |

ISO, `SHA256SUMS` e `SHA256SUMS.gpg` vieram do mesmo diretório oficial por HTTPS. A chave foi obtida de `https://keyserver.ubuntu.com/pks/lookup?op=get&search=0x843938DF228D22F7B3742BC0D94AA3F0EFE21092`, importada em chaveiro dedicado em `sources/verification/`. A impressão digital completa foi comparada com o [tutorial oficial de verificação Ubuntu](https://ubuntu.com/tutorials/how-to-verify-ubuntu#4-retrieve-the-correct-signature-key), fonte independente do diretório das imagens.

O aviso GPG de confiança desconhecida indica ausência de certificação pessoal no chaveiro; a identidade foi validada pela impressão digital oficial, sem atribuir confiança artificial. O download usou extensão `.part`; a renomeação para `.iso` ocorreu somente após SHA-256 válido. Não houve falha de autenticidade ou integridade.

ISO e metadados permanecem em `sources/`, ignorados pelo Git. Logs locais estão em `reports/phase2/`. Um resumo pequeno e versionável está em [evidencias/iso-oficial.json](evidencias/iso-oficial.json).

## Estrutura real

| Arquivo | Bytes na ISO | Função observada |
|---|---:|---|
| `/casper/minimal.squashfs` | 685.113.344 | Base selecionada pelo catálogo de instalação |
| `/casper/minimal.live.squashfs` | 1.301.176.320 | Camada live, com Casper, ferramentas e instalador |

Ambas são SquashFS 4.0 com compressão xz, blocos de 131.072 bytes, xattrs e IDs Unix. Valores de superbloco são ligeiramente menores que os arquivos por causa do padding. Existem ainda kernel `vmlinuz`, `initrd`, manifests, arquivos `.size` e checksums assinados internos em `/casper`. A assinatura interna também foi validada por gpgv, e `sha256sum -c` confirmou as duas cópias SquashFS (relatórios `casper-gpg.txt` e `casper-sha256.txt`).

`install-sources.yaml` tem uma fonte padrão: ID `xubuntu-desktop-minimal`, tipo `fsimage-layered`, caminho `minimal.squashfs`, tamanho declarado 2.382.868.480 bytes, variante `desktop` e suporte de locale `langpack`. Esse tamanho é metadado da fonte expandida, não o tamanho comprimido. `minimal.live.size` declara 2.072.498.176 bytes e `filesystem.size` declara 4.455.366.656 bytes.

O GRUB não passa `layerfs-path` na linha do kernel. A cópia extraída do initrd contém `conf/conf.d/default-layer.conf` com `LAYERFS_PATH=minimal.live.squashfs`. O código `scripts/casper`, em `setup_overlay`, deriva os ancestrais pelo nome: base `minimal` e folha `minimal.live`, com a folha sobreposta à base. `default-boot-to-casper.conf` também define BOOT=casper. Essa constatação vem da leitura dos arquivos; nenhum deles foi executado.

`filesystem.manifest` é uma lista completa; `minimal.manifest` e `minimal.live.manifest` são deltas textuais com cabeçalhos e linhas de adição/remoção. Não tratá-los como simples listas de pacotes. A camada live possui sua própria `/var/lib/dpkg/status`, que sobrepõe a da base, além de estado e sementes snap.

## Instalador

O manifest geral registra `snap:ubuntu-desktop-bootstrap`, canal `24.04/stable/ubuntu-24.04`, revisão 572. A camada live contém o snap de 118.587.392 bytes em `var/lib/snapd/snaps` e `var/lib/snapd/seed/snaps`, configurações em `/etc/subiquity` e o serviço `snap.ubuntu-desktop-bootstrap.subiquity-server.service`. Isso identifica Ubuntu Desktop Bootstrap com backend Subiquity; não é um pipeline a ser projetado supondo Ubiquity.

Não iniciar o snap nem o serviço no host. A configuração efetiva e o comportamento de instalação só serão comprovados em VM na Fase 3. Referência: [catálogo de fontes do instalador](https://canonical-subiquity.readthedocs-hosted.com/en/latest/reference/autoinstall-reference.html#source).

## Boot BIOS e UEFI

- Volume: `Xubuntu 24.04.5 LTS amd64`; catálogo `/boot.catalog`.
- BIOS: imagem El Torito `/boot/grub/i386-pc/eltorito.img`, boot-info-table e grub2-boot-info.
- UEFI: imagem EFI oculta no namespace ISO, anexada como partição GPT número 2, início no setor de 512 bytes 6.226.512, extensão de 10.160 setores (5.201.920 bytes). O El Torito referencia LBA 1.556.628 em blocos de 2048 bytes.
- Área de sistema: GRUB2 MBR, MBR protetor e GPT; offset de partição 16.
- Árvore visível também contém `/EFI/boot/bootx64.efi`, `grubx64.efi` e `mmx64.efi`.

`reports/phase2/boot.txt` registra a estrutura; `boot-replay.txt` registra os parâmetros sugeridos por `xorriso -report_el_torito as_mkisofs`. Esse relatório é referência para revisão, não um script executado. Copiar apenas os arquivos visíveis em `/EFI` não preserva a partição EFI anexada. Boot estrutural BIOS/UEFI confirmado; inicialização em VMware e Secure Boot ainda não testados.

## Reprodução e evidências

Ver [tests/README.md](../tests/README.md). `scripts/validar-iso.py` revalida assinatura, signatário e hash offline. `scripts/inspecionar-iso.py` valida antes de extrair, usa `xorriso -indev` sem saída ISO e lê superblocos/listagens com unsquashfs; confere novamente o hash original ao terminar. Cópias em `work/phase2` não são destinadas a construção.

O initrd foi inventariado por `lsinitramfs` e extraído por `unmkinitramfs`, ferramentas já instaladas, apenas para leitura da configuração. Os cinco testes automatizados verificam rejeições de metadados e conteúdo adulterados. Testes de boot e instalação continuam pendentes.
