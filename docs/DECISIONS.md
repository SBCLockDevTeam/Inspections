# Decision Log

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
