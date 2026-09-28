# SPDX-FileCopyrightText: 2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

from typing import TYPE_CHECKING

import csv
import pathlib

from .handler import SnergeHandler

if TYPE_CHECKING:
    import logging

    from prosegen import ProseGen


def load_data(logger: logging.Logger, instance: ProseGen) -> ProseGen:
    load_sergisms(logger, instance)
    load_uno_quotes(logger, instance)
    load_lrr_quotes(logger, instance)
    return instance


def load_uno_quotes(logger: logging.Logger, instance: ProseGen) -> None:
    logger.info("Loading quotes from Uno-db")
    line: dict[str, str]
    count = 0

    with pathlib.Path("quotes/quotes.csv").open("r", encoding="utf-8") as quotes:
        reader = csv.DictReader(quotes)

        for line in reader:
            count += 1
            instance.add_knowledge(line["quote"].strip('"'), f"Uno #{line['id']}")

    logger.info("Added %d Uno quotes", count)


def load_sergisms(logger: logging.Logger, instance: ProseGen) -> None:
    logger.info("Loading quotes from Sergisms")
    line: dict[str, str]
    count = 0

    with pathlib.Path("quotes/sergisms.csv").open("r", encoding="utf-8") as quotes:
        reader = csv.DictReader(quotes)

        for line in reader:
            count += 1
            instance.add_knowledge(line["quote"].strip('"'), f"Sergisms #{line['id']}")

    logger.info("Added %d Sergisms", count)


def load_lrr_quotes(logger: logging.Logger, instance: ProseGen) -> None:
    logger.info("Loading quotes from LRR")
    line: dict[str, str]
    count = 0

    with pathlib.Path("quotes/serge-lrr.csv").open("r", encoding="utf-8") as quotes:
        reader = csv.DictReader(quotes)

        for line in reader:
            count += 1
            instance.add_knowledge(line["quote"].strip('"'), f"LRR #{line['id']}")

    logger.info("Added %d LRR quotes", count)


__all__ = "SnergeHandler", "load_data"
