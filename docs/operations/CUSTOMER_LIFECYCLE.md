# Customer Lifecycle

English is canonical. The Japanese mirror is [CUSTOMER_LIFECYCLE_JA.md](CUSTOMER_LIFECYCLE_JA.md).

This chapter is the public model for one deployment environment. The deploy path itself is [Community Deployment Guide](../COMMUNITY_DEPLOYMENT_GUIDE.md). This chapter does not add a required fact.

## 1. One environment

One environment is one private caller repository generated from `SignalNexus/signal-nexus-deploy`. That repository owns one pin, one recommended SHA, one Linux host, one Render Web Service, and one empty venue manifest until a venue is purchased.

The public core stays in `SignalNexus/signal-nexus`. The caller repository does not fork the core.

## 2. One pin

These three fields are the same 40-character public SHA:

| Name | Where |
| --- | --- |
| `core-pin` | File at the root of the caller repository |
| `uses` | `.github/workflows/deploy.yml` |
| `core_sha` | The same workflow |

The pin job stops when they differ. A newer core is written in all three places. The minimum SHA is the value in the Community Deployment Guide.

## 3. One recommended SHA

The recommended SHA is the public core SHA of the last successful deploy for that environment. The first successful deploy sets it. Each later successful deploy replaces it. A failed deploy does not replace it and does not clear the previous value.

Another caller repository is a different record. Do not copy that pin or that recommended SHA into this environment.

## 4. Empty manifest until a purchase

`venueadd/venues.yaml` stays `venues: []` until a venue is purchased. An empty list loads no VenueAdd package and does not require `VENUEADD_READ_TOKEN`.

`config/venues.yml` is the runtime catalog. It is not the purchase list. Enabling a built-in venue in the catalog is a `BUILTIN_VENUES` decision, not a VenueAdd purchase.

## 5. What this chapter does not do

This chapter does not create a repository, a host, or a Render service. Those procedures are [Customer Creation](CUSTOMER_CREATION.md), [Infrastructure Execution](INFRASTRUCTURE_EXECUTION.md), and [Launch Gate](LAUNCH_GATE.md).
