# P2 — Contracts, Additive Persistence and Private Files

Date: October 28, 2026.
Scope: phase P2 of the [implementation plan](PDF_EXPORT_INTEGRATIONS_IMPLEMENTATION_PLAN.md). This is backend groundwork, with no new HTTP routes, UI actions, or production deployment.

## Delivered against the plan

| P2 task | Implementation and evidence |
| --- | --- |
| 1. Versioned contracts | `domain/pdf_integrations.py` defines strict version-one configuration/inventory, file references, allowlisted sources/transforms, conditional requirements, answer groups, manual inputs, normalized-target correspondence, verification/provenance, form answers, readiness blockers and artifact snapshots. Unknown fields/schema versions and executable transform kinds are rejected |
| 2. Additive records and integrity | Separate `PdfBase` metadata defines the five record families below plus a schema marker. New foreign keys, checks and indexes protect parent/state relationships; database triggers protect append-only and sealed records on both SQLite and PostgreSQL |
| 3. Idempotent seeding | Explicit initialization inserts only `nfpa72` and `compliance`, disabled and without an active version. It never creates checklist tasks, imports legacy drafts, publishes mappings, or changes inspection records |
| 4. Version/audit lifecycle | Draft writes use expected-revision SQL compare-and-set, retain prior draft payloads in audit, and invalidate stored verification. Template replacement requires a new version. Sealing requires matching retained test output, complete target dispositions/verification and explicit policies. Published payload/evidence is immutable, including through direct SQL. Activation selects a retained published version of the same integration; enablement has its own revision check |
| 5. Form decision history | Additional answers/overrides append rows with inspection/version/input/panel scope, full answer/override evidence, actor/time and input-definition hash. Zero, No, NA and cleared values stay distinct. Definition compatibility is explicit; no answer copying or source/checklist mutation happens automatically |
| 6. Artifact foundation | Pending/ready/failed records retain configuration version/hash, immutable snapshot/provenance, renderer identity, unique private key, download filename, output hash/size and author/time. Preview confirmation tokens are stored only as hashes and bind actor, snapshot, version and a 30-minute expiry. Final metadata requires a matching confirmed preview. No final rendering is implemented here |
| 7. Fail-closed feature switch | Default-disabled configuration controls optional initialization and all new repository operations. Per-integration enablement gates new inspection answers/previews. Disabled integrations retain history. Optional initialization failure disables only this feature; current app startup/health and old records remain available |
| 8. Private storage | New ID-derived template/artifact keys use the existing upload volume when wired into the future service. Atomic no-replacement file publication, owner-only files/directories, size/hash verification, and rejection of arbitrary paths/symlink parents are tested. Templates must exist with matching bytes before draft creation/update/sealing |
| 9. Migration/restart rehearsal | Tests populate legacy tables before enabling the feature, reopen stores repeatedly, and compare old rows unchanged. SQLite and PostgreSQL both retain legacy drafts, audit/checklist decisions, accepted/pending evidence, and new versions/artifacts across reinitialization. Forward/unknown schema versions fail closed without rewriting metadata |

## Boundaries and files

- `storage.py`: a small optional initialization hook after existing schema maintenance. Existing models/columns and legacy initialization rules are unchanged.
- `integrations/pdf_feature.py`: dependency-free feature switch and availability guard.
- `integrations/pdf_models.py`: separate ORM metadata for new records.
- `integrations/pdf_schema.py`: transactional schema initialization, version marker, seed identities and database guards.
- `integrations/pdf_repository.py`: internal transaction primitives, authorization/parent checks, revisions, retained decisions and artifact/confirmation lifecycle.
- `integrations/pdf_files.py`: private immutable blob storage. Its root is a trusted server setting; it must not come from an HTTP request. P4/P7 service wiring will use `api.common.UPLOAD_ROOT`.
- `.github/workflows/ci.yml`: adds a disposable PostgreSQL 16 test service and test-only URL so cross-database checks run in CI. It does not modify production Compose resources.

The existing PDF registry/draft routes, NFPA editable-draft helpers, Initiating Devices exports, checklist logic, review UI and event handling are unchanged. The unrelated working-tree change to package `SOURCES.txt` is outside this work.

## Schema and initialization policy

New table families:

| Table | Retention/integrity rule |
| --- | --- |
| `pdf_integrations` | Exactly the two supported keys; disabled by default; revisioned enablement/active-version reference |
| `pdf_integration_versions` | Draft revisions; published payload/evidence immutable; no version deletion |
| `inspection_form_decisions` | Append-only decisions referencing retained published definitions; no update/delete |
| `pdf_export_artifacts` | Pending can finalize once to ready/failed; snapshot/ownership/key/filename stays fixed; sealed artifacts cannot be updated/deleted |
| `pdf_integration_audit_entries` | Append-only edit/publication/activation/enablement/decision/artifact metadata |
| `pdf_integration_schema` | Singleton schema version marker, initially `1` |

Database schema version, JSON `schema_version`, and edit `revision` are separate concepts. Future schema changes require an explicit additive migration and supported marker update. Initialization will not guess how to adopt an unversioned partial schema or downgrade a future schema.

