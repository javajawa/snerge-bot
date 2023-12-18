from __future__ import annotations

import asyncio
import re
from enum import Enum

from twitchio import Message, Chatter, Channel  # typing: ignore

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

    async def message_process(self, message: Message, channel: Channel) -> bool:
        # Only do full message check if in recording mode
        if self.bot_state == GuessHandlerBotState.COLLECTING_VALS:
            if self.is_guess(message.content):
                await self.record_guess(message.author.name, message.content, channel)
                return True
            elif message.content.lower().startswith("!guess "):
                await self.record_guess(
                    message.author.name, message.content[len("!guess ") :], channel
                )
                return True

        if self.is_elevated_permissions(message.author):
            content = message.content
            if content == "!startguessing" or content.startswith("!startguessing "):
                await self.startguessing(channel)
                return True
            elif content == "!stopguessing" or content.startswith("!stopguessing "):
                await self.stopguessing(channel)
                return True
            elif content == "!score" or content.startswith("!score "):
                await self.score(channel, content[len("!score ") :])
                return True
            elif content == "!stats" or content.startswith("!stats "):
                await self.stats(channel)
                return True
            elif content == "!guesscommands" or content.startswith("!guesscommands "):
                await self.guesscommands(channel)
                return True

        return False

    def is_guess(self, message: str) -> bool:
        # Is this a number?
        return self.regexp_pattern.search(message) is not None

    def reset_guesses(self) -> None:
        self.guesses = GuessStore(self.use_latest_reply)

    def is_elevated_permissions(self, author: Chatter) -> bool:
        return author.is_mod or author.is_broadcaster

    async def record_guess(
        self,
        name: str,
        message: str,
        channel: Channel,
        ping_name: str | None = None,
    ) -> None:
        """
        Check the value from "message" is a positive integer; report back if not.
        Two checks: Integer, and Positive
        Then hand over to guess handler.
        """
        if ping_name is None:
            ping_name = name

        try:
            value_int = int(self.regexp_pattern.match(message)[0])
        except ValueError:
            # self.logger.info(
            # f"Input message returned ValueError -  ({name}:{message}) - not an integer"
            # )
            await channel.send(f"@{ping_name} Positive whole numbers only please")
            return None
        except Exception:
            # self.logger.error(
            # f"Alternative error when handling message in record_guess ({name}:{message})"
            # )
            return None

        if value_int < 0:
            # self.logger.info("value_int error ({value}")
            # self.logger.error(
            # "Converting value to Input message is negative ({name}:{message})"
            # )
            await channel.send(f"@{ping_name} Positive whole numbers only please")
            return None

        # Feed to guess handler
        # self.logger.info(f"Recording guess {value_int} from {name}")
        self.guesses.accept_guess(name, value_int)
        return None

    # Commands
    async def startguessing(self, channel: Channel) -> None:
        if self.bot_state == GuessHandlerBotState.NOT_PROCESSING:
            self.reset_guesses()
            self.bot_state = GuessHandlerBotState.COLLECTING_VALS
            await channel.send("Give guesses now! Positive integers only!")
        else:
            # self.logger.warning("Tried to start guessing, but not in the correct state")
            pass

    async def stopguessing(self, channel: Channel) -> None:
        if self.bot_state == GuessHandlerBotState.COLLECTING_VALS:
            # self.logger.info(
            #    f"Asked to stop guessing. Going to delay by {self.config.stopguess_delay} seconds"
            # )
            await channel.send("Guessing window closed")
            await asyncio.sleep(self.stopguess_delay)
            # self.logger.info(f"Guessing window closed")
            self.bot_state = GuessHandlerBotState.HOLDING_FOR_ANSWER
            await self.stats(channel)
        else:
            # self.logger.warning("Tried to stop guessing, but not in the correct state")
            pass

    async def score(self, channel: Channel, scoreval: str) -> None:
        if self.bot_state == GuessHandlerBotState.COLLECTING_VALS:
            # self.logger.warning("Asked to make score, but still collecting.")
            await channel.send("Please call !stopguessing before asking for a score")
        else:
            # Convert
            try:
                scoreval_int = int(self.regexp_pattern.match(scoreval)[0] or "")
            except Exception:
                # Supress Error
                return None

            # Produce score in either case
            (result_names, result_values) = self.guesses.get_score(
                scoreval_int, self.closest_without_going_over
            )

            if self.closest_without_going_over:
                pre_msg = "Winners without going over: "
            else:
                pre_msg = "Winners: "

            message = (
                pre_msg
                + ", ".join(result_names)
                + ". Guesses of: "
                + str(result_values)[1:-1]
            )
            await channel.send(message)

    async def stats(self, channel: Channel) -> None:
        stats = self.guesses.stats()
        message = (
            f"{stats['count']} results between {stats['min']}-{stats['max']}."
            f"Mean:{stats['mean']}, StDev:{stats['stdev']:.1f}. Median:{stats['median']}"
        )

        # self.logger.info(f"Stats Message:{message}")
        await channel.send(message)

    async def guesscommands(self, channel: Channel) -> None:
        prefix = "!"
        await channel.send(
            f"{prefix}startguessing, {prefix}stopguessing, {prefix}score (result), {prefix}stats."
        )
