# DevLite OS 1.0.1

O pacote `devlite-update` destina-se ao DevLite OS 1.0 amd64 já instalado. Ele entrega DevControl 3.1, padrões do XFCE, editor Mousepad via dependência Ubuntu e identificação do GRUB. A sessão precisa ser encerrada e iniciada novamente para carregar os novos padrões XDG. Os perfis pessoais têm precedência. Ubuntu APT, Snap e os aplicativos existentes mantêm seus fluxos próprios.

## Repositório e referência instalada

O remoto `origin` é [magatonca/devlite](https://github.com/magatonca/devlite). A API anônima do GitHub confirmou visibilidade pública. O DevControl usa esse repositório para consultar releases estáveis e baixar seus anexos, sem credenciais no notebook. A chave de lançamento autentica o pacote independentemente do acesso ao GitHub. Caso o repositório se torne privado, o fluxo automático público fica indisponível. Nesse cenário, obtenha os três anexos de forma autenticada em uma estação de confiança, via GitHub CLI com login interativo e credencial no chaveiro, e aplique o procedimento de validação local. Nenhuma credencial deve ser transferida para o processo privilegiado do atualizador.

A referência local `v1.0.0` aponta para `a6e39cca471e9b92c7604a1c335742261b8f102c`, o primeiro commit da v7. Os 174 arquivos do snapshot de código conferem byte a byte com esse commit e também com seu sucessor `e1572de`. O fingerprint do manifesto, `6b7d981a0d302ea0bd19cbd11389ffbff1a659d71f6197f0584c8eb14eaca72f`, confere com o relatório da ISO instalada. O código da atualização 1.0.1 fica em um commit posterior, usando o mesmo histórico.

## Gerar, assinar e publicar

Para obter apenas o DEB e o checksum em uma saída nova, execute `python3 -B maintenance/update/build.py DIRETORIO` na raiz do projeto. Para preparar uma release assinada, revise e registre o código em um commit, deixando a cópia limpa. Confira `VERSION` e `CHANGELOG.md`.

Use uma chave de lançamento OpenPGP protegida, mantida fora do Git. Na estação de assinatura, em terminal interativo:

```sh
export GNUPGHOME="$HOME/.local/share/devlite-signing"
install -d -m 0700 "$GNUPGHOME"
export GPG_TTY="$(tty)"
gpg --quick-generate-key 'DevLite OS Release <magatonca@users.noreply.github.com>' ed25519 sign 2y
gpg --list-secret-keys --fingerprint
```

Escolha uma frase secreta forte no diálogo do GnuPG e guarde-a no gerenciador de senhas. Execute a geração uma vez. Informe a impressão digital completa da chave existente nas próximas assinaturas.

```sh
export RELEASE_FPR='IMPRESSAO_DIGITAL_COMPLETA'
maintenance/update/release.sh prepare artifacts/devlite-update-v1.0.1-assinado
```

O diretório deve ser novo. O script gera o DEB, `SHA256SUMS`, `SHA256SUMS.sig`, a chave pública exportada e o identificador do commit. Ele confirma que o pacote contém somente a chave pública e que ela coincide com a exportação. O notebook usa o chaveiro do pacote. Em uma rotação de emergência, o administrador pode provisionar um chaveiro atualizado em `/etc/devlite-update.gpg` após autenticar sua impressão digital por canal independente.

### Backup e revogação

Monte um volume removível cifrado e substitua o caminho abaixo pelo diretório nele reservado. Mantenha uma segunda cópia separada e guarde a frase secreta fora dos volumes. O certificado pode revogar a chave e também precisa ficar offline.

```sh
(
set -eu
umask 077
destino=/caminho/do/volume-cifrado/devlite-signing
install -d -m 0700 "$destino"
test ! -e "$destino/$RELEASE_FPR.secret.gpg"
gpg --output "$destino/$RELEASE_FPR.secret.gpg" --export-secret-keys "$RELEASE_FPR"
test -s "$destino/$RELEASE_FPR.secret.gpg"
install -m 0600 "$GNUPGHOME/openpgp-revocs.d/$RELEASE_FPR.rev" "$destino/$RELEASE_FPR.rev"
)
```

Teste o backup em um chaveiro temporário no volume cifrado, importando a chave privada e assinando um arquivo de teste. Verifique a assinatura com a chave pública conhecida. Preserve o certificado como foi gerado. Em caso de perda ou comprometimento, siga as instruções do próprio certificado para importar a revogação e comunicar a nova chave. Nunca publique a chave privada ou os arquivos de backup.

Após autorização explícita para publicar, confirme o commit e use a CLI do GitHub com `gh auth login --web` e armazenamento seguro das credenciais. Crie a tag local da atualização caso ainda não exista, envie o commit e a tag sem forçar e publique os três anexos:

```sh
git tag -a v1.0.1 -m 'DevLite OS 1.0.1'
git push origin main
git push origin refs/tags/v1.0.1
maintenance/update/release.sh publish artifacts/devlite-update-v1.0.1-assinado
```

O modo `publish` exige a tag remota já existente e correspondente à tag local, revalida assinatura, checksum e metadados e usa `gh release create --verify-tag`. A publicação da tag histórica `v1.0.0`, se desejada, exige autorização separada. [GitHub Releases](https://cli.github.com/manual/gh_release_create)

## Primeira instalação no notebook

Copie os quatro arquivos produzidos para uma pasta no notebook. No exemplo, defina `servidor` como o endereço SSH do servidor de construção.

```sh
servidor='magaton@ENDERECO_DO_SERVIDOR'
origem="$servidor:/home/magaton/DevLite-OS/artifacts/devlite-update-v1.0.1-assinado"
mkdir -p "$HOME/devlite-1.0.1"
cd "$HOME/devlite-1.0.1"
scp "$origem/devlite-update_1.0.1_amd64.deb" "$origem/SHA256SUMS" \
    "$origem/SHA256SUMS.sig" "$origem/devlite-update.gpg" .
```

Confirme que a impressão digital corresponde à conhecida antes da instalação. Os comandos abaixo interrompem a sequência se a assinatura ou o SHA-256 falhar. A instalação de dependências usa os repositórios Ubuntu já configurados.

```sh
(
set -eu
gpg --show-keys --fingerprint devlite-update.gpg
printf 'Digite a impressão digital OpenPGP obtida do mantenedor por canal independente: '
IFS= read -r esperada
case "$esperada" in ''|*[!0-9A-F]*) exit 1 ;; esac
sudo install -d -o root -g root -m 0755 /var/lib/devlite-update
sudo install -d -o root -g root -m 0700 /var/lib/devlite-update/releases
staging=$(sudo mktemp -d /var/lib/devlite-update/releases/instalacao.XXXXXXXX)
sudo install -o root -g root -m 0600 devlite-update.gpg SHA256SUMS SHA256SUMS.sig \
    devlite-update_1.0.1_amd64.deb "$staging/"
observada=$(sudo gpg --homedir "$staging" --batch --no-options --with-colons --show-keys "$staging/devlite-update.gpg" |
    awk -F: '$1=="pub"{pub++; primary=1} $1=="fpr" && primary{print $10; primary=0} END{if(pub!=1)exit 1}')
test "${#esperada}" -eq 40
test "$observada" = "$esperada"
sudo gpgv --keyring "$staging/devlite-update.gpg" "$staging/SHA256SUMS.sig" "$staging/SHA256SUMS"
sudo grep -xEq '^[0-9a-f]{64}  devlite-update_1[.]0[.]1_amd64[.]deb$' "$staging/SHA256SUMS"
test "$(sudo cat "$staging/SHA256SUMS" | wc -l)" -eq 1
sudo sh -c 'cd "$1" && sha256sum -c SHA256SUMS' sh "$staging"
deb="$staging/devlite-update_1.0.1_amd64.deb"
test "$(sudo dpkg-deb -f "$deb" Package)" = devlite-update
test "$(sudo dpkg-deb -f "$deb" Version)" = 1.0.1
test "$(sudo dpkg-deb -f "$deb" Architecture)" = amd64
sudo mkdir "$staging/verificado"
sudo dpkg-deb -x "$deb" "$staging/verificado"
sudo cmp "$staging/devlite-update.gpg" "$staging/verificado/usr/share/keyrings/devlite-update.gpg"
sudo apt-get update
sudo apt-get install "$deb"
sudo test ! -e /var/lib/devlite-update/releases/v1.0.1
sudo mv -T "$staging" /var/lib/devlite-update/releases/v1.0.1
sudo touch /var/lib/devlite-update/releases/v1.0.1/installed
)
```

A primeira instalação fica registrada em `/var/log/dpkg.log`. Para alterar o editor da sua conta caso ela já tenha uma associação própria, execute `xdg-mime default org.xfce.mousepad.desktop text/plain` como usuário comum.

## Próximas atualizações e recuperação

Cada versão deve conter todos os arquivos necessários do `devlite-update`, inclusive as correções anteriores. O DevControl compara apenas a versão instalada com a última release estável e instala diretamente o DEB mais recente. Mantenha os scripts de migração compatíveis com todas as versões ainda suportadas, inclusive saltos de versão. Teste cada release a partir da versão suportada mais antiga. A atualização atual mantém as dependências iniciais atendidas pelo Ubuntu e não altera diretórios pessoais, dados MariaDB ou projetos.

No DevControl abra **Atualizações → Consultar → Baixar e verificar → Instalar**. O download em sessão comum valida a assinatura e o hash. Após autenticação no Polkit, o instalador obtém uma cópia em diretório privado, valida novamente e exige o mesmo SHA-256 antes de passar o DEB ao dpkg. A instalação segue a fila do dpkg e conserva conffiles locais em caso de divergência. A aba **Histórico** mostra os últimos resultados registrados pelo instalador em `/var/lib/devlite-update/history.jsonl`.

**Restaurar versão anterior** pede autenticação e reinstala somente um DEB anterior instalado com sucesso e armazenado em cache. A recuperação revalida sua assinatura e seu checksum. Se a atualização impedir a abertura do DevControl, execute no terminal:

```sh
sudo /usr/lib/devlite-update/updater.py restore
```

Para voltar ao DevControl e aos padrões originais da ISO 1.0, encerre a sessão depois de remover o pacote com `sudo apt-get purge devlite-update`. A recuperação cobre os arquivos administrados pelo pacote. Dados pessoais e dependências do Ubuntu são independentes.
