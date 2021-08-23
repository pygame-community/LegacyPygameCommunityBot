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

from . import events

class TaskNamespace(SimpleNamespace):
    """A subclass of SimpleNamespace, which is used by bot task objects
    to store instance-specific data.
    """

    def __contains__(self, k: str):
        return k in self.__dict__


class _BotTask:
    """The base class of all bot task objects."""

    def __init__(
        self,
        task_data: Optional[TaskNamespace] = None,
    ):
        self.manager = None
        self.created = datetime.datetime.now().astimezone(datetime.timezone.utc)
        self.data = (
            TaskNamespace()
            if task_data is None
            else TaskNamespace(**task_data.__dict__)
        )
        self._is_waiting = False
        self._task_loop = None

    def setup(self, **kwargs):
        """This method allows subclasses to define specific
        keyword arguments that get added to their `.data` namespace
        as variables.

        Returns:
            This task object.
        """
        self.data.__dict__.update(**kwargs)
        return self

    async def before_run(self):
        """A method subclasses can use to initialize their task objects
        when their internal task loops start.
        """
        pass

    async def after_run(self):
        """A method subclasses can use to initialize their task objects
        when their internal task loops end.
        """

    async def error(self, exc: Exception):
        print(
            f"An Exception occured while running task {self.__class__}:\n\n",
            utils.format_code_exception(exc),
        )

    def is_waiting(self):
        """Whether this task is currently waiting
        for a coroutine to complete, which was triggered using `.wait_for()`.

        Returns:
            bool: True/False
        """
        return self._is_waiting

    async def wait_for(self, coro):
        """Wait for a given coroutine to complete.
        While the coroutine is active, this task object
        will be marked as waiting.

        Args:
            coro (coroutine): An awaitable object

        Returns:
            Any: The result of the given coroutine.
        """
        self._is_waiting = True
        result = await coro
        self._is_waiting = False
        return result

    def kill(self):
        """Stops this task object and removes it from its `BotTaskManager`."""
        self._task_loop.cancel()
        if self.manager is not None:
            self.manager.remove_task(self)

    def is_running(self):
        """Whether this task is currently running.

        Returns:
            bool: True/False
        """
        return self._task_loop.is_running()


class IntervalTask(_BotTask):
    """Base class for interval based tasks.
    Subclasses are expected to override the `run()` method.
    `before_run()` and `after_run()` and `error(exc)` can optionally be implemented.

    One can override the class variables `default_seconds`, `default_minutes`,
    `default_hours`, `default_count` and `default_reconnect` in subclasses. They are derived
    from the keyword arguments of the `discord.ext.tasks.loop` decorator.
    These will act as interval defaults for each bot task object
    created from them.
    Each interval task object can recieve a `data=` keyword argument during initiation, which takes
    a `TaskNamespace()` object as input, which may be used to customize task behavior at runtime, by
    overriding the default namespace object in `.data`, which is the namespace to store bot information.


    Attributes:
        seconds (property):
        minutes (property):
        hours (property):
            The number of seconds/minutes/hours between every iteration. Changes the task interval for the next iteration when modified.
        data: A namespace object that is used by task objects to hold data.
    """

    default_seconds = 0
    default_minutes = 0
    default_hours = 0
    default_count = None
    default_reconnect = True

    def __init__(
        self,
        seconds: Optional[int] = None,
        minutes: Optional[int] = None,
        hours: Optional[int] = None,
        count: Optional[int] = None,
        reconnect: Optional[bool] = None,
        **kwargs,
    ):
        """Create a new IntervalTask instance.

        Args:
            seconds (Optional[int]):
            minutes (Optional[int]):
            hours (Optional[int]):
            count (Optional[int]):
            reconnect (Optional[bool]):
                Overrides for the default class variables for an IntervalTask instance.
            data (Optional[TaskNamespace]):
                A namespace object to override the `.data` object. Defaults to None.
        """

        super().__init__(**kwargs)
        self._seconds = self.default_seconds if seconds is None else seconds
        self._minutes = self.default_minutes if minutes is None else minutes
        self._hours = self.default_hours if hours is None else hours
        self._count = self.default_count if count is None else count
        self._reconnect = self.default_reconnect if reconnect is None else reconnect

        self._task_loop = tasks.Loop(
            self.run,
            seconds=self._seconds,
            minutes=self._minutes,
            hours=self._hours,
            count=self._count,
            reconnect=self._reconnect,
            loop=None,
        )

        self._task_loop.before_loop(self.before_run)
        self._task_loop.after_loop(self.after_run)
        self._task_loop.error(self.error)

    def next_iteration(self):
        """When the next iteration of this task will occur.
        If not known, this method will return `None`.

        Returns:
            Optional[datetime.datetime]:
                The time at which the next iteration will occur.
        """
        return self._task_loop.next_iteration()

    def _get_interval_seconds(self):
        return self._seconds

    def _set_interval_seconds(self, t: int):
        self._seconds = t
        self._task_loop.change_interval(
            seconds=self._seconds, minutes=self._minutes, hours=self._hours
        )

    def _get_interval_minutes(self):
        return self._minutes

    def _set_interval_minutes(self, t: int):
        self._minutes = t
        self._task_loop.change_interval(
            seconds=self._seconds, minutes=self._minutes, hours=self._hours
        )

    def _get_interval_hours(self):
        return self._hours

    def _set_interval_hours(self, t: int):
        self._hours = t
        self._task_loop.change_interval(
            seconds=self._seconds, minutes=self._minutes, hours=self._hours
        )

    seconds = property(_get_interval_seconds, _set_interval_seconds)
    minutes = property(_get_interval_minutes, _set_interval_minutes)
    hours = property(_get_interval_hours, _set_interval_hours)

    async def run(self):
        """The code to run at the set interval.
        This method must be overloaded in subclasses.

        Raises:
            NotImplementedError: This method must be overloaded in subclasses.
        """
        raise NotImplementedError()


