#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

import threading

from snerge import bot, config as conf, logging, quotes, server, token


# Configure logging
logging.init()

# Load our configuration
logger = logging.get_logger()
config = conf.config()
data = quotes.load_data(logger)

# Get, and refresh, the app token
app = token.refresh_app_token()

# Create the IRC bot
bot = bot.Bot(logger=logging.get_logger("bot"), app=app, config=config, quotes=data)
bot_thread = threading.Thread(name="snerge-bot", target=bot.run)

# Create the web UI controller
servlet = server.Servlet(logging.get_logger("server"))
unicorn = server.StandAlone(servlet, {"bind": "127.0.1.2:8888", "workers": 1})

# Add the handlers to the website
handler1 = server.OAuthHandler(logging.get_logger("oauth"), app)
servlet.register_handler("/", handler1.handle)
handler2 = server.EventHandler(logging.get_logger("webhook"), app, config, bot)
servlet.register_handler("/webhook", handler2.handle_webhook)
handler3 = server.WhenceHandler(data)
servlet.register_handler("/whence", handler3.handle_page)
servlet.register_handler("/whence.json", handler3.handle_search)

try:
    logger.info("Starting up IRC bot")
    bot_thread.start()
    logger.info("Starting up web server")
    unicorn.run()
except KeyboardInterrupt:
    pass
finally:
    logger.warning("Closing down IRC bot")
    bot.loop.create_task(bot.stop())
    bot_thread.join()
