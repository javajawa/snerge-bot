#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

import dataclasses
import pickle

import requests


@dataclasses.dataclass
class App:
    client_id: str
    client_secret: str
    irc_token: str
    app_token: str
    redirect_url: str

    def store(self) -> None:
        with open("tokens/_app.token", "wb") as handle:
            pickle.dump(self, handle)

    @classmethod
    def load(cls) -> App:
        with open("tokens/_app.token", "rb") as handle:
            data = pickle.load(handle)

            if not isinstance(data, App):
                raise TypeError("Found incorrect token type: " + type(data))

            return data


@dataclasses.dataclass
class Token:
    user_id: int
    user: str
    access_token: str
    refresh_token: str

    def store(self) -> None:
        with open(f"tokens/{self.user}.token", "wb") as handle:
            pickle.dump(self, handle)

    def renew(self, app: App) -> bool:
        token_request = requests.post(
            "https://id.twitch.tv/oauth2/token",
            {
                "client_id": app.client_id,
                "client_secret": app.client_secret,
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


def refresh_app_token() -> App:
    app = App.load()

    response = requests.post(
        "https://id.twitch.tv/oauth2/token",
        {
            "client_id": app.client_id,
            "client_secret": app.client_secret,
            "grant_type": "client_credentials",
            "scope": "channel:read:redemptions",
        },
    )

    app.app_token = response.json()["access_token"]
    app.store()

    return app
