# Application Architecture

## Completed-form exports and supplied-form setup (P7–P8)

`integrations/pdf_exports.py` captures scope/configuration/saved facts in one database-enforced snapshot and binds previews, requester, renderer and file hash to explicit final confirmation. Deterministic request IDs enforce idempotency using existing artifact primary keys. Pending records commit before bounded rendering/private publication; sealing/recovery is separate. Public provenance redacts private paths. `pdf_renderer.py` builds fresh selected-page trees with validated overlays and output structural checks; previews are visibly marked. `pdf_setup.py` generates/provisions only unpublished candidates, with adjustable defaults and no automatic business approval. See the [operating guide](PDF_INTEGRATIONS_OPERATIONS.md) and [P7](PDF_INTEGRATION_P7_REPORT.md)/[P8](PDF_INTEGRATION_P8_REPORT.md) reports.

## PDF administration and technician details (P4–P6)

`api/routers/admin_integrations.py` and `integrations/pdf_service.py` add an admin-only, revisioned template/draft/test/publication lifecycle. Resource-limited `pdf_admin_worker.py` performs intake, sanitized raster previews and watermarked diagnostic rendering. Published configuration and exact-hash verification remain immutable. `api/integrations.js` is the independently packaged mapping workspace and technician UI.

`api/routers/inspection_form_integrations.py` and `integrations/pdf_details.py` expose saved additional inputs, explicit scope and readiness. Scope decisions use the existing append-only PDF integration audit table; input answers use `inspection_form_decisions`. Writes serialize per inspection (SQLite immediate transaction / PostgreSQL row locks), compare saved fingerprints and never modify existing inspection/checklist/point/event records. Polling preserves private local edits, reports conflicts and archives local answers when definitions change. Feature failures stay inside the new UI section. P7 adds the preview/confirmation/download lifecycle described above; production candidates remain disabled pending administrator setup. See [P4](PDF_INTEGRATION_P4_REPORT.md), [P5](PDF_INTEGRATION_P5_REPORT.md), and [P6](PDF_INTEGRATION_P6_REPORT.md) reports.

## Saved PDF sources and readiness (P3)

`integrations/pdf_sources.py` opens independent, database-enforced read transactions and resolves only saved, authorized configuration/inspection/decision data. `domain/pdf_mapping.py` evaluates typed transforms, conditions, group states and layout bounds; `domain/pdf_readiness.py` compiles blockers/target plans and stable snapshot fingerprints. Administrative draft catalogs are diagnostic and cannot approve exports. P3 introduced no router; P4–P6 registration is described above. See [P3 authority and compatibility boundaries](PDF_INTEGRATION_P3_REPORT.md).

## Optional PDF integration backend (P2)

Strict version-one contracts live in `domain/pdf_integrations.py`. Separate models, transactional schema initialization, revisioned/append-only repository primitives and private blob storage live in `integrations/pdf_models.py`, `pdf_schema.py`, `pdf_repository.py` and `pdf_files.py`. `pdf_feature.py` provides a dependency-free, disabled-by-default switch. `storage.open_store()` lazily initializes this separate metadata only when opted in; optional failures leave legacy workflows available. P2 introduced no router or frontend asset; P4–P6 registration is described above. See [P2 report](PDF_INTEGRATION_P2_REPORT.md).

## PDF integration feasibility tools (October 28, 2026)

`integrations/pdf_inventory.py` inspects private PDF widget occurrences and geometry; `integrations/pdf_renderer.py` creates watermarked vector probe documents; `integrations/pdf_probe.py` is their private offline command. The original CLI remains separate; P4 also uses the inventory and diagnostic renderer through a bounded worker. Existing PDF drafts/exports stay independent. Original uploads and private proof artifacts remain outside Git. See [part 1 report](PDF_INTEGRATION_PART1_REPORT.md) for scope, tooling, and remaining production gates.

The P1 follow-up routes the CLI through `pdf_probe_limits.py` and `pdf_probe_worker.py`: a fresh Linux process enforces resource limits, stages private results and publishes only a completed proof with retained original/hash/correspondence manifest. This is not an HTTP endpoint or a filesystem/network sandbox. See [P1 report](PDF_INTEGRATION_P1_REPORT.md).

