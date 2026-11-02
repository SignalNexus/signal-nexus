# Signal Nexus Operations Manual

English is canonical. The Japanese mirror is [OPERATIONS_MANUAL_JA.md](OPERATIONS_MANUAL_JA.md).

This file is the binder for the thirteen chapters. It does not replace [Community Deployment Guide](COMMUNITY_DEPLOYMENT_GUIDE.md). The guide is the public authority for the path through health validation.

README is the first document. [Documentation Structure](DOCUMENTATION_STRUCTURE.md) is the index of roles.

## Chapters

| Chapter | Document | Responsibility |
| --- | --- | --- |
| 01 Product Operations | [README](../README.md), [Product Specification](product/PRODUCT_SPECIFICATION.md), [Product Catalog](product/PRODUCT_CATALOG.md), [Screen Specification](ui/SCREEN_SPECIFICATION.md), [Screen Relationship Diagram](ui/SCREEN_RELATIONSHIP_DIAGRAM.md), [Strategy Integration Guide](integration/STRATEGY_INTEGRATION_GUIDE.md) | Product, screens, TradingView, daily operation after the system meets the success checks |
| 02 Customer Lifecycle | [Customer Lifecycle](operations/CUSTOMER_LIFECYCLE.md) | One caller repository, one pin, one recommended SHA, empty manifest until a purchase |
| 03 Customer Bootstrap | [Customer Creation](operations/CUSTOMER_CREATION.md) | Template, seven runtime files, `confirm`, `venues: []` |
| 04 Infrastructure Provisioning | [Infrastructure Execution](operations/INFRASTRUCTURE_EXECUTION.md) | Linux host, local PostgreSQL 16, Render Web Service, nine secrets, five variables |
| 05 Deployment | [Deployment Readiness](operations/DEPLOYMENT_READINESS.md) | One `workflow_dispatch`, health, seven SHA256 values |
| 06 Venue Operations | [Venue License](operations/VENUE_LICENSE.md), [AddVenue Operations](operations/ADDVENUE_OPERATIONS.md) | License, repository access, fetch. Lighter is a worked case, not a required install |
| 07 Release Management | [Release Management](operations/RELEASE_MANAGEMENT.md), [Launch Gate](operations/LAUNCH_GATE.md) | Release gate, export, recommended SHA |
| 08 Troubleshooting | [Troubleshooting](operations/TROUBLESHOOTING.md) | Failures the guide's path can hit |
| 09 Rollback | [Rollback](operations/ROLLBACK.md) | That caller repository only |
| 10 Architecture Reference | [Architecture](architecture/ARCHITECTURE.md), [AddVenue deployment](architecture/ADDVENUE_DEPLOY.md) | Public core, caller repository, VenueAdd |
| 11 Starter Package | Buildbook, included with Starter | Detail, checklist, FAQ, screens, failure notes. No required fact the guide does not state |
| 12 AddVenue Package | Per-venue LICENSE, README, SETUP, RELEASE_NOTES, plus [AddVenue Operations](operations/ADDVENUE_OPERATIONS.md) | One purchased venue |
| 13 Historical Decisions | `business/consideration/design/` | Reviews and customer evidence. Internal. Not exported |

Chapters 03, 04, 05, 07, and 09 state no requirement the guide lacks.

## Deploy reading path

```text
README
  |
  v
COMMUNITY_DEPLOYMENT_GUIDE
  |
  +-- Architecture
  +-- Operations chapters 02 through 09, when a later procedure is needed
  +-- Buildbook, optional
```
