# Customer Creation

English is canonical. The Japanese mirror is [CUSTOMER_CREATION_JA.md](CUSTOMER_CREATION_JA.md).

This chapter is the public procedure for creating a caller repository and the seven runtime files. The authority for names, commands, and success is [Community Deployment Guide](../COMMUNITY_DEPLOYMENT_GUIDE.md). This chapter does not add a required fact.

## 1. Generate the caller repository

1. Use GitHub to generate a new private repository from the template `SignalNexus/signal-nexus-deploy`.
2. Do not fork the template. Do not push onto the template.
3. Confirm `core-pin`, `uses`, and `core_sha` are the same public SHA, at least the minimum in the guide.
4. Confirm `venueadd/venues.yaml` is `venues: []`.
5. Confirm `render-build.sh` is present.

The owner of this repository is the operator of this environment.

## 2. Place the seven runtime files

Copy each example to the live name. Commit the live files before the first `workflow_dispatch`.

| Example | Live file |
| --- | --- |
| `config/examples/locale.yml.example` | `config/locale.yml` |
| `config/examples/month_target.yml.example` | `config/month_target.yml` |
| `config/examples/ops_schedule.yml.example` | `config/ops_schedule.yml` |
| `config/examples/protective_exit.yml.example` | `config/protective_exit.yml` |
| `config/examples/strategies.yml.example` | `config/strategies.yml` |
| `config/examples/strategy_results.yml.example` | `config/strategy_results.yml` |
| `config/examples/venues.yml.example` | `config/venues.yml` |

All seven must exist and be non-empty. `{}` is rejected. `confirm` validates them. The sample registry may be committed unchanged.

`venueadd/venues.yaml` is not one of the seven. Leave it `venues: []`.

## 3. What waits

Do not set `VENUEADD_READ_TOKEN`. Do not add a VenueAdd row. Do not set MEXC or Arcus secrets unless `BUILTIN_VENUES` will name those venues.

The nine secrets and five variables wait for [Infrastructure Execution](INFRASTRUCTURE_EXECUTION.md). `DEPLOY_ANALYTICS` stays unset until that chapter sets it, immediately before the first dispatch.

## 4. Ready for infrastructure

Creation is complete when the caller repository exists, the three SHA fields match, the seven live files are committed, `venues: []` is unchanged, and `confirm` would accept the seven files.

The host and the Render Web Service are the next chapter.
