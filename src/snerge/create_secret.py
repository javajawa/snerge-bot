#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2020 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

import os

from snerge import token


if __name__ == "__main__":
    app = token.App(
        client_id=os.environ.get("CLIENT_ID", ""),
        client_secret=os.environ.get("CLIENT_SECRET", ""),
        irc_token=os.environ.get("IRC_TOKEN", ""),
        redirect_url=os.environ.get("REDIRECT_URL", ""),
        webhook_secret=os.environ.get("WEBHOOK_SECRET", "").encode("utf-8"),
        app_token="",
    )
    app.store()
