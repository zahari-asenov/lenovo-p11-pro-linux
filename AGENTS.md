# J706F project workflow

- Edit the single active source tree under `kernel/`. Use Git branches and commits
  for experiments, not full source or build-directory copies.
- Build with `scripts/build.sh`. Generated output belongs outside this checkout,
  under `J706F_BUILD_ROOT` (default: the sibling `j706f-build` directory).
- Package with `python3 scripts/package.py`. Preserve `known-good.img` and its
  manifest until a replacement actually boots and passes relevant device checks.
  Offline packaging checks are not successful device boots.
- Private archives, device credentials, root images and personal study notes are
  external/local inputs, never publication inputs. Do not follow historical
  archive links while scanning Git for publication or copy private data into it.
- Read `docs/reference/BOOT-RECOVERY.md` and
  `docs/reference/HANDOFF-LINUX-USB.md` before device work. Documentation cleanup
  authorizes no device storage changes. Development normally uses `fastboot boot`;
  partition writes require an explicit user request.
- Preserve signed firmware, calibration and partition layout. The reference
  tablet has Linux in both boot slots; older Android fallback notes are history.
  On a stock installation, never boot Android with the neutral Linux DTBO.
- Before RAM tests explicitly refresh slot A and verify state. This workaround
  does not prove bootloader failure handling repaired. Do not modify ABL or guess
  GPT flag masks as a diagnostic shortcut.
- Never probe GPIO59–62, hot-unbind Bluetooth, or bypass speaker protection.
- Read the latest brightness status before testing. The accepted clock fix avoids
  live PLL retuning; installed kernel66 maps active slider values to a nonzero
  floor. Historical raw511 recovery is not the same physical level under that
  mapping: logical340 maps physical511, but recovery of a failed new-mapping
  session has not been accepted. Do not sweep brightness without a targeted plan.
- Record experiments in `docs/06-experiment-journal.md` and update
  `docs/03-problems-and-tests.md`, linking sanitized evidence. Keep source/image
  hashes, offline checks, actual boot, user acceptance and recovery separate.
  Preserve failed and inconclusive history; never convert a hypothesis or
  firmware-load result into a hardware fix.

## Commit quality

- Commit focused milestones with their documentation and actual validation.
- Separate driver changes, tooling and unrelated cleanup. Inspect staged changes
  and run `git diff --cached --check` before committing.
- Use an imperative subject and explain problem, approach, tradeoffs and tested
  limits. State skipped, failed and inconclusive device checks honestly.
- Public documentation describes technical behavior; raw chats and personal
  conversation-derived study guides stay outside the repository.
