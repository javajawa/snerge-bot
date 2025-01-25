#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

import asyncio
import logging

import aiohttp.client
from snerge import log, token


def main() -> None:
    # Configure logging
    log.init()
    logger = log.get_logger("download")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    downloader = QuoteDownloader(logger, loop)
    downloader()


class QuoteDownloader:
    loop: asyncio.AbstractEventLoop
    logger: logging.Logger
    app: token.App
    user_token: token.Token

    def __init__(self, logger: logging.Logger, loop: asyncio.AbstractEventLoop) -> None:
        self.logger = logger
        self.loop = loop
        self.session = aiohttp.ClientSession(loop=loop)
        self.app = token.refresh_app_token()
        self.user_token = token.Token.load("snergebot")

    def __del__(self) -> None:
        self.loop.run_until_complete(self.session.close())
        self.loop.close()

    def __call__(self) -> None:
        self.loop.run_until_complete(self.communication())

    async def communication(self) -> None:
        with open("output.txt", "a", encoding="utf-8") as file:
            async with self.session.ws_connect(
                "wss://eventsub.wss.twitch.tv/ws?keepalive_timeout_seconds=60"
            ) as socket:
                welcome: aiohttp.WSMessage = await anext(socket)
                welcome_data = welcome.json()

                session_id = welcome_data["payload"]["session"]["id"]
                self.logger.info("Session ID: %s", session_id)

                await self.register(session_id)
                task = self.loop.create_task(self.query())

                msg: aiohttp.WSMessage
                async for msg in socket:
                    if msg.type != aiohttp.WSMsgType.TEXT:
                        self.logger.warning(
                            "Unexpected %s message type", msg.type, extra={"msg": msg}
                        )
                        continue

                    data = msg.json()

                    if data["payload"]["subscription"]["type"] != "channel.chat.message":
                        continue
                    if data["payload"]["event"]["chatter_user_id"] == self.user_token.user_id:
                        continue
                    file.write(data["payload"]["event"]["message"]["text"] + "\n")
                    file.flush()

        task.cancel()
        await task

    async def query(self) -> None:
        for quote in range(2780, 2830):
            await asyncio.sleep(10)
            await self.send_message(f"!unosearch {quote}")

    async def send_message(self, message: str) -> None:
        response = await self.session.post(
            "https://api.twitch.tv/helix/chat/messages",
            headers={
                "Content-type": "application/json",
                "Client-ID": self.app.client_id,
                "Authorization": "Bearer " + self.user_token.access_token,
            },
            json={
                "broadcaster_id": "73022083",  # SergeYager
                "sender_id": self.user_token.user_id,  # SnergeBot
                "message": message,
            },
        )
        self.logger.info("Sent message %s: status=%d", message, response.status)

    async def register(self, session_id: str) -> None:
        self.user_token.renew(self.app)

        response = await self.session.post(
            "https://api.twitch.tv/helix/eventsub/subscriptions",
            headers={
                "Content-type": "application/json",
                "Client-ID": self.app.client_id,
                "Authorization": "Bearer " + self.user_token.access_token,
            },
            json={
                "type": "channel.chat.message",
                "version": "1",
                "condition": {
                    "broadcaster_user_id": "73022083",  # SergeYager
                    "user_id": str(self.user_token.user_id),  # SnergeBot
                },
                "transport": {"method": "websocket", "session_id": session_id},
            },
        )

        self.logger.warning("Subscription result %d", response.status)
        self.logger.warning(await response.json())
        if response.status != 202:
            raise RuntimeError


if __name__ == "__main__":
    main()
