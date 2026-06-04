"""Resolve names to IDs and ensure each tracked user has a custom letter emoji."""
import io
import logging
import os
import re

from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger(__name__)

# A distinct color per user, assigned by index. Wraps if there are more users.
PALETTE = [
    (46, 204, 113),   # green
    (231, 76, 60),    # red
    (155, 89, 182),   # purple
    (52, 152, 219),   # blue
    (241, 196, 15),   # yellow
    (230, 126, 34),   # orange
    (26, 188, 156),   # teal
    (233, 30, 99),    # pink
    (149, 165, 166),  # gray
    (52, 73, 94),     # navy
]

_FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "C:\\Windows\\Fonts\\arialbd.ttf",
    "C:\\Windows\\Fonts\\Arial.ttf",
]


def _load_font(size):
    for p in _FONT_PATHS:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _letter_png(label, color, size=128):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([4, 4, size - 4, size - 4], fill=color)
    font = _load_font(int(size * 0.6) if len(label) == 1 else int(size * 0.42))
    bbox = d.textbbox((0, 0), label, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text(((size - w) / 2 - bbox[0], (size - h) / 2 - bbox[1]),
           label, fill=(255, 255, 255, 255), font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _sanitize(name):
    return re.sub(r"[^a-z0-9_-]", "", name.lower())


def resolve(client, cfg):
    """Returns (bot_user_id, channel_map, user_emoji).

    channel_map: {channel_id: channel_display_or_name}
    user_emoji:  {user_id: emoji_name}
    """
    bot_user_id = cfg.bot_user_id or client.me()["id"]

    team = client.team_by_name(cfg.team)
    team_id = team["id"]

    channel_map = {}
    channel_ids = []
    for name in cfg.channels:
        ch = client.channel_by_name(team_id, name)
        channel_map[ch["id"]] = ch.get("display_name") or ch["name"]
        channel_ids.append(ch["id"])

    # Resolve the set of users to track.
    if isinstance(cfg.users, list) and cfg.users:
        users = [client.user_by_username(u) for u in cfg.users]
    else:
        # "auto": union of human members across all watched channels.
        member_ids = set()
        for cid in channel_ids:
            for m in client.channel_members(cid):
                member_ids.add(m["user_id"])
        users = [u for u in client.users_by_ids(member_ids) if not u.get("is_bot")]
        # Skip the bot's own account.
        users = [u for u in users if u["id"] != bot_user_id]

    user_emoji = {}
    for i, u in enumerate(sorted(users, key=lambda x: x["username"])):
        label = u["username"][: max(1, cfg.emoji_initials)].upper()
        emoji_name = _sanitize(cfg.emoji_prefix + u["username"])
        color = PALETTE[i % len(PALETTE)]
        if cfg.emoji_create and not client.emoji_exists(emoji_name):
            if client.create_emoji(emoji_name, bot_user_id, _letter_png(label, color)):
                log.info("Created custom emoji :%s: (%s)", emoji_name, u["username"])
            else:
                log.warning("Could not create emoji :%s:; reactions for %s may fail",
                            emoji_name, u["username"])
        user_emoji[u["id"]] = emoji_name

    log.info("Tracking %d users across %d channels as bot %s",
             len(user_emoji), len(channel_map), bot_user_id)
    return bot_user_id, channel_map, user_emoji
