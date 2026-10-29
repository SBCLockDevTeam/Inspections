# Alarm Inspection Processor

A separate web application for turning alarm Points List and Event History files into reviewable, auditable inspection reports.

The first release is deterministic and does not require an AI API key.

See [docs/README.md](docs/README.md) for the product and engineering documentation.

Deployment notes are in [infra/README.md](infra/README.md). The deployment is designed to coexist with the existing Work_Order application on the same DigitalOcean server.

## Local development

The processing rules are currently implemented as a small Python package so they can be tested independently of the web interface. The initial development target is Python 3.12.

```text
src/alarm_inspection/
  domain/       Pure business rules and normalized records
  intake/       File parsing and source-table detection
  services/     Application workflows
  api/          HTTP endpoints
tests/          Unit and fixture tests
```


PDF integrations P4–P6 add **Administration → Integrations** and an isolated **Export Form Details** section. Administrators upload private templates, select exact widget occurrences, configure typed mappings/policies, review watermarked tests and explicitly verify/publish versions. Technicians save additional answers and explicit panel scope and see saved-data readiness. Unsaved edits remain private; conflicting saves and changed source definitions require review. The feature remains disabled by default (`INSPECTIONS_PDF_INTEGRATIONS_ENABLED=true` opts in); both integrations require published configuration and explicit enablement. Linux resource limits and Poppler (`pdftoppm`) are required for admin previews. See the [P4](docs/PDF_INTEGRATION_P4_REPORT.md), [P5](docs/PDF_INTEGRATION_P5_REPORT.md) and [P6](docs/PDF_INTEGRATION_P6_REPORT.md) reports. The preview/download lifecycle is implemented; new export actions remain unavailable until an integration is configured, verified, published and enabled. Existing exports remain independent.

The PDF export lifecycle now supports saved-data previews, stale-proof rejection, confirmed immutable finals, idempotent retries, history and pending-file recovery. Reference-form candidates remain unpublished and disabled until the administrator establishes defaults and verifies/publishes them. See the [operating guide](docs/PDF_INTEGRATIONS_OPERATIONS.md) and [P7](docs/PDF_INTEGRATION_P7_REPORT.md)/[P8](docs/PDF_INTEGRATION_P8_REPORT.md) reports. The temporary HTTP deployment supports secure UUID generation without requiring HTTPS-only browser APIs.

Deployment evidence and remaining user-owned setup/print gates are recorded in the [P9 verification report](docs/PDF_INTEGRATION_P9_REPORT.md) and [P10 rollout report](docs/PDF_INTEGRATION_P10_REPORT.md). Both supplied forms are installed as disabled drafts; production defaults and business approval remain yours to establish.
