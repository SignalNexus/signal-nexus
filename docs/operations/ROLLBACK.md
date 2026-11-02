# Rollback

English is canonical. The Japanese mirror is [ROLLBACK_JA.md](ROLLBACK_JA.md).

This chapter expands [Community Deployment Guide](../COMMUNITY_DEPLOYMENT_GUIDE.md) section 13. It does not add a required fact. A rollback changes that caller repository, that host, and that Render service only.

## 1. What a rollback is

A failure of the success checks in [Deployment Readiness](DEPLOYMENT_READINESS.md) is a rollback. The recommended SHA is not replaced. A previous recommended SHA stays.

Do not edit another caller repository as part of this rollback.

## 2. Failed first deploy

The environment has no last successful deploy.

1. Set `DEPLOY_ANALYTICS` to `false` on that caller repository.
2. Leave `venues: []` and the three SHA fields in place.
3. The workflow rolls the Render service back to the deploy that was live before the hook.
4. A retry uses a new SSH key and a new database password. Record the new fingerprint. Replace `ANALYTICS_SSH_PRIVATE_KEY`, `ANALYTICS_SSH_HOST_FINGERPRINT`, and `ANALYTICS_DB_PASSWORD`.
5. Return to [Infrastructure Execution](INFRASTRUCTURE_EXECUTION.md) for the replaced secrets, then [Deployment Readiness](DEPLOYMENT_READINESS.md).

## 3. Failed later deploy

The environment has a last successful deploy.

1. Return the seven runtime files, or the three SHA fields, to the last successful deploy.
2. Run `workflow_dispatch` once. `DEPLOY_ANALYTICS` stays `true`.
3. The workflow rolls the Render service back to the deploy that was live before that failed run.
4. Repeat the success checks. The recommended SHA stays the last successful value until those checks pass again on a later update.

A venue rollback that keeps the same core SHA changes the manifest `sha` to the previous commit and runs deploy once. The tree under `ANALYTICS_VENUE_DIRECTORY/<import_name>/` is replaced by that commit.

## 4. Scope

| In scope | Out of scope |
| --- | --- |
| This caller repository | Another caller repository |
| This host | Another host |
| This Render Web Service | Another Render service |
| This environment's recommended SHA | A public tag, or another environment's pin |
