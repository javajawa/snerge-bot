#!/usr/bin/env python3
# vim: ts=4 expandtab nospell

# SPDX-FileCopyrightText: 2020 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

"""Only Hope Bot"""

from __future__ import annotations

import time
import itertools
import sys

import requests

import prosegen

data = requests.get("https://raw.githubusercontent.com/RebelliousUno/BrewCrewQuoteDB/main/quotes.txt")

length = int(sys.argv[1]) if len(sys.argv) > 1 else 20
prosegen = prosegen.ProseGen(length)

for line in data.text.split("\n"):
    line = line.strip()

    if not line:
        continue

    line_quotes = line.split('"')[1:]

    for quote, attr in zip(*[iter(line_quotes)]*2):
        if 'Serge' in attr or 'Snerge' in attr:
            prosegen.add_knowledge(quote)

for i in range(0, 20):
    wisdom = prosegen.make_statement(24)
    
    if len(wisdom) > 80:
        i -= 1
        continue

    print(wisdom)
