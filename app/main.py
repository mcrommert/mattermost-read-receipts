"""Entrypoint: load config, resolve names, run the reconcile loop."""
import logging
import time

from . import config
from .client import MattermostClient
from .provision import resolve
from .receipts import ReceiptTracker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("mm-read-receipts")


def main():
    try:
        cfg = config.load()
    except config.ConfigError as e:
        log.error("Config error: %s", e)
        raise SystemExit(1)

    client = MattermostClient(cfg.url, cfg.token)

    # Retry resolution until the server is reachable (handy on container start order).
    while True:
        try:
            bot_id, channel_map, user_emoji = resolve(client, cfg)
            break
        except Exception as e:
            log.warning("Startup resolve failed (%s); retrying in 10s", e)
            time.sleep(10)

    tracker = ReceiptTracker(
        client, bot_id, channel_map, user_emoji, max_age_hours=cfg.max_age_hours
    )
    log.info("Read-receipts bot running. Polling every %ds.", cfg.poll_interval)

    while True:
        tracker.tick(int(time.time() * 1000))
        time.sleep(cfg.poll_interval)


if __name__ == "__main__":
    main()
