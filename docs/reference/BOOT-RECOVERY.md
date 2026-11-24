# Boot and recovery constraints

This applies only to the TB-J706F port. It is not a stock-to-Linux installation
procedure. Configure the identity of your own existing installation using
[the local configuration guide](../07-persistent-installation.md).

## Preserve the recovery path

- Keep a previously accepted boot image and its manifest outside Git.
- Preserve signed boot firmware, calibration and the partition layout. Never
  flash modified ABL/XBL, erase firmware partitions, merge A/B slots, or guess GPT
  flag masks to diagnose a failed boot.
- If Android remains installed, restore its matching stock DTBO before booting
  it. The neutral DTBO used by this Linux port is not an Android replacement.
- Never probe GPIO59–62 or hot-unbind Bluetooth. Audio tests retain protection
  firmware. A compiled image is not a booted image or a hardware acceptance test.

## RAM boot testing

Use a data-capable USB connection and verify the intended device before sending
anything. Fastboot response alone does not establish a successful Linux boot.
The reference device has required explicit slot-A refresh before RAM tests:

```sh
fastboot -s "$DEVICE_SERIAL" --set-active=a
fastboot -s "$DEVICE_SERIAL" getvar current-slot
fastboot -s "$DEVICE_SERIAL" getvar slot-unbootable:a
fastboot -s "$DEVICE_SERIAL" getvar slot-retry-count:a
fastboot -s "$DEVICE_SERIAL" boot "$J706F_BUILD_ROOT/artifacts/current-test.img"
```

`DEVICE_SERIAL` must be your verified device serial, kept in local configuration.
Do not use these commands with an unidentified device. The slot workaround is
not a proven repair of Lenovo's failure handling. Do not replace `boot` with
`flash` as part of development testing without a separate explicit install plan.

Afterward verify the running kernel, intended boot parameters, writable root and
filesystem error count. Obtain visual/audio acceptance separately. Lenovo ABL
has dropped the extended boot-header command line; test controls and root
identity must fit the legacy field and be checked on the running kernel.

## Filesystem recovery

Repair requires a separate RAM recovery with all internal filesystems unmounted
and internal swap disabled. Read-only mounting is not equivalent to unmounting.
The maintenance tools verify device identity, geometry, mount/swap absence and
read-only policy before checking. Repair is a separate explicit conservative
request, followed by an independent read-only check. They are tied to the
reviewed filesystem layout; do not weaken guards to make another layout pass.

No source cleanup or publication command authorizes device access, partition
writes or filesystem repair. Raw evidence and metadata captures stay private.
