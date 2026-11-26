#!/bin/bash
# Run from the XFCE terminal with Epiphany open. Output stays on stdout.
set -u
export LC_ALL=C
printf '\n== Boot, session and resources ==\n'
if test -d /sys/firmware/efi; then echo UEFI; else echo BIOS; fi
printf 'Session: %s\nDesktop: %s\n' "${XDG_SESSION_TYPE:-unknown}" "${XDG_CURRENT_DESKTOP:-unknown}"
uname -r
free -m
df -h /
systemd-analyze time
systemd-analyze critical-chain --no-pager
printf '\n== AppArmor and browser processes ==\n'
cat /sys/module/apparmor/parameters/enabled
sysctl kernel.apparmor_restrict_unprivileged_userns
while read -r pid name; do
    printf '%s %s\n' "$pid" "$name"
    cat "/proc/$pid/attr/current"
    awk '/^(NoNewPrivs|Seccomp|Seccomp_filters|CapEff|NSpid):/' "/proc/$pid/status"
    for namespace in user mnt pid net; do
        printf '%s ' "$namespace"
        readlink "/proc/$pid/ns/$namespace" || true
    done
done < <(ps -u "$(id -u)" -o pid=,comm= | awk '$2 ~ /^(epiphany|WebKit|bwrap|xdg-dbus-proxy)/')
printf '\n== Session integrations ==\n'
xdg-settings get default-web-browser
for name in org.gnome.Epiphany org.a11y.Bus; do
    timeout 5 gdbus call --session --dest org.freedesktop.DBus --object-path /org/freedesktop/DBus --method org.freedesktop.DBus.NameHasOwner "$name"
done
for name in org.freedesktop.NetworkManager org.freedesktop.RealtimeKit1; do
    timeout 5 gdbus call --system --dest org.freedesktop.DBus --object-path /org/freedesktop/DBus --method org.freedesktop.DBus.NameHasOwner "$name"
done
printf '\n== Audit (redacted paths; inspect before sharing) ==\n'
journalctl -b -k --no-pager -o cat | awk '/apparmor="DENIED"/ && /epiphany|WebKit|bwrap|xdg-dbus-proxy/' | tail -100 | sed -E 's@/home/[^/ "]+@/home/<usuario>@g'
printf '\n== Services and installed versions ==\n'
systemctl show --no-pager --property=Id,LoadState,ActiveState,UnitFileState,Result apache2.service mariadb.service docker.service docker.socket containerd.service ssh.service ssh.socket
dpkg-query -W curl composer apache2 mariadb-server openssh-server openvpn docker-ce docker-compose-plugin epiphany-browser
for command in node npm tsc git python3; do "$command" --version; done
