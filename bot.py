#!/usr/bin/env python3
# vim: nospell expandtab ts=4

# SPDX-FileCopyrightText: 2020 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

from typing import Any, Optional

import asyncio
import random
import threading
import time

import requests
from twitchio.ext import commands  # type: ignore
from twitchio.dataclasses import Channel, Message  # type: ignore

import prosegen


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
    prosegen: prosegen.ProseGen
    target: Optional[Channel]
    last_message: int

    def __init__(self) -> None:
        with open("twitch.token") as token:
            super().__init__(
                nick="SnergeBot",
                prefix="!",
                irc_token=token.read().strip(),
                initial_channels=["sergeyager"],
            )

        self.load_data()
        self.target = None
        self.last_message = 0
        asyncio.run(self.send_quote())

    def load_data(self) -> None:
        data = requests.get(
            "https://raw.githubusercontent.com/RebelliousUno/BrewCrewQuoteDB/main/quotes.txt"
        )
        self.prosegen = prosegen.ProseGen(20)

        for line in data.text.split("\n"):
            line = line.strip()

            if not line:
                continue

            line_quotes = line.split('"')[1:]

            for quote, attr in zip(*[iter(line_quotes)] * 2):
                if "Serge" in attr or "Snerge" in attr:
                    self.prosegen.add_knowledge(quote)

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
        print(f"Connected | {self.nick}")

        self.target = self.get_channel("sergeyager")

    async def event_message(self, message: Message) -> None:
        if message.author.name.lower() == self.nick.lower():
            return

        self.last_message = int(time.time())

    async def send_quote(self) -> None:
        if not self.target:
            print("No target initialised")
            next_call = random.randint(*BACKOFF_STARTUP)

        elif time.time() - self.last_message > CHAT_ACTIVE_WINDOW:
            next_call = random.randint(*BACKOFF_NO_CHATTERS)

        else:
            quote = self.get_quote()

            if random.randint(0, 500) == 0:
                await self.target.send("[UwU] " + self.owo_magic(quote) + " [UwU]")
            else:
                await self.target.send("sergeSnerge " + quote + " sergeSnerge")
            next_call = random.randint(*BACKOFF_MESSAGE_SENT)

        self._timer = threading.Timer(next_call, lambda: asyncio.run(self.send_quote()))
        self._timer.start()

    async def event_pubsub(self, data: Any) -> None:
        raise NotImplementedError


if __name__ == "__main__":
    Bot().run()
