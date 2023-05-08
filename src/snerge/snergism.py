#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

"""Only Hope Bot"""

from __future__ import annotations

import asyncio

from prosegen import ProseGen

from snerge import log
from snerge.quotes import load_data


async def main() -> None:
    log.init()

    prosegen = ProseGen(20)
    prosegen = await load_data(log.get_logger(), prosegen)

    # x = re.compile("^[a-z]+$")
    # for key in sorted(prosegen.dictionary.keys()):
    #     if x.match(key):
    #         continue
    #     print(key, len(prosegen.dictionary[key]))
    #
    # try:
    #     while True:
    #         word = input("? ")
    #         for source in prosegen.dictionary.get(word, set()):
    #             print(source.source)
    #             print(source.original)
    #             print(source.tokens)
    #             print()
    # except (KeyboardInterrupt, EOFError):
    #     pass

    for i in range(0, 20):
        wisdom = prosegen.make_statement(24)

        if len(wisdom) > 140:
            i -= 1
            continue

        print(wisdom)


if __name__ == "__main__":
    asyncio.run(main())
