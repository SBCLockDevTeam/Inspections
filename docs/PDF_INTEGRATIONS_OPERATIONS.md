# PDF integrations operating guide

## Current workflow (October 29 interface simplification)

This workflow supersedes the earlier draft/test/verify/publish setup instructions for the normal interface. Both supplied forms remain available. Existing drafts, published configurations, accepted answers and retained exports are preserved. No default mappings are inferred from template presets.

## Configure an integration

1. Open **Administration → Integrations → Open NFPA 72** or **Open Compliance Form**. No sample inspection or panel selection is needed.
2. Choose a PDF field in the left list or directly on the form. The highlighted rectangle identifies its exact page and occurrence even when field names repeat. Search the PDF field list or change page/zoom as needed.
3. On the right, choose a blue field-name button grouped under **Store Data**, **NFPA 72** or **Compliance**. Selecting a PDF field highlights its mapped inspection field in light blue and scrolls it into view. The list includes all active checklist definitions, including fields whose answers have not been entered yet. Points Lists and Events are not mapping sources for these forms.
4. Each writable PDF field on the **left** has its own **PDF default** box. Enter fixed company/contact text there even when that field has no Inspection mapping: the value prints in the PDF without adding an Inspection field. For a mapped PDF field, its default is used only when the compatible saved answer is empty. Leave the box empty for no default. These values belong only to the integration; saving or exporting never fills or changes Store Data, checklist answers or task definitions. The right pane contains Inspection source buttons and a small **×** that clears only the connection, preserving the PDF default. Defaults also remain attached to the PDF field when changing its source. Existing Required/format settings remain saved and can be edited in Debug mode. PDF checkbox fields offer only **Checked** and **Not checked** on the left. An unset checkbox is shown as **Not checked**, and Save integration records that Boolean state in a new version; existing published versions are retained. With no mapping, the explicitly configured state prints in every export. With a mapping, the default applies only when the compatible saved answer is missing; saved Yes/No/NA answers still control the mark through **Mark when**. An incompatible or changed source blocks instead of using its default. This user-configured PDF state never changes checklist answers. Radio groups and signatures keep their existing restrictions.
5. **Save integration** validates source compatibility, formatting and defaults, renders private watermarked proofs, retains a new immutable published version, and enables it for all inspections. Unmapped fields are deliberately blank. The displayed mapped/blank counts disclose that choice. Save does not certify business completeness or physical readability of the resulting form: review the form and choose Required deliberately.
6. If another administrator saves or the available checklist definitions change, the save fails with a conflict and retains local edits. Reopen to compare current settings. Existing versions are never overwritten.

JSON, inventory metadata, prior versions and the earlier advanced draft/test/publication tools are behind **Debug mode**. Existing advanced configurations remain readable and usable. Saving through the normal interface explicitly creates a Store Data/Check List version: former manual/panel candidate fields become unmapped blanks, with the original configuration retained. Review the mapped/blank counts before saving. Disablement and explicit prior-version activation remain available in Debug mode.

A changed/deactivated checklist type or choice set requires mapping review; a default cannot hide an incompatible source. Renaming or reordering a task retains its stable identity. Long or unsupported values block with a field-specific error rather than being truncated. Closed PDF choices accept only their declared options.

NFPA exports exactly pages 1–4; Compliance exports page 1. Supplemental reports remain separate, and this partial NFPA form does not certify that supplemental reports are attached. Map any such declaration to an actual checklist answer when needed. No signatures, attachment declarations or passing outcomes are inferred.

## Technician export

Save the inspection's **Store Data**, **NFPA 72** and **Compliance** answers. Open **☰ → Export Forms** and choose **Export NFPA 72** or **Export Compliance Form**. Required mapped answers must exist or have a configured default. Optional missing answers remain blank. NFPA 72 and Compliance fields use the same editable, automatically saved checklist controls. Administrators add or move fields using the Section selector under Administration → Data Sections; new fields become PDF sources automatically. No panel selection, Points List approval, Event History mapping or separate manual Form Details answers are required for integrations saved through the normal interface. Existing Initiating Devices export rules are unchanged.

Review the watermarked preview, then confirm and download. The PDF uses saved data from that specific inspection. The server rechecks authorization, current configuration and preview hash; a source/configuration change requires a new preview. Retries reuse the same confirmed record. Export history retains final PDFs and offers technical provenance under Debug provenance.

Historical downloads retain their original data and hashes even after an integration is disabled. Deleted/inaccessible inspections cannot download. Correct saved data and create a new export rather than editing retained files.

## Recovery and maintenance

A pending record is not downloadable. After the two-minute processing lease, the requester or administrator may recover a pending final from history. Recovery regenerates the frozen plan with the recorded renderer, checks any existing bytes and seals the same record. A database failure after a file write is recoverable; filesystem publication and database commit are deliberately separate. Unknown renderer versions need the matching application image/operator review. Failed records remain failed; create a fresh reviewed preview/request after resolving the cause.

