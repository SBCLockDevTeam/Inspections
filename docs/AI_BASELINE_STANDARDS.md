# AI Baseline Standards

## Purpose
This file defines baseline implementation and review standards for AI-assisted changes in this repository.

## Core Principles
1. Deterministic first.
- Parsing, normalization, mapping, approval, and export gating logic must remain deterministic.
- AI must never silently mutate accepted mappings, point addresses, approval decisions, or event timestamps.

2. Preserve auditability.
- Keep original uploads and decision evidence intact.
- Avoid destructive transformations that erase source lineage.

3. Feature isolation.
- API code should be organized by feature responsibility (auth, admin, inspections, point-list preview, UI serving).
- Shared cross-cutting concerns should live in common helper modules.

4. Backwards-compatible API behavior.
- Preserve existing paths, payload keys, and error conventions unless an explicit versioning decision is made.

## Required Workflow for Structural Refactors
1. Create backups before edits.
2. Apply changes in dependency order.
3. Run compile and tests.
4. Document architecture deltas and known risks.

## Security and Data Handling
- Keep uploaded files private.
- Never commit secrets, tokens, `.env` files, or customer source files.
- Validate uploads by extension, type, and deterministic parser checks.

## Quality Gates
- Code compiles.
- Tests pass.
- No new route regressions.
- Documentation reflects current module boundaries.
