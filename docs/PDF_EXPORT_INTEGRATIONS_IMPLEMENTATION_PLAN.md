# PDF Export Integrations Implementation Plan

Status: P0–P7 delivered, including snapshot-bound previews, confirmed final retention and history. P8–P10 remain in progress.
Updated: October 29, 2026.
Requirements: [PDF Export Integrations Specification](PDF_EXPORT_INTEGRATIONS_SPEC.md).

## 1. Delivery contract

Implement the entire specification as an additive feature in the existing FastAPI/Python application and its current HTML/JavaScript interface. Deliver two integrations: NFPA 72 using source pages 1–4, and Compliance using its single source page. Preserve every existing inspection workflow and export contract.

This document plans the work; it does not authorize or perform application changes, production configuration, or deployment. The specification remains the requirements authority. Changes to business policy must be recorded before a dependent production mapping is published.

The release is complete only when both supplied forms have verified mappings, technicians can complete required additional data and export reliable PDFs, existing workflows pass regression checks, and deployment evidence satisfies the repository's verification standard. A working generic mapper with unconfigured forms is an intermediate milestone.

## 2. Implementation boundaries

### Existing code to preserve

- Leave `api/pdf_templates.py`, legacy template routes, NFPA draft routes, and both existing PDF draft tables compatible. Do not retrofit this feature into their field-name-only mapping behavior.
- Leave current point/event mutations, accepted mapping retention, checklist decision history, and Initiating Devices export semantics unchanged.
- Modify `storage.py` only to register additive models/schema initialization needed by the new feature. Keep domain rules outside storage.
- Make narrow integration changes in `api/app.py`, `api/index.html`, `api/review.js`, and UI asset delivery. Avoid a frontend rewrite or unrelated refactor.
- Keep originals, normalized derivatives, previews, and artifacts private. The current production Compose volume already persists `/tmp/alarm-inspection-uploads`; use integration-specific subdirectories within that volume.
- Keep the new feature disabled by default. Unconfigured, disabled, or broken integrations must not break current routes or inspection entry.

### Proposed new modules

Names below are implementation targets, not existing files. Split further only when responsibility or size warrants it.

| Location under `src/alarm_inspection/` | Responsibility |
| --- | --- |
| `domain/pdf_integrations.py` | Typed, versioned configuration; target dispositions; value types; publication validation |
| `domain/pdf_mapping.py` | Allowlisted transforms, answer-group rules, applicability, formatting, missing-value policies |
| `domain/pdf_readiness.py` | Pure readiness decisions, structured blockers, signature and supplemental-sheet policies |
| `integrations/pdf_inventory.py` | PDF inspection, widget identity, diagnostics, page geometry, private normalized-template metadata |
| `integrations/pdf_renderer.py` | Verified field/overlay rendering, appearance cleanup, flattening, page selection, output inspection |
| `integrations/pdf_sources.py` | Read-only saved-data resolution and provenance, consistent snapshots, source compatibility |
| `integrations/pdf_repository.py` | New records, append-only decisions, optimistic version checks, artifact lifecycle |
| `integrations/pdf_service.py` | Template lifecycle, test runs, publication, previews, export orchestration |
| `integrations/pdf_files.py` | Private paths, hashes, atomic file writes, bounded processing and cleanup |
| `api/routers/admin_integrations.py` | Admin configuration, inventory, testing, publication, activation/disablement |
| `api/routers/inspection_form_integrations.py` | Form details, readiness, preview confirmation, exports/history/downloads |
| `api/integrations.js` | Mapping workspace and technician form/export UI, isolated from legacy PDF dialogs |

Create package initializers where required. Add the new UI asset to `pyproject.toml` package data and serve it through the existing UI router. Reuse existing authentication/admin helpers and ordinary response conventions. Do not introduce Redis jobs or another service solely for this feature; revisit processing execution only if measured bounds require it.

## 3. Dependency and milestone map

