#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

from typing import Any, Callable, Dict

import json

from prosegen import ProseGen

from .base import Response, File, WSGIEnv


class SetEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, set):
            return list(o)
        return json.JSONEncoder.default(self, o)


class WhenceHandler:
    quotes: ProseGen
    mapping: Dict[str, Callable[[WSGIEnv], Response]]

    def __init__(self, quotes: ProseGen) -> None:
        self.quotes = quotes
        self.mapping = {
            "/": File("text/html", "html/whence/whence.html").serve,
            "/whence.css": File("text/css", "html/whence/whence.css").serve,
            "/whence.js": File("text/javascript", "html/whence/whence.js").serve,
            "/search": self.handle_search,
        }

    def handle(self, path: str, environ: WSGIEnv) -> Response:
        if path not in self.mapping:
            return Response(404, "text/plain", b"Not Found")

        return self.mapping[path](environ)

    def handle_search(self, environ: WSGIEnv) -> Response:
        length = int(environ.get("CONTENT_LENGTH", "0"))
        word = environ.get("wsgi.input").read(length)  # type: ignore

        output = {}

        for word in word.decode("utf-8").strip().split(" "):
            output[word] = (
                self.quotes.dictionary[word] if word in self.quotes.dictionary else []
            )

        return Response(
            200, "application/json", json.dumps(output, cls=SetEncoder).encode("utf-8")
        )
