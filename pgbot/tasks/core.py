"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file implements the base classes for a task object system that
can be used to implement background processes for the bot. 
"""

from __future__ import annotations
import asyncio
from collections import deque
import datetime
import itertools
from types import SimpleNamespace
from typing import Any, Callable, Coroutine, Iterable, Optional, Sequence, Union

import discord
from discord.ext import tasks

from pgbot.utils import utils
from pgbot.tasks import events


class TaskNamespace(SimpleNamespace):
    def __contains__(self, k: str):
        return k in self.__dict__


class _BotTask:
    def __init__(
        self,
        data: Optional[TaskNamespace] = None,
    ):
        self.manager = None
        self.data = TaskNamespace() if data is None else data
        self._is_waiting = False
        self.task_loop = None

    async def error(self, exc: Exception):
        print(
            f"An Exception occured while running task {self.__class__}:\n\n",
            utils.format_code_exception(exc),
        )

    def is_waiting(self):
        return self._is_waiting

    async def wait_for(self, coro):
        self._is_waiting = True
        result = await coro
        self._is_waiting = False
        return result

    def kill(self):
        self.task_loop.cancel()
        if self.manager is not None:
            self.manager.remove_task(self)


class IntervalTask(BotTask):
    """Base class for interval based tasks.
    Subclasses are expected to override the class variables and the run(self, *args **kwargs) method.
    before_run(self) and after_run(self) and error(self, exc) can optionally be implemented.
    """

    seconds = 0
    minutes = 0
    hours = 0
    count = None
    reconnect = True

    def __init__(
        self,
        seconds: Optional[int] = None,
        minutes: Optional[int] = None,
        hours: Optional[int] = None,
        count: Optional[int] = None,
        reconnect: Optional[bool] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.instance_seconds = self.seconds if seconds is None else seconds
        self.instance_minutes = self.minutes if minutes is None else minutes
        self.instance_hours = self.hours if hours is None else hours
        self.instance_count = self.count if count is None else count
        self.instance_reconnect = self.reconnect if reconnect is None else reconnect

        self.task_loop = tasks.loop(
            seconds=self.instance_seconds,
            minutes=self.instance_minutes,
            hours=self.instance_hours,
            count=self.instance_count,
            reconnect=self.instance_reconnect,
        )(self.run)

        if hasattr(self, "before_run"):
            self.task_loop.before_loop(self.before_run)
        if hasattr(self, "after_run"):
            self.task_loop.after_loop(self.after_run)
        if hasattr(self, "error"):
            self.task_loop.error(self.error)

    async def run(self):
        pass

class ClientEventTask(BotTask):
    event_classes = (events.ClientEvent,)
    reconnect = True

    def __init__(
        self,
        count: Optional[int] = None,
        manager: Optional[BotTaskManager] = None,
        reconnect: Optional[bool] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._event_queue = deque()
        self.instance_reconnect = self.reconnect if reconnect is None else reconnect

        self._is_waiting = False

        self.task_loop = tasks.loop(
            seconds=0, reconnect=self.instance_reconnect
        )(self._run)

        if hasattr(self, "before_run"):
            self.task_loop.before_loop(getattr(self, "before_run"))
        if hasattr(self, "after_run"):
            self.task_loop.after_loop(getattr(self, "after_run"))
        if hasattr(self, "error"):
            self.task_loop.error(getattr(self, "error"))

    def _add_event(self, event: events.ClientEvent):
        if not self._is_waiting:
            self._event_queue.append(event)
            if not self.task_loop.is_running():
                self.task_loop.start()

    def kill(self):
        self.task_loop.cancel()
        if self.manager is not None:
            self.manager.remove_task(self)

    async def _run(self):
        if not self._event_queue:
            self.task_loop.stop()
            return

        elif self._is_waiting:
            return

        return await self.run(self._event_queue.popleft())

    def is_waiting(self):
        return self._is_waiting

    async def wait_for(self, coro):
        self._is_waiting = True
        result = await coro
        self._is_waiting = False
        return result

    async def run(self, event: events.ClientEvent):
        pass


class BotTaskManager:
    def __init__(self, *tasks: Union[ClientEventTask, IntervalTask]):
        self._client_event_task_pool = set()
        self._interval_task_pool = set()
        self._seek_queue = deque()
        if tasks:
            self.add_tasks(*tasks)

    def add_tasks(
        self,
        *tasks: Union[ClientEventTask, IntervalTask],
        start=True,
        immediate_starting=True,
    ):
        for task in tasks:
            is_client_event_task = False
            if isinstance(task, ClientEventTask):
                is_client_event_task = True
                self._client_event_task_pool.add(task)
            elif isinstance(task, IntervalTask):
                self._interval_task_pool.add(task)
            else:
                raise TypeError(
                    f"expected an instance of class ClientEventTask or IntervalTask, not {task.__class__.__name__}"
                )

            task.manager = self
            if start and immediate_starting:
                if is_client_event_task and not task._event_queue:
                    continue
                if not task.task_loop.is_running():
                    task.task_loop.start()

        if start and not immediate_starting:
            for task in tasks:
                if isinstance(task, ClientEventTask) and not task._event_queue:
                    continue
                if not task.task_loop.is_running():
                    task.task_loop.start()

    def __iter__(self):
        return itertools.chain(tuple(self._client_event_task_pool), tuple(self._interval_task_pool))

    def add_task(self, task: Union[ClientEventTask, IntervalTask], start=True):
        is_client_event_task = False
        if isinstance(task, ClientEventTask):
            is_client_event_task = True
            self._client_event_task_pool.add(task)
        elif isinstance(task, IntervalTask):
            self._interval_task_pool.add(task)
        else:
            raise TypeError(
                f"expected an instance of class ClientEventTask or IntervalTask, not {task.__class__.__name__}"
            )

        task.manager = self
        if (
            start
            and not is_client_event_task
            or (is_client_event_task and task._event_queue)
        ):
            if not task.task_loop.is_running():
                task.task_loop.start()

    def has_task(self, task: Union[ClientEventTask, IntervalTask]):
        return task in self._client_event_task_pool or task in self._interval_task_pool

    def __contains__(self, task: Union[ClientEventTask, IntervalTask]):
        return self.has_task(task)

    def remove_task(self, task: Union[ClientEventTask, IntervalTask], cancel=True):
        if not isinstance(task, (ClientEventTask, IntervalTask)):
            raise TypeError(
                f"expected an instance of class ClientEventTask or IntervalTask, not {task.__class__.__name__}"
            )

        if task in self._client_event_task_pool:
            self._client_event_task_pool.remove(task)
        elif task in self._interval_task_pool:
            self._interval_task_pool.remove(task)

        if task.manager is self:
            task.manager = None
        if cancel:
            task.task_loop.cancel()

    def remove_tasks(self, *tasks: Union[ClientEventTask, IntervalTask], cancel=True):
        for task in tasks:
            self.remove_task(task, cancel=cancel)

    async def dispatch_client_event(self, event: events.ClientEvent):
        for i, client_event_task in enumerate(tuple(self._client_event_task_pool)):
            if isinstance(event, client_event_task.event_classes):
                client_event_task._add_event(event)
            if i % 50:
                await asyncio.sleep(0)


        for i, seek_list in enumerate(tuple(self._seek_queue)):
            if isinstance(event, seek_list[0]):
                seek_list[1] = event
            if i % 50:
                await asyncio.sleep(0)

    async def wait_for_client_event(
        self,
        event_classes: Union[events.ClientEvent, Iterable[events.ClientEvent]],
        check: Optional[Callable[[events.ClientEvent], bool]] = None,
    ):
        seek_list = [event_classes, None]
        self._seek_queue.append(seek_list)
        check_is_callable = callable(check)

        while seek_list[1] is None:
            await asyncio.sleep(0)
            if seek_list[1] is not None and (check_is_callable and check(seek_list[1])):
                break
            else:
                seek_list[1] = None

        self._seek_queue.remove(seek_list)
        return seek_list[1]

    async def kill_all(self):
        for i, task in enumerate(
            itertools.chain(tuple(self._client_event_task_pool), tuple(self._interval_task_pool))
        ):
            task.task_loop.cancel()
            self.remove_task(task)
            if i % 50:
                await asyncio.sleep(0)

    async def kill_all_interval_tasks(self):
        for i, task in enumerate(tuple(self._interval_task_pool)):
            task.task_loop.cancel()
            self.remove_task(task)
            if i % 50:
                await asyncio.sleep(0)

    async def kill_all_client_event_tasks(self):
        for i, task in enumerate(tuple(self._client_event_task_pool)):
            task.task_loop.cancel()
            self.remove_task(task)
            if i % 50:
                await asyncio.sleep(0)
