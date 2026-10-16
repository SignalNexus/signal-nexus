# Correction Decisions

English is the canonical text.

## Discord Audit Delivery

| | |
| --- | --- |
| Issue | Discord Audit Delivery |
| Severity | Critical |
| Classification | Known Temporary Divergence |
| Current State | Posts are enabled. A wait longer than one minute still stops further posts in that process. |
| Decision | Enable Delivery |
| Documentation Change | None |
| Code Change | `_DISCORD_POSTS_ENABLED` is `True`. |
| Owner | Codebase |
| Status | Done |

`_DISCORD_POSTS_ENABLED` in `app/notifications/discord.py` is `True`. A set `DISCORD_WEBHOOK_URL` posts the audit copy. A Discord 429 whose `retry_after` is longer than 60 seconds sets the process pause and records `429 paused` instead of the raw wait.

The release behavior is: when `DISCORD_WEBHOOK_URL` is set, the audit copy is sent to Discord.

Architecture, the Buildbook, and the Product Specification already say that Discord receives audit copies. Those documents stay as they are. The code now matches them. This item is not a documentation correction.
