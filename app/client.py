"""Minimal Mattermost REST API client (only the calls this bot needs)."""
import json
from urllib.parse import quote

import requests


class MattermostClient:
    def __init__(self, url, token, timeout=10):
        self.base = url.rstrip("/") + "/api/v4"
        self.s = requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {token}"})
        self.timeout = timeout

    # --- low level ---
    def _get(self, path, **kw):
        r = self.s.get(self.base + path, timeout=self.timeout, **kw)
        r.raise_for_status()
        return r.json()

    def _post(self, path, **kw):
        return self.s.post(self.base + path, timeout=self.timeout, **kw)

    def _delete(self, path, **kw):
        return self.s.delete(self.base + path, timeout=self.timeout, **kw)

    # --- identity / lookups ---
    def me(self):
        return self._get("/users/me")

    def team_by_name(self, name):
        return self._get(f"/teams/name/{quote(name, safe='')}")

    def channel_by_name(self, team_id, name):
        return self._get(f"/teams/{team_id}/channels/name/{quote(name, safe='')}")

    def user_by_username(self, username):
        return self._get(f"/users/username/{quote(username, safe='')}")

    def channel_members(self, channel_id, page=0, per_page=200):
        return self._get(f"/channels/{channel_id}/members",
                         params={"page": page, "per_page": per_page})

    def users_by_ids(self, ids):
        if not ids:
            return []
        r = self._post("/users/ids", json=list(ids))
        r.raise_for_status()
        return r.json()

    # --- read state ---
    def channel(self, channel_id):
        return self._get(f"/channels/{channel_id}")

    def member_msg_count(self, channel_id, user_id):
        try:
            data = self._get(f"/channels/{channel_id}/members/{user_id}")
            c = data.get("msg_count")
            return c if isinstance(c, int) else -1
        except Exception:
            return -1

    def recent_posts(self, channel_id, per_page=60):
        data = self._get(f"/channels/{channel_id}/posts", params={"per_page": per_page})
        posts = data.get("posts", {})
        ordered = [posts[pid] for pid in data.get("order", []) if pid in posts]
        ordered.reverse()  # oldest first
        return ordered

    # --- reactions ---
    def post_reactions(self, post_id):
        try:
            return self._get(f"/posts/{post_id}/reactions") or []
        except Exception:
            return []

    def add_reaction(self, user_id, post_id, emoji):
        r = self._post("/reactions",
                       json={"user_id": user_id, "post_id": post_id, "emoji_name": emoji})
        return r.status_code in (200, 201)

    def remove_reaction(self, user_id, post_id, emoji):
        r = self._delete(f"/users/{user_id}/posts/{post_id}/reactions/{emoji}")
        return r.status_code == 200

    # --- custom emoji ---
    def emoji_exists(self, name):
        try:
            self._get(f"/emoji/name/{name}")
            return True
        except Exception:
            return False

    def create_emoji(self, name, creator_id, png_bytes):
        files = {"image": (name + ".png", png_bytes, "image/png")}
        data = {"emoji": json.dumps({"creator_id": creator_id, "name": name})}
        r = self._post("/emoji", files=files, data=data)
        return r.status_code in (200, 201)
