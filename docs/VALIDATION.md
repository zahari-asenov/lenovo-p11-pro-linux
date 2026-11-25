# Publication validation

Local validation completed on 2026-11-25. Nothing has been published.

## Source and host checks

- ARM64 kernel and J706F power device tree built with `scripts/build.sh` in the external build directory. Existing device-tree warnings remain; this is not a warning-free build claim.
- Host gate passed: Python compilation, shell syntax, public JSON consistency, workflow/template YAML, persistent-root selection mocks, isolated contrast settings, private configuration rejection and shell round-trip, synthetic Bluetooth DTB modification, charging policy, exhaustive brightness mapping, packaging round-trip and installer write/hash boundaries.
- Seven unconfigured device/preparation commands rejected public templates before payload reads, network access or output creation.
- Public documentation links and heading anchors passed review.
- Publication source changes have not been booted or installed on the tablet. GitHub workflows are defined but have not run on GitHub. A fresh system-toolchain build in CI remains an independent check.

## Accepted device behavior

The installed display image predates publication-only cleanup. Its brightness clock fix and smooth minimum-to-maximum adjustment were visually accepted by the user after persistent installation. The sanitized [release record](../configs/releases/display-2026-11-25.json) separates source, image, partition readback and device observations. New host checks do not expand that hardware acceptance.

Filesystem repair passed independent offline checks and the subsequent installed system mounted writable without recorded new errors. The original corruption trigger remains unknown; these checks do not certify storage hardware health.

## Publication boundaries

Only the clean publication branch is intended for distribution. Original investigation refs and detailed records remain private. See [publication audit](PUBLICATION-AUDIT.md) and [release procedure](RELEASING.md). No tablet storage operations were performed during this cleanup.
