# PDF Integration Part 1: Baseline and Feasibility

Date: October 28, 2026.
Baseline application commit: `d9323e7` (documentation changes only after application commit `1b968ce`).
Scope: first commit batch of the [implementation plan](PDF_EXPORT_INTEGRATIONS_IMPLEMENTATION_PLAN.md), P0–P1. No production deployment.

Follow-up: the [explicit P1 completion report](PDF_INTEGRATION_P1_REPORT.md) records enforced subprocess bounds, retained originals/lineage manifests, expanded geometry/mirroring tests, native-fill comparison and actual Firefox/Chromium PDF-viewer checks added after this initial prototype batch. Measurements and outstanding items below describe the initial run unless superseded by that report.

## Delivered

- Read-only occurrence inventory with stable IDs, page geometry, display rectangles, inherited field metadata, defaults, choices/export states, duplicate-name groups, and parser diagnostics.
- An offline, always-watermarked vector rendering proof that removes original widget annotations/values and fills explicit individual locations without field-name coupling. It creates a new document containing only selected page drawing content and probe overlays.
- A private command that produces inventory, summary, diagnostic PDF, and optional Poppler page previews. Existing output directories cannot be overwritten.
- Generated synthetic PDF fixtures for duplicate names, presets, checkbox/choice/signature fields, active actions, excluded pages, rotated/cropped geometry, malformed duplicate keys, encrypted files, and cyclic parent structures.
- A disposable SQLite fixture containing accepted and pending events, two panel categories, accepted/review points, legacy and typed checkbox decisions, a removed dropdown choice, inactive task, legacy drafts, deleted inspection, audit evidence, and a synthetic original upload. Repeated initialization and independent backup/restore preserve the logical database dump and upload bytes.
- [Decision register](PDF_INTEGRATION_DECISIONS.md), including unresolved business policies and the limits of the feasibility implementation.

There are no new HTTP endpoints, UI controls, database tables, schema changes, automatic defaults, AI calls, or enabled export integrations in this batch. Original PDFs and existing application modules are unchanged.

## Compatibility baseline and checks

Pre-change non-browser suite: **106 passed, 4 skipped**, in 50.37 seconds. Skips were the four explicitly opt-in browser checks; they were then run separately and all passed (typed checklist/admin choices, live synchronization, naming, and Points List review/table-save/clear-confirmation interaction).

One existing dependency warning is present: FastAPI/Starlette reports deprecation of its current `httpx` test-client integration. It did not fail the baseline. No unrelated dependency or application change was made to suppress it.

Post-change full suite with browser checks enabled: **132 passed, no skips**, in 140.64 seconds. The final focused feasibility/baseline run passed **23 tests**, including one additional indirect-annotation/appearance case added after full-suite collection. Compile and Git whitespace checks also passed. All four existing browser regressions ran successfully.

| Protected behavior | Existing evidence |
| --- | --- |
| Review status/description edits, save and explicit clear confirmation | `test_review_fixes.py`, including its actual browser test |
| Saved-data export gates, request forgery rejection, filename | `test_review_fixes.py`, `test_pdf_export.py` |
| Accepted event retention, pending evidence and provenance | `test_review_fixes.py`, `test_event_device_status.py` |
| Legacy/typed task answers, removed choices, audit history, ordering | `test_inspection_tasks.py`, `test_typed_checklist_browser.py` |
| Panel categories and administration permissions | `test_panel_types.py` |
| Highlights and cross-device refresh with private unsaved edits | `test_device_highlights.py`, `test_live_sync_browser.py` |
| Inspection naming, creation/deletion and retained audit data | `test_inspection_names.py`, `test_inspection_lifecycle.py`, `test_inspection_naming_browser.py` |
| Existing NFPA draft/template helper contracts | `test_pdf_export.py`, `test_pdf_templates.py`; no legacy PDF routes/helpers modified |

This is bounded regression evidence, not a claim that every legacy route or possible input has exhaustive coverage. Future phases must extend coverage where they touch those contracts.

## Private supplied-form proof

Both original hashes match specification §3. Occurrence inventory reproduces the expected counts:

| Result | NFPA pages 1–4 | Compliance page 1 |
| --- | --- | --- |
| Widget occurrences | 196 (40 / 65 / 49 / 42 by page) | 283 |
| Text / checkbox / choice / signature | 132 / 58 / 4 / 2 | 127 / 141 / 13 / 2 |
| Repeated qualified-name groups | 8 | 2 |
| Parser warning messages captured | 4 | 0 |
| Source bytes | 1,783,622 | 1,020,622 |
| Probe output pages | 4 | 1 |
| Probe output bytes, this run | 319,774 | 342,426 |
| Inventory duration, this run | 0.179 s | 0.109 s |
| Reinspection plus vector render duration, this run | 0.364 s | 0.191 s |
| Total including 96-DPI Poppler images, this run | 1.050 s | 0.549 s |

