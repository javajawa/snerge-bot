#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

from typing import Dict, Optional, Union

import asyncio
import dataclasses
import hashlib
import hmac
import json
import requests

from snerge import bot, config, logging, token
from .base import Response, WSGIEnv


REQUIRED_HEADERS = [
    "CONTENT_LENGTH",
    "HTTP_TWITCH_EVENTSUB_MESSAGE_ID",
    "HTTP_TWITCH_EVENTSUB_MESSAGE_TIMESTAMP",
    "HTTP_TWITCH_EVENTSUB_SUBSCRIPTION_TYPE",
    "HTTP_TWITCH_EVENTSUB_MESSAGE_TYPE",
    "HTTP_TWITCH_EVENTSUB_MESSAGE_SIGNATURE",
]


@dataclasses.dataclass
class TwitchEvent:
    message_id: str
    timestamp: str
    signature: str

    subscription_type: str
    message_type: str

    payload: bytes
    content: Dict[str, Union[Dict[str, str], str]]

    def signature_valid(self, secret: bytes) -> bool:
        mode, signature = self.signature.split("=", 1)

        if mode != "sha256":
            return False

        payload = (
            self.message_id.encode("utf-8") + self.timestamp.encode("utf-8") + self.payload
        )

        sig = hmac.new(secret, msg=payload, digestmod=hashlib.sha256).hexdigest()

        return sig == signature


class EventHandler:
    logger: logging.Logger
    secret: bytes

    _app: token.App
    _bot: bot.Bot

    def __init__(
        self, logger: logging.Logger, app: token.App, conf: config.Config, _bot: bot.Bot
    ) -> None:
        self.logger = logger
        self.secret = b"hello_i_am_snerge"
        self._app = app
        self._bot = _bot

        asyncio.run(self.register(conf.channel))

    def handle_webhook(self, environ: WSGIEnv) -> Response:
        event = self.load_event(environ)

        if not event:
            self.logger.warning("Received invalid event")
            return Response(400, "text/plain", b"Invalid event")

        if not event.signature_valid(self.secret):
            self.logger.warning("Received event with invalid signature")
            return Response(400, "text/plain", b"Incorrect Signature")

        self.logger.info("%s web-hook event %s", event.subscription_type, event.message_type)

        if event.message_type == "webhook_callback_verification":
            return self.handle_verification_event(event)

        if event.message_type == "channel.channel_points_custom_reward_redemption.add":
            return self.handle_reward_event(event)

        self.logger.info(json.dumps(event.content, indent="  "))
        return Response(204, "text/plain", b"")

    def handle_verification_event(self, event: TwitchEvent) -> Response:
        challenge = event.content.get("challenge", None)

        if not isinstance(challenge, str):
            self.logger.warning("Verification callback with missing or invalid challenge")
            return Response(400, "text/plain", b"Invalid or missing challenge")

        self.logger.info("Callback complete for %s", event.content)
        return Response(200, "text/plain", challenge.encode("utf-8"))

    def handle_reward_event(self, event: TwitchEvent) -> Response:
        reward_event = event.content.get("event", {})

        if not isinstance(reward_event, dict) or "reward" not in reward_event:
            self.logger.warning("No reward in redemption event")
            return Response(204, "text/plain", b"")

        reward = reward_event.get("reward", {})

        if not isinstance(reward, dict) or "id" not in reward:
            self.logger.warning("No id in redemption event reward")
            return Response(204, "text/plain", b"")

        if reward["id"] != "03979e28-d8c5-4985-8a32-fc27da71b3c1":
            self.logger.info("Skipping non-Snerge reward")
            return Response(204, "text/plain", b"")

        self.logger.info("Sending quote for reward")
        asyncio.run(self._bot.send_quote())

        return Response(204, "text/plain", b"")

    def load_event(self, environ: WSGIEnv) -> Optional[TwitchEvent]:
        # Check that we have all the data to load an event
        missing = [key for key in REQUIRED_HEADERS if key not in environ]
        if missing:
            self.logger.info("Missing headers from event: %s", missing)
            return None

        # Load the POST payload (JSON)
        try:
            length = int(environ["CONTENT_LENGTH"])
            payload = environ["wsgi.input"].read(length)  # type: ignore
            content = json.loads(payload)
        except (ValueError, json.JSONDecodeError) as err:
            self.logger.info("Unable to load json payload: %s", err)
            return None

        # Ensure that the JSON data is an object!
        if not isinstance(content, dict):
            self.logger.info("Payload is not a dict: %s", payload)
            return None

        # Create the event object
        return TwitchEvent(
            message_id=environ.get("HTTP_TWITCH_EVENTSUB_MESSAGE_ID", ""),
            timestamp=environ.get("HTTP_TWITCH_EVENTSUB_MESSAGE_TIMESTAMP", ""),
            signature=environ.get("HTTP_TWITCH_EVENTSUB_MESSAGE_SIGNATURE", ""),
            subscription_type=environ.get("HTTP_TWITCH_EVENTSUB_SUBSCRIPTION_TYPE", ""),
            message_type=environ.get("HTTP_TWITCH_EVENTSUB_MESSAGE_TYPE", ""),
            payload=payload,
            content=content,
        )

    async def register(self, username: str) -> None:
        self.logger.info("Loading token for %s", username)
        user = token.Token.load(username)

        if not user:
            self.logger.error("No token available for %s", username)

        data = {
            "type": "channel.channel_points_custom_reward_redemption.add",
            "version": "1",
            "condition": {
                "broadcaster_user_id": str(user.user_id),
            },
            "transport": {
                "method": "webhook",
                "callback": "https://snerge.tea-cats.co.uk/webhook",
                "secret": self.secret.decode("utf-8"),
            },
        }

        self.logger.info("Registering webhook for %s", username)

        response = requests.post(
            "https://api.twitch.tv/helix/eventsub/subscriptions",
            json=data,
            headers={
                "Content-type": "application/json",
                "Client-ID": self._app.client_id,
                "Authorization": "Bearer " + self._app.app_token,
            },
        )

        self.logger.warning("Webhook response: %s", response.json())
