#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

import csv

from prosegen import ProseGen
from snerge import log


def load_data(logger: log.Logger, instance: ProseGen) -> ProseGen:
    load_sergisms(logger, instance)
    load_uno_quotes(logger, instance)
    load_lrr_quotes(logger, instance)
    return instance


def load_uno_quotes(logger: log.Logger, instance: ProseGen) -> None:
    logger.info("Loading quotes from Uno-db")
    line: dict[str, str]
    count = 0

    with open("quotes/quotes.csv", "r", encoding="utf-8") as quotes:
        reader = csv.DictReader(quotes)

        for line in reader:
            count += 1
            instance.add_knowledge(line["quote"].strip('"'), f"Uno #{line['id']}")

    logger.info("Added %d Uno quotes", count)


def load_sergisms(logger: log.Logger, instance: ProseGen) -> None:
    logger.info("Loading quotes from Sergisms")
    line: dict[str, str]
    count = 0

    with open("quotes/sergisms.csv", "r", encoding="utf-8") as quotes:
        reader = csv.DictReader(quotes)

        for line in reader:
            count += 1
            instance.add_knowledge(line["quote"].strip('"'), f"Sergisms #{line['id']}")

    logger.info("Added %d Sergisms", count)


def load_lrr_quotes(logger: log.Logger, instance: ProseGen) -> None:
    logger.info("Loading quotes from LRR")
    line: dict[str, str]
    count = 0

    with open("quotes/serge-lrr.csv", "r", encoding="utf-8") as quotes:
        reader = csv.DictReader(quotes)

        for line in reader:
            count += 1
            instance.add_knowledge(line["quote"].strip('"'), f"LRR #{line['id']}")

    logger.info("Added %d LRR quotes", count)


def main() -> None:
    # Configure logging
    log.init()
    logger = log.get_logger("download")

    dataset = load_data(logger, ProseGen(8))

    for word, data in dataset.dictionary.items():
        sources = sorted(datum.source for datum in data)
        print(word, len(data), " ".join(sources), sep="\t")


if __name__ == "__main__":
    main()
