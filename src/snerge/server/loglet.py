# SPDX-FileCopyrightText: 2026 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

from typing import TYPE_CHECKING

import asyncio
import json
import time

from aiohttp.web import (
    HTTPAccepted,
    HTTPForbidden,
    Request,
    Response,
    StreamResponse,
    WebSocketResponse,
)

from .oauth import AUTH_VAR, JWTData
from .util import SetEncoder

if TYPE_CHECKING:
    import logging

    from snerge.bot import SnergeConnectionManager
    from snerge.util.log import BufferedHandler


class LoggingHandler:
    logger: logging.Logger
    bot: SnergeConnectionManager
    buffer: BufferedHandler
    sockets: set[WebSocketResponse]

    def __init__(
        self,
        logger: logging.Logger,
        bot: SnergeConnectionManager,
        buffer: BufferedHandler,
    ) -> None:
        self.logger = logger
        self.bot = bot
        self.buffer = buffer
        self.sockets = set()
        self.buffer.add_sink(self.fanout)

    def _can(self, user: JWTData) -> bool:
        return (
            "sergeyager" in user["snerge.tea-cats.co.uk/moderated_channels"]
            or "cuddly_kitteh" in user["snerge.tea-cats.co.uk/moderated_channels"]
        )

    async def get_history(self, request: Request) -> Response:
        user = request[AUTH_VAR]
        if not self._can(user):
            return Response(
                status=403,
                content_type="application/json",
                text=json.dumps(
                    [
                        {
                            "time": time.time(),
                            "logger": "auth",
                            "level": "error",
                            "message": f"{user['name']} is not authorized to see logs",
                        },
                    ],
                ),
            )

        return Response(
            status=200,
            content_type="application/json",
            text=json.dumps(list(self.buffer.get_history()), cls=SetEncoder),
        )

    async def reconnect(self, request: Request) -> Response:
        user = request[AUTH_VAR]

        if not self._can(user):
            return HTTPForbidden()

        self.logger.info("Reconnect requested by %s", user["name"])

        await self.bot.reconnect()
        return HTTPAccepted()

    async def fanout(self, record: logging.LogRecord) -> None:
        if self.sockets:
            await asyncio.gather(
                *(socket.send_json(record, dumps=SetEncoder().encode) for socket in self.sockets),
            )

    async def read_stream(self, request: Request) -> StreamResponse:
        if not self._can(request[AUTH_VAR]):
            return HTTPForbidden()

        socket = WebSocketResponse()

        await socket.prepare(request)
        self.sockets.add(socket)

        async for _ in socket:
            pass

        self.sockets.discard(socket)

        return socket
