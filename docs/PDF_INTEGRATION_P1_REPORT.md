# P1 — PDF Inventory and Rendering Feasibility

Date: October 28, 2026.
Scope: phase P1 of the [implementation plan](PDF_EXPORT_INTEGRATIONS_IMPLEMENTATION_PLAN.md), extending the initial [baseline/prototype batch](PDF_INTEGRATION_PART1_REPORT.md).

## Outcome

The initial batch provided working inventory and rendering prototypes. This follow-up closes the explicit P1 gaps: enforced execution bounds, retained original-to-derivative correspondence, native-fill comparison, intentional-mirroring and full-rotation tests, and actual browser PDF-viewer checks. Production mappings, admin/technician UI, database changes, final exports, and deployment remain later phases.

## P1 task evidence

| Task | Result |
| --- | --- |
| 1. Verify and preserve originals | Both supplied fingerprints match specification §3. The bounded command accepts `--expected-sha256`, rejects replacements, and retains exact source bytes as private `original.pdf` alongside its derivative |
| 2. Enumerate occurrences and inherited metadata | Existing inventory captures qualified identity, widget/page location, flags, values/defaults, choices/states, geometry and diagnostics. Parent inheritance, indirect annotation arrays/appearances and cyclic structures have synthetic coverage |
| 3. Reconcile coverage | NFPA: 196 widgets, page counts 40/65/49/42, 184 distinct qualified paths, 8 repeated-name groups. Compliance: 283 widgets, 281 distinct paths, 2 repeated-name groups. These paths/groups are not automatically approved business questions or result groups. NFPA pages 5–11 are excluded |
| 4. Stable IDs | Repeated extraction produces identical IDs; changing the source invalidates them; selecting different retained pages does not renumber occurrence IDs |
| 5. Isolation and mirroring | Distinct supplied-form markers occupy 14 NFPA and 2 Compliance repeated text locations. A separate synthetic test explicitly mirrors two occurrences, then changes only one without affecting the other |
| 6. Native and overlay prototypes | Native name-based filling updated all 3 selected NFPA occurrences and both selected Compliance occurrences with one value. It cannot independently map those locations. The fresh-document vector overlay retains exact-location independence, clears annotation presets and omits original form/action trees |
| 7. Derivative lineage | `manifest.json` records source/output hashes and a source-target-to-output-page/rectangle correspondence for every selected widget. The original and derivative remain separate private files; the source is never rewritten |
| 8. Preview coordinates/toolchain | Raster tests compare actual changed pixels with inventory display rectangles for cropped pages at 0°, 90°, 180°, and 270°. Fractional invalid rotations are rejected rather than truncated. Poppler at 96 DPI is the chosen workspace-preview strategy |
| 9. Bounds and measurements | The CLI now uses a fresh Linux worker with enforced address-space, CPU, file-size and wall-time limits; timeout/failure kills the process group. Tests exercise these limits and descendant termination. Only a successful staged result is published |

No automatic result grouping, classification, or business mapping is inferred from widget names. Those remain explicit configuration work.

## Execution boundary

The CLI invokes `pdf_probe_limits.run_bounded_probe`; its internal worker applies limits before loading PDF libraries or source content. It stages results privately and links completed files into a new owner-only output directory without overwriting existing files. The report is published last. Failed jobs do not publish an output directory or modify their input.

Default bounds:

| Resource | Bound |
| --- | --- |
| Source | 40 MiB; at most 50 source pages |
| Selected widget occurrences | 5,000; parent hierarchy at most 32 nodes |
| Worker wall time | 30 seconds, covering parsing, rendering and optional previews |
| CPU | 20 seconds soft / 21 seconds hard per process |
| Virtual address space | 512 MiB per process, inherited by the rasterizer |
| Individual file | 64 MiB |
| Published output set | At most 128 MiB, checked before publication; includes retained original |
| Preview images | At most 40 million pixels across selected pages at 96 DPI |
| Private values/request JSON | At most 2 MiB |

