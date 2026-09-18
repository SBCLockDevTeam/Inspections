# Alarm Inspection Processing Application

## Purpose

This online application turns alarm Points Lists and Event History files into reviewable, auditable Initiating Devices inspection reports. It is a separate application and deployment from the existing `Work_Order` system.

## Workflow

1. Create an inspection with store number, address, city, state, and inspection dates.
2. Upload one or more Points Lists, one per security panel.
3. Assign each Points List a category: Fire, Burglar, Combo, or Gas Station.
4. Parse the files and show a review modal before committing the inspection.
5. Edit descriptions, change each record between Accept and Review, and delete all remaining Review rows.
6. Explicitly approve the reviewed Points Lists. Loading a file is not approval.
7. Upload Event History repeatedly as testing proceeds.
8. Retain successful point-to-time mappings across uploads until every required point is mapped.
9. Resolve missing, duplicate, conflicting, or malformed mappings.
10. Generate the final PDF only after all required results and mappings are complete.

## Points List rules

The original specification requires support for XLS, XLSX, and PDF source files with layout variation. The parser must identify point and description columns by headers/content rather than fixed letters, handle blank columns, combine descriptions rendered across multiple rows, reject unassigned and placeholder rows, and reject point addresses outside 1 through 255.

Accepted and Review decisions must be visible to the technician. Descriptions are editable. The original source file must be retained for audit, while approved decisions become the working dataset. Corrections after approval require an explicit replacement or versioning action.

## Event History rules

Event History uploads are cumulative evidence batches. Keep event types `A` and `T`, normalize point addresses, and select the first qualifying timestamp for each approved point. Never silently replace a successful mapping. Later uploads may fill previously unmapped points.

## Output

The final output is an Initiating Devices PDF. It must not be created while any required result, mapping, location, description, or exception remains unresolved.

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

