# Boot and build

## Architecture and boot modes

This is native ARM64 Linux. The repository includes the kernel source and board
configuration. Selected host-side checks use emulation; the desktop runs on the
tablet's own CPU and GPU.

```text
kernel/ + configs/j706f.config
    -> external Image.gz + board DTB
    -> kernel + DTB + bootstrap initramfs
    -> Android-format header-v2 boot image
```

The image format is a bootloader interface; it does not mean Android userspace
is required. Three distinct modes exist:

| Mode | Root filesystem and purpose |
| --- | --- |
| Persistent Linux | Internal ext4 root selected and validated by the bootstrap; normal installed desktop, no host download |
| Historical RAM-root desktop | Host-served external root archive downloaded into RAM; useful for older bring-up experiments |
| Maintenance recovery | Recovery tools run in RAM while installed filesystems remain unmounted; assessment is read-only unless repair is explicitly enabled |

The development tablet currently uses persistent Linux in both boot slots.
The slots contain boot images, not two separate copies of the desktop root.

## Host and source build

Use an ARM64 cross compiler on a Linux host. `scripts/setup-host.sh` checks host
commands and Python/Gio availability without installing anything. On Debian or
Ubuntu, `scripts/setup-host.sh --install` explicitly installs the listed packages
through apt and sudo. Review the script before using its installation mode.
The device-tree-compiler package must provide `dtc`, `fdtget` and `fdtput`; the
latter two are used for local configuration of the generated board DTB.
Python 3.11 or newer is required by current packaging tools; a command-presence
check does not establish header/library completeness or a successful build.
Packaging and root preparation additionally need their declared input artifacts;
these are not supplied by a source clone.

From the repository root, select one external build directory:

```sh
./scripts/setup-host.sh
export J706F_BUILD_ROOT="$HOME/j706f-build"
export J706F_TOOLCHAIN_MODE=system
./scripts/build.sh
```

System mode uses the host-installed cross compiler and development libraries.
The default `auto` mode selects a complete external bundled compiler when found,
otherwise system tools; `bundled` mode remains available for the original
maintainer environment. The build wrapper records compiler/configuration
provenance in the external `environment.json`; changing compilers does not
guarantee byte-identical output or device acceptance.

The default targets are `Image.gz` and
`qcom/sm7150-lenovo-j706f-power.dtb`. Output belongs under
`$J706F_BUILD_ROOT/kernel`, never in a second source copy. The configuration is
seeded from `configs/j706f.config` only when the external build has no `.config`.
Save intentional configuration changes back to the maintained configuration.

The reproducibility record pins the upstream source commit and source archive
hash in `configs/layout.json`. A source export does not need to include the
original upstream Git commit object or private maintainer references. Build
metadata records the actual project revision and dirty state.

## Private Bluetooth identity

The public board DTS does not contain a fixed Bluetooth address. The default
`configs/bluetooth.json` has a null `local_bd_address_le`. If firmware does not
supply a usable identity, configure a unique, valid unicast address privately in
`configs/local/bluetooth.json` or the matching file beneath `J706F_CONFIG_DIR`.
The field accepts six whitespace-separated hexadecimal bytes in device-tree
little-endian order. Do not commit that file or copy another device's address.

For the board DTB, `scripts/build.sh` invokes `scripts/apply-local-dtb.py` on the
external generated file. A configured identity is validated and read back before
replacement; missing/null configuration removes a stale local override. The
helper does not modify the source DTS or print the address. It requires `fdtget`
and `fdtput`. Consult the script and local configuration before packaging.

Removing a fixed identity is source hygiene, not a new hardware acceptance test.
The accepted installed display update predates this publication cleanup; a new
configured DTB needs its own Bluetooth and boot checks. A source-only build
without a local override must not be advertised as verified Bluetooth operation.

## Packaging is separate from building

The packager validates header/payload roundtrips, size and input provenance before
replacing the stable test artifact. It does not send commands to the device.
Choose the mode explicitly for persistent development:

```sh
python3 scripts/package.py --persistent
```

This requires a prepared persistent initramfs and private root provenance inputs.
It does not create an installation from a source-only checkout. The historical
RAM-root mode is the packager's default and requires its matching bootstrap and
root archive. `scripts/serve.sh` is for that host-download mode, not normal
installed startup. Maintenance has its own preparation and packaging options;
read the scripts and recovery records before enabling repair capability.

Public configuration templates contain placeholders. Keep actual target settings
in ignored `configs/local/` or an external `J706F_CONFIG_DIR`, and verify serials,
partition identities, hashes and credentials against that target. Do not copy the development tablet's
installation plan onto another unit. Private root preparation can include
account and network state and must not be served publicly or committed.

## Artifact roles and validation

Keep `artifacts/known-good.img` and its JSON manifest as an accepted recovery
point. Build and package new work as `artifacts/current-test.img` with its adjacent
manifest, all beneath the external build directory. The retained known-good
artifact may be older than the currently installed system; consult its own
manifest rather than assigning it the latest hardware acceptance.

Record source revision, image and root hashes, build/package checks, actual boot,
user observations and recovery separately in the technical milestone record.
A matching payload roundtrip proves packaging, not a successful device boot.

## Before device work

Read [boot recovery](reference/BOOT-RECOVERY.md),
[USB handoff](reference/HANDOFF-LINUX-USB.md), current known issues and the applicable
[contribution workflow](../CONTRIBUTING.md). Normally test with `fastboot boot`;
flashing or changing storage is a separate, explicitly authorized operation.

The development tablet's two slots contain Linux, but stock devices differ.
Do not boot stock Android with a Linux-neutral DTBO. Preserve bootloader,
calibration and required firmware partitions; an Android-related name does not
make a partition disposable. Never test modified ABL or arbitrary GPIO reads as
a recovery shortcut.

Explicitly refresh and verify slot A before RAM tests as documented in recovery.
That workaround has not established reliable bootloader failure handling.
A normal boot, fastboot command success and a clean filesystem assessment remain
separate observations. Repair the installed root only from a verified recovery
state with the target unmounted and swap inactive.