| Phase | Depends on | Reviewable result | Exit gate |
| --- | --- | --- | --- |
| P0 Baseline and decisions | Specification | Compatibility checklist and decision register | Current behavior and unresolved business policies identified |
| P1 PDF feasibility | P0 | Inventory and safe-rendering proof for both forms | Independent target filling and flattened output demonstrated |
| P2 Contracts and storage | P1 | Versioned schemas, isolated tables, feature switch | Existing/fresh SQLite and PostgreSQL compatibility |
| P3 Sources and rules | P2 | Typed data catalog, resolution, mapping/readiness functions | Deterministic rule and provenance tests pass |
| P4 Admin backend | P2–P3 | Draft, test, publish, activate, disable APIs | Authorization, coverage, immutability, conflicts enforced |
| P5 Mapping workspace | P1, P4 | Admin → Integrations and visual editor | Exact target selection and publication workflow work |
| P6 Technician details | P3–P4 | Form Details entry, explicit scope, readiness UI | Existing entry/sync behavior preserved |
| P7 Export lifecycle | P1, P3–P4, P6 | Preview, confirmation, retained final downloads | Snapshot, rendering, persistence and failure tests pass |
| P8 Configure both forms | P5–P7 | Reviewed production candidate mappings | Every included location accounted for and tested |
| P9 Release verification | P8 | Regression, viewer/print and recovery evidence | Acceptance matrix complete with no unresolved release blockers |
| P10 Rollout and handoff | P9 | Verified deployment and operating guide | Live interaction checks and rollback readiness confirmed |

Implement in this order. Framework work may proceed while business decisions are pending, but publication and export must fail clearly when a dependent policy is unresolved. Do not enable an unfinished integration because its UI is available.

## 4. P0 — Baseline and decision register

Tasks:

1. Read `PROJECT_DESCRIPTION.md`, the specification, relevant domain/API/storage modules, current tests, and deployment documentation. Refresh Git state using the repository workflow.
2. Record current API contracts and the key browser behaviors listed in specification §2. Establish unit/API/browser baselines; record pre-existing failures and skipped tests separately from passing tests.
3. Inventory current test tooling. Browser tests are opt-in with `INSPECTIONS_RUN_BROWSER_TESTS=1` and use Playwright; installing only the existing test extra does not ensure browser tooling is available. Document the required local/CI test environment.
4. Create synthetic inspections covering legacy and typed checkbox decisions, multiple panels/categories, accepted and pending times, unresolved review rows, saved PDF drafts, removed dropdown choices, and deleted records.
5. Open a decision register for task-to-field mappings, missing inputs, approved constants, panel applicability, date/time/timezone rules, signatures, supplemental sheets, defects/work orders, and filenames. Track decision, owner, rationale, and affected targets. Use “unresolved” explicitly instead of assumptions.
6. Define the comparison baseline for preserving existing records and audit history across initialization and migration. Include backup/restore rehearsal on disposable data before production changes.

Deliverables: baseline test report, compatibility matrix, private fixture inventory, and configuration decision register. Add links in repository docs; never commit supplied PDFs, customer answers, source extracts, or secrets.

## 5. P1 — Prove reliable PDF inventory and rendering

Tasks:

1. Verify original file fingerprints against specification §3. Preserve originals unchanged in private storage. Reject an unexpected replacement from automatic reuse of the old inventory.
2. Enumerate selected-page annotations and parent field trees. Capture qualified names, widget occurrences, rectangles, page boxes/rotation, flags, choices/export states, values/defaults, appearance information, and parser diagnostics.
3. Reconcile the expected 196 NFPA widget occurrences and 283 Compliance occurrences. Distinguish widgets, logical fields, result groups, printed labels, and excluded pages. Record every discrepancy.
4. Assign deterministic version-scoped target IDs using the source fingerprint, page, occurrence, geometry, and qualified field identity. Verify repeat extraction against the same original produces the same IDs.
5. Demonstrate that neighboring targets and repeated names can receive distinct sentinel values. Test intentional mirroring separately from accidental coupling.
6. Prototype native appearance rendering and safe overlay fallback using the already declared PDF libraries where feasible. Clear original field/default appearances, regenerate needed content, flatten the derivative, remove active actions, and retain only the selected pages and permitted metadata.
7. If duplicate-key structure prevents safe native filling, prove a normalized private derivative or exact-location overlay strategy. Record original-to-derivative target correspondence and both hashes. Do not paint opaque rectangles over printed lines as an unverified workaround.
8. Generate page previews with a coordinate system shared by rendered page images and widget rectangles, including cropped/rotated synthetic fixtures. Prefer server-rendered page images for the mapping workspace; choose and document the rasterizer after feasibility testing. If a browser PDF renderer is selected instead, serve its reviewed assets locally.
9. Measure preview/export execution time, memory, upload sizes, page limits, and output sizes. Set bounded execution and resource limits. A renderer failure must remain isolated from current application routes.

