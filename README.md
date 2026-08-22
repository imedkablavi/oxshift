# OxShift

Local-first real-time voice changer MVP for Linux, with a cross-platform audio core designed to grow toward Windows and AI voice conversion.

## Current MVP

- Real-time microphone capture/output via `sounddevice`
- Presets: Clean, Radio, Robot, Anonymous
- Gain, wet/dry mix, noise gate
- Input/output device selection
- Live input/output meters
- Linux virtual microphone helper for PipeWire/PulseAudio compatibility
- Local processing only; no network upload
- Small test suite for DSP blocks

## Linux quick start

Requirements: Python 3.10+, PipeWire/PulseAudio compatibility (`pactl`), PortAudio.

```bash
sudo apt install python3-venv portaudio19-dev pulseaudio-utils
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Create a virtual microphone
./scripts/linux_virtual_mic.sh create

# Launch
python -m voxshift
```

In OxShift, choose your physical microphone as **Input** and a playback device corresponding to `VoxShift Output` / `voxshift_sink` as **Output**. In Discord/OBS/Zoom, choose **VoxShift Microphone** / `voxshift_mic` as the microphone.

Remove the virtual devices with:

```bash
./scripts/linux_virtual_mic.sh remove
```

## Architecture

`audio_engine.py` owns the real-time stream. `dsp.py` contains allocation-light DSP blocks. `ui.py` is deliberately separated from the engine so a future native UI can replace Tk without rewriting audio processing.

The production roadmap is to move the real-time DSP/audio engine into Rust/C++ while keeping UI and model-management decoupled, then add Windows virtual audio support and optional local AI inference.

## Safety / privacy direction

OxShift is designed for user-controlled voice effects and consent-based voice models. The MVP has no cloud transport or voice cloning.
