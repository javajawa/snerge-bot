#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2020 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

from typing import Awaitable, Callable

import asyncio
import os.path
import random
import re

from twitchio import Client, Channel, Chatter, Message, User  # type: ignore
import twitchio.client  # type: ignore

from snerge import log
from snerge.config import Config
from snerge.token import App
from snerge.guessmessagehandler import GuessMessageHandler
from prosegen import ProseGen, Fact, GeneratedQuote

CONTRACTABLE = re.compile(" (old|just|of|[a-z]{3,6}ing)[^a-z]")
CONTRACT_IS = re.compile(" ([a-z]+) is ")


def contract(g: re.Match[str]) -> str:
    x = g.group(0)
    return x[:-2] + "'" + x[-1]


def contract_is(g: re.Match[str]) -> str:
    return f" {g.group(1)}'s "


class Bot(Client):  # type: ignore
    config: Config
    quotes: ProseGen
    guess_handler: GuessMessageHandler
    commands: dict[str, tuple[bool, Callable[[Channel, str], Awaitable[None]]]]

    last_message: int = 0
    _stop: bool = False

    def __init__(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        logger: log.Logger,
        loop: asyncio.AbstractEventLoop,
        config: Config,
        app: App,
        quotes: ProseGen,
    ) -> None:
        super().__init__(token=app.irc_token, loop=loop)

        self.logger = logger
        self.config = config
        self.quotes = quotes
        self.guess_handler = GuessMessageHandler(
            self.config.use_latest_reply,
            self.config.stopguess_delay,
            self.config.closest_without_going_over,
        )

        self.commands = {
            "!guesscommands": (True, self.guess_handler.guess_commands),
            "!startguessing": (True, self.guess_handler.start_guessing),
            "!stopguessing": (True, self.guess_handler.stop_guessing),
            "!score": (True, self.guess_handler.score),
            "!stats": (True, self.guess_handler.stats),
            "!snerge": (True, lambda _, prompt: self.send_quote(prompt)),
            "!snuwuge": (True, lambda _, prompt: self.send_quote(prompt, force_owo=True)),
            "!subscribe": (False, self.subscribe),
            "!unsubscribe": (False, self.subscribe),
        }

        twitchio.client.logger = logger.getChild("client")

    async def _start(self) -> None:
        self.logger.info("Starting up IRC bot")

        await super().start()

    async def event_ready(self) -> None:
        self.logger.info("Connected as %s", self.nick)
        self.logger.info("Requesting to join %s", self.config.channel)
        self.loop.create_task(self.join(), name="join-channel")

    async def event_reconnect(self) -> None:
        self.logger.info("Reconnect occurred")
        self.loop.call_later(
            10, lambda: self.loop.create_task(self.join(), name="join-channel")
        )

    async def join(self) -> None:
        await asyncio.sleep(5)
        self.logger.info("Joining channel %s", self.config.channel)
        await self.join_channels([self.config.channel])

    async def event_join(self, channel: Channel, user: User) -> None:
        if channel.name != self.config.channel:
            return
        if user.name.lower() != self.nick.lower():
            return

        self.logger.info("Connected to channel %s", self.config.channel)
        await channel.send("Never fear, Snerge is here!")

    async def event_message(self, message: Message) -> None:
        # Ignore loop-back messages
        if message.echo:
            return

        # Note when chat last happened
        self.last_message = int(self.loop.time())
        self.logger.debug("Saw a message at %d", self.last_message)

        if not (target := self.get_channel(self.config.channel)):
            return

        chatter = target.get_chatter(message.author.name)
        if not isinstance(chatter, Chatter):
            return

        # Run the guess handler,
        await self.guess_handler.message_process(message, chatter)

        command, _, content = str(message.content).partition(" ")
        command = command.lower()

        if command not in self.commands:
            return

        need_mod, call = self.commands[command]

        if need_mod and not (
            chatter.is_mod
            or chatter.is_broadcaster
            or message.author.name == "thirsty_kitteh"
        ):
            return

        self.logger.info("Command %s from %s", command, chatter.display_name)
        await call(message.channel, content)

    async def subscribe(self, chatter: Chatter, topic: str) -> None:
        if topic not in [
            "snerge",
            "snerge facts",
            "snergefacts",
            "serge facts",
            "sergefacts",
        ]:
            return

        if os.path.exists(os.path.join("subscribed", chatter.name)):
            await chatter.send("You are already subscribed to SnergeFacts.")
            return

        if not (target := self.get_channel(self.config.channel)):
            return

        with open(os.path.join("subscribed", chatter.name), "w", encoding="utf-8"):
            pass

        await target.send(
            (
                f"Thank you {chatter.name} for subscribing to SnergeFacts! "
                "Here's a special SnergeFact for you!"
            )
        )
        await self.send_quote()

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

    async def send_quote(self, prompt: str | None = None, force_owo: bool = False) -> None:
        if not (target := self.get_channel(self.config.channel)):
            return

        quote = get_quote(self.quotes, *self.config.quote_length, prompt)
        quote = self.cuteify(quote, force_owo)

        self.logger.info("Sending quote %s", quote)

        await target.send(quote)

    def cuteify(self, quote: str, force_owo: bool) -> str:
        # Add in the accent.
        if random.randint(0, 10) == 0:
            quote = CONTRACTABLE.sub(contract, quote)
        if random.randint(0, 5) == 0:
            quote = CONTRACT_IS.sub(contract_is, quote)

        # There is a 0.5% chance of Snerge going UwU!
        if force_owo or random.randint(0, 200) == 0:
            return "~UωU~ " + owo_magic(quote) + " ~UωU~"

        # Shorter quotes have a 2.5% chance for an Oh nyo~
        if len(quote) < self.config.quote_length[1] - 20 and random.randint(0, 40) == 0:
            quote = quote + "  ✧･ﾟ. Oh nyo~! :3 *･ﾟ✧"

        return "sergeSnerge " + quote + " sergeSnerge"

    def request_stop(self) -> None:
        self._stop = True

    async def close(self) -> None:
        if target := self.get_channel(self.config.channel):
            await target.send("sergeSnerge Sleepy time!")

        self._closing.set()
        await asyncio.sleep(2)
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
    loop = asyncio.get_event_loop()

    app = token.refresh_app_token()
    data = await loop.run_in_executor(None, quotes.load_data, logger, ProseGen(20))

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
