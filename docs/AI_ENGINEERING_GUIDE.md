# AI Engineering Guide

This document is for the AI used to build and maintain the application.

## Rules for every AI coding session

1. Read this file and the relevant document under `docs/` before changing code.
2. Read only the package, module, and tests relevant to the requested change.
3. Do not inspect or modify the existing `Work_Order` application.
4. Do not change deployment, database schema, or public behavior without updating the decision log.
5. Make the smallest coherent change.
6. Add or update tests before changing a processing rule.
7. Run targeted tests first, then the full test suite when practical.
8. Report changed files, tests run, and unresolved risks.

## Token-efficiency practices

- Keep domain rules in small pure functions with narrow tests.
- Use fixture files and compact expected-result JSON instead of repeatedly sending whole spreadsheets to an AI.
- Maintain a short `docs/CHANGELOG_AI.md` containing recent architecture changes and known issues.
- Use repository search and targeted file reads rather than loading the whole repository.
- Ask the AI to modify one bounded concern at a time.
- Prefer generated diagnostics and test failures over large source dumps.
- Store reusable prompts in `docs/prompts/` only when they are genuinely repeated.

## Required change report

Every implementation change should end with:

- Summary of behavior changed.
- Files changed.
- Tests added or run.
- Data or migration impact.
- Deployment impact.
- Remaining uncertainty.

## AI provider boundary

The first release must work with no AI key. Define an interface such as `SuggestionProvider` behind the processing engine. The default implementation returns `not_configured`. The deterministic engine must never call that interface during normal processing.

## Review standard

AI-generated code is not accepted merely because tests pass. Review file handling, authorization, data retention, date/time behavior, duplicate handling, error visibility, and whether a rule has accidentally become a guess.

