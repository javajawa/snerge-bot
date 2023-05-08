#!/usr/bin/python3

# SPDX-FileCopyrightText: 2020 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations


class Buffer:
    size: int
    pos: int
    data: list[str]

    def __init__(self, size: int) -> None:
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
            raise IndexError("Attempting to hash more items than buffer size")

        if items < 1:
            raise IndexError("Must hash at least one item")

        return hash(tuple(self.subset(items)))

    def to_str(self, items: int) -> str:
        return f"||{' '.join(self.subset(items))}||@{self.hash(items)}"

    def subset(self, items: int) -> list[str]:
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
