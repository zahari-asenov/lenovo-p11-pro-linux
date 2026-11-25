# Technical milestones and experiment outcomes

This is the public technical record. It summarizes meaningful successes, failures
and validation limits; raw logs, machine-specific plans and personal session
notes are maintained separately. Hardware status is tracked in
[known issues](03-problems-and-tests.md).

## October 2026 — Boot and observability

- Exact firmware/device-tree selection was reconstructed. A panel implementation
  for another P11 model was not sufficient board support for TB-J706F.
- Initial RAM boot attempts produced no confirmed Linux runtime. Lenovo's older
  overlay engine rejected metadata accepted by newer host tooling; corrected
  symbol/fixup handling passed the archived engine.
- Relocation checks addressed a mismatch between loader placement and ARM64
  startup assumptions. Offline success remained distinct from kernel execution.
- Stock-kernel rescue initially recovered retained console output. Mainline logs
  then established all eight CPUs and unfinished device probing. Later rescue
  attempts failed unreliably, including unchanged earlier images; added logging
  was not isolated as the cause.
- Entry/return and register-level tracing localized a hanging GPIO59 read.
  Reserving GPIO59–62 allowed startup to progress. Historical crash triggers are
  not procedures to repeat.
- Bounded Sahara MemoryDebug capture supplied missing logs. This established
  read access to the advertised memory region, not a verified emergency flashing
  or bootloader-restoration route.
- Missing PSCI domain providers blocked the USB dependency chain. Provider
  configuration enabled native userspace ACM/ECM while retaining the CPU-idle
  bring-up workaround.

## October 2026 — Display, input and desktop

- Correct RM692E6 EDO panel selection, display clock/reference-generator support
  and representable regulator constraints enabled panel initialization.
- A wrapper incorrectly rejected successful padded command-transfer lengths.
  Correcting it allowed the stock startup sequence and visible colour bars/text.
- Keyboard enumeration alone produced no usable reports. Voltage, cover, LED and
  reset-quirk attempts failed; hall-sensor supply and physical lid configuration
  enabled actual keyboard/touchpad operation.
- Missing userspace kernel features blocked Weston socket-lock creation.
  FILE_LOCKING and other required features enabled the first native desktop.
- Correct touchscreen report coordinates enabled touch. CPU pinning did not
  solve dragging latency; CPU-frequency and memory-bandwidth scaling improved
  responsiveness. GPU/firmware integration subsequently enabled accelerated
  rendering.
- Wi-Fi needed firmware/calibration services and complete userspace supplicant
  dependencies. Authentication and Internet operation were verified separately.
  Bluetooth discovery preceded accepted headphone pairing and playback.
- Native Debian/GNOME required correct archive ownership, account metadata,
  helper permissions and browser syscall support. Dock/buttons/terminal settings
  were userspace integration work, separate from hardware drivers.

## October 2026 — Failed brightness approaches

Runtime brightness caused split transitions, flashes or blanking. LP-only and
synchronized LP variants failed. HS delivery synchronized the halves without
solving progressive corruption. Direct unchanged writes and one slow small ramp
were accepted, but a faster comparison began after previous errors and could not
establish a safe update-rate threshold.

Dual-completion waiting, hardware broadcast programming and vendor-style FIFO
watermark changes built and booted but did not pass the slider reproducer.
Successful command transfers and a log interval without an explicit error did
not establish correct pictures. A brightness reset plus display power cycle was
a recovery procedure, not a permanent fix.

## October 2026 — Persistent Linux and protected audio

An internal ext4 root and independent bootstrap replaced laptop-downloaded RAM
operation on the development tablet. Linux boot images in both slots reference
one shared root. Boot-success marking and verified image contents do not repair
the loader's unresolved failure policy. Android system/recovery removal and
additional Linux storage were separate authorized operations, not prerequisites
for first kernel boot. Required bootloader, firmware and calibration were retained.

Speaker card/amplifier enumeration and protection firmware loading initially
coexisted with silence. Data-line, gain, monitor-input and interrupt candidates
were insufficient. Comparing Android's protected startup, tuning and PCM framing
led to accepted audio. Matching desktop output to the accepted 16-bit, 48 kHz
route restored loud, clear browser playback after normal startup. The independent
contribution of every preceding change was not isolated; speaker protection
remained enabled.

## October 2026 — Charging and low-power behavior

Laptop USB current limits constrained net charging. A main-charger candidate
increased a short normal-temperature wall test from about 1 A to about 1.66 A
battery current. This was not full fast-charge or full-cycle validation.
Charge-pump register identification and interrupt registration were tested with
the pump disabled. Complete adapter negotiation, interrupt delivery and coordinated
thermal/fault/current policy remained unaccepted.

A shutdown-driver candidate still returned to Linux with charger-mode startup.
Charging-only userspace later stopped the desktop, blanked the screen and allowed
Power-to-login. Earlier blanking/persistence attempts failed or were inconclusive.
This mode keeps Linux running; it is not true electrical power-off. A normal sleep
attempt disconnected Wi-Fi, then USB suspend failed with EAGAIN and the system
resumed automatically.

At very low charge, gauge health DEAD triggered an overly broad charge rejection.
A narrow admission exception retained temperature, read-error and other fault
checks. Installed operation and measured wall-charge recovery were verified;
long-term capacity and complete fast charging were not certified.