The admin-only POST `/api/admin/integrations/maintenance/expired-previews` removes at most 100 ready preview files more than a day beyond their 30-minute expiry and records cleanup. It never removes originals, final files, accepted decisions or audit records. Do not manually delete pending final bytes: they may be awaiting reconciliation. Bound resource use with the existing Linux worker (30 seconds wall, 20 seconds CPU, 512 MiB address space, 64 MiB output); diagnose a failed test rather than raising limits blindly.

## Isolated deployment and backup

Only use `/opt/inspections`, Compose project `inspections`, and port 18080 on `167.172.18.72`. Never modify `/opt/serviceflow`/the separate `infra` project. Follow AGENTS.md over older general deployment notes. Template bytes, extracts, drafts and proofs stay outside Git and image build contexts; originals and retained exports live in the inspection uploads volume.

Before replacing the image, privately record the deployed commit, image ID and container/project inventory; tag the old image for rollback. Build the pushed reviewed commit while the old API remains available. Briefly stop only the inspection API to take a consistent PostgreSQL dump and uploads archive, and save its private environment file. Keep backups root-only under `/opt/inspections-backups/`; verify gzip/archive integrity. Do not print credentials or copy them into Git.

Keep the global feature switch available as before. Installing a template/candidate still creates an unpublished disabled draft. An administrator’s explicit **Save integration** now validates, publishes and enables the chosen Store Data/Check List configuration; deploying this interface never auto-saves or enables existing drafts. No source PDFs or private proof files belong in Git.

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

Report any unmapped business fields and pending physical-print acceptance. Deployment alone does not enable either integration; the administrator establishes mappings/defaults and explicitly saves when ready.

## Rollback

Disable integrations first if they were enabled. Restore the saved inspection image tag/commit in `/opt/inspections` only, set the optional feature off if needed, and recreate the **inspections** project. Retain additive tables, original files, decisions and artifacts; do not drop tables or restore a database over newer accepted customer decisions as an ordinary code rollback. The separate Work_Order project is never a rollback target. Recheck health and actual review behavior after rollback. Backup restore is a separate, explicitly reviewed recovery operation, not the normal response to a mapping error. Mapping-only defects can use explicit prior-version activation after review.

## Simplified-interface verification

The implementation passed a full 325-test regression run with PostgreSQL and real Chromium enabled (no skips), plus a 25-case focused run covering the final mapper/export changes and two additional dense-field/default-overflow cases. Compilation, JavaScript syntax and whitespace checks passed. Both private supplied forms rendered a mapped inspection date with exact 4/1-page outputs; the dense Compliance date field uses a 5-point font determined from its geometry. An independent Poppler render was reviewed. An existing probe test's process-reaping race was corrected without changing application process limits. The only warning is the existing FastAPI/Starlette test-client deprecation.

The production administrator still owns the actual business mappings and defaults. Installing this update does not publish or enable the retained reference drafts. Physical-printer acceptance, additional NFPA pages, automatic signatures and supplemental attachment merging remain outside this update.

Checkbox-default update: the full suite passed 345 tests with SQLite, PostgreSQL and Chromium enabled, with no skips. Coverage includes strict Boolean validation, retaining an explicit unchecked default, checked/unchecked final PDFs inspected with an independent renderer, saved Yes/No/NA taking precedence, required missing-answer fallbacks, changed-source blocking, and unchanged Inspection answers. The only warning is the existing test-client deprecation.

## October 30 inspection section update

The inspection form now has editable NFPA 72 and Compliance sections. Manage both under Administration → Data Sections using the Section selector. The one-time additive migration assigns existing tasks to Compliance and moves Panel Model/Firmware version to NFPA 72, preserving IDs, choices, answer history and existing PDF references. Administrators may subsequently move fields without changing their saved answers. Source grouping refreshes from those definitions; moving a field does not change its compatibility hash.

All former Export Form Details tools are under inspection ☰ → Export Forms, including existing advanced manual details/scope, readiness, preview, confirmation, history and recovery. Closing the dialog preserves local export-detail edits. NFPA 72 in the inspection form is for editable inspection data and is independent of the optional PDF feature switch.

Verification: 351 full regression cases passed with PostgreSQL and Chromium enabled; 27 focused field/API/migration cases also passed, including the final dropdown-definition byte-preservation check. The single warning is the existing test-client deprecation. Deployment compares legacy data excluding only the new section column, and separately verifies the exact intended section assignments and unchanged field IDs/types/options.

### Administration → Data Sections

The former Inspection Tasks tab is named Data Sections. The Section selector supports Store Data, NFPA 72 and Compliance for new and existing custom fields. Store Data custom fields use the same typed controls, autosave, Header Save, history and shared refresh as the other sections, and automatically appear in the Store Data integration source group. The built-in Store Number/address/date identity fields and their validation remain intact. No existing field is moved automatically by this update.

Data Sections/Store Data update: 353 regression tests passed with PostgreSQL and Chromium enabled and no skips. Browser coverage adds a Store Data custom field through Administration, verifies its placement and cross-device saving, and confirms the built-in Store Number is unchanged. Mapping coverage confirms new Store Data fields appear while preserving local mapping edits. The only warning is the existing test-client deprecation.
