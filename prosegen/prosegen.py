#!/usr/bin/python3
# vim: nospell expandtab ts=4

# SPDX-FileCopyrightText: 2020 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

from collections import Counter
from typing import Counter as counter, Dict, List, Set

import itertools
import random
import re

from prosegen import misspell

from .buffer import Buffer


DQUOTE1 = re.compile(r'(?:^| )"([^\s]+)"(?: |$)')
DQUOTE2 = re.compile(r'(?:^| )"([^"]+)"(?: |$)')
SQUOTE1 = re.compile(r"(?:^| )'([^\s]+)'(?: |$)")
SQUOTE2 = re.compile(r"(?:^| )'(.+)'(?: |$)")
NDASH = re.compile(r"(\w)--( |$)")
ELLIPSIS_P = re.compile(r"\.\.\.+([?!])")
ELLIPSIS = re.compile(r"\.\.\.+")
PUNCT = re.compile(r"([?!\.,;:])([\s?!]|$)")
SPACE = re.compile(r"\s+")
FILTER_TO_WORD = re.compile(r"[^\w'\-]+")

PUNCT_END = ["?", "!", "."]


class ProseGen:
    size: int
    dataset: Dict[int, counter[str]]
    dictionary: Dict[str, Set[str]]
    cont_buffer: Buffer

    def __init__(self, buffer_size: int):
        self.size = buffer_size
        self.dataset = {}
        self.dictionary = {}
        self.cont_buffer = Buffer(self.size)

    def add_knowledge(self, data: str, source: str = "", debug: bool = False) -> None:
        data = data.lower().strip()

        data = ELLIPSIS_P.sub(r" … \1 ", data)
        data = ELLIPSIS.sub(r" … ", data)
        data = PUNCT.sub(r" \1 ", data)
        data = NDASH.sub(r"\1 –", data)
        data = DQUOTE1.sub(r' "!PUNCT \1 " ', data)
        data = DQUOTE2.sub(r' "!PUNCT \1 " ', data)
        data = SQUOTE1.sub(r' "!PUNCT \1 " ', data)
        data = SQUOTE2.sub(r' "!PUNCT \1 " ', data)
        data = SPACE.sub(" ", data)
        words = data.strip().split(" ")

        if not words:
            return

        if debug:
            print(words)

        buff = Buffer(self.size)

        self.add_words(self.cont_buffer, words, source, debug)
        self.add_word(self.cont_buffer, "!END", "", debug)

        self.add_words(buff, words, source, debug)
        self.add_word(buff, "!END", "", debug)

    def add_words(self, buff: Buffer, words: List[str], source: str, debug: bool) -> None:
        for word in words:
            if word == "":
                continue

            add_ender = False

            if word in PUNCT_END:
                word = "!PUNCT" + word
                add_ender = True
            if word in [",", "…", ";", ":", '"', "'", "–"]:
                word = "!PUNCT" + word
            elif word == "!END" or "!PUNCT" in word:
                pass
            else:
                word = FILTER_TO_WORD.sub("", word)
                word = misspell.replace(word)

            self.add_word(buff, word, source, debug)
            buff.push(word)

            if add_ender:
                self.add_word(buff, "!END", "", debug)

    def add_word(self, buff: Buffer, word: str, source: str, debug: bool) -> None:
        lasthash = -1

        if word not in self.dictionary:
            self.dictionary[word] = set()

        if source:
            self.dictionary[word].add(source)

        for size in range(1, self.size):
            item = buff.hash(size)

            if item == lasthash:
                break

            lasthash = item

            if item not in self.dataset:
                self.dataset[item] = Counter()

            if debug:
                print(f"Phrase {buff.to_str(size)} continues to {word}")

            if word in self.dataset[item]:
                self.dataset[item][word] += 1
            else:
                self.dataset[item][word] = 1

    def make_statement(self, min_len: int = 0) -> str:
        buff: Buffer = Buffer(self.size)
        output: str = ""
        title: bool = True
        no_space: bool = False
        quote: bool = False

        while True:
            can_end = len(output) > min_len and not quote
            item = self.get_token(buff, quote, can_end)

            if item == "!END":
                return output.strip()

            buff.push(item)

            space = "" if no_space else " "
            no_space = False

            if "!PUNCT" in item:
                space = space if item.endswith("!PUNCT") else ""
                no_space = item.endswith("!PUNCT")
                item = item[0] if item.endswith("!PUNCT") else item[-1]

                if item == '"':
                    quote = not quote

                title = item in PUNCT_END

            elif title:
                item = item[0].title() + item[1:] if len(item) > 1 else item.upper()
                title = False

            output += space + item

    def get_token(self, buffer: Buffer, in_quote: bool, can_end: bool) -> str:
        options: counter[str] = Counter()

        for size in range(1, buffer.size):
            item = buffer.hash(size)
            if item in self.dataset:
                options += self.dataset[item]

        if not can_end:
            del options["!END"]

        if in_quote:
            del options['"!PUNCT']
        else:
            del options['!PUNCT"']

        if not options:
            return "!END"

        i = random.randrange(sum(options.values()))
        return next(itertools.islice(options.elements(), i, None))
