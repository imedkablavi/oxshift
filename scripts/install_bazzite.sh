#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${OXSHIFT_HOME:-$HOME/.local/share/oxshift}"
BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.local/share/applications"
BOX="${OXSHIFT_DISTROBOX:-oxshift}"

say() { printf '\n[OxShift/Bazzite] %s\n' "$*"; }
warn() { printf '\n[OxShift/Bazzite warning] %s\n' "$*" >&2; }
fail() { printf '\n[OxShift/Bazzite error] %s\n' "$*" >&2; exit 1; }

if [[ ! -r /etc/os-release ]]; then
  fail "Cannot read /etc/os-release."
fi
# shellcheck disable=SC1091
source /etc/os-release
if [[ "${ID:-}" != "bazzite" && "${VARIANT_ID:-}" != *"bazzite"* && "${IMAGE_ID:-}" != *"bazzite"* ]]; then
  warn "This installer is intended for Bazzite/Fedora Atomic hosts. Continuing anyway."
fi

command -v distrobox >/dev/null 2>&1 || fail "Distrobox was not found. Bazzite normally ships it; install/enable Distrobox from Bazzite Portal and retry."
command -v podman >/dev/null 2>&1 || fail "Podman was not found. It is required by Distrobox."

FEDORA_VERSION="${VERSION_ID%%.*}"
if [[ ! "$FEDORA_VERSION" =~ ^[0-9]+$ ]]; then
  FEDORA_VERSION="44"
fi
IMAGE="${OXSHIFT_DISTROBOX_IMAGE:-registry.fedoraproject.org/fedora:${FEDORA_VERSION}}"

say "Detected Bazzite/Fedora Atomic. Host package layering will NOT be used."
say "Using Distrobox '$BOX' with image '$IMAGE'."

if ! distrobox list --no-color 2>/dev/null | awk 'NR>1 {print $2}' | grep -Fxq "$BOX"; then
  say "Creating OxShift Distrobox"
  distrobox create --yes --name "$BOX" --image "$IMAGE"
else
  say "Reusing existing Distrobox '$BOX'"
fi

say "Installing runtime dependencies inside Distrobox (host remains immutable)"
distrobox enter --name "$BOX" -- bash -lc \
  'sudo dnf -y install python3 python3-devel python3-tkinter portaudio portaudio-devel pulseaudio-utils libsndfile libsndfile-devel gcc gcc-c++'

say "Copying OxShift into $DEST"
mkdir -p "$DEST"
tar \
  --exclude='.git' \
  --exclude='.venv' \
  --exclude='.venv-bazzite' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  -C "$ROOT" -cf - . | tar -C "$DEST" -xf -

say "Creating isolated Python environment inside Distrobox"
distrobox enter --name "$BOX" -- bash -lc \
  "python3 -m venv '$DEST/.venv-bazzite' && '$DEST/.venv-bazzite/bin/python' -m pip install --upgrade pip setuptools wheel && '$DEST/.venv-bazzite/bin/python' -m pip install -r '$DEST/requirements.txt'"

if [[ "${OXSHIFT_SKIP_WEBRTC:-0}" != "1" ]]; then
  say "Trying optional WebRTC speech backend inside Distrobox"
  if ! distrobox enter --name "$BOX" -- bash -lc \
    "'$DEST/.venv-bazzite/bin/python' -m pip install pywebrtc-audio"; then
    warn "WebRTC backend could not be installed. Built-in mic cleanup remains available."
  fi
fi

cat > "$DEST/run-bazzite.sh" <<EOF
#!/usr/bin/env bash
set -e
cd "$DEST"
exec "$DEST/.venv-bazzite/bin/python" -m voxshift "\$@"
EOF
chmod +x "$DEST/run-bazzite.sh"

mkdir -p "$BIN_DIR" "$APP_DIR"
cat > "$BIN_DIR/oxshift" <<EOF
#!/usr/bin/env bash
set -e
# Distrobox forwards the host desktop session (X11/Wayland) and PipeWire/Pulse sockets.
exec distrobox enter --name "$BOX" -- "$DEST/run-bazzite.sh" "\$@"
EOF
chmod +x "$BIN_DIR/oxshift"

cat > "$APP_DIR/oxshift.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=OxShift Studio
Comment=Local real-time voice studio and soundboard
Exec=$BIN_DIR/oxshift
Terminal=false
Categories=AudioVideo;Audio;
StartupNotify=true
EOF

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$APP_DIR" >/dev/null 2>&1 || true
fi

# Virtual microphone belongs on the Bazzite host, not inside the container.
if [[ "${OXSHIFT_SKIP_VIRTUAL_MIC:-0}" != "1" ]]; then
  if command -v pactl >/dev/null 2>&1; then
    say "Creating OxShift virtual microphone on host PipeWire/Pulse"
    bash "$DEST/scripts/linux_virtual_mic.sh" create || warn "Virtual mic creation failed; OxShift itself is still installed."
  else
    warn "Host pactl not found. PipeWire-Pulse tools are required for the virtual microphone."
  fi
fi

say "Bazzite installation complete"
printf '%s\n' "Run: $BIN_DIR/oxshift"
printf '%s\n' "Desktop launcher: OxShift Studio"
printf '%s\n' "Container: $BOX ($IMAGE)"
printf '%s\n' "Host OS was not modified with dnf/rpm-ostree package layering."
