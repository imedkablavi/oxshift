#!/usr/bin/env bash
set -euo pipefail

SINK="voxshift_sink"
SOURCE="voxshift_mic"
DESC_SINK="VoxShift Output"
DESC_SOURCE="VoxShift Microphone"
STATE_DIR="${XDG_RUNTIME_DIR:-/tmp}/voxshift"
STATE_FILE="$STATE_DIR/modules"

need_pactl() {
  command -v pactl >/dev/null 2>&1 || {
    echo "Error: pactl was not found. Install pulseaudio-utils / your distribution's PulseAudio client tools." >&2
    exit 1
  }
}

create() {
  need_pactl
  mkdir -p "$STATE_DIR"
  if pactl list short sinks | grep -q "[[:space:]]$SINK[[:space:]]"; then
    echo "VoxShift virtual sink already exists."
    exit 0
  fi

  sink_id=$(pactl load-module module-null-sink \
    sink_name="$SINK" \
    sink_properties="device.description='$DESC_SINK'" \
    rate=48000 channels=1)

  source_id=$(pactl load-module module-remap-source \
    master="$SINK.monitor" \
    source_name="$SOURCE" \
    source_properties="device.description='$DESC_SOURCE'" \
    channels=1)

  printf '%s\n%s\n' "$source_id" "$sink_id" > "$STATE_FILE"
  echo "Created: $DESC_SINK ($SINK)"
  echo "Created: $DESC_SOURCE ($SOURCE)"
}

remove() {
  need_pactl
  if [[ -f "$STATE_FILE" ]]; then
    while IFS= read -r module_id; do
      [[ -n "$module_id" ]] && pactl unload-module "$module_id" 2>/dev/null || true
    done < "$STATE_FILE"
    rm -f "$STATE_FILE"
  else
    pactl list short modules | awk -v s="$SINK" -v m="$SOURCE" '$0 ~ s || $0 ~ m {print $1}' | sort -rn | while read -r id; do
      pactl unload-module "$id" 2>/dev/null || true
    done
  fi
  echo "VoxShift virtual audio modules removed."
}

case "${1:-}" in
  create) create ;;
  remove) remove ;;
  *) echo "Usage: $0 {create|remove}"; exit 2 ;;
esac
