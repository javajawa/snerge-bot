# SPDX-FileCopyrightText: 2026 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

from typing import TYPE_CHECKING

import pathlib
import random
import re

from prosegen import Fact, GeneratedQuote, ProseGen

if TYPE_CHECKING:
    from logging import Logger

    from snerge.config import Config
    from snerge.util.twitch_stubs import TwitchChatEvent


CONTRACTIBLE = re.compile(r" (old|just|of|[a-z]{3,6}ing)[^a-z]")
CONTRACT_IS = re.compile(r" ([a-z]+) is ")
FRIEND = re.compile(r" friend ?")

SUBSCRIPTIONS = {
    "snerge",
    "snerge facts",
    "snergefacts",
    "serge facts",
    "sergefacts",
}


class SnergeHandler:
    logger: Logger
    config: Config
    subscribers: pathlib.Path
    data: ProseGen

    def __init__(self, logger: Logger, config: Config, data: ProseGen) -> None:
        self.logger = logger
        self.config = config
        self.data = data
        self.subscribers = pathlib.Path("subscribed")
        self.subscribers.mkdir(exist_ok=True, parents=True)

    def quote(self, prompt: str | None = None, *, force_owo: bool = False) -> str:
        quote = self.get_quote(prompt)
        return self.make_cute(quote, force_owo=force_owo)

    def get_quote(self, prompt: str | None = None) -> str:
        initial_tokens = [
            x for x in Fact(prompt or "", "chat").tokens if x and x in self.data.dictionary
        ]

        # Max 100 attempts to generate a quote
        for _ in range(100):
            generator = GeneratedQuote(self.data, self.config.quote_length[0])
            for token in initial_tokens:
                generator.append_token(token)

            wisdom = generator.make_statement()

            if self.config.quote_length[0] < len(wisdom) < self.config.quote_length[1]:
                return wisdom

        return "I don't like coffee."

    def make_cute(self, quote: str, *, force_owo: bool) -> str:
        # Add in the accent.
        if chance(one_in=10):
            quote = CONTRACTIBLE.sub(contract, quote)
        if chance(one_in=5):
            quote = CONTRACT_IS.sub(contract_is, quote)
        if chance(one_in=5):
            quote = FRIEND.sub(" sergeFriend ", quote)

        # There is a 0.5% chance of Snerge going UwU!
        if force_owo or chance(one_in=120):
            return "~UωU~ " + owo_magic(quote) + " ~UωU~"

        # Shorter quotes have a 2.5% chance for an Oh nyo~
        if len(quote) < self.config.quote_length[1] - 20 and chance(one_in=40):
            quote = quote + "  ✧･ﾟ. Oh nyo~! :3 *･ﾟ✧"

        return "sergeSnerge " + quote + " sergeSnerge"

    def subscribe(self, message: TwitchChatEvent) -> str | None:
        topic = message["message"]["text"].split(" ", maxsplit=1)
        if len(topic) == 1 or topic[1] not in SUBSCRIPTIONS:
            return None

        marker = self.subscribers / message["chatter_user_login"]

        if marker.exists():
            return "You are already subscribed to SnergeFacts."

        marker.touch(exist_ok=True)

        return (
            f"Thank you {message['chatter_user_name']} for subscribing to SnergeFacts! "
            f"Here's a special SnergeFact for you: {self.quote()}"
        )


def chance(*, one_in: int) -> bool:
    return random.randint(0, one_in - 1) == 0  # noqa: S311 not cryptography


def owo_magic(non_owo_string: str) -> str:
    """
    Converts a non_owo_string to an owo_string.

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


def contract(g: re.Match[str]) -> str:
    x = g.group(0)
    return x[:-2] + "'" + x[-1]


def contract_is(g: re.Match[str]) -> str:
    return f" {g.group(1)}'s "
