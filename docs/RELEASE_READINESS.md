# OxShift 0.3 Alpha release-readiness report

Status legend: **PASS** implemented/verified by automated tests, **PARTIAL** implemented but still needs platform/hardware evidence, **BLOCKED** required evidence is not yet available.

| Area | Status | Evidence / remaining work |
|---|---|---|
| Realtime callback boundary | PASS | AI inference uses bounded worker queues; soundboard decoding and recorder disk writes are off-thread; device recovery only signals from callbacks and reopens on a worker. |
| Audio device reconnect/recovery | PARTIAL | Stable name/host-API resolution and asynchronous recovery are implemented and unit-tested. Physical USB/Bluetooth/PipeWire/WASAPI disconnect/reconnect soak remains manual. |
| Windows virtual microphone | PARTIAL | User-level endpoint detection helper + installer flow are implemented. Alpha deliberately relies on a separately installed signed virtual-audio driver rather than bundling an unsigned/custom kernel driver. Real VB-CABLE/VoiceMeeter routing must be verified on Windows hardware. |
| Model execution trust boundary | PASS | Raw ONNX/PTH are quarantined. Allow-listed bundles require manifest validation, path containment, size limit, SHA-256 and expected ONNX I/O signature. `.pth` execution is disabled. |
| Validated ONNX adapter | PARTIAL | `oxshift-rvc-stream-v1` adapter exists and runs through the existing VC worker. Additional real-world RVC graph families require separate schemas/adapters; they are not guessed. |
| Noise suppression / mic conditioning | PASS | Built-in adaptive cleanup + AGC and optional WebRTC backend are exposed in Alpha Studio and persisted in profiles. |
| Reorderable effects chain | PASS | Stage ordering/bypass is implemented in DSP, exposed in Alpha Studio and profile-persistent. |
| Soundboard editor / playlists | PASS | Background waveform preview, trim/fade/loop/volume metadata editor and persistent playlists are implemented. |
| Latency/XRun/underrun telemetry | PARTIAL | Offline callback-budget benchmark plus runtime callback/XRun and VC queue/underrun counters exist. Physical end-to-end latency still requires loopback hardware measurement. |
| Multi-hour stress/leak | PARTIAL | 2-hour paced harness and manual Actions workflow exist; PR CI runs accelerated smoke. Full multi-hour hardware/device soak must be completed for the release candidate. |
| Linux packaged build | PENDING CI | PyInstaller package job produces a Linux x86_64 tarball. Must remain green on the PR/tag runner. |
| Windows packaged build | PENDING CI | PyInstaller portable ZIP and Inno Setup installer are configured. Must remain green on the PR/tag runner. |
| Release checksums/signing | PARTIAL | Tag workflow generates SHA-256, keyless-signs artifacts with Sigstore/Cosign, verifies provenance, then publishes. A disposable/test Alpha tag should verify the end-to-end release path before broad distribution. |
| Safe auto-update | PARTIAL | Fail-closed staged/checksum/Sigstore/atomic-swap/rollback design is documented. Write-capable unattended updater is intentionally disabled in this Alpha until the trust chain is proven. |
| Studio UI / legacy isolation | PASS | `python -m voxshift` launches `OxShiftAlphaUI`; legacy modules remain importable only for rollback/reference and are no longer in the entrypoint. |
| README/install documentation | PASS | README now documents Alpha architecture, Windows/Linux install/routing, AI validation, benchmarks, release integrity and limitations. |
| Real screenshots/demo | BLOCKED | Must be captured from actual packaged Alpha builds with real routing. Generated mock screenshots are intentionally not used as product evidence. |
| GitHub metadata/social preview | READY TO APPLY | Proposed description, topics and social-preview composition are in `docs/PRODUCT_METADATA.md`. Repository settings/social image require a GitHub UI/API metadata action not part of the code change. |

## Alpha promotion rule

Do not present `0.3.0-alpha.1` as broadly release-ready until all of the following are true:

1. PR Linux and Windows unit-test/package jobs are green.
2. The realtime benchmark/stress-smoke artifact is green and reviewed.
3. A 2+ hour paced soak completes without unbounded Python allocation/thread growth or invalid audio blocks.
4. USB/virtual-device disconnect/reconnect is tested on at least one Linux PipeWire system and one Windows WASAPI system.
5. VB-CABLE or equivalent signed endpoint routing is validated with Discord/OBS/Zoom or equivalent capture software.
6. A test/pre-release tag proves checksum generation, Cosign signing, verification and release upload.
7. Real screenshots and a short demo are captured from the packaged build.

## Explicit non-goals for this Alpha

- silently installing a Windows kernel-mode virtual audio driver;
- executing arbitrary imported ONNX/PyTorch files;
- claiming universal compatibility with every RVC graph family;
- claiming “zero latency” or publishing synthetic benchmark numbers as hardware round-trip measurements;
- unattended self-update before signature verification and rollback are implemented and exercised end-to-end.
