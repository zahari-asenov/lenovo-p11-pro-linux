# Native Linux on the Lenovo Tab P11 Pro (TB-J706F)

Board support, kernel changes and development tools for running native ARM64
Linux on the **Lenovo TB-J706F**. The current development tablet runs Debian 13
with GNOME from internal storage, independently of a host computer. Both boot
slots contain Linux and share one persistent root filesystem.

This is an experimental device port, not a general installer or an official
Lenovo distribution. The kernel source is included under `kernel/`.

## Current hardware status

Status reflects observed operation on the development tablet, most recently
checked on **25 November 2026**. It is not a guarantee for another unit or firmware.

| Feature | Observed status |
| --- | --- |
| Internal-storage Linux startup | Working; normal slot A startup checked, both boot partition contents verified |
| Display and brightness | Installed clock-handling fix accepted; smooth adjustment with an approximately 10–100% active brightness range, separate blank/off |
| Accelerated GNOME, touchscreen, keyboard and touchpad | Working; advanced gesture support remains incomplete |
| Wi-Fi and Bluetooth headphones | Working |
| Built-in speakers | Protected audio accepted, including loud and clear browser playback |
| Battery and ordinary wall charging | Working with measured charging improvements; complete fast-charge negotiation/charge-pump operation is not accepted |
| Suspend and shutdown while charging | Unresolved; screen-off/charging-only behavior is not proof of electrical power-off or reliable sleep |
| Cameras, flashlight and microphone | Not established as working |

These hardware results describe the accepted installed reference system, not a
new device test of later source-publication changes. In particular, the public
DT no longer embeds a fixed Bluetooth address; firmware without a usable identity
requires private local configuration as described in the build guide.

The brightness floor describes the panel command range, not calibrated luminance.
The tested route retains the board-specific command-controller option; its
independent effect has not been isolated. The clock trace identified redundant
live shared-PLL retuning, and the accepted fix avoids that retuning while the
link is active. Earlier unsuccessful experiments remain in the journal.

A separate filesystem corruption incident was repaired offline without a wipe.
Subsequent integrity checks passed; its original cause remains undetermined.

## Start here

- [Project guide](docs/00-start-here.md)
- [Build and boot modes](docs/01-boot-and-build.md)
- [Release preparation](docs/RELEASING.md) and [accepted display-update provenance](configs/releases/display-2026-11-25.json)
- [Known problems and tests](docs/03-problems-and-tests.md) and [technical experiment journal](docs/06-experiment-journal.md)
- [Contributing](CONTRIBUTING.md), [security reporting](SECURITY.md), and [licensing](LICENSE)

Use a single source checkout and an external build directory:

```sh
./scripts/setup-host.sh
export J706F_BUILD_ROOT="$HOME/j706f-build"
export J706F_TOOLCHAIN_MODE=system
./scripts/build.sh
```

Read the build guide first for host prerequisites, toolchain setup and packaging
inputs. A clean clone provides source, not a prepared desktop root image,
proprietary device firmware, private credentials or a ready-to-flash release.
The normal build and packaging commands do not install anything on a tablet.

## Development and recovery

`kernel/` is the sole active kernel tree. Keep generated files, images, root
filesystems and private state outside the checkout. Use branches and commits for
experiments. Package with `scripts/package.py`; inspect the adjacent manifest
before a device test. Packaging validation and an actual successful boot are
separate results.

Read [boot recovery](docs/reference/BOOT-RECOVERY.md) and
[USB handoff](docs/reference/HANDOFF-LINUX-USB.md) before device work. Development
normally uses `fastboot boot`, not partition writes. A/B bootloader behavior and
recovery constraints still apply even though Android userspace was removed from
the development tablet.

Retain a previously accepted `known-good.img` and its manifest separately from
`current-test.img`. Artifact roles are local; their filenames do not identify a
universal release. Machine-specific configuration, raw logs, private artifacts
and personal notes are excluded from the public source. Configure the intended device locally;
public templates are not a validated partition inventory.

Never commit account state, SSH keys, Wi-Fi secrets, calibration dumps or private
root images. Firmware extracted from a device does not acquire a redistribution
license by being used with Linux. See [NOTICE](NOTICE) for source provenance.