class ClientEventTask(_BotTask):
    """A task class for tasks that run in reaction to specific client events
    (Discord API events) passed to them by their BotTaskManager object.
    Subclasses are expected to override the `run(self, event)` method.
    `before_run(self)` and `after_run(self)` and `error(self, exc)` can
    optionally be implemented.
    One can also override the class variables `default_count` and `default_reconnect`
    in subclasses. They are derived from the keyword arguments of the
    `discord.ext.tasks.loop` decorator. Unlike `IntervalTask` class instances,
    the instances of this class depend on their `BotTaskManager` to trigger
    the execution of their `.run()` method, and will stop running if
    all ClientEvent objects passed to them have been processed.

    Attributes:
        EVENT_TYPES:
            A tuple denoting the set of `ClientEvent` classes whose instances
            should be recieved after their corresponding event is registered
            by the `BotTaskManager` of an instance of this class.

        data: A namespace object that is used by task objects to hold data.
    """

    EVENT_TYPES: tuple = (events.ClientEvent,)
    default_reconnect = True
    default_count = None

    def __init__(
        self,
        count: Optional[int] = None,
        reconnect: Optional[bool] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._event_queue = deque()
        self._count = self.default_count if count is None else count
        self._current_loop = 0
        self._reconnect = self.default_reconnect if reconnect is None else reconnect
        self._is_waiting = False
        self._task_loop = tasks.loop(reconnect=self._reconnect)(self._run)

        self._task_loop.before_loop(self.before_run)
        self._task_loop.after_loop(self.after_run)
        self._task_loop.error(self.error)

    def _add_event(self, event: events.ClientEvent):
        if not self._is_waiting:
            self._event_queue.append(event)
            if not self._task_loop.is_running():
                self._task_loop.start()

    def check(self, event: events.ClientEvent):
        """A method for subclasses can override to perform validations on a ClientEvent
        object that is passed to them. Must return a boolean value indicating the
        validaiton result.

        Args:
            event (events.ClientEvent): The ClientEvent object to run checks upon.
        """
        return True

    async def _run(self):
        if not self._event_queue or self._current_loop == self._count:
            self._task_loop.stop()
            return

        elif self._is_waiting:
            return

        self._current_loop += 1
        return await self.run(self._event_queue.popleft())

    async def run(self, event: events.ClientEvent):
        """The code to run whenever a client event is registered.
        This method must be overloaded in subclasses.

        Raises:
            NotImplementedError: This method must be overloaded in subclasses.
        """
        raise NotImplementedError()

    async def wait_for(self, coro):
        """Wait for a given coroutine to complete.
        While the coroutine is active, this task object
        will be marked as waiting, and will not recieve
        any client events.

        Args:
            coro (coroutine): An awaitable object

        Returns:
            Any: The result of the given coroutine.
        """
        return await super().wait_for(coro)


class SingletonTask(IntervalTask):
    """A subclass of `IntervalTask` whose subclasses's
    task objects will only run once, before stopping
    automatically.
    """

    def __init__(self, task_data: Optional[TaskNamespace] = None, **kwargs):
        super().__init__(count=1, task_data=task_data)


class DelayTask(SingletonTask):
    """A subclass of `IntervalTask` that
    adds a given set of task objects to its `BotTaskManager`
    only after a given period of time in seconds.

    Attributes:
        delay (float):
            The delay for the input tasks in seconds.
    """

    def __init__(
        self, delay: float, *tasks: Union[ClientEventTask, IntervalTask], **kwargs
    ):
        """Create a new DelayTask instance.

        Args:
            delay (float):
                The delay for the input tasks in seconds.
            *tasks Union[ClientEventTask, IntervalTask]:
                The tasks to be delayed.
        """
        super().__init__(**kwargs)
        self.data.delay = delay
        self.data.tasks = tasks

    async def before_run(self):
        await asyncio.sleep(self.data.delay)

    async def run(self):
        self.manager.add_tasks(*self.data.tasks)

    async def after_run(self):
        self.kill()


class BotTaskManager:
    """The task manager for all interval tasks and client event tasks.
    It acts as a container for interval and client event task objects, whilst also dispatching
    client events to client event task objects. Each of the tasks that a bot task manager
    contains can use it to register new task objects that they instantiate at runtime.
    """

    def __init__(self, *tasks: Union[ClientEventTask, IntervalTask]):
        """Create a new bot task manager instance.

        Args:
            *tasks: Union[ClientEventTask, IntervalTask]:
                The task objects to add during initiation.
        """
        self._client_event_task_pool = {}
        self._interval_task_pool = set()
        self._event_waiting_queues = {}
        if tasks:
            self.add_tasks(*tasks)

    def start_task_scheduling(self):
        pass

    def add_tasks(
        self,
        *tasks: Union[ClientEventTask, IntervalTask],
        start=True,
    ):
        """Add the given task objects to this bot task manager.

        Args:
            *tasks: Union[ClientEventTask, IntervalTask]:
                The tasks to be added.
            start (bool, optional):
                Whether the given interval task objects should start immediately after being added.
                Defaults to True.
        Raises:
            TypeError: An invalid object was given as a task.
        """
        for task in tasks:
            self.add_task(task, start=start)

    def __iter__(self):
        return itertools.chain(
            tuple(self._client_event_task_pool), tuple(self._interval_task_pool)
        )

    def add_task(self, task: Union[ClientEventTask, IntervalTask], start=True):
        """Add the given task object to this bot task manager.

        Args:
            task: Union[ClientEventTask, IntervalTask]:
                The task to add.
            start (bool, optional):
                Whether a given interval task object should start immediately after being added.
                Defaults to True.
        Raises:
            TypeError: An invalid object was given as a task.
        """
        is_client_event_task = False
        if isinstance(task, ClientEventTask):
            is_client_event_task = True
            for ce_type in task.EVENT_TYPES:
                if ce_type.__name__ not in self._client_event_task_pool:
                    self._client_event_task_pool[ce_type.__name__] = set()
                self._client_event_task_pool[ce_type.__name__].add(task)

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
            if not task._task_loop.is_running():
                task._task_loop.start()

    def has_task(self, task: Union[ClientEventTask, IntervalTask]):
        """Whether a task is contained in this bot task manager.

        Args:
            task (Union[ClientEventTask, IntervalTask]): The task object to look for.

        Returns:
            bool: True/False
        """
        if task in self._interval_task_pool:
            return True
        elif isinstance(task, events.ClientEvent):
            return any(
                task in ce_set
                for ce_set in (
                    self._client_event_task_pool[ce_type.__name__]
                    for ce_type in task.EVENT_TYPES
                    if ce_type.__name__ in self._client_event_task_pool
                )
            )
        return False

    def __contains__(self, task: Union[ClientEventTask, IntervalTask]):
        return self.has_task(task)

    def remove_task(self, task: Union[ClientEventTask, IntervalTask], cancel=True):
        """Remove the given task object from this bot task manager.

        Args:
            *tasks: Union[ClientEventTask, IntervalTask]:
                The task to be removed, if present.
            start (bool, optional):
                Whether the given interval task object should be cancelled immediately after being removed.
                Defaults to True.
        Raises:
            TypeError: An invalid object was given as a task.
        """
        if not isinstance(task, (ClientEventTask, IntervalTask)):
            raise TypeError(
                f"expected an instance of class ClientEventTask or IntervalTask, not {task.__class__.__name__}"
            )

        if isinstance(task, IntervalTask) and task in self._interval_task_pool:
            self._interval_task_pool.remove(task)

        elif isinstance(task, ClientEventTask):
            for ce_type in task.EVENT_TYPES:
                if (
                    ce_type.__name__ in self._client_event_task_pool
                    and task in self._client_event_task_pool[ce_type.__name__]
                ):
                    self._client_event_task_pool[ce_type.__name__].remove(task)
                if not self._client_event_task_pool[ce_type.__name__]:
                    del self._client_event_task_pool[ce_type.__name__]

        if task.manager is self:
            task.manager = None
        if cancel:
            task._task_loop.cancel()

    def remove_tasks(self, *tasks: Union[ClientEventTask, IntervalTask], cancel=True):
        """Remove the given task objects from this bot task manager.

        Args:
            *tasks: Union[ClientEventTask, IntervalTask]:
                The tasks to be removed, if present.
            start (bool, optional):
                Whether the given interval task objects should be cancelled immediately after being removed.
                Defaults to True.
        Raises:
            TypeError: An invalid object was given as a task.
        """
        for task in tasks:
            self.remove_task(task, cancel=cancel)

    async def dispatch_client_event(self, event: events.ClientEvent):
        """Dispatch a `ClientEvent` subclass to all client event task objects
        in this bot task manager.

        Args:
            event (events.ClientEvent): The subclass to be dispatched.
        """
        event_class_name = type(event).__name__

        if event_class_name in self._client_event_task_pool:
            for i, client_event_task in enumerate(
                tuple(self._client_event_task_pool[event_class_name])
            ):
                if isinstance(event, client_event_task.EVENT_TYPES) and client_event_task.check(event):
                    client_event_task._add_event(event.copy())
                if i % 50:
                    await asyncio.sleep(0)

        if event_class_name in self._event_waiting_queues:
            for i, wait_list in enumerate(
                tuple(self._event_waiting_queues[event_class_name])
            ):
                if isinstance(event, wait_list[0]):
                    wait_list[1] = event.copy()
                if i % 50:
                    await asyncio.sleep(0)

    async def wait_for_client_event(
        self,
        *event_types: events.ClientEvent,
        check: Optional[Callable[[events.ClientEvent], bool]] = None,
    ):
        """Wait for specific type of client event to be dispatched, and return that.

        Args:
            *event_types (events.ClientEvent):
                The client event type/types to wait for. If any of its/their
                instances is dispatched, that instance will be returned.
            check (Optional[Callable[[events.ClientEvent], bool]], optional):
                A callable obejct used to validate if a valid client event that was recieved meets specific conditions.
                Defaults to None.

        Returns:
            ClientEvent: A valid client event object
        """

        wait_list = [event_types, None]

        for event_type in event_types:
            if not issubclass(event_type, events.ClientEvent):
                raise TypeError(
                    "Argument 'event_types' must contain only subclasses of 'ClientEvent'"
                )

        for event_type in event_types:
            if event_type.__name__ not in self._event_waiting_queues:
                self._event_waiting_queues[event_type.__name__] = deque()

            self._event_waiting_queues[event_type.__name__].append(wait_list)

        check_is_callable = callable(check)

        while wait_list[1] is None:
            await asyncio.sleep(
                0
            )  # sleep until a ClientEvent object is passed to wait_list[1]
            if wait_list[1] is not None:
                if check_is_callable and check(wait_list[1]):
                    break
                else:
                    wait_list[1] = None

        for event_type in event_types:
            d = self._event_waiting_queues[event_type.__name__]
            d.remove(wait_list)
            if not d:
                del self._event_waiting_queues[event_type.__name__]

        return wait_list[1]

    async def kill_all(self):
        """Kill all task objects that are in this bot task manager."""
        for i, task in enumerate(
            itertools.chain(
                tuple(
                    t
                    for t in (
                        ce_set for ce_set in self._client_event_task_pool.values()
                    )
                ),
                tuple(self._interval_task_pool),
            )
        ):
            task._task_loop.cancel()
            self.remove_task(task)
            if i % 50:
                await asyncio.sleep(0)

    async def kill_all_interval_tasks(self):
        """Kill all interval task objects that are in this bot task manager."""
        for i, task in enumerate(tuple(self._interval_task_pool)):
            task._task_loop.cancel()
            self.remove_task(task)
            if i % 50:
                await asyncio.sleep(0)

    async def kill_all_client_event_tasks(self):
        """Kill all client event task objects that are in this bot task manager."""
        for i, task in enumerate(
            tuple(
                t for t in (ce_set for ce_set in self._client_event_task_pool.values())
            )
        ):
            task._task_loop.cancel()
            self.remove_task(task)
            if i % 50:
                await asyncio.sleep(0)
