# PDF Export Integrations Specification

Status: proposed implementation specification; no application behavior is changed by this document.
Date: October 28, 2026.

## 1. Objective and scope

Add two configurable PDF export integrations to the existing inspection application:

| Integration | Inspection action | Initial output |
| --- | --- | --- |
| NFPA 72 | **Export NFPA 72** | Exactly pages 1–4 of the supplied Fire Alarm PDF |
| Compliance inspection | **Export Compliance Form** | The supplied one-page Compliance PDF |

The technician completes and saves inspection data, resolves required decisions, then exports a completed form. An administrator configures how saved inspection data populates each PDF under **Administration → Integrations**. Configuration is shared across inspections, while answers, overrides, and generated documents belong to an individual inspection.

The governing constraint is preservation of all existing inspection functionality. This is an additive feature. Implementation must not replace the application, redesign its workflow, or change existing export eligibility. Form contents are reference material for identifying destinations and required business decisions; embedded PDF scripts and instructions are not application requirements or executable configuration.

Initial scope excludes NFPA pages 5–11, additional integration types, automatic attachment merging, automatic device classification from descriptions, an AI API dependency, and a digital-signature service. Do not claim that this four-page export by itself contains all supplemental sheets referenced by the form.

## 2. Existing implementation and compatibility boundary

This specification is based on the actual source, including:

- `storage.py`: inspections, panels, accepted/review point decisions, accepted and pending event times, checklist definitions and decision history, source files, and two existing PDF draft models.
- `api/pdf_templates.py`: an NFPA-only template registry, field-name extraction, string normalization, and form filling.
- `api/routers/inspections_templates.py`: existing template draft, preview, and download endpoints.
- `api/routers/inspections_nfpa_draft.py`: the separate NFPA draft workflow.
- `api/routers/inspections_export.py`: gated Initiating Devices export using saved, accepted data for an explicitly selected panel.
- `domain/checklist.py` and `api/routers/inspection_tasks.py`: typed checklist values and append-only decision history. For checkbox tasks, Yes, No, and NA all count as answered; answered does not mean passed.
- `api/app.py`, `api/index.html`, and `api/review.js`: authentication, administration, inspection UI, and shared refresh behavior.

Existing template helpers are insufficient as the authoritative mapper for these forms: a sorted list of names and string values cannot distinguish every widget location, validate semantic answer groups, or safely handle defaults and signatures.

Mandatory compatibility requirements:

1. Preserve existing URLs, request/response contracts, saved PDF drafts, template configuration, and draft editing/download behavior. Existing drafts must never be silently adopted as approved integration mappings or overwritten.
2. Preserve Points List parsing, category/panel association, review modal, editable descriptions, Accept/Review controls, separate bulk deletion, and explicit commit confirmation. Do not add a source-row or per-row Delete column.
3. Preserve repeated Event History intake, pending evidence, explicit acceptance, successful mappings, manual correction rules, and audit evidence.
4. Preserve existing checklist answers and history, task ordering, dropdown behavior, inspection naming, highlights, deletion, authentication, permissions, and cross-device refresh.
5. Preserve the Initiating Devices export and its filename exactly: `{store#}-{city},{state}-Initiating Devices-{category}-MM-DD-YY.pdf`.
6. New integration failures or incomplete configuration must not prevent existing inspection work or existing exports. Enforce the new gates only on the two new completed-form exports.
7. Use additive storage changes. Do not rename, drop, truncate, or repurpose existing tables/columns. Any shared refactor must have demonstrated compatibility and a separate justification.

## 3. Supplied PDF assessment

Both files were inspected locally with PDF metadata/text extraction, widget inspection, and representative page rendering. No original PDF is included in the repository by this specification.

| Property | NFPA 72 source | Compliance source |
| --- | --- | --- |
| Filename | `0000-city, VA Fire Alarm Inspection 00-00-00.pdf` | `0000-City, VA Compliance Inspection 00-00-00.pdf` |
| Source pages | 11 | 1 |
| Included pages | 1–4, in source order | 1 |
| Page geometry | US Letter, 612 × 792 PDF points; reported rotation 0 | US Letter, 612 × 792 PDF points; reported rotation 0 |
| Forms | AcroForm; embedded JavaScript present | AcroForm; embedded JavaScript present |
| Included widget locations | 196: page counts 40, 65, 49, 42 | 283 |
| Included widget types | 132 text, 58 button, 4 choice, 2 signature | 127 text, 141 button, 13 choice, 2 signature |

