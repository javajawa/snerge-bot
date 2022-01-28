#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable

import gunicorn.app.base  # type: ignore

from snerge import logging
from .base import Response, WSGICallback, WSGIEnv
from .oauth import OAuthHandler
from .eventsub import EventHandler


class StandAlone(gunicorn.app.base.Application):  # type: ignore
    servlet: Servlet
    options: Dict[str, Any]

    def __init__(self, servlet: Servlet, options: Dict[str, Any]):
        self.servlet = servlet
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

    def load(self) -> Servlet:
        return self.servlet


class Servlet:
    handlers: Dict[str, Callable[[WSGIEnv], Response]]
    logger: logging.Logger

    def __init__(self, logger: logging.Logger) -> None:
        self.handlers = {}
        self.logger = logger

    def __call__(self, environ: WSGIEnv, start: WSGICallback) -> Iterable[bytes]:
        path = environ.get("PATH_INFO", "/")

        response = self._handle(path, environ)

        start(response.get_status(), response.get_headers())

        return response.get_contents()

    def register_handler(self, path: str, handler: Callable[[WSGIEnv], Response]) -> None:
        self.handlers[path] = handler

    def _handle(self, path: str, environ: WSGIEnv) -> Response:
        if path not in self.handlers:
            self.logger.info("Path not mapped: %s", path)
            return self._render404()

        handler = self.handlers[path]
        response = handler(environ)

        if not isinstance(response, Response):
            self.logger.error(
                "Request to path %s handled by %s returned non-Response object (type %s)",
                path,
                handler,
                type(response),
            )
            response = Response(500, "text/plain", b"An error occurred")

        return response

    @staticmethod
    def _render404() -> Response:
        return Response(404, "text/plain", b"Not Found")


__all__ = ["StandAlone", "Servlet", "OAuthHandler", "EventHandler"]
