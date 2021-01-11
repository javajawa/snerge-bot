#!/bin/sh

# SPDX-FileCopyrightText: 2020 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

black bot.py prosegen
flake8 bot.py prosegen
mypy --strict bot.py prosegen
pylint bot.py prosegen
