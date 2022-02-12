#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

from typing import Any

import asyncio
from aiohttp import web

import prosegen
from snerge import bot, config as conf, logging, quotes, server, token


def process_task_exception(task: asyncio.Task[Any], logger: logging.Logger) -> None:
    try:
        exception = task.exception()
        if exception:
            logger.error(exception)
    except (asyncio.InvalidStateError, asyncio.CancelledError):
        pass


def main() -> None:
    # Configure logging
    logging.init()

    # Configure async
    event_loop = asyncio.get_event_loop()

    # Load our configuration
    logger = logging.get_logger()
    config = conf.config()
    data = prosegen.ProseGen(20)

    # Get, and refresh, the app token
    app = token.refresh_app_token()

    # Create the IRC bot
    irc_bot = bot.Bot(
        logger=logging.get_logger("bot"), loop=event_loop, app=app, config=config, quotes=data
    )

    # Create the web UI controller
    servlet = web.Application()

    # Add the handlers to the website
    handler2 = server.EventHandler(logging.get_logger("webhook"), app, irc_bot)
    servlet.router.add_route("POST", "/webhook", handler2.handle_webhook)

    handler3 = server.WhenceHandler(data)
    servlet.router.add_route("GET", "/whence/", handler3.handle_static)
    servlet.router.add_route("GET", "/whence/{path:.+}", handler3.handle_static)
    servlet.router.add_route("POST", "/whence/search", handler3.handle_search)

    handler1 = server.OAuthHandler(logging.get_logger("oauth"), app, handler2)
    servlet.router.add_route("GET", "/", handler1.handle)

    event_loop.create_task(quotes.load_data(logger, data))
    event_loop.create_task(handler2.register(config.channel))

    # Create the website container
    runner = web.AppRunner(
        servlet,
        handle_signals=False,
        access_log=logging.get_logger("server"),
        logger=logging.get_logger("server"),
    )
    event_loop.run_until_complete(runner.setup())

    site = web.TCPSite(runner, "127.0.0.2", 8888)

    # Run the bot
    _web = event_loop.create_task(site.start())
    _irc = event_loop.create_task(irc_bot.connect())

    try:
        event_loop.run_forever()
    except KeyboardInterrupt:
        logger.info("Interrupt received, exiting")
    except Exception as err:  # pylint: disable=broad-except
        logger.error("Loop exception: %s", err)

    logger.warning("Commencing shutdown")
    process_task_exception(_irc, logger)
    process_task_exception(_web, logger)

    logger.info("Shitting down IRC")
    event_loop.run_until_complete(irc_bot.stop())
    logger.info("Shitting down Web")
    event_loop.run_until_complete(site.stop())
    event_loop.run_until_complete(runner.cleanup())
    logger.info("Waiting for IRC to exit")
    event_loop.run_until_complete(_irc)
    process_task_exception(_irc, logger)
    logger.info("Waiting for Web to exit")
    event_loop.run_until_complete(_web)
    process_task_exception(_web, logger)
    logger.info("Closing event loop")
    event_loop.close()


if __name__ == "__main__":
    main()