## 22 November 2026 — Memory pressure and offline repair

Prioritized LZ4 zram, lower-priority disk swap and capped persistent logs were
installed. Bounded swap integrity and persistence checks passed. A heavy browser
workload still caused memory stalls without a recorded OOM/reboot in the observed
interval; this was not a general freeze fix.

Root metadata errors required an offline check. Conservative preen replayed the
journal and corrected orphan/deletion metadata; an independent read-only check
passed. Optional extent-tree shortening was left unchanged. A clean checker
result did not establish why corruption occurred.

## 25 November 2026 — Recurring corruption and verified recovery

Root bitmap checksum disagreement recurred and the filesystem became read-only.
Graphical login could not write its working configuration. Wi-Fi also failed on
the affected boot; a temporary return of login did not prove repair.

Early shutdown-handoff attempts had no verified offline repair receipt. Host
console permissions/privilege restrictions then blocked control of an otherwise
running RAM recovery. A visible console and guarded fixed-function endpoint
provided access without arbitrary host privilege escalation.

Before repair, device/partition identity, geometry, unmounted internal filesystems,
inactive swap and read-only state were checked. Metadata was captured before the
single requested conservative repair. The repair reported corrections; a separate
five-pass check passed. A fresh recovery boot remained clean, and independent
before/after bitmap CRC comparison confirmed the captured mismatches were corrected.
Installed Linux returned with writable root and running login/radio services.

No wipe/reinstall was performed. The interrupted backup was not a complete
verified backup, and personal files were not exhaustively checked. The cause of
recurrence remains unproven; absence of explicit UFS errors is not a hardware
health certificate.

## 25 November 2026 — Brightness root cause and accepted update

1. Panel lifecycle serialization and checked PM/clock error unwind improved
   readiness handling, but the hardware test still corrupted during gradual
   adjustment. These changes were not a sufficient display fix.
2. Related Android-source command-master selection motivated a board-only opt-in
   physical DMA-master experiment. Logical encoder/PHY roles and read-transfer
   correctness were preserved. Master selection alone also failed.
3. A narrow log filter initially missed real FIFO/timeout lines. Full inspection
   found controller errors even before the later sweep, invalidating an assumed
   clean baseline.
4. Standard DSI/DPU/clock tracepoints and a bounded first-timeout recorder captured
   the failure sequence. Slight rate-rounding differences caused repeated actual
   shared-PLL retuning during brightness work. The first lane error occurred in
   clock preparation before the next command trigger.
5. Avoiding redundant active-link rate programming passed the tested slider route:
   the acceptance trace had no DSI error or VCO-retune events. The retained
   command-master option's independent contribution was not isolated.
6. A monotonic active brightness floor of approximately 10% was added, with zero
   reserved for blanking. Logical readback was corrected before installation;
   physical panel codes remain separately observable through tracing.
7. Both boot partitions received verified final contents. Normal installed slot A
   startup and smooth/visible brightness adjustment were accepted. Slot B was not
   separately booted in this final session.

See [accepted display provenance](../configs/releases/display-2026-11-25.json).
Dark-video/colour observations did not establish a general gamma, HDR or range
fault; a grayscale check did not reproduce the earlier suspected crushed blacks.
These remain separate from the accepted brightness result.

## Publication preparation — 2026-11-25

The accepted tablet installation was left unchanged. A separate public source
series imports the pinned upstream snapshot, board/driver port, portable tools,
checks and concise documentation. Original investigation refs and full records
remain private; this curated history does not erase failed experiments.

Publication-only source cleanup removes the dormant GPIO diagnostic, restores
upstream probe logging, scopes experimental DSI registers to this board, and
moves locally generated Bluetooth identity into ignored configuration applied
only to generated external DTBs. The brightness mapping retains its accepted
valid-range arithmetic and gains exhaustive host checks.

The ARM64 kernel/device tree build and complete offline host gate passed. The
build retains inherited device-tree warnings. Public documentation links passed;
GitHub workflows have not run remotely. No new image was packaged, booted or
installed during this cleanup. See [validation](VALIDATION.md) and the
[selected-history publication audit](PUBLICATION-AUDIT.md) for scope and limits.

## First public CI validation — 2026-11-25

The initial GitHub push contained only the curated source branch and clean
upstream baseline tag. GitHub rejected both workflow definitions before jobs
started because the job-level environment used an unavailable `runner.temp`
expression. Local YAML parsing had not validated GitHub context availability.
The correction uses the supported `github.workspace` context with an external
sibling build directory. This is a CI configuration fix, not a kernel or device
change. Remote execution results must be checked separately after the push.

The next host run reached the tests and exposed a mock-path bug: sequential
substitution of `/run` rewrote already-inserted temporary paths containing
`/runner`. A single substitution pass now leaves generated paths intact, and
the fixture itself includes `runner/work` so this failure is covered locally.
Production root-selection code was not changed.

## Recording future experiments

Add a focused technical entry with source/configuration and artifact identity,
checks actually performed, hardware observations, acceptance, recovery and limits.
Preserve failed and inconclusive results. Link sanitized distributable evidence;
keep private logs, device inventories and personal notes outside the repository.
