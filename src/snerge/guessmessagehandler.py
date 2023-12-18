#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2023 Kitsune
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

import asyncio
import re
from enum import Enum

from twitchio import Message, Chatter, Channel  # type: ignore

from .guessstore import GuessStore


class GuessHandlerBotState(Enum):
    NOT_PROCESSING = 0
    COLLECTING_VALS = 1
    HOLDING_FOR_ANSWER = 2


class GuessMessageHandler:
    bot_state: GuessHandlerBotState
    guesses: GuessStore
    use_latest_reply: bool
    stopguess_delay: int
    closest_without_going_over: bool
    regexp_pattern = re.compile(r"^(?P<value>[-+]?\d+\.?\d*)")

    def __init__(
        self,
        use_latest_reply: bool = True,
        stopguess_delay: int = 5,
        closest_without_going_over: bool = False,
    ):
        self.use_latest_reply = use_latest_reply
        self.stopguess_delay = stopguess_delay
        self.closest_without_going_over = closest_without_going_over
        self.guesses = GuessStore(self.use_latest_reply)
        self.bot_state = GuessHandlerBotState.NOT_PROCESSING
        self.reset_guesses()

    async def message_process(self, message: Message, chatter: Chatter) -> None:
        if self.bot_state != GuessHandlerBotState.COLLECTING_VALS:
            return

        if self.is_guess(message.content):
            return await self.record_guess(chatter, message.content, message.channel)

        command, _, content = message.content.partition(" ")
        command = command.lower()

        if command == "!guess":
            await self.record_guess(chatter, content, message.channel)

    def is_guess(self, message: str) -> bool:
        # Is this a number?
        return self.regexp_pattern.search(message) is not None

    def reset_guesses(self) -> None:
        self.guesses = GuessStore(self.use_latest_reply)

    async def record_guess(self, name: Chatter, message: str, channel: Channel) -> None:
        """
        Check the value from "message" is a positive integer; report back if not.
        Two checks: Integer, and Positive
        Then hand over to guess handler.
        """

        if not (match := self.regexp_pattern.match(message)):
            await channel.send(f"{name.mention} Positive whole numbers only please")
            return

        try:
            value_int = int(match[0])
        except ValueError:
            await channel.send(f"{name.mention} Positive whole numbers only please")
            return

        if value_int < 0:
            await channel.send(f"{name.mention} Positive whole numbers only please")
            return

        # Feed to guess handler
        self.guesses.accept_guess(name.display_name, value_int)

    # Commands
    async def start_guessing(self, channel: Channel, _: str) -> None:
        if self.bot_state == GuessHandlerBotState.NOT_PROCESSING:
            self.reset_guesses()
            self.bot_state = GuessHandlerBotState.COLLECTING_VALS
            await channel.send("Give guesses now! Positive integers only!")
        elif self.bot_state == GuessHandlerBotState.HOLDING_FOR_ANSWER:
            await channel.send("Still waiting to give an answer!")

    async def stop_guessing(self, channel: Channel, _: str) -> None:
        if self.bot_state != GuessHandlerBotState.COLLECTING_VALS:
            return

        await channel.send("Guessing window closed")
        await asyncio.sleep(self.stopguess_delay)
        self.bot_state = GuessHandlerBotState.HOLDING_FOR_ANSWER
        await self.stats(channel, _)

    async def score(self, channel: Channel, scoreval: str) -> None:
        if self.bot_state == GuessHandlerBotState.COLLECTING_VALS:
            await channel.send("Please call !stopguessing before asking for a score")
            return

        # Convert
        try:
            match = self.regexp_pattern.match(scoreval)
            if not match:
                return
            scoreval_int = int(match[0])
        except ValueError:
            # Supress Error
            return

        # Produce score in either case
        (result_names, result_values) = self.guesses.get_score(
            scoreval_int, self.closest_without_going_over
        )

        if self.closest_without_going_over:
            pre_msg = "Winners without going over: "
        else:
            pre_msg = "Winners: "

        # Answer given, reset state.
        self.bot_state = GuessHandlerBotState.NOT_PROCESSING

        message = (
            pre_msg
            + ", ".join(result_names)
            + ". Guesses of: "
            + ", ".join(map(str, result_values))
        )
        await channel.send(message)

    async def stats(self, channel: Channel, _: str) -> None:
        stats = self.guesses.stats()
        message = (
            f"{stats['count']} results between {stats['min']}-{stats['max']}. "
            f"Mean:{stats['mean']}, StDev:{stats['stdev']:.1f}. Median:{stats['median']}"
        )

        await channel.send(message)

    @staticmethod
    async def guess_commands(channel: Channel, _: str) -> None:
        prefix = "!"
        await channel.send(
            f"{prefix}startguessing, {prefix}stopguessing, {prefix}score (result), {prefix}stats."
        )
