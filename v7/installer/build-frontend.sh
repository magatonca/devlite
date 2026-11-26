#!/bin/bash
# Run on an unprivileged build machine with the pinned Flutter SDK.
set -euo pipefail
repo=$(cd -- "$(dirname -- "$0")/../.." && pwd)
revision=2e8d70ee20871c2683e36cbde3a360a0a73108c9
if [[ $# != 1 || $(id -u) == 0 ]]; then
    echo 'Usage: build-frontend.sh PATH-TO-UPSTREAM-GIT-CHECKOUT (unprivileged)' >&2
    exit 2
fi
upstream=$(realpath -e -- "$1")
if [[ $(git -C "$upstream" rev-parse HEAD) != "$revision" ]]; then
    echo "Expected Ubuntu Desktop Provision commit $revision" >&2
    exit 2
fi
if ! flutter --no-version-check --version --machine | python3 -c '
import json, sys
text = sys.stdin.read()
start = text.index("{")
release, _ = json.JSONDecoder().raw_decode(text[start:])
sys.exit(release["frameworkVersion"] != "3.19.2" or
         release["frameworkRevision"] != "7482962148e8d758338d8a28f589f317e1e42ba4")
'; then
    echo 'Flutter 3.19.2 is required.' >&2
    exit 2
fi
export PYTHONPATH="$repo"
python3 -B -c 'from v6.storage import ROOT, require_space; from v7.storage import FRONTEND; require_space(ROOT, sum(FRONTEND.values()))'
job=$(mktemp -d "$repo/work/v7-frontend-XXXXXXXX")
printf 'Frontend workspace: %s\n' "$job"
export PUB_CACHE="$job/pub-cache"
git clone --quiet --no-hardlinks --no-checkout -- "$upstream" "$job/source"
cd "$job/source"
git checkout --quiet --detach "$revision"
git submodule update --init --recursive
git apply --check "$repo/v7/installer/devlite-product.patch"
git apply "$repo/v7/installer/devlite-product.patch"
dart pub get --enforce-lockfile
dart run melos bootstrap
cd packages/ubuntu_bootstrap
flutter --no-version-check test --no-pub --concurrency=1 --reporter=expanded
flutter --no-version-check build linux --release --no-pub
bundle="$PWD/build/linux/x64/release/bundle"
test -x "$bundle/ubuntu_bootstrap"
test -f "$bundle/lib/libapp.so"
find "$bundle" -type f -print0 | sort -z | xargs -0 sha256sum > "$job/frontend.SHA256SUMS"
printf 'Frontend bundle: %s\n' "$bundle"
