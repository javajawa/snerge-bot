#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

from typing import Any

import json

from prosegen import ProseGen

from .base import Response, WSGIEnv


WHENCE_PAGE = b"""
<!DOCTYPE html>
<html>
    <head>
        <meta charset="utf-8">
        <title>Snerge Bot</title>
        <script type="module" defer>
            import { elemGenerator } from "https://javajawa.github.io/elems.js/elems.js";

            const ul = elemGenerator("ul");
            const li = elemGenerator("li");
            const a = elemGenerator("a");

            function search() {
                const term = document.getElementById("search")?.value || "";
                fetch('/whence.json', {method: 'POST', body: "minecraft"})
                    .then(r => r.json())
                    .then(r => Object.entries(r))
                    .then(r => r.forEach(([word, refs]) => {
                        document.body.appendChild(
                            ul(li(word), ul(refs.map(ref => li(ref))))
                        );
                    }));
            }

            document.getElementById("search").addEventListener("change", search);
        </script>
    </head>
    <body>
        <input name="search" id="search" />
    </body>
</html>
"""


class SetEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, set):
            return list(o)
        return json.JSONEncoder.default(self, o)


class WhenceHandler:
    quotes: ProseGen

    def __init__(self, quotes: ProseGen) -> None:
        self.quotes = quotes

    @staticmethod
    def handle_page(_: WSGIEnv) -> Response:
        return Response(200, "text/html", WHENCE_PAGE)

    def handle_search(self, environ: WSGIEnv) -> Response:
        length = int(environ.get("CONTENT_LENGTH", "0"))
        word = environ.get("wsgi.input").read(length)  # type: ignore

        output = {}

        for word in word.decode("utf-8").strip().split(" "):
            output[word] = self.quotes.dictionary[word]

        return Response(
            200, "application/json", json.dumps(output, cls=SetEncoder).encode("utf-8")
        )
