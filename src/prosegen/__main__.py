#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2020 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

import sys

from prosegen import ProseGen


instance = ProseGen(20)

for count in range(1, len(sys.argv)):
    arg = sys.argv[count]
    instance.add_knowledge(arg, source=f"arg{count}", debug=True)

for key in sorted(instance.dictionary.keys()):
    print(f"{key:20s} {instance.dictionary[key]}")
