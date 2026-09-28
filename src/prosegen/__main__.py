# SPDX-FileCopyrightText: 2020 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

import sys

from prosegen import ProseGen

instance = ProseGen(20)

for count in range(1, len(sys.argv)):
    arg = sys.argv[count]
    instance.add_knowledge(arg, source=f"arg{count}", debug=True)

for _key in sorted(instance.dictionary.keys()):
    pass
