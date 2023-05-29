#!/usr/bin/python3

# SPDX-FileCopyrightText: 2020 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import itertools
import random
import re

from prosegen import misspell

from .buffer import Buffer


DOUBLE_QUOTE1 = re.compile(r'(?:^| )"(\S+)"(?: |$)')
DOUBLE_QUOTE2 = re.compile(r'(?:^| )"([^"]+)"(?: |$)')
SINGLE_QUOTE1 = re.compile(r"(?:^| )'(\S+)'(?: |$)")
SINGLE_QUOTE2 = re.compile(r"(?:^| )'(.+)'(?: |$)")
SMALL_NUMBER = re.compile(r"(?:^| )[0-9](?: |$)")
BIG_NUMBER = re.compile(r"(?:^| )[0-9]+(?: |$)")
DO_NOT_WANT = re.compile(r"(?:^| )nooo+(?: |$)")
SURPRISE = re.compile(r"(?:^| )oo+h+(?: |$)")
TEXT_EN_DASH = re.compile(r"(\w)(--|–)")
ELLIPSIS_WITH_PUNCTUATION = re.compile(r"\.\.\.+([?!])")
ELLIPSIS = re.compile(r"(\.\.\.+|…)")
EMPHASIS = re.compile(r"(?:^| )\*([^*]+)\*(?: |$)")
BRACKETS_ROUND = re.compile(r"(?:^| )\(([^)]+)\)(?: |$)")
BRACKETS_SQUARE = re.compile(r"(?:^| )\[([^!][^]]+)](?: |$)")
GENERAL_PUNCTUATION = re.compile(r"([?!.,;:‽])([\s?!]|$)")

SPACE = re.compile(r"\s+")


@dataclass
class Punctuation:
    text: str
    space_before: bool
    space_after: bool
    may_end_quote: bool = False
    capital_after: bool = False
    block_open: str | None = None
    block_close: str | None = None


PUNCTUATION: dict[str, Punctuation] = {
    "[!EN_DASH]": Punctuation("–", False, False),
    "[!EM_DASH]": Punctuation("—", False, False),
    "[!PERIOD]": Punctuation(".", False, True, True, True),
    "[!ELLIPSIS]": Punctuation("…", False, True, True),
    "[!EXCLAMATION]": Punctuation("!", False, True, True, True),
    "[!QUESTION]": Punctuation("?", False, True, True, True),
    "[!INTERROBANG]": Punctuation("‽", False, True, True, True),
    "[!COMMA]": Punctuation(",", False, True),
    "[!SEMICOLON]": Punctuation(";", False, True),
    "[!COLON]": Punctuation(":", False, True),
    "[!OPEN_QUOTE]": Punctuation(
        '"', True, False, block_open="[!OPEN_QUOTE]", block_close="[!CLOSE_QUOTE]"
    ),
    "[!CLOSE_QUOTE]": Punctuation(
        '"', False, True, block_open="[!OPEN_QUOTE]", block_close="[!CLOSE_QUOTE]"
    ),
    "[!OPEN_EMPHASIS]": Punctuation(
        "*", True, False, block_open="[!OPEN_EMPHASIS]", block_close="[!CLOSE_EMPHASIS]"
    ),
    "[!CLOSE_EMPHASIS]": Punctuation(
        "*", False, True, block_open="[!OPEN_EMPHASIS]", block_close="[!CLOSE_EMPHASIS]"
    ),
    "[!OPEN_BRACKETS]": Punctuation(
        "(", True, False, block_open="[!OPEN_BRACKETS]", block_close="[!CLOSE_BRACKETS]"
    ),
    "[!CLOSE_BRACKETS]": Punctuation(
        ")", False, True, block_open="[!OPEN_BRACKETS]", block_close="[!CLOSE_BRACKETS]"
    ),
    "[!BIG_NUMBER]": Punctuation("69", True, True),
    "[!NUMBER]": Punctuation("off-by-one", True, True),
}


