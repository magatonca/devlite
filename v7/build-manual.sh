#!/bin/bash
set -euo pipefail
root=/home/magaton/DevLite-OS
cd "$root"
if [[ $(id -un) != magaton ]]; then
    echo 'Execute como magaton.' >&2
    exit 2
fi
if [[ $# == 1 && $1 == --preflight ]]; then
    exec /usr/bin/python3 -B -m v7.preflight
fi
if [[ $# == 2 && $1 == --assemble && $2 =~ ^/var/lib/devlite-v7/pack-[a-z0-9_]{8}$ ]]; then
    exec /usr/bin/python3 -B -m v7.assemble --monitored "$2"
fi
echo 'Use --preflight ou --assemble CAMINHO-DO-PACK. O pack usa a unidade administrativa.' >&2
exit 2
