"""Configuration loading and validation."""
import os
import sys

import yaml


class ConfigError(Exception):
    pass


class Config:
    def __init__(self, data):
        # Mattermost connection. The token may live in the file or (preferred) the env.
        self.url = (os.environ.get("MM_URL") or data.get("mattermost_url") or "").rstrip("/")
        self.token = os.environ.get("MM_TOKEN") or data.get("admin_token") or ""

        self.team = data.get("team")
        self.channels = data.get("channels") or []
        self.users = data.get("users") or "auto"

        # Optional: the user reactions are posted as. Defaults to the token owner.
        self.bot_user_id = os.environ.get("MM_BOT_USER_ID") or data.get("bot_user_id") or ""

        self.poll_interval = int(data.get("poll_interval", 10))
        self.max_age_hours = int(data.get("max_age_hours", 24))

        emoji = data.get("emoji") or {}
        self.emoji_prefix = emoji.get("prefix", "seen_")
        self.emoji_create = bool(emoji.get("auto_create", True))
        self.emoji_initials = int(emoji.get("initials", 1))

        self._validate()

    def _validate(self):
        missing = []
        if not self.url:
            missing.append("mattermost_url (or MM_URL)")
        if not self.token:
            missing.append("admin_token (or MM_TOKEN)")
        if not self.team:
            missing.append("team")
        if not self.channels:
            missing.append("channels (at least one)")
        if missing:
            raise ConfigError("Missing required config: " + ", ".join(missing))


def load(path=None):
    path = path or os.environ.get("CONFIG_PATH", "config.yml")
    if not os.path.exists(path):
        raise ConfigError(f"Config file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return Config(data)
