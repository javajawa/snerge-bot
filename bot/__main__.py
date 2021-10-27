#!/usr/bin/env python3
# vim: nospell expandtab ts=4

# SPDX-FileCopyrightText: 2020 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

from typing import Any

import asyncio
import logging
import json
import random
import threading
import time

from systemd.journal import JournalHandler  # type: ignore
from twitchio.ext import commands  # type: ignore
from twitchio.dataclasses import Channel, Message  # type: ignore

from bot.load import load_data
from bot.token import App, Token
from prosegen import ProseGen


LOGGER = logging.getLogger("snerge")

CHANNEL = "sergeyager"

# The time until retry after when we lack a functional connection to Twitch
BACKOFF_STARTUP = (10, 10)
# The time until retry wait when no-one has talked recently
BACKOFF_NO_CHATTERS = (300, 300)
# How long to wait between sending quotes
BACKOFF_MESSAGE_SENT = (1500, 2100)

# How recently someone must have messaged for the channel to be considered active.
CHAT_ACTIVE_WINDOW = 360

# How long a quote should be (to prevent one word quotes and sentences that
# fill the entire screen).
MESSAGE_LEN_MIN = 24
MESSAGE_LEN_MAX = 80


class Bot(commands.Bot):  # type: ignore
    app: App
    prosegen: ProseGen
    target: Channel
    last_message: int

    def __init__(self) -> None:
        self.app = App.load()

        super().__init__(
            nick="SnergeBot",
            prefix="!",
            irc_token=self.app.irc_token,
            initial_channels=[CHANNEL],
        )

        self.target = None
        self.last_message = 0
        self.token = Token.load(CHANNEL)

        LOGGER.info("Renewing oAuth token")
        self.token.renew(self.app)

        self.prosegen = load_data()

        asyncio.run(self.send_quote())

    @staticmethod
    def owo_magic(non_owo_string: str) -> str:
        """
        Converts a non_owo_stirng to an owo_string

        :param non_owo_string: normal string

        :return: owo_string
        """

        return (
            non_owo_string.replace("ove", "wuw")
            .replace("R", "W")
            .replace("r", "w")
            .replace("L", "W")
            .replace("l", "w")
        )

    def get_quote(self) -> str:
        # Max 100 attempts to generate a quote
        for _ in range(0, 100):
            wisdom = self.prosegen.make_statement(MESSAGE_LEN_MIN)

            if MESSAGE_LEN_MIN < len(wisdom) < MESSAGE_LEN_MAX:
                return wisdom

        return "I don't like coffee."

    async def event_ready(self) -> None:
        LOGGER.info("Connected as %s", self.nick)

        self.target = self.get_channel(CHANNEL)
        if self.target:
            LOGGER.info("Connected to channel %s", CHANNEL)

        await self.pubsub_subscribe(
            self.token.access_token, f"channel-points-channel-v1.{self.token.user_id}"
        )

    async def event_message(self, message: Message) -> None:
        if message.author.name.lower() == self.nick.lower():
            return

        self.last_message = int(time.time())

    async def send_quote(self) -> None:
        if not self.target:
            LOGGER.info("No target initialised")
            next_call = random.randint(*BACKOFF_STARTUP)

        elif time.time() - self.last_message > CHAT_ACTIVE_WINDOW:
            next_call = random.randint(*BACKOFF_NO_CHATTERS)

        else:
            await self.send_quote_actual()
            next_call = random.randint(*BACKOFF_MESSAGE_SENT)

        self._timer = threading.Timer(next_call, lambda: asyncio.run(self.send_quote()))
        self._timer.start()

    async def send_quote_actual(self) -> None:
        quote = self.get_quote()

        LOGGER.info("Sending quote %s", quote)

        if random.randint(0, 2000) == 0:
            await self.target.send("[UwU] " + self.owo_magic(quote) + " [UwU]")
        else:
            await self.target.send("sergeSnerge " + quote + " sergeSnerge")

    async def event_pubsub(self, data: Any) -> None:
        raise NotImplementedError

    async def event_raw_pubsub(self, data: Any) -> None:
        if "type" not in data:
            LOGGER.info("No type in pub-sub event")
            return

        if data["type"] == "RESPONSE":
            if not data["error"]:
                LOGGER.info("PubSub initialised")
            elif data["error"] == "ERR_BADAUTH":
                LOGGER.warning("PubSub issue: %s", json.dumps(data))
                LOGGER.info("Renewing oAuth token")
                self.token.renew(self.app)
            else:
                LOGGER.error("PubSub issue: %s", json.dumps(data))

            return

        if data["type"] != "MESSAGE":
            return

        if "topic" not in data["data"]:
            LOGGER.info("No topic in pub-sub message")
            return

        if data["data"]["topic"] != "channel-points-channel-v1.73022083":
            LOGGER.info("Unexpected pub-sub topic %s", data["data"]["topic"])
            return

        _json = json.loads(data["data"]["message"])

        if _json["data"]["redemption"]["reward"]["title"] == "Summon Snerge":
            await self.send_quote_actual()
        else:
            LOGGER.info(
                "Ignoring non-Snerge reward %s",
                _json["data"]["redemption"]["reward"]["title"],
            )


if __name__ == "__main__":
    LOGGER.addHandler(JournalHandler(SYSLOG_IDENTIFIER="snerge-bot"))
    LOGGER.setLevel(logging.INFO)
    Bot().run()