## Recommended shape

Use a small web application with a browser interface, an API, a background processing worker, relational storage, and object storage for source and generated files.

Suggested first-release stack:

- Frontend: React with TypeScript.
- API: Python FastAPI.
- Processing: Python package shared by the API and worker.
- Background jobs: Redis-backed worker, such as RQ or Celery.
- Database: PostgreSQL.
- File storage: S3-compatible object storage, preferably a private DigitalOcean Space.
- Deployment: Docker Compose or separate containers on DigitalOcean, behind the existing server's reverse proxy.

The exact framework may change, but the boundaries must remain.

## Logical components

```text
Browser
  -> Web UI
  -> API
       -> Inspection service
       -> File intake service
       -> Deterministic processing engine
       -> Review and export service
       -> PostgreSQL
       -> Private object storage
       -> Background worker
```

## Processing pipeline

1. Store the original file unchanged.
2. Identify file type and extract a source table.
3. Normalize headers, rows, whitespace, and dates.
4. Run deterministic validation and transformation rules.
5. Produce normalized Points and Events datasets.
6. Join Events to Initiating Devices by normalized point address.
7. Create accepted records and exception records.
8. Require review of exceptions before export.
9. Generate the final report from a versioned template.

## Domain model

- Inspection
- PointList
- EventHistoryUpload
- PointRecord
- EventRecord
- InitiatingDevice
- MappingResult
- ProcessingRun
- Exception
- Export
- RuleSetVersion

Use stable internal IDs. Treat point address as a normalized business key, not as the database primary key. Each inspection owns many PointLists and EventHistoryUploads. PointLists are immutable after acceptance. MappingResults are durable and retain the evidence upload and timestamp that produced each accepted mapping.

## Security

- Keep uploaded files private.
- Use per-user authentication before production use.
- Validate file size, extension, MIME type, and content.
- Do not execute uploaded macros.
- Store secrets only in deployment secret storage.
- Never commit API keys, DigitalOcean tokens, database passwords, or `.env` files.
- Log metadata and processing decisions, not sensitive file contents.

## Shared browser state

Authenticated, visible browsers poll the existing authorized read endpoints every three seconds. Pending Event History matches are stored as shared evidence and synchronize alongside cell warning colors; explicit Accept Results is still required to create accepted mappings. The database remains the shared source of truth across API processes; no in-memory event hub or extra infrastructure is required. Hidden tabs catch up on visibility change, and timeouts or disconnections retry on the next interval. The user bar reports connection status.

Refreshes update the current inspection, checklist, points and highlights, panel types, active administration tab, and open PDF draft. Store Data saves send only fields changed locally. Untouched table/PDF fields can receive remote values while local edits remain private until saved. Refreshes discard responses when the user navigates, edits, or saves during a request. Deletion on another device closes the deleted inspection. Simultaneous edits to the same field retain the existing last-save behavior; this is synchronization, not document locking or conflict resolution.

### Simplified PDF integration setup (October 29)

The normal mapper reads `/api/admin/integrations/sources` without a sample inspection. Only Store Data and active Check List definitions are listed. `pdf_simple.py` validates the typed mapping save against the opened configuration/integration revisions and source catalog hash, creates a new version, renders bounded watermarked complete-form proofs without a write lock, then atomically publishes/enables it with retained `SimpleVerificationEvidence`. Old versions are preserved. Originals and `mapping-test.pdf` proofs remain private, immutable and hash verified; no inspection FK or customer answers are needed to configure a form.

`mapping_mode=store_checklist` restricts all source references (including transform/condition references) to inspection/checklist. Snapshot capture skips panels, points, events and manual Form Details. Checklist schema fingerprints detect incompatible definition changes. Per-field defaults apply only to missing compatible data; result marks use an explicit Yes/No/NA predicate. Legacy advanced contracts retain their earlier policies. Frozen previews/finals, authorization, retained history and existing Initiating Devices rules are unchanged. JSON and advanced version tools are in Debug mode.
