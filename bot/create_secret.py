#!/usr/bin/env python3
# vim: nospell expandtab ts=4

# SPDX-FileCopyrightText: 2020 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

import os

import bot.token


if __name__ == "__main__":
    bot.token.App(
        os.environ.get("CLIENT_ID", ""),
        os.environ.get("CLIENT_SECRET", ""),
        os.environ.get("IRC_TOKEN", ""),
        os.environ.get("REDIRECT_URL", ""),
    ).store()
