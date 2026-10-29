# P9 technical verification and remaining release gates

October 29, 2026. The configurable framework passed its technical gate. Business defaults, complete per-field approval and physical-printer acceptance remain deferred; this report does not approve the supplied forms for completed production exports.

## Automated evidence

The final full suite passed **308 tests**, PostgreSQL and browser tests explicitly enabled, no skips. The only warning was the existing FastAPI/Starlette test-client deprecation warning. Two further focused browser runs exercised admin mapping/publication and the final export journey with `crypto.randomUUID` deliberately unavailable, covering the temporary HTTP origin's secure UUID fallback. Python compile, JavaScript syntax, whitespace and packaged-asset checks passed.

| Area | Verified behavior |
| --- | --- |
| Existing application | Parsing/review edits and Accept/Review/bulk deletion/explicit commit, repeated event retention, typed tasks/history/order, panel types, naming/deletion, highlights/sync, legacy drafts/templates and Initiating Devices contracts |
| Storage/source authority | SQLite/PostgreSQL initialization and immutable records; actual read-only snapshots; current saved task/input compatibility; scope ownership/membership; accepted versus pending evidence; relevant source fingerprints |
| Mapping/readiness | Zero/No/NA/missing distinction, independent groups/quantities, explicit empty marker states, transforms/timezones without invented times, negative conditions, overflow/glyph blocking and stale overrides |
| Administration | Authorization, fixed page selections, per-occurrence identities, complete dispositions, malformed input/quarantine, revision conflicts, exact-hash testing/publication, prior-version/disablement and preserved local edits |
| Completed exports | Consistent snapshot confirmation, stale/forged/expired proofs, exact four/one-page results, flattened/cleared appearances, safe filenames/headers, requester-bound previews, idempotent concurrent retries, immutable history/provenance and corruption rejection |
| Failure/recovery | Renderer/storage failures never download; DB failure after file publication leaves recoverable pending state; same-byte recovery; preview cleanup preserves finals/originals; existing writes/sync continue during paused PDF processing |
| Browser | Exact target selection/zoom/keyboard/narrow layouts, conflicts, two-device private edits, failed-save recovery, definition/scope changes, preview/stale rejection/final download/history, optional asset failure isolation and HTTP UUID fallback |

## Supplied-form technical evidence

Private catalogs cover 196 NFPA and 283 Compliance destinations for the exact specification hashes. Source-based synthetic No/Yes/NA vectors passed on all five included pages in Poppler and independent MuPDF; per-occurrence probes distinguish adjacent/repeated cells. Original geometry is retained, including Compliance's nonzero/negative page origin. Printable PostScript conversion succeeded. Private manifests bind each technical configuration/output hash and retain raster comparisons; no customer/reference PDFs, extracts or generated proofs are in Git/image layers. See [P8 report](PDF_INTEGRATION_P8_REPORT.md).

## Deployed-image and recovery evidence

The deployed image includes Poppler, the packaged integration UI, timezone data and renderer `pdf-p7-1`. The exact supplied templates rendered successfully through that image's bounded worker without publishing/enabling their drafts. Live authenticated UI/legacy review/event/export checks and API recreation/persistence passed; see [P10 report](PDF_INTEGRATION_P10_REPORT.md).

The consistent production database backup was restored into a uniquely named, isolated temporary database. Both the new image (with additive PDF tables) and retained prior image booted against it and preserved all 14 legacy-table data hashes. The temporary database was then dropped; production was neither restored nor reset. The upload archive was checked byte-for-byte against 89 unchanged pre-existing original/retained files. Backups and the prior image remain private on the server.

## Open business/physical gates

The user will establish defaults later. Administrators must review candidate labels/types/units/conditions and every actual destination, establish scope/timezone/company and other policies, inspect realistic completed outputs/readability, verify/test/publish and explicitly enable. Physical-printer acceptance remains open. Dense Compliance fields and ASCII/Helvetica input support have explicit overflow/character gates; signing/attachment merging and NFPA pages 5–11 remain outside initial scope. Full production-form acceptance is not claimed while these gates remain open.