Exit gate: inspect all five included pages; prove duplicate isolation, removal of presets/scripts, page selection, and printable self-contained appearances in two independent viewers. Resolve the PDF toolchain and any required Python/system dependency changes before building the full workspace. This is a feasibility gate, not final business mapping approval.

P1 evidence: [phase report and bounds](PDF_INTEGRATION_P1_REPORT.md). The initial first batch supplied the prototypes; the P1 follow-up adds the explicit limits, lineage manifest, native comparison, mirroring/rotation tests and two-viewer checks. Production form/physical-print approval remains a later release gate.

## 6. P2 — Contracts, additive persistence, and private files

Tasks:

1. Define validated schemas for integration configuration, inventory, source references, transforms, answer groups, manual input definitions, field verification, and readiness blockers. Include `schema_version`; reject unknown/unsupported versions.
2. Add the five record families proposed by specification §9: integrations, versions, form decisions, artifacts, and integration audit entries. Add explicit keys, indexes, version counters, status validation, and integrity checks. Validate parent references in both SQLite and PostgreSQL rather than assuming identical defaults.
3. Seed only stable `nfpa72` and `compliance` identities idempotently. Do not auto-publish, auto-import legacy drafts, or modify checklist definitions.
4. Keep a published version immutable. Allow draft edits with an expected revision; freeze published payloads and verification evidence. Activation references a retained published version. Define audit records for every edit, publication, activation, and disablement.
5. Save manual answers as append-only decisions with stable input IDs, semantic/type compatibility metadata, integration version, inspection and optional panel scope, author/time, and override reasons. Reuse prior answers across versions only after explicit schema compatibility validation.
6. Define artifact records for previews/test runs and final exports with lifecycle status, version, scope, source snapshot, provenance, output hash, actor/time, and unique internal storage key. Preview confirmation needs a server-retained record or equivalently bound opaque token; it cannot trust client-provided field values or hashes alone.
7. Add an application feature switch independent of legacy template configuration, plus per-integration enablement. Gate only new routes/assets/actions. Ensure dependency imports and new failures do not break legacy startup when disabled.
8. Use private directories such as `_pdf_integrations/{key}/{version}/` and `{inspection_id}/form_exports/{artifact_id}/` beneath the current upload volume. Accept IDs through validated lookup; never accept caller-supplied filesystem paths.
9. Rehearse idempotent additive initialization on fresh databases and populated pre-change databases. The current store uses `Base.metadata.create_all` and compatibility helpers; add only what the new tables need and document future schema-version handling. No migration framework replacement is required.

Exit gate: prior rows/drafts/audits remain unchanged, initialization is repeatable, records persist across restart, and disabled integration behavior leaves the baseline intact. Update the decision log and data-structure documentation when schema implementation occurs.

P2 evidence: [contracts, schema and private storage report](PDF_INTEGRATION_P2_REPORT.md). Initialization is opt-in and independent of legacy PDF settings; publication/export services and UI remain later-phase work.

## 7. P3 — Typed sources, mapping rules, and readiness

Tasks:

