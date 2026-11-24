# Runtime access and validation

The reference tablet runs native persistent Linux. The accepted display checkpoint
is recorded in [the release provenance](../../configs/releases/display-2026-11-25.json).
Both boot partition contents were verified; normal slot A startup and user visual
acceptance were checked. This is not a guarantee for another tablet or firmware.

## Access

Use pinned SSH identity and known-host files stored outside Git. Never embed
passwords or disable host-key verification to obtain access. Configure addresses,
usernames and device identity locally; no public file supplies credentials.

The bootstrap uses an isolated USB Ethernet link and read-only diagnostic HTTP.
A fixed bootloader-request helper may be present in locally prepared recovery
assets. It is not a general network shell. Do not expose diagnostic or repair
listeners to a normal LAN. Missing USB enumeration, failed Wi-Fi firmware startup
and a failed graphical login are distinct conditions.

A working installed `j706f-fastboot` helper requests a clean one-shot bootloader
restart. Normal `reboot-argument=bootloader` alone was unreliable on the reference
firmware. If fastboot stays visible but USB is absent, reconnecting the data cable
has been necessary. Physical key behavior is firmware-specific.

## Display

Repeated active clock-rate programming was traced to a fractional-rate mismatch.
The accepted fix preserves initial rate setup and avoids retuning a live shared
PLL for ordinary commands. Tests recorded many brightness commands without
controller errors or VCO reprogramming, followed by user acceptance.

The active brightness mapping is approximately 10–100% of the panel command
range. GNOME's minimum makes the effective lowest setting approximately 11%.
Blanking/off remains separate. This is not calibrated luminance. Brightness and
actual_brightness both use the logical interface scale; command tracing records
the physical panel code.

Historical recovery using logical/raw 511 applies to the old mapping. Under the
new mapping logical 340 corresponds to physical 511. That arithmetic is checked;
recovery of a failed session under the new mapping has not been accepted. Do not
repeat full slider sweeps after a visual failure. Stop, capture bounded evidence
and follow the recovery plan.

## Tracing

`scripts/capture-display-trace.sh` requires root and the tracing-enabled kernel.
It records an isolated bounded RAM ring and stops at the first actual controller
timeout or its time limit. It does not change brightness, global tracing or
persistent storage. Verify the recorder is armed before a controlled test.
Logs alone do not prove a correct picture; visual acceptance remains separate.

Suspend, true shutdown while charging and further hardware support remain
[known issues](../03-problems-and-tests.md). A black display or Wi-Fi reconnect
is not proof of either sleep or electrical power-off.
