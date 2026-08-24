# Windows virtual microphone strategy

OxShift Alpha does **not** install a kernel-mode virtual audio driver silently or bundle an unsigned driver. Windows virtual microphone support is built around a user-installed, signed virtual-audio endpoint.

## Supported Alpha routing

The tested routing model is:

1. Physical microphone -> OxShift input.
2. OxShift output -> a virtual playback endpoint such as **CABLE Input**.
3. Discord, OBS, Zoom, Teams, games, etc. -> the paired virtual recording endpoint such as **CABLE Output**.

VoiceMeeter-style routes are also compatible when they expose normal Windows audio endpoints.

Run the bundled helper from PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\setup_virtual_mic.ps1
```

It detects compatible endpoints and prints the route. It does not download a driver or request administrator privileges.

## Installer policy

The OxShift installer contains only the application, documentation and the endpoint-detection helper. A future native OxShift virtual driver would require a separately maintained Windows audio-driver project, EV/Attestation signing, HLK/compatibility testing and explicit elevated installation. That work is intentionally outside the Python Alpha installer so application updates cannot silently mutate kernel audio components.

## Failure behavior

If a virtual endpoint is missing or is unplugged/re-enumerated, OxShift's audio recovery worker retries device resolution by stable device name and host API outside the realtime callback. When the endpoint returns, the stream is reopened. If it does not return, OxShift stays in a waiting/recovery state instead of blocking the PortAudio callback.
