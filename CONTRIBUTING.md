# Contributing

Start with [the project guide](docs/00-start-here.md), the current
[known issues](docs/03-problems-and-tests.md), and [technical milestones](docs/06-experiment-journal.md).
The repository contains an experimental board port and a full kernel source tree.
A documented fix for one development tablet is not automatically a tested release
for every TB-J706F.

## Keep changes focused

Use the single `kernel/` tree and one external build directory. Use Git branches
and commits for experiments rather than copying source or build trees. Follow
`AGENTS.md` when using an assistant. Keep kernel changes, tools and unrelated
cleanup in separate logical commits, each with the relevant documentation.

Preserve upstream copyright and license identifiers. Check [LICENSE](LICENSE)
and [NOTICE](NOTICE) before adding third-party code or binary assets. Contributions
must identify their origin and use the applicable component's license. Do not
copy proprietary firmware, calibration or stock system images into Git.

## Build and validate

Use `scripts/build.sh` and `scripts/package.py` as described in the
[build guide](docs/01-boot-and-build.md). Inspect `git diff --check` and the staged
diff before committing. For kernel patches, run the kernel's checkpatch tool on
the patch and explain unresolved findings. Run the tests relevant to the changed
behavior; do not describe a build or packaging check as a hardware test.

For each experiment record:

- The problem and specific hypothesis; which behavior changed.
- Source revision and configuration, image/root hashes and matching manifests.
- Build, packaging and host-side validation results, including failures.
- Actual boot identity and relevant device observations.
- User visual/audio acceptance and recovery, separately from command success.
- Remaining uncertainty and links to sanitized, available evidence.

Update the technical milestones and known issues at meaningful checkpoints.
Retain failed and inconclusive technical results; a later success should explain
what it supersedes. Keep raw operational logs and personal notes outside Git.

## Device work

Read [boot recovery](docs/reference/BOOT-RECOVERY.md) and
[USB handoff](docs/reference/HANDOFF-LINUX-USB.md), then the current known issues.
Preserve an accepted image and manifest. Default
experiments RAM-boot through fastboot; storage writes need a separate reviewed
plan and the device owner's authorization. A failed kernel boot does not justify
a reset, firmware erase or speculative bootloader patch.

Do not probe GPIO59–62, hot-unbind Bluetooth, or bypass speaker-protection
firmware. Do not treat screen blanking as successful suspend or electrical
power-off. Do not repair a mounted root filesystem; use verified offline
maintenance with internal mounts and swap checked first.

Never publish passwords, SSH keys, network credentials, account databases,
personal files, raw private device dumps or authentication URLs. Redact serials,
network names and other identifying data when sharing logs. Preserve useful
technical context and state exactly what was removed.

## Propose and review

Explain the concrete trigger and expected result. Include validation actually
performed and material limitations. Separate source review from hardware
acceptance, and explain any dependence on externally retained evidence.

Before requesting inclusion, verify that documented commands work from the
repository root with an explicitly selected external build directory. Keep
public entry points free of machine-specific paths. Machine-specific
configuration, raw logs and personal records belong outside
the public source.

For security-sensitive findings follow [SECURITY.md](SECURITY.md), rather than
posting private dumps in an ordinary issue.
