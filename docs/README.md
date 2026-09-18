# Alarm Inspection Processing Application

This repository will contain a separate online application for preparing alarm inspection reports from Points List and Event History files.

## Product goal

Make the inspection workflow simple and repeatable:

1. Enter inspection metadata.
2. Upload a Points List in XLS, XLSX, or PDF format.
3. Review the normalized initiating devices.
4. Upload the Event History report after field testing.
5. Review exceptions and unmatched points.
6. Export the completed inspection report.

The application must produce the same result from the same inputs without requiring an AI API. AI support is deferred and must remain optional.

## Repository boundaries

This is a new application. It must not import code, deployment files, environment variables, databases, or storage from the existing Work_Order application. The existing application is located at `C:\Users\User\Documents\code\python\sbc\Work_Order` and is out of scope for modification.

## Current status

The initial work is planning and architecture. Implement the deterministic processing engine before adding any AI capability.

## Important documents

- [Product requirements](PRODUCT_REQUIREMENTS.md)
- [Architecture](ARCHITECTURE.md)
- [Processing rules](PROCESSING_RULES.md)
- [Implementation roadmap](ROADMAP.md)
- [AI engineering guide](AI_ENGINEERING_GUIDE.md)
- [Deployment isolation plan](DEPLOYMENT.md)
- [Decision log](DECISIONS.md)

