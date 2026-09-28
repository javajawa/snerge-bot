# SPDX-FileCopyrightText: 2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

import dataclasses
import pathlib
import pickle

import aiohttp

TOKENS = pathlib.Path("tokens")
APP_TOKEN = TOKENS / "_app.token"


@dataclasses.dataclass
class App:
    client_id: str
    client_secret: str
    irc_token: str
    app_token: str
    redirect_url: str
    webhook_secret: bytes

    def store(self) -> None:
        with APP_TOKEN.open("wb") as handle:
            pickle.dump(self, handle)

    @classmethod
    def load(cls) -> App:
        with APP_TOKEN.open("rb") as handle:
            data = pickle.load(handle)  # noqa: S301 -- I'm sticking with pickle

            if not isinstance(data, App):
                raise TypeError("Found incorrect token type: " + type(data))

            return data

    async def refresh(self, session: aiohttp.ClientSession) -> None:
        self.redirect_url = "https://snerge.tea-cats.co.uk/oauth"
        async with session.post(
            "https://id.twitch.tv/oauth2/token",
            params={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "client_credentials",
                "scope": (
                    "user:bot user:read:chat user:write:chat bits:read channel:read:redemptions"
                ),
            },
            timeout=aiohttp.ClientTimeout(total=15),
        ) as response:
            self.app_token = (await response.json())["access_token"]

        self.store()


@dataclasses.dataclass
class Token:
    user_id: int
    user: str
    access_token: str
    refresh_token: str

    def store(self) -> None:
        with (TOKENS / f"{self.user}.token").open("wb") as handle:
            pickle.dump(self, handle)

    async def renew(self, session: aiohttp.ClientSession, app: App) -> bool:
        async with session.post(
            "https://id.twitch.tv/oauth2/token",
            params={
                "client_id": app.client_id,
                "client_secret": app.client_secret,
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
            },
            timeout=aiohttp.ClientTimeout(total=15),
        ) as token_request:
            token = await token_request.json()

        if "access_token" not in token:
            return False

        self.access_token = token["access_token"]
        self.refresh_token = token["refresh_token"]

        self.store()

        return True

    @classmethod
    def load(cls, user: str) -> Token:
        with (TOKENS / f"{user}.token").open("rb") as handle:
            data = pickle.load(handle)  # noqa: S301 -- I'm sticking with pickle

            if not isinstance(data, Token):
                raise TypeError("Found incorrect token type: " + type(data))

            return data


class Tokens:
    chatter: Token
    broadcaster: Token
    oauth_app: App

    __slots__ = "broadcaster", "chatter", "oauth_app"

    def __init__(self, app: App, chatter: Token, broadcaster: Token) -> None:
        self.chatter = chatter
        self.broadcaster = broadcaster
        self.oauth_app = app

    @property
    def app_token(self) -> str:
        return self.oauth_app.app_token

    @property
    def broadcaster_token(self) -> str:
        return self.broadcaster.access_token

    @property
    def client_id(self) -> str:
        return self.oauth_app.client_id

    @property
    def broadcaster_id(self) -> str:
        return str(self.broadcaster.user_id)

    @property
    def chatter_id(self) -> str:
        return str(self.chatter.user_id)

    async def refresh(self, session: aiohttp.ClientSession) -> None:
        await self.oauth_app.refresh(session)
        await self.broadcaster.renew(session, self.oauth_app)
        await self.chatter.renew(session, self.oauth_app)
