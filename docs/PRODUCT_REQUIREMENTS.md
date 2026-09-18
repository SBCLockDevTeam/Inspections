# Product Requirements

## User workflow

The user creates an inspection, enters store number, address, inspection start and completion dates, and adds one or more security-panel Points Lists. Each Points List has a category. The application builds one combined Initiating Devices report and later fills Test Results from repeated Event History uploads.

## Inputs

- Points List: one or more XLS, XLSX, or PDF files per inspection.
- Points List category: Fire, Burglar, Combo, or Gas Station.
- Event History: one or more XLS, XLSX, or PDF uploads over the course of the inspection.
- Manual metadata: store number, address, inspection dates, technician, and optional customer information.

## Outputs

- Normalized Initiating Devices data.
- Completed inspection report in the required PDF format.
- Filename: `{store#}-{city},{state}-Initiating Devices-{category}-MM-DD-YY.pdf`.
- PDF generation is disabled until all required results and mappings are complete.
- Processing summary and exception report.
- Original source files retained with the inspection record.

## Reliability requirements

- No silent data loss.
- Every deleted row or rejected record must have a reason.
- Every test result must show its source event and matching point.
- Ambiguous records must be sent to a review queue.
- Successful mappings must survive later Event History uploads and reprocessing.
- A Points List becomes immutable after it is accepted into the inspection; corrections require an explicit replacement/version action.
- Reprocessing the same source files must be deterministic.
- AI API integration is not part of the first release.

## Acceptance criteria

- A technician can complete the normal workflow without editing raw spreadsheets.
- Valid points are retained and invalid points are excluded according to the processing rules.
- The first qualifying event per point is mapped correctly.
- Missing events, duplicate events, unexpected columns, and parsing failures are visible before export.
- The final report matches the approved customer template.
