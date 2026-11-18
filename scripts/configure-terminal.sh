#!/bin/sh
# Run as the desktop user on the tablet; settings persist in their installed home.
set -eu
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=$XDG_RUNTIME_DIR/bus}"
profile=$(gsettings get org.gnome.Terminal.ProfilesList default | tr -d "'")
case "$profile" in ''|*[!0-9a-f-]*) echo 'Unexpected terminal profile ID' >&2; exit 1;; esac
schema="org.gnome.Terminal.Legacy.Profile:/org/gnome/terminal/legacy/profiles:/:$profile/"
mkdir -p "$HOME/.config/fontconfig"
# Give the generic monospace family an installed fixed-width font.
cat > "$HOME/.config/fontconfig/90-j706f-monospace.conf" <<'EOF'
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">
<fontconfig>
  <alias binding="strong">
    <family>monospace</family>
    <prefer><family>Liberation Mono</family></prefer>
  </alias>
</fontconfig>
EOF
# User fontconfig scans conf.d, rather than arbitrary files in its parent.
mkdir -p "$HOME/.config/fontconfig/conf.d"
ln -sfn ../90-j706f-monospace.conf "$HOME/.config/fontconfig/conf.d/90-j706f-monospace.conf"
fc-cache >/dev/null
gsettings set org.gnome.desktop.interface monospace-font-name 'Liberation Mono 12'
gsettings set "$schema" use-system-font false
gsettings set "$schema" font 'Liberation Mono 13'
gsettings set "$schema" cell-width-scale 1.0
gsettings set "$schema" cell-height-scale 1.0
gsettings set "$schema" use-theme-colors false
gsettings set "$schema" background-color '#1e1e1e'
gsettings set "$schema" foreground-color '#dedede'
gsettings set "$schema" palette "['#2e3436', '#cc0000', '#4e9a06', '#c4a000', '#3465a4', '#75507b', '#06989a', '#d3d7cf', '#555753', '#ef2929', '#8ae234', '#fce94f', '#729fcf', '#ad7fa8', '#34e2e2', '#eeeeec']"
gsettings set org.gnome.Terminal.Legacy.Settings theme-variant 'dark'
fc-match monospace
gsettings get "$schema" font
gsettings get "$schema" background-color
