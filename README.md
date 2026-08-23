# OxShift

**Local-first real-time voice changer, soundboard and voice studio for Windows and Linux.**

OxShift routes a physical microphone through low-latency DSP, microphone conditioning, optional validated local ONNX voice conversion, a streaming soundboard and a virtual-audio endpoint — without sending microphone audio to a cloud service.

> **Status: 0.3.0 Alpha candidate.** Core DSP/soundboard/profile/recording paths are usable. Packaged builds, recovery and release hardening are being validated in the Alpha PR. Treat the current release line as pre-release software, not as a production audio driver.

## Why OxShift

- **Local-first:** microphone audio, soundboard media and model files stay on the machine.
- **Realtime-safe architecture:** disk decoding, WAV writes, model validation and AI inference do not block the PortAudio callback.
- **Voice Studio:** pitch, timbre/color, gain, gate, filtering, saturation, modulation, delay and compression.
- **Custom effects chain:** reorder or bypass individual DSP stages and save the result in profiles.
- **Microphone conditioning:** adaptive built-in noise suppression/AGC plus an optional WebRTC backend when available.
- **Soundboard:** WAV/MP3/OGG/FLAC/AIFF, waveform preview, trim, fades, loop, ducking, playlists and hotkeys.
- **Recovery:** re-resolves audio devices by stable identity after USB/Bluetooth/virtual-device re-enumeration and retries outside the realtime thread.
- **Validated local AI:** arbitrary imported models are quarantined; only allow-listed, checksummed ONNX schemas can become executable adapters.
- **Windows + Linux packaging:** portable/application packages are built in CI; Windows installer setup is separated from kernel virtual-audio drivers.

## Product preview

The Alpha entry point launches **OxShift Studio** with Home, Voices, Soundboard, Studio, Profiles, AI Models and Audio pages. The older UI implementations remain in the repository only as a rollback/reference path and are no longer launched by `python -m voxshift`.

Real release screenshots and the short demo must be captured from an actual packaged Alpha build rather than generated mock UI. The capture specification is in [`docs/PRODUCT_METADATA.md`](docs/PRODUCT_METADATA.md). Until those assets are captured, screenshots are intentionally not faked in this README.

## Install

### Windows Alpha

For release builds, use either:

- `OxShift-Setup-<version>-windows-x86_64.exe` — user-level installer, or
- `OxShift-<version>-windows-x86_64-portable.zip` — portable build.

OxShift itself is an application, not a Windows kernel audio driver. To expose processed audio as a microphone, install a signed virtual-audio endpoint you trust (for example VB-CABLE/VoiceMeeter), then route:

```text
Physical microphone
      ↓
   OxShift
      ↓
CABLE Input / virtual playback endpoint
      ↓
CABLE Output / virtual recording endpoint
      ↓
Discord / OBS / Zoom / game chat
```

The installer ships a detection helper that checks for compatible endpoints but does **not** silently download or install a driver:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\setup_virtual_mic.ps1
```

See [`docs/WINDOWS_VIRTUAL_MIC.md`](docs/WINDOWS_VIRTUAL_MIC.md).

### Linux Alpha

Requirements: Python 3.10+, PipeWire/PulseAudio compatibility (`pactl`) and PortAudio.

```bash
git clone https://github.com/imedkablavi/oxshift.git
cd oxshift
./scripts/install_linux.sh
```

For Bazzite/Fedora Atomic, the installer automatically switches to the Distrobox-safe path instead of layering packages onto the immutable host.

To create/remove the PipeWire/Pulse virtual microphone manually:

```bash
./scripts/linux_virtual_mic.sh create
./scripts/linux_virtual_mic.sh remove
```

Select your physical microphone as OxShift input and the OxShift/VoxShift virtual sink as output. In Discord/OBS/Zoom/game chat, select the paired `voxshift_mic` / **VoxShift Microphone** source.

### Run from source

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m voxshift
```

Optional ONNX runtime:

```bash
pip install -r requirements-ai.txt
```

GPU provider packages remain platform-specific; OxShift does not assume CUDA/DirectML is available.

## Realtime audio architecture

```text
Physical mic
    │
    ▼
Mic conditioning ──► VC queue ──► local DSP chain ──┐
                     │                               │
                     └─ AI worker thread             ├─► final mix ─► virtual output
                                                     │
Soundboard decoder threads ─► bounded audio queues ──┘
                                                     │
                                                     └─► recorder queue ─► WAV writer thread
```

The callback is intentionally constrained:

- no soundboard file reads/decoding;
- no recording disk writes;
- no model manifest/hash/graph validation;
- no blocking AI inference;
- no device re-enumeration/reopen work.

When a device disappears, a recovery worker re-queries PortAudio devices and resolves the saved device name/host API. The callback fails closed to silence on an internal error rather than performing slow recovery work itself.

## Voice Studio

Built-in presets include Clean, Broadcast, Deep, Bright, Anonymous, Robot, Android, Radio, Telephone, Intercom, Ghost, Cyber, Megaphone and Low-Fi.

The Studio page exposes:

- pitch and timbre/formant-color controls;
- wet/dry, gain and noise gate;
- microphone noise suppression and AGC;
- optional WebRTC processing when the backend is installed;
- reorderable `filter → pitch → timbre → drive → modulation → tremolo → echo → compressor` chain;
- per-stage bypass;
- profile persistence for the complete chain and conditioning state.