@dataclass
class Fact:
    source: str
    original: str
    tokens: list[str]

    def __init__(self, data: str, source: str) -> None:
        self.source = source
        self.original = data
        self._tokenize()

    def _tokenize(self) -> None:
        data = self.original.lower().strip()

        data = TEXT_EN_DASH.sub(r"\1 [!EN_DASH] ", data)
        data = ELLIPSIS_WITH_PUNCTUATION.sub(r" [!ELLIPSIS] \1 ", data)
        data = ELLIPSIS.sub(r" [!ELLIPSIS] ", data)
        data = GENERAL_PUNCTUATION.sub(self._punctuation_token, data)

        data = EMPHASIS.sub(r" [!OPEN_EMPHASIS] \1 [!CLOSE_EMPHASIS] ", data)
        data = BRACKETS_ROUND.sub(r" [!OPEN_BRACKETS] \1 [!CLOSE_BRACKETS] ", data)
        data = BRACKETS_SQUARE.sub(r" [!OPEN_BRACKETS] \1 [!CLOSE_BRACKETS] ", data)
        data = DOUBLE_QUOTE1.sub(r" [!OPEN_QUOTE] \1 [!CLOSE_QUOTE] ", data)
        data = DOUBLE_QUOTE2.sub(r" [!OPEN_QUOTE] \1 [!CLOSE_QUOTE] ", data)
        data = SINGLE_QUOTE1.sub(r" [!OPEN_QUOTE] \1 [!CLOSE_QUOTE] ", data)
        data = SINGLE_QUOTE2.sub(r" [!OPEN_QUOTE] \1 [!CLOSE_QUOTE] ", data)

        data = ELLIPSIS_WITH_PUNCTUATION.sub(r" [!ELLIPSIS] \1 ", data)
        data = ELLIPSIS.sub(r" [!ELLIPSIS] ", data)
        data = GENERAL_PUNCTUATION.sub(self._punctuation_token, data)
        data = SMALL_NUMBER.sub(r" [!NUMBER] ", data)
        data = BIG_NUMBER.sub(r" [!BIG_NUMBER] ", data)
        data = DO_NOT_WANT.sub(r" nooooo ", data)
        data = SURPRISE.sub(r" oooooh ", data)
        data = SPACE.sub(" ", data)

        self.tokens = [misspell.replace(x) for x in data.strip().split(" ")]

    @staticmethod
    def _punctuation_token(data: re.Match[str]) -> str:
        for key, punct in PUNCTUATION.items():
            if data.group(1) == punct.text:
                return f" {key} "

        return f" {data.group(1)} "

    def __hash__(self) -> int:
        return hash((self.source, self.original))


class ProseGen:
    size: int
    dataset: dict[int, Counter[str]]
    dictionary: dict[str, set[Fact]]
    cont_buffer: Buffer

    def __init__(self, buffer_size: int):
        self.size = buffer_size
        self.dataset = {}
        self.dictionary = {"[!END]": set()}
        self.cont_buffer = Buffer(self.size)

    def add_knowledge(self, data: str, source: str = "", debug: bool = False) -> None:
        fact = Fact(data, source)

        if not fact.tokens:
            return

        for token in fact.tokens:
            self.dictionary.setdefault(token, set()).add(fact)

        if debug:
            print(fact.tokens)

        self.add_words(self.cont_buffer, fact.tokens, debug)
        self.add_word(self.cont_buffer, "[!END]", debug)

        buff = Buffer(self.size)
        self.add_words(buff, fact.tokens, debug)
        self.add_word(buff, "[!END]", debug)

    def add_words(self, buff: Buffer, words: list[str], debug: bool) -> None:
        for word in words:
            if word == "":
                continue

            add_ender = False

            self.add_word(buff, word, debug)
            buff.push(word)

            if add_ender:
                self.add_word(buff, "!END", debug)

    def add_word(self, buff: Buffer, word: str, debug: bool) -> None:
        last_hash = -1

        for size in range(1, self.size):
            item = buff.hash(size)

            # When the buffer is not full, the different sizes of backtrack
            # may have the same result. In this case, we stop processing.
            if item == last_hash:
                break

            last_hash = item

            if item not in self.dataset:
                self.dataset[item] = Counter()

            if debug:
                print(f"Phrase {buff.to_str(size)} continues to {word}")

            if word in self.dataset[item]:
                self.dataset[item][word] += 1
            else:
                self.dataset[item][word] = 1

    def make_statement(self, min_len: int = 0) -> str:
        return GeneratedQuote(self, min_len).make_statement()

    def get_token(self, buffer: Buffer, stack: list[str], can_end: bool) -> str:
        options: Counter[str] = Counter()

        for size in range(1, buffer.size):
            item = buffer.hash(size)
            if item in self.dataset:
                options += self.dataset[item]

        if not can_end:
            del options["[!END]"]

        for in_block in stack:
            del options[in_block]

        if not options:
            return "[!END_NO_OPTIONS]"

        i = random.randrange(sum(options.values()))
        return next(itertools.islice(options.elements(), i, None))


