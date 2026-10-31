# Security Policy

Signal Nexus Community Edition

English is the canonical text. The Japanese edition is [SECURITY_JA.md](SECURITY_JA.md). This policy explains how to report a vulnerability in the Community Edition. It does not grant permission to test systems you do not own. Use of the software remains subject to [LICENSE.md](LICENSE.md).

## Controls in this edition

This edition is for one person running their own host. It does not add roles, tenants, or an approval board.

- `KILL_SWITCH=true` on Render stops a webhook order. The same value on the virtual machine stops `/api/mexc/order`, `/api/arcus/order`, and a protective exit. `dry_run` remains a Render gate. The virtual machine is the live executor.
- The order API uses the same strategy `side` and action rules as the webhook. A refusal is HTTP 403. The audit row records `KILL_SWITCH` or the direction reason. Postgres being down does not let the order through.
- `bar_time` must fall within `MAX_BAR_AGE_SECONDS` of the server clock. The default is 24 hours (86400 seconds). This stops an old alert body from opening a new position. It does not replace a durable order id.
- `WEBHOOK_SECRET` and `ANALYTICS_API_SECRET`, when set, must be at least 24 characters or that process does not start. `PORTAL_PASSWORD` has no length rule. An unset secret stays closed at the request.
- The portal session cookie is `HttpOnly`, `SameSite=lax`, and `Secure`.
- The Analytics API listens on `127.0.0.1` unless `ANALYTICS_BIND_HOST` says otherwise. Caddy publishes it. `/docs` and `/openapi.json` stay off unless `ENABLE_API_DOCS=true` at process start.
- MEXC keys should be limited to the virtual machine address. An empty IP field leaves a trade key usable from any network. Withdrawal stays off. That is an exchange setting, not a check inside this process.

## Reporting a Vulnerability

Report a vulnerability in private. Use GitHub private vulnerability reporting on the official repository:

[https://github.com/SignalNexus/signal-nexus/security/advisories/new](https://github.com/SignalNexus/signal-nexus/security/advisories/new)

If that page is unavailable, contact the repository owner through GitHub and say that you have a security report. Wait for a private channel. Do not include the details in that first public contact.

Do not open a public issue, pull request, discussion, or commit that contains exploit details, proof-of-concept code, a live secret, or a live endpoint that is not yours.

Include what you can of the following:

- a description of the issue and the impact you believe it has
- the component, file, or request path
- the version, tag, or commit you tested
- the steps a maintainer can repeat on a local instance
- any condition that must be true for the issue to matter, such as a live execution mode

You do not need to produce a weaponized exploit. A clear reproduction on a system you control is enough.

## Scope

The following are in scope when they affect the Community Edition source in the official repository:

- the application source, including the webhook, the portal, the execution path, and the analytics store
- authentication and authorization as implemented in that source, including the webhook secret and the portal password
- a software defect that can cause an unintended order, a skipped risk control, or a disclosure of a secret the software stores
- a dependency vulnerability that is exploitable in the Community Edition's default configuration

A deployment you run yourself is in scope only as evidence of a defect in that source. The defect report should be reproducible from the published code.

## Responsible Disclosure

Investigate and report in good faith.

- Give the Author a private report before any public statement.
- Allow a reasonable time to investigate and to publish a mitigation before you publish details. The default window is 90 days after the Author acknowledges the report. A shorter or longer window can be agreed in writing.
- Do not access, change, or take data that is not yours.
- Do not degrade a service, and do not send traffic that interferes with anyone else's use.
- Do not test an exchange, a DEX, an RPC provider, an oracle, or any other third party.
- Do not test a deployment you do not own, including the Author's, unless the Author has agreed to that test in writing.
- Until a fix is published, or the disclosure window has ended, do not publish exploit code, scanner output, or a step-by-step attack.

If you follow this policy, the Author will not bring a legal claim against you for that good-faith research on the Community Edition. This promise does not cover research outside the scope, research that breaks the rules above, or a claim brought by someone other than the Author.

## Out of Scope

The following are out of scope:

- the Author's private production systems, unpublished editions, membership repositories, and paid products, unless the Author invites a report about that system
- third-party services, including exchanges, DEX protocols, RPC providers, oracles, TradingView, Discord, and cloud hosts
- social engineering, phishing, and physical attacks against the Author or a user
- volumetric denial of service
- a report that depends on a webhook secret, a portal password, or a venue key that you were not issued and that you did not find through a defect in the published code
- a missing hardening step that you cannot connect to a concrete impact
- a modified fork, or code that you changed
- a supported configuration that behaves as the documentation describes, including a live mode that sends the order the strategy row defines

A rejected feature request, a question about setup, and a bug that has no security impact belong in a normal issue, not in this channel.

## Response Commitment

The Author will make a best-effort response:

- acknowledge a report within 7 days
- send an assessment update within 14 days after acknowledgement
- fix or mitigate a confirmed issue in a later Community Edition publication, with priority set by impact
- publish a GitHub Security Advisory when a fix for a confirmed vulnerability is ready, when that is appropriate

There is no bug bounty unless the Author announces one in writing.

If you want credit, say so in the report. Credit is given after a fix, in the advisory or the release note. If you want to stay unnamed, say that instead.

These targets are a commitment of effort by a single maintainer. They are not a service-level agreement, not a warranty, and not a promise that every report will result in a code change. The Author may decline a report that is out of scope, duplicate, or not a vulnerability.

Supported software is the Community Edition published by the Author in the official repository. Forks and local modifications are not supported.
