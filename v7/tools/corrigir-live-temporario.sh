#!/bin/sh
set -eu
[ "$(id -u)" -ne 0 ] || exit 1
grep -q 'layerfs-path=.*\.v7\.squashfs' /proc/cmdline || exit 1
[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ] || { echo 'Execute no terminal gráfico do Live.' >&2; exit 1; }
case "${1:-}" in ''|--software) ;; *) exit 2 ;; esac
umask 077
work=$(mktemp -d "$HOME/.devlite-live-teste-XXXXXXXX")
cat > "$work/launch" <<'EMBED_LAUNCH'
#!/bin/sh
set -eu
app=${1:?}
shift
case "$app" in firefox|devlite-installer) ;; *) exit 2 ;; esac
error() {
    printf '%s\n' "$1" >&2
    /usr/bin/timeout 5 /usr/bin/notify-send -u critical 'DevLite OS' "$1" || :
}
if ! /usr/bin/timeout 180 /bin/sh -c '
    until /usr/bin/systemctl is-active --quiet snapd.seeded.service &&
          /usr/bin/snap list "$1" >/dev/null 2>&1; do
        sleep 2
    done
' devlite "$app"; then
    error "O aplicativo $app não ficou disponível. Verifique o serviço snapd.seeded."
    exit 1
fi
if /usr/bin/snap run "$app" "$@"; then
    exit 0
else
    status=$?
    error "O aplicativo $app encerrou com código $status. Abra pelo terminal para ver o erro."
    exit "$status"
fi
EMBED_LAUNCH
cat > "$work/configure-desktop" <<'EMBED_DESKTOP'
#!/bin/sh
set -eu
[ "$(id -u)" -ne 0 ] || exit 1
grep -q 'layerfs-path=.*\.v7\.squashfs' /proc/cmdline || exit 1
source_file=${1:-/usr/share/applications/devlite-installer.desktop}
desktop=$(xdg-user-dir DESKTOP)
[ -n "$desktop" ] && [ "$desktop" != "$HOME" ] || exit 1
mkdir -p -- "$desktop"
shortcut="$desktop/${source_file##*/}"
if [ ! -e "$shortcut" ] && [ ! -L "$shortcut" ]; then
    install -m 0755 -- "$source_file" "$shortcut"
fi
if [ -f "$shortcut" ] && [ ! -L "$shortcut" ] && cmp -s "$source_file" "$shortcut"; then
    checksum=$(sha256sum "$shortcut" | cut -d ' ' -f1)
    gio set "$shortcut" metadata::xfce-exe-checksum "$checksum" || :
    gio set "$shortcut" metadata::trusted true || :
fi
config=${XDG_CONFIG_HOME:-"$HOME/.config"}/xfce4/panel
mkdir -p -- "$config"
changed=no
for plugin in $(xfconf-query -c xfce4-panel -lv | awk '$1 ~ /^\/plugins\/plugin-[0-9]+$/ && $2 == "whiskermenu" {sub(/^.*plugin-/, "", $1); print $1}'); do
    settings="$config/whiskermenu-$plugin.rc"
    [ ! -L "$settings" ] || continue
    icon=/usr/share/icons/hicolor/scalable/apps/devlite.svg
    grep -Fxq "button-icon=$icon" "$settings" 2>/dev/null && continue
    tmp=$(mktemp "$config/.devlite-whisker-XXXXXX")
    if [ -f "$settings" ]; then
        sed '/^button-icon=/d; /^button-title=/d' "$settings" > "$tmp"
    fi
    printf 'button-icon=%s\nbutton-title=Menu DevLite OS\n' "$icon" >> "$tmp"
    mv -T -- "$tmp" "$settings"
    changed=yes
done
if [ "$changed" = yes ]; then
    xfce4-panel --restart
fi
EMBED_DESKTOP
chmod 0700 "$work/launch" "$work/configure-desktop"
launcher="$work/launch"
if [ "${1:-}" = --software ]; then
    printf '#!/bin/sh\nexport LIBGL_ALWAYS_SOFTWARE=1\nexec "%s" "$@"\n' "$launcher" > "$work/software"
    chmod 0700 "$work/software"
    launcher="$work/software"
fi
apps=${XDG_DATA_HOME:-"$HOME/.local/share"}/applications
mkdir -p -- "$apps"
installer="$apps/devlite-installer-teste.desktop"
browser="$apps/devlite-firefox-teste.desktop"
cat > "$installer" <<EOF
[Desktop Entry]
Type=Application
Name=Instalar DevLite OS 1.0 (teste)
Exec="$launcher" devlite-installer
Icon=/usr/share/icons/hicolor/scalable/apps/devlite.svg
StartupWMClass=ubuntu_bootstrap
EOF
cat > "$browser" <<EOF
[Desktop Entry]
Type=Application
Name=Firefox (teste DevLite)
Exec="$launcher" firefox %u
Icon=firefox
MimeType=text/html;application/xhtml+xml;x-scheme-handler/http;x-scheme-handler/https;
EOF
for type in text/html application/xhtml+xml x-scheme-handler/http x-scheme-handler/https; do
    xdg-mime default devlite-firefox-teste.desktop "$type"
done
"$work/configure-desktop" "$installer"
printf '%s\n' 'Abra os dois atalhos de teste no menu. Compare o conteúdo renderizado antes de aprovar.'