class GeneratedQuote:
    prose: ProseGen
    buffer: Buffer

    output: str = ""

    min_length: int
    block_stack: list[str] = []

    next_token_in_title_case: bool = True
    space_before_next_token: bool = False

    def __init__(self, prose: ProseGen, min_length: int) -> None:
        self.prose = prose
        self.buffer = Buffer(prose.size)
        self.min_length = min_length

    def make_statement(self) -> str:
        while True:
            token = self.get_potential_token()

            if token is None or token == "[!END]":
                return self.output.strip()

            self.append_token(token)

    def get_potential_token(self) -> str | None:
        options: Counter[str] = Counter()

        for size in range(1, self.buffer.size):
            item = self.buffer.hash(size)
            if item in self.prose.dataset:
                options += self.prose.dataset[item]

        if not self._can_end:
            del options["[!END]"]

        for in_block in self.block_stack:
            del options[in_block]
            if PUNCTUATION[in_block].block_close in options:
                options[PUNCTUATION[in_block].block_close or ""] *= 4

        if not options:
            return None

        i = random.randrange(sum(options.values()))
        return next(itertools.islice(options.elements(), i, None))

    def append_token(self, token: str) -> None:
        self.buffer.push(token)

        if token in PUNCTUATION:
            self._process_punctuation_token(token)
        else:
            self._append_token(token)

    def _append_token(self, token: str) -> None:
        if self.next_token_in_title_case:
            token = token[0].title() + token[1:] if len(token) > 1 else token.upper()

        if self.space_before_next_token:
            self.output += " "
        self.output += token

        self.next_token_in_title_case = False
        self.space_before_next_token = True

    def _process_punctuation_token(self, token: str, in_block_change: bool = False) -> None:
        punctuation = PUNCTUATION.get(token)
        if not punctuation:
            return

        was_space = self.space_before_next_token
        was_title = self.next_token_in_title_case

        self.space_before_next_token = (
            self.space_before_next_token and punctuation.space_before
        )

        if not in_block_change and punctuation.block_close:
            if not self._handle_block_change(token, punctuation):
                self.space_before_next_token = was_space
                self.next_token_in_title_case = was_title
                return

        self._append_token(punctuation.text)

        self.space_before_next_token = punctuation.space_after
        self.next_token_in_title_case = was_title or punctuation.capital_after

    def _handle_block_change(self, token: str, punctuation: Punctuation) -> bool:
        if punctuation.block_open == token:
            # If we're already in this block, we prevent opening it again.
            if punctuation.block_open in self.block_stack:
                return False

            self.block_stack.append(token)
            return True

        if punctuation.block_open not in self.block_stack:
            return False

        # We're closing a block, and any inner blocks inside it.
        while self.block_stack:
            opening_token_were_closing = self.block_stack.pop()
            opening_punctuation = PUNCTUATION[opening_token_were_closing]

            if opening_punctuation.block_close == token:
                return True

            self._process_punctuation_token(opening_punctuation.block_close or "", True)

        raise ValueError("Escaped block closing?")

    @property
    def _can_end(self) -> bool:
        return len(self.output) > self.min_length and not self.block_stack