1. Build a read-only source catalog for inspection metadata, stable checklist task IDs, selected approved panels/points/times, additional form details, approved constants, and allowlisted computations.
2. Resolve checklist values with existing latest-decision and legacy checkbox semantics. Detect type changes, deactivated sources, and removed choices without rewriting answers or history.
3. Implement explicit source/target type compatibility. Preserve zero, No, NA, empty, and missing distinctly. Define numeric bounds, units, date/time precision, timezone handling, and validation for additional inputs.
4. Implement declarative transforms and answer groups. Validate on/off states and clear all nonselected members. Keep visual/functional tests and installed/tested-good values independent unless a reviewed rule links them.
5. Implement conditionally required fields and an allowlisted applicability vocabulary. Support required remarks/work-order references for configured negative outcomes. No answer is automatically a passing answer.
6. Define counts only over explicit classified/approved data and scope. Do not derive good counts from timestamps or classifications from descriptions/highlights. Report insufficient structured information as a blocker or required manual input.
7. Implement explicit panel applicability, required-scope membership, and the reviewed no-panel case. Prevent empty/omitted scope from bypassing required point checks. Validate ownership and deletion for every panel ID.
8. Build read-only readiness validation using the authoritative existing rules as the reference. Initially avoid refactoring the current Initiating Devices endpoint; share helpers only with demonstrated equivalence tests if necessary.
9. Define structured blocker codes with target/source IDs, section, message, and navigation destination, for example `MISSING_ANSWER`, `UNACCEPTED_EVENT`, `SOURCE_CHANGED`, `AMBIGUOUS_TARGET`, `OVERFLOW`, and `SIGNATURE_POLICY_UNRESOLVED`.
10. Produce a canonical snapshot of configuration version, input schema, selected scope, saved source rows/decisions, and provenance. Hash typed values deterministically; exclude volatile read timestamps. Changes to relevant task definitions and applicability must invalidate affected snapshots too.

Exit gate: pure rule tests cover valid, missing, incompatible, and ambiguous cases; source APIs cannot mutate inspection data; request-supplied answers cannot bypass saved-data validation.

P3 evidence: [saved sources, mapping and readiness report](PDF_INTEGRATION_P3_REPORT.md). Normal readiness uses the saved active configuration and database-enforced read-only snapshots. Count mappings without approved classification/result data fail closed; admin draft catalogs remain explicitly diagnostic.

## 8. P4 — Administration backend and publication

Tasks:

1. Add admin-only routes for listing integrations, template intake, draft creation/copy, inventory/preview access, mapping updates, testing, publication, activation, and disablement. Reuse current authentication/reset-password/admin enforcement.
2. Validate PDF content, configured size/page limits, encryption support, filenames, and parser results. Quarantine incomplete intake privately; retain originals and diagnostics without executing embedded actions.
3. Lock initial page selections to NFPA 1–4 and Compliance 1. A different source fingerprint requires a new verified inventory/version; never reuse verification by field name alone.
4. Save mapping changes with expected revision checks. A stale save or concurrent publication returns the repository-compatible conflict response and preserves both users' work for review.
5. Provide diagnostic test renders with synthetic values, target/group coverage, duplicate warnings, overflow checks, and renderer metadata. Mark them as test documents; never count them as completed inspection exports.
6. Publication validates every included target disposition, source/type compatibility, grouping, presets, blank/exclusion reasons, policies, and all-page test evidence tied to the exact configuration hash. Editing a relevant mapping invalidates affected test/verification evidence.
7. Publish and update the active-version reference transactionally with audit metadata. Retain old versions; activation of a previous version and disablement must be explicit auditable operations.

Exit gate: direct non-admin API attempts fail; malformed/incomplete/ambiguous drafts cannot publish; tests prove immutable published configuration and conflict handling across database sessions.

## 9. P5 — Visual Admin mapping workspace

Tasks:

1. Add Administration → Integrations without changing current Users, Panel Types, or Inspection Tasks behavior. Explicitly extend tab selection and refresh dispatch; the current refresh fallback assumes the task tab.
2. Show both integration cards with status, selected pages, fingerprint/version, verification counts, and last editor/time. Include draft, test, publish, disable, and previous-version actions according to state.
3. Implement page navigation, zoom, field rectangles, keyboard selection, inventory search, and two-way selection between preview and target list. Verify coordinate conversion at several zooms and viewport sizes.
4. Display friendly labels alongside exact field identity/type/flags, source/default values, warning diagnostics, duplicated/linked locations, and allowed export states.
5. Add typed source selection, transform configuration, requiredness/applicability, explicit dispositions, manual-input definitions, overflow settings, signature policy, and verification actions. Surface intentionally linked targets before saving.
6. Provide save/conflict recovery, test-render comparison, unresolved-target filters, and a publication summary requiring explicit confirmation. Do not lose unsaved edits on background refresh or switching pages.
7. Update package data, UI asset routing, and release packaging checks. Keep legacy NFPA/template dialogs and their event handlers independent.

