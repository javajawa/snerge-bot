#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

from typing import AsyncGenerator, List, Tuple

import asyncio
import csv
import json
import re

import aiohttp

from aiostream import stream  # type: ignore
from bs4 import BeautifulSoup, NavigableString, Tag

from prosegen import ProseGen
from snerge import log
from snerge.util import SetEncoder


StringGen = AsyncGenerator[Tuple[str, str], None]


async def load_data(logger: log.Logger, instance: ProseGen) -> ProseGen:
    async with aiohttp.ClientSession() as session:
        quotes = 0
        async for qid, quote in load_uno_quotes(logger):
            quotes += 1
            instance.add_knowledge(quote, source=f"Uno #{qid}")
        logger.info("Added %d Uno quotes", quotes)

        quotes = 0
        async for qid, quote in load_lrr_quotes(logger, session):
            quotes += 1
            instance.add_knowledge(quote, source=f"LRR #{qid}")
        logger.info("Added %d LRR quotes", quotes)

    return instance


async def load_uno_quotes(logger: log.Logger) -> StringGen:
    logger.info("Loading quotes from Uno-db")
    line: dict[str, str]

    with open("quotes.csv", "r", encoding="utf-8") as quotes:
        reader = csv.DictReader(quotes)

        for line in reader:
            yield line["id"], line["quote"].strip('"')


async def load_lrr_quotes(logger: log.Logger, session: aiohttp.ClientSession) -> StringGen:
    exclude = []

    with open("moderate.txt", "rt", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            _id, _ = line.split(" ", 1)
            exclude.append(_id)

    logger.info("Added %d quotes to the LRR exclude list", len(exclude))

    combined = stream.merge(
        *[load_lrr_quote_page(logger, session, page, exclude) for page in range(1, 18)]
    )
    async with combined.stream() as streamer:
        async for quote_id, quote in streamer:
            yield quote_id, quote


async def load_lrr_quote_page(
    logger: log.Logger, session: aiohttp.ClientSession, page: int, exclude: List[str]
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


async def download_new_quote_list(session: aiohttp.ClientSession) -> None:
    response = await session.get(
        "https://raw.githubusercontent.com/RebelliousUno/BrewCrewQuoteDB/main/quotes.csv"
    )

    data = (await response.text(encoding="utf-8")).split("\n")

    line: dict[str, str]
    reader = csv.DictReader(data[1:], next(csv.reader([data[0]])), escapechar=None)
    matcher = re.compile(r'"\\s*-\\s*[^,]+,')

    with open("quotes.csv", "w", encoding="utf-8") as quotes:
        writer = csv.DictWriter(quotes, ["id", "date", "author", "quote"])
        writer.writeheader()
        for line in reader:
            if line["id"] == "'-1":
                continue

            # Fix up double CSV-quoting by reparsing the fields.
            line = {k: next(csv.reader([v], escapechar=None))[0] for k, v in line.items()}

            author = line["author"].lower()

            # ignore anything with multiple attributions.
            if " and " in author or matcher.match(line["quote"]):
                continue

            # Ignore anything not from Serge (or feedback from Snerge)
            if not author.startswith(("serge", "snerge")):
                continue

            # Ignore purely action lines
            if '"' not in line["quote"]:
                continue

            # Sometimes people use fancy quotes
            line["quote"] = line["quote"].replace("’", "'")
            line["quote"] = clean_quote(line["quote"]) or ""

            if line["quote"]:
                writer.writerow(line)


def clean_quote(quote: str) -> str | None:
    leading_action = re.compile(r'^\\*[^*"]+\\* ("[^"]+")$')
    trailing_action = re.compile(r'^("[^"]+") \\*[^*"]+\\*$')

    trailer = trailing_action.match(quote)
    leader = leading_action.match(quote)

    if trailer:
        return trailer.group(1) if len(trailer.group(1)) > 24 else None

    if leader:
        return leader.group(1) if len(leader.group(1)) > 24 else None

    return quote


async def main() -> None:
    log.init()
    logger = log.get_logger()

    async with aiohttp.ClientSession() as session:
        with open("loaded_lrr_quotes.txt", "wt", encoding="utf-8") as handle:
            async for quote_id, quote in load_lrr_quotes(logger, session):
                handle.write(f"{quote_id}, {quote}\n")

    dataset = ProseGen(20)
    await load_data(logger, dataset)

    with open("parsed_state.json", "wt", encoding="utf-8") as handle:
        json.dump(dataset.dictionary, handle, cls=SetEncoder, indent=2)


if __name__ == "__main__":
    asyncio.run(main())
