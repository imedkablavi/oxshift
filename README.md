# OxShift

OxShift is a local-first desktop voice studio that combines a real-time voice changer, a Soundpad-style soundboard/music player, virtual-microphone routing, and a foundation for local AI voice models.

> Current status: **0.2 development preview**. The DSP voice changer and soundboard pipeline are functional foundations. Local AI model discovery and a non-blocking realtime VC runtime are implemented; model-specific RVC graph adapters remain compatibility-gated until their schemas and latency are validated.

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

### Local AI / RVC runtime

The **AI Models** page can locally import and catalog `.onnx`, `.pth`, and `.index` files. OxShift also has a realtime conversion stage that runs inference on a worker thread instead of inside the PortAudio callback.

The runtime uses bounded input/output queues. If an AI backend is slower than the realtime budget, the callback never waits for it: old work can be dropped and OxShift can fall back to passthrough audio instead of freezing the device stream. Runtime statistics track submitted/converted blocks, dropped inputs, output underruns, inference time, peak time, and adapter errors.

RVC bundles can use an `oxshift-rvc.json` manifest to describe required components instead of treating arbitrary ONNX graphs as interchangeable:

```json
{
  "name": "My Voice",
  "version": 1,
  "sample_rate": 40000,
  "synthesizer": "model.onnx",
  "content_encoder": "contentvec.onnx",
  "pitch_estimator": "rmvpe.onnx",
  "index": "voice.index",
  "speaker_id": 0
}
```

The runtime validates bundle files before a model-specific adapter is allowed to execute them. Full RVC conversion still requires a validated content-encoder/F0/synthesizer adapter; imported models are not executed blindly.

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

GPU provider packages are handled separately because CUDA/DirectML availability is platform-specific.

## Architecture

```text
voxshift/
├── audio_engine.py   # realtime microphone + VC stage + soundboard mixer callback
├── dsp.py            # local DSP rack and realtime pitch backend
├── voices.py         # declarative voice preset catalog
├── soundboard.py     # persistent streaming soundboard/mixer
├── hotkeys.py        # optional global hotkey listener
├── ai_models.py      # local model registry and backend capability detection
├── rvc_runtime.py    # async VC worker, bounded queues and RVC bundle manifests
└── ui.py             # desktop dashboard and pages
```

The realtime callback does not read media files from disk or run slow AI inference synchronously. Soundboard decoding and voice conversion work happen outside the callback and feed bounded float32 queues.

## Privacy and responsible use

OxShift is local-first. The application does not upload microphone audio, soundboard media, or imported voice-model files. AI voice conversion should be used with models and voices you have the right and consent to use; the project is not intended for deceptive impersonation.

## Tests

```bash
python -m unittest discover -s tests -v
```

GitHub Actions runs the suite on supported Python versions for pull requests.

## Roadmap

Near-term engineering priorities:

- Validated ONNX adapters for ContentVec/HubERT + RMVPE/FCPE + RVC synthesizer graphs
- CPU/CUDA/DirectML execution profiles and model warm-up
- Real end-to-end latency measurement and adaptive chunk sizing
- Soundboard waveform editor, trim, fade-in/fade-out, playlists and folders
- Per-sound output/monitor routing
- Native Windows virtual-audio setup guidance/automation where legally and technically appropriate
- Settings migration and crash-safe persistence
- Packaging/installers for Windows and Linux
- Long-run audio stress tests and device reconnect handling
