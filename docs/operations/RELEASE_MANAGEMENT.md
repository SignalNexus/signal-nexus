# Release Management

English is canonical. The Japanese mirror is [RELEASE_MANAGEMENT_JA.md](RELEASE_MANAGEMENT_JA.md).

This chapter is how a public core commit is published and how one environment takes that commit. The operator path that moves a pin is [Community Deployment Guide](../COMMUNITY_DEPLOYMENT_GUIDE.md) section 11. This chapter does not add a required fact for that path.

## 1. Development and publication

The development repository is not the public product. A push to its `main` does not publish Signal Nexus and does not deploy a caller host.

Publication is a tag `public-` plus eleven digits on a development commit. The export writes the public tree to `SignalNexus/signal-nexus` `main`. It does not copy `config/`. The public `config/` stays the sample.

A caller repository does not follow public `main` by itself. It runs the commit in `core-pin`.

## 2. Release gate

A `public-` tag is allowed only when that commit is on the development `main` and the gate on that commit has succeeded:

- Unit tests
- The export path check, including the refusal of `config/`, `business/`, and secrets
- `render-build.sh` in Actions, with seven non-empty fixture files, printing seven sha256 lines
- For a workflow change, a reading of the new `analytics-deploy.yml` against those tests
- For a paid venue, the port tests with a mock. No live venue is required to publish the core

Render health on a caller service, and a deploy to that caller's host, are acceptance for that environment. They do not block the tag.

## 3. How an environment takes a public update

1. Confirm the new public SHA still contains the futures-read condition from the guide.
2. Write that SHA in `core-pin`, `uses`, and `core_sha`.
3. Run `workflow_dispatch` once. `DEPLOY_ANALYTICS` stays `true`.
4. Repeat the success checks in [Deployment Readiness](DEPLOYMENT_READINESS.md).
5. When those checks pass, the recommended SHA for this environment becomes that public SHA.

Signal Nexus does not edit the caller repository after the operator chooses the pin.

## 4. Recommended SHA rule

The recommended SHA is the public core SHA of the last successful deploy for that environment. The first successful deploy sets it. Each later successful deploy replaces it. A failed deploy does not replace it.

Another caller repository is a different record.

## 5. What this chapter does not do

This chapter does not tag a release. It does not export. It does not move another environment's pin.
