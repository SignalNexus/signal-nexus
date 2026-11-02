# Infrastructure Execution

English is canonical. The Japanese mirror is [INFRASTRUCTURE_EXECUTION_JA.md](INFRASTRUCTURE_EXECUTION_JA.md).

This chapter is the public procedure for the Linux host, PostgreSQL, the Render Web Service, the nine secrets, and the five variables. The authority for minima and names is [Community Deployment Guide](../COMMUNITY_DEPLOYMENT_GUIDE.md) sections 4 through 7. This chapter does not add a required fact. It does not start `workflow_dispatch`.

## 1. Linux host

Create one Linux host for this caller repository only.

| Piece | Minimum |
| --- | --- |
| Image | Canonical Ubuntu 24.04 |
| User | `ubuntu`, home `/home/ubuntu`, `sudo -n` succeeds |
| Ingress | TCP 22 reachable by GitHub-hosted runners. TCP 443 from the internet. TCP 5432 closed. TCP 80 closed |
| TLS | Caddy with TLS-ALPN |
| Fingerprint | The Actions secret is the `SHA256:` field from `ssh-keygen -lf` on the ed25519 host key |
| SSH key | ed25519, no passphrase |

`VM.Standard.E2.1.Micro` in Oracle `ap-tokyo-1` is the example shape. It is not the only host that can run the software.

Do not copy environment files from another host. Do not restore another environment's database dump.

## 2. PostgreSQL

The first deploy installs PostgreSQL 16 when it is missing, creates role `signalnexus` and database `signalnexus`, and listens on localhost. `pg_hba.conf` allows `127.0.0.1/32` with `scram-sha-256` or `md5`.

The password is this environment's `ANALYTICS_DB_PASSWORD`. It is not stored on Render.

## 3. Render Web Service

Create one Web Service connected to this caller repository's `main` branch.

| Setting | Value |
| --- | --- |
| Build Command | `bash render-build.sh && pip install -r .core/requirements.txt` |
| Start Command | `cd .core && uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| `ANALYTICS_API_URL` | `https://` plus `CADDY_SITE_ADDRESS` |
| `ANALYTICS_API_SECRET` | At least 24 characters. The same value is stored on GitHub |
| `EXECUTION_MODE` | `dry_run` |
| `KILL_SWITCH` | `false` |

Wait until the service is Live and `GET /health` returns `{"status":"ok"}` before any `workflow_dispatch`.

`CADDY_SITE_ADDRESS` is `<public-ip>.sslip.io`, hostname only. `RENDER_HEALTH_URL` is `https://<render-host>/health`.

## 4. Nine secrets

Set these as GitHub repository secrets on this caller repository. They are required before the first dispatch.

| Secret | Meaning |
| --- | --- |
| `ANALYTICS_SSH_HOST` | Public IPv4 of this host |
| `ANALYTICS_SSH_PRIVATE_KEY` | The key file, from `BEGIN` through `END` |
| `ANALYTICS_SSH_HOST_FINGERPRINT` | The `SHA256:` field |
| `ANALYTICS_API_SECRET` | Shared with Render |
| `ANALYTICS_DB_PASSWORD` | Password of role `signalnexus` |
| `RENDER_HEALTH_URL` | `https://<render-host>/health` |
| `CADDY_SITE_ADDRESS` | Hostname only |
| `RENDER_DEPLOY_HOOK` | The Deploy Hook URL of this Web Service |
| `RENDER_API_KEY` | A key that can read this service, its deploys, and its build log |

Do not copy secret values from another caller repository.

## 5. Five variables

| Variable | Value |
| --- | --- |
| `ANALYTICS_SSH_USER` | `ubuntu` |
| `ANALYTICS_CORE_DIRECTORY` | `/home/ubuntu/signal-nexus` |
| `ANALYTICS_VENUE_DIRECTORY` | `/opt/signal-nexus/venueadd` |
| `BUILTIN_VENUES` | `none`, or the built-in set this environment runs |
| `DEPLOY_ANALYTICS` | `true`, after the nine secrets and immediately before the one dispatch |

`DEPLOY_ANALYTICS` is last. Until it is `true`, do not start the workflow.

## 6. Ready for the first deploy

Infrastructure execution is complete when the host meets section 1, Render `GET /health` is `{"status":"ok"}`, the nine secrets exist, and the first four variables exist. The dispatch itself is [Deployment Readiness](DEPLOYMENT_READINESS.md).
