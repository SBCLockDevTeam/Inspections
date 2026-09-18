# Application Architecture

## Recommended shape

Use a small web application with a browser interface, an API, a background processing worker, relational storage, and object storage for source and generated files.

Suggested first-release stack:

- Frontend: React with TypeScript.
- API: Python FastAPI.
- Processing: Python package shared by the API and worker.
- Background jobs: Redis-backed worker, such as RQ or Celery.
- Database: PostgreSQL.
- File storage: S3-compatible object storage, preferably a private DigitalOcean Space.
- Deployment: Docker Compose or separate containers on DigitalOcean, behind the existing server's reverse proxy.

The exact framework may change, but the boundaries must remain.

## Logical components

```text
Browser
  -> Web UI
  -> API
       -> Inspection service
       -> File intake service
       -> Deterministic processing engine
       -> Review and export service
       -> PostgreSQL
       -> Private object storage
       -> Background worker
```

## Processing pipeline

1. Store the original file unchanged.
2. Identify file type and extract a source table.
3. Normalize headers, rows, whitespace, and dates.
4. Run deterministic validation and transformation rules.
5. Produce normalized Points and Events datasets.
6. Join Events to Initiating Devices by normalized point address.
7. Create accepted records and exception records.
8. Require review of exceptions before export.
9. Generate the final report from a versioned template.

## Domain model

- Inspection
- SourceFile
- PointRecord
- EventRecord
- InitiatingDevice
- ProcessingRun
- Exception
- Export
- RuleSetVersion

Use stable internal IDs. Treat point address as a normalized business key, not as the database primary key.

## Security

- Keep uploaded files private.
- Use per-user authentication before production use.
- Validate file size, extension, MIME type, and content.
- Do not execute uploaded macros.
- Store secrets only in deployment secret storage.
- Never commit API keys, DigitalOcean tokens, database passwords, or `.env` files.
- Log metadata and processing decisions, not sensitive file contents.