Exit gate: browser tests show exact duplicate-location selection, map/test/verify/publish behavior, conflict handling, keyboard use, narrow layouts, and preserved existing admin tabs.

## 10. P6 — Technician Form Details and readiness UI

Tasks:

1. Add authorized APIs to read/write additional form decisions, retrieve resolved source status, select explicit panel scope, and view readiness. Distinguish ordinary additional answers from overrides requiring a reason.
2. Add a collapsible Export Form Details section with separate NFPA/Compliance organization, typed inputs, units, required/conditional indicators, source links, override badges, and signature/supplemental-sheet explanations.
3. Reuse current save expectations while preserving unsaved local edits. Make failed saves visible and block preview confirmation until required changes are saved. Do not alter existing Store Data, checklist, or points saves.
4. Integrate saved values and readiness into the existing periodic refresh lifecycle, including hidden-tab recovery, navigation cancellation, deletion, retry, and inspection changes. Use local dirty-state tracking; do not overwrite unsaved input.
5. Show separate export actions with disabled/unavailable reasons and field-level links to blockers. A missing mapping or failed integration must not disable existing actions.
6. Detect incompatible published input-definition changes. Preserve earlier decisions, flag fields needing review, and avoid carrying an old answer into a different question with the same label.

Exit gate: two-device/browser scenarios prove saved synchronization, private unsaved edits, source-change warnings, save-failure recovery, explicit scope, and uninterrupted legacy workflows.

## 11. P7 — Preview, confirmation, rendering, and retained export

Tasks:

1. Resolve and validate a consistent saved-data snapshot for preview. Store/bind its integration version, configuration hash, scope, source fingerprint, renderer version, requester/access context, and draft artifact hash. Watermark previews visibly.
2. Make preview read-only with respect to inspection answers/statuses. Opening it must not accept events, complete tasks, or change existing drafts.
3. Confirm using the retained preview identity. Recheck current authorization, feature/integration state, published version, scope, readiness, and a new consistent source snapshot on the server. Reject changed data with a useful stale-preview response.
4. Define final acceptance at acquisition/validation of that consistent confirmation snapshot. Render only that frozen snapshot. Use a transaction strategy proven on PostgreSQL and SQLite, avoiding mixed reads; test changes before confirmation versus changes after the snapshot boundary. Later edits create a new export candidate and never rewrite an accepted artifact.
5. Complete verified rendering: reset preset values/appearances, populate approved dispositions, enforce text bounds and glyph coverage, handle result groups, remove active actions, flatten, and include exactly the permitted pages. Run output structural checks before retention.
6. Generate sanitized approved filenames using saved completion date and any configured panel disambiguation. Unique internal IDs prevent overwrite even when download names match.
7. Implement a recoverable file/database lifecycle: create a non-downloadable pending record, render to a temporary private file, atomically move it within the persistent volume, then finalize the record with its hash/metadata. A download requires a ready record and matching file. Handle database failure after file creation with retained status/reconciliation; never claim a filesystem rename and SQL commit are one atomic transaction.
8. Add idempotency for retries of the same final-confirmation request so connection retries do not accidentally duplicate artifacts. An intentional later export can receive a new request ID and creates a new retained artifact.
9. Add authorized export history/downloads, safe content-disposition headers, provenance retrieval, and clear failed/pending states. Define bounded cleanup for temporary previews and abandoned incomplete files; never delete final artifacts, originals, or decision history through temporary-file cleanup.

Exit gate: correct PDFs download after successful retention; stale/forged confirmations fail; concurrent changes never mix snapshots; renderer/file/database failures and restart recovery leave no partial downloads and preserve inspection data.

## 12. P8 — Configure and verify both supplied forms

Tasks:

