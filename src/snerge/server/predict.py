# SPDX-FileCopyrightText: 2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

from typing import Any

import json

from aiohttp.web import Request, Response

import prosegen.prosegen
from prosegen import ProseGen

from .util import SetEncoder


class PredictHandler:
    quotes: ProseGen
    mapping: list[Any]

    def __init__(self, quotes: ProseGen) -> None:
        self.quotes = quotes
        self.mapping = []

    async def get_dictionary(self, _: Request) -> Response:
        tokens: set[str] = set(self.quotes.dictionary.keys())

        return Response(
            status=200,
            content_type="application/json",
            text=json.dumps(tokens, cls=SetEncoder),
        )

    async def make_prediction(self, request: Request) -> Response:
        words = await request.text()

        initial_tokens = prosegen.prosegen.Fact(words, "")
        parsed_tokens: list[str] = []
        generator = prosegen.prosegen.GeneratedQuote(self.quotes, 30)

        for token in initial_tokens.tokens:
            if token not in self.quotes.dictionary:
                continue

            parsed_tokens.append(token)
            generator.append_token(token)

        statement = generator.make_statement()
        tokenised = prosegen.prosegen.Fact(statement, "")

        return Response(
            status=200,
            content_type="application/json",
            text=json.dumps(
                {
                    "input": {
                        "text": words,
                        "tokens": parsed_tokens,
                    },
                    "output": {
                        "text": tokenised.original,
                        "tokens": tokenised.tokens,
                    },
                },
                cls=SetEncoder,
            ),
        )
