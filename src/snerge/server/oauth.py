# SPDX-FileCopyrightText: 2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

from typing import TYPE_CHECKING, NamedTuple, TypedDict

import random
import time

import jwt
from aiohttp import client, web
from yarl import URL

from snerge.token import AppToken, Token

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    import logging

    Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]


class TwitchUser(NamedTuple):
    uid: int
    login: str


JWTData = TypedDict(
    "JWTData",
    {
        "iss": str,
        "aud": str,
        "sub": str,
        "name": str,
        "user_id": int,
        "iat": int,
        "exp": int,
        "snerge.tea-cats.co.uk/moderated_channels": list[str],
    },
)


AUTH_COOKIE = "snerge-auth"
AUTH_VAR = web.RequestKey("snerge-auth", JWTData)


class UserFetchError(Exception):
    pass


class OAuthHandler:
    logger: logging.Logger
    session: client.ClientSession
    app: AppToken
    pending_auth_csrf_tokens: dict[str, tuple[bool, str | None]]

    def __init__(self, logger: logging.Logger, sess: client.ClientSession, app: AppToken) -> None:
        self.logger = logger
        self.app = app
        self.session = sess
        self.pending_auth_csrf_tokens = {}

    @web.middleware
    async def verify(self, request: web.Request, handler: Handler) -> web.StreamResponse:
        jwt_token = request.cookies.get(AUTH_COOKIE)
        auth_redir = web.HTTPFound(URL("/oauth/mod").with_query({"to": request.path}))

        if request.path.startswith("/oauth"):
            return await handler(request)

        if not jwt_token:
            return auth_redir

        try:
            token = jwt.decode(
                jwt_token,
                self.app.jwt_hmac_key,
                issuer="snerge.tea-cats.co.uk",
                audience="snerge.tea-cats.co.uk",
                algorithms=["HS256"],
            )
        except jwt.ExpiredSignatureError:
            return auth_redir  # TODO(kitteh): SNR-001 Automatic refresh
        except jwt.InvalidTokenError as exc:
            self.logger.info("Received invalid token", exc_info=exc)
            return auth_redir

        try:
            request[AUTH_VAR] = JWTData(**token)  # type: ignore[typeddict-item]
        except TypeError:
            return auth_redir

        return await handler(request)

    async def whoami(self, request: web.Request) -> web.StreamResponse:
        user = request[AUTH_VAR]

        return web.json_response(user)

    async def handle(self, request: web.Request) -> web.Response:
        # If the user has just arrived, redirect them
        # to the oAuth flow on the Twitch site.
        if not request.query:
            return self.redirect_to_authorize(for_bot=False)

        return await self.process_oauth_callback(request)

    async def start_human(self, request: web.Request) -> web.Response:
        return self.redirect_to_authorize(
            for_bot=False,
            redirect_to=request.query.getone("to", None),
        )

    async def start_bot(self, _: web.Request) -> web.Response:
        return self.redirect_to_authorize(for_bot=True)

    def redirect_to_authorize(
        self,
        *,
        for_bot: bool,
        redirect_to: str | None = None,
    ) -> web.Response:
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

        self.pending_auth_csrf_tokens[state] = for_bot, redirect_to
        self.logger.info("Redirect created, CSRF token: %s", state)

        return web.HTTPTemporaryRedirect(
            location=str(destination),
            content_type="text/plain",
            text="Redirecting to " + str(destination),
        )

    async def process_oauth_callback(self, request: web.Request) -> web.Response:
        auth = request.query.getall("state")
        code = request.query.getall("code")

        if len(auth) != 1 or len(code) != 1:
            return web.Response(
                status=400,
                content_type="text/plain",
                text="Missing or incorrect state info",
            )

        return await self.handle_code(auth[0], code[0])

    async def handle_code(self, our_csrf_token: str, their_csrf_token: str) -> web.Response:
        self.logger.info("Getting auth token, CSRF token: %s", our_csrf_token)

        if our_csrf_token not in self.pending_auth_csrf_tokens:
            self.logger.info("csrf_token %s is not a pending token", our_csrf_token)
            return web.Response(
                status=400,
                content_type="text/plain",
                text="Invalid response state token",
            )

        for_bot, redir = self.pending_auth_csrf_tokens.pop(our_csrf_token)

        token_request = await self.session.post(
            "https://id.twitch.tv/oauth2/token",
            params={
                "client_id": self.app.client_id,
                "client_secret": self.app.client_secret,
                "code": their_csrf_token,
                "grant_type": "authorization_code",
                "redirect_uri": self.app.redirect_url,
            },
            timeout=client.ClientTimeout(total=15),
        )

        token_json = await token_request.json()

        if "access_token" not in token_json:
            self.logger.warning("Unable to get token: %s", str(token_json))
            return web.Response(
                status=500,
                content_type="text/plain",
                text="Auth Error: " + str(token_json),
            )

        try:
            user = await self.fetch_user_data(token_json["access_token"])
        except UserFetchError as error:
            return web.Response(status=500, content_type="text/plain", text=str(error))

        new_token = Token(
            user.uid,
            user.login,
            token_json["access_token"],
            token_json["refresh_token"],
        )
        new_token.store()

        self.logger.info("Successfully registered user %s", user)

        if for_bot:
            return web.Response(
                status=200,
                content_type="text/plain",
                text=f"Thank you {user.login}! Your credentials have been stored!",
            )

        new_auth_token = await self._create_jwt(new_token)

        r = web.HTTPFound(location=redir or "/")
        r.set_cookie(AUTH_COOKIE, new_auth_token)

        return r

    async def _create_jwt(self, token: Token) -> str:
        self.logger.info("Fetching moderation info for %s (%d)", token.user, token.user_id)

        async with self.session.get(
            "https://api.twitch.tv/helix/moderation/channels",
            params={"user_id": token.user_id},
            headers={
                "Authorization": "Bearer " + token.access_token,
                "Client-ID": self.app.client_id,
            },
        ) as user_data:
            mod_perms = await user_data.json()

        channels = {c["broadcaster_login"] for c in mod_perms["data"]}
        channels.add(token.user)
        now = int(time.time())

        return jwt.encode(
            JWTData(  # type: ignore[arg-type]
                **{
                    "iss": "snerge.tea-cats.co.uk",
                    "aud": "snerge.tea-cats.co.uk",
                    "sub": str(token.user_id),
                    "user_id": token.user_id,
                    "name": token.user,
                    "iat": now,
                    "exp": now + 86400,
                    "snerge.tea-cats.co.uk/moderated_channels": list(channels),
                },
            ),
            self.app.jwt_hmac_key,
            algorithm="HS256",
        )

    async def fetch_user_data(self, access_token: str) -> TwitchUser:
        user_request = await self.session.get(
            "https://api.twitch.tv/helix/users",
            headers={
                "Authorization": "Bearer " + access_token,
                "Client-ID": self.app.client_id,
            },
            timeout=client.ClientTimeout(total=15),
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
