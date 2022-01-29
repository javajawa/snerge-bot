#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

from typing import Callable, Dict, Iterable, List, Sequence, Tuple, Union

import dataclasses
import hashlib
import os


WSGIEnv = Dict[str, str]
WSGICallback = Callable[[str, Sequence[Tuple[str, str]]], None]


@dataclasses.dataclass
class Response:
    status: int
    mime_type: str
    contents: Union[bytes, Iterable[bytes]]
    headers: List[Tuple[str, str]] = dataclasses.field(default_factory=list)

    def get_status(self) -> str:
        return str(self.status)

    def get_headers(self) -> List[Tuple[str, str]]:
        headers: Dict[str, str] = {
            "Content-Type": self.mime_type,
            "Cache-Control": "private, max-age=0",
        }

        ret = list(headers.items())
        ret.extend(self.headers)

        return ret

    def get_contents(self) -> Iterable[bytes]:
        if isinstance(self.contents, bytes):
            return [self.contents]

        return self.contents


class File:
    filename: str
    mime: str
    modified: int
    size: int
    tag: str
    contents: bytes

    def __init__(self, mime: str, filename: str) -> None:
        self.filename = filename
        self.mime = mime
        self.modified = 0
        self.size = 0
        self.tag = ""
        self.contents = b""

        self.reload()

    def reload(self) -> None:
        if not os.path.exists(self.filename):
            raise FileNotFoundError(f"{self.filename} does not exist")

        stat = os.stat(self.filename)

        if int(stat.st_mtime) <= self.modified:
            return

        self.modified = int(stat.st_mtime)
        self.size = stat.st_size

        with open(self.filename, "rb") as ifile:
            self.contents = ifile.read()

        tag = hashlib.sha256()
        tag.update(self.contents)
        self.tag = tag.hexdigest()

    def serve(self, environ: WSGIEnv) -> Response:
        try:
            self.reload()
        except FileNotFoundError:
            pass

        if not self.tag:
            return Response(404, "text/plain", b"not found")

        if environ.get("HTTP_IF_NONE_MATCH", "") == self.tag:
            return Response(
                304,
                self.mime,
                [],
                [("ETag", self.tag), ("Last-Modified", str(self.modified))],
            )

        return Response(
            200,
            self.mime,
            self.contents,
            [
                ("Content-Length", str(self.size)),
                ("ETag", self.tag),
                ("Last-Modified", str(self.modified)),
            ],
        )