1. Upload each supplied PDF privately and reconcile inventory to the specification fingerprints/counts. Any derivative must preserve original lineage and verified field correspondence.
2. Build the field catalog with section/friendly labels and exact target IDs. Include custom rows, duplicated locations, footer widgets, contact fields, and signature locations. A widget count is not a substitute for business-field verification.
3. For every target, select an existing typed source, approved constant, defined computation, additional input, or explicit blank/exclusion/signature policy. Resolve the P0 decisions as they become concrete in the workspace.
4. Review all preset selections, sample values, historical dates, and instructions. Clear or replace inspection-specific defaults; approve genuine constants explicitly.
5. Test NFPA page 1 identity/system data; page 2 power, notifications and visual/functional results; page 3 monitoring/interface data; page 4 completion, restoration, certification, defects and acceptance.
6. Test every Compliance section, separating quantities, tested-good counts, result marks, NA fields, custom lines, remarks, work-order decisions, and signature/print-name destinations.
7. Use labeled sentinel tests and realistic synthetic completed inspections. Exercise every answer state/group, conditional section, blank policy, longest permitted text, numeric bounds, and timezone/date rule.
8. Retain private all-page visual review evidence and a coverage manifest tied to each candidate configuration hash. Obtain explicit administrator verification through the publication workflow.

Exit gate: both configurations are publishable with no unresolved required policies or target dispositions. Full outputs are readable at normal scale and in print. Remaining deliberate limitations are visible to the technician.

## 13. P9 — Verification matrix and release gate

Add focused tests with synthetic data/PDF fixtures; test names below are proposed:

| Layer | Proposed tests | Essential evidence |
| --- | --- | --- |
| Schema/storage | `test_pdf_integration_storage.py` | Fresh/populated SQLite and PostgreSQL, repeat initialization, immutable versions, history retention, conflict checks |
| Inventory | `test_pdf_integration_inventory.py` | Duplicate names/parents, malformed diagnostics, stable IDs, page geometry, unsupported templates |
| Domain | `test_pdf_integration_mapping.py`, `test_pdf_integration_readiness.py` | Typed values, legacy answers, groups, applicability, scope, missing inputs, signatures, overflow |
| Saved sources | `test_pdf_integration_sources.py` | Stable task/panel IDs, provenance, source changes, deterministic snapshots, accepted versus pending events |
| Admin API | `test_pdf_integration_admin.py` | Auth/admin enforcement, stale edits, publication coverage, test-evidence invalidation, activation/disablement |
| Inspection API | `test_pdf_integration_exports.py` | Deleted/inaccessible inspection, forged requests, stale preview, consistent final snapshot, idempotency, retained downloads |
| Renderer/recovery | `test_pdf_integration_renderer.py` | No preset leakage, flattened appearances, permitted page count, no active actions/excluded hidden fields, storage/DB fault recovery |
| Browser | `test_pdf_integrations_browser.py` | Admin mapping and technician export journeys, save failures, narrow screens, keyboard selection, two-device refresh/conflicts |

Run targeted checks per coherent change, then the full suite at release. Run opt-in browser tests explicitly; skipped browser/PDF dependency tests do not establish coverage. Test with PostgreSQL separately from the default SQLite path. Keep private supplied-form validation as a required release task even when CI uses synthetic fixtures.

Regression coverage must include existing tests for PDF exports/templates, review fixes, event retention/status, typed tasks, task/dropdown ordering, panel types, highlights, inspection lifecycle/naming, and live synchronization. Add characterization coverage only where existing tests cannot protect an identified compatibility risk. Run the actual Points List review interaction as well as new exports.

Before release, require:

- All specification §11 acceptance criteria traced to automated evidence or signed-off private manual review.
- All five included pages verified in a browser and an independent viewer, with print checks and no JavaScript dependence.
- Both source-to-output mappings and artifact provenance reviewed; negative outcomes remain negative.
- Feature-off and failure-isolation checks pass; existing records/history compare unchanged except explicitly authorized new decisions.
- Recovery, retry, disablement, previous-version activation, and prior-application rollback rehearsed.
- Package/container includes new assets, required fonts/rasterizer dependencies, and permission configuration; no source PDFs or secrets in Git/image layers.
- Compile check passes and test skips/known limitations are reported explicitly. No unsupported claim that testing guarantees every possible existing behavior.

## 14. P10 — Controlled rollout and handoff

