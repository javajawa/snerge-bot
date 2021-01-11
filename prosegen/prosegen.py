#!/usr/bin/python3
# vim: nospell expandtab ts=4

# SPDX-FileCopyrightText: 2020 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

from collections import Counter
from typing import Counter as counter, Dict, List

import itertools
import random
import re

import prosegen.misspell as misspell

from .buffer import Buffer


class ProseGen:
    size: int
    punct: re.Pattern  # type: ignore
    dataset: Dict[int, counter[str]]

    def __init__(self, buffer_size: int):
        self.size = buffer_size
        self.dataset = {}
        self.emote = re.compile(r"(^ | ):([^\s:]+):( |$)")
        self.quote = re.compile(r' "([^"]+)" ')
        self.punct = re.compile(r"([!\.,;:])( |$)")
        self.space = re.compile(r"\s+")
        self.form = re.compile(r"[^\w']+")

    def add_knowledge(self, data: str) -> None:
        data = data.lower().strip()

        data = self.quote.sub(r" \" \1 \" ", data)
        data = self.emote.sub(r" EMOTE\2 ", data)
        data = self.punct.sub(r" \1 ", data)
        data = self.space.sub(" ", data)
        words = data.split(" ")

        if not words:
            return

        words.append("!END")

        buff = Buffer(self.size)

        self.add_words(buff, words)

    def add_words(self, buff: Buffer, words: List[str]) -> None:
        for word in words:
            if word == "":
                continue

            if word in ["!", ".", ",", ";", ":", '"']:
                word = "!PUNCT" + word
            elif word == "!END":
                pass
            else:
                word = self.form.sub("", word)
                word = misspell.replace(word)

            for size in range(1, self.size):
                item = buff.hash(size)

                if item not in self.dataset:
                    self.dataset[item] = Counter()

                if word in self.dataset[item]:
                    self.dataset[item][word] += 1
                else:
                    self.dataset[item][word] = 1

            buff.push(word)

    def make_statement(self) -> str:
        buff: Buffer = Buffer(self.size)
        output: str = ""

        while True:
            item = self.get_token(buff)

            if item == "!END":
                return output.strip()

            buff.push(item)

            if item.startswith("!PUNCT"):
                output += item[-1]
            elif item.endswith("!PUNCT"):
                output += item[0]
            elif item.startswith("EMOTE"):
                output += " :" + item[5:] + ":"
            else:
                output += " " + item

    def get_token(self, buffer: Buffer) -> str:
        options: counter[str] = Counter()

        for size in range(1, buffer.size):
            item = buffer.hash(size)
            if item in self.dataset:
                options += self.dataset[item]

        if not options:
            return "!END"

        i = random.randrange(sum(options.values()))
        return next(itertools.islice(options.elements(), i, None))
