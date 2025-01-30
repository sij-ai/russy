#!/usr/bin/env python3

import asyncio
import logging
import os
import sys
import time
from typing import Dict, List

import yaml
import feedparser
import markdown

from nio import (
    AsyncClient,
    LoginResponse,
    JoinResponse,
    RoomResolveAliasResponse
)

CONFIG_FILE = "config.yaml"
STATE_FILE = ".state"

class RssBot:
    def __init__(self):
        self.setup_logging()
        self.config = self.load_config()

        matrix_cfg = self.config["matrix"]
        self.server = matrix_cfg["server"]
        self.username = matrix_cfg["username"]
        self.password = matrix_cfg["password"]

        self.room_ids = {}  # Stores {room_alias: real_room_id}
        self.client = AsyncClient(self.server, self.username)
        
        self.feeds = self.config["rss"]
        
        # Hardcoded default interval (overridable per feed)
        self.default_interval = 3600  # 1 hour

        self.state = self.load_state()

    async def process_feeds_loop(self):
        """Loop that checks each RSS feed at its configured interval."""
        while True:
            for feed in self.feeds:
                await self.process_feed(feed)
                feed_interval = feed.get("interval", self.default_interval)  # Per-feed override
                self.logger.info(f"Waiting {feed_interval} seconds before checking {feed['name']} again...")
                await asyncio.sleep(feed_interval)

    async def main(self):
        await self.login()
        await self.join_rooms_from_feeds()
        asyncio.create_task(self.process_feeds_loop())
        await self.client.sync_forever(timeout=30000, full_state=True)

    def setup_logging(self):
        self.logger = logging.getLogger("rss_bot")
        self.logger.setLevel(logging.DEBUG)

        fh = logging.FileHandler("rss_bot.log")
        fh.setLevel(logging.DEBUG)

        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)

        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)

        self.logger.addHandler(fh)
        self.logger.addHandler(ch)

    def load_config(self):
        script_dir = os.path.dirname(os.path.realpath(__file__))
        path = os.path.join(script_dir, CONFIG_FILE)
        if not os.path.exists(path):
            self.logger.error(f"Missing config file: {CONFIG_FILE}")
            sys.exit(1)
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def load_state(self) -> Dict[str, List[str]]:
        if not os.path.exists(STATE_FILE):
            return {}
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def save_state(self):
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            yaml.dump(self.state, f)
        self.logger.debug("State file saved.")

    async def login(self):
        self.logger.info(f"Logging in as {self.username} on {self.server}, ephemeral store.")
        resp = await self.client.login(self.password)
        if isinstance(resp, LoginResponse):
            self.logger.info("Login success.")
        else:
            self.logger.error(f"Login failed: {resp}")
            sys.exit(1)

    async def join_rooms_from_feeds(self):
        """Join all feed rooms and store their real room IDs."""
        unique_rooms = set(feed["room"] for feed in self.feeds)
        for room_alias in unique_rooms:
            self.logger.info(f"Attempting to join {room_alias}.")
            try:
                resp = await self.client.join(room_alias)
                if isinstance(resp, JoinResponse) and hasattr(resp, "room_id"):
                    self.room_ids[room_alias] = resp.room_id
                    self.logger.info(f"Joined {room_alias} -> {resp.room_id}")
                else:
                    self.logger.warning(f"Join to {room_alias} did not return a room_id. Attempting alias resolution.")
                    await self.resolve_room_id_by_alias(room_alias)
            except Exception as e:
                self.logger.error(f"Couldn't join {room_alias}: {e}")

    async def resolve_room_id_by_alias(self, alias: str):
        """Attempt to resolve a room alias to a real room ID directly."""
        try:
            resp = await self.client.room_resolve_alias(alias)
            if isinstance(resp, RoomResolveAliasResponse):
                self.room_ids[alias] = resp.room_id
                self.logger.info(f"Resolved alias {alias} -> {resp.room_id}")
            else:
                self.logger.error(f"Failed to resolve alias {alias}. Response: {resp}")
        except Exception as e:
            self.logger.error(f"Error resolving alias {alias}: {e}")

    async def send_html_message(self, alias_or_room_id: str, text: str):
        """Send a message to a Matrix room using the real room ID."""
        room_id = self.room_ids.get(alias_or_room_id, alias_or_room_id)
        if not room_id.startswith("!"):
            self.logger.error(f"No known room ID for alias {alias_or_room_id}. Cannot send.")
            return

        formatted_body = markdown.markdown(text, extensions=["fenced_code", "nl2br"])
        content = {
            "msgtype": "m.text",
            "body": text,
            "format": "org.matrix.custom.html",
            "formatted_body": formatted_body
        }
        try:
            await self.client.room_send(room_id=room_id, message_type="m.room.message", content=content)
        except Exception as e:
            self.logger.error(f"Error sending message to {room_id}: {e}")

    async def process_feed(self, feed_info):
        """Check one feed for new entries, post them to feed_info['room']."""
        name = feed_info["name"]
        url  = feed_info["feed"]
        room_alias = feed_info["room"]

        if name not in self.state:
            self.state[name] = []

        self.logger.info(f"Checking feed '{name}' from {url}")
        data = feedparser.parse(url)
        new_entries = [entry for entry in data.entries if entry.get("id", entry.get("link")) not in self.state[name]]

        for entry in sorted(new_entries, key=lambda e: e.get("published_parsed", time.gmtime())):
            entry_id = entry.get("id") or entry.get("link")
            title = entry.get("title", "No Title")
            link = entry.get("link", "")
            summary = entry.get("summary", "")
            msg_text = f"**{title}**\n{link}\n\n{summary}"

            self.logger.info(f"Posting new entry to {room_alias}: {title}")
            await self.send_html_message(room_alias, msg_text)
            await asyncio.sleep(2)

            self.state[name].append(entry_id)

        self.save_state()

    async def post_rss_entries(self):
        for feed in self.feeds:
            await self.process_feed(feed)

def main():
    bot = RssBot()
    asyncio.run(bot.main())

if __name__ == "__main__":
    main()
