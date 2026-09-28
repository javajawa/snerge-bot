# SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

from collections.abc import Awaitable
from typing import TYPE_CHECKING, Any

import asyncio
import http
import json
import random

import aiohttp

from .guess import GuessMessageHandler
from .quotes import SnergeHandler
from .util import KnownBadges

if TYPE_CHECKING:
    import logging

    from prosegen import ProseGen

    from .config import Config
    from .token import Tokens
    from .util.twitch_stubs import (
        TwitchChatEvent,
        TwitchEvent,
        TwitchNotificationEvent,
        TwitchRewardRedemptionEvent,
    )

type Handler = Awaitable[Handler | None]


class SnergeBot:
    logger: logging.Logger
    session: aiohttp.ClientSession
    auth: Tokens
    config: Config
    guess_handler: GuessMessageHandler
    snerge_handler: SnergeHandler
    chat_event: asyncio.Event

    __slots__ = (
        "auth",
        "chat_event",
        "config",
        "guess_handler",
        "logger",
        "session",
        "snerge_handler",
    )

    def __init__(
        self,
        logger: logging.Logger,
        session: aiohttp.ClientSession,
        tokens: Tokens,
        config: Config,
        quotes: ProseGen,
    ) -> None:
        self.logger = logger
        self.session = session
        self.config = config
        self.auth = tokens
        self.guess_handler = GuessMessageHandler(
            use_latest_reply=config.use_latest_reply,
            stopguess_delay=config.stopguess_delay,
            closest_without_going_over=config.closest_without_going_over,
        )
        self.snerge_handler = SnergeHandler(logger.getChild("quotes"), config, quotes)
        self.chat_event = asyncio.Event()

    async def auto_time_loop(self) -> None:
        try:
            while True:
                if not self.chat_event.is_set():
                    self.logger.info("Waiting for next chat event")
                    await self.chat_event.wait()

                self.logger.debug("Sending automated quote")
                quote = self.snerge_handler.quote()
                next_call = random.randint(  # noqa: S311 - not cryptographic.
                    *self.config.auto_quote_time,
                )
                await self.send_message(quote)

                self.logger.info(
                    "Scheduling next automated quote in %d:%d",
                    next_call // 60,
                    next_call % 60,
                )

                # Queue the next attempt to send a quote
                await asyncio.sleep(next_call - self.config.chat_active_probe)
                self.logger.info("Clearing recent chat event flag before next quote")
                self.chat_event.clear()
                await asyncio.sleep(self.config.chat_active_probe)
        except asyncio.CancelledError:
            pass

    async def communication(self) -> None:
        handler = await self._handle_socket(
            "wss://eventsub.wss.twitch.tv/ws?keepalive_timeout_seconds=10",
            register=True,
            connected=asyncio.Future(),
        )
        while handler:
            handler = await handler

        await self.send_message("sergeSnerge Sleepy time!")

    async def _handle_socket(  # noqa: C901
        self,
        endpoint: str,
        *,
        register: bool,
        connected: asyncio.Future[bool],
    ) -> Handler | None:
        msg: aiohttp.WSMessage
        next_call: Handler | None = None

        try:
            self.logger.info("Connecting to websocket endpoint")
            async with self.session.ws_connect(endpoint) as socket:
                async for msg in socket:
                    if msg.type == aiohttp.WSMsgType.CLOSE:
                        self.logger.warning("Received close message")
                        break

                    if msg.type != aiohttp.WSMsgType.TEXT:
                        self.logger.warning(
                            "Unexpected %s message type",
                            msg.type,
                            extra={"packet": msg},
                        )
                        continue

                    data: TwitchEvent = msg.json()

                    match data["metadata"]["message_type"]:
                        case "session_welcome":
                            session_id = data["payload"]["session"]["id"]
                            self.logger.info("Session ID: %s", session_id)
                            if register:
                                self.logger.info("Registering subscriptions")
                                await self.register(session_id)
                                await self.send_message("Never fear, Snerge is here!")
                            connected.set_result(True)

                        case "session_keepalive":
                            pass

                        case "session_reconnect":
                            self.logger.info("Handling reconnect request")
                            callback: asyncio.Future[bool] = asyncio.Future()
                            next_call = self._handle_socket(
                                data["payload"]["session"]["reconnect_url"],
                                register=False,
                                connected=callback,
                            )
                            next_call = asyncio.create_task(next_call)

                            self.logger.info("Waiting for new socket to report ready")
                            await callback
                            self.logger.info("New socket connected")

                        case "notification":
                            try:
                                await self.notification(data["payload"])
                            except Exception as exp:
                                self.logger.exception(
                                    "Error handling notification",
                                    exc_info=exp,
                                    extra={"event": data},
                                )

                        case _:
                            self.logger.warning(
                                "Unknown event type: %s",
                                data["metadata"]["message_type"],
                            )

        except asyncio.CancelledError:
            self.logger.info("Ending websocket loop")
            return None

        self.logger.info("Websocket closed")

        return next_call

    async def notification(self, payload: dict[str, Any]) -> None:
        subscription_type = payload["subscription"]["type"]

        match subscription_type:
            case "channel.chat.message":
                await self.handle_chat_message(payload["event"])
            case "channel.chat.notification":
                await self.handle_chat_notification(payload["event"])
            case "channel.channel_points_custom_reward_redemption.add":
                await self.handle_reward_redemption(payload["event"])
            case "channel.update":
                self.logger.info(
                    "Stream updated to %s - %s",
                    payload["event"]["category_name"],
                    payload["event"]["title"],
                )
            case _:
                self.logger.info(
                    "Unhandled notification for subscription %s",
                    subscription_type,
                    extra=payload,
                )

    async def handle_chat_message(self, event: TwitchChatEvent) -> None:
        if event["chatter_user_id"] == str(self.auth.chatter_id):
            return
        if event["broadcaster_user_id"] != self.auth.broadcaster_id:
            return
        if KnownBadges.BOT in event["badges"]:
            return

        # Note when chat last happened
        self.chat_event.set()

        text = event["message"]["text"]
        if text.startswith("!guess "):
            self.logger.debug("Passing '%s' to guess handler", text)
            async for resp in self.guess_handler.message_process(event):
                await self.send_message(resp)

        elif text.startswith("!snerge"):
            self.logger.debug("Passing '%s' to snerge handler", text)
            quote = self.snerge_handler.quote(text.removeprefix("!snerge").strip())
            await self.send_message(quote)
        elif text.startswith("!snuwuge"):
            self.logger.debug("Passing '%s' to snerge handler", text)
            quote = self.snerge_handler.quote(text.removeprefix("!snuwuge").strip(), force_owo=True)
            await self.send_message(quote)

        elif text.startswith(("!subscribe", "!unsubscribe")):
            self.logger.debug("Passing '%s' to subscribe handler", text)
            if reply := self.snerge_handler.subscribe(event):
                await self.send_message(reply)

    async def handle_chat_notification(self, event: TwitchNotificationEvent) -> None:
        if event[event["notice_type"]] is None:
            self.logger.warning("Receive notification %s without data", event["notice_type"])
            return

        match event["notice_type"]:
            case "resub":
                if event["resub"]:
                    self.logger.info(
                        "%s resubscribed as tier %s for %d months (%d months total)",
                        event["chatter_user_name"],
                        event["resub"]["sub_tier"],
                        event["resub"]["duration_months"],
                        event["resub"]["cumulative_months"],
                    )

            case "sub_gift":
                if event["sub_gift"]:
                    self.logger.info(
                        "%s gifted %s to %s",
                        event["chatter_user_name"],
                        event["sub_gift"]["sub_tier"],
                        event["sub_gift"]["recipient_user_name"],
                    )

            case _:
                self.logger.info(
                    "%s performed action %s",
                    event["chatter_user_name"],
                    event["notice_type"],
                    extra=event[event["notice_type"]],
                )

    async def handle_reward_redemption(self, event: TwitchRewardRedemptionEvent) -> None:
        if event["reward"]["id"] != "03979e28-d8c5-4985-8a32-fc27da71b3c1":
            return

        self.logger.info("Reward redeemed by %s", event["user_name"], extra=event)
        quote = self.snerge_handler.quote()
        await self.send_message(event["user_name"] + " " + quote)

    async def send_message(self, message: str) -> None:
        response = await self.session.post(
            "https://api.twitch.tv/helix/chat/messages",
            headers={
                "Content-type": "application/json",
                "Client-ID": self.auth.client_id,
                "Authorization": "Bearer " + self.auth.app_token,
            },
            json={
                "broadcaster_id": self.auth.broadcaster_id,  # SergeYager
                "sender_id": self.auth.chatter_id,  # SnergeBot
                "message": message,
            },
        )

        payload = await response.json()
        if "data" not in payload:
            pass

        sent = payload.get("data", [{}])[0].get("is_sent", False)
        reason = payload.get("data", [{}])[0].get("drop_reason", payload.get("message"))

        self.logger.info(
            "Sent message '%s'",
            message,
            extra={"status": response.status, "sent": sent, "reason": reason},
        )

    async def register(self, session_id: str) -> None:
        user_events: dict[str, str] = {
            "channel.chat.message": "1",
            "channel.chat.message_delete": "1",
            "channel.update": "2",
            "channel.chat.notification": "1",
        }

        for event_type, version in user_events.items():
            config = {
                "type": event_type,
                "version": version,
                "condition": {
                    "broadcaster_user_id": self.auth.broadcaster_id,
                    "user_id": self.auth.broadcaster_id,
                },
                "transport": {"method": "websocket", "session_id": session_id},
            }
            await self.register_eventsub(self.auth.broadcaster_token, config)

        channel_events: dict[str, str] = {
            "channel.channel_points_custom_reward_redemption.add": "1",
            "channel.bits.use": "1",
        }

        for event_type, version in channel_events.items():
            config = {
                "type": event_type,
                "version": version,
                "condition": {
                    "broadcaster_user_id": self.auth.broadcaster_id,
                },
                "transport": {"method": "websocket", "session_id": session_id},
            }
            await self.register_eventsub(self.auth.broadcaster_token, config)

    async def register_eventsub(self, auth: str, config: dict[str, Any]) -> None:
        response = await self.session.post(
            "https://api.twitch.tv/helix/eventsub/subscriptions",
            headers={
                "Content-type": "application/json",
                "Client-ID": self.auth.client_id,
                "Authorization": "Bearer " + auth,
            },
            json=config,
        )

        if response.status == http.HTTPStatus.ACCEPTED:
            self.logger.info("Subscription result %d for %s", response.status, config["type"])
        else:
            try:
                data = await response.json()
            except (aiohttp.ContentTypeError, json.JSONDecodeError):
                data = {"resp": await response.text()}

            if "message" in data:
                data[".message"] = data["message"]
                del data["message"]
            if "level" in data:
                data[".level"] = data["level"]
                del data["level"]

            self.logger.error(
                "Error %s subscribing to %s",
                response.status,
                config["type"],
                extra=data,
            )
