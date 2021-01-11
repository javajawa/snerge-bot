#!/usr/bin/python3
# vim: nospell expandtab ts=4

# SPDX-FileCopyrightText: 2020 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

from typing import List

import zlib


class Buffer:
    size: int
    pos: int
    data: List[str]

    def __init__(self, size: int):
        self.size = size
        self.pos = 0
        self.data = [""] * size

    def push(self, item: str) -> None:
        self.data[self.pos] = item
        self.pos += 1

        if self.pos == self.size:
            self.pos = 0

    def hash(self, items: int) -> int:
        if items > self.size:
            raise Exception("Attempting to hash more items than buffer size")

        if items < 1:
            raise Exception("Must hash at least one item")

        start: int = self.pos - items
        strings: List[str]

        if start < 0:
            start = self.size + start

            if self.pos == 0:
                strings = self.data[start : self.size]
            else:
                strings = self.data[start : self.size] + self.data[0 : self.pos]
        else:
            strings = self.data[start : self.pos]

        return zlib.crc32(" ".join(strings).encode())
