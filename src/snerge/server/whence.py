#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

import json

from aiohttp.web import Request, Response, FileResponse, StreamResponse
from prosegen import ProseGen

from snerge.util import SetEncoder


class WhenceHandler:
    quotes: ProseGen

    def __init__(self, quotes: ProseGen) -> None:
        self.quotes = quotes

    @staticmethod
    async def handle_static(request: Request) -> StreamResponse:
        path = request.match_info.get("path", "")

        if path == "":
            return FileResponse(
                status=200,
                headers={"Content-Type": "text/html"},
                path="html/whence/whence.html",
            )

        if path == "whence.js":
            return FileResponse(
                status=200,
                headers={"Content-Type": "text/javascript"},
                path="html/whence/whence.js",
            )

        if path == "whence.css":
            return FileResponse(
                status=200,
                headers={"Content-Type": "text/css"},
                path="html/whence/whence.css",
            )

        return Response(status=200, text=path)

    async def handle_search(self, request: Request) -> Response:
        word = await request.text()

        output: dict[str, list[dict[str, str | list[str]]]] = {}
        tokens = self.quotes.dictionary.keys()

        for word in word.strip().split(" "):
            for token in tokens:
                if word.lower() in token.lower():
                    data = self.quotes.dictionary[token]
                    output[token] = [
                        {"source": fact.source, "text": fact.original, "tokens": fact.tokens}
                        for fact in data
                    ]

        return Response(
            status=200,
            content_type="application/json",
            text=json.dumps(output, cls=SetEncoder),
        )
