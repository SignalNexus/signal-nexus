# Review Feedback Actions

English is the canonical text. The Japanese edition is [REVIEW_FEEDBACK_ACTIONS_JA.md](REVIEW_FEEDBACK_ACTIONS_JA.md). This file records the 2026-10-16 review. It is not a user-facing procedure.

Japanese editions are a review aid. They are not polished here. After the English text is settled, a later translation pass may use another tool. That policy is intentional.

| Feedback | Decision | Action | Priority | Status |
| --- | --- | --- | --- | --- |
| BUILDBOOK_JA reads as an unfinished translation | Keep English canonical. Do not polish the whole Japanese book in this pass | Opening of `BUILDBOOK_JA.md` now points at the English book for screen-level steps. Full prose rewrite waits | P4 | Done as policy |
| Delete the README sentence at the top of the Buildbook | The sentence has no reader value | Removed from `BUILDBOOK.md` and `BUILDBOOK_JA.md` | P1 | Done |
| "Do not push to SignalNexus/signal-nexus" is abrupt at the top | Move it to the repository step | Moved in both Buildbook editions | P1 | Done |
| Repeated introductions of the other documents | One introduction | Collapsed to one paragraph in both Buildbook editions | P1 | Done |
| "本流 / Advanced notes" sentence is unclear | Use Main Flow and Advanced Notes, and say Main Flow is enough to build | Replaced in both Buildbook editions | P1 | Done |
| GitHub, Render, Oracle, and Discord need a click path | Put the path in the English book. Advanced Notes may hold the clicks | Added in `BUILDBOOK.md` | P1 | Done |
| TradingView free plan and webhooks | Basic cannot send a strategy webhook. Two-factor authentication is required. Ports are 80 and 443. Paid plan limits change | Table added under TradingView Advanced Notes in `BUILDBOOK.md`. Reader is told to check the live pricing page | P1 | Done |
| Render GitHub connection clicks | Dashboard, New, Web Service, connect GitHub, select the repo | Added under Render Advanced Notes in `BUILDBOOK.md` | P1 | Done |
| Recommend Tokyo | The exercised region is Japan East (`ap-tokyo-1`). Another region can reject Arcus calls that Tokyo accepts | Written in `BUILDBOOK.md` | P1 | Done |
| Create VCN, subnet, and security rules before the instance | Required path | Written in `BUILDBOOK.md`: wizard, TCP 22 from the reader's IP, TCP 443 from the internet, no 5432 | P1 | Done |
| Postgres backup daily at 03:00, keep four generations, rotate | The deploy script does not install this job. The book must tell the reader to add it | Written as a manual step in `BUILDBOOK.md`. Not claimed as an existing workflow | P1 | Done |
| Oracle field-level clicks | Same as the VCN and instance steps | Written in `BUILDBOOK.md` | P1 | Done |
| Explain `CADDY_SITE_ADDRESS` | Hostname only, stored as a GitHub secret, written to `/home/ubuntu/site.env`, used by Caddy. `https://` is added only for `ANALYTICS_API_URL` | Written in `BUILDBOOK.md` | P1 | Done |
| "Create the accounts" does not name them | Name MEXC, Rabby, and Arcus | Written in `BUILDBOOK.md` | P1 | Done |
| Add MEXC and Arcus referral links, with a change warning | Use the URLs supplied on 2026-10-16, including the TradingView pricing link. State that they can change | Added to `BUILDBOOK.md` and `BUILDBOOK_JA.md` | P1 | Done |
| Arcus Advanced Notes: Robinhood Chain and gas for signing | Gas is required when the Arcus API key is issued, on Robinhood Chain. Placing an order with that key does not spend gas | Written in both Buildbook editions | P1 | Done |
| Show `<account>/<repo>` from the start, not a personal repository name | The comparison stays. The book does not teach one person's repository name | Updated in `BUILDBOOK.md` and `BUILDBOOK_JA.md` | P1 | Done |
| `arcus-region-probe.yml` is not for this reader | Remove it from the Buildbook. Do not delete the workflow file | Removed from both Buildbook editions | P1 | Done |
| `RENDER_HEALTH_URL` cannot be known before Render exists | Push code first, create the Render service, then store the secret, then run Actions again | Reordered in `BUILDBOOK.md` | P1 | Done |
| Say where each validation command runs | Ubuntu shell for the three checks | Written in `BUILDBOOK.md` | P1 | Done |
| Architecture JA ASCII diagram is hard to read | Use Mermaid. English stays the figure of record, so both editions change | Mermaid added to `ARCHITECTURE.md` and `ARCHITECTURE_JA.md` | P2 | Done |
| Are the Arcus read address and order address different? | Two settings. The reader uses `ANALYTICS_ARCUS_ADDRESS` and does not sign. Orders use `ARCUS_ADDRESS` and `ARCUS_SIGNING_KEY`. The same address may be stored in both | Corrected in `ARCHITECTURE.md`, `ARCHITECTURE_JA.md`, and `BUILDBOOK.md` | P2 | Done |
| Product Specification JA needs an overview and a table of contents | Add them. Do not make this a second architecture | Added to `PRODUCT_SPECIFICATION_JA.md` | P3 | Done |
| "どこで動くか" repeats Architecture | Remove the repeated sentences from the Japanese edition | Replaced with a pointer to Architecture JA | P3 | Done |
| Japanese prose quality | Not this pass | Deferred until the English books are stable | P4 | Deferred |
