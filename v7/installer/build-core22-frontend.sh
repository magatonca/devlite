#!/bin/bash
# Run within an amd64 Ubuntu 22.04 builder with Jammy GTK headers and pinned Flutter.
set -euo pipefail
if [[ $(id -u) == 0 || $(uname -m) != x86_64 ]]; then
    echo 'Use um builder amd64 sem privilégios.' >&2
    exit 2
fi
. /etc/os-release
if [[ $ID != ubuntu || $VERSION_ID != 22.04 ]]; then
    echo 'O frontend para core22 precisa das bibliotecas de desenvolvimento do Jammy.' >&2
    exit 2
fi
if [[ $(pkg-config --modversion glib-2.0) != 2.72.* ]]; then
    echo 'Use os headers GLib 2.72 do Jammy.' >&2
    exit 2
fi
exec bash "$(dirname -- "$0")/build-frontend.sh" "$@"
