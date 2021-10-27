#!/usr/bin/env python3
# vim: nospell expandtab ts=4

# SPDX-FileCopyrightText: 2020 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Sequence, Tuple, Union

import dataclasses
import hashlib
import hmac
import json
import logging
import random
import sys

from urllib.parse import parse_qs

import requests
import gunicorn.app.base  # type: ignore
from systemd.journal import JournalHandler  # type: ignore

from bot import token


LOGGER = logging.getLogger("snerge")

WSGIEnv = Dict[str, str]
WSGICallback = Callable[[str, Sequence[Tuple[str, str]]], None]


class StandAlone(gunicorn.app.base.Application):  # type: ignore
    options: Dict[str, Any]

    def __init__(self, options: Dict[str, Any]):
        self.options = options

        super().__init__()

    def load_config(self) -> None:
        config = {
            key: value
            for key, value in self.options.items()
            if key in self.cfg.settings and value is not None
        }
        for key, value in config.items():
            self.cfg.set(key.lower(), value)

    def init(self, parser: Any, opts: Any, args: Any) -> None:
        pass

    def load(self) -> Handler:
        return Handler()


@dataclasses.dataclass
class Response:
    status: int
    mime_type: str
    contents: Union[bytes, Iterable[bytes]]
    headers: List[Tuple[str, str]] = dataclasses.field(default_factory=list)

    def get_status(self) -> str:
        return str(self.status)

    def get_headers(self) -> List[Tuple[str, str]]:
        headers: Dict[str, str] = {
            "Content-Type": self.mime_type,
            "Cache-Control": "private, max-age=0",
        }

        ret = list(headers.items())
        ret.extend(self.headers)

        return ret

    def get_contents(self) -> Iterable[bytes]:
        if isinstance(self.contents, bytes):
            return [self.contents]

        return self.contents


class Handler:
    app: token.App
    states: List[str]

    def __init__(self) -> None:
        self.app = token.App.load()
        self.states = []

    def __call__(self, environ: WSGIEnv, start: WSGICallback) -> Iterable[bytes]:
        if environ.get("PATH_INFO", "/") != "/":
            response = self.render404()
        elif not environ.get("QUERY_STRING", None):
            response = self.get_redirect()
        else:
            data = parse_qs(environ.get("QUERY_STRING", ""))
            response = self.handle_code(data)

        start(response.get_status(), response.get_headers())

        return response.get_contents()

    @staticmethod
    def render404() -> Response:
        return Response(404, "text/plain", b"Not Found")

    def get_redirect(self) -> Response:
        state = "%24x" % random.randrange(16 ** 24)

        destination = (
            "https://id.twitch.tv/oauth2/authorize"
            "?response_type=code"
            f"&client_id={self.app.client_id}"
            f"&redirect_uri={self.app.redirect_url}"
            "&scope=channel:read:redemptions"
            f"&state={state}"
        )

        self.states.append(state)
        LOGGER.info("Redirect created, nonce: %s", state)

        return Response(
            307,
            "text/plain",
            b"Redirecting to " + destination.encode("utf-8"),
            [("location", destination)],
        )

    def handle_code(self, data: Dict[str, List[str]]) -> Response:
        state = data.get("state", [])

        if len(state) != 1 or state[0] not in self.states:
            return Response(400, "text/plain", b"Missing or incorrect state info")

        LOGGER.info("Getting auth token, nonce: %s", state[0])
        self.states.remove(state[0])

        token_request = requests.post(
            "https://id.twitch.tv/oauth2/token",
            {
                "client_id": self.app.client_id,
                "client_secret": self.app.client_secret,
                "code": data["code"],
                "grant_type": "authorization_code",
                "redirect_uri": self.app.redirect_url,
            },
        )

        token_json = token_request.json()

        if "access_token" not in token_json:
            LOGGER.warning("Unable to get token: %s", str(token_json))
            return Response(
                500, "text/plain", b"Auth Error: " + str(token_json).encode("utf-8")
            )

        user_request = requests.get(
            "https://api.twitch.tv/helix/users",
            headers={
                "Authorization": "Bearer " + token_json["access_token"],
                "Client-ID": self.app.client_id,
            },
        )

        user_json = user_request.json()

        if "data" not in user_json or len(user_json["data"]) != 1:
            LOGGER.warning("Unable to get user: %s", str(user_json))
            return Response(
                500, "text/plain", b"User Fetch Error: " + str(user_json).encode("utf-8")
            )

        user = user_json["data"][0]

        new_token = token.Token(
            int(user["id"]),
            user["login"],
            token_json["access_token"],
            token_json["refresh_token"],
        )
        new_token.store()

        LOGGER.info("Successfully registered user %s", user["login"])

        message = f"Thank you {new_token.user}! Your credentials have been stored!"

        return Response(200, "text/plain", message.encode("utf-8"))


if __name__ == "__main__":
    if sys.stdout.isatty():
        LOGGER.addHandler(logging.StreamHandler())
        LOGGER.setLevel(logging.DEBUG)
    else:
        LOGGER.addHandler(JournalHandler(SYSLOG_IDENTIFIER="snerge-bot"))
        LOGGER.setLevel(logging.DEBUG)

    _options = {
        "bind": "%s:%s" % ("127.0.1.2", "8888"),
        "workers": 1,
    }

    StandAlone(_options).run()