Counts describe annotation/widget occurrences, not business questions or necessarily unique field names. Button fields require subtype/flag inspection before treating them as checkboxes or radio controls. Full-document `get_fields()` counts include parent nodes and excluded NFPA pages and must not be used as the mapping completeness denominator.

Source SHA-256 fingerprints:

```text
NFPA 72:   b956b9c0ae6864970eb2f582a12a9e59d81162e1843f3b8e54f536a08d43aa71
Compliance: f51cb8c0808fa356382b0672ef0f5613306def35503ec37721fe7923ce6c8dd2
```

### 3.1 Specific reliability findings

- Names are not reliable semantic labels. For example, Compliance uses `InspectionTest Start DateTime` for the visible date-of-inspection destination, and some NFPA button widgets have leaf names `0` and `1`.
- Some locations share a fully qualified name. NFPA examples include `Store Address`, `Name of property representative`, and date/time fields. Compliance includes repeated `INSPECTOR NAME` and `RELAYS GOOD` paths. Shared names may represent intentional mirroring or unintended coupling; each occurrence requires visual review.
- The parser reported duplicate dictionary-key warnings, including `/T`, `/DA`, and `/TU`. Template intake must surface these diagnostics and require a verified rendering strategy instead of treating extraction as unquestionably correct.
- NFPA contains preset visual-inspection and monitoring selections, a sample store number, contact information, placeholder instructions, and historical footer values. Compliance contains preset company/contact information and other values. These are not evidence that an inspection was performed or passed.
- Some printed labels are duplicated or misspelled, and dense tables place independent quantities, results, and NA indicators beside each other. Label text alone cannot identify a target.
- Both PDFs contain signature destinations. A typed inspector name must not be converted into a signature.

### 3.2 Required section coverage

| Form/page | Mapping coverage |
| --- | --- |
| NFPA page 1 | Start/completion date and time; supplemental-form declaration; property/store/representative information; testing and monitoring organizations; account and transmission information; document location; control unit, firmware, primary power |
| NFPA page 2 | Secondary power and battery capacity; pre-test notifications and times; control-unit and secondary-power visual/functional results and comments |
| NFPA page 3 | Supplementary-sheet references and interface text; supervising-station and public-emergency reporting results, times, comments |
| NFPA page 4 | Completion notifications; restoration date/time; certification details; unresolved defects/work orders; owner acceptance; signature destinations |
| Compliance page 1 | Inspector/store/panel details; sections 1–4 device counts and test results; 5 egress; 6 power; 7 communication; 8 audio/paging; 9 keypads/areas; 10 access control; 11 management training; 12 signage; 13 CCTV; 14 pharmacy CCTV; 15 work-order acknowledgement; remarks and signatures |

Inventory all writable widgets, including unlabeled/custom rows, totals, footer widgets, and repeated locations. Treat printed explanatory text separately from writable destinations. Preserve the supplied layout, labels, legal notices, and source pagination; the NFPA footer may still say “p. 1 of 11” on a four-page export. Record that limitation in integration details.

## 4. Technician experience

1. Complete the inspection through the current workflow and save pending edits.
2. Any additional answers required only by a form are collected in a new collapsible **Export Form Details** section. This section is independent of current Store Data, Check List, and Points Lists & Events behavior. Its fields come from the selected integration's published source definitions, with clear required/optional labels.
3. Display **Export NFPA 72** and **Export Compliance Form** as separate actions. If an integration is unavailable or incomplete, show the reason beside its action. Leave existing actions usable.
4. If the form needs panel-specific data, require an explicit panel selection or a previously saved, explicit scope choice. An inspection with several panels must never silently use the first panel or aggregate incompatible equipment. Custom panel categories require explicit applicability configuration.
5. Run server-side readiness validation. Show missing answers and unresolved decisions by form section and field, with links to the appropriate input. Never infer readiness from a completion date or client-side button state.
6. When ready, show the completed form preview and a concise summary of the integration version, selected scope, and any deliberately blank fields such as signatures reserved for later signing. Require confirmation to download the final export. Draft previews must be visibly marked and cannot be represented as completed exports.
7. Save the completed artifact and its provenance, then download it. Repeated exports create separate retained artifacts; they do not overwrite prior exports or change the inspection's accepted data.

