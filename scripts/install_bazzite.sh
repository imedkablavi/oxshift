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

command -v distrobox >/dev/null 2>&1 || fail "Distrobox was not found. Enable/install Distrobox from Bazzite Portal and retry."
command -v podman >/dev/null 2>&1 || fail "Podman was not found. It is required by Distrobox."

FEDORA_VERSION="${VERSION_ID%%.*}"
if [[ ! "$FEDORA_VERSION" =~ ^[0-9]+$ ]]; then
  FEDORA_VERSION="44"
fi
IMAGE="${OXSHIFT_DISTROBOX_IMAGE:-registry.fedoraproject.org/fedora:${FEDORA_VERSION}}"

say "Detected Bazzite/Fedora Atomic. Host package layering will NOT be used."
say "Using Distrobox '$BOX' with image '$IMAGE'."

# `distrobox list` uses pipe-delimited output on current releases; checking a fixed awk
# column can mistake an existing box for a missing one. Normalize pipes and search tokens.
if distrobox list --no-color 2>/dev/null | tr '|' ' ' | awk -v box="$BOX" '{for (i=1; i<=NF; i++) if ($i == box) found=1} END {exit !found}'; then
  say "Reusing existing Distrobox '$BOX'"
else
  say "Creating OxShift Distrobox"
  distrobox create --yes --name "$BOX" --image "$IMAGE"
fi

say "Installing runtime dependencies inside Distrobox (host remains immutable)"
# Never use a login shell here. The host HOME is shared into Distrobox, so ~/.bashrc may
# prepend Linuxbrew Python or broken Homebrew paths. Pin /usr/bin/python3 from Fedora.
distrobox enter --name "$BOX" -- /bin/bash --noprofile --norc -c \
  'set -e; sudo dnf -y install python3 python3-devel python3-pip python3-tkinter portaudio portaudio-devel pulseaudio-utils libsndfile libsndfile-devel gcc gcc-c++'

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
distrobox enter --name "$BOX" -- /bin/bash --noprofile --norc -c \
  "set -e; rm -rf '$DEST/.venv-bazzite'; /usr/bin/python3 -m venv '$DEST/.venv-bazzite'; if ! '$DEST/.venv-bazzite/bin/python' -m pip --version >/dev/null 2>&1; then '$DEST/.venv-bazzite/bin/python' -m ensurepip --upgrade; fi; '$DEST/.venv-bazzite/bin/python' -m pip install --upgrade pip setuptools wheel; '$DEST/.venv-bazzite/bin/python' -m pip install -r '$DEST/requirements.txt'"

if [[ -f "$DEST/requirements-hotkeys.txt" && "${OXSHIFT_SKIP_HOTKEYS:-0}" != "1" ]]; then
  say "Trying optional global Soundboard hotkeys"
  if ! distrobox enter --name "$BOX" -- /bin/bash --noprofile --norc -c \
    "'$DEST/.venv-bazzite/bin/python' -m pip install -r '$DEST/requirements-hotkeys.txt'"; then
    warn "Global hotkeys could not be installed. OxShift remains usable; Wayland may block global key capture anyway."
  fi
fi

if [[ "${OXSHIFT_SKIP_WEBRTC:-0}" != "1" ]]; then
  say "Trying optional WebRTC speech backend inside Distrobox"
  if ! distrobox enter --name "$BOX" -- /bin/bash --noprofile --norc -c \
    "'$DEST/.venv-bazzite/bin/python' -m pip install pywebrtc-audio"; then
    warn "WebRTC backend could not be installed. Built-in mic cleanup remains available."
  fi
fi

# Verify one module at a time and surface the actual stderr. Previous verification used one
# combined import and could terminate under `set -e` without telling the user which runtime
# component failed.
say "Verifying Python/Tk runtime"
RUNTIME_PY="$DEST/.venv-bazzite/bin/python"
for module in tkinter _tkinter numpy sounddevice pedalboard; do
  if output="$(distrobox enter --name "$BOX" -- "$RUNTIME_PY" -c "import $module; print('$module OK')" 2>&1)"; then
    printf '[OxShift/Bazzite] %s\n' "$output"
  else
    printf '%s\n' "$output" >&2
    fail "Runtime verification failed while importing '$module'. The launcher was not created."
  fi
done

# Verify the installed checkout is importable from its real installation directory.
if output="$(distrobox enter --name "$BOX" -- /bin/bash --noprofile --norc -c \
  "cd '$DEST' && '$RUNTIME_PY' -m voxshift --help >/dev/null && printf 'OxShift CLI import OK'" 2>&1)"; then
  printf '[OxShift/Bazzite] %s\n' "$output"
else
  printf '%s\n' "$output" >&2
  fail "OxShift package import verification failed."
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
