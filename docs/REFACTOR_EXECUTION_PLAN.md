# API Refactor Execution Plan

## Scope
Refactor the monolithic API module into feature-focused modules while preserving behavior, route contracts, and deterministic processing rules.

## Completed Backup
- Timestamped backup directory created: `backups/refactor-20260922-210344`
- `app.py` backed up before edits.
- All workspace markdown files (`.md`) backed up before edits.

## Logical Order of Changes (Dependency-Aware)
1. Extract shared utility primitives first.
- Password hashing/verification helpers.
- General parsing/boolean/date helpers.
- Shared auth and admin support helpers.

2. Extract leaf feature routers next.
- Point-list preview router.
- UI router for home page and review script serving.

3. Extract stateful routers after shared helpers exist.
- Auth router.
- Admin router.
- Inspections router and event-history/event-dates workflow.

4. Replace `app.py` last.
- Keep it thin: app creation, middleware, route registration.
- Keep backwards-compatible symbols required by existing tests.

5. Verify runtime and test behavior.
- Compile source and tests.
- Run test suite.
- Resolve regressions before finalizing.

## Expected Results
- API remains functionally equivalent:
- Existing route paths and payload behavior remain stable.
- Auth middleware continues to guard `/api/*` except explicit auth endpoints.
- Event-history and review workflows remain deterministic.

- New architecture quality targets:
- `app.py` acts as composition root only.
- Feature ownership is explicit per router module.
- Shared helpers are reused instead of duplicated.
- Static HTML payload is externalized from Python source.

## Verification Checklist
- [ ] `python -m compileall -q src tests` succeeds.
- [ ] `pytest` passes.
- [ ] Home page still serves and loads `review.js`.
- [ ] Existing tests that import `app._UPLOAD_ROOT` and `app._ensure_inspection_upload_dir` still pass.

## Rollback Path
If any regression appears:
1. Restore from `backups/refactor-20260922-210344`.
2. Re-apply refactor in smaller steps by router.
3. Re-run compile and tests after each step.
