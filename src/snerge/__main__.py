#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

from typing import Awaitable, Callable

import asyncio

from aiohttp import web

import prosegen
from snerge import bot, config as conf, log, quotes, server, token, AsyncRunner


def main() -> None:
    # Configure logging
    log.init()

    # Configure async
    runner = AsyncRunner(log.get_logger("runner"))
    asyncio.set_event_loop(runner.loop)

    # Load our configuration
    logger = log.get_logger()
    config = conf.config()
    data = prosegen.ProseGen(20)

    # Get, and refresh, the app token
    app = token.refresh_app_token()

    # Create the IRC bot
    irc_bot = bot.Bot(
        logger=log.get_logger("bot"),
        loop=runner.loop,
        app=app,
        config=config,
        quotes=data,
    )

    # Queue loading in the quotes database.
    runner.create_onetime_task("quote-loader", quotes.load_data(logger, data))

    # Create the event subscription handle, and initialise of it.
    event_subscription_handler = server.EventHandler(log.get_logger("webhook"), app, irc_bot)
    register = runner.create_onetime_task(
        "register-webhooks", event_subscription_handler.register(config.channel)
    )

    # Create the HTTP daemon and attack the handlers.
    site_setup = runner.create_onetime_task(
        "setup-httpd", create_httpd(app, data, event_subscription_handler.handle_webhook)
    )

    # Run the setup tasks until they are complete.
    runner.gather(register, site_setup)

    # Run the bot
    _irc = runner.create_main_task("twitch-irc-bot", irc_bot.queue_quote())

    runner.run_forever()

    logger.warning("Commencing shutdown")
    irc_bot.request_stop()
    runner.gather(_irc, site_setup.result().server.shutdown())


async def create_httpd(
    app: token.App,
    data: prosegen.ProseGen,
    event_handler: Callable[[web.Request], Awaitable[web.StreamResponse]],
) -> web.AppRunner:
    # Create the web UI controller
    servlet = web.Application()

    # Add the handlers to the website
    servlet.router.add_route("POST", "/webhook", event_handler)

    handler3 = server.WhenceHandler(data)
    servlet.router.add_route("GET", "/whence/", handler3.handle_static)
    servlet.router.add_route("GET", "/whence/{path:.+}", handler3.handle_static)
    servlet.router.add_route("POST", "/whence/search", handler3.handle_search)

    handler1 = server.OAuthHandler(log.get_logger("oauth"), app)
    servlet.router.add_route("GET", "/", handler1.handle)

    # Create the website container
    runner = web.AppRunner(
        servlet,
        handle_signals=False,
        access_log=log.get_logger("server"),
        logger=log.get_logger("server"),
    )

    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.2", 8888)
    await site.start()

    return runner


if __name__ == "__main__":
    main()
