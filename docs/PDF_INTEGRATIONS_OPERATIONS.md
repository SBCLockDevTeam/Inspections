# PDF integrations operating guide

## Current rollout scope

The user will establish production defaults later. Both supplied forms are installed as **unpublished, disabled drafts**. Technical preparation/testing is not business approval. Do not enable completed-form exports until the administrator establishes policies, reviews every included location, tests, verifies and publishes the version. Existing inspection entry, Points List/event review, legacy PDF drafts and Initiating Devices exports remain independent.

## Configure and approve

1. Open Administration → Integrations. Select the NFPA 72 or Compliance draft and open its workspace. Original fingerprints and included pages are immutable; NFPA uses pages 1–4, Compliance uses page 1. Uploading another source requires a new version/inventory.
2. Select a saved sample inspection, enter explicit sample panel IDs when needed, and load the typed source catalog. Map stable task IDs, not similar descriptions. Source gaps use typed Form Details inputs; changing their meaning or type requires reviewing older answers.
3. Review **every** exact page/occurrence/rectangle. Search/select works in both directions; zoom and metadata distinguish repeated names. In particular, store and representative addresses and the duplicate relay quantity destinations have independent meanings. Review custom rows, control references, default/preset values and signatures too.
4. Establish applicability/categories, optional/default IANA timezone and company/contact constants. A per-field timezone overrides the integration timezone. Date-only data never acquires an invented time; datetime values require actual recorded offsets. Shared constants are mapping decisions with an explicit invariant reason, never test outcomes, notification times or signatures. Editable PDF combo fields allow reviewed custom text; closed choices require their declared options.
5. Review manual input types, numeric bounds/units, requiredness and conditional No/NA rules. Candidates are conservative placeholders, not approved policies. Installed/tested-good quantities remain independent; neither timestamps nor device descriptions establish counts or passing results. Single NA markers use explicit empty group choices to clear marks. If NA is unsupported, configure a reviewed policy or let it block.
6. Choose the signing policy. The supported initial workflow leaves designated signatures blank for later signing. Already-signed requirements block until a separate signing workflow exists. NFPA requires an explicit saved Yes/No supplemental-sheet declaration; separate reports are not automatically merged.
7. Approve download naming by selecting `completion_date_panel_id`. It uses saved completion dates, the specified Fire Alarm/Compliance titles and a panel-ID suffix for single-panel outputs. Existing Initiating Devices filenames do not change.
8. Save using the expected revision. A conflict retains local work; download the local configuration or explicitly reload to compare. Published versions require a copied draft for edits. Never silently replace accepted mappings or verification.
9. Run mapping tests. Review the retained, watermarked complete-form vectors and every included page. All declared choices are covered in compact vectors; tests are not completed inspections. Inspect long values, zero, No, NA, quantities, comments, dates/times, independent visual/functional states and negative-outcome explanations. Overflow/unsupported glyphs block, never truncate.
10. Verify each target against the current exact-hash test, enter a change summary and explicitly publish. Publication activates the version reference; enablement is a separate explicit action. Re-testing/mapping changes reset verification. Prior published versions remain available for explicit activation.

Presets are not inspection evidence. Some original Compliance fields are dense and use small text; adjust font/overflow settings and verify readability. A larger normalized derivative requires separately verified renderer support and cannot be silently substituted. Physical-printer approval and finalized business mappings remain user-owned release gates.

## Technician export

Save Store Data, checklist, points/events and Form Details. Explicitly save panel scope when configured. Readiness links identify missing/incompatible answers, stale overrides and unresolved mappings. No pending event is accepted merely by opening a preview.

Choose Export NFPA 72 or Export Compliance Form. Review every page of the marked draft, the version/scope and deliberate blank/signature disclosure; then confirm. The server rechecks authorization, published/enabled state, saved data, scope and preview hash. Changes require a new preview. Changes after the accepted snapshot cannot rewrite that artifact. Network retries of the same confirmation reuse the same record; an intentional later export creates a separate artifact. History includes ready/failed/pending records and safe provenance links.

