#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

"""Only Hope Bot"""

from __future__ import annotations

from snerge import logging
from snerge.quotes import load_data


def main() -> None:
    logging.init()

    prosegen = load_data(logging.get_logger())

    for i in range(0, 20):
        wisdom = prosegen.make_statement(24)

        if len(wisdom) > 80:
            i -= 1
            continue

        print(wisdom)


if __name__ == "__main__":
    main()
