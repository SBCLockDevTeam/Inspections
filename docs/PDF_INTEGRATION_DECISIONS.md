# PDF Integration Decision Register

Date: October 28, 2026.
Scope: first implementation batch, P0–P1 of the [implementation plan](PDF_EXPORT_INTEGRATIONS_IMPLEMENTATION_PLAN.md).

## Technical decisions implemented in this batch

| ID | Decision | Evidence and limits |
| --- | --- | --- |
| T01 | Keep feasibility tools disconnected from FastAPI, storage initialization, and current UI | No existing application module, route, table, or asset is changed. Feature enablement belongs to P2 |
| T02 | Identify widget occurrences using original fingerprint, source page, annotation occurrence, rectangle, and qualified field path | Deterministic IDs distinguish repeated names. Replacing the source invalidates IDs. Selection changes do not change IDs on retained pages |
| T03 | Use a fresh PDF page tree, allowlisted drawing content/resources, and occurrence-specific vector overlays for the initial feasibility proof | Avoids field-name coupling and original widget appearances. Fresh documents omit form trees, annotations, actions, attachments, and excluded-page structures. Production security/structure checks remain P7 work |
| T04 | Clear every widget in the diagnostic derivative before adding explicit probe values | Supplied preselected answers and sample values are not treated as inspection evidence. Preserving approved constants requires explicit future mapping dispositions |
| T05 | Always watermark feasibility output; prohibit populating signature widgets | Probe output is never a completed inspection. Probe text is ASCII-only, single-line and bounds-checked; unsupported text fails explicitly |
| T06 | Use existing `pypdf` and ReportLab dependencies for vector inspection/rendering; Poppler for optional local preview images | No new runtime dependency or deployment change. Poppler is not assumed installed in the production image. MuPDF was used only as a second local verification engine, not imported by application code |
| T07 | Initial offline limits: 40 MiB source bytes, 50 source pages, 5,000 selected widget occurrences, parent depth 32 | Sufficient for supplied forms, with cyclic/malformed/encrypted/unsupported-geometry cases rejected. These limits are not a hostile-PDF sandbox; isolation/time/memory bounds must precede web intake |
| T08 | Keep generated inventories and proofs private and outside Git | New output directories use owner-only permissions; files use owner-only permissions where supported. Original/default values in inventory JSON are private data |

These technical decisions establish feasibility only. They do not approve any business mapping, constant, test result, signature, or production configuration.

## Business decisions pending before dependent publication

Owner for each item: application administrator/business owner. Status is **unresolved** unless a recorded approval later replaces it. Synthetic test values are not defaults or approvals.

| ID | Decision required | Affected fields | Framework handling until resolved |
| --- | --- | --- | --- |
| B01 | Exact stable checklist IDs and additional input definitions | Both forms, every destination | Build typed catalog; do not match questions by wording or order |
| B02 | Approved constant organization/contact information versus inspection-specific data | Organization, phone/email/address and monitoring fields | Clear supplied values in probes; future publication requires explicit dispositions |
| B03 | Panel/category applicability and required scope, including any no-panel Compliance case | Panel identifiers, models, quantities, accepted point results | No implicit first-panel selection, cross-panel aggregation, or empty-scope bypass |
| B04 | Date/time format, site timezone, and required precision; Compliance start versus completion date | Inspection/notification/restoration/certification dates and times | Existing date-only fields cannot supply real times; no midnight/export-time substitution |
| B05 | Required, optional, conditional, and allowed NA/blank policies | Result groups and conditionally applicable sections | Missing and NA remain distinct; negative outcomes are not converted into passes |
| B06 | Defect and work-order decisions required for negative outcomes | NFPA defects; Compliance remarks and section 15 | Capture explicit decisions in future Form Details; no fabricated acknowledgements |
| B07 | Supplemental-sheet declaration and responsibility for separate attachments | NFPA supplemental checkbox and sections 6.3–6.5 | Do not retain preset Yes; automatic attachment merging remains excluded |
| B08 | Leave signatures blank for later signing versus require an already signed form | Both inspector/owner signature locations | Never populate signatures in probes; signed-output requirements require separate supported scope |
| B09 | Approve proposed new filenames and panel disambiguation | Both new downloads | Current Initiating Devices filename remains unchanged |
| B10 | Explicit classifications/count definitions and manual measured values | Installed/tested-good counts, power readings, CCTV and related fields | Do not infer from point text, highlights, accepted times, or checklist completion flags |

Record each future resolution with date, administrator identity, rationale, integration/version, and affected target IDs. A business decision cannot retroactively rewrite original uploads, accepted data, audit decisions, or retained artifacts.
