# Engineering Change Notes

## October 28, 2026 — P3 saved-source mapping and readiness

- Added read-only typed catalogs/snapshots, deterministic conditions/transforms/group states, scope/completion gates, layout checks and structured blockers.
- Added stable provenance/fingerprints and stale override/definition handling; preserved old published JSON/hash integrity when adding optional mapping settings.
- New SQLite/PostgreSQL tests include actual read-only enforcement/concurrent commits, legacy/negative/zero/missing values and scope/event gates. No UI/routes/schema/deployment changed. See [P3 report](PDF_INTEGRATION_P3_REPORT.md) for count/font and later-phase limits.

## October 28, 2026 — P2 backend foundations

- Added strict versioned PDF configuration/decision/snapshot contracts and a separate optional six-table schema (five record families plus version marker).
- Added revision guards, immutable published versions, append-only decisions/audit, preview token binding, retained artifact states and private immutable/hash-checked files.
- Feature defaults to disabled; initialization failures preserve legacy startup. No UI/routes/deployment added. SQLite/PostgreSQL tests compare existing data and rehearse retention/recovery. CI now includes disposable PostgreSQL.
- See [P2 report](PDF_INTEGRATION_P2_REPORT.md). Semantic source/readiness/publication services and completed PDF generation remain future phases.

## October 28, 2026 — Explicit P1 completion

- Added enforced offline subprocess CPU/address-space/file/wall limits, staged publication, retained original bytes and target-to-output manifests.
- Added mirroring, four-rotation raster alignment, malformed rotation and resource-enforcement tests; compared native filling with overlays and checked all five pages in Firefox/Chromium PDF viewers.
- No application UI/routes/schema/deployment changed. See [P1 report](PDF_INTEGRATION_P1_REPORT.md); production HTTP isolation, mapping approval and physical-printer acceptance remain later gates.

## October 28, 2026 — PDF integration part 1

- Added isolated offline PDF occurrence inventory, watermarked feasibility renderer, and private probe command; current application behavior and schema are unchanged.
- Added synthetic PDF fixtures/tests and a disposable populated-database preservation/backup-restore baseline.
- Reconciled the supplied NFPA first four pages (196 widgets) and Compliance page (283 widgets); private proofs demonstrate duplicate-name isolation and clearing original presets.
- See [part 1 evidence](PDF_INTEGRATION_PART1_REPORT.md) and [decision register](PDF_INTEGRATION_DECISIONS.md) for verification and limits. Published mappings, UI, production exports/storage, upload isolation, and browser/physical-print acceptance remain future work.
