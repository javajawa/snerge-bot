# SPDX-FileCopyrightText: 2021 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

from typing import TYPE_CHECKING, Any, ParamSpec, Self

import asyncio
import concurrent.futures
import signal

if TYPE_CHECKING:
    import types
    from collections.abc import Callable, Coroutine, Generator

    import logging


Params = ParamSpec("Params")


class AsyncRunner:
    _loop: asyncio.AbstractEventLoop
    _logger: logging.Logger
    _pool: concurrent.futures.ThreadPoolExecutor
    _tasks: set[asyncio.Task[Any] | asyncio.Future[Any]]

    def __init__(self, logger: logging.Logger) -> None:
        self._loop = asyncio.get_event_loop()
        self._logger = logger
        self._pool = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        self._loop.set_default_executor(self._pool)
        self._tasks = set()
        self._shutdown_event = asyncio.Event()

        try:
            self._loop.add_signal_handler(signal.SIGINT, self.stop_loop)
            self._loop.add_signal_handler(signal.SIGTERM, self.stop_loop)
        except NotImplementedError:
            # We're probably running on Windows, where this is not an option
            pass

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        return self._loop

    def __await__(self) -> Generator[None, None, bool]:
        return self._shutdown_event.wait().__await__()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        self._shutdown_event.set()
        for task in self._tasks:
            task.cancel()
        results = await asyncio.gather(*self._tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                self._logger.exception("Error found during shutdown", exc_info=result)

        self._pool.shutdown(cancel_futures=True)

    def create_onetime_task[T](
        self,
        name: str,
        future: Coroutine[None, None, T],
    ) -> asyncio.Task[T]:
        task: asyncio.Task[T] = self._loop.create_task(future, name=name)
        self._tasks.add(task)
        task.add_done_callback(self.process_task_exception)
        task.add_done_callback(self._tasks.discard)

        return task

    def create_background_task[**P, T](
        self,
        func: Callable[P, T],
        *args: P.args,
        **_: P.kwargs,
    ) -> asyncio.Future[T]:
        future: asyncio.Future[T] = self._loop.run_in_executor(self._pool, func, *args)
        self._tasks.add(future)
        future.add_done_callback(self.process_task_exception)
        future.add_done_callback(self._tasks.discard)
        return future

    def process_task_exception[T](self, task: asyncio.Task[T] | asyncio.Future[T]) -> None:
        if isinstance(task, asyncio.Task):
            self._logger.info("Task %s is %s", task.get_name(), "done" if task.done() else task)

        try:
            exception = task.exception()
            if exception:
                self._logger.error(exception)
        except (asyncio.InvalidStateError, asyncio.CancelledError):
            pass

    def stop_loop[T](self, task: asyncio.Task[T] | None = None) -> None:
        if self._shutdown_event.is_set():
            return

        if task:
            self._logger.info("Loop stop called due to main task %s exiting", task.get_name())
            self.process_task_exception(task)
        else:
            self._logger.info("Shutdown triggered by external signal")

        self._shutdown_event.set()

    def create_main_task(
        self,
        name: str,
        future: Coroutine[None, None, None],
    ) -> asyncio.Task[None]:
        task: asyncio.Task[None] = self._loop.create_task(future, name=name)
        task.add_done_callback(self.stop_loop)
        task.add_done_callback(self._tasks.discard)
        self._tasks.add(task)

        return task


__all__ = ("AsyncRunner",)
