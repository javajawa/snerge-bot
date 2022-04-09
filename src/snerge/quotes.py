#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

from typing import AsyncGenerator, List, Tuple

import asyncio
import json

import aiohttp

from bs4 import BeautifulSoup, NavigableString, Tag

from prosegen import ProseGen
from snerge import logging
from snerge.util import SetEncoder


StringGen = AsyncGenerator[Tuple[str, str], None]


async def load_data(logger: logging.Logger, instance: ProseGen) -> ProseGen:
    async with aiohttp.ClientSession() as session:
        quotes = 0
        async for qid, quote in load_uno_quotes(logger, session):
            quotes += 1
            instance.add_knowledge(quote, source=f"uno line {qid}")
        logger.info("Added %d Uno quotes", quotes)

        quotes = 0
        async for qid, quote in load_lrr_quotes(logger, session):
            quotes += 1
            instance.add_knowledge(quote, source=f"lrr {qid}")
        logger.info("Added %d LRR quotes", quotes)

    return instance


async def load_uno_quotes(
    logger: logging.Logger, session: aiohttp.ClientSession
) -> StringGen:
    logger.info("Loading quotes from Uno-db")
    data = await session.get(
        "https://raw.githubusercontent.com/RebelliousUno/BrewCrewQuoteDB/main/quotes.txt"
    )

    qid = 0
    for line in (await data.text()).split("\n"):
        qid += 1
        line = line.strip()

        if not line:
            continue

        line_quotes = line.split('"')[1:]

        for quote, attr in zip(*[iter(line_quotes)] * 2):
            if "Serge" in attr or "Snerge" in attr:
                yield str(qid), str(quote)


async def load_lrr_quotes(
    logger: logging.Logger, session: aiohttp.ClientSession
) -> StringGen:
    exclude = []

    with open("moderate.txt", "rt", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            _id, _ = line.split(" ", 1)
            exclude.append(_id)

    logger.info("Added %d quotes to the LRR exclude list", len(exclude))

    for page in range(1, 16):
        async for quote_id, quote in load_lrr_quote_page(logger, session, page, exclude):
            yield quote_id, quote


async def load_lrr_quote_page(
    logger: logging.Logger, session: aiohttp.ClientSession, page: int, exclude: List[str]
) -> StringGen:
    logger.info("Loading LRR quote page %d", page)
    html = await session.get(
        f"https://lrrbot.com/quotes/search?q=serge&mode=name&page={page}"
    )
    soup = BeautifulSoup(await html.text(), "html.parser")

    quotes = soup.find("ol", class_="quotes")

    if not quotes or not isinstance(quotes, Tag):
        return

    for quote in quotes.find_all("li"):
        quote_id = quote.find(class_="num").text

        if quote_id in exclude:
            continue

        quote_text = quote.find("blockquote").text

        attrib = quote.find("div", class_="attrib")
        attrib_text = "".join(
            element for element in attrib if isinstance(element, NavigableString)
        )
        attrib_text = attrib_text.strip("—").strip()

        if attrib_text == "Serge":
            yield quote_id, quote_text


async def main() -> None:
    logging.init()
    logger = logging.get_logger()
    session = aiohttp.ClientSession()

    with open("loaded_lrr_quotes.txt", "wt", encoding="utf-8") as handle:
        async for quote_id, quote in load_lrr_quotes(logger, session):
            handle.write(f"{quote_id}, {quote}\n")

    dataset = ProseGen(20)
    asyncio.run(load_data(logger, dataset))

    with open("parsed_state.json", "wt", encoding="utf-8") as handle:
        json.dump(dataset.dictionary, handle, cls=SetEncoder)


if __name__ == "__main__":
    asyncio.run(main())