Opening a preview must not write new answers, accept pending evidence, change statuses, or complete checklist tasks. If saves fail, remain on the inspection and identify unsaved fields. A failed integration export must retain all entered inspection information.

## 5. Administration → Integrations

Add an Integrations option alongside existing administration options, initially listing exactly **NFPA 72** and **Compliance inspection**. Only administrators may upload/configure templates, edit mappings, test configuration, publish versions, disable an integration, or select a prior published version.

Each integration displays its status (Unconfigured, Draft, Published, Disabled), template filename/fingerprint, included page range, verified/unresolved target count, published version, and last editor/time.

### 5.1 Visual mapping workspace

Provide a zoomable page preview, page navigator, highlighted field rectangles, searchable inventory, and mapping editor. Selecting a rectangle selects its inventory entry; selecting an inventory entry scrolls/highlights that exact location. Support keyboard selection and labeled controls.

For each destination show:

- Stable target ID, friendly label, form section, source page, widget occurrence, rectangle, fully qualified PDF name, type/flags, tooltip, existing/default values, and permitted choice/export states.
- Mapping source, source type, formatting/transform, requiredness/applicability, missing-value policy, overflow behavior, and administrator verification status.
- Whether the widget shares a field name or parent with another location; highlight all affected locations before saving a linked mapping.

The target identity must include the immutable template fingerprint, page, widget occurrence/rectangle, and qualified field path. Do not rely on leaf name, label, array position across different versions, or PDF object number alone. Group widgets intentionally only after review; do not couple unrelated locations with the same name.

Support mapping to a verified rectangle overlay if native filling is ambiguous, malformed, or unavailable. Overlay mode must suppress the original field appearance/value in that region without erasing printed labels or allowing the old widget to reappear. If safe isolation is impossible, require a private, reviewed normalized template derivative or block publication. Never modify the original upload.

### 5.2 Target disposition and publication

Every included writable target must have an explicit disposition: mapped source, approved static value, computed value, manual form-detail input, intentionally blank with reason, or excluded with reason. Signature targets have a separate signing disposition. Record administrator identity/time for verification.

Publication requires complete inventory coverage, compatible value types, explicit group behavior, resolution of duplicate/ambiguous targets, disposition of every preset, and verified test output on all included pages. No “best guess” mapping may be published. Static values may describe an approved organization or invariant; never use them to manufacture test outcomes, notification times, acceptance, or signatures.

Changing a published template or mapping creates a draft version. Require preview/testing and an explicit Publish confirmation with a change summary. Keep the previous published version available. An administrator can reactivate a prior version without deleting subsequent versions or exports. Reject concurrent stale edits with a conflict message; do not silently overwrite another administrator's work.

## 6. Source catalog and mapping rules

Expose a typed, allowlisted source catalog rather than raw database access or executable expressions.

| Source family | Supported values and constraints |
| --- | --- |
| Inspection | Store number, store type, address, city, state, inspector name, start date, completion date |
| Checklist | Stable task ID, compatible current saved answer, and decision provenance. Labels are for display; matching must not depend on wording or task order |
| Selected panel | Stable panel/list ID, category, accepted/undeleted points, saved locations/descriptions, accepted test times and their provenance |
| Form details | Additional inspection-specific text, numeric measurements, date/time, explicit Yes/No/NA choices, defects/work orders, contact data, and acknowledgements |
| Approved constants | Versioned organization/contact information or other reviewed invariants |
| Computed values | Allowlisted, deterministic formatting, concatenation, explicit answer lookup, and defined counts over an explicitly selected approved dataset |

NFPA date/time destinations cannot obtain a real time from the current date-only `Inspection.start_date` and `completion_date`. Capture required times explicitly, with a recorded timezone, or approve a date-only policy for that destination. Do not invent midnight or use export time as inspection time. A completion time is not automatically a restoration or notification time.

