#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2020 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

from typing import Optional

import asyncio
import random
import threading
import time

from twitchio import Client, Channel, Message  # type: ignore

from snerge import logging
from snerge.config import Config
from snerge.token import App
from prosegen import ProseGen


class Bot(Client):  # type: ignore
    config: Config
    quotes: ProseGen
    target: Optional[Channel]
    last_message: int
    _timer: Optional[threading.Timer]

    def __init__(
        self, logger: logging.Logger, config: Config, app: App, quotes: ProseGen
    ) -> None:

        super().__init__(
            token=app.irc_token,
            initial_channels=[config.channel],
        )

        self.target = None
        self.last_message = 0
        self.logger = logger
        self.config = config
        self.quotes = quotes

        self.queue_quote()

    async def event_ready(self) -> None:
        self.logger.info("Connected as %s", self.nick)
        self.join_channel()

    def join_channel(self) -> None:
        """Attempt to join the channel, in a loop"""
        self.logger.info("Joining channel %s", self.config.channel)
        self.target = self.get_channel(self.config.channel)

        if self.target:
            self.logger.info("Connected to channel %s", self.config.channel)
            return

        threading.Timer(5, self.join_channel).start()

    async def event_message(self, message: Message) -> None:
        # Ignore loop-back messages
        if not message.author or message.author.name.lower() == self.nick.lower():
            return

        # Note when chat last happened
        self.last_message = int(time.time())
        self.logger.debug("Saw a message as %d", self.last_message)

        # Commands can only be processed by mods, when we can reply.
        if not self.target and not message.author.is_mod:
            return

        # !snerge command: send a quote!
        if message.content.startswith("!snerge"):
            self.logger.info("Manual Snerge by %s", message.author.name)
            await self.send_quote()

    def queue_quote(self) -> None:
        # If we haven't managed to connect to the channel, wait a while.
        if not self.target:
            next_call = random.randint(*self.config.startup_probe)
            self.logger.info("No target initialised, waiting %d seconds", next_call)

        # If we haven't heard from chat in a while, assume the stream is down
        elif time.time() - self.last_message > self.config.chat_active_probe[0]:
            next_call = random.randint(*self.config.chat_active_probe)
            self.logger.debug("Chat not active, waiting %d seconds", next_call)

        # Otherwise, send off a quote
        else:
            asyncio.run(self.send_quote())
            next_call = random.randint(*self.config.auto_quote_time)

        # Queue the next attempt to send a quote
        self._timer = threading.Timer(next_call, self.queue_quote)
        self._timer.start()

    async def send_quote(self) -> None:
        if not self.target:
            return

        quote = get_quote(self.quotes, *self.config.quote_length)

        self.logger.info("Sending quote %s", quote)

        # There is a 0.5% chance of Snerge going UwU!
        if random.randint(0, 200) == 0:
            await self.target.send("[UwU] " + owo_magic(quote) + " [UwU]")
        else:
            await self.target.send("sergeSnerge " + quote + " sergeSnerge")

    async def close(self) -> None:
        if self._timer:
            self._timer.cancel()

        await super().close()


def get_quote(quotes: ProseGen, min_length: int, max_length: int) -> str:
    # Max 100 attempts to generate a quote
    for _ in range(100):
        wisdom = quotes.make_statement(min_length)

        if min_length < len(wisdom) < max_length:
            return wisdom

    return "I don't like coffee."


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


def main() -> None:
    from snerge import config, token, quotes  # pylint: disable=import-outside-toplevel

    logging.init()
    logger = logging.get_logger()

    app = token.refresh_app_token()
    data = quotes.load_data(logger)

    # Create the IRC bot
    bot = Bot(
        logger=logger,
        app=app,
        config=config.config(),
        quotes=data,
    )

    bot.run()


if __name__ == "__main__":
    main()
