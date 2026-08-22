# OxShift

OxShift is a local-first real-time voice changer for Linux, built around a low-latency DSP engine and a desktop interface designed to grow into local AI voice conversion.

## Current build

### Dashboard

- Dark desktop dashboard with clear navigation
- Quick voice selection
- Live microphone and virtual-output meters
- Engine state and local-processing indicator
- Dedicated Dashboard, Voices, Studio and Audio sections

### Voice library

OxShift now ships with a structured preset catalog instead of hard-coded effect names. Presets have categories, descriptions and their own DSP configuration.

Built-in voices include:

- Clean
- Broadcast
- Deep
- Bright
- Anonymous
- Robot
- Android
- Radio
- Telephone
- Intercom
- Ghost
- Cyber
- Megaphone
- Low-Fi

The library supports category filtering and text search. Preset data lives in `voxshift/voices.py`, so new voices can be added without modifying the UI or audio callback.

### Real-time DSP rack

The current local DSP pipeline supports:

- Noise gate
- High-pass / low-pass tone shaping
- Soft saturation / drive
- Ring modulation
- Tremolo
- Streaming-safe short echo
- Lightweight dynamics compression
- Wet/dry mix
- Output gain with safe clipping

The real-time callback remains separated from the UI, and DSP state is kept inside the audio engine path.

## Linux quick start

Requirements: Python 3.10+, PipeWire/PulseAudio compatibility (`pactl`), PortAudio.

```bash
sudo apt install python3-venv portaudio19-dev pulseaudio-utils
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Create the virtual microphone
./scripts/linux_virtual_mic.sh create

# Launch OxShift
python -m voxshift
```

In **Audio**, choose your physical microphone as input and the playback device corresponding to the OxShift virtual sink as output. In Discord, OBS, Zoom or another application, choose **OxShift/VoxShift Microphone** as the microphone source.

Remove the virtual devices with:

```bash
./scripts/linux_virtual_mic.sh remove
```

## Architecture

```text
voxshift/
├── audio_engine.py   # real-time device stream and levels
├── dsp.py            # stateful streaming DSP rack
├── voices.py         # voice/preset catalog
├── ui.py             # desktop dashboard and voice browser
└── __main__.py       # application entry point
```

The next production milestones are true pitch/formant processing, configurable effect chains, soundboard/hotkeys, preset persistence, recording, measured latency telemetry, native Windows virtual audio support, and optional local RVC/ONNX inference.

## Design direction

OxShift takes product-level ideas from the broader open-source voice-changing ecosystem—voice libraries, realtime meters, separate studio controls, effect racks and local inference—while keeping its own implementation and UI.

## Safety and privacy

OxShift is designed for user-controlled voice effects and consent-based voice models. Audio processing is local in the current build; there is no cloud transport or built-in voice cloning.