These timings are development-machine observations, not production guarantees. The command also reports process-lifetime peak RSS where the host supports it; it is not per-document allocated memory. Resource isolation before HTTP intake remains future work.

Private evidence directory for this run: `work/pdf-feasibility/20261028-170221/`. This path is ignored by Git. It contains original-value inventories and must remain private; do not attach or publish it as generic test data.

Fourteen distinct NFPA text-location probes and two distinct Compliance text-location probes distinguish repeated fields. All five selected pages were rasterized and visually inspected: printed labels, grid lines, and notices remain; original preset text/selections are cleared; probe markers appear at separate locations; all pages carry the diagnostic watermark. The unmodified original NFPA pagination still refers to eleven pages.

Independent verification uses Poppler and MuPDF rendering/text extraction. Both produce the expected page count and readable probe markers, with no form widgets or links in the derivative. Fractional page geometry may round to one extra edge pixel in one rasterizer; comparisons pad that edge with white. Mean absolute pixel differences were 4.317–9.216 on a 0–255 scale, recorded as informational metrics rather than a calibrated acceptance threshold because font rasterization differs. Visual inspection and text/structure/geometry checks establish this proof. This is an offline rendering/print-appearance check, not a completed browser PDF-viewer or physical-printer acceptance test.

## Running the tools and tests

Use Python 3.12+ with the repository's existing web/test extras. The implementation session used `/tmp/inspections-parser-venv/bin/python`; no system Python or production dependency was changed.

```bash
python -m pip install -e '.[web,test]'
python -m pytest -q tests/test_pdf_integration_inventory.py tests/test_pdf_integration_renderer.py tests/test_pdf_integration_probe.py tests/test_pdf_integration_baseline.py
python -m compileall -q src tests
```

Optional raster comparison requires local Poppler (`pdftoppm`) and Pillow. The PDF libraries already depend on Pillow through ReportLab. The raster test reports a skip if Poppler is unavailable; do not count that skip as rendering verification. MuPDF was a local independent verification tool, not a required application/test dependency.

The existing browser suite requires Playwright and its Chromium browser/system dependencies:

```bash
python -m pip install playwright
python -m playwright install chromium
INSPECTIONS_RUN_BROWSER_TESTS=1 python -m pytest -q -ra
```

Use the host's normal Playwright browser-dependency setup if Chromium cannot start. Existing CI currently runs the non-opt-in suite; browser verification must be requested explicitly.

Example private probe (use a new output directory for each run):

```bash
PYTHONPATH=src python -m alarm_inspection.integrations.pdf_probe \
  '/home/sbc-1/Downloads/0000-city, VA Fire Alarm Inspection 00-00-00.pdf' \
  --pages 1-4 --output-dir work/pdf-feasibility/nfpa-example --previews
```

Use `--pages 1` for Compliance. `--values-json` accepts a private JSON object mapping inspected target IDs to diagnostic strings or Boolean button marks. Signature population is rejected. Unsupported characters, tiny/overflowing text, unknown targets, and stale/tampered inventories fail explicitly. No values JSON is required for a cleared-background proof.

## Remaining boundaries

- Full business labeling, approval of every destination, answer-group semantics, approved constants, typed sources, panel applicability, and signature/attachment policies belong to P3–P8. Nothing in this proof approves them.
- The feasibility renderer clears original annotations; it does not preserve annotation-only artwork as an approved output style or detect arbitrary historical answers baked into page drawing content. It preserves the source page drawing content deliberately. Such content requires private visual verification/normalization before publication.
- Prototype text is single-line ASCII with a minimum diagnostic font size. Production fonts, wrapping/shrink policy, Unicode coverage, result-group validation, and target-specific style verification remain P7 work.
- No web intake is exposed. Upload validation, decompression/CPU/memory isolation, authorization, durable versioned storage, final artifact retention/recovery, and source snapshots remain later phases.
- Backup/restore rehearsal used disposable SQLite and synthetic upload bytes. PostgreSQL migration/recovery rehearsal and deployment-volume backup remain P2/P9/P10 gates.
- Browser PDF-viewer acceptance, physical printing where required, and production enablement remain release gates. Existing app browser regressions have been exercised separately.

Next implementation batch: P2, typed contracts, additive storage, private artifact lifecycle foundations, and a disabled-by-default feature switch. Preserve the original proof fixtures and baseline so each later batch can establish compatibility.
