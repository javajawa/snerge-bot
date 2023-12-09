#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2020 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

import asyncio
import random

from twitchio import Client, Channel, Chatter, Message, User  # type: ignore

from snerge import log
from snerge.config import Config
from snerge.token import App
from snerge.guessmessagehandler import GuessMessageHandler
from prosegen import ProseGen, Fact, GeneratedQuote


class Bot(Client):  # type: ignore
    config: Config
    quotes: ProseGen
    last_message: int
    _stop: bool = False
    guess_handler : GuessHandler

    def __init__(  # pylint: disable=too-many-arguments
        self,
        logger: log.Logger,
        loop: asyncio.AbstractEventLoop,
        config: Config,
        app: App,
        quotes: ProseGen,
    ) -> None:
        super().__init__(token=app.irc_token, loop=loop)

        self.last_message = 0
        self.logger = logger
        self.config = config
        self.quotes = quotes
        self.guess_handler = guess_handler(self.config.use_latest_reply)

    async def _start(self) -> None:
        self.logger.info("Starting up IRC bot")

        await super().start()

    async def event_ready(self) -> None:
        self.logger.info("Connected as %s", self.nick)
        self.logger.info("Requesting to join %s", self.config.channel)
        self.loop.create_task(self.join(), name="join-channel")

    async def event_reconnect(self) -> None:
        self.logger.info("Reconnect occurred")
        self.loop.create_task(self.join(), name="join-channel")

    async def join(self) -> None:
        await asyncio.sleep(5)
        self.logger.info("Joining channel %s", self.config.channel)
        await self.join_channels([self.config.channel])

    async def event_join(self, channel: Channel, user: User) -> None:
        if channel.name != self.config.channel:
            return
        if user.name.lower() != self.nick.lower():
            return

        target = self.get_channel(self.config.channel)

        if target:
            self.logger.info("Connected to channel %s", self.config.channel)
            await target.send("Never fear, Snerge is here!")

    async def event_message(self, message: Message) -> None:
        # Ignore loop-back messages
        if not message.author or message.author.name.lower() == self.nick.lower():
            return

        # Note when chat last happened
        self.last_message = int(self.loop.time())
        self.logger.debug("Saw a message at %d", self.last_message)

        if not (target := self.get_channel(self.config.channel)):
            return

        # Commands can only be processed by mods, when we can reply.
        chatter = target.get_chatter(message.author.name)

        if not isinstance(chatter, Chatter) or not message.author.is_mod:
            return

        # !snerge command: send a quote!
        content = message.content.lower()

        if content.startswith("!unoquote "):
            self.logger.info(message.content)

        if content == "!snerge" or content.startswith("!snerge "):
            self.logger.info("Manual Snerge by %s", message.author.name)
            await self.send_quote(content.replace("!snerge", "").strip())

    async def queue_quote(self) -> None:
        await self.connect()

        while not self._stop:
            # If we haven't managed to connect to the channel, wait a while.
            if not self.get_channel(self.config.channel):
                next_call = random.randint(*self.config.startup_probe)
                self.logger.info("No target initialised, waiting %d seconds", next_call)

            # If we haven't heard from chat in a while, assume the stream is down
            elif self.loop.time() - self.last_message > self.config.chat_active_probe[0]:
                next_call = random.randint(*self.config.chat_active_probe)
                self.logger.debug("Chat not active, waiting %d seconds", next_call)

            # Otherwise, send off a quote
            else:
                await self.send_quote()
                next_call = random.randint(*self.config.auto_quote_time)

            # Queue the next attempt to send a quote
            await self.sleep(next_call)

        await self.close()

    async def sleep(self, time: int) -> None:
        target_time = self.loop.time() + time

        while True:
            if self._stop:
                return

            sleep_for = min(10.0, target_time - self.loop.time())

            if sleep_for <= 0:
                return

            await asyncio.sleep(sleep_for)

    async def send_quote(self, prompt: str | None = None) -> None:
        if not (target := self.get_channel(self.config.channel)):
            return

        quote = get_quote(self.quotes, *self.config.quote_length, prompt)

        self.logger.info("Sending quote %s", quote)

        # There is a 0.5% chance of Snerge going UwU!
        if random.randint(0, 200) == 0:
            await target.send("~UωU~ " + owo_magic(quote) + " ~UωU~")
        else:
            await target.send("sergeSnerge " + quote + " sergeSnerge")

    def request_stop(self) -> None:
        self._stop = True

    async def close(self) -> None:
        if target := self.get_channel(self.config.channel):
            await target.send("sergeSnerge Sleepy time!")

        await super().close()


def get_quote(
    quotes: ProseGen, min_length: int, max_length: int, prompt: str | None = None
) -> str:
    initial_tokens = [
        x for x in Fact(prompt or "", "chat").tokens if x and x in quotes.dictionary
    ]

    # Max 100 attempts to generate a quote
    for _ in range(100):
        generator = GeneratedQuote(quotes, min_length)
        for token in initial_tokens:
            generator.append_token(token)

        wisdom = generator.make_statement()

        if min_length < len(wisdom) < max_length:
            return wisdom

    return "I don't like coffee."


def owo_magic(non_owo_string: str) -> str:
    """
    Converts a non_owo_string to an owo_string

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


async def main() -> None:
    from snerge import config, token, quotes  # pylint: disable=import-outside-toplevel

    log.init()
    logger = log.get_logger()

    app = token.refresh_app_token()
    data = await quotes.load_data(logger, ProseGen(20))

    # Create the IRC bot
    bot = Bot(
        logger=logger,
        loop=asyncio.get_event_loop(),
        app=app,
        config=config.config(),
        quotes=data,
    )

    await bot.start()


if __name__ == "__main__":
    asyncio.run(main())
