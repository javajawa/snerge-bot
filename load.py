#!/usr/bin/env python3
# vim: nospell expandtab ts=4

# SPDX-FileCopyrightText: 2020 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

from typing import Generator, List, Tuple

import requests

from bs4 import BeautifulSoup, NavigableString  # type: ignore

import prosegen


ProseGen = prosegen.ProseGen


def load_data() -> ProseGen:
    instance = prosegen.ProseGen(20)

    for quote in load_uno_quotes():
        instance.add_knowledge(quote)

    for _, quote in load_lrr_quotes():
        instance.add_knowledge(quote)

    return instance


def load_uno_quotes() -> Generator[str, None, None]:
    data = requests.get(
        "https://raw.githubusercontent.com/RebelliousUno/BrewCrewQuoteDB/main/quotes.txt"
    )

    for line in data.text.split("\n"):
        line = line.strip()

        if not line:
            continue

        line_quotes = line.split('"')[1:]

        for quote, attr in zip(*[iter(line_quotes)] * 2):
            if "Serge" in attr or "Snerge" in attr:
                yield quote


def load_lrr_quotes() -> Generator[Tuple[str, str], None, None]:
    exclude = []

    with open("moderate.txt", "rt") as handle:
        for line in handle:
            line = line.strip()
            _id, _ = line.split(" ", 1)
            exclude.append(_id)

    for page in range(1, 14):
        yield from load_lrr_quote_page(page, exclude)


def load_lrr_quote_page(
    page: int, exclude: List[str]
) -> Generator[Tuple[str, str], None, None]:
    html = requests.get(f"https://lrrbot.com/quotes/search?q=serge&mode=name&page={page}")
    soup = BeautifulSoup(html.content, "html.parser")

    quotes = soup.find("ol", class_="quotes")

    if not quotes:
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


def main() -> None:
    with open("loaded_lrr_quotes.txt", "wt") as handle:
        for quote_id, quote in load_lrr_quotes():
            handle.write(f"{quote_id}, {quote}\n")


if __name__ == "__main__":
    main()
