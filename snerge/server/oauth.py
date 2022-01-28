#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

from typing import List

import dataclasses
import random

from urllib.parse import parse_qs

import requests

from snerge import logging
from snerge.server.base import Response, WSGIEnv
from snerge.token import App, Token


@dataclasses.dataclass
class TwitchUser:
    uid: int
    login: str


class UserFetchError(Exception):
    pass


class OAuthHandler:
    logger: logging.Logger
    app: App
    pending_auth_nonces: List[str]

    def __init__(self, logger: logging.Logger, app: App) -> None:
        self.logger = logger
        self.app = app
        self.pending_auth_nonces = []

    def handle(self, environ: WSGIEnv) -> Response:
        # If the user has just arrived, redirect them
        # to the oAuth flow on the Twitch site.
        if "QUERY_STRING" not in environ:
            return self.redirect_to_authorize()

        return self.process_oauth_callback(environ)

    def redirect_to_authorize(self) -> Response:
        state = "%24x" % random.randrange(16 ** 24)

        destination = (
            "https://id.twitch.tv/oauth2/authorize"
            "?response_type=code"
            f"&client_id={self.app.client_id}"
            f"&redirect_uri={self.app.redirect_url}"
            "&scope=channel:read:redemptions"
            f"&state={state}"
        )

        self.pending_auth_nonces.append(state)
        self.logger.info("Redirect created, nonce: %s", state)

        return Response(
            307,
            "text/plain",
            b"Redirecting to " + destination.encode("utf-8"),
            [("location", destination)],
        )

    def process_oauth_callback(self, environ: WSGIEnv) -> Response:
        data = parse_qs(environ.get("QUERY_STRING", ""))
        auth = data.get("state", [])
        code = data.get("code", "")

        if len(auth) != 1 or not code or isinstance(code, list):
            return Response(400, "text/plain", b"Missing or incorrect state info")

        return self.handle_code(auth[0], code)

    def handle_code(self, our_nonce: str, their_nonce: str) -> Response:
        self.logger.info("Getting auth token, nonce: %s", our_nonce)

        if our_nonce not in self.pending_auth_nonces:
            self.logger.info("Nonce %s is not a pending nonce", our_nonce)
            return Response(400, "text/plain", b"Invalid state nonce")

        self.pending_auth_nonces.remove(our_nonce)

        token_request = requests.post(
            "https://id.twitch.tv/oauth2/token",
            {
                "client_id": self.app.client_id,
                "client_secret": self.app.client_secret,
                "code": their_nonce,
                "grant_type": "authorization_code",
                "redirect_uri": self.app.redirect_url,
            },
        )

        token_json = token_request.json()

        if "access_token" not in token_json:
            self.logger.warning("Unable to get token: %s", str(token_json))
            return Response(
                500, "text/plain", b"Auth Error: " + str(token_json).encode("utf-8")
            )

        try:
            user = self.fetch_user_data(token_json["access_token"])
        except UserFetchError as error:
            return Response(500, "text/plain", str(error).encode("utf-8"))

        new_token = Token(
            user.uid,
            user.login,
            token_json["access_token"],
            token_json["refresh_token"],
        )
        new_token.store()

        self.logger.info("Successfully registered user %s", user)

        message = f"Thank you {user}! Your credentials have been stored!"

        return Response(200, "text/plain", message.encode("utf-8"))

    def fetch_user_data(self, access_token: str) -> TwitchUser:
        user_request = requests.get(
            "https://api.twitch.tv/helix/users",
            headers={
                "Authorization": "Bearer " + access_token,
                "Client-ID": self.app.client_id,
            },
        )

        user_json = user_request.json()

        if "data" not in user_json or len(user_json["data"]) != 1:
            self.logger.warning("Unable to get user: %s", str(user_json))
            raise UserFetchError(str(user_json))

        user = user_json["data"][0]

        if "login" not in user:
            self.logger.warning("Username missing from user: %s", user)
            raise UserFetchError("Username missing from user: " + str(user))

        return TwitchUser(int(user["id"]), str(user["login"]))