Panel model, account number, battery readings, contact names, defects, and similar values are not all structured fields in the current store. Resolve them with typed existing checklist mappings where suitable, or isolated Form Details inputs. Do not claim these values already exist. Creating integrations must not create or alter shared checklist tasks automatically.

Apply these rules in Python with focused tests:

1. Distinguish missing, empty, zero, No, NA, not tested, and failed. Never use truthiness or `completed=True` as a substitute for a test result.
2. Use the latest applicable saved checklist decision with the existing legacy checkbox interpretation. Type changes, deactivated/deleted sources, or removed dropdown choices must surface compatibility warnings and require explicit resolution; never silently remap by text or select a replacement option.
3. Map Yes/No/NA groups explicitly. Validate PDF on/off export states and mutual exclusion; clear all other marks in the group. If a destination offers only Yes/No, an NA answer needs an approved policy or blocks export.
4. Identify independent visual versus functional tests and installed versus tested-good quantities. Do not reuse one answer for both unless explicitly configured and verified.
5. Counts use documented classifications and scope. An accepted point or an accepted timestamp does not alone prove a device passed. Do not infer installed counts, good counts, camera coverage, or safety results from free-text descriptions/highlights.
6. Approved transforms are declarative and deterministic: date/time formats, explicit timezone conversion, number/unit formats, concatenation, and enumerated lookups. Disallow arbitrary Python, SQL, JavaScript, network calls, or administrator-supplied code.
7. Detect unsupported characters and text overflow. Wrap only inside verified multiline areas, or shrink to an approved minimum readable size; otherwise block final export and identify the field. Never silently truncate, overlap adjacent fields, or append pages in this initial fixed-page release.
8. Each template's existing values must be explicitly retained as an approved constant, replaced, or cleared. Reset preset result selections and old appearances before populating actual results. Inspect historical footer dates separately from legal/version text.
9. Form-detail overrides are separate saved decisions with author, time, reason, and original/resolved values. They do not update source inspection fields or erase history. Highlight overrides and detect stale overrides after source changes; require revalidation.
10. Signatures require an explicit policy per target. Version one may leave designated fields blank for later signing and disclose this in preview. If a signed form is required, block completed export until a supported signing workflow is separately specified. Do not copy template signatures, fabricate signatures, or label an unsigned form as signed.

## 7. Completion and final-export gates

Readiness must be enforced by the server on both preview approval and final export:

- The inspection exists, is not deleted, and is accessible under current authentication rules.
- The integration has a published, enabled version matching the immutable template and selected page range.
- Inspection identity/location and all configured required answers, measurements, and manual decisions are saved and valid.
- Explicit panel scope is present wherever needed. All required point review decisions and accepted point-to-time mappings within that scope are complete, using existing authoritative validation semantics. Pending evidence never substitutes for accepted mappings.
- Unrelated panels are not silently combined; the scope and any allowed exclusion are visible. An inspection-wide integration validates every panel in its explicitly configured required scope. An empty scope cannot bypass required point checks. A form that genuinely needs no panel data requires an explicit, reviewed no-panel applicability policy.
- Every included target has a verified disposition. Required fields are populated or have an explicit allowed NA/blank policy. No duplicate target assignment, unresolved transform, incompatible choice, overflow, stale override, or unsupported signature requirement remains.
- Required supplemental sheets/declarations are resolved. NFPA supplemental-form checkboxes must reflect an actual user-confirmed attachment decision, not the supplied preset. Existing Initiating Devices reports remain separate; this release does not automatically merge them.

A No/failed outcome can be a complete answer. Require configured remarks/work-order decisions where appropriate; never turn failures into passing answers to permit export.

Take a consistent saved snapshot for validation and rendering. Record a source revision/fingerprint in readiness and preview responses. If inspection data, form details, panel scope, or the published integration version changes before final confirmation, require a refreshed preview instead of generating a mixture of old and new values. Apply this check server-side across devices/processes.

## 8. Rendering and output contract

Use the original PDF layout as the background. Render only the selected pages, preserve page geometry and printed content, and populate all configured destinations using verified native appearances or safe overlays. Native PDF scripts/calculations must never be required for correct output; implement required logic in deterministic Python.

