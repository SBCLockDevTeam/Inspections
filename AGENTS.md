# Project Instructions

## Project identity

This is the Alarm Inspection Processing Application, GitHub repository SBCLockDevTeam/Inspections.

Read PROJECT_DESCRIPTION.md and the relevant files under docs/ before making changes.

## Find the editable source

The editable application source is under src/alarm_inspection/, with FastAPI code under src/alarm_inspection/api/, deterministic rules under src/alarm_inspection/domain/, parsers under src/alarm_inspection/intake/ when present, tests under tests/, and deployment files under infra/.

If a project tool shows only sources/, treats it as an empty mirror, or says there is no editable source, do not stop. Locate the repository root by finding pyproject.toml, Dockerfile, README.md, and src/alarm_inspection/api/app.py. Do not create a replacement application in sources/.

## Source-of-truth requirements

- Read the actual files under src/ before editing.
- Do not infer implementation from the live page alone.
- Keep deterministic parsing, validation, mapping, approval, and export rules in Python source and tests.
- Preserve original uploads and audit decisions.
- Never silently delete or replace accepted mappings.
- Do not add an AI API dependency without an explicit scope decision. The first release works without an AI key.

## Required review workflow

Points Lists are one per security panel and each has a category: Fire, Burglar, Combo, or Gas Station.

The review flow is:

1. Load one or more Points Lists.
2. Parse and show every list in a modal/table review view.
3. Allow description edits.
4. Allow each row status to change between Accept and Review.
5. Provide a button to delete all rows still in Review.
6. Require explicit confirmation before committing the reviewed data.

The modal must not show a source-row column. Do not repurpose a removed source-row column as a Delete column. Status controls and the bulk delete action must be separate and clear.

Event History may be uploaded repeatedly. Successful point-to-time mappings persist across uploads until all required mappings are complete.

Do not generate the final PDF until all required mappings and manual decisions are complete. Filename format:

    {store#}-{city},{state}-Initiating Devices-{category}-MM-DD-YY.pdf

## GitHub workflow

Remote: https://github.com/SBCLockDevTeam/Inspections.git

Before changing code:

    git fetch origin
    git status
    git log -5 --oneline

After a coherent change:

    python -m compileall -q src tests
    git add <specific-files>
    git commit -m "Describe the change"
    git push origin main

Do not commit .env, tokens, passwords, customer source files, generated uploads, or deployment secrets.

## DigitalOcean deployment

The existing application is a separate Compose project named infra under /opt/serviceflow. Do not modify it.

The inspection application runs separately:

- Server: 167.172.18.72
- Remote directory: /opt/inspections
- Compose project: inspections
- Temporary HTTP port: 18080
- Health URL: http://167.172.18.72:18080/health

Never paste or transmit the DigitalOcean token. Authenticate locally with doctl auth init when needed. Use SSH:

    ssh root@167.172.18.72

Only after the prompt is root@serviceflow-prod run:

    cd /opt/inspections
    git fetch origin
    git reset --hard origin/main
    docker build --no-cache -t inspections-api:local .
    docker compose -p inspections --env-file .env.inspections -f infra/compose.production.yaml up -d --force-recreate
    docker compose -p inspections --env-file .env.inspections -f infra/compose.production.yaml ps
    curl http://127.0.0.1:18080/health

Do not run /opt/..., docker, or server deployment commands in local Windows PowerShell. Do not run git reset --hard against the existing Work_Order repository.

## Verification standard

Before declaring a deployment complete:

- Confirm the GitHub commit is present on the server.
- Confirm the inspections Compose project is running.
- Confirm the health endpoint.
- Confirm the live page contains the changed behavior.
- Test the actual review interaction, not only the health endpoint.
- Report remaining known limitations.

