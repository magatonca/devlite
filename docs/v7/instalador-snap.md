# Construção e homologação do Snap DevLite

> Para a rota pessoal autorizada em 26/11/2026, consulte [Instalador local](instalador-local.md). Este documento mantém a rota Store.
## Builder no Hyper-V

Use uma VM descartável Ubuntu 22.04 amd64 com 1 vCPU, 4 GiB de RAM, swap e pelo menos 20 GiB livres no disco de trabalho. Reserve 10 GiB para o término do build. Use uma VM separada para o ensaio de instalação, com disco de sistema e disco de teste descartável. Uma sessão Ubuntu ou Xubuntu 24.04 amd64 com AppArmor ativo é representativa para o ensaio do Snap e de seu daemon.

O servidor de desenvolvimento tem 1 vCPU, 3,8 GiB de RAM e swap de 3,8 GiB. A árvore PRoot foi suficiente para o frontend. Para empacotar core22, o Snapcraft precisa de privilégios administrativos no ambiente de construção para resolver APT, instalar componentes e configurar o staging. Execute o modo direto **somente dentro da VM Jammy**, com os comandos abaixo. [Ambientes de build do Snapcraft](https://documentation.ubuntu.com/snapcraft/8.14/reference/build-environment-options/)

Copie integralmente `work/v7-frontend-yhYqEZv8/snapcraft-devlite` para `$HOME/snapcraft-devlite` na VM. O manifesto é relativo a esse diretório. Use uma cópia de trabalho por tentativa. Copie também `v7/installer/automount-fail-closed.patch` para `$HOME/automount-fail-closed.patch`. O patch impede que o frontend abra se a inibição do automount falhar. 

```bash
set -euo pipefail
umask 022
cd "$HOME/snapcraft-devlite"
sha256sum -c --quiet SHA256SUMS
test "$(dpkg --print-architecture)" = amd64
. /etc/os-release
test "$ID:$VERSION_ID" = ubuntu:22.04
test "$(df -B1 --output=avail . | tail -n1)" -ge 21474836480

sudo snap install snapcraft --classic --channel=8.x/stable
out=$(mktemp -d "$HOME/devlite-snap-XXXXXXXX")
cp "$HOME/automount-fail-closed.patch" "$out/"
patch --batch --forward -p0 < "$out/automount-fail-closed.patch"
bash -n snap/local/launcher
find payload snap -type f -perm /022 -exec chmod go-w -- {} +
sha256sum snap/local/launcher "$out/automount-fail-closed.patch" > "$out/launcher-build-inputs.sha256"
snapcraft --version > "$out/builder.txt"
sudo env SNAPCRAFT_BUILD_INFO=1 /snap/bin/snapcraft pack --destructive-mode \
  --output "$out/devlite-installer_1.0-v7_amd64.snap" 2>&1 | tee "$out/build.log"
(cd "$out" && sha256sum devlite-installer_1.0-v7_amd64.snap > SHA256SUMS)
```

Retenha a saída, o log, a versão do Snapcraft e o manifesto de build. Durante a execução, monitore o mesmo volume em outro terminal com `watch -n 5 "df -h '$HOME/snapcraft-devlite' '$HOME' /var"`. Interrompa a tentativa antes que o volume se aproxime de 10 GiB livres. Se /var estiver em volume separado, aplique a mesma reserva a ele e assegure o orçamento antes de começar.

No projeto DevLite, execute `/usr/bin/python3 -B -m v7.installer.inspect_snap /caminho/devlite-installer_1.0-v7_amd64.snap > snap-inspection.json`. Compare as versões e commits do manifesto Snapcraft com `v7/installer/inputs.json` e confira as bibliotecas fornecidas no Snap ou no core22. O inspetor lê metadados e ELF sem montar ou executar o pacote. O SHA-256 local documenta o artefato de build.

## Registro e revisão classic

1. O titular entra em sua conta Ubuntu One no painel Snapcraft, executa `snapcraft login` e `snapcraft register devlite-installer`. Confirme que o nome está disponível. [Registro](https://documentation.ubuntu.com/core/explanation/stores/store-overview/)
2. Com autorização para enviar a revisão, execute `snapcraft upload /caminho/devlite-installer_1.0-v7_amd64.snap`. Guarde o número de revisão e o URL da receita revisada. O envio sem `--release` submete o arquivo para revisão sem promover a revisão a um canal. Combine com o revisor como disponibilizar a revisão para o grupo autorizado de homologação. [Publicação Snapcraft](https://snapcraft.io/docs/releasing-your-app/)
3. Envie o texto abaixo no fórum. Antes do envio, preencha os campos entre colchetes e insira resultados que tenham sido executados. A aprovação classic é vinculada ao snap-id novo. [Modelo oficial](https://forum.snapcraft.io/t/about-the-classic-confinement-category/43830) · [Processo de revisão](https://snapcraft.io/docs/reference/administration/reviewing-classic-confinement-snaps/)

### Texto para o fórum

**Title: Classic confinement request for devlite-installer**

Hello Snap Store reviewers,

I am requesting classic confinement for **devlite-installer**, the DevLite OS 1.0 desktop operating system installer for amd64. It is intended for the DevLite Live installation session on a classic Ubuntu-derived system. The snap uses core22.

- Snap name: devlite-installer
- Publisher and snap-id: [publisher account and registered snap-id]
- Submitted revision: [revision number]
- Snapcraft recipe and build provenance: [reviewable recipe and pinned-input manifest URLs]
- Upstream: https://github.com/canonical/ubuntu-desktop-provision and https://github.com/canonical/subiquity
- Upstream relationship: DevLite is an independent downstream project. It builds a branded Flutter frontend from the pinned Canonical Ubuntu Desktop Provision source revision. The recipe uses the corresponding pinned Subiquity source and the Curtin revision from the upstream Ubuntu Desktop Bootstrap recipe. DevLite's package has a separate Store identity and publisher. The Canonical snap remains available as a recovery reference.
- Supported category: [category confirmed with the reviewers, or request guidance on the appropriate category]

The desktop frontend connects to the local Subiquity daemon through a Unix socket. The backend performs a user-authorized operating system installation on a selected disk. Subiquity and Curtin need to discover and prepare block devices, partition and format the selected disk, mount target filesystems, run installation steps in the target root, and configure the appropriate bootloader. The launcher coordinates the host systemd automount inhibitor for the duration of the installer. This is a system installation workflow that spans the live system and a newly constructed target filesystem.

We understand that strict confinement is preferred. The intended use of classic confinement follows the upstream desktop installer architecture. We would appreciate guidance on a supported strict interface combination or a narrower design applicable to this workflow. Strict interface evaluation and results: [list the interfaces actually evaluated, the scope of testing and the specific denials or limitations observed]. We will provide evidence from the disposable VM and our build and dependency manifests on request.

For the DevLite Live integration we restrict traversal of the local backend socket directory to root and the administrative group, preserve upstream confirmations for storage operations, and verify startup and cleanup of the automount inhibitor. The candidate is gated on signature verification, the pinned build and the installer integration tests. We understand the trust implications of classic confinement and will maintain the downstream package and its security updates.

Thank you for reviewing the request.

## Obter e validar a revisão após aprovação

Obtenha do editor a revisão amd64 autorizada. Baixe a revisão exata e as assertions em um diretório novo. Se o revisor usar um mecanismo de distribuição restrito, use o acesso autorizado por ele.

```bash
rev=NUMERO_DA_REVISAO
download=$(mktemp -d "$HOME/devlite-asserted-XXXXXXXX")
snap download devlite-installer --revision="$rev" --target-directory="$download"
(cd "$download" && sha256sum "devlite-installer_${rev}.snap" > SHA256SUMS)
```

Revise o snap-id, o nome e os registros snap-declaration e snap-revision. Na VM de ensaio, use o snapd ativo para validar a cadeia e a correspondência do arquivo com a revisão. Guarde o SHA-256 do arquivo obtido.

```bash
sudo snap ack "$download/devlite-installer_${rev}.assert"
sudo snap install --classic "$download/devlite-installer_${rev}.snap"
snap list devlite-installer
snap known snap-revision "snap-revision=$rev"
```

Monte o seed Live com a revisão aprovada, core22 e o conjunto Firefox verificado. Execute `snap debug validate-seed /caminho/live-seed/seed.yaml`. Preserve as assertions, os hashes e o recibo de revisão. O gate da v7 exige snap-id e SHA-256, seed aceito pelo snapd, digest do worker revisado e verificações técnicas concluídas. [Conteúdo e modos de instalação de Snaps](https://snapcraft.io/docs/explanation/snap-development/install-modes/)

## Ensaio Hyper-V anterior à ISO

- Tire um checkpoint da VM de ensaio. Instale a revisão autenticada e aplique **na VM** o drop-in de socket que consta em `v7/live_installer.py`. Confira a disponibilidade da unidade `udisks2-inhibit.service` herdada da sessão Live. Compare-a com a referência v6 se a instalação limpa da VM tiver uma unidade diferente.
- Execute `sudo systemctl daemon-reload` e `sudo systemctl restart snap.devlite-installer.subiquity-server.service`. Confira `stat -c '%a %U:%G %n' /run/subiquity /run/subiquity/socket`. O diretório deve mostrar `750 root:sudo`. Na sessão administrativa de teste, abra `snap run devlite-installer` como usuário da sessão e confirme que o frontend consulta o estado e recebe o inventário de armazenamento. Confirme que um usuário sem acesso administrativo recebe erro ao tentar conectar ao mesmo socket.
- Antes de abrir a interface, verifique se o inibidor está inativo. Durante a interface, verifique `systemctl is-active udisks2-inhibit.service` e anexe somente uma mídia de teste. Confirme ausência de automount. Feche a interface normalmente, cancele uma instalação de teste, repita com encerramento por sinal e confira a liberação da inibição. Bloqueie a aprovação se a interface conseguir prosseguir quando a unidade de inibição falhar.
- Pare o daemon e confirme que o frontend relata indisponibilidade. Reinicie e confira a reconexão ou recuperação controlada. Use somente discos descartáveis para particionamento manual, guiado e autoinstall. Confirme a identidade em todas as telas, os logs Subiquity/Curtin e o resultado do boot do disco de teste. Use VM geração 2 para UEFI e geração 1 para BIOS quando aplicável.
- Guarde `journalctl -u snap.devlite-installer.subiquity-server.service -u udisks2-inhibit.service`, o estado das units, a autorização positiva e negativa e os logs do instalador. Remova dados pessoais e credenciais dos logs antes de compartilhar. Faça rollback do checkpoint entre cenários. A futura candidata ainda passa pela homologação completa do Live e do sistema instalado.