Final artifacts must have self-contained visible appearances and be flattened for consistent viewing/printing. Do not depend on `/NeedAppearances`, an open browser tab, or Acrobat executing JavaScript. Remove active actions and references to excluded pages from generated derivatives. Keep the original upload unchanged. Keep draft previews visibly distinct from finals.

Proposed filenames for the two new exports, using the saved inspection completion date:

```text
{store#}-{city},{state}-Fire Alarm Inspection-MM-DD-YY.pdf
{store#}-{city},{state}-Compliance Inspection-MM-DD-YY.pdf
```

These are proposals following the supplied form names; they do not change the mandated Initiating Devices filename. Sanitize filenames without changing displayed inspection data. Use a unique internal artifact ID/path even when the download filename repeats. If multiple panels produce separate files, include an approved disambiguating panel label and retain the panel ID in artifact metadata.

Store template/mapping version, selected scope, snapshot fingerprint, resolved value provenance, exporter identity/time, renderer version, output hash, filename, and success/failure status. Download authorization must match current inspection access rules. Do not expose private storage paths. Write artifacts atomically and return a final download only after both the complete PDF and its export record are retained; never expose partial files.

## 9. Proposed technical boundary

Add dedicated Python modules under `src/alarm_inspection/` for template inventory, typed source resolution, mapping validation, export readiness, and rendering. Keep deterministic rules under `domain/` and HTTP handling in new integration-specific routers under `api/routers/`. Register the additive routes in the existing app; do not replace current routers.

Proposed additive persisted records:

| Record | Purpose |
| --- | --- |
| PdfIntegration | Stable `nfpa72` / `compliance` identity, enabled state, published-version reference |
| PdfIntegrationVersion | Immutable original/normalized template references and hashes, page selection, verified inventory, mapping schema/version, constants, manual-input definitions, applicability, publication metadata |
| InspectionFormDecision | Append-only form-detail answers/overrides, stable source key, inspection/integration IDs, source compatibility metadata, actor/time/reason |
| PdfExportArtifact | Immutable artifact path/hash, status, scope, template/mapping version, source snapshot and provenance, creator/time |
| PdfIntegrationAuditEntry | Configuration, verification, publication, activation, and disablement history |

Use an additive migration consistent with current PostgreSQL and local SQLite behavior. Define a versioned JSON schema for inventories/mappings and validate on save and export. Preserve legacy draft tables unchanged; any future import must be an explicit, reviewed copy operation.

Illustrative additive API surface (final naming to follow repository conventions):

| Route family | Responsibility |
| --- | --- |
| `/api/admin/integrations` | List the two integrations; admin-only configuration |
| `/api/admin/integrations/{key}/versions` | Private template intake, draft versions, inventory and mappings |
| `/api/admin/integrations/{key}/versions/{version}/test` | Diagnostic sample rendering and validation, never a completed inspection export |
| `/api/admin/integrations/{key}/versions/{version}/publish` | Explicit publication after verification and concurrency checks |
| `/api/inspections/{id}/form-integrations/{key}/details` | Authorized inspection-specific form answers and history |
| `/api/inspections/{id}/form-integrations/{key}/readiness` | Required inputs, scope, missing decisions, source revision |
| `/api/inspections/{id}/form-integrations/{key}/preview` | Draft output from the validated saved snapshot |
| `/api/inspections/{id}/form-integrations/{key}/exports` | Confirmed final generation and retained artifact history |

Validate keys, scopes, and source identifiers server-side. Template intake must enforce configured size/page limits, parseability, and expected PDF content; report malformed/encrypted/unsupported forms clearly. Never execute embedded scripts, launch actions, or remote resource references. Use private existing application storage and permissions; no new external service or AI key is required.

## 10. Implementation sequence and rollback

1. Establish the current regression baseline and use synthetic fixtures. Inventory/visually verify all included destinations from the supplied private forms, resolving malformed/duplicate targets before building final export behavior.
2. Add isolated storage, typed sources, mapping validation, and Admin → Integrations behind a disabled-by-default feature setting. Test drafts without altering current workflows.
3. Add optional Form Details entry, deterministic readiness, snapshot validation, rendering, and the two export actions. Configure/test the supplied templates in private storage.
4. Verify all pages and answer groups, publish each integration explicitly, then enable the new actions. Publish NFPA only with pages 1–4 selected.
5. Regress existing workflows before any deployment. Deploy only through the separate `inspections` project and established deployment procedure when implementation/deployment is authorized.

