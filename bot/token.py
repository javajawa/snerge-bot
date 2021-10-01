#!/usr/bin/env python3
# vim: nospell expandtab ts=4

# SPDX-FileCopyrightText: 2020 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

import dataclasses
import pickle

import requests


CLIENT_ID = "hm7gmtnxatfdzfy1wmapsa53cd11e0"
CLIENT_SECRET = "mx0quj2awpncofjaampzf3bxg0paze"
REDIRECT_URL = "https://snerge.tea-cats.co.uk/"


@dataclasses.dataclass
class Token:
    user: str
    access_token: str
    refresh_token: str

    def store(self) -> None:
        with open(f"tokens/{self.user}.token", "wb") as handle:
            pickle.dump(self, handle)

    def renew(self) -> bool:
        token_request = requests.post(
            "https://id.twitch.tv/oauth2/token",
            {
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
            },
        )

        token = token_request.json()

        if "access_token" not in token:
            return False

        self.access_token = token["access_token"]
        self.refresh_token = token["refresh_token"]

        self.store()

        return True

    @classmethod
    def load(cls, user: str) -> Token:
        with open(f"tokens/{user}.token", "rb") as handle:
            data = pickle.load(handle)

            if not isinstance(data, Token):
                raise TypeError("Found incorrect token type: " + type(data))

            return data
