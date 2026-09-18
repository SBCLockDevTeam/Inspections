# Implementation Roadmap

## Phase 0 Discovery

- Collect representative Points List files, Event History files, and one approved final report.
- Record file formats, column aliases, date formats, and output requirements.
- Define the first rule-set version.

## Phase 1 Foundation

- Create the new GitHub repository.
- Create the application skeleton with frontend, API, processing package, worker, tests, and deployment files.
- Add local development with Docker Compose.
- Add health checks, structured logging, and environment validation.

## Phase 2 Deterministic processing

- Implement spreadsheet intake.
- Implement header detection and normalization.
- Implement Points List rules.
- Implement Event History rules.
- Implement point matching and first-event selection.
- Support multiple categorized, immutable Points Lists per inspection.
- Support repeated Event History uploads with cumulative mapping retention.
- Add fixture-based tests from real but sanitized files.

## Phase 3 Review workflow

- Add inspection creation and metadata entry.
- Add upload progress and processing status.
- Add accepted/review/rejected summaries.
- Add a review screen for exceptions and locations.
- Require explicit approval of the initial Points List parse before acceptance.
- Add immutable processing-run results.

## Phase 4 Export

- Implement the approved Initiating Devices template.
- Block export until results and mappings are complete.
- Generate the required category-aware PDF filename.
- Add PDF layout verification against the approved template.
- Add export verification and download history.

## Phase 5 PDF input

- Add text-based PDF extraction.
- Add OCR only if real samples require it.
- Keep OCR results reviewable and never treat OCR output as unquestionable.

## Phase 6 Optional AI support

- Add a provider interface with a disabled default.
- Use AI only for flagged descriptions, column mapping suggestions, or location suggestions.
- Require human acceptance and store the prompt, model, response, and decision when AI is enabled.
- Add token budgets, caching, and batch review to prevent excessive usage.
