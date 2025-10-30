#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

import asyncio
import csv

from prosegen import ProseGen
from snerge import log


async def load_data(logger: log.Logger, instance: ProseGen) -> ProseGen:
    await asyncio.gather(
        load_sergisms(logger, instance),
        load_uno_quotes(logger, instance, "quotes.csv"),
        load_lrr_quotes(logger, instance),
    )
    return instance


async def load_uno_quotes(logger: log.Logger, instance: ProseGen, file: str) -> None:
    logger.info("Loading quotes from Uno-db")
    line: dict[str, str]
    count = 0

    with open(file, "r", encoding="utf-8") as quotes:
        reader = csv.DictReader(quotes)

        for line in reader:
            count += 1
            instance.add_knowledge(line["quote"].strip('"'), f"Uno #{line['id']}")

    logger.info("Added %d Uno quotes", count)


async def load_sergisms(logger: log.Logger, instance: ProseGen) -> None:
    logger.info("Loading quotes from Sergisms")
    line: dict[str, str]
    count = 0

    with open("sergisms.csv", "r", encoding="utf-8") as quotes:
        reader = csv.DictReader(quotes)

        for line in reader:
            count += 1
            instance.add_knowledge(line["quote"].strip('"'), f"Sergisms #{line['id']}")

    logger.info("Added %d Sergisms", count)


async def load_lrr_quotes(logger: log.Logger, instance: ProseGen | None) -> None:
    logger.info("Loading quotes from LRR")
    line: dict[str, str]
    count = 0

    with open("serge-lrr.csv", "r", encoding="utf-8") as quotes:
        reader = csv.DictReader(quotes)

        for line in reader:
            count += 1
            instance.add_knowledge(line["quote"].strip('"'), f"LRR #{line['id']}")

    logger.info("Added %d LRR quotes", count)
