#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause
from __future__ import annotations

import asyncio
import signal
from asyncio import Task
from typing import Coroutine, Any, Optional

from snerge import logging


class AsyncRunner:
    _loop: asyncio.AbstractEventLoop
    _logger: logging.Logger

    def __init__(self, logger: logging.Logger):
        self._loop = asyncio.new_event_loop()
        self._logger = logger

        try:
            self._loop.add_signal_handler(signal.SIGINT, self.stop_loop)
            self._loop.add_signal_handler(signal.SIGTERM, self.stop_loop)
        except NotImplementedError:
            # We're probably running on Windows, where this is not an option
            pass

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        return self._loop

    def create_onetime_task(self, name: str, future: Coroutine[Any, Any, Any]) -> Task[Any]:
        task = self._loop.create_task(future)
        task.set_name(name)
        task.add_done_callback(self.process_task_exception)

        return task

    def process_task_exception(self, task: Task[Any]) -> None:
        self._logger.info("Task %s is %s", task.get_name(), "done" if task.done() else task)

        try:
            exception = task.exception()
            if exception:
                self._logger.error(exception)
        except (asyncio.InvalidStateError, asyncio.CancelledError):
            pass

    def stop_loop(self, task: Optional[Task[Any]] = None) -> None:
        if task:
            self._logger.info("Loop stop called by %s", task.get_name())
            self.process_task_exception(task)

        self._loop.stop()

    def create_main_task(self, name: str, future: Coroutine[Any, Any, Any]) -> Task[Any]:
        task = self._loop.create_task(future, name=name)
        task.add_done_callback(self.stop_loop)

        return task

    def gather(self, *future: Any) -> None:
        for task in future:
            self._loop.run_until_complete(task)

    def run_forever(self) -> None:
        self._loop.run_forever()
