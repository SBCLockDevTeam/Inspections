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
