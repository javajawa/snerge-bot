#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2020 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

import os

from snerge import token

if __name__ == "__main__":
    app = token.AppToken(
        client_id=os.environ.get("CLIENT_ID", ""),
        client_secret=os.environ.get("CLIENT_SECRET", ""),
        redirect_url=os.environ.get("REDIRECT_URL", ""),
        app_token="",
        jwt_hmac_key="",
    )
    app.store()
