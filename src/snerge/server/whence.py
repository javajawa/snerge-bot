# SPDX-FileCopyrightText: 2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

from typing import TYPE_CHECKING

import json

from aiohttp.web import Request, Response

from .util import SetEncoder

if TYPE_CHECKING:
    from prosegen import ProseGen


class WhenceHandler:
    quotes: ProseGen

    def __init__(self, quotes: ProseGen) -> None:
        self.quotes = quotes

    async def handle_search(self, request: Request) -> Response:
        words = await request.text()

        output: dict[str, list[dict[str, str | list[str]]]] = {}
        tokens = self.quotes.dictionary.keys()

        for word in words.strip().split(" "):
            for token in tokens:
                if word.lower() in token.lower():
                    data = self.quotes.dictionary[token]
                    output[token] = [
                        {
                            "source": fact.source,
                            "text": fact.original,
                            "tokens": fact.tokens,
                        }
                        for fact in data
                    ]

        return Response(
            status=200,
            content_type="application/json",
            text=json.dumps(output, cls=SetEncoder),
        )
