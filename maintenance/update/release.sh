#!/bin/sh
# Build and sign locally, or publish an already prepared release explicitly.
set -eu
if [ "$#" -ne 2 ]; then
    echo "Uso: RELEASE_FPR=<fingerprint> $0 {prepare|publish} DIRETORIO" >&2
    exit 2
fi
action=$1
case "$action" in prepare|publish) ;; *) exit 2 ;; esac
case "$2" in /*) output=$2 ;; *) output="$PWD/$2" ;; esac
: "${RELEASE_FPR:?Informe a impressão digital da chave OpenPGP de lançamento.}"
case "$RELEASE_FPR" in *[!0-9A-F]*) exit 2 ;; esac
test "${#RELEASE_FPR}" -eq 40

root=$(CDPATH='' cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$root"
project=magatonca/devlite
remote=https://github.com/$project.git
test "$(git remote get-url origin)" = "$remote"
test "$(git remote get-url --push origin)" = "$remote"
if [ -n "$(git status --porcelain)" ]; then
    echo 'Revise e registre as alterações em um commit antes de preparar a release.' >&2
    exit 1
fi
version=$(cat VERSION)
tag="v$version"
package=$(python3 -B -c 'from maintenance.update.updater import package_name; import sys; print(package_name(sys.argv[1]))' "$tag")
revision=$(git rev-parse HEAD)
unset SOURCE_DATE_EPOCH

if [ "$action" = prepare ]; then
    keyring=$(mktemp)
    trap 'rm -f -- "$keyring"' EXIT
    gpg --export "$RELEASE_FPR" > "$keyring"
    test -s "$keyring"
    python3 -B maintenance/update/build.py "$output" --public-key "$keyring"
    gpg --local-user "$RELEASE_FPR" --detach-sign --output "$output/SHA256SUMS.sig" "$output/SHA256SUMS"
    install -m 0644 "$keyring" "$output/devlite-update.gpg"
    printf '%s\n' "$revision" > "$output/source-commit"
fi

test "$(cat "$output/source-commit")" = "$revision"
gpgv --keyring "$output/devlite-update.gpg" "$output/SHA256SUMS.sig" "$output/SHA256SUMS"
fingerprint=$(gpg --batch --with-colons --show-keys "$output/devlite-update.gpg" |
    awk -F: '$1=="pub"{count++; primary=1} $1=="fpr" && primary{print $10; primary=0} END{if(count!=1)exit 1}')
test "$fingerprint" = "$RELEASE_FPR"
(cd "$output" && sha256sum -- "$package" | cmp -s - SHA256SUMS)
test "$(dpkg-deb -f "$output/$package" Package)" = devlite-update
test "$(dpkg-deb -f "$output/$package" Version)" = "$version"
test "$(dpkg-deb -f "$output/$package" Architecture)" = amd64
verify_dir=$(mktemp -d)
trap 'rm -rf -- "$verify_dir"; if [ -n "${keyring:-}" ]; then rm -f -- "$keyring"; fi' EXIT
dpkg-deb -x "$output/$package" "$verify_dir"
cmp "$output/devlite-update.gpg" "$verify_dir/usr/share/keyrings/devlite-update.gpg"

if [ "$action" = publish ]; then
    # A separate operator action must push the reviewed tag first.
    test "$(git rev-parse "refs/tags/$tag^{commit}")" = "$revision"
    local_tag=$(git rev-parse "refs/tags/$tag")
    remote_tag=$(git ls-remote --exit-code --refs origin "refs/tags/$tag" | cut -f1)
    test "$local_tag" = "$remote_tag"
    gh release create "$tag" --repo "$project" --verify-tag --title "DevLite OS $version" \
        --notes-file CHANGELOG.md "$output/$package" "$output/SHA256SUMS" "$output/SHA256SUMS.sig"
fi
