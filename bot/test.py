#!/usr/bin/env python3
# vim: nospell expandtab ts=4

# SPDX-FileCopyrightText: 2020 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

import logging
import sys

from prosegen import ProseGen


LOGGER = logging.getLogger("snerge")


def load_data() -> None:
    instance = ProseGen(20)

    argc = 0
    for arg in sys.argv[1:]:
        argc += 1
        instance.add_knowledge(arg, source=f"arg{argc}", debug=True)

    for key in sorted(instance.dictionary.keys()):
        print("{:20s} {}".format(key, instance.dictionary[key]))


if __name__ == "__main__":
    load_data()
