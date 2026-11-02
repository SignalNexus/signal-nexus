# Troubleshooting

English is canonical. The Japanese mirror is [TROUBLESHOOTING_JA.md](TROUBLESHOOTING_JA.md).

These notes cover failures the [Community Deployment Guide](../COMMUNITY_DEPLOYMENT_GUIDE.md) path can hit. They do not add a required fact. Console recovery steps stay in the Buildbook.

## 1. Futures read on `none`

`BUILTIN_VENUES=none` does not run `deploy.futures_read`. The log must not contain `futures read credentials are not configured`.

If that line appears, the pin is older than the futures-read condition, or `BUILTIN_VENUES` contains `mexc_futures`. Write the minimum SHA from the guide in all three SHA fields, or add the futures read pair, then run deploy once.

## 2. Missing or empty runtime files

The deploy stops when any of the seven live files is missing or empty. `{}` is rejected. Copy each example to `config/<name>` and commit. Run `confirm` before `workflow_dispatch`.

## 3. Pin mismatch

The pin job stops when `core-pin`, `uses`, and `core_sha` differ. Write the same public SHA in all three places.

## 4. Render health before dispatch

Do not start `workflow_dispatch` while Render `GET /health` is not `{"status":"ok"}`. The Web Service must be Live, on this caller repository's `main`, with the build and start commands from the guide.

A configured secret shorter than 24 characters stops the process.

## 5. Runner Git credentials

A venue fetch on the GitHub-hosted runner uses a credential helper. The username is `x-access-token`. Helpers that were set for another host are cleared before the fetch. A token stored as `VENUEADD_READ_TOKEN` is the password.

An empty manifest returns before git. Do not set the token to debug a first deploy that still has `venues: []`.

## 6. Failed venue fetch

A row whose repository the token cannot read fails `venueadd-install`. The Analytics API is not restarted. The installed tree stays as it was.

Fix the token or the row, then run deploy once. Do not restart the service by hand to force a half-applied tree.

## 7. `DEPLOY_ANALYTICS` still false

The workflow does not deploy the host while `DEPLOY_ANALYTICS` is unset or `false`. Set the nine secrets first. Set `DEPLOY_ANALYTICS=true` last, immediately before the one dispatch.
