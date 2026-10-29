# Decision Log

## 2026 10 28 P3 authoritative saved sources and deterministic readiness

Resolve PDF mappings from saved active configuration and authorized inspection records in independent read-only transactions (PostgreSQL repeatable read; explicit SQLite read transaction). Keep No/NA/zero/missing distinct, reject incompatible/stale inputs, require explicit panel scope and accepted event mappings, and preserve source/decision provenance. Count sources without approved classifications/results remain unavailable; never infer good counts from accepted timestamps or descriptions. Draft catalogs are admin-only diagnostics. Optional JSON mapping fields preserve older published hashes by hashing persisted payloads, without rewriting history. No database migration, existing route/UI change or deployment is included. See [P3 report](PDF_INTEGRATION_P3_REPORT.md).

## 2026 10 28 Opt-in P2 PDF integration persistence

Add strict schema-version-one contracts and separate optional ORM metadata for the two PDF integrations, versions, append-only form decisions/audit, artifact lifecycle and schema marker. The switch `INSPECTIONS_PDF_INTEGRATIONS_ENABLED` defaults to disabled and is independent of legacy template settings. Opted-in initialization is additive, transactional and tested against SQLite/PostgreSQL; published/sealed records are protected by database triggers. New artifact/decision parent references are validated, while actor IDs remain retained strings to preserve existing physical user deletion. Private files use ID-derived keys, no-replacement publication and hash checks. Optional initialization errors fail the new feature closed without blocking old app startup. No UI/routes/production deployment are added. See [P2 evidence and future migration policy](PDF_INTEGRATION_P2_REPORT.md).

## 2026 10 28 Complete explicit P1 feasibility gates

The diagnostic CLI now uses a resource-bounded Linux subprocess, retains exact original bytes and a source-to-output target manifest, and publishes only successful staged proofs. Native filling was compared with location overlays; the native name update coupled 3 selected NFPA and 2 Compliance occurrences, supporting the overlay choice. Actual Firefox PDF.js and Chromium PDFium checks cover all five included pages. Poppler is selected for future workspace previews; its production package is added when that functionality is introduced. Existing application behavior/schema/deployment remain unchanged. See [P1 report](PDF_INTEGRATION_P1_REPORT.md).

## 2026 10 28 Isolated PDF integration feasibility

The first PDF integration implementation batch adds offline inventory and always-watermarked diagnostic rendering tools under `integrations/`, generated synthetic PDF tests, and a disposable data-preservation/backup baseline. No existing application route, model, UI asset, or export helper is changed, and no new integration is enabled. Occurrence identities use the immutable original PDF fingerprint and location; diagnostic derivatives clear widget presets and use location-specific vector overlays in a fresh document. Production publication, signing policies, security/resource isolation, and final mapping remain later-phase requirements. See [technical/business decisions](PDF_INTEGRATION_DECISIONS.md) and [verification evidence](PDF_INTEGRATION_PART1_REPORT.md).

## 2026 09 18 Separate application

The inspection processor will be a new application and repository. The existing Work_Order project remains untouched.

## 2026 09 18 Deterministic first release

The first release will not require an AI API key. File parsing, validation, matching, and export will be deterministic and auditable.

## 2026 09 18 Optional AI boundary

AI will be added later through a provider interface for suggestions and exception assistance only. It will not be part of the authoritative data-processing path.

## 2026 09 18 Separate deployment resources

The new application will use separate service names, secrets, storage, database access, and deployment configuration on the same DigitalOcean server.

## 2026 09 18 Multiple panel point lists

An inspection may contain multiple Points Lists, one per security panel. Each list is categorized as Fire, Burglar, Combo, or Gas Station and is immutable after acceptance.

## 2026 09 18 Incremental event history

Event History uploads are cumulative. Successful point-to-time mappings are retained across uploads until all mappings are complete.

## 2026 09 18 Gated PDF export

The final PDF is not created until all results and mappings are complete. The filename includes store, city, state, category, and inspection date.
