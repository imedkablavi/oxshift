# Changelog

All notable user-facing changes to OxShift are documented here.

The project follows Semantic Versioning. Pre-release versions use `aN` in the Python package and `-alpha.N` in Git tags/releases.

## 0.3.0-alpha.1 — unreleased

### Added

- OxShift Alpha Studio as the default application shell.
- Audio device identity tracking and asynchronous reconnect/recovery after USB/Bluetooth/virtual endpoint re-enumeration.
- Microphone conditioning controls for noise suppression, AGC and the optional WebRTC backend.
- Reorderable/bypassable custom effects chain persisted in studio profiles.
- Soundboard waveform preview, non-destructive trim/fade/loop editing and persistent playlists.
- Strict allow-listed ONNX bundle validation with manifest schema, path containment, size limits, SHA-256 and ONNX I/O signature checks.
- `oxshift-rvc-stream-v1` validated streaming ONNX adapter for the existing background VC worker.
- Windows virtual-microphone endpoint detection helper and Inno Setup installer strategy.
- Linux and Windows packaged build jobs.
- Offline latency/budget benchmark, accelerated stress test and manual multi-hour soak workflow.
- SHA-256 and keyless Sigstore/Cosign signing for release artifacts.

### Changed

- Raw `.onnx` imports are cataloged as quarantined until wrapped in a validated OxShift bundle.
- `.pth` model execution is disabled for Alpha because arbitrary PyTorch pickle loading is outside the local model trust boundary.
- Legacy UI modules remain in-tree for rollback, but the package entry point no longer imports or launches them.
- Diagnostics schema v2 reports callback errors, device recovery, cleanup backend and the real VC queue/inference counters.

### Security / privacy

- Slow AI inference remains outside the PortAudio callback.
- Media decoding and recording disk I/O remain worker-thread operations.
- Device re-enumeration/reopen work runs on a recovery thread, never the realtime callback.
- Application updates do not silently install or replace Windows kernel audio drivers.
- Unattended self-update remains disabled until checksum and Sigstore verification can be enforced end-to-end.

### Known Alpha limitations

- A real Windows virtual microphone still depends on a user-installed signed virtual-audio driver such as VB-CABLE/VoiceMeeter; OxShift does not bundle a kernel driver.
- Real RVC ecosystems expose multiple incompatible graph layouts. Alpha executes only the documented allow-listed streaming schema; arbitrary RVC graphs are deliberately rejected.
- Hardware round-trip latency, Windows WASAPI/virtual-cable recovery and a full multi-hour physical-device soak must be validated on release-candidate machines before promoting the Alpha beyond pre-release status.
