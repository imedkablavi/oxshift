# Using OxShift Alpha

This guide describes the user-facing workflow in the current `0.3` Alpha candidate.

## First five minutes

1. Launch OxShift.
2. Complete the four-step setup guide.
3. Choose the physical microphone you speak into.
4. Choose the virtual playback/output endpoint used to feed other apps.
5. Pick a starting voice and microphone-cleanup preset.
6. On **Home**, confirm the setup checklist shows input and output selected.
7. On **Audio**, use **Test microphone** while the engine is stopped. Speak normally for 1.5 seconds and check the measured dBFS level.
8. Press **Start engine**.
9. In Discord, OBS, Zoom, game chat, or another target app, choose the recording/microphone side of the same virtual audio route.

The microphone test does not save its temporary capture, route it to speakers, or run it through an AI model.

## Audio routing

### Linux / PipeWire-Pulse

The normal route is:

```text
physical microphone
      ↓
   OxShift
      ↓
OxShift/VoxShift virtual sink
      ↓
voxshift_mic / VoxShift Microphone
      ↓
target application
```

Create the project virtual route with:

```bash
./scripts/linux_virtual_mic.sh create
```

If you reconnect a USB/Bluetooth device while OxShift is running, the engine records the callback/device failure and attempts device re-resolution outside the realtime callback. The **Audio** page exposes the recovery counters and a manual **Recover now** action.

### Windows

OxShift does not silently install a kernel audio driver. Install a signed virtual-audio product you trust, such as VB-CABLE/VoiceMeeter, then route:

```text
physical microphone
      ↓
   OxShift
      ↓
CABLE Input / virtual playback endpoint
      ↓
CABLE Output / virtual recording endpoint
      ↓
target application
```

The Home/Audio route status recognizes common VB-Audio/VoiceMeeter virtual endpoint names and warns when the selected output looks like normal speakers instead of a virtual route.

## Home

Home is intended to answer four questions without opening another page:

- Is a microphone selected?
- Is an output selected?
- Does the output look like a virtual microphone route?
- Is the audio engine running?

It also exposes live mic, Soundboard, and output meters, basic callback/XRun health, recording controls, and shortcuts to the main workflows.

## Voices and Studio

Use **Voices** for a preset starting point. Search and category filters are paginated so the page stays bounded instead of creating an unlimited number of Tk widgets.

Use **Studio** for the actual chain:

- pitch and timbre/color;
- wet/dry;
- gain and gate;
- built-in or optional WebRTC microphone processing;
- noise suppression and AGC;
- reorderable DSP stages;
- per-stage bypass.

Studio/profile changes are autosaved after a short debounce by default. Disable edit-time autosave in **Preferences** if you want to use `Ctrl+S` manually.

## Starter profiles

The Profiles page can create new profiles without overwriting the active one:

- **Gaming** — clean voice, moderate cleanup, low soundboard ducking;
- **Streaming** — Broadcast starting point with balanced cleanup;
- **Calls** — stronger cleanup, lower soundboard level, one-at-a-time sound playback.

**Reset active to Clean** asks for confirmation and preserves the active profile name and saved input/output device names.

## Soundboard

The Soundboard supports streaming audio rather than loading an entire long file into the realtime callback.

For each sound you can edit:

- display name;
- category;
- volume;
- trim start/end;
- fade in/out;
- loop;
- global hotkey.

Hotkey examples:

```text
<f8>
<ctrl>+<alt>+1
<shift>+a
```

OxShift validates the syntax and prevents assigning the same hotkey to two sounds. A valid hotkey can still be unavailable at runtime when the desktop security model blocks global key capture, especially under some Wayland compositors; the rest of OxShift continues to work.

Large sound libraries are paginated and remain searchable.

## Playlists

Create a named playlist, add sounds from the library, then use **Play**, **Next**, and **Stop**. Playlist entries reference the Soundboard library; removing a sound prunes stale playlist references.

## Local AI models

Raw `.onnx` and `.pth` files are not treated as trusted executable models. The Alpha trust boundary requires a supported `oxshift-model.json` schema plus checksum and graph-signature validation.

The current CLI activation path is explicit:

```bash
python -m voxshift --model-manifest /path/to/bundle/oxshift-model.json
```

Model validation occurs outside the PortAudio callback. Conversion runs through the bounded voice-conversion worker queue.

## Preferences

Open **Preferences** in the top bar or press `Ctrl+,`.

Current options include:

- edit-time profile autosave;
- global Soundboard hotkeys;
- rerun first-use setup;
- reset remembered window size;
- refresh audio devices.

## Keyboard shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+1` | Home |
| `Ctrl+2` | Voices |
| `Ctrl+3` | Soundboard |
| `Ctrl+4` | Studio |
| `Ctrl+5` | Profiles |
| `Ctrl+6` | AI Models |
| `Ctrl+7` | Audio |
| `Ctrl+S` | Save current profile state |
| `Ctrl+,` | Preferences |
| `F5` | Refresh audio devices |

## Privacy behavior

OxShift is local-first. The application does not intentionally upload microphone audio, Soundboard files, or imported model files. Diagnostics exclude device names, usernames, local media paths, sound names, and model filenames.

The isolated microphone test uses a short in-memory sample only to calculate signal level. Recording output is an explicit user action and writes through a background queue rather than the realtime callback.

## Troubleshooting

### No microphone signal

- Open **Audio** and confirm an input is selected.
- Stop the engine if running.
- Run **Test microphone**.
- Check the OS microphone mute/privacy controls and hardware gain if the result is below roughly `-55 dBFS`.

### OxShift meter moves but the target app hears nothing

- Verify the OxShift output is a virtual playback/sink endpoint rather than ordinary speakers.
- In the target app, select the paired virtual recording/microphone endpoint.
- Refresh devices after installing a virtual route.

### Device disappeared during use

- Check the Audio recovery counters.
- Reconnect the device and use **Recover now** if automatic recovery has not restored it.
- Saved profiles use device names/host API information so an index change does not by itself permanently break the route.

### Global hotkey does not fire

- Confirm global hotkeys are enabled in Preferences.
- Check the Soundboard editor for a listener error after saving the hotkey.
- On Wayland, compositor/security policy may intentionally prevent global capture.
