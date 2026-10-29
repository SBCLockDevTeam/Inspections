# P10 disabled framework rollout and handoff

October 29, 2026. Application code **940352e** is deployed on `167.172.18.72` under `/opt/inspections`, Compose project `inspections`, port 18080. Documentation-only commits after that code revision record this evidence and do not change the deployed source. The rollout makes the configurable framework available; both production-form integrations remain **disabled, unpublished drafts** because the user will establish defaults later.

## Deployment and isolation

The pushed source revision was checked on the server and built without cache. Its running image, Compose services, packaged assets/timezone support and localhost/external `/health` were verified. Work_Order/the separate project was not modified; its container identities were unchanged. The existing inspection upload volume was reused and its persistence verified. Compose reports that this pre-existing volume lacks Compose ownership metadata; it was not replaced.

A retained prior-image tag, old commit/environment, consistent database dump and upload archive are stored root-only under `/opt/inspections-backups/pdf-integrations-20261029T121800Z`. `/opt/inspections-backups/current-pdf-rollout` identifies the backup. Archive integrity/checksums passed. During the first backup attempt, an stdin-fed helper stopped the API before its later commands ran. The prior container was restarted; the helper was corrected to run from an on-disk file, and backup/switch completed. No data loss occurred. Deployment/recreation included brief inspection API restarts.

Customer data hashes matched across **14 legacy tables**, excluding the auth-session table, the explicitly synthetic inspection and startup-only settings timestamps. Existing setting values and customer inspections, points, checklist decisions, event mappings and source records were preserved. All **89 pre-existing original/retained files** matched the upload archive byte-for-byte. Backup restore and prior-image compatibility were exercised in an isolated temporary database, then removed; production was not restored/reset.

## Installed reference forms

NFPA pages 1–4: 196 exact widget occurrences, source hash `b956b9c0ae6864970eb2f582a12a9e59d81162e1843f3b8e54f536a08d43aa71`. Compliance page 1: 283 occurrences, hash `f51cb8c0808fa356382b0672ef0f5613306def35503ec37721fe7923ce6c8dd2`.

Both have complete draft dispositions/additional-input candidates, zero business verification/publication, no active version and `enabled=false`. Categories/applicability/default timezone/company constants are not established. Originals and private reference/proof files are outside Git/build contexts; immutable application originals are in the persistent inspection uploads volume. No existing legacy mapping/draft was silently adopted or overwritten.

The exact deployed bounded renderer processed both supplied forms using private synthetic technical plans; the proofs remained visibly marked drafts and did not become completed exports or publication evidence. Draft payloads, original hashes and disabled/unpublished state matched before/after API recreation.

## Live interaction evidence

An authenticated browser on the actual HTTP origin verified secure UUID fallback, both mapping cards, exact inventory selection/zoom and real sanitized page images. A clearly synthetic inspection exercised XLSX modal parsing, description edits, both Accept/Review directions, the separate bulk Review deletion action, no source-row/Delete column, and explicit Save Decisions. It also exercised pending Event History acceptance, later-upload preservation of the accepted timestamp, location editing and an actual legacy Initiating Devices PDF download with the mandated filename/content. New export actions stayed disabled while existing actions remained usable.

The synthetic inspection was soft-deleted, preserving its original uploads and audit evidence. Temporary verification sessions were logged out/removed without changing account passwords, roles or other sessions. Authenticated administration was checked again after recreation. Private screenshots/results and proof manifests remain outside Git. Health and the inspections project were healthy at handoff.

## Remaining owner actions

Open Administration → Integrations and follow the [operating guide](PDF_INTEGRATIONS_OPERATIONS.md). Establish defaults/policies; review every target and field readability, including deliberate blanks/signatures and negative/NA conditions; run saved-version tests; explicitly verify/publish; then enable each integration. Physical-printer/business acceptance and real completed-form enablement remain open. Do not interpret a complete technical draft catalog as 479 approved business mappings. NFPA pages 5–11, automatic report merging and a signature service remain excluded.

Rollback uses the retained inspection image/commit/environment only, with new integrations disabled and additive tables/files/history preserved. Never use `/opt/serviceflow` or erase newer accepted data as an ordinary code rollback. See the operating guide for recovery/maintenance and rollback boundaries.
