# Decision Log

## 2026 09 18 Separate application

The inspection processor will be a new application and repository. The existing Work_Order project remains untouched.

## 2026 09 18 Deterministic first release

The first release will not require an AI API key. File parsing, validation, matching, and export will be deterministic and auditable.

## 2026 09 18 Optional AI boundary

AI will be added later through a provider interface for suggestions and exception assistance only. It will not be part of the authoritative data-processing path.

## 2026 09 18 Separate deployment resources

The new application will use separate service names, secrets, storage, database access, and deployment configuration on the same DigitalOcean server.

## 2026 09 18 Multiple panel point lists

An inspection may contain multiple Points Lists, one per security panel. Each list is categorized as Fire, Burglar, Combo, or Gas Station and is immutable after acceptance.

## 2026 09 18 Incremental event history

Event History uploads are cumulative. Successful point-to-time mappings are retained across uploads until all mappings are complete.

## 2026 09 18 Gated PDF export

The final PDF is not created until all results and mappings are complete. The filename includes store, city, state, category, and inspection date.