Historical ready downloads verify file hashes and remain authorized even after an integration is disabled. Deleted/inaccessible inspections cannot download. Never edit retained final bytes or database snapshots to correct a report; correct saved data and create a new export.

## Recovery and maintenance

A pending record is not downloadable. After the two-minute processing lease, the requester or administrator may recover a pending final from history. Recovery regenerates the frozen plan with the recorded renderer, checks any existing bytes and seals the same record. A database failure after a file write is recoverable; filesystem publication and database commit are deliberately separate. Unknown renderer versions need the matching application image/operator review. Failed records remain failed; create a fresh reviewed preview/request after resolving the cause.

The admin-only POST `/api/admin/integrations/maintenance/expired-previews` removes at most 100 ready preview files more than a day beyond their 30-minute expiry and records cleanup. It never removes originals, final files, accepted decisions or audit records. Do not manually delete pending final bytes: they may be awaiting reconciliation. Bound resource use with the existing Linux worker (30 seconds wall, 20 seconds CPU, 512 MiB address space, 64 MiB output); diagnose a failed test rather than raising limits blindly.

## Isolated deployment and backup

Only use `/opt/inspections`, Compose project `inspections`, and port 18080 on `167.172.18.72`. Never modify `/opt/serviceflow`/the separate `infra` project. Follow AGENTS.md over older general deployment notes. Template bytes, extracts, drafts and proofs stay outside Git and image build contexts; originals and retained exports live in the inspection uploads volume.

Before replacing the image, privately record the deployed commit, image ID and container/project inventory; tag the old image for rollback. Build the pushed reviewed commit while the old API remains available. Briefly stop only the inspection API to take a consistent PostgreSQL dump and uploads archive, and save its private environment file. Keep backups root-only under `/opt/inspections-backups/`; verify gzip/archive integrity. Do not print credentials or copy them into Git.

Start with new integrations disabled. `INSPECTIONS_PDF_INTEGRATIONS_ENABLED=true` makes the optional administrative framework available; it does not enable either integration. Source provisioning must use `pdf_setup.install_candidate`, which only creates disabled/unpublished drafts, and an authorized active admin. Never forge field verification/publication to bootstrap defaults.

Deploy using the established procedure:

```sh
ssh root@167.172.18.72
# Confirm root@serviceflow-prod before continuing.
cd /opt/inspections
git fetch origin
git reset --hard origin/main
docker build --no-cache -t inspections-api:local .
docker compose -p inspections --env-file .env.inspections -f infra/compose.production.yaml up -d --force-recreate
docker compose -p inspections --env-file .env.inspections -f infra/compose.production.yaml ps
curl http://127.0.0.1:18080/health
```

Confirm the pushed commit on the server, the running image/Compose project, localhost and external health, packaged assets, authenticated admin draft selection/preview and the actual Points List review/edit/Accept–Review/bulk-delete/confirmation interaction. Test event retention and the legacy export on a clearly synthetic inspection. Verify both draft references and original hashes survive API recreation. Remove only temporary test sessions and soft-delete the synthetic inspection, preserving its evidence. Compare customer-data hashes/counts without treating legitimate concurrent user edits as corruption.

Do not label full production-form rollout complete while mappings/defaults/physical-print acceptance are deferred. Keep both exports disabled and report the remaining gates.

## Rollback

Disable integrations first if they were enabled. Restore the saved inspection image tag/commit in `/opt/inspections` only, set the optional feature off if needed, and recreate the **inspections** project. Retain additive tables, original files, decisions and artifacts; do not drop tables or restore a database over newer accepted customer decisions as an ordinary code rollback. The separate Work_Order project is never a rollback target. Recheck health and actual review behavior after rollback. Backup restore is a separate, explicitly reviewed recovery operation, not the normal response to a mapping error. Mapping-only defects can use explicit prior-version activation after review.
