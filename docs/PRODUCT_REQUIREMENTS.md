# Product Requirements

## User workflow

The user creates an inspection, enters store number, address, inspection start and completion dates, and uploads source files. The application builds an Initiating Devices report and later fills Test Results from Event History.

## Inputs

- Points List: XLS, XLSX, or PDF.
- Event History: XLS, XLSX, or PDF where practical; the first release may require spreadsheet input if PDF extraction is not reliable.
- Manual metadata: store number, address, inspection dates, technician, and optional customer information.

## Outputs

- Normalized Initiating Devices data.
- Completed inspection report in the required Excel format.
- Optional PDF export after the Excel output is verified.
- Processing summary and exception report.
- Original source files retained with the inspection record.

## Reliability requirements

- No silent data loss.
- Every deleted row or rejected record must have a reason.
- Every test result must show its source event and matching point.
- Ambiguous records must be sent to a review queue.
- Reprocessing the same source files must be deterministic.
- AI API integration is not part of the first release.

## Acceptance criteria

- A technician can complete the normal workflow without editing raw spreadsheets.
- Valid points are retained and invalid points are excluded according to the processing rules.
- The first qualifying event per point is mapped correctly.
- Missing events, duplicate events, unexpected columns, and parsing failures are visible before export.
- The final report matches the approved customer template.

