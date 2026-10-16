# Documentation ↔ Code Audit

Audit date: 2026-10-16. English is the canonical text. The Japanese edition is [DOCUMENTATION_CODE_AUDIT_JA.md](DOCUMENTATION_CODE_AUDIT_JA.md).

This file records where the six canonical documents differ from the repository. It does not change those documents. The repository README was not part of the audit.

Runtime checked here: `GET https://signal-nexus.onrender.com/health` returned `{"status":"ok"}`. The virtual machine, Discord delivery, and a live webhook were not called.

## Summary

### Matches

Architecture. The split is in the code. Render runs `app.main` (`POST /webhook`, `GET /health`, portal). The Analytics API on the VM exposes `GET /health` and the order routes. Postgres is opened from that API. GitHub Actions workflow `analytics-vm` copies the repo onto the VM. MEXC and Arcus are order paths. Live orders are handed from Render to that API.

Buildbook. The public clone URL, Render build and start commands, the workflow file name, the secret names that workflow reads, `config/strategies.yml` fields, and `POST /webhook` returning `{"status":"dry_run"}` for one venue match the code.

Strategy Integration Guide. `strategy_id`, `symbol`, `action`, `client_order_id`, and `WEBHOOK_SECRET` match `WebhookPayload` and `route()`. `size` and `size_quote` in the body are HTTP 422. A wrong secret is HTTP 401. Unset `EXECUTION_MODE` is `dry_run` and does not send the order. The action table matches `_accepts`.

Screen Specification. Dashboard, Trading, Analytics, and Operations exist. The blocks, columns, and the six Audit Log labels match `portal_pages.py`. Planned orders are stored and are not one of those labels.

Screen Relationship Diagram. ✅ The only cross-view links in the portal are Dashboard → Trading Positions, Dashboard → Analytics Strategies, and Dashboard → Operations Schedule.

Product Specification. The portal does not place an order. `dry_run` does not send an order. An audit trail is written when the Analytics API is configured. The Analytics screen is a view, not the stored record.

### Divergences

#### 1. Discord copies are not sent

Status. Resolved. `_DISCORD_POSTS_ENABLED` is `True`. The decision is in [CORRECTION_DECISIONS.md](CORRECTION_DECISIONS.md). A wait longer than one minute still stops further posts in that process and records `429 paused`.

| | |
| --- | --- |
| Item | Discord audit delivery |
| Documents | Architecture, Buildbook completion item, Product Specification |
| Implementation | `app/notifications/discord.py` sets `_DISCORD_POSTS_ENABLED = True`. When `DISCORD_WEBHOOK_URL` is set, `discord_copy` posts the audit copy. |
| Difference | None for ordinary delivery. A Discord 429 whose `retry_after` exceeds 60 seconds pauses later posts in that process. |
| Impact | A reader who sets the webhook receives the audit copy, unless Discord has paused that process. |
| Proposed correction | Done. |

#### 2. Actions has gates the Buildbook does not list

| | |
| --- | --- |
| Item | When `analytics-vm` fails |
| Document | Buildbook, chapter 5, "Deploy the machine" |
| Implementation | After the copy, `.github/workflows/analytics-vm.yml` waits until the importer log contains `arcus fills `, then runs `deploy.confirm_arcus_leverage` and `deploy.confirm_mexc_env`. |
| Difference | The book says the job stops when a secret is missing, the host key does not match, or Render health is not ok. The fills wait can fail the run after those three have passed. `confirm_arcus_leverage` prints an HTTP error and still exits 0, so a leverage rejection does not by itself fail the job. |
| Impact | Major. A red Actions run can look like a secret or health failure when the importer has not logged yet. |
| Proposed correction | Name the fills wait as a stop condition. Say the leverage command reports status and does not fail the job by itself. |

#### 3. A repeated `client_order_id` is not a 422

| | |
| --- | --- |
| Item | Duplicate alert |
| Document | Strategy Integration Guide, sections 3 and 5 |
| Implementation | `receive_webhook` returns HTTP 200 and `{"status":"duplicate"}` when the id was already claimed. HTTP 422 is validation. HTTP 401 is the secret. |
| Difference | The guide says a repeat is discarded, which is true, and that a rejected alert is HTTP 422. A duplicate is discarded with a different status. |
| Impact | Minor. A reader can treat a duplicate as a validation error. |
| Proposed correction | State that a repeated id returns `{"status":"duplicate"}` and does not send an order. |

#### 4. The portal has a login in front of the four views

| | |
| --- | --- |
| Item | Portal entry |
| Documents | Screen Specification, Screen Relationship Diagram |
| Implementation | `PORTAL_PASSWORD` empty makes `_session_ok` false. `/portal`, `/portal/trading`, `/portal/analytics`, and `/portal/operations` render a login page until the password matches. |
| Difference | The four views and the tree are real after login. The documents do not show the login page. |
| Impact | Minor. The views match. The first screen a reader opens is the login, which is not in the tree. |
| Proposed correction | Add the login as a gate in front of Portal, not as a fifth primary view. The password itself stays a Buildbook setting. |

#### 5. Some Dashboard words on the page are Japanese

| | |
| --- | --- |
| Item | Dashboard field names |
| Document | Screen Specification, Dashboard |
| Implementation | Eyebrows are English (`Today`, `Risk Summary`, `PnL`). Several values are labeled in Japanese, including `実績（USD）`, `月目標`, `達成率`, `残必要額`, `月末着地予測`. |
| Difference | The English specification describes the same facts in English. The page does not use those English phrases. |
| Impact | Minor. The information is there. A reader looking for the English phrase will not see it as a heading. |
| Proposed correction | Say that those value labels are shown in Japanese on the page. |

#### 6. The operational record is stored only when the API is configured

| | |
| --- | --- |
| Item | Operational record and audit trail |
| Document | Product Specification |
| Implementation | `append_audit` returns without posting when `ANALYTICS_API_URL` or `ANALYTICS_API_SECRET` is empty. The webhook still answers `dry_run`. |
| Difference | The product text says the record and the trail are kept. That is true after the Buildbook connects Render to the VM. It is not true for a webhook that has only `WEBHOOK_SECRET`. |
| Impact | Minor. The documented build sets both variables. A reader of the product text alone can think every accepted alert is stored. |
| Proposed correction | Say the record is kept when the VM connection is configured. |

## What was not found

No deleted secret name appears in the Buildbook appendix. `analytics-vm.yml` exists. `GET /health` on Render exists and, on the checked host, returns `{"status":"ok"}`. The sample strategy row `btc_long_example` is accepted by the registry shape the guide describes. Hyperliquid, Paradex, and GRVT are not enabled order paths in the venue loader's enabled set used at runtime.
