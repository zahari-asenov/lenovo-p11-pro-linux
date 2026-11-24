# Persistent Linux architecture

This repository supplies kernel/board support and advanced development tools.
It is **not a general OS installer** and does not contain a redistributable desktop
root image, device credentials, factory calibration or a universal partition plan.

## Existing installation model

The development tablet runs Debian/GNOME from an internal ext4 filesystem. Both
boot slots contain Linux kernel/initramfs images referring to one shared root.
They are not two independent desktop installations. A separate data filesystem
provides additional Linux storage; partition identities and capacity are local
installation details, not public constants to copy onto another unit.

The persistent bootstrap:

1. Selects the configured root by stable partition identity.
2. Checks the expected device, partition name/size and Linux-root marker.
3. Performs the documented read-only validation before enabling the installed
   writable root and switching to systemd.

Normal installed startup does not download the desktop from the host. Firmware,
calibration and radio/audio userspace dependencies must already be available in
the target root. A running kernel alone does not supply them.

## Local configuration and artifacts

Public configuration files are templates with explicit placeholders. Real target
identities and operational plans belong in ignored `configs/local/` or an
external directory selected by `J706F_CONFIG_DIR`. The configuration loader
merges matching JSON filenames over tracked templates and validates device inputs
before device-specific operations. For example, an external location can be
selected without committing its contents:

```sh
export J706F_CONFIG_DIR="$HOME/.config/j706f"
```

Verify the loader's current configuration contract before packaging. Do not use an example serial, zero UUID,
example capacity or another tablet's inventory as a real target.

Build output, prepared initramfs, root provenance and image manifests live beneath
the external `J706F_BUILD_ROOT`. Preparing or packaging regular files does not
authorize changing a tablet. A private root may contain account/network state
and must not be committed or served publicly.

## Kernel-only updates

A RAM-booted test kernel can use an existing persistent root without replacing
it. This separates driver testing from OS installation. A later boot-image update
also need not replace applications or personal files, but requires its own exact
target inventory, reviewed write plan and device-owner authorization.

The accepted display update verified both boot partition contents and a normal
slot A startup. This does not mean every future image or separate slot B boot is
accepted. Keep the artifact's source/image identity and test results together.

Do not merge A/B partitions or remove bootloader, firmware or calibration as an
installation shortcut. On a stock device, Android must not be started with a
Linux-neutral DTBO. A loader failure before the bootstrap can still invalidate a
slot; sharing a Linux root does not repair that policy.

## Recovery and integrity

Read [boot recovery](reference/BOOT-RECOVERY.md) and
[USB access](reference/HANDOFF-LINUX-USB.md) before device work. Metadata repair
must run from verified recovery with the installed target unmounted and internal
swap inactive. Follow an independent check after repair; do not force a damaged
root writable to recover the desktop.

Current limitations and recurrence history are summarized in
[known issues](03-problems-and-tests.md) and [technical milestones](06-experiment-journal.md).
