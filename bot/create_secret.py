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
        client_id=os.environ.get("CLIENT_ID", ""),
        client_secret=os.environ.get("CLIENT_SECRET", ""),
        irc_token=os.environ.get("IRC_TOKEN", ""),
        app_token="",
        redirect_url=os.environ.get("REDIRECT_URL", ""),
    ).store()
