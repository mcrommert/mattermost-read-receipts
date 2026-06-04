# Mattermost Read Receipts

Mattermost has no built-in read receipts. This is a small, self-hosted bot that adds
them — and it works **everywhere**, including the iOS/Android apps, because it represents
"seen" as an ordinary emoji reaction rather than a custom UI element.

Each tracked person gets one custom emoji (a colored disc with their initial). The bot
places that emoji on the **most recent message they've read that someone else wrote**, and
moves it down as they keep reading. So every conversation shows, at a glance, how far each
person has read — with at most one marker per person.

```
Alice:  hey, did you see the deploy went out?           🅐
Bob:    yeah just looked — looks clean                  🅐
Alice:  nice, I'll close the ticket                  🅑
        └ Bob's marker sits here: he's read up to this point
```

## Why a reaction?

Mattermost stores `last_viewed_at` / `msg_count` per user per channel (that's how unread
counts work), but there is **no server-side hook** that fires when someone views a channel,
and webapp plugins don't render in the mobile apps. Reactions are the one primitive that
syncs natively to web, desktop, **and** mobile with zero client code. So the bot polls each
member's read counter and, when it advances past a message, drops their reaction on it.

This approach is best for **DMs and small channels**. Per-message read state is O(users ×
messages), which is exactly why Mattermost hasn't shipped it for busy channels — so point
this at group DMs and small private channels, not `~town-square`.

## How it works

1. Poll each watched channel every few seconds.
2. For each member, read their `msg_count` (messages they've acknowledged) and compare it
   to each message's snapshot threshold to determine the newest message they've read.
3. Reconcile reactions so each person's emoji is on exactly that message — adding the new
   one and removing the old one in the same pass.

It uses **only the REST API**, so it keeps working across Mattermost server upgrades with no
changes. State is in-memory; a restart simply re-reconciles to the correct state (there's no
reaction storm because the target state is at most one reaction per user per channel).

## Requirements

- A Mattermost server you administer.
- A **personal access token** for a system-admin account (Account Settings → Security →
  Personal Access Tokens; enable them in System Console → Integrations if needed). The bot
  needs to read channel members and add/remove reactions. Reactions are posted **as this
  account**, because Mattermost does not allow reacting on behalf of another user — so the
  hover tooltip on a marker will show the admin/bot account, not the person. The *letter* is
  the real signal.
- Docker (recommended) or Python 3.11+.

## Quick start (Docker)

```bash
git clone https://github.com/mcrommert/mattermost-read-receipts.git
cd mattermost-read-receipts

cp config.example.yml config.yml
# edit config.yml: server URL, team, channels, users

# put your token in the environment (don't commit it)
export MM_TOKEN="your-system-admin-token"

docker compose up -d --build
docker compose logs -f
```

On first run the bot creates one custom emoji per tracked user (e.g. `:seen_alice:`) and
starts placing markers as people read.

## Configuration

See [`config.example.yml`](config.example.yml) for the full annotated reference. The
essentials:

| Key | Description |
| --- | --- |
| `mattermost_url` / `MM_URL` | Your server URL. |
| `admin_token` / `MM_TOKEN` | System-admin personal access token. Prefer the env var. |
| `team` | Team URL slug (the part in `/<team>/channels/...`). |
| `channels` | List of channel **slugs** to watch. |
| `users` | List of usernames to track, or `auto` for all human members. |
| `poll_interval` | Seconds between polls (default `10`). |
| `max_age_hours` | Ignore messages older than this (default `24`). |
| `emoji.auto_create` | Auto-create the colored-letter emoji (default `true`). |
| `emoji.prefix` | Emoji are named `<prefix><username>` (default `seen_`). |

## Running without Docker

```bash
pip install -r requirements.txt
export MM_URL="https://mattermost.example.com"
export MM_TOKEN="your-system-admin-token"
python -m app.main          # expects ./config.yml (or set CONFIG_PATH)
```

## Notes & limitations

- **Scope to DMs / small channels.** Don't point it at large, high-traffic channels.
- **Markers are owned by the token account.** Hover shows that account, not the reader.
- **Cold start.** Messages that already existed when the bot starts get a coarse read
  threshold, so people who are behind won't get a marker on the backlog until new messages
  arrive. Tracking is exact for everything posted while the bot is running.
- **Bot never deletes other people's reactions** — only the ones it placed.

## License

[MIT](LICENSE)
