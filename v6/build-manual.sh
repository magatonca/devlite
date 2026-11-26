#!/bin/bash
set -euo pipefail
root=/home/magaton/DevLite-OS
cd "$root"
if [[ $(id -un) != magaton ]]; then
    echo 'Execute manualmente como magaton.' >&2
    exit 2
fi
if [[ $# == 1 && $1 == --execute-authorized ]]; then
    mode=pack
elif [[ $# == 2 && $1 == --validate-guest && $2 =~ ^pack-[a-z0-9_]{8}$ ]]; then
    mode=probe
else
    echo 'Use --execute-authorized ou --validate-guest ID-DO-PACK.' >&2
    exit 2
fi
/usr/bin/python3 -B -m v6.gate verify
if [[ $mode == pack ]]; then
    /usr/bin/python3 -B -m v6.storage all
fi
audit=$(mktemp -d "$root/work/v6-manual-XXXXXXXX")
echo "Log do executor: $audit/pack.log"
sudo -- /usr/bin/systemd-run --unit=devlite-v6-pack --wait --pipe --collect \
    --working-directory="$root" \
    --property=StateDirectory=devlite-v6 --property=StateDirectoryMode=0755 \
    --property=ProtectSystem=strict --property=ProtectHome=read-only \
    --property=PrivateNetwork=yes --property=PrivateMounts=yes --property=PrivateTmp=yes \
    --property=NoNewPrivileges=yes --property=ProtectKernelTunables=yes \
    --property=ProtectKernelModules=yes --property=ProtectControlGroups=yes \
    --property=RestrictRealtime=yes '--property=RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6' \
    --property=MemoryMax=2684354560 --property=MemorySwapMax=1073741824 \
    --property=CPUQuota=100% --property=TasksMax=128 --property=LimitCORE=0 \
    --property=RuntimeMaxSec=10800 --property=TimeoutStopSec=60 --property=KillMode=control-group \
    --property='CapabilityBoundingSet=CAP_SYS_ADMIN CAP_SYS_CHROOT CAP_KILL CAP_CHOWN CAP_DAC_OVERRIDE CAP_DAC_READ_SEARCH CAP_FOWNER CAP_FSETID CAP_MKNOD CAP_SETFCAP CAP_SETPCAP CAP_SETUID CAP_SETGID' \
    /usr/bin/unshare --mount --propagation private --pid --fork --kill-child --mount-proc --ipc --uts \
    /usr/bin/python3 -EB -m v6.pack "$@" 2>&1 | tee "$audit/pack.log"
if [[ $mode == probe ]]; then
    exit 0
fi
mapfile -t packs < <(sed -nE 's@^Pack verificado: (/var/lib/devlite-v6/pack-[a-z0-9_]{8})/published$@\1@p' "$audit/pack.log")
if [[ ${#packs[@]} != 1 ]]; then
    echo 'Recibo de pack não encontrado de forma inequívoca.' >&2
    exit 1
fi
/usr/bin/python3 -B -m v6.storage assemble -- /usr/bin/python3 -B -m v6.assemble "${packs[0]}"
