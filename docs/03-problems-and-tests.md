# Hardware status and known issues

Status: **25 November 2026**, for the development TB-J706F. These observations do
not establish support for another model or firmware revision. Source compilation,
packaging, actual boot and hardware acceptance are separate results.

## Accepted operation

| Area | Observed result | Limits |
| --- | --- | --- |
| Native startup | Debian 13/GNOME runs from internal ext4 storage without a host download. Both boot partitions contain verified Linux images. | Final display-update session verified normal slot A startup; B was not separately booted in that session. |
| Display | Accelerated desktop and touch input work. The installed live-clock fix and smooth brightness adjustment were visually accepted. | Tested route retains the board-specific command-master option; its independent contribution was not isolated. |
| Brightness range | Active requests map monotonically to approximately 10–100% of panel command range; blanking remains zero. | This is a command-code floor, not calibrated luminance. Logical readback uses the same scale as requests. |
| Keyboard and touchpad | Typing, pointer operation and globe-to-Super mapping work. | Advanced multi-finger gestures are incomplete. |
| Connectivity | Wi-Fi Internet and Bluetooth headphone pairing/playback were observed working. | Firmware/calibration and userspace dependencies must be present in the target root. |
| Speakers | Protected built-in audio and loud, clear browser playback were accepted after normal reboot. | Do not bypass amplifier protection. Per-speaker calibration adoption/balance was not independently certified. |
| Ordinary wall charging | Main-charger changes improved measured battery charging; the low-charge software lockout was corrected. | Short normal-temperature measurements are not a complete charge-cycle, thermal or battery-health certification. |
| Memory pressure handling | Prioritized compressed RAM swap and lower-priority disk swap started persistently; bounded swap integrity checks passed. | Heavy workloads can still stall. No general freeze root cause was established. |

Later source-publication changes, including removal of a fixed Bluetooth address,
are not additional device acceptance. Configure identity privately when firmware
requires it, then validate the resulting DTB on the target.

The [display acceptance record](../configs/releases/display-2026-11-25.json)
preserves the tested source/image identity. Subsequent source or documentation
changes do not retrospectively change that acceptance.

## Open issues

| Issue | Established evidence | Next useful validation |
| --- | --- | --- |
| Reliable suspend/resume | USB suspend returned EAGAIN; Linux resumed and Wi-Fi reconnected after an attempted sleep. | Isolate the USB/platform suspend failure and verify wake, display and radio recovery. |
| True power-off while charging | Charging-only startup stops the desktop and can blank the screen; the kernel still runs. | Determine supported firmware/PMIC behavior and measure actual system power state. |
| Complete fast charging | Main charging works; high-voltage negotiation and complete charge-pump policy are not accepted. | Validate adapter contract, fault/thermal limits, current coordination and interrupt delivery. |
| Filesystem corruption recurrence | Offline repairs passed, but metadata corruption recurred. The root became read-only and graphical login failed. | Retain first-failure evidence and distinguish interrupted writes, kernel/memory/persistence issues and storage hardware. |
| Dark-video/colour difference | Available comparisons did not establish a general near-black fault, HDR or colour-range cause. | Use reproducible same-frame/format comparisons before altering global calibration. |
| Gesture support | Some captured touchpad runs reported only two contacts; touchscreen gesture integration also had desktop interference. | Separate raw-contact reporting from compositor gesture handling. |
| Cameras, flashlight, microphone and pen | No complete hardware acceptance is recorded. | Investigate and test each subsystem independently. |
| Bootloader failure handling | Failed attempts have invalidated a slot and triggered fallback. Refreshing slot A recovers some tests. | Capture the exact failing loader stage; no supported permanent fallback repair is established. |

## Failed and inconclusive approaches retained

- **Brightness:** LP-only delivery, synchronized HS writes, waiting for both DMA
  completions, hardware broadcast, watermark changes, readiness checks and
  command-master selection did not independently solve the visual reproducer.
  One fast-ramp comparison began after errors and did not establish a safe rate.
- **Audio:** enumeration, firmware loading, gain changes, data-line selection,
  protection-monitor and interrupt candidates were insufficient to establish
  audible output. Accepted operation followed Android-matched framing and
  desktop format integration; preceding changes were not all isolated.
- **Boot recovery:** rescue booting worked initially, then failed unreliably.
  Removing extra probe messages did not remove that failure. MemoryDebug access
  does not prove Firehose/UFS restoration or modified-bootloader acceptance.
- **Input:** enumeration, cover removal, voltage matching and a reset quirk did
  not fix missing keyboard reports. Correct hall-sensor power was decisive.
- **Charging shutdown:** a driver shutdown candidate still returned to Linux.
  Charging-only screen-off behavior is not a successful electrical power-off.
- **Storage repair:** early shutdown-handoff attempts lacked a verified offline
  repair receipt. A temporary return of login did not establish filesystem repair.

See [technical milestones](06-experiment-journal.md) for the subsequent accepted
changes and [recovery constraints](reference/BOOT-RECOVERY.md) before device work.
Raw logs, device identities and private operational records are not public inputs.
