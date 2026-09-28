# SPDX-FileCopyrightText: 2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

from typing import TYPE_CHECKING

import dataclasses
import random

import aiohttp
from aiohttp.web import Request, Response
from yarl import URL

from snerge.token import App, Token

if TYPE_CHECKING:
    import logging


@dataclasses.dataclass
class TwitchUser:
    uid: int
    login: str


class UserFetchError(Exception):
    pass


class OAuthHandler:
    logger: logging.Logger
    session: aiohttp.ClientSession
    app: App
    pending_auth_csrf_tokens: list[str]

    def __init__(self, logger: logging.Logger, session: aiohttp.ClientSession, app: App) -> None:
        self.logger = logger
        self.app = app
        self.session = session
        self.pending_auth_csrf_tokens = []

    async def handle(self, request: Request) -> Response:
        # If the user has just arrived, redirect them
        # to the oAuth flow on the Twitch site.
        if not request.query:
            return self.redirect_to_authorize(for_bot=False)

        return await self.process_oauth_callback(request)

    def redirect_to_authorize(self, *, for_bot: bool) -> Response:
        state = hex(random.randrange(16**24)).zfill(24)  # noqa: S311 - not cryptographic.

        destination = URL("https://id.twitch.tv/oauth2/authorize").with_query(
            response_type="code",
            client_id=self.app.client_id,
            redirect_uri=self.app.redirect_url,
            force_verify="true" if for_bot else "false",
            state=state,
            scope=(
                "channel:bot channel:read:redemptions user:read:chat bits:read"
                if for_bot
                else "user:read:moderated_channels"
            ),
        )

        self.pending_auth_csrf_tokens.append(state)
        self.logger.info("Redirect created, CSRF token: %s", state)

        return Response(
            status=307,
            content_type="text/plain",
            text="Redirecting to " + str(destination),
            headers={
                "location": str(destination),
                "connection": "close",
            },
        )

    async def process_oauth_callback(self, request: Request) -> Response:
        auth = request.query.getall("state")
        code = request.query.getall("code")

        if len(auth) != 1 or len(code) != 1:
            return Response(
                status=400,
                content_type="text/plain",
                text="Missing or incorrect state info",
            )

        return await self.handle_code(auth[0], code[0])

    async def handle_code(self, our_csrf_token: str, their_csrf_token: str) -> Response:
        self.logger.info("Getting auth token, CSRF token: %s", our_csrf_token)

        if our_csrf_token not in self.pending_auth_csrf_tokens:
            self.logger.info("csrf_token %s is not a pending nonce", our_csrf_token)
            return Response(
                status=400,
                content_type="text/plain",
                text="Invalid response state token",
            )

        self.pending_auth_csrf_tokens.remove(our_csrf_token)

        token_request = await self.session.post(
            "https://id.twitch.tv/oauth2/token",
            params={
                "client_id": self.app.client_id,
                "client_secret": self.app.client_secret,
                "code": their_csrf_token,
                "grant_type": "authorization_code",
                "redirect_uri": self.app.redirect_url,
            },
            timeout=aiohttp.ClientTimeout(total=15),
        )

        token_json = await token_request.json()

        if "access_token" not in token_json:
            self.logger.warning("Unable to get token: %s", str(token_json))
            return Response(
                status=500,
                content_type="text/plain",
                text="Auth Error: " + str(token_json),
            )

        try:
            user = await self.fetch_user_data(token_json["access_token"])
        except UserFetchError as error:
            return Response(status=500, content_type="text/plain", text=str(error))

        new_token = Token(
            user.uid,
            user.login,
            token_json["access_token"],
            token_json["refresh_token"],
        )
        new_token.store()

        self.logger.info("Successfully registered user %s", user)

        message = f"Thank you {user.login}! Your credentials have been stored!"

        return Response(status=200, content_type="text/plain", text=message)

    async def fetch_user_data(self, access_token: str) -> TwitchUser:
        user_request = await self.session.get(
            "https://api.twitch.tv/helix/users",
            headers={
                "Authorization": "Bearer " + access_token,
                "Client-ID": self.app.client_id,
            },
            timeout=aiohttp.ClientTimeout(total=15),
        )

        user_json = await user_request.json()

        if "data" not in user_json or len(user_json["data"]) != 1:
            self.logger.warning("Unable to get user: %s", str(user_json))
            raise UserFetchError(str(user_json))

        user = user_json["data"][0]

        if "login" not in user:
            self.logger.warning("Username missing from user: %s", user)
            raise UserFetchError("Username missing from user: " + str(user))

        return TwitchUser(int(user["id"]), str(user["login"]))
