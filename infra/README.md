# Deployment Instructions

This deployment is intentionally separate from the existing Work_Order deployment.

## Required server setup

Create a dedicated directory such as `/opt/inspections`, a dedicated Compose project name `inspections`, and a dedicated environment file `.env.inspections`. Do not place these files in the Work_Order directory.

The reverse proxy should forward a new hostname or path to `127.0.0.1:18080`. Do not reuse the existing application's port or Compose project.

## Required environment values

At minimum, `.env.inspections` must contain:

```text
INSPECTIONS_IMAGE=ghcr.io/sbclockdevteam/inspections:main
POSTGRES_DB=inspections
POSTGRES_USER=inspections
POSTGRES_PASSWORD=<generated-secret>
DATABASE_URL=postgresql+psycopg://inspections:<same-password>@db:5432/inspections
REDIS_URL=redis://redis:6379/0
STORAGE_BUCKET=<private-inspections-space>
AI_PROVIDER=disabled
```

Do not commit `.env.inspections`.

## First deployment sequence

1. Create the private container registry or choose the server's existing registry policy.
2. Configure GitHub Actions secrets for registry access and deployment access.
3. Build and publish the image from `main`.
4. Copy `infra/compose.production.yaml` to `/opt/inspections`.
5. Create `.env.inspections` on the server.
6. Run `docker compose -p inspections -f compose.production.yaml pull`.
7. Run `docker compose -p inspections -f compose.production.yaml up -d`.
8. Verify `/health` locally on port 18080 before changing the reverse proxy.
9. Configure the new hostname or path and TLS.
10. Run a smoke test with sanitized fixture files.

## Rollback

Set `INSPECTIONS_IMAGE` to the previous image tag and run `docker compose -p inspections ... up -d`. Never roll back by changing or restarting the Work_Order Compose project.

