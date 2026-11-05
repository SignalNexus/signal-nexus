# Community Deployment Guide

English is canonical. The Japanese mirror is [COMMUNITY_DEPLOYMENT_GUIDE_JA.md](COMMUNITY_DEPLOYMENT_GUIDE_JA.md).

This guide is the public authority for deploying Signal Nexus Community Edition through health validation. It is for a reader who already knows the basic operations of GitHub Actions, SSH, Linux, and Render. That reader uses only the published information in `SignalNexus/signal-nexus` and `SignalNexus/signal-nexus-deploy`.

Required:

- [README](../README.md)
- This guide
- `SignalNexus/signal-nexus-deploy`

Reference, the implementation itself:

- `SignalNexus/signal-nexus`

Optional reading:

- [Architecture](architecture/ARCHITECTURE.md). It confirms the system layout. It is not required to reach health validation.
- The Buildbook, included with Starter. It adds detail, checklists, screens, FAQ, and failure notes. It does not add a required fact.

## Quick path

In this guide, the private repository you generate from `SignalNexus/signal-nexus-deploy` is the caller repository. Do the work in this order. Each step links to the section that has the detail.

1. Create the caller repository from the template. [Section 2](#2-deploy-repository).
2. Place the seven runtime files by copying the samples. [Section 3](#3-required-runtime-files).
3. Create the Render Web Service that receives webhooks. [Sections 4](#4-infrastructure-minimum) and [5](#5-build-and-start).
4. Prepare the Linux host. [Section 4](#4-infrastructure-minimum).
5. Set the secrets and the variables. [Sections 6](#6-required-secrets), [7](#7-required-variables), and [8](#8-builtin_venues).
6. Start the GitHub Actions workflow named `deploy` with `workflow_dispatch`. [Section 9](#9-initial-deploy).
7. Check health. [Section 10](#10-success).

A later change uses the same workflow. [Section 11](#11-ongoing-deployments).

## 1. Deployment architecture

```text
TradingView alert
        |
        v
Render Webhook Service
        |
        | ANALYTICS_API_URL
        v
Analytics API on the Linux host
        |
        v
PostgreSQL on localhost

VenueAdd packages load beside the Analytics API only when the manifest names them.
An empty manifest loads none.
```

The webhook receives alerts. The Analytics API stores the operational record. PostgreSQL persists it. VenueAdd stays outside this public core.

The reference webhook host is a Render Web Service. The reference machine is a Linux VM. Signal Nexus is not those two products. The automation requires GitHub Actions, SSH as `ubuntu`, Caddy on TCP 443, PostgreSQL on localhost, and `RENDER_HEALTH_URL`.

## 2. Deploy repository

This guide calls the private repository you generate from `SignalNexus/signal-nexus-deploy` the caller repository. It is yours. The core source stays in `SignalNexus/signal-nexus`. The caller repository does not fork the core.

These three are the same 40-character public SHA:

| Name | Where |
| --- | --- |
| `core-pin` | File at the root of the caller repository |
| `uses` | `.github/workflows/deploy.yml` |
| `core_sha` | The same workflow |

The pin job stops when they differ. A newer core is written in all three places.

The minimum SHA is `7b6d8c0a03a6ec1510fa7f786a13ed2e39803523`. That commit runs `deploy.futures_read` only when `BUILTIN_VENUES` contains `mexc_futures`. Replace it when a newer public core still contains that gate.

## 3. Required runtime files

Copy each example to the live name before the first deploy. You may edit the values. You do not have to change every field. The sample content can be deployed as it is. What is required is that the seven files exist and pass `confirm`. All seven must be non-empty. `{}` is rejected.

| Example | Live file |
| --- | --- |
| `config/examples/locale.yml.example` | `config/locale.yml` |
| `config/examples/month_target.yml.example` | `config/month_target.yml` |
| `config/examples/ops_schedule.yml.example` | `config/ops_schedule.yml` |
| `config/examples/protective_exit.yml.example` | `config/protective_exit.yml` |
| `config/examples/strategies.yml.example` | `config/strategies.yml` |
| `config/examples/strategy_results.yml.example` | `config/strategy_results.yml` |
| `config/examples/venues.yml.example` | `config/venues.yml` |

`locale.yml` is the portal language and clock. `month_target.yml` is the month target. `ops_schedule.yml` is the operating schedule. `protective_exit.yml` is the protective-exit map. `strategies.yml` is the registry. `strategy_results.yml` holds result labels. `venues.yml` is the runtime catalog. A venue with `enabled: false` stays out of the enabled set.

`venueadd/venues.yaml` is not one of the seven. Leave it as `venues: []` until a venue is purchased.

`confirm` validates the runtime files. If that check fails, the deploy does not continue. The example registry passes that check when copied unchanged:

```yaml
example-btc-spot:
  symbol: BTC/USDT
  side: long
  venue: mexc_spot
  size_quote: 10
```

`mexc_spot` is enabled in the example catalog because a strategy venue must be an enabled row. `mexc_futures` and `arcus` are present and disabled.

## 4. Infrastructure minimum

| Piece | Minimum |
| --- | --- |
| Linux host | Canonical Ubuntu 24.04. User `ubuntu`. `sudo -n` succeeds. Home `/home/ubuntu` |
| Ingress | TCP 22 reachable by GitHub-hosted runners. TCP 443 from the internet. TCP 5432 closed. TCP 80 closed. Caddy uses TLS-ALPN |
| PostgreSQL | The first deploy creates role `signalnexus` and database `signalnexus`. The deploy installs the Ubuntu 24.04 package, PostgreSQL 16. It listens on localhost. `pg_hba.conf` allows `127.0.0.1/32` with `scram-sha-256` or `md5` |
| Render | A Web Service on the caller repository, branch `main`. It receives webhooks. It is Live, and `GET /health` returns `{"status":"ok"}`, before you start the deploy workflow |
| Site | `CADDY_SITE_ADDRESS` is `<public-ip>.sslip.io`, the hostname only. `RENDER_HEALTH_URL` is `https://<render-host>/health`. `ANALYTICS_API_URL` on Render is `https://` plus the site address |
| Fingerprint | The Actions secret is the `SHA256:` field from `ssh-keygen -lf` on the ed25519 host key. The private key has no passphrase |

In Render, create a Web Service connected to the caller repository's `main` branch. It receives the webhooks. Use the build and start commands in section 5.

`VM.Standard.E2.1.Micro` in Oracle `ap-tokyo-1` is the reference shape. It is not the only host that can run the software. The console clicks are in the Buildbook.

`workflow_dispatch` is how you start the GitHub Actions workflow named `deploy` on the caller repository. You open that workflow and run it. No screenshot is required. Section 9 is the first run. Section 11 is every later run.

## 5. Build and start

These commands are the authority for the caller repository:

| | Command |
| --- | --- |
| Build | `bash render-build.sh && pip install -r .core/requirements.txt` |
| Start | `cd .core && uvicorn app.main:app --host 0.0.0.0 --port $PORT` |

Set these as the Build Command and the Start Command of the Render Web Service.

`render-build.sh` reads `core-pin`, fetches that commit of `SignalNexus/signal-nexus` into `.core/`, copies the seven live files into `.core/config/`, and prints one sha256 line per file. The workflow reads those lines from the build log.

Render environment before the first deploy:

| Name | Value |
| --- | --- |
| `ANALYTICS_API_URL` | `https://<public-ip>.sslip.io` |
| `ANALYTICS_API_SECRET` | At least 24 characters. The same value is stored on GitHub |
| `EXECUTION_MODE` | `dry_run` |
| `KILL_SWITCH` | `false` |

`WEBHOOK_SECRET`, `PORTAL_PASSWORD`, and `DISCORD_WEBHOOK_URL` may wait. A configured secret shorter than 24 characters stops the process.

## 6. Required secrets

Set these as GitHub repository secrets on the caller repository. They are required before the first `workflow_dispatch`:

| Secret | Meaning |
| --- | --- |
| `ANALYTICS_SSH_HOST` | Public IPv4 of the Linux host |
| `ANALYTICS_SSH_PRIVATE_KEY` | The key file, from `BEGIN` through `END` |
| `ANALYTICS_SSH_HOST_FINGERPRINT` | The `SHA256:` field |
| `ANALYTICS_API_SECRET` | Shared with Render |
| `ANALYTICS_DB_PASSWORD` | Password of role `signalnexus`. It is not stored on Render |
| `RENDER_HEALTH_URL` | `https://<render-host>/health` |
| `CADDY_SITE_ADDRESS` | Hostname only |
| `RENDER_DEPLOY_HOOK` | The Deploy Hook URL of the Render Web Service. The path ends in `srv-...` |
| `RENDER_API_KEY` | A key that can read that service, its deploys, and its build log |

Set later:

| Secret | When |
| --- | --- |
| `VENUEADD_READ_TOKEN` | The manifest gains a row. `venues: []` returns before git |
| `ANALYTICS_MEXC_API_KEY`, `ANALYTICS_MEXC_API_SECRET` | `BUILTIN_VENUES` contains `mexc_spot` |
| `ANALYTICS_MEXC_FUTURES_API_KEY`, `ANALYTICS_MEXC_FUTURES_API_SECRET` | `BUILTIN_VENUES` contains `mexc_futures` |
| Arcus address and signing names | `BUILTIN_VENUES` contains `arcus` |
| `KILL_SWITCH` | Only to set the flag true. An absent value stays false |
| Order keys `MEXC_API_*` and `MEXC_FUTURES_API_*` | When you change `EXECUTION_MODE` to `live`. Until then the mode is `dry_run` and orders are not sent. Not the first health check |

Names without values are listed in the template file `deploy/target.env.example`.

## 7. Required variables

Set these as GitHub repository variables on the caller repository.

| Variable | Value |
| --- | --- |
| `ANALYTICS_SSH_USER` | `ubuntu` |
| `ANALYTICS_CORE_DIRECTORY` | `/home/ubuntu/signal-nexus` |
| `ANALYTICS_VENUE_DIRECTORY` | `/opt/signal-nexus/venueadd` |
| `BUILTIN_VENUES` | `none`, or the built-in set this deployment runs |
| `DEPLOY_ANALYTICS` | `true`, after the nine secrets and immediately before the one dispatch |

## 8. BUILTIN_VENUES

`none` and the empty string are an empty set. The futures read and the extra secrets follow membership.

| Value | Whether futures read runs | Additional secrets |
| --- | --- | --- |
| `none` | Does not run | None |
| `mexc_spot` | Does not run | The MEXC spot read pair |
| `mexc_futures` | Runs | The MEXC futures read pair. A missing name stops the deploy |
| `arcus` | Does not run | The Arcus address |
| A comma-separated set | Runs only when `mexc_futures` is a member | The union of the selected rows |

Whether the MEXC spot API keys are required is decided by `BUILTIN_VENUES`, not by `strategies.yml`. The example registry can be deployed with `BUILTIN_VENUES=none`.

## 9. Initial deploy

1. Pin the three SHA fields to the same public commit, at least the minimum in section 2.
2. Copy the seven examples to `config/`. You do not have to edit every field. Commit them with `venues: []` and `render-build.sh`.
3. Create the Linux host and record the fingerprint.
4. In Render, create a Web Service connected to the caller repository's `main` branch. Use the commands in section 5. Wait until `GET /health` is `{"status":"ok"}`.
5. Store the nine secrets, then the five variables. `DEPLOY_ANALYTICS=true` is last.
6. On GitHub, open Actions, open the workflow named `deploy`, and run it once with `workflow_dispatch`.

The deploy installs PostgreSQL when it is missing, creates `signalnexus`, copies the seven files, and restarts the Analytics API. With `venues: []` it does not fetch a venue repository.

When the workflow finishes, carry out the checks in section 10.

## 10. Success

This deploy is successful only when every item below is met.

| Check | Expected |
| --- | --- |
| Render `GET /health` | `{"status":"ok"}` |
| Analytics `GET https://<CADDY_SITE_ADDRESS>/health` | `{"status":"ok"}` |
| Seven config SHA256 values | The caller's files, the deploy log, and the copies under `ANALYTICS_CORE_DIRECTORY/config/` match |
| `SIGNAL_NEXUS_VENUEADD` | Unset while the manifest is empty |
| Venue fetch | The log does not name a venue repository |
| Futures read | With `BUILTIN_VENUES=none`, the log does not contain `futures read credentials are not configured` |

Compute the hashes with `sha256sum` on the seven live paths.

A deploy that passes every check in this section is a successful deploy. The most recent successful deploy for that environment is the last successful deploy.

## 11. Ongoing deployments

Run the deploy workflow again when you change any of the following:

- the seven runtime files
- `core-pin`
- `uses`
- `core_sha`
- Render environment variables

The first deploy is in section 9. After that, the same workflow deploys a change.

1. Update the seven live runtime files, or write a new public SHA in `core-pin`, `uses`, and `core_sha`, or change the Render environment variables. A new SHA still has to contain the futures-read gate from section 2. The three SHA fields stay equal.
2. The Render service is already Live. `GET /health` still returns `{"status":"ok"}` before you start.
3. Run the GitHub Actions workflow named `deploy` once with `workflow_dispatch`. `DEPLOY_ANALYTICS` stays `true`.
4. Repeat the checks in section 10.
5. When those checks pass, the recommended SHA for this environment becomes the public core SHA this deploy used.

## 12. Recommended SHA

The recommended SHA is the public core SHA of the last successful deploy for that environment. The first successful deploy sets it. Each later successful deploy replaces it. A failed deploy does not replace it, and it does not clear the previous value. Another caller's pin is a different record.

Do not read the first success as the only SHA that can be recommended.

## 13. Rollback

A failure of the checks in section 10 is a rollback. The rollback changes that caller's repository, that caller's host, and that caller's Render service.

On a failed first deploy, set `DEPLOY_ANALYTICS` to false on that repository. Leave `venues: []` and the pin in place. A retry uses a new SSH key and a new database password. The workflow rolls the Render service back to the deploy that was live before the hook.

If a deploy after an update fails, return to the last successful deploy. The workflow rolls the Render service back to the deploy that was live before that run. This rollback applies to later deploys as well as to the first deploy.

Do not edit another caller's repository as part of this rollback.

## 14. Starter

| Item | This guide | Buildbook |
| --- | --- | --- |
| Authority for this path | Yes | Follows this guide |
| Requirements and commands | Yes. The short form | Detailed explanation |
| Checklist | — | Yes |
| FAQ | — | Yes |
| Failure notes | — | Yes |
| Registry | One minimal registry | Commented examples |
| Success criteria | Yes. The checks in section 10 | A filled run |
| Rollback | Yes. One section | Failure notes |

Starter adds verification, detail, checklists, screens, FAQ, and failure notes. It does not add a required fact.
