# Preparing a public source release

No repository or release has been published by this preparation work.

1. Run `scripts/check-project.py` and `scripts/build.sh` with an external build
   directory. Record the tool versions in the generated `environment.json`.
   A distribution-toolchain build should also pass the manual ARM64 workflow.
2. Run the selected-public-ref publication audit described in
   [PUBLICATION-AUDIT.md](PUBLICATION-AUDIT.md) against the final committed tree.
   Review new findings; never suppress upstream-looking paths without comparing
   their exact bytes. Review non-secret personal metadata separately.
3. Resolve every licensing requirement in [LICENSE](../LICENSE). Preserve
   per-file upstream terms and supply corresponding source for any distributed
   binaries. Do not bundle private root images, account state or firmware without
   suitable redistribution terms.
4. Review the [hardware status](../README.md), known issues and recovery notes.
   Keep source compilation, packaging, actual boot and user acceptance separate.
5. Check `git status --short`, select the intended branch and create a local
   annotated tag only after review. Configure the chosen GitHub repository when
   its owner and name are known. The prepared branch is `codex/public-source` and its baseline tag is
   `public-upstream-fd78d179`. Push only that branch and intended public tags explicitly; do not mirror
   every local ref or internal checkpoint.
6. Enable private security advisories in the new repository if available and
   update SECURITY.md to identify that channel. Run the GitHub workflows before
   describing them as passing.

[The accepted display checkpoint](../configs/releases/display-2026-11-25.json)
records hashes and its original source revision. It is a device acceptance
record, not an uploaded binary or a claim that every subsequent source revision
was booted. Later documentation/tooling changes do not retrospectively change
those hashes. No private root or device identity is included in this record.

A source release can be useful without a desktop image. The kernel source is
buildable independently; boot packaging still needs the explicitly documented
bootstrap and root inputs. Do not advertise a general installation image until a
clean-room, device-specific preparation and recovery path has been validated.