1. Update architecture, data-structure documentation, decision log, and deployment/operator guide with final implemented boundaries and dependencies. Document mapping setup, field verification, publication, missing-input resolution, artifact recovery, and rollback.
2. Commit coherent changes with specific staged files and push using the repository workflow. Resolve GitHub authentication before a release depends on remote commits; do not deploy an unpushed local build as though it matches `origin/main`.
3. Back up the inspection database and upload volume and record the currently deployed commit/image. Keep backups private. Do not touch the separate `/opt/serviceflow` application or its Compose project.
4. Deploy the reviewed commit to `/opt/inspections` over SSH using AGENTS.md's production procedure. Keep new integrations disabled initially. Verify startup/schema initialization and existing application behavior first.
5. Confirm the server checkout contains the intended commit, `inspections` Compose services are running, and health succeeds at both localhost and the documented external endpoint.
6. Privately install templates/configurations, test exact deployed rendering, publish verified versions explicitly, and enable the new feature/integrations. Never rely on developer-machine template paths existing on the server.
7. Test a synthetic inspection through live Form Details, readiness blockers, preview, final download, history, and re-export for each form. Inspect downloaded PDFs. Test the actual existing Points List review and accepted event behavior; a health response is insufficient.
8. Verify persistence across application recreation and confirm the other application remains isolated. Report deployed commit, enabled mapping versions, test evidence, and remaining deliberate limitations.

Rollback: disable new integrations/actions first. If necessary, restore the previous application image/commit using the deployment runbook while retaining additive tables and all original/decision/artifact files. Reactivate a prior verified mapping version for mapping-only defects. Do not drop tables or erase accepted history as rollback. Re-run existing health and review checks after rollback.

## 15. Suggested commit sequence and completion tracking

Keep each batch reviewable; split a batch further if it grows. Update checkboxes only when the exit gate is met, not when code is merely written.

- [x] Baseline/decision register and synthetic PDF fixture support (P0–P1). See [part 1 evidence and limitations](PDF_INTEGRATION_PART1_REPORT.md); final mapping, viewer/print acceptance, and production intake hardening remain later-phase gates.
- [x] Typed contracts, additive tables/private file lifecycle, disabled feature switch (P2). See [P2 report](PDF_INTEGRATION_P2_REPORT.md).
- [x] Saved source catalog, deterministic mapping and readiness rules (P3). See [P3 report](PDF_INTEGRATION_P3_REPORT.md).
- [x] Admin draft/test/publication/version lifecycle APIs (P4). See [P4 report](PDF_INTEGRATION_P4_REPORT.md).
- [x] Visual Admin → Integrations workspace and packaged assets (P5). See [P5 report](PDF_INTEGRATION_P5_REPORT.md).
- [x] Inspection-specific Form Details, scope and readiness UI/API (P6). See [P6 report](PDF_INTEGRATION_P6_REPORT.md).
- [x] Snapshot-bound previews, confirmed final renderer, artifact history/recovery (P7). See [P7 report](PDF_INTEGRATION_P7_REPORT.md).
- [ ] Both supplied forms configured and privately verified; policy decisions recorded (P8).
- [ ] Full regression, viewer/print evidence and release documentation (P9).
- [ ] Controlled production enablement, live interaction verification and handoff (P10).

For every code batch: add appropriate meaningful tests before changing deterministic rules, run targeted checks, run `python -m compileall -q src tests`, stage specific files, commit, and push. Leave unrelated working-tree changes untouched. Broaden tests at integration/release boundaries and after any failure or substantive new risk.

Outstanding limits to communicate at handoff: NFPA pages 5–11 are excluded; supplemental reports remain separate; no automatic signature service or AI dependency is included; publication depends on administrator-approved mappings and business policies; original NFPA source pagination may reference eleven pages. Scheduling estimates should be made after P1 proves the rendering strategy and P8's field-review workload is understood.

P4–P6 verification (October 29, 2026): the final full suite passed **274 tests**, with PostgreSQL and browser tests explicitly enabled, no skips, and one pre-existing test-client deprecation warning. Compile, JavaScript syntax, whitespace, documentation links and packaged-asset checks passed. Rendering and slow integration reads were separately exercised while existing inspection saves/synchronization continued. No production deployment or enablement occurred.

October 29 user direction: panel/category applicability, site timezones and company/contact defaults must be adjustable; the user will establish defaults later. P8–P10 may prepare/install unpublished drafts and deploy the configurable framework with exports disabled. Business mapping approval, publication, enablement and final supplied-form acceptance remain deferred gates; do not label those gates complete based on framework tests.
