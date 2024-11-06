# SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

import asyncio

from . import Foo


if __name__ == "__main__":
    asyncio.run(Foo("serge.md").main())
