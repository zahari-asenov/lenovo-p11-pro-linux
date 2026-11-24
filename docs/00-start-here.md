# Project documentation

Native Linux board support for the Lenovo Tab P11 Pro **TB-J706F**. The reference
installation runs Debian 13/GNOME from internal storage, with two Linux boot slots
and one shared persistent root. This repository provides source and development
tools, not a general-purpose tablet installer.

## Guides

1. [Boot and build](01-boot-and-build.md): host setup, kernel compilation and packaging modes.
2. [Hardware map](02-hardware-map.md): board components and source locations.
3. [Hardware status and known issues](03-problems-and-tests.md): accepted behavior, limitations and failed approaches.
4. [Development workflow](05-development-workflow.md): focused changes, validation and experiment records.
5. [Technical milestones](06-experiment-journal.md): significant successes, failures and inconclusive tests.
6. [Persistent Linux architecture](07-persistent-installation.md): existing-root boot and update boundaries.
7. [Boot recovery](reference/BOOT-RECOVERY.md) and [USB access](reference/HANDOFF-LINUX-USB.md): prerequisites for device work.
8. [Release preparation](RELEASING.md): source-release validation and publication boundaries.

The [display acceptance record](../configs/releases/display-2026-11-25.json)
identifies the accepted installed update. It does not bundle a desktop root or
certify subsequent source revisions.

## Repository conventions

`kernel/` is the sole active kernel tree. Generated output belongs outside the
checkout under `J706F_BUILD_ROOT`. Device identities and operational configuration
are local inputs; public templates contain placeholders. Never commit credentials,
account state, private root images or raw device dumps.

A successful build, image roundtrip, boot, firmware load and visually/audibly
accepted feature are different results. Keep those distinctions in technical
records. Failed approaches remain summarized without publishing raw operational
logs or personal notes.

See [CONTRIBUTING](../CONTRIBUTING.md), [SECURITY](../SECURITY.md),
[LICENSE](../LICENSE) and [NOTICE](../NOTICE) for contribution, reporting and
component-licensing information.
