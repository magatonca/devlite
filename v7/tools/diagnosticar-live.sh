#!/bin/bash
set -u
umask 077
report=$(mktemp -d "$HOME/devlite-diagnostico-XXXXXXXX")
{
    printf 'DISPLAY=%s WAYLAND_DISPLAY=%s XDG_SESSION_TYPE=%s\n' "${DISPLAY:-}" "${WAYLAND_DISPLAY:-}" "${XDG_SESSION_TYPE:-}"
    printf 'XDG_DATA_DIRS=%s XDG_CURRENT_DESKTOP=%s\n' "${XDG_DATA_DIRS:-}" "${XDG_CURRENT_DESKTOP:-}"
    id
    cat /proc/cmdline
    systemctl --failed --no-pager
    systemctl status snapd.seeded.service snap.devlite-installer.subiquity-server.service --no-pager
    stat -c '%a %U:%G %n' /run/subiquity /run/subiquity/socket
    timeout 8 curl -fsS --unix-socket /run/subiquity/socket 'http://localhost/meta/status'
    snap version
    snap list
    snap changes
    snap changes | awk '$2 == "Error" {print $1}' | while read -r change; do
        snap tasks "$change"
    done
    snap connections firefox
    snap debug sandbox-features
    xdg-settings get default-web-browser
    xfconf-query -c xfce4-panel -lv | grep whisker
    journalctl -b -u snapd -u snapd.seeded -u snap.devlite-installer.subiquity-server.service --no-pager -n 100
    journalctl -kb --no-pager --grep 'apparmor=.*DENIED|segfault|drm|GPU' -n 100
    for command in glxinfo eglinfo; do
        if command -v "$command" >/dev/null; then timeout 15 "$command" -B; fi
    done
    for path in /snap/devlite-installer/current/bin/ubuntu_bootstrap /snap/devlite-installer/current/bin/lib/libapp.so; do
        stat "$path"
        if command -v readelf >/dev/null; then readelf -d "$path"; fi
    done
    timeout 15 snap run firefox --version
    for file in "$HOME"/snap/devlite-installer/current/.cache/*log* /var/log/installer/ubuntu_bootstrap.log; do
        if [ -r "$file" ] && [ -f "$file" ]; then tail -n 70 -- "$file"; fi
    done
    if command -v mokutil >/dev/null; then mokutil --sb-state; fi
} > "$report/sistema.log" 2>&1
if [[ ${1:-} == --apps ]]; then
    if [[ -z ${DISPLAY:-}${WAYLAND_DISPLAY:-} ]]; then
        printf '%s\n' 'Abra um terminal no desktop Live para testar a renderização.' >&2
    else
        printf '%s\n' 'Observe se o Firefox renderiza a página de teste. Feche-o para continuar.'
        timeout 90 snap run firefox --new-window 'data:text/html,DevLite%20OS%20Firefox%20teste' > "$report/firefox.log" 2>&1
        printf 'Saída Firefox: %s\n' "$?" >> "$report/firefox.log"
        printf '%s\n' 'Observe a tela inicial do instalador e feche-a sem iniciar a instalação.'
        timeout 90 snap run devlite-installer > "$report/instalador.log" 2>&1
        printf 'Saída instalador: %s\n' "$?" >> "$report/instalador.log"
    fi
fi
printf 'Relatório: %s\n' "$report"