Rollback disables the new integrations/actions and restores the previous application release if necessary. Leave additive records, original templates, decisions, and generated artifacts intact. Do not roll back by dropping data. This specification alone requires no server deployment or database migration.

## 11. Acceptance and verification

The feature is acceptable only when the following are demonstrated:

1. An administrator sees both integrations, visually selects every included target, maps existing inspection/checklist sources and additional form details, tests output, and explicitly publishes a verified version. Non-admin API calls cannot configure or publish.
2. The measured 196 NFPA and 283 Compliance widget occurrences are reconciled to approved dispositions for these exact source fingerprints. Discovery differences and duplicate-key warnings are reviewed rather than silently ignored. Every business field and custom row is visually accounted for.
3. Sentinels distinguish neighboring cells and repeated names. Changing one unrelated target never changes another; intentionally mirrored locations update exactly as configured. Coverage includes all checkbox/radio states, choice values, blank/zero/No/NA, quantities, dates/times, comments, and signatures.
4. The NFPA final has exactly four pages in source order; Compliance has exactly one. Excluded-page form fields do not remain as hidden answer data or broken references. Printed text, geometry, and notices are preserved.
5. Preselected visual/monitoring results, sample values, placeholder instructions, and historical dates cannot leak into a final document without an explicit reviewed disposition. No pending event, incomplete review, or missing required mapping can be bypassed by request-supplied values.
6. Source gaps and ambiguity block final generation with useful field-level messages. Long text, unsupported characters, multiple panels, incompatible source changes, invalid PDF states, failed rendering/storage, stale previews, and concurrent publication are exercised.
7. Golden visual tests cover every included page using synthetic answers. Inspect actual saved PDFs in a browser viewer and Acrobat (or another independent PDF viewer), including print output. Confirm visible results are identical without JavaScript or form regeneration. Rendering tolerances must allow harmless rasterization differences while detecting misplaced/missing values.
8. Trace an exported answer back to its saved inspection/checklist/manual decision and mapping version. Re-export after edits creates a new artifact; earlier artifacts and their provenance remain readable. Changing published mappings does not rewrite prior documents.
9. Existing regression tests and actual browser interactions pass: Points List review/description edits/status controls/bulk deletion/confirmation; repeated events and accepted mapping retention; Initiating Devices gating and filename; existing NFPA/template drafts; checklist types/history; task/dropdown ordering; naming; highlights; deletion; authentication; administration; and cross-device refresh with unsaved edits preserved.
10. Turning the feature off or causing either integration to fail leaves existing inspection creation, entry, saving, review, and exports working. Verify both an existing database and a fresh database without rewriting customer records.
11. Before calling a future deployment complete, verify the server commit, `inspections` Compose status, health URL, new live page behavior, and actual review/export interactions. Do not modify the separate Work_Order deployment.

Run appropriate Python/domain/API and browser tests during implementation, plus the repository compile check. Use synthetic test PDFs/data in Git; keep supplied customer/reference PDFs, source extracts, generated outputs, and secrets out of commits.

## 12. Business decisions to resolve during configuration

These do not prevent reviewing or building the isolated framework. They must be resolved before publishing a production integration that depends on them:

- The exact stable checklist task mappings and additional inputs needed for every field; typed numeric/date/time validation where a textbox is insufficient.
- Which approved company/contact presets remain constants, and which values vary by inspection.
- Panel applicability/selection rules for Fire, Burglar, Combo, Gas Station, and custom categories, including any explicit no-panel Compliance use case.
- Date/time formats and site timezone; whether Compliance's inspection date means start or completion date. Proposed filename dates use completion date.
- Which questions are required versus conditionally NA/blank; defects and work-order acknowledgement requirements; supplemental-sheet declaration policy.
- Whether the exported document is ready for later handwritten signing or must already be signed. Signature capture/cryptographic signing requires a separate scope decision.
- Approval of the proposed two new filenames and multi-panel disambiguation.

Known limitation: widget discovery and representative rendering establish feasibility and risks; they do not establish a complete, business-approved field mapping. Full visual verification and test exports of all included destinations are implementation/publication gates.
