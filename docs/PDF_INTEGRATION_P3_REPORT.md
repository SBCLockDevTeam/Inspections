# P3 — Saved Sources, Mapping Rules and Readiness

Date: October 28, 2026.
Scope: P3 of the [implementation plan](PDF_EXPORT_INTEGRATIONS_IMPLEMENTATION_PLAN.md). This phase adds internal read-only services and pure rules; it registers no HTTP routes or frontend controls and performs no deployment.

## Delivered against the plan

| P3 task | Implementation/evidence |
| --- | --- |
| 1. Typed saved-source catalog | Authorized catalogs identify inspection metadata, stable checklist IDs, selected panel evidence and versioned manual input IDs. Labels/options/units are display metadata. Approved constants come only from saved configuration. Unsupported counts are explicitly unavailable, not inferred |
| 2. Current compatible decisions | Latest checklist decisions use the existing legacy checkbox interpretation. Inactive/missing tasks, input-type changes, removed choices and incompatible manual definitions require review. Cleared/latest answers never fall back to an earlier value |
| 3. Typed values | Zero, False, No, NA, blank and missing remain distinct. Manual values retain P2 numeric/unit/bounds/date/offset validation. Date-only inspection fields cannot produce times or timezone conversions |
| 4. Declarative transforms/groups | Explicit date/time formats, known timezone conversion, numeric precision, concatenation and typed JSON lookup keys. Groups bind every member to the same reviewed source/transform and clear nonselected buttons. Unsupported NA or invalid PDF on/off states block rather than guess |
| 5. Conditional requiredness | Required manual inputs, targets and groups evaluate saved conditions. Numeric zero is answered and Boolean false is not numeric zero. Missing condition inputs are not guessed. Conditional remarks/work-order inputs can be required after No/failed answers without converting those answers into passes |
| 6. Explicit counts | The pure counter accepts only distinct approved classifications and explicit approved results; accepted timestamps do not confer a passing result. The current database has no such complete classified/result dataset, so actual count-source resolution blocks and recommends a typed numeric manual input |
| 7. Explicit scope | Panel mode requires one compatible owned active panel. Inspection mode requires every configured-category panel. Duplicate/foreign/deleted/omitted IDs and empty required scopes block. No-panel mode needs its reviewed reason and cannot acquire panel dependencies or accept an injected scope |
| 8. Authoritative completion | Selected-panel Review rows, missing results/locations/descriptions, bad/duplicate addresses and duplicate accepted mappings block. The current `validate_export_rows` rules are reused without changing the existing endpoint. Pending event evidence never substitutes for accepted times |
| 9. Structured blockers | Issues identify code, source, target, section and navigation destination. Ready data produces a typed target plan; a blocked result cannot be converted into an artifact context |
| 10. Consistent fingerprints | A fresh database-enforced read transaction captures configuration, scope, relevant definitions/decisions, inspection metadata, panel/point/evidence state and provenance. Fingerprints exclude read time, include rule version, and change on relevant saved changes. Unrelated unmapped task edits do not invalidate export snapshots |

## Code boundaries

- `domain/pdf_mapping.py`: typed source/target values, condition evaluation, allowlisted transforms, scalar/button/group compatibility, bounds/glyph checks, and explicit approved-dataset counting. No database or file writes.
- `domain/pdf_readiness.py`: saved snapshot/result types, requiredness, signatures/supplemental decisions, complete target dispositions, group planning and deterministic blocker collection.
- `integrations/pdf_sources.py`: authorized, independent read transactions; saved-data capture; catalogs; manual compatibility/override checking; selected-panel completion facts; readiness entry point.
- `domain/pdf_integrations.py`: additive JSON contract fields for concatenation sources, missing-value/font policies, supplemental declaration identity and override source identity.
- `integrations/pdf_repository.py`: integrity checking hashes persisted canonical JSON rather than an expanded model with newer defaults. No published payload is rewritten.

Existing application routers, UI, parsers, legacy PDF drafts/exports and database tables/columns are unchanged. The feature remains disabled by default. No accepted point/event/checklist/manual decision is changed by these readers.

## Read-only service entry points

```python
capture_snapshot(store, inspection_id, integration_key, actor_id=..., panel_ids=[...])
assess_readiness(store, inspection_id, integration_key, actor_id=..., panel_ids=[...])
source_catalog(store, inspection_id, integration_key, actor_id=..., panel_ids=[...])
configuration_source_catalog(store, inspection_id, saved_version_id, actor_id=..., panel_ids=[...])
```

Normal readiness always reads the enabled, active published configuration and saved answers from the server. It accepts no submitted rows, timestamps, answer values or configuration payload. Authorization follows the current application's active-user/shared-inspection access model and rejects deleted inspections.

The configuration catalog additionally requires an administrator and a saved version ID. It works before the first version is published, avoiding a configuration bootstrap deadlock. Its snapshot is always marked diagnostic/unconfigured and cannot approve an inspection export. P4 can use it for mapping setup; it is not a route today.

