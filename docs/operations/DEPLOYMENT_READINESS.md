# Deployment Readiness

English is canonical. The Japanese mirror is [DEPLOYMENT_READINESS_JA.md](DEPLOYMENT_READINESS_JA.md).

This chapter is the public checklist immediately before `workflow_dispatch`, and the success checks after it. The authority is [Community Deployment Guide](../COMMUNITY_DEPLOYMENT_GUIDE.md) sections 8 through 12. This chapter does not add a required fact.

## 1. Before the first dispatch

Every row must be true.

| Check | Required |
| --- | --- |
| Three SHA fields | Equal. At least the minimum SHA in the guide |
| Seven live runtime files | Present, non-empty, accepted by `confirm` |
| Manifest | `venues: []` |
| Linux host | `ubuntu`, `sudo -n`, TCP 22 and 443 |
| Render | Live. `GET /health` is `{"status":"ok"}` |
| Nine secrets | Set on this caller repository |
| Four path and venue variables | Set. `BUILTIN_VENUES` decided |
| `DEPLOY_ANALYTICS` | Set to `true` last |
| `VENUEADD_READ_TOKEN` | Unset while the manifest is empty |
| Extra venue secrets | Only if `BUILTIN_VENUES` names those venues |

`none` and the empty string are an empty built-in set. Futures read runs only when `BUILTIN_VENUES` contains `mexc_futures`.

## 2. First dispatch

On GitHub, open Actions, open the workflow named `deploy`, and run it once with `workflow_dispatch`.

The deploy installs PostgreSQL when it is missing, creates `signalnexus`, copies the seven files, and restarts the Analytics API. With `venues: []` it does not fetch a venue repository.

## 3. Success

The deploy is successful only when every item below is met.

| Check | Expected |
| --- | --- |
| Render `GET /health` | `{"status":"ok"}` |
| Analytics `GET https://<CADDY_SITE_ADDRESS>/health` | `{"status":"ok"}` |
| Seven config SHA256 values | The caller files, the deploy log, and the copies under `ANALYTICS_CORE_DIRECTORY/config/` match |
| `SIGNAL_NEXUS_VENUEADD` | Unset while the manifest is empty |
| Venue fetch | The log does not name a venue repository |
| Futures read | With `BUILTIN_VENUES=none`, the log does not contain `futures read credentials are not configured` |

Compute the hashes with `sha256sum` on the seven live paths.

A deploy that passes every check in this section is a successful deploy. That public core SHA becomes the recommended SHA for this environment.

## 4. Later deploys

Run the same workflow when the seven files, the three SHA fields, or the Render environment variables change. `DEPLOY_ANALYTICS` stays `true`. Render `GET /health` is still `{"status":"ok"}` before you start. Repeat section 3. A later success replaces the recommended SHA. A failure does not.

A failure is [Rollback](ROLLBACK.md).
