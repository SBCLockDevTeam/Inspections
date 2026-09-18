# Decision Log

## 2026 09 18 Separate application

The inspection processor will be a new application and repository. The existing Work_Order project remains untouched.

## 2026 09 18 Deterministic first release

The first release will not require an AI API key. File parsing, validation, matching, and export will be deterministic and auditable.

## 2026 09 18 Optional AI boundary

AI will be added later through a provider interface for suggestions and exception assistance only. It will not be part of the authoritative data-processing path.

## 2026 09 18 Separate deployment resources

The new application will use separate service names, secrets, storage, database access, and deployment configuration on the same DigitalOcean server.