Catalogs contain private values and must remain behind authorization. `catalog_fingerprint` covers all picker metadata/panel choices; `source_fingerprint` covers the relevant export dependencies. Display labels never identify a source. Legacy PDF draft fields are not silently adopted as approved inspection answers.

## Snapshot consistency and provenance

PostgreSQL uses `REPEATABLE READ` and `SET TRANSACTION READ ONLY`. SQLite uses an explicit read transaction and `PRAGMA query_only`; the setting is restored before the pooled connection is returned. Tests attempt real writes, verify rejection and then verify that normal writes work again. Concurrent-commit tests use PostgreSQL and a disposable SQLite WAL database to prove subsequent reads stay on the initial snapshot.

Readers open independent connections and never flush another session's pending edits. Shared/in-memory `StaticPool`/`SingletonThreadPool` engines are explicitly rejected before checkout so the reader cannot roll back a caller's shared connection. The application uses file-backed SQLite locally and PostgreSQL in production.

The fingerprint includes the ruleset identifier `pdf-p3-1`, immutable stored configuration hash, effective configuration, explicit scope, saved inspection facts, selected panel evidence and relevant source fingerprints. Record decision times/IDs remain provenance; current read time is absent. Pending evidence is retained as evidence state, but is never treated as an accepted result. Provenance records retain the actual stored mapping/decision IDs and filenames; missing per-upload foreign keys are not invented.

Manual decisions can be reused across retained versions only when the exact input-definition hash is compatible. An incompatible latest decision is shown for review, never replaced by an older compatible answer. Overrides name their actual source and its fingerprint/original value. Changed, cyclic/excessive or identity-less legacy override dependencies require review; source rows and override history are retained.

## Contract compatibility and layout policy

Optional version-one fields add:

- `Transform.sources` for explicit multi-source concatenation.
- `TargetMapping.missing`, `font_size` and `minimum_font_size`.
- `IntegrationConfig.supplemental_source`.
- `FormAnswer.overridden_source`.

Older published JSON remains intact and its stored hash is checked against that persisted JSON. New optional defaults are not written back or used to invalidate its historical integrity hash. Effective rendering configuration is separately included in the new snapshot fingerprint. Cross-database tests load a pre-extension published payload and verify its bytes/hash remain unchanged.

Default missing-value policy is `block`. An optional blank policy needs an explicit reason and cannot hide a changed/incompatible source or a required answer. Signature destinations remain blank only under an explicit later-signing policy; already-signed output remains unsupported and blocked. NFPA supplemental declarations require a named saved Yes/No source rather than the PDF's preset selection.

Numeric formatting preserves the saved precision when no precision is declared. Explicit decimal rounding uses deterministic half-up behavior. Lookups use canonical JSON keys to distinguish numbers, strings and booleans, for example:

```json
{"kind":"lookup","lookup":{"\"Yes\"":true,"\"No\"":false}}
```

The initial layout contract measures Helvetica/ASCII, explicit font sizes and normalized target rectangles where configured. Block/wrap/shrink policies preserve the original text and never truncate; shrinking respects the declared minimum. Unrepresentable characters require an approved font instead of replacement glyphs. P7 must implement exactly this target plan or extend the verified font/layout contract before producing finals; P3 does not call the legacy filler or prototype renderer.

## Validation

New tests cover pure transforms/requiredness/groups/layout and the saved-source service on SQLite/PostgreSQL: legacy unchecked/No answers, removed choices, source-definition changes, numeric zero and clearing, scope/Review/pending/accepted/duplicate cases, conditional remarks, stale overrides, read-only enforcement, concurrent snapshots, admin draft catalogs, request-value rejection and older published hashes.

Added **45 P3 tests**. Final full-tree verification with browser checks, PostgreSQL and the integration switch enabled: **242 passed, no skips**, in 143.84 seconds. This includes the four existing browser regressions, P2 compatibility checks and all new cross-database cases. Compilation, Git whitespace and documentation-reference checks passed.

All tests use synthetic data and disposable schemas. No customer PDF/upload, private source extract, token or generated report is added to Git. The pre-existing FastAPI/Starlette test-client dependency warning is unrelated to P3.

## Remaining phase boundaries

P4 still supplies the administration APIs and complete publication/test-evidence service; P5/P6 supply mapping and data-entry UI; P7 supplies final rendering, current-snapshot revalidation/confirmation and retained downloads. P3's fingerprint is a change detector, not permission to trust a client-submitted snapshot. Final services must recapture authoritative saved data before confirmation.

Automatic physical-device counts remain unavailable until an explicit approved classification/result dataset is defined; numeric Form Details are the supported alternative. Unicode fonts and actual final-layout/viewer/print acceptance remain renderer/release gates. Original NFPA pages 5–11 and automatic attachment merging remain outside this release. No AI key or API is required.
