#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

from typing import Dict, Optional, Union

import dataclasses
import hashlib
import hmac
import json
import requests

from aiohttp.web import Request, Response

from snerge import bot, log, token


REQUIRED_HEADERS = [
    "Twitch-Eventsub-Message-Id",
    "Twitch-Eventsub-Message-Signature",
    "Twitch-Eventsub-Message-Timestamp",
    "Twitch-Eventsub-Message-Type",
    "Twitch-Eventsub-Subscription-Type",
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
    logger: log.Logger

    _app: token.App
    _bot: bot.Bot

    def __init__(self, logger: log.Logger, app: token.App, _bot: bot.Bot) -> None:
        self.logger = logger
        self._app = app
        self._bot = _bot

    async def handle_webhook(self, request: Request) -> Response:
        event = await self.load_event(request)

        if not event:
            self.logger.warning("Received invalid event")
            return Response(status=400, content_type="text/plain", text="Invalid event")

        if not any(map(event.signature_valid, [b"hello_i_am_snerge", b"hello_my_world"])):
            self.logger.warning("Received event with invalid signature")
            return Response(status=400, content_type="text/plain", text="Incorrect Signature")

        self.logger.debug("%s web-hook event %s", event.subscription_type, event.message_type)

        if event.message_type == "webhook_callback_verification":
            return self.handle_verification_event(event)

        if event.subscription_type == "channel.channel_points_custom_reward_redemption.add":
            return await self.handle_reward_event(event)

        if event.subscription_type != "channel.follow":
            self.logger.info(json.dumps(event.content, indent="  "))

        return Response(status=204, content_type="text/plain", body=b"")

    def handle_verification_event(self, event: TwitchEvent) -> Response:
        challenge = event.content.get("challenge", None)

        if not isinstance(challenge, str):
            self.logger.warning("Verification callback with missing or invalid challenge")
            return Response(
                status=400, content_type="text/plain", text="Invalid or missing challenge"
            )

        data = event.content.get("data", {})
        if isinstance(data, dict):
            self.logger.info("%s", data)
            self.logger.info("Callback complete for %s %s", data.get("type"), data.get("id"))
        return Response(status=200, content_type="text/plain", text=challenge)

    async def handle_reward_event(self, event: TwitchEvent) -> Response:
        reward_event = event.content.get("event", {})

        if not isinstance(reward_event, dict) or "reward" not in reward_event:
            self.logger.warning("No reward in redemption event")
            return Response(status=204, content_type="text/plain", body=b"")

        reward: Union[str, Dict[str, Union[Dict[str, str], str]]] = reward_event.get(
            "reward", {}
        )

        if not isinstance(reward, dict) or "id" not in reward:
            self.logger.warning("No id in redemption event reward")
            return Response(status=204, content_type="text/plain", body=b"")

        if reward["id"] != "03979e28-d8c5-4985-8a32-fc27da71b3c1":
            self.logger.debug("Skipping non-Snerge reward")
            return Response(status=204, content_type="text/plain", body=b"")

        self.logger.info("Sending quote for reward")
        await self._bot.send_quote()

        return Response(status=204, content_type="text/plain", body=b"")

    async def load_event(self, request: Request) -> Optional[TwitchEvent]:
        # Check that we have all the data to load an event
        missing = [key for key in REQUIRED_HEADERS if key not in request.headers]

        if missing:
            self.logger.info("Missing headers from event: %s", missing)
            return None

        # Load the POST payload (JSON)
        try:
            payload = await request.read()
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
            message_id=request.headers.get("Twitch-Eventsub-Message-Id", ""),
            timestamp=request.headers.get("Twitch-Eventsub-Message-Timestamp", ""),
            signature=request.headers.get("Twitch-Eventsub-Message-Signature", "="),
            message_type=request.headers.get("Twitch-Eventsub-Message-Type", ""),
            subscription_type=request.headers.get("Twitch-Eventsub-Subscription-Type", ""),
            payload=payload,
            content=content,
        )

    async def register(self, username: str) -> None:
        self.logger.info("Loading token for %s", username)
        user = token.Token.load(username)

        if not user:
            self.logger.error("No token available for %s", username)

        user.renew(self._app)

        for event_type in [
            "channel.channel_points_custom_reward_redemption.add",
        ]:
            data = {
                "type": event_type,
                "version": "1",
                "condition": {
                    "broadcaster_user_id": str(user.user_id),
                },
                "transport": {
                    "method": "webhook",
                    "callback": "https://snerge.tea-cats.co.uk/webhook",
                    "secret": self._app.webhook_secret.decode("utf-8"),
                },
            }

            self.logger.info("Registering %s webhook for %s", event_type, username)

            response = requests.post(
                "https://api.twitch.tv/helix/eventsub/subscriptions",
                json=data,
                headers={
                    "Content-type": "application/json",
                    "Client-ID": self._app.client_id,
                    "Authorization": "Bearer " + self._app.app_token,
                },
                timeout=15,
            )

            subscription = response.json()

            if not isinstance(subscription, dict):
                self.logger.error("Unable to parse subscription response %s", subscription)
                continue

            if "data" in subscription:
                self.logger.info(
                    "Subscribe to %s for %s: %s",
                    event_type,
                    username,
                    subscription["data"][0]["id"],
                )
                continue

            error = subscription.get("error", "")
            message = subscription.get("message", "")

            if error == "Conflict" and message == "subscription already exists":
                self.logger.info("Using old subscription for %s for %s", event_type, username)
                continue

            self.logger.warning(
                "Error subscribing to %s for %s: %s", event_type, username, message
            )