The wall-time guard kills the worker and descendants. Address-space/CPU limits apply per process, not as an aggregate container budget. The output-set check is a publication limit, not a live filesystem quota; temporary disk use remains bounded by page/file/process limits. A filesystem/network sandbox and production job-level quotas remain required before accepting untrusted uploads through HTTP. No such endpoint exists in P1.

The bounded command explicitly requires Linux; it refuses to claim equivalent resource enforcement on unsupported platforms. Direct inspection/rendering helpers remain portable for trusted local tests, but do not enforce the subprocess boundary themselves.

## Supplied-form measurements

These are local diagnostic measurements, not production performance commitments:

| Measurement | NFPA 1–4 | Compliance 1 |
| --- | --- | --- |
| Source bytes | 1,783,622 | 1,020,622 |
| Derivative bytes | 319,774 | 342,426 |
| Inventory | 0.230 s | 0.251 s |
| Reinspection + vector rendering | 0.374 s | 0.279 s |
| Worker total including preview images | 1.111 s | 0.804 s |
| Worker process peak RSS | 46,194,688 bytes | 45,617,152 bytes |

Process peak RSS measures the Python worker's lifetime, not summed rasterizer memory. Both jobs passed the default resource limits. Their derivative hashes match the previous diagnostic outputs, confirming the new boundary/manifest did not change the page drawing results.

## Viewer and print-appearance verification

Opened each exact diagnostic derivative in both **Firefox PDF.js** and **Chromium PDFium**, navigated all four NFPA pages and the single Compliance page, checked viewer-reported counts, and captured ten private browser screenshots. Visually reviewed page content, separate probe markers, cleared result selections, printed grids/labels/notices, and the diagnostic designation. No original embedded PDF JavaScript or form regeneration is needed for visible results.

The prior Poppler/MuPDF raster and structural checks remain supporting evidence. Physical printer testing and business acceptance of completed, populated forms remain P9 gates; P1 does not approve any inspection result or signature.

Private evidence: `work/pdf-feasibility/p1-completion/`, ignored by Git. Each form directory holds original bytes, inventory, manifest, derivative, raster previews, resource report and viewer screenshots. Top-level `native-comparison.json` and `browser-viewers.json` record the comparison result and screenshot/document hashes. Do not commit or publish these source-derived files.

## Toolchain decision

- Python runtime inspection/vector drawing continues to use existing `pypdf` and ReportLab web extras. No new Python production dependency is introduced.
- Poppler `pdftoppm` supplies mapping-workspace previews. Add the operating-system package `poppler-utils` to the inspection image when server preview functionality is introduced in P5; verify its packaging in P9. The current production image is unchanged by P1.
- Firefox/Chromium Playwright browser binaries and MuPDF are local verification tools. They are not application services or runtime dependencies.
- Every probe remains visibly watermarked and signature population is rejected. Prototype text remains single-line ASCII; production typography and result-group semantics remain P7/P8 work.

Example bounded command (choose an unused output directory):

```bash
PYTHONPATH=src python -m alarm_inspection.integrations.pdf_probe \
  '/home/sbc-1/Downloads/0000-city, VA Fire Alarm Inspection 00-00-00.pdf' \
  --pages 1-4 --expected-sha256 b956b9c0ae6864970eb2f582a12a9e59d81162e1843f3b8e54f536a08d43aa71 \
  --output-dir work/pdf-feasibility/nfpa-bounded-example --previews
```

## Validation and next phase

Focused phase tests: **40 passed**, including real raster-coordinate comparisons and CPU/memory/file/wall-limit enforcement. Full suite with `INSPECTIONS_RUN_BROWSER_TESTS=1`: **150 passed, no skips**, in 140.80 seconds. All four existing browser regressions passed. The existing FastAPI/Starlette test-client dependency deprecation warning remains unchanged. Compilation and Git whitespace checks passed.

P1 changes only the isolated development tools, tests and documentation. Existing application routers, UI, storage initialization, database records, drafts and exports are unchanged. No deployment occurred. Proceed next to P2's typed contracts, additive records and disabled feature switch, retaining the unresolved business decisions in the [decision register](PDF_INTEGRATION_DECISIONS.md).
