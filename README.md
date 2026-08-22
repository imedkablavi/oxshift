# OxShift

OxShift is a local-first desktop voice studio that combines a real-time voice changer, a Soundpad-style soundboard/music player, virtual-microphone routing, and a foundation for local AI voice models.

> Current status: **0.2 development preview**. The DSP voice changer and soundboard pipeline are functional foundations. Local AI model discovery is implemented, while full RVC inference remains intentionally adapter-gated until model compatibility and latency are validated.

## Highlights

### Real-time voice studio

- Live microphone capture/output through `sounddevice`
- Voice preset library with categories and search
- Presets including Clean, Broadcast, Deep, Bright, Anonymous, Robot, Android, Radio, Telephone, Intercom, Ghost, Cyber, Megaphone, and Low-Fi
- Gain, wet/dry mix, noise gate, filtering, saturation, modulation, delay, and compression
- Realtime pitch shifting through Spotify Pedalboard / Rubber Band when available
- Experimental timbre/formant-color control (spectral-envelope coloring, **not** independent AI formant conversion)
- Input/output/soundboard meters and callback performance telemetry
- XRuns / over-budget callback counter

### Soundboard / music player

The Soundboard is designed around the same virtual-microphone path as the voice changer, so callers can hear both the processed microphone and local audio.

- Import WAV, MP3, OGG, FLAC, and AIFF
- Streaming decode/resampling instead of loading long songs fully into RAM
- Background decoding with bounded buffers so file I/O does not run in the realtime audio callback
- Play, pause, stop, stop-all
- Overlapping playback or one-at-a-time mode
- Per-sound volume metadata and master volume
- Optional microphone ducking while media is playing
- Loop and trim metadata in the persistent sound library
- Global hotkeys through `pynput` (platform support permitting)
- Persistent local library under the user's configuration directory

Hotkey examples use pynput syntax:

```text
<f8>
<ctrl>+<alt>+1
<shift>+<f10>
```

On Linux/Wayland, desktop security policy may prevent global key capture. OxShift keeps working even when the global-hotkey listener is unavailable.

### Local AI model foundation

The **AI Models** page can locally import and catalog:

- `.onnx`
- `.pth`
- `.index`

OxShift detects installed ONNX Runtime execution providers but does **not** blindly execute arbitrary imported graphs. RVC models require a compatible inference adapter, F0 extraction, feature extraction, retrieval/index handling, buffering, and hardware-specific latency tuning. That adapter is the next AI milestone.

This separation is intentional: model storage/discovery, the realtime audio engine, and inference backends should remain independently replaceable.

## Linux quick start

Requirements: Python 3.10+, PipeWire/PulseAudio compatibility (`pactl`), and PortAudio.

```bash
sudo apt install python3-venv portaudio19-dev pulseaudio-utils
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

./scripts/linux_virtual_mic.sh create
python -m voxshift
```

In OxShift:

1. Select your physical microphone as **Input**.
2. Select the OxShift/VoxShift virtual sink as **Output**.
3. Start the engine.
4. In Discord, OBS, Zoom, games, or another VoIP app, select **VoxShift Microphone** / `voxshift_mic` as the microphone.
5. Open **Soundboard** to import music/effects. Playback is mixed into the same virtual microphone output.

Remove Linux virtual devices with:

```bash
./scripts/linux_virtual_mic.sh remove
```

## Optional AI runtime

For ONNX Runtime provider detection:

```bash
pip install -r requirements-ai.txt
```

GPU provider packages will be handled separately because CUDA/DirectML/CoreML availability is platform-specific.

## Architecture

```text
voxshift/
├── audio_engine.py   # realtime microphone + soundboard mixer callback
├── dsp.py            # local DSP rack and realtime pitch backend
├── voices.py         # declarative voice preset catalog
├── soundboard.py     # persistent streaming soundboard/mixer
├── hotkeys.py        # optional global hotkey listener
├── ai_models.py      # local model registry and backend capability detection
└── ui.py             # desktop dashboard and pages
```

The realtime callback does not read media files from disk. Soundboard decoding/resampling runs on background threads and feeds bounded float32 queues consumed by the audio callback.

## Privacy and responsible use

OxShift is local-first. The application does not upload microphone audio, soundboard media, or imported voice-model files. AI voice conversion should be used with models and voices you have the right and consent to use; the project is not intended for deceptive impersonation.

## Tests

```bash
python -m unittest discover -s tests -v
```

GitHub Actions runs the suite on supported Python versions for pull requests.

## Roadmap

Near-term engineering priorities:

- Production RVC/ONNX inference adapter with validated model schemas
- F0 backends (RMVPE/FCPE) and configurable retrieval index
- CPU/CUDA/DirectML execution profiles
- Real end-to-end latency measurement
- Soundboard waveform, trim, fade-in/fade-out, playlists and folders
- Per-sound output/monitor routing
- Native Windows virtual-audio setup guidance/automation where legally and technically appropriate
- Settings migration and crash-safe persistence
- Packaging/installers for Windows and Linux
- Long-run audio stress tests and device reconnect handling
