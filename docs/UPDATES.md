# Safe update design

OxShift Alpha uses a **check-and-verify-first** release model. The application must never replace itself merely because a newer file exists on GitHub.

## Release trust chain

Every tagged release is expected to publish:

- platform package(s),
- `SHA256SUMS.txt`,
- a Sigstore/Cosign bundle for each distributable artifact,
- generated GitHub release notes.

The release workflow signs blobs with GitHub OIDC through Sigstore. Checksums protect accidental corruption; the Sigstore bundle provides provenance/signature verification.

## Updater state machine

A future in-app updater must use this order:

1. Fetch only release metadata over HTTPS.
2. Compare semantic versions and reject downgrades unless the user explicitly requests rollback.
3. Download the candidate package to a staging directory, never over the running install.
4. Verify the expected SHA-256 digest.
5. Verify the Sigstore bundle/provenance against the OxShift GitHub repository identity.
6. Verify package/platform/architecture metadata.
7. Stop audio cleanly and launch a separate updater process.
8. Atomically swap the staged package into place.
9. Keep the previous version until the new version launches and passes a health marker.
10. Roll back automatically if startup/health validation fails.

Any verification failure must abort the update and leave the current installation untouched.

## Alpha behavior

`0.3.0a1` does not perform unattended self-updates. Release metadata/checksum/signature production is implemented first so the trust chain exists before write-capable auto-update code is enabled. This avoids shipping an updater that can download and execute arbitrary artifacts.

Windows driver installation is explicitly separate from application updates. An application update must never silently install or replace a virtual-audio kernel driver.
