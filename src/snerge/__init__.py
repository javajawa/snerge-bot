# SPDX-FileCopyrightText: 2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

import asyncio
import pathlib

import aiohttp
from aiohttp import web

import prosegen

from . import bot, quotes, server, token
from .config import config as load_config
from .runner import AsyncRunner
from .util import log


def entrypoint() -> None:
    asyncio.run(main())


async def main() -> None:
    # Configure logging
    loop = asyncio.get_running_loop()
    buffer = log.init(loop=loop)
    logger = log.get_logger()

    # Configure async
    logger.info("Configuring async runner")
    async with AsyncRunner(log.get_logger("runner")) as coord:
        # Load our configuration
        logger.info("Loading configuration")
        conf = load_config()

        # Create HTTP session
        session = aiohttp.ClientSession()

        tokens = token.Tokens(
            app=token.App.load(),
            chatter=token.Token.load(conf.chatter),
            broadcaster=token.Token.load(conf.broadcaster),
        )

        # Queue loading in the quotes database.
        data = prosegen.ProseGen(20)

        snerge = bot.SnergeBot(logger.getChild("bot"), session, tokens, conf, data)

        # Create the HTTP daemon and attack the handlers.
        logger.info("Running start up processes")
        httpd, _, _ = await asyncio.gather(
            coord.create_onetime_task(
                "setup-httpd",
                create_httpd(tokens, session, snerge, buffer, data),
            ),
            coord.create_onetime_task("token-refresh", tokens.refresh(session)),
            coord.create_background_task(quotes.load_data, logger, data),
        )

        logger.info("Running main processes")
        coord.create_main_task("twitch-webhook", snerge.communication())
        coord.create_main_task("auto-timer", snerge.auto_time_loop())

        await coord

        logger.info("Commencing shutdown")
    # __aexit__ called here
    logger.info("Complete shutdown of main runner loop")

    await httpd.shutdown()
    logger.info("Complete shutdown of HTTP daemon")

    await session.close()
    logger.info("Complete shutdown of HTTP client")


async def create_httpd(
    tokens: token.Tokens,
    session: aiohttp.ClientSession,
    snerge: bot.SnergeBot,
    buffer: log.BufferedHandler,
    data: prosegen.ProseGen,
) -> web.AppRunner:
    # Create the web UI controller
    servlet = web.Application()

    servlet.router.add_route("GET", "/", _handle_static)
    servlet.router.add_route("GET", "/{path:.+}", _handle_static)

    loglet = server.LoggingHandler(snerge, buffer)
    servlet.router.add_route("POST", "/log/history", loglet.get_history)
    servlet.router.add_route("GET", "/log/stream", loglet.read_stream)

    whence = server.WhenceHandler(data)
    servlet.router.add_route("POST", "/whence/search", whence.handle_search)

    predict = server.PredictHandler(data)
    servlet.router.add_route("GET", "/predict/dictionary", predict.get_dictionary)
    servlet.router.add_route("POST", "/predict/predict", predict.make_prediction)

    oauth = server.OAuthHandler(log.get_logger("oauth"), session, tokens.oauth_app)
    servlet.router.add_route("GET", "/oauth", oauth.handle)

    # Create the website container
    _runner = web.AppRunner(
        servlet,
        handle_signals=False,
        logger=log.get_logger("server"),
    )

    await _runner.setup()
    site = web.TCPSite(_runner, "127.0.0.2", 8888)
    await site.start()
    log.get_logger("server").info("HTTP server started at %s", site.name)

    return _runner


async def _handle_static(request: web.Request) -> web.FileResponse:
    content_root = pathlib.Path("html")
    content_types = {
        ".css": "text/css",
        ".js": "application/javascript",
        ".json": "application/json",
    }

    path_str = request.match_info.get("path", "")

    if path_str == "":
        path = content_root / "index.html"
    elif request.path.endswith("/"):
        path = content_root / path_str
        path = path / (path.name + ".html")
    else:
        path = content_root / path_str

    return web.FileResponse(
        status=200,
        headers={"Content-Type": content_types.get(path.suffix, "text/html")},
        path=path,
    )
