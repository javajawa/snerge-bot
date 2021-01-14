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

        return zlib.crc32(" ".join(self.subset(items)).encode())

    def to_str(self, items: int) -> str:
        return f"||{' '.join(self.subset(items))}||@{self.hash(items)}"

    def subset(self, items: int) -> List[str]:
        start: int = self.pos - items

        if start >= 0:
            segment = slice(start, self.pos)
            return [x for x in self.data[segment] if x]

        start = self.size + start

        if self.pos == 0:
            segment = slice(start, self.size)
            return [x for x in self.data[segment] if x]

        segment1 = slice(start, self.size)
        segment2 = slice(0, self.pos)
        return [x for x in (self.data[segment1] + self.data[segment2]) if x]
