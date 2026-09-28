# SPDX-FileCopyrightText: 2023 Kitsune
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

import asyncio
import re
from enum import Enum

from snerge.util import KnownBadges

from .store import GuessStore

if TYPE_CHECKING:
    from snerge.util.twitch_stubs import TwitchChatEvent


Messages = AsyncGenerator[str]


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
    regexp_pattern = re.compile(r"^(?:!guess (?P<v1>.+)|(?P<v2>[-+]?\d+\.?\d*))")

    def __init__(
        self,
        *,
        use_latest_reply: bool,
        stopguess_delay: int,
        closest_without_going_over: bool,
    ) -> None:
        self.use_latest_reply = use_latest_reply
        self.stopguess_delay = stopguess_delay
        self.closest_without_going_over = closest_without_going_over
        self.guesses = GuessStore(use_latest_reply=self.use_latest_reply)
        self.bot_state = GuessHandlerBotState.NOT_PROCESSING
        self.reset_guesses()

    async def message_process(self, message: TwitchChatEvent) -> Messages:
        text = message["message"]["text"]
        name = message["chatter_user_name"]
        moderator = (
            KnownBadges.MOD in message["badges"] or KnownBadges.STREAMER in message["badges"]
        )

        if moderator and text.startswith("!guess") and (call := await self._mod_action(text)):
            async for msg in call:
                yield msg
            return

        if self.bot_state != GuessHandlerBotState.COLLECTING_VALS:
            return

        match = self.regexp_pattern.search(text)

        if not match:
            return

        try:
            value = match.group("v1") or match.group("v2")
            value_int = int(value)
            if value_int < 0:
                yield f"{name} Positive whole numbers only please"
                return
        except ValueError:
            yield f"{name} Positive whole numbers only please"
            return

        # Feed to guess handler
        self.guesses.accept_guess(name, value_int)

    async def _mod_action(self, text: str) -> Messages | None:
        if text.startswith("!guess score "):
            _, _, val = text.partition(" ")
            return self.score(val)
        match text:
            case "!guess start":
                return self.start_guessing()
            case "!guess stop":
                return self.stop_guessing()
            case "!guess stats":
                return self.stats()
            case "!guess help":
                return self.guess_commands()

        return None

    def reset_guesses(self) -> None:
        self.guesses = GuessStore(use_latest_reply=self.use_latest_reply)

    # Commands
    async def start_guessing(self) -> Messages:
        if self.bot_state == GuessHandlerBotState.NOT_PROCESSING:
            self.reset_guesses()
            self.bot_state = GuessHandlerBotState.COLLECTING_VALS
            yield "Give guesses now! Positive integers only!"
        elif self.bot_state == GuessHandlerBotState.HOLDING_FOR_ANSWER:
            yield "Still waiting to give an answer!"

    async def stop_guessing(self) -> Messages:
        if self.bot_state != GuessHandlerBotState.COLLECTING_VALS:
            return

        yield "Guessing window closed"
        await asyncio.sleep(self.stopguess_delay)
        self.bot_state = GuessHandlerBotState.HOLDING_FOR_ANSWER

        async for msg in self.stats():
            yield msg

    async def score(self, scoreval: str) -> Messages:
        if self.bot_state == GuessHandlerBotState.COLLECTING_VALS:
            yield "Please call !stopguessing before asking for a score"
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
        result_names, result_values = self.guesses.get_score(
            scoreval_int,
            closest_without_going_over=self.closest_without_going_over,
        )

        pre_msg = "Winners without going over: " if self.closest_without_going_over else "Winners: "

        # Answer given, reset state.
        self.bot_state = GuessHandlerBotState.NOT_PROCESSING

        yield (
            pre_msg
            + ", ".join(result_names)
            + ". Guesses of: "
            + ", ".join(map(str, result_values))
        )

    async def stats(self) -> Messages:
        stats = self.guesses.stats()
        message = (
            f"{stats['count']} results between {stats['min']}-{stats['max']}. "
            f"Mean:{stats['mean']}, StDev:{stats['stdev']:.1f}. Median:{stats['median']}"
        )

        yield message

    @staticmethod
    async def guess_commands() -> Messages:
        prefix = "!guess "
        yield (
            f"Valid commands are {prefix}start, {prefix}stop, "
            f"{prefix}score <result>, {prefix}stats."
        )