The timbre/formant-color control is spectral coloring, not independent neural formant conversion.

## Soundboard

The Soundboard mixes through the same final virtual-microphone path as processed speech.

Features:

- WAV, MP3, OGG, FLAC and AIFF import;
- background streaming decode/resampling with bounded buffers;
- play/pause/stop, overlap control and mic ducking;
- waveform preview;
- non-destructive trim start/end;
- fade in/out and loop;
- per-sound volume;
- persistent named playlists;
- global hotkeys where the desktop session permits them.

On Linux/Wayland, compositor/security policy may block global key capture. OxShift remains usable without global hotkeys.

## Local AI model trust boundary

OxShift does **not** run arbitrary imported `.onnx` or `.pth` files.

Raw ONNX/PTH imports are cataloged as **quarantined**. PyTorch `.pth` execution is disabled in Alpha because pickle-backed model loading is outside the trust boundary. An executable Alpha ONNX bundle must use an allow-listed schema and an `oxshift-model.json` manifest, stay inside its bundle directory, match a pinned SHA-256 digest and expose the exact expected ONNX inputs/outputs.

Current allow-listed schema: `oxshift-rvc-stream-v1`.

Example manifest:

```json
{
  "name": "My validated voice",
  "schema": "oxshift-rvc-stream-v1",
  "version": 1,
  "sample_rate": 48000,
  "model": "model.onnx",
  "sha256": "<64-character SHA-256 of model.onnx>"
}
```

The `oxshift-rvc-stream-v1` graph contract is deliberately narrow:

```text
inputs:  audio [float32 mono block], pitch_shift [float32 scalar]
output:  audio [same-length finite float32 mono block]
```

Real-world RVC repositories use several mutually incompatible ContentVec/HubERT/F0/synthesizer layouts. Those are not guessed or blindly executed; additional adapters must be implemented and validated schema-by-schema.

## Profiles and diagnostics

Profiles persist voice/DSP values, mic conditioning, effect order/bypass state, soundboard settings, sample rate/block size and preferred input/output device names.

Diagnostics export intentionally excludes device names, usernames, sound paths and model filenames. It reports health data such as:

- callback/peak timing and XRuns;
- callback errors and recovery attempts/successes;
- cleanup and pitch backends;
- recorder queue drops;
- VC inference time, queue drops and output underruns.

## Benchmarks and stress tests

Fast offline callback-budget benchmark:

```bash
python scripts/benchmark_audio.py --seconds 3 --json benchmark.json --markdown benchmark.md
```

Default multi-hour paced stress/leak test (2 hours):

```bash
python scripts/stress_audio.py --duration 7200 --json stress.json --markdown stress.md
```

CI runs a short accelerated stress smoke and uploads the benchmark/stress reports as artifacts. `.github/workflows/soak.yml` provides an explicit multi-hour workflow for release-candidate validation.

These tests measure in-process processing budget/memory behavior. They do **not** replace physical-device round-trip latency and WASAPI/PipeWire XRun testing.

## Builds and release integrity

Pull requests build/test on Linux and Windows. Tagged releases rebuild the platform packages, generate `SHA256SUMS.txt`, then keyless-sign every distributable and the checksum file with Sigstore/Cosign using GitHub OIDC. The workflow verifies those signatures before publishing the release.

Safe update design is documented in [`docs/UPDATES.md`](docs/UPDATES.md). Alpha does not enable unattended self-update before end-to-end checksum/signature/rollback verification exists.

## Development and tests

```bash
python -m unittest discover -s tests -v
```

Important engineering files:

```text
voxshift/
├── alpha_ui.py          # default Alpha Studio shell
├── pro_ui.py            # Studio foundation reused by Alpha
├── audio_engine.py      # PortAudio callback + off-thread device recovery
├── audio_devices.py     # stable device identity/re-resolution
├── speech_processing.py # built-in/WebRTC mic conditioning
├── dsp.py               # realtime DSP rack + configurable effects chain
├── soundboard.py        # streaming soundboard/mixer
├── playlists.py         # UI-side persistent playlist sequencing
├── waveform.py          # bounded waveform preview generation
├── recorder.py          # bounded-queue background WAV recorder
├── profiles.py          # validated atomic profile persistence
├── diagnostics.py       # privacy-safe health snapshots
├── model_validation.py  # allow-list/checksum/ONNX graph trust boundary
├── rvc_adapters.py      # validated streaming ONNX adapter
└── rvc_runtime.py       # bounded async VC worker
```

## Privacy and responsible use

OxShift is local-first and does not upload microphone audio, soundboard media or imported voice models. Use voice models and voices only when you have the right and consent to do so. The project is not intended for deceptive impersonation.

## Alpha release gates

Before declaring `0.3.0-alpha.1` ready for broad testing, the project should have:

- green Linux + Windows tests and packaged-build jobs;
- a green callback-budget/stress smoke artifact;
- a completed multi-hour paced soak;
- physical PipeWire and Windows WASAPI/virtual-cable reconnect tests;
- real screenshots + a short demo captured from packaged builds;
- verification of checksum + Sigstore bundles from a test tag.

See the release-readiness report in [`docs/RELEASE_READINESS.md`](docs/RELEASE_READINESS.md).
