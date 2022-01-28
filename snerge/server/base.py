#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

from typing import Callable, Dict, Iterable, List, Sequence, Tuple, Union

import dataclasses


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
