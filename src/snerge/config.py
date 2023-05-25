#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

from typing import Tuple

import dataclasses


@dataclasses.dataclass
class Config:
    channel: str
    startup_probe: Tuple[int, int]
    chat_active_probe: Tuple[int, int]
    auto_quote_time: Tuple[int, int]
    quote_length: Tuple[int, int]


def config() -> Config:
    # The time until retry after when we lack a functional connection to Twitch
    backoff_startup = (10, 10)
    # How recently someone must have messaged for the channel to be considered active.
    # Also the time until retry wait when no-one has talked recently
    backoff_no_chatters = (300, 300)
    # How long to wait between sending quotes
    backoff_message_sent = (1500, 2100)
    # How long a quote should be (to prevent one word quotes and sentences that
    # fill the entire screen).
    message_length = (24, 100)

    return Config(
        "sergeyager",
        backoff_startup,
        backoff_no_chatters,
        backoff_message_sent,
        message_length,
    )
