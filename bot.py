#!/usr/bin/python3
# vim: nospell expandtab ts=4

# SPDX-FileCopyrightText: 2020 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations


import asyncio
import random
import threading

import requests
from twitchio.ext import commands  # type: ignore

import prosegen


class Bot(commands.Bot):  # type: ignore
    prosegen: prosegen.ProseGen

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
        asyncio.run(self.send_quote())

    def load_data(self) -> None:
        data = requests.get(
            "https://raw.githubusercontent.com/RebelliousUno/BrewCrewQuoteDB/main/quotes.txt"
        )
        self.prosegen = prosegen.ProseGen(8)

        for line in data.text.split("\n"):
            line = line.strip()

            if not line:
                continue

            quotes = line.split('"')[1::2]

            for quote in quotes:
                self.prosegen.add_knowledge(quote)

    def get_quote(self) -> str:
        i = 0

        while i < 100:
            wisdom = self.prosegen.make_statement()

            if 16 < len(wisdom) < 80:
                return wisdom

        return "I don't like coffee."

    async def event_ready(self) -> None:
        print(f"Connected | {self.nick}")

        self.target = self.get_channel("sergeyager")

    async def send_quote(self) -> None:
        if self.target:
            quote = self.get_quote()
            print(f"Sending '{quote}'")
            await self.target.send(quote)

            next_call = 3600 + random.randint(-600, 600)

        else:
            print("No target initialised")

            next_call = 30

        self._timer = threading.Timer(next_call, lambda: asyncio.run(self.send_quote()))
        self._timer.start()


if __name__ == "__main__":
    Bot().run()
