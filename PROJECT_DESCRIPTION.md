# Alarm Inspection Processing Application

## Purpose

This online application turns alarm Points Lists and Event History files into reviewable, auditable Initiating Devices inspection reports. It is a separate application and deployment from the existing `Work_Order` system.

## Workflow

1. Enter the new inspection details and choose Save or Cancel. Save creates the inspection; Cancel discards the form without adding a record.
2. Upload one or more Points Lists, one per security panel.
3. Assign each Points List a configured panel type. The defaults are Fire, Burglar, Combo, and Gas Station; administrators can add more under Administration → Panel Types.
4. Parse the files and show a review modal before committing the inspection.
5. Edit descriptions, change each record between Accept and Review, and delete all remaining Review rows.
6. Explicitly approve the reviewed Points Lists. Loading a file is not approval.
7. Upload Event History repeatedly as testing proceeds.
8. Retain successful point-to-time mappings across uploads until every required point is mapped.
9. Resolve missing, duplicate, conflicting, or malformed mappings.
10. Generate the final PDF only after all required results and mappings are complete.

Inspections can be deleted from Home or from an open inspection after explicit confirmation. Deleted inspections disappear from the active list and cannot be opened or edited. Original uploads, review decisions, and successful mappings remain stored for audit.

Inspection names use `{store number}-{City}-{ST}-{MM-YYYY}`, based on the inspection Start Date. The application generates the name for new and existing inspections and updates it when store number, city, state, or Start Date changes. New inspections require City and a two-letter State. Existing locations are extracted conservatively from their saved addresses; missing or ambiguous locations require correction. This naming convention does not change the final PDF filename format below.

Administration groups user accounts and password settings under Users and provides a separate Panel Types tab. Panel types are shared, persisted choices; only administrators can add them. Names are limited to 40 characters and duplicates are rejected regardless of capitalization or extra spaces. Existing Points List categories remain intact.

Application form fields use a consistent inline `Label: Data` layout, including Store Data, creation dialogs, administration, and PDF fields. Checkbox task descriptions retain their checklist layout. Administrators can reorder dropdown choices with up/down arrows when adding or editing a task; the saved order appears in inspection dropdowns, while existing answers and historical choice snapshots are retained.

The inspection form contains independently collapsible Store Data, NFPA 72, Compliance, and Points Lists & Events sections. Custom Store Data fields, NFPA 72 and Compliance share the typed field/decision system; administrators choose a section when adding or editing a data field. Panel Model and Firmware version are in NFPA 72. Existing IDs and answers survive section moves, and new fields in both sections automatically become integration sources. The former Export Form Details tools are available under the inspection hamburger menu → Export Forms. Administrators manage shared checklist tasks under Administration → Data Sections, including descriptions, order, active status, and an input type: Checkbox, Textbox, or Dropdown. Dropdown choices can be added and removed in administration. Existing selected choices remain visible if removed from the current list, and type changes preserve prior answers in history. Each inspection keeps its own checklist values and completion decisions, including the user, timestamp, task text, input type, and dropdown choices at the time of entry. Checkbox changes and dropdown selections save immediately; textbox values save on leaving the field, pressing Enter, or using the inspection Save button. Values synchronize across devices while unsaved local edits remain private. Checkbox tasks show three boxes: Yes, No, and NA, with at most one selected. Any selection counts as answered; deselecting it clears the answer. Existing checked answers display as Yes and existing unchecked answers stay unanswered. This applies to existing and new tasks and inspections without rewriting decision history. New tasks appear on existing and new inspections; deactivating a task retains earlier decisions. No checklist tasks are prefilled.

The Points List table has its own horizontal scroll area, including in Edit mode, so the Test Result column and its full input remain reachable on narrow screens.

Saved shared state refreshes across active devices approximately every three seconds, including inspection details, Device Type highlights, points, checklist decisions, administration, and PDF drafts. Unsaved local edits remain private and are preserved during refresh. Pending Event History matches are shared evidence and still require explicit acceptance. Hidden browser tabs catch up when reopened; interrupted connections retry automatically.

## Points List rules

The original specification requires support for XLS, XLSX, and PDF source files with layout variation. The parser must identify point and description columns by headers/content rather than fixed letters, handle blank columns, combine descriptions rendered across multiple rows, reject unassigned and placeholder rows, and reject point addresses outside 1 through 255.

Accepted and Review decisions must be visible to the technician. Descriptions are editable. The original source file must be retained for audit, while approved decisions become the working dataset. Corrections after approval require an explicit replacement or versioning action.

Device Type cells toggle between white and very light green on double-click (or Enter/Space while focused). Highlights save automatically per accepted point and persist when reopening the inspection; they do not change review status or test results. After a successful Event History upload, a marked cell turns light yellow when it has neither a pending nor an accepted event time. A later matching upload restores green; accepted times keep their green status. Pending evidence accumulates across uploads and devices without automatically accepting results.

## Event History rules

Event History uploads are cumulative evidence batches. Keep event types `A` and `T`, normalize point addresses, and select the first qualifying timestamp for each approved point. Never silently replace a successful mapping. Later uploads may fill previously unmapped points.

## Output

The final output is an Initiating Devices PDF. It must not be created while any required result, mapping, location, description, or exception remains unresolved.

Final Initiating Devices exports use saved, accepted points and accepted test times
for the explicitly selected panel. Request data cannot substitute or omit points.
Ordinary table saves preserve accepted mappings and their evidence; correcting an
accepted test time requires explicitly clearing saved dates first. Clearing results,
editing accepted points, accepting event times, and deleting panels record the user,
time, and prior data in an append-only audit table. Deleted panels are hidden while
their source files, decisions, and mappings remain stored.

Filename format:

```text
{store#}-{city},{state}-Initiating Devices-{category}-MM-DD-YY.pdf
```

If an inspection contains multiple categories, export behavior must be explicit; the application must not guess.

## AI boundary

The first release must work without an AI API key. Parsing, validation, matching, approval, and export gating are deterministic and authoritative. Future AI support may suggest descriptions, locations, column mappings, or explanations for exceptions, but it must never silently change point addresses, timestamps, approvals, or export eligibility.

## Technical and deployment boundary

The application uses FastAPI, PostgreSQL, persistent private file storage, and Docker Compose. It is deployed as a separate `inspections` project on the same DigitalOcean server as `Work_Order`, currently exposed temporarily on port 18080. It must not reuse the existing application's database, volumes, environment files, containers, ports, or deployment directory.

## Current implementation and remaining work

The prototype includes inspection intake, multiple categorized Points List uploads, an XLSX preview parser, review UI, PostgreSQL metadata, repeated Event History upload storage, health checks, and isolated deployment files.

Before production use, complete and test approval-state transitions, review every uploaded Points List, correct continuation-row parsing, move UI code out of inline scripts, add authentication and upload validation, use persistent file storage, add XLS/PDF adapters, implement cumulative Event History mapping, add database migrations, and implement gated PDF generation.

The original requirements are documented in `inspection spec.docx`; this description incorporates that document and all scope decisions made afterward.

