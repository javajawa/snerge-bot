#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

import logging
import sys

try:
    from systemd.journal import JournalHandler  # type: ignore # pylint: disable=import-error
except ImportError:
    pass

Logger = logging.Logger


def init() -> None:
    logger = logging.getLogger("snerge")

    if sys.stdout.isatty():
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(name)s:%(levelname)s] %(message)s", datefmt="%H:%M:%S"
            )
        )
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
    else:
        handler = JournalHandler(SYSLOG_IDENTIFIER="snerge-bot")
        handler.setFormatter(logging.Formatter("[%(name)s:%(levelname)s] %(message)s"))

        logger.addHandler(handler)
        logger.setLevel(logging.INFO)


def get_logger(name: str = "") -> logging.Logger:
    if not name:
        return logging.getLogger("snerge")

    return logging.getLogger("snerge." + name)
