#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${OXSHIFT_HOME:-$HOME/.local/share/oxshift}"
BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.local/share/applications"
PYTHON_BIN="${PYTHON_BIN:-python3}"

say() { printf '\n[OxShift] %s\n' "$*"; }
warn() { printf '\n[OxShift warning] %s\n' "$*" >&2; }

# Bazzite is Fedora Atomic/immutable. Never try to mutate its host image with dnf.
if [[ -r /etc/os-release ]]; then
  # shellcheck disable=SC1091
  source /etc/os-release
  if [[ "${ID:-}" == "bazzite" || "${VARIANT_ID:-}" == *"bazzite"* || "${IMAGE_ID:-}" == *"bazzite"* ]]; then
    say "Bazzite detected; switching to the atomic-safe Distrobox installer."
    exec bash "$ROOT/scripts/install_bazzite.sh" "$@"
  fi
fi

install_system_deps() {
  if [[ "${OXSHIFT_SKIP_SYSTEM_DEPS:-0}" == "1" ]]; then
    return
  fi
  if command -v apt-get >/dev/null 2>&1; then
    say "Installing Debian/Ubuntu audio dependencies"
    sudo apt-get update
    sudo apt-get install -y python3 python3-venv python3-tk portaudio19-dev pulseaudio-utils libsndfile1
  elif command -v dnf >/dev/null 2>&1; then
    say "Installing Fedora audio dependencies"
    sudo dnf install -y python3 python3-tkinter portaudio-devel pulseaudio-utils libsndfile
  elif command -v pacman >/dev/null 2>&1; then
    say "Installing Arch audio dependencies"
    sudo pacman -S --needed --noconfirm python tk portaudio libpulse libsndfile
  else
    warn "Unknown package manager. Install Python 3.10+, Tk, PortAudio, pactl/PipeWire-Pulse and libsndfile manually."
  fi
}

install_system_deps

say "Installing application into $DEST"
mkdir -p "$DEST"
# Copy the unpacked release while excluding local build/runtime state.
tar \
  --exclude='.git' \
  --exclude='.venv' \
  --exclude='.venv-bazzite' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  -C "$ROOT" -cf - . | tar -C "$DEST" -xf -

say "Creating Python environment"
"$PYTHON_BIN" -m venv "$DEST/.venv"
"$DEST/.venv/bin/python" -m pip install --upgrade pip setuptools wheel
"$DEST/.venv/bin/python" -m pip install -r "$DEST/requirements.txt"

if [[ "${OXSHIFT_SKIP_WEBRTC:-0}" != "1" ]]; then
  say "Trying optional WebRTC speech backend"
  if ! "$DEST/.venv/bin/python" -m pip install pywebrtc-audio; then
    warn "WebRTC backend could not be installed. OxShift will use its built-in cleanup backend."
  fi
fi

mkdir -p "$BIN_DIR" "$APP_DIR"
cat > "$BIN_DIR/oxshift" <<EOF
#!/usr/bin/env bash
set -e
cd "$DEST"
exec "$DEST/.venv/bin/python" -m voxshift "\$@"
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

if command -v pactl >/dev/null 2>&1 && [[ "${OXSHIFT_SKIP_VIRTUAL_MIC:-0}" != "1" ]]; then
  say "Creating OxShift virtual microphone"
  bash "$DEST/scripts/linux_virtual_mic.sh" create || warn "Virtual microphone setup failed. You can retry with: bash $DEST/scripts/linux_virtual_mic.sh create"
else
  warn "pactl not found or virtual mic setup skipped."
fi

say "Installation complete"
printf '%s\n' "Run: $BIN_DIR/oxshift"
printf '%s\n' "If ~/.local/bin is in PATH, run: oxshift"
printf '%s\n' "Desktop launcher: OxShift Studio"
