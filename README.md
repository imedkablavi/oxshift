# OxShift

OxShift is a local-first desktop voice studio combining a real-time voice changer, Soundpad-style soundboard/music player, virtual-microphone routing, recording, studio profiles, diagnostics, and a foundation for local AI voice models.

> Current status: **0.3 development preview**. The DSP voice changer, soundboard, recording path, profile system and non-blocking VC runtime are implemented as development foundations. Model-specific RVC graph adapters remain compatibility-gated until schemas and latency are validated.

## Product-grade studio UI

`python -m voxshift` now launches the newer **OxShift Studio** interface. The older UI remains in the repository during the transition.

The new shell separates the product into Home, Voices, Soundboard, Studio, Profiles, AI Models and Audio. Home includes live mic/soundboard/output meters, engine health, recording controls and privacy-safe diagnostics export.

### Studio profiles

Profiles persist complete working setups instead of requiring users to rebuild settings every launch. A profile currently stores:

- active voice preset
- gain, wet/dry, noise gate
- pitch and timbre/formant-color controls
- soundboard master volume, ducking and overlap mode
- sample rate and audio block size

Profile writes use an atomic temporary-file replacement and value validation so a partial write or invalid setting is less likely to corrupt startup state.

### Real-time output recorder

OxShift can record the final mixed output - processed microphone plus Soundboard - to mono PCM16 WAV.

Recording is non-blocking for the device callback: audio blocks are copied into a bounded queue and disk I/O is handled by a worker thread. If storage becomes too slow, dropped recorder blocks are counted instead of allowing file writes to stall microphone processing.

### Diagnostics

A support snapshot can be exported as JSON. It includes platform/audio-engine health such as sample rate, block size, callback timing, XRuns, VC inference timing and recorder drops. Device names, local paths, sound names and model filenames are intentionally excluded from the diagnostics payload.

## Real-time voice studio

- Live microphone capture/output through `sounddevice`
- Voice preset library with categories and search
- Clean, Broadcast, Deep, Bright, Anonymous, Robot, Android, Radio, Telephone, Intercom, Ghost, Cyber, Megaphone and Low-Fi presets
- Gain, wet/dry mix, noise gate, filtering, saturation, modulation, delay and compression
- Realtime pitch shifting through Spotify Pedalboard / Rubber Band when available
- Experimental timbre/formant-color control (spectral-envelope coloring, **not** independent AI formant conversion)
- Input/output/soundboard meters and callback telemetry
- XRuns / over-budget callback counter

## Soundboard / music player

The Soundboard shares the virtual-microphone path with the voice changer, so callers can hear processed microphone audio and local media together.

- WAV, MP3, OGG, FLAC and AIFF import
- Streaming decode/resampling instead of loading long songs fully into RAM
- Background decoding with bounded buffers
- Play, pause, stop and stop-all
- Overlap or one-at-a-time mode
- Per-sound volume metadata and master volume
- microphone ducking while media plays
- loop, trim and non-destructive fade metadata
- global hotkeys through `pynput` when supported by the desktop session
- persistent local library

On Linux/Wayland, desktop security policy may prevent global key capture. OxShift continues to work when the global-hotkey listener is unavailable.

## Local AI / RVC runtime

The AI Models page can catalog `.onnx`, `.pth` and `.index` files. OxShift also has a realtime conversion stage that runs inference on a worker thread instead of inside the PortAudio callback.

The runtime uses bounded input/output queues. If an AI backend misses the realtime budget, the callback does not wait for it: work can be dropped and OxShift can fall back to passthrough audio instead of freezing the device stream. Runtime telemetry tracks dropped work, output underruns, inference time, peak time and adapter errors.

RVC bundles can use an `oxshift-rvc.json` manifest rather than treating arbitrary ONNX graphs as interchangeable:

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

Full RVC conversion still requires a validated content-encoder/F0/synthesizer adapter; imported models are not executed blindly.

## Linux quick start

Requirements: Python 3.10+, PipeWire/PulseAudio compatibility (`pactl`) and PortAudio.

```bash
sudo apt install python3-venv portaudio19-dev pulseaudio-utils
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

./scripts/linux_virtual_mic.sh create
python -m voxshift
```

Select the physical microphone as input and the OxShift/VoxShift virtual sink as output. In Discord, OBS, Zoom or a game, select **VoxShift Microphone** / `voxshift_mic` as the microphone source.

Remove Linux virtual devices with:

```bash
./scripts/linux_virtual_mic.sh remove
```

## Optional AI runtime

```bash
pip install -r requirements-ai.txt
```

GPU provider packages remain platform-specific because CUDA/DirectML availability differs by machine.

## Architecture

```text
voxshift/
├── audio_engine.py   # realtime microphone + VC + DSP + mixer callback
├── dsp.py            # local DSP rack and realtime pitch backend
├── voices.py         # declarative voice preset catalog
├── soundboard.py     # persistent streaming soundboard/mixer
├── recorder.py       # bounded-queue background WAV recorder
├── profiles.py       # validated, atomic studio-profile persistence
├── diagnostics.py    # privacy-safe engine health snapshots
├── hotkeys.py        # optional global hotkey listener
├── ai_models.py      # local model registry and provider detection
├── rvc_runtime.py    # async VC worker and bundle validation
├── pro_ui.py         # current OxShift Studio interface
└── ui.py             # previous interface retained during transition
```

The realtime callback does not perform media file reads, slow AI inference or recording disk writes synchronously.

## Privacy and responsible use

OxShift is local-first. The application does not upload microphone audio, soundboard media or imported voice-model files. AI voice conversion should be used with models and voices you have the right and consent to use; the project is not intended for deceptive impersonation.

## Tests

```bash
python -m unittest discover -s tests -v
```

GitHub Actions runs the suite on supported Python versions for pull requests.

## Next engineering milestones

- validated ONNX adapters for ContentVec/HubERT + RMVPE/FCPE + RVC synthesizer graphs
- WebRTC/RNNoise-style noise suppression and automatic microphone conditioning
- configurable, reorderable effect chains / VoiceLab-style custom voices
- Soundboard waveform editor, folders/playlists and richer per-sound controls
- device reconnect/recovery and saved device routing
- native Windows virtual-audio setup and installer flow
- Linux and Windows packaging, release artifacts and update strategy
- long-running audio stress tests and latency benchmarks
