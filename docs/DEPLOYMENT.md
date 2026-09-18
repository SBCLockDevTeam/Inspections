# Deployment Isolation Plan

## Existing application

The existing application is `C:\Users\User\Documents\code\python\sbc\Work_Order`. It is not to be edited, reconfigured, or used as a source of shared runtime state.

## New repository

Create a new private GitHub repository with a distinct name, for example `alarm-inspection-processor`. The repository root must contain its own README, `.env.example`, Docker files, CI workflow, infrastructure notes, and application code.

## DigitalOcean separation

Use a distinct application/service name, for example `alarm-inspection-processor`. The deployment must have:

- Its own image or build directory.
- Its own environment variable namespace.
- Its own database/schema and database user.
- Its own private object-storage bucket or Space prefix.
- Its own Redis namespace or instance.
- Its own health-check path.
- Its own logs and rollback procedure.
- A separate reverse-proxy hostname or path configured only after local verification.

Do not overwrite the existing application's container, compose project, deployment directory, domain configuration, or environment file.

## Secrets

Use GitHub Actions secrets or DigitalOcean secret storage for deployment credentials. Use a separate token with the minimum permissions needed. Do not copy the existing application's `.env` file. The local DigitalOcean credential file may be used only by the operator to create the new resources; it must never be committed or printed.

## Deployment stages

1. Local Docker Compose.
2. Private or temporary DigitalOcean deployment.
3. Smoke test with sanitized fixture files.
4. Production hostname and TLS configuration.
5. Backup and rollback verification.

