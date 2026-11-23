# Security and device-safety reports

This is an experimental native-Linux port, not a security-maintained tablet
product. There is no promised response time or supported stable release series.
A successful desktop demonstration does not certify secure boot, recovery,
charging safety, data integrity or reliable suspend.

## Reporting

If the repository's hosting service offers private vulnerability reporting,
use that facility. If no private channel is listed, open a minimal issue asking
the maintainer for a private reporting route **without disclosing the exploit,
credentials or private device data**. Do not send reports to upstream kernel or
Lenovo contacts on the assumption that they maintain this project.

Provide a concise description of the affected component and revision, the
observed effect, reproduction conditions and a suggested mitigation if known.
Share only sanitized evidence. Do not attach private root images, account state,
SSH keys, authentication tokens, Wi-Fi profiles or unrestricted memory dumps.

## Known boundaries

- Bootloader unlocking changes the device's trust model. A/B slot handling and
  a RAM-boot recovery image are not an independently verified emergency restore
  path for a damaged bootloader.
- Maintenance interfaces can expose privileged recovery actions. Use the
  documented isolated connection and fixed-function controls; do not expose
  them to an untrusted network.
- Speaker-protection and charging protections are required. A shortcut that
  disables them is not an acceptable diagnostic fix.
- Filesystem corruption has recurred. Offline repairs passed, but the original
  cause is unproven and personal-file integrity was not exhaustively verified.
- Suspend, charging-only operation and true shutdown are distinct. Read the
  current problem ledger before relying on unattended low-power behavior.

For ordinary bugs, use the contribution workflow and include exact source/image
provenance and the distinction between offline tests and observed device behavior.
