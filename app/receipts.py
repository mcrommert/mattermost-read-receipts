"""Single-marker 'read up to here' reconciliation.

Each tracked user's emoji lives on exactly one message per channel: the newest message
authored by someone else that they have read. When they read something newer, the marker
moves down (old reaction removed, new one added). At most one reaction per user per channel.
"""
import logging

log = logging.getLogger(__name__)


class ReceiptTracker:
    def __init__(self, client, bot_user_id, channel_map, user_emoji, max_age_hours=24):
        self.c = client
        self.bot_id = bot_user_id
        self.channels = channel_map           # {channel_id: name}
        self.user_emoji = user_emoji          # {user_id: emoji_name}
        self.all_emoji = set(user_emoji.values())
        self.max_age_ms = max_age_hours * 3600 * 1000
        # {channel_id: {post_id: {create_at, author, threshold, marks:set()}}}
        self.known = {cid: {} for cid in channel_map}

    def _bot_marks(self, post_id):
        """Tracked emoji currently placed by the bot on this post."""
        return {r["emoji_name"] for r in self.c.post_reactions(post_id)
                if r["user_id"] == self.bot_id and r["emoji_name"] in self.all_emoji}

    def tick(self, now_ms):
        cutoff = now_ms - self.max_age_ms
        for cid, name in self.channels.items():
            try:
                self._reconcile(cid, name, cutoff)
            except Exception as e:
                log.warning("Error processing %s: %s", name, e)

    def _reconcile(self, cid, name, cutoff):
        known = self.known[cid]
        posts = self.c.recent_posts(cid)

        try:
            member_ids = {m["user_id"] for m in self.c.channel_members(cid)}
        except Exception:
            member_ids = set(self.user_emoji)
        tracked = [uid for uid in self.user_emoji if uid in member_ids]
        if not tracked:
            return

        # Register new posts once, snapshotting read-threshold and existing markers.
        new = [p for p in posts if p["id"] not in known and p["create_at"] >= cutoff]
        if new:
            total = self.c.channel(cid).get("total_msg_count", 0)
            for p in new:
                known[p["id"]] = {
                    "create_at": p["create_at"],
                    "author": p["user_id"],
                    "threshold": total,
                    "marks": self._bot_marks(p["id"]),
                }

        for pid in [pid for pid, m in known.items() if m["create_at"] < cutoff]:
            del known[pid]
        if not known:
            return

        window = sorted(known.items(), key=lambda kv: kv[1]["create_at"])  # oldest -> newest
        counts = {uid: self.c.member_msg_count(cid, uid) for uid in tracked}

        # Target post per user: newest post by someone else that they've read.
        target = {}
        for uid in tracked:
            mc = counts[uid]
            chosen = None
            if mc >= 0:
                for pid, meta in window:
                    if meta["author"] == uid:
                        continue
                    if mc >= meta["threshold"]:
                        chosen = pid
            target[uid] = chosen

        # Reconcile each user's single marker against in-memory state.
        for uid in tracked:
            emoji = self.user_emoji[uid]
            desired = target[uid]
            for pid, meta in window:
                here = emoji in meta["marks"]
                if pid == desired and not here:
                    if self.c.add_reaction(self.bot_id, pid, emoji):
                        meta["marks"].add(emoji)
                        log.info("%s: :%s: -> %s", name, emoji, pid[:8])
                elif pid != desired and here:
                    if self.c.remove_reaction(self.bot_id, pid, emoji):
                        meta["marks"].discard(emoji)
                        log.info("%s: :%s: removed from %s", name, emoji, pid[:8])
