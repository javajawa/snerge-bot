#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

import asyncio
import csv

import aiohttp
from bs4 import BeautifulSoup, Tag, NavigableString

from snerge import log


async def download_lrr_quotes(logger: log.Logger) -> None:
    with open("serge-lrr.csv", "w", encoding="utf-8") as quotes:
        writer = csv.DictWriter(quotes, ("id", "date", "author", "quote"))
        async with aiohttp.ClientSession() as session:
            calls = (
                load_lrr_quote_page(logger, session, writer, page, 9500)
                for page in range(1, 19)
            )
            await asyncio.gather(*calls)


async def load_lrr_quote_page(  # pylint: disable=too-many-locals
    logger: log.Logger,
    session: aiohttp.ClientSession,
    writer: csv.DictWriter[str],
    page: int,
    max_id: int,
) -> None:
    logger.info("Loading LRR quote page %d", page)
    html = await session.get(
        f"https://lrrbot.com/quotes/search?q=serge&mode=name&page={page}"
    )
    soup = BeautifulSoup(await html.text(), "html.parser")

    quotes = soup.find("ol", class_="quotes")
    count = 0

    if not quotes or not isinstance(quotes, Tag):
        return

    for quote in quotes.find_all("li"):
        quote_id = quote.find(class_="num").text

        if int(quote_id.strip(" #")) <= max_id:
            return

        quote_text = str(quote.find("blockquote").text).strip()

        attrib = quote.find("div", class_="attrib")
        attrib_text = " ".join(
            " ".join(element.text.lstrip("—").strip().split())
            for element in attrib
            if isinstance(element, NavigableString)
        ).strip()
        date_elem = attrib.find("span", class_="date")
        date = date_elem.text.strip("[]") if date_elem else "no date"

        if attrib_text == "Serge" or attrib_text.startswith("Serge, "):
            count += 1
            writer.writerow(
                {"id": quote_id, "date": date, "author": attrib_text, "quote": quote_text}
            )

    logger.info("Added %d LRR quotes from page %d", count, page)


if __name__ == "__main__":
    asyncio.run(download_lrr_quotes(logger=log.Logger(__name__)))
