# Deployment Instructions

This deployment is intentionally separate from the existing Work_Order deployment.

## Required server setup

Create a dedicated directory such as `/opt/inspections`, a dedicated Compose project name `inspections`, and a dedicated environment file `.env.inspections`. Do not place these files in the Work_Order directory.

Until a domain is available, the API can be reached at `http://SERVER_IP:18080`. Later, a reverse proxy can forward a hostname or path to port 18080. Do not reuse the existing application's port or Compose project.

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
INSPECTIONS_BOOTSTRAP_ADMIN_PASSWORD=<unique-secret-at-least-12-characters>
```

Do not commit `.env.inspections`.

The bootstrap password is required when no administrator exists, or when upgrading an
installation that still uses the original predictable administrator password. There
is no default bootstrap password. The initial administrator must change its password
before accessing inspections or administration. Securely initialized installations
can restart without the bootstrap variable; rotating this variable does not change
an administrator's already secured password.

## Preserve existing uploads before the first storage upgrade

The API now mounts a dedicated `inspections_inspections_uploads` volume at the original
upload path, so existing database paths remain valid. Existing uploads in the old
container must be copied before that container is recreated. Run the following only
on the inspection server, in `/opt/inspections`, during a maintenance window. These
commands stop only the inspections API and leave the original uploads and a separate
backup intact. If a command fails, retain the old container and backup and do not
continue with recreation.

```bash
cd /opt/inspections
api_container=$(docker compose -p inspections --env-file .env.inspections -f infra/compose.production.yaml ps -q api)
test -n "$api_container"
source_image=$(docker inspect --format '{{.Image}}' "$api_container")
upload_backup="/opt/inspections/backups/uploads-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$upload_backup"
docker compose -p inspections --env-file .env.inspections -f infra/compose.production.yaml stop api
docker cp "$api_container:/tmp/alarm-inspection-uploads/." "$upload_backup/"
docker volume create inspections_inspections_uploads
docker run --rm --entrypoint python \
  --mount "type=bind,source=$upload_backup,target=/backup,readonly" \
  --mount type=volume,source=inspections_inspections_uploads,target=/restore \
  "$source_image" -c 'import shutil; shutil.copytree("/backup", "/restore", dirs_exist_ok=True)'
```

After the copy succeeds, build and recreate the inspections API using the project
deployment sequence. Verify that previously uploaded files and saved PDF drafts
remain readable. Back up both PostgreSQL and the uploads volume; do not use Compose
`down -v` during upgrades. Fresh installations do not need this copy step.

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

## Inspection HTTPS hostname

`https://inspections.securitybuildingcontrols.com` uses the optional `https`
service in the **inspections** Compose project. Caddy manages and renews its
Let's Encrypt certificate using TLS-ALPN validation on TCP 443. DNS must have
an A record named `inspections` pointing to `167.172.18.72`, and TCP 443 must be
reachable. Do not add an AAAA record unless IPv6 is separately configured.

Port 80 belongs to the separate serviceflow application. This configuration
neither binds port 80 nor installs HTTP-to-HTTPS redirects there. Use and bookmark
the full HTTPS URL. Do not edit or restart the `infra` project.

After DNS resolves correctly, enable `COMPOSE_PROFILES=https` in the server's
private `.env.inspections` and start `https`. Validate the certificate and HTTPS
health endpoint before making the final cutover. Then set these additional
values in that same private file and recreate the inspections API:

```text
INSPECTIONS_HTTP_BIND=127.0.0.1
INSPECTIONS_COOKIE_SECURE=true
```

The old public IP:18080 URL then stops accepting connections. The health endpoint
remains available on `http://127.0.0.1:18080/health` on the server. Secure session
cookies are sent only over HTTPS; no passwords are stored in browser local storage.
Password saving/autofill remains a browser/password-manager setting.

Use the normal production Compose command; its `--env-file .env.inspections`
also retains the HTTPS profile on future deployments. Caddy certificate keys and
ACME state persist in `inspections_caddy_data`; never commit them or delete the
volume. Verify HTTPS health, the served page, a trusted certificate, and unchanged
serviceflow container IDs after deployment. To roll back the cutover, restore the
previous bind/cookie values in the private environment and recreate only the
inspections API; do not remove its database or uploads volumes.
