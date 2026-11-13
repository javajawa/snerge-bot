# SPDX-FileCopyrightText: 2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

from typing import Self

import abc
import dataclasses
import json
import pathlib
import tempfile

import aiohttp

from .server.util import SetEncoder

TOKENS = pathlib.Path("tokens")
APP_TOKEN = TOKENS / "_app.json"


@dataclasses.dataclass
class _Token(abc.ABC):
    @classmethod
    def _load(cls, path: pathlib.Path) -> Self:
        with path.open("rb") as handle:
            data = json.load(handle)

        if not isinstance(data, dict):
            raise TypeError

        allowed_fields = {f.name for f in dataclasses.fields(cls)}
        data = {k: v for k, v in data.items() if k in allowed_fields}

        return cls(**data)

    @property
    @abc.abstractmethod
    def path(self) -> pathlib.Path:
        pass

    def store(self) -> None:
        path = self.path
        with tempfile.NamedTemporaryFile(mode="x", dir=path.parent, encoding="utf-8") as handle:
            json.dump(self, handle, cls=SetEncoder, indent=2)
            handle.write("\n")
            handle.flush()
            pathlib.Path(handle.name).rename(self.path)


@dataclasses.dataclass()
class AppToken(_Token):
    client_id: str
    client_secret: str
    app_token: str
    redirect_url: str
    jwt_hmac_key: str = ""

    @classmethod
    def load(cls) -> AppToken:
        return cls._load(APP_TOKEN)

    @property
    def path(self) -> pathlib.Path:
        return TOKENS / "_app.json"

    async def refresh(self, session: aiohttp.ClientSession) -> None:
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
class Token(_Token):
    user_id: int
    user: str
    access_token: str
    refresh_token: str

    @classmethod
    def load(cls, user: str) -> Token:
        return cls._load(TOKENS / f"{user}.json")

    @property
    def path(self) -> pathlib.Path:
        return TOKENS / f"{self.user}.json"

    async def renew(self, session: aiohttp.ClientSession, app: AppToken) -> bool:
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


class Tokens:
    chatter: Token
    broadcaster: Token
    oauth_app: AppToken

    __slots__ = "broadcaster", "chatter", "oauth_app"

    def __init__(self, app: AppToken, chatter: Token, broadcaster: Token) -> None:
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