Initialization is transactional and serialized with a SQLite write lock / PostgreSQL advisory transaction lock. SQLite foreign-key enforcement is enabled only on an opted-in engine; existing legacy tables gain no new constraints. New decision/artifact foreign keys reference existing inspections/panels, whose current deletion is soft. Actor IDs deliberately have no user foreign key, preserving the existing physical user-deletion behavior while retaining audit identity strings.

New tables are excluded from legacy `Base.metadata`. With the switch absent/false, startup imports no PDF model/contract dependency and creates no PDF tables. If tables already exist, disabling leaves their data and private files intact. An unsupported schema or optional initialization error leaves `session.info['pdf_integrations_available']` false and emits a fixed message without exception text or connection secrets.

## Feature switch

```text
INSPECTIONS_PDF_INTEGRATIONS_ENABLED
```

Only `1` or `true` (case/outer-space insensitive) enables optional initialization. Missing/unrecognized/false values leave the feature disabled. It is independent of `NFPA_TEMPLATE_PATH` and all legacy PDF settings. New operations require both the switch and a successfully initialized session factory. Enabling after a disabled startup requires reinitialization/restart; changing the environment cannot silently adopt missing tables.

No environment file was edited. P2 tests explicitly opt in against disposable stores. Production enablement remains P9/P10 work after semantic services, mappings and UI are ready. Published/active technical records in synthetic tests do not enable a production form.

## File and transaction semantics

Trusted key formats:

```text
_pdf_integrations/{nfpa72|compliance}/{version-uuid}/original.pdf
_pdf_integrations/{nfpa72|compliance}/{version-uuid}/normalized.pdf
{inspection-id}/form_exports/{artifact-uuid}/document.pdf
```

Writes use a same-directory private temporary file, flush/fsync, and a hard link that fails if the destination exists. Temporary write files are removed; retained originals/artifacts have no automatic deletion method. Reads verify both size and SHA-256. Default blob size limit is 64 MiB; PDF intake's lower resource/content limits still belong to the intake service.

The filesystem and database are not one atomic transaction. Rehearsal demonstrates: commit a pending record, retain bytes, simulate rollback during finalization, observe the artifact remains unavailable, then verify and finalize the same bytes successfully. Pending/failed records never qualify for a download. P7 will supply orchestration, idempotent request handling and reconciliation; P2 supplies the durable states and integrity checks.

Existing artifacts remain readable after later panel soft-deletion while new confirmation fails for the deleted scope. Deleted inspections continue to follow current access restrictions. A disabled individual integration blocks new previews/answers while retaining its artifact history. No inspection answer, accepted mapping or legacy draft is changed by preview/confirmation metadata.

## Validation

Focused P2 suite: **47 passed** with both SQLite and PostgreSQL cases enabled. Coverage includes:

- Strict schema/version/source/transform validation and typed value preservation.
- Verification timestamp JSON round trips, override reasons and input semantics.
- Immutable private files, size/hash checks, traversal and symlink rejection.
- Fresh/populated stores, idempotent initialization, retained old rows and file bytes.
- Same-session and two-session stale edits; database-level immutability and foreign keys.
- Retained audit/decision identity after deleting a user.
- Preview actor/token/context checks, immutable snapshots and failed/pending reads.
- Per-integration and global disablement; template integrity before persistence.
- Recoverable transaction failure, published metadata retention after reopening, and unknown-schema isolation.
- Default-disabled startup without model imports; optional initialization failure without exposing exception contents or blocking legacy health.

Local engines: SQLite **3.45.1**, PostgreSQL **16.15**; Python 3.12, SQLAlchemy 2.1.6 and Pydantic 2.14.1. PostgreSQL ran as a disposable user-owned cluster with a private local socket and no TCP listener. No existing server/application/database was used.

To run cross-database checks, provide `INSPECTIONS_PDF_TEST_POSTGRES_URL` for a disposable PostgreSQL database where the test role may create/drop uniquely named test schemas. Tests isolate and remove those schemas, not the database's other schemas. Without this variable, PostgreSQL cases explicitly skip; skips do not satisfy this phase's verification gate. CI supplies its own disposable service.

Full verification with `INSPECTIONS_RUN_BROWSER_TESTS=1`, the integration switch enabled and the disposable PostgreSQL URL configured: **197 passed, no skips**, in 157.82 seconds. This includes the four existing browser regressions and all cross-database cases. Compilation, Git whitespace checks and documentation-reference checks passed. The pre-existing FastAPI/Starlette test-client deprecation warning remains. The updated GitHub CI job has not been claimed as remotely executed.

## Remaining phase boundaries

P2's `seal_version` is an internal storage operation with structural/retention evidence, not the complete P4 publication service. P3 must resolve authoritative saved data, conditional applicability, source compatibility, answer groups/counts and readiness; P4 must validate actual PDFs and enforce all semantic/test/publication gates before exposing publication. P6/P7 must recompute current snapshots and authorization at confirmation, render verified final PDFs and orchestrate retained downloads. No UI or HTTP caller can invoke P2 primitives today.

Operating-system resource/filesystem/network isolation for untrusted PDF intake remains a separate requirement. Private file path checks assume a trusted service-owned root; they are not a general filesystem sandbox against a hostile local administrator. Physical-print and full business-form acceptance remain release gates. No AI dependency, deployment secret, customer upload or generated PDF is committed.
