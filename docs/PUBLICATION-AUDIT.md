# Publication privacy and artifact audit

The intended publication graph is a curated source snapshot and logical commit series. Original maintainer refs, investigation records, device settings and raw reports remain private and preserved. Nothing has been published.

## Selected publication graph

Audited source tip: `fa19364f5` on `codex/public-source`. Baseline:
`public-upstream-fd78d179` (`9bd153578`). The six-commit selected graph contained
94,288 unique blobs and 1,612,872,068 uncompressed blob bytes, including 124
project blob versions. No blob exceeded 50 MiB and no project binary payload was
found.

Gitleaks covered the complete initial five-commit graph and the exact subsequent
delta. The full scan returned exit 1 with 241 findings: 240 generic API-key
matches and one SGX test private key, all byte-identical to upstream baseline
blobs. The delta and final commit-metadata scans returned exit 0 with no findings.
No project credential was confirmed. The supplementary project privacy scan
found only generic USB networking addresses, retained source attribution and a
service-unit name matching the email pattern; no personal home path, device
serial or project private-key header was found.

The following audit-record/journal-only commit is checked separately as a delta;
its immutable result is retained in the private audit report. Any later content
change requires a new scan. This is scanner-based review, not a guarantee that
unknown secret formats cannot exist.

## Scope and limitations

The current public-file review found no confirmed project credentials, personal home paths, device serials, private keys or private archive payloads. Configuration examples use placeholders; the repeated-digit UUID in configuration tests is synthetic. Copyright and upstream contributor attribution remain intact.

Gitleaks 8.30.1 is pinned and its release checksum was verified. Upstream kernel selftests contain public key fixtures and scanner matches; classify these by exact baseline blob identity rather than broad path exclusions. A modified fixture requires fresh review. Pattern scanning cannot prove the absence of every encoded or unknown secret.

Private device configuration, images, firmware, calibration, raw logs, photos and personal study notes stay outside the public graph. The audit does not inspect or certify the external archive. Original private history must not be pushed with `--all` or `--mirror`.

## Reproduce without exposing matches

`scripts/audit-publication.py` reads Git objects and, optionally, a Gitleaks JSON
report. It emits only paths, object IDs, categories and counts, never matched
values. By default it inventories every ref and all reachable blob sizes, checks project
privacy indicators and binary artifacts, and classifies scanner findings by
exact upstream blob identity. It does not traverse archive compatibility links.

Use an external private directory for raw scanner reports. Substitute the pinned
Gitleaks executable and an explicit external config containing
`[extend]` followed by `useDefault = true`:

Scan the explicit public branch and clean baseline. Gitleaks exit 1 means
findings requiring classification, not a zero-finding pass. Do not blanket-ignore
kernel files to manufacture a pass.

```sh
PUBLIC_REF=codex/public-source
PUBLIC_UPSTREAM_REF=public-upstream-fd78d179
PUBLIC_COMMIT=$(git rev-parse --verify --end-of-options "${PUBLIC_REF}^{commit}")
gitleaks git --log-opts="--full-history $PUBLIC_COMMIT" --config="$AUDIT_CONFIG" \
  --ignore-gitleaks-allow --redact=100 --no-banner \
  --report-format=json --report-path="$AUDIT_DIR/public-gitleaks-redacted.json" .
python3 scripts/audit-publication.py --revision "$PUBLIC_COMMIT" \
  --upstream-ref "$PUBLIC_UPSTREAM_REF" \
  --gitleaks-report "$AUDIT_DIR/public-gitleaks-redacted.json" \
  > "$AUDIT_DIR/public-git-inventory.json"
```

Repeat `--revision` to inspect the union of multiple intended public tips, with a
matching multi-tip Gitleaks scan. The inventory rejects supplied findings whose
commits fall outside its selected history. This validates finding membership,
not scanner completeness: an empty or truncated scanner report still needs its
tool exit status and actual invocation reviewed. Keep prior private reports
separate; never publish them with the clean release.

## Publication gate

Scan the selected final revision and review all non-baseline findings. Record scanner invocation and exit status alongside the redacted report outside the checkout. Inspect object sizes and ancestors, not only the tip tree. Publish only an explicitly named reviewed branch; this document does not authorize publication. GitHub workflows and broader hardware validation remain separate checks.
