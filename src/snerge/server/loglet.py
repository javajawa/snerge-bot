# SPDX-FileCopyrightText: 2026 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

from typing import TYPE_CHECKING

import asyncio
import json

from aiohttp.web import Request, Response, WebSocketResponse

from .util import SetEncoder

if TYPE_CHECKING:
    import logging

    from snerge.bot import SnergeBot
    from snerge.util.log import BufferedHandler


class LoggingHandler:
    bot: SnergeBot
    buffer: BufferedHandler
    sockets: set[WebSocketResponse]

    def __init__(self, bot: SnergeBot, buffer: BufferedHandler) -> None:
        self.bot = bot
        self.buffer = buffer
        self.sockets = set()
        self.buffer.add_sink(self.fanout)

    async def get_history(self, _: Request) -> Response:
        return Response(
            status=200,
            content_type="application/json",
            text=json.dumps(list(self.buffer.get_history()), cls=SetEncoder),
        )

    async def fanout(self, record: logging.LogRecord) -> None:
        if self.sockets:
            await asyncio.gather(
                *(socket.send_json(record, dumps=SetEncoder().encode) for socket in self.sockets),
            )

    async def read_stream(self, request: Request) -> WebSocketResponse:
        socket = WebSocketResponse()

        await socket.prepare(request)
        self.sockets.add(socket)

        async for _ in socket:
            pass

        self.sockets.discard(socket)

        return socket
