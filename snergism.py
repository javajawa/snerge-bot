#!/usr/bin/env python3
# vim: ts=4 expandtab nospell

# SPDX-FileCopyrightText: 2020 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

"""Only Hope Bot"""

from __future__ import annotations

from load import load_data


def main() -> None:
    prosegen = load_data()

    for i in range(0, 20):
        wisdom = prosegen.make_statement(24)

        if len(wisdom) > 80:
            i -= 1
            continue

        print(wisdom)


if __name__ == "__main__":
    main()
