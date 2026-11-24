# Development workflow

Use one active kernel source tree and one external build directory. Track
experiments with Git branches and focused commits rather than copied source or
build trees. See [boot and build](01-boot-and-build.md) for setup.

```sh
git status --short
git switch -c codex/describe-change
export J706F_BUILD_ROOT="$HOME/j706f-build"
./scripts/build.sh
git diff --check
```

A complete source build is independent of device-specific root images, credentials
and operational configuration. Keep those inputs outside version control; local
configuration under `configs/local/` is ignored. Public templates contain
placeholders and must not be treated as a verified device inventory.

## Change and validation record

Keep a driver fix, tooling change and unrelated cleanup separate. A useful commit
explains the observed problem, why the change addresses it, tradeoffs and actual
validation. Review staged changes before committing:

```sh
git diff --cached
git diff --cached --check
```

For each experiment record:

- The specific hypothesis and changed behavior.
- Source revision, configuration and input hashes.
- Build, packaging and host-check outcomes, including failures.
- Actual boot identity and the relevant hardware observations.
- Visual/audio acceptance and recovery, separately from command success.
- Remaining uncertainty and a sanitized technical summary.

Update the [milestone record](06-experiment-journal.md) and
[known issues](03-problems-and-tests.md) at meaningful checkpoints. Preserve failed
and inconclusive technical results; do not publish raw chat transcripts, personal
study notes, unrestricted logs or private device state.

## Packaging and hardware tests

Commit before packaging when practical so the manifest identifies a clean source
revision. A later documentation commit does not change the source identity of an
older image. Keep accepted `known-good.img` and test `current-test.img` artifacts
with matching manifests outside the checkout.

Read [boot recovery](reference/BOOT-RECOVERY.md) and
[USB access](reference/HANDOFF-LINUX-USB.md) before device work. Normally use a RAM
boot and change one behavior at a time. Storage writes are a separate explicitly
authorized operation. Do not infer a boot or hardware fix from packaging success,
a firmware-load message or a bootloader response.

Never probe GPIO59–62, hot-unbind Bluetooth or bypass speaker protection. Do not
repair the mounted root filesystem. A screen-off result does not demonstrate
suspend or electrical power-off.

## Public-source preparation

Run `scripts/check-project.py` and the applicable checks. Review the final tree
and all references intended for publication for secrets and personal metadata.
See [RELEASING](RELEASING.md), [CONTRIBUTING](../CONTRIBUTING.md) and
[SECURITY](../SECURITY.md). Publishing a clean source export does not justify
pushing private maintainer history or bundling private firmware/root images.
