# SPDX-FileCopyrightText: 2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

from types import TracebackType
from typing import TYPE_CHECKING, Any

import asyncio
import collections
import logging
import sys
import traceback

from pythonjsonlogger.json import JsonFormatter as _JsonFormatter

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

try:
    from systemd.journal import JournalHandler  # type: ignore[import-not-found]
except ImportError:
    from typing import TextIO

    class JournalHandler(logging.StreamHandler[TextIO]):  # type: ignore[no-redef]
        def __init__(self, *, SYSLOG_IDENTIFIER: str) -> None:  # noqa: N803,ARG002
            super().__init__()


_SysExcInfoType = (
    tuple[type[BaseException], BaseException, TracebackType | None] | tuple[None, None, None]
)

Logger = logging.Logger


def init(loop: asyncio.AbstractEventLoop) -> BufferedHandler:
    logger = logging.getLogger("snerge")
    buffer = BufferedHandler(loop)
    logger.addHandler(buffer)

    if sys.stdout.isatty():
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
    else:
        handler = JournalHandler(SYSLOG_IDENTIFIER="snerge-bot")
        handler.setFormatter(JsonFormatter())

        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    def handle_exception(
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_traceback: TracebackType | None,
    ) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        logger.exception("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = handle_exception
    return buffer


def get_logger(name: str = "") -> logging.Logger:
    if not name:
        return logging.getLogger("snerge")

    return logging.getLogger("snerge." + name)


class BufferedHandler(logging.Handler):
    _data: collections.deque[logging.LogRecord]
    _loop: asyncio.AbstractEventLoop
    _tasks: set[asyncio.Task[None]]
    _sinks: list[Callable[[logging.LogRecord], Awaitable[None]]]

    def __init__(self, loop: asyncio.AbstractEventLoop, level: int = logging.NOTSET) -> None:
        super().__init__(level)
        self._name = "Buffer"
        self._loop = loop
        self._data = collections.deque(maxlen=100)
        self._tasks = set()
        self._sinks = []

    def add_sink(self, sink: Callable[[logging.LogRecord], Awaitable[None]]) -> None:
        self._sinks.append(sink)

    def emit(self, record: logging.LogRecord) -> None:
        self._data.append(record)
        if not self._sinks:
            return

        task = self._loop.create_task(self._fanout(record))
        task.add_done_callback(self._tasks.discard)
        self._tasks.add(task)

    async def _fanout(self, record: logging.LogRecord) -> None:
        await asyncio.gather(*(x(record) for x in self._sinks))

    def get_history(self) -> collections.abc.Iterator[logging.LogRecord]:
        return iter(self._data)


class JsonFormatter(_JsonFormatter):
    def add_fields(
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        log_record["level"] = record.levelname
        log_record["logger"] = record.name

        super().add_fields(log_record, record, message_dict)

    def formatException(  # type: ignore[override]  # noqa: N802 inherited function name
        self,
        ei: _SysExcInfoType,
    ) -> dict[str, Any] | None:
        exc_type, exc_value, exc_traceback = ei
        if exc_type is None or exc_value is None:
            return None

        trace = traceback.extract_tb(exc_traceback)

        return {
            "type": exc_type.__name__,
            "message": str(exc_value),
            "traceback": [
                {
                    "source": f"{frame.filename}:{frame.lineno}",
                    "method": frame.name,
                    "code": frame.line,
                    "locals": frame.locals,
                }
                for frame in reversed(trace)
            ],
            "cause": (
                self.formatException(
                    (
                        type(exc_value.__cause__),
                        exc_value.__cause__,
                        exc_value.__cause__.__traceback__,
                    ),
                )
                if exc_value.__cause__
                else None
            ),
        }


__all__ = "BufferedHandler", "Logger", "get_logger", "init"
