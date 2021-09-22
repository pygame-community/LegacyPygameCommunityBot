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
import enum
import functools
import itertools
import inspect
import pickle
from random import getrandbits
import time
from types import SimpleNamespace
from typing import Any, Callable, Coroutine, Iterable, Optional, Sequence, Union

import discord
from discord.ext import tasks

from pgbot.utils import utils
from pgbot.db import DiscordDB
from pgbot import common

from . import events, serializers

JOB_CLASS_MAP = {}


class JobError(RuntimeError):
    """Generic job object run-time error."""

    pass

class JobStateError(JobError):
    pass


class JobInitializationError(JobError):
    """Initialisation of a job object failed due to an error."""

    pass


class JobNamespace(SimpleNamespace):
    """A subclass of SimpleNamespace, which is used by bot job objects
    to store instance-specific data.
    """

    def __contains__(self, k: str):
        return k in self.__dict__

    def __iter__(self):
        return iter(self.__dict__.items())

    def copy(self):
        return JobNamespace(**self.__dict__)

    def to_dict(self):
        return JobNamespace(**self.__dict__)

    @staticmethod
    def from_dict(d):
        return JobNamespace(**d)

    __copy__ = copy


class JobWarning(RuntimeWarning):
    """Base class for warnings about dubious job object runtime behavior."""

    pass


# class JobProxy:

#     def __init__(self, job: BotJob, manager):
#         self._identifier = job._identifier
#         self._job_created_at = job.created_at
#         self.__mgr = manager
#         self._job_is_waiting = None
#         self._job_is_initialized = None
#         self._job_has_completed = None
#         self._job_was_killed = None
#         self._job_killed_itself = None
#         self._job_is_idle = None
#         self._job_class = job.__class__

#         self.wait_for_completion = (lambda *args, **kwargs: job.wait_for_completion(*args, **kwargs) )

#     @property
#     def job_class(self):
#         return self._job_class

#     @property
#     def id(self):
#         return self._identifier

#     @property
#     def created_at(self):
#         return self._job_created_at

#     @property
#     def registered_at(self):
#         return self._job_registered_at

#     def is_alive(self):
#         """Whether this job is currently alive (initialized and bound to a job manager).

#         Returns:
#             bool: True/False
#         """
#         job = self.__mgr._job_id_map[self._identifier]
#         return job._mgr is not None and job._is_initialized

#     def is_waiting(self):
#         """Whether this job is currently waiting
#         for a coroutine to complete, which was awaited using `.wait_for(awaitable)`.

#         Returns:
#             bool: True/False
#         """
#         job = self.__mgr._job_id_map[self._identifier]
#         return job._is_waiting

#     def is_alive(self):
#         """Whether this job is currently alive (initialized and bound to a job manager).

#         Returns:
#             bool: True/False
#         """
#         job = self.__mgr._job_id_map[self._identifier]
#         return job._mgr is not None and job._is_initialized

#     def is_running(self):
#         """Whether this job is currently running (alive and not idle).

#         Returns:
#             bool: True/False
#         """
#         self._job._mgr is not None and self._job._task_loop.is_running() and not self._job._idle

#     def is_idling(self):
#         """Whether this job is currently idling (alive and not running).

#         Returns:
#             bool: True/False
#         """
#         return self._job._mgr is not None and self._job._idle

#     def failed(self):
#         """Whether this jobs `.on_run()` method failed an execution attempt, usually due to an
#         exception.

#         Returns:
#             bool: True/False
#         """
#         return self._job._task_loop.failed()

#     def was_killed(self):
#         """Whether this job was killed using `.kill()`."""
#         return self._job_was_killed


#     def has_completed(self):
#         """Whether this job has ended, either due to being killed, or due to it ending itself.

#         Returns:
#             bool: True/False
#         """
#         return self._job_has_completed


#     def wait_for_completion(self, timeout: float = None):
#         """Wait for this job object to end.

#         Args:
#             timeout (float, optional): [description]. Defaults to None.

#         Raises:
#             asyncio.TimeoutError: The timeout was exceeded.

#         Raises:
#             asyncio.CancelledError: The job was killed.
#         """
#         if self._job._task_loop.loop is not None:
#             fut = self._job._task_loop.loop.create_future()
#         else:
#             fut = asyncio.get_event_loop().create_future()

#         self._job._completion_futures.append(fut)

#         return asyncio.wait_for(fut, timeout)


#     def get_output(self):
#         """Get the data that this job has marked as its output, if present.

#         Returns:
#             (JobNamespace, optional): The output namespace of this job, if present.
#         """
#         if "OUTPUT" in self._job.DATA:
#             try:
#                 return self._job.DATA.OUTPUT.copy()
#             except AttributeError:
#                 pass

#         return None


def call_with_method(cls, name, mode="after"):
    """A decorator to chain the execution of a method to another method from
    one of its superclasses. This works through the decorator making an
    implicit call to the method of the superclass specified before/after
    calling the actual method.

    Args:
        cls: (type):
            The class from which to select a method to chain to.
        name (str):
            The name of the method to chain to.
        mode (str, optional):
            The order in which the methods should be called.
            Defaults to "after".
    Raises:
        ValueError: mode is not a valid string ('before' or 'after')
    """

    def chain_deco(func):
        chained_func = getattr(cls, name)

        if isinstance(mode, str):
            if mode.lower() not in ("before", "after"):
                raise ValueError("argument 'mode' must be either 'before' or 'after'")
        else:
            raise TypeError("argument 'mode' must be of type 'str'")

        chained_func_coro = inspect.iscoroutinefunction(chained_func)
        func_coro = inspect.iscoroutinefunction(func)
        after_mode = mode.lower() == "after"

        if chained_func_coro and func_coro:
            async def chainer(*args, **kwargs):
                if after_mode:
                    await chained_func(*args, **kwargs)
                    return await func(*args, **kwargs)
                else:
                    output = await func(*args, **kwargs)
                    await chained_func(*args, **kwargs)
                    return output

        elif chained_func_coro or func_coro:
            if after_mode:
                async def chainer(*args, **kwargs):
                    chained_output = (
                        (await chained_func(*args, **kwargs))
                        if chained_func_coro
                        else chained_func(*args, **kwargs)
                    )
                    return (
                        (await func(*args, **kwargs))
                        if func_coro
                        else func(*args, **kwargs)
                    )
            else:
                async def chainer(*args, **kwargs):
                    output = (
                        (await func(*args, **kwargs))
                        if func_coro
                        else func(*args, **kwargs)
                    )
                    chained_output = (
                        (await chained_func(*args, **kwargs))
                        if chained_func_coro
                        else chained_func(*args, **kwargs)
                    )
                    return output

        else:
            if after_mode:
                def chainer(*args, **kwargs):
                    chained_func(*args, **kwargs)
                    return func(*args, **kwargs)
            else:
                def chainer(*args, **kwargs):
                    output = func(*args, **kwargs)
                    chained_func(*args, **kwargs)
                    return output

        return chainer

    return chain_deco


class BotJob:
    """The base class of all bot job objects. Do not instantiate this class by hand."""

    def __init_subclass__(cls):
        JOB_CLASS_MAP[cls.__name__] = cls

    def __init__(
        self,
        job_data: Optional[JobNamespace] = None,
    ):
        self._mgr = None
        self.__created_at = datetime.datetime.now().astimezone(datetime.timezone.utc)
        self._registered_at = None
        self._identifier = f"{id(self)}-{int(self._created_at.timestamp()*1000)}"
        self.DATA = (
            JobNamespace() if job_data is None else JobNamespace(**job_data.__dict__)
        )
        if "OUTPUT" not in self.DATA:
            self.DATA.OUTPUT = JobNamespace()

        self._reconnect = None
        self._task_loop = None
        self._completion_futures = []
        self._output_futures = []
        self._proxy = None

        self.__is_waiting = False
        self.__is_initialized = False
        self.__has_completed = False
        self.__was_killed = False
        self.__killed_itself = False
        self.__is_idle = False

    
    @_created_at.setter
    def _created_at_s(self, v):
        self.__created_at = v
        if self._proxy:
            self._proxy.__created_at = v

    @property
    def _is_waiting(self):
        return self.__is_waiting
    
    @_is_waiting.setter
    def _is_waiting_s(self, v):
        self.__is_waiting = v
        if self._proxy:
            self._proxy._job_is_waiting = v

    @property
    def _has_completed(self):
        return self.__has_completed
    
    @_has_completed.setter
    def _has_completed_s(self, v):
        self.__has_completed = v
        if self._proxy:
            self._proxy._job_has_completed = v

    @property
    def _was_killed(self):
        return self.__was_killed
    
    @_was_killed.setter
    def _was_killed_s(self, v):
        self.__was_killed = v
        if self._proxy:
            self._proxy._job_was_killed = v

    @property
    def _killed_itself(self):
        return self.__killed_itself
    
    @_killed_itself.setter
    def _killed_itself_s(self, v):
        self.__was_killed = v
        if self._proxy:
            self._proxy._job_killed_itself = v

    @property
    def _is_idle(self):
        return self.__is_idle
    
    @_is_idle.setter
    def _is_idle_s(self, v):
        self.__is_idle = v
        if self._proxy:
            self._proxy._job_is_idle = v

    @property
    def id(self):
        return self._identifier

    @property
    def manager(self):
        return self._mgr

    @property
    def created_at(self):
        return self._created_at

    @property
    def registered_at(self):
        return self._registered_at

    async def initialize(self, raise_exceptions: bool = True):
        """This method initializes a job object.
        registered.

        Args:
            raise_exceptions (bool, optional):
                Whether exceptions should be raised. Defaults to True.

        Returns:
            bool: Whether the initialization attempt was successful.
        """
        if not self._is_initialized:
            try:
                await self.on_init()
                self._is_initialized = True
            except Exception:
                self._is_initialized = False
                if raise_exceptions:
                    raise
        else:
            if raise_exceptions:
                raise JobInitializationError(
                    "this bot job object is already initialized"
                )
            else:
                return False

        return self._is_initialized

    async def INITIALIZE(self, raise_exceptions: bool = True):
        """
        DO NOT USE THIS METHOD OUTSIDE OF YOUR CLASS DEFINITION.

        This method initializes a job object.

        Args:
            raise_exceptions (bool, optional):
                Whether exceptions should be raised. Defaults to True.

        Returns:
            bool: Whether the initialization attempt was succesful.
        """
        try:
            await self.on_init()
            return True
        except Exception:
            if raise_exceptions:
                raise
            else:
                return False

    async def as_initialized(self):
        """Like .initialize(), but it returns this job object after initialization if no errors occur."""
        await self.initialize()
        return self

    async def _on_pre_run(self):
        self._idle = False
        try:
            output = await self.on_pre_run()
        except Exception as exc:
            await self.on_pre_error(exc)
        return output

    async def on_init(self):
        """This method allows subclasses to initialize their job object instances
        by processing data passed to their `.data` attribute.
        """
        pass

    async def on_pre_run(self):
        """A generic hook method that subclasses can use to initialize their job objects
        when their internal task loops start.
        """
        pass

    async def _on_post_run(self):
        if not self._task_loop.is_being_cancelled():
            try:
                output = await self.on_post_run()
            except Exception as exc:
                await self.on_post_error(exc)
            self._idle = True
            return output
        else:
            return await self.on_force_stop()

    async def on_post_run(self):
        """A method subclasses can use to uninitialize their job objects
        when their internal task loops end execution.
        """
        pass

    async def on_force_stop(self):
        """A method subclasses can use to uninitialize their job objects
        when their internal task loops were force stopped (cancelled).
        """
        pass

    async def on_error(self, exc: Exception):
        print(
            f"An Exception occured while running job {self.__class__}:\n\n",
            utils.format_code_exception(exc),
        )

    async def on_pre_error(self, exc: Exception):
        print(
            f"An Exception occured before job {self.__class__} could start running its loop:\n\n",
            utils.format_code_exception(exc),
        )

    async def on_post_error(self, exc: Exception):
        print(
            f"An Exception occured after running job {self.__class__} finished running its loop:\n\n",
            utils.format_code_exception(exc),
        )

    async def wait_for(self, awaitable):
        """Wait for a given coroutine to complete.
        While the coroutine is active, this job object
        will be marked as waiting.

        Args:
            awaitable: An awaitable object

        Returns:
            Any: The result of the given coroutine.

        Raises:
            TypeError: The given object was not a coroutine.
        """
        if inspect.isawaitable(awaitable):
            self._is_waiting = True
            result = await awaitable
            self._is_waiting = False
            return result

        raise TypeError("argument 'coro' must be a coroutine")

    def restart(self):
        """Restarts the internal task loop of this job object. This is only
        possible if it is currently bound to a job manager.

        Raises:
            RuntimeError: The job object was never added to a `BotJobManager` instance
        """
        if self._mgr is not None:
            self._task_loop.restart()

        raise RuntimeError("Cannot restart job without being in a BotJobManager")

    def kill(self):
        """Stops this job's current execution unconditionally like `.cancel_run()`, before closing it and removing it from its `BotJobManager`.
        In order to check if a job was closed by killing it, on can call `.was_killed()`."""
        self._task_loop.cancel()
        self._idle = False
        self._has_completed = True
        self._was_killed = True

        for fut in self._completion_futures:
            if not fut.cancelled():
                fut.cancel(msg=f"Job object '{self}' was killed.")

        for fut in self._output_futures:
            if not fut.cancelled():
                fut.cancel(
                    msg=f"Job object '{self}' was killed. job output might be corrupted."
                )

        self._completion_futures.clear()
        self._output_futures = []

        if self._mgr is not None:
            self._mgr._remove_job(self)

    def cancel_run(self):
        """Stops this job's current loop iteration unconditionally and makes it idle. This will not trigger `.on_post_run()`, but will trigger `.on_force_stop()`."""
        self._task_loop.cancel()
        self._idle = True

    def stop_run(self):
        """Stops this job object's current loop iteration and makes it idle. Use `.cancel_run()` if it is
        undesirable to attempt reconnecting when that is enabled, and when
        `.on_post_run()` should not be called."""
        self._task_loop.stop()
        self._idle = True

    def COMLPLETE(self):
        """
        DO NOT CALL THIS METHOD FROM OUTSIDE YOUR JOB SUBCLASS.

        Stops this job object gracefully like `.stop_run()`, before removing it from its `BotJobManager`.
        Any job that was closed has officially finished execution, and all jobs waiting for this job
        to close will be notified. If a job had reconnecting enabled, then it will be silently cancelled to ensure
        that it suspends all execution."""

        if self._reconnect:
            self._task_loop.cancel()
        else:
            self._task_loop.stop()

        for fut in self._completion_futures:
            if not fut.cancelled():
                fut.set_result(None)

        for fut in self._output_futures:
            if not fut.cancelled():
                fut.set_result(self.get_output())

        self._completion_futures.clear()
        self._output_futures.clear()

        self._idle = False
        self._has_ended = True
        if self._mgr is not None:
            self._mgr._remove_job(self)

    def is_waiting(self):
        """Whether this job is currently waiting
        for a coroutine to complete, which was awaited using `.wait_for(awaitable)`.

        Returns:
            bool: True/False
        """
        return self._is_waiting

    def is_alive(self):
        """Whether this job is currently alive (initialized and bound to a job manager).

        Returns:
            bool: True/False
        """
        return self._mgr is not None and self._is_initialized

    def is_running(self):
        """Whether this job is currently running (alive and not idle).

        Returns:
            bool: True/False
        """
        return self._mgr is not None and self._task_loop.is_running() and not self._idle

    def is_idling(self):
        """Whether this job is currently idling (alive and not running).

        Returns:
            bool: True/False
        """
        return self._mgr is not None and self._idle

    def failed(self):
        """Whether this jobs `.on_run()` method failed an execution attempt, usually due to an
        exception.

        Returns:
            bool: True/False
        """
        return self._task_loop.failed()

    def was_killed(self):
        """Whether this job was killed using `.kill()`."""
        return self._was_killed

    def killed_itself(self):
        return self._killed_itself

    def has_ended(self):
        """Whether this job has ended, either due to being killed, or due to it ending itself.

        Returns:
            bool: True/False
        """
        return self._has_ended

    def completion_promise(self, timeout: float = None):
        """Wait for this job object to end.

        Args:
            timeout (float, optional): [description]. Defaults to None.

        Raises:
            asyncio.TimeoutError: The timeout was exceeded.

        Raises:
            asyncio.CancelledError: The job was killed.
        """
        if self._task_loop.loop is not None:
            fut = self._task_loop.loop.create_future()
        else:
            fut = asyncio.get_event_loop().create_future()

        self._completion_futures.append(fut)

        return asyncio.wait_for(fut, timeout)

    def wait_for_output(self, timeout):
        """Wait for this job object to end, and return output data, if present.

        Args:
            timeout (float, optional): [description]. Defaults to None.

        Raises:
            asyncio.TimeoutError: The timeout was exceeded.

        Raises:
            asyncio.CancelledError: The job was killed.
        """

        if self._task_loop.loop is not None:
            fut = self._task_loop.loop.create_future()
        else:
            fut = asyncio.get_event_loop().create_future()

        self._output_futures.append(fut)

        return asyncio.wait_for(fut, timeout)

    def get_output(self):
        """Get the data that this job has marked as its output, if present.

        Returns:
            (JobNamespace, optional): The output namespace of this job, if present.
        """
        if "OUTPUT" in self.DATA:
            try:
                return self.DATA.OUTPUT.copy()
            except AttributeError:
                pass

        return None

    def __str__(self):
        return f"<{self.__class__.__name__}: id:{self._identifier}>"


class IntervalJob(BotJob):
    """Base class for interval based jobs.
    Subclasses are expected to overload the `run()` method.
    `on_pre_run()` and `on_post_run()` and `on_error(exc)` can optionally be overloaded.

    One can override the class variables `default_seconds`, `default_minutes`,
    `default_hours`, `default_count` and `default_reconnect` in subclasses. They are derived
    from the keyword arguments of the `discord.ext.tasks.loop` decorator.
    These will act as interval defaults for each bot job object
    created from them.
    Each interval job object can recieve a `data=` keyword argument during initiation, which takes
    a `JobNamespace()` object as input, which may be used to customize job behavior at runtime, by
    overriding the default namespace object in `.data`, which is the namespace to store bot information.

    Attributes:
        seconds (property):
        minutes (property):
        hours (property):
            The number of seconds/minutes/hours between every iteration. Changes the job interval for the next iteration when modified.
        job_data: A namespace object that is used by job objects to hold data.
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
        """Create a new IntervalJob instance.

        Args:
            seconds (Optional[int]):
            minutes (Optional[int]):
            hours (Optional[int]):
            count (Optional[int]):
            reconnect (Optional[bool]):
                Overrides for the default class variables for an IntervalJob instance.
            data (Optional[JobNamespace]):
                A namespace object to override the `.data` object. Defaults to None.
        """

        super().__init__(**kwargs)
        self._seconds = self.default_seconds if seconds is None else seconds
        self._minutes = self.default_minutes if minutes is None else minutes
        self._hours = self.default_hours if hours is None else hours
        self._count = self.default_count if count is None else count
        self._reconnect = self.default_reconnect if reconnect is None else reconnect

        self._task_loop = tasks.Loop(
            self.on_run,
            seconds=self._seconds,
            minutes=self._minutes,
            hours=self._hours,
            count=self._count,
            reconnect=self._reconnect,
            loop=None,
        )

        self._task_loop.before_loop(self._on_pre_run)
        self._task_loop.after_loop(self._on_post_run)
        self._task_loop.error(self.on_error)

    def next_iteration(self):
        """When the next iteration of `.on_run()` will occur.
        If not known, this method will return `None`.

        Returns:
            Optional[datetime.datetime]:
                The time at which the next iteration will occur.
        """
        return self._task_loop.next_iteration()

    def get_interval(self):
        """Returns a tuple of the seconds, minutes and hours at which this job
        object is executing its `.on_run()` method.

        Returns:
            [type]: `(seconds, minutes, hours)`
        """
        return self._seconds, self._minutes, self._hours

    def change_interval(self, seconds: int = 0, minutes: int = 0, hours: int = 0):
        """Change the interval at which this job will run its `on_run()` method.
        This will only be applied on the next iteration of `.on_run()`

        Args:
            seconds (int, optional): Defaults to 0.
            minutes (int, optional): Defaults to 0.
            hours (int, optional): Defaults to 0.

        Returns:
            [type]: [description]
        """
        self._task_loop.change_interval(
            seconds=seconds,
            minutes=minutes,
            hours=hours,
        )

        self._seconds = seconds
        self._minutes = minutes
        self._hours = hours

    async def on_run(self):
        """The code to run at the set interval.
        This method must be overloaded in subclasses.

        Raises:
            NotImplementedError: This method must be overloaded in subclasses.
        """
        raise NotImplementedError()


class ClientEventJob(BotJob):
    """A job class for jobs that run in reaction to specific client events
    (Discord API events) passed to them by their `BotJobManager` object.
    Subclasses are expected to overload the `run(self, event)` method.
    `on_pre_run(self)` and `on_post_run(self)` and `on_error(self, exc)` can
    optionally be overloaded.
    One can also override the class variables `default_count` and `default_reconnect`
    in subclasses. They are derived from the keyword arguments of the
    `discord.ext.tasks.loop` decorator. Unlike `IntervalJob` class instances,
    the instances of this class depend on their `BotJobManager` to trigger
    the execution of their `.run()` method, and will stop running if
    all ClientEvent objects passed to them have been processed.

    Attributes:
        EVENT_TYPES:
            A tuple denoting the set of `ClientEvent` classes whose instances
            should be recieved after their corresponding event is registered
            by the `BotJobManager` of an instance of this class.

        data: A namespace object that is used by job objects to hold data.
    """

    EVENT_TYPES: Union[tuple, list] = (events.ClientEvent,)
    default_reconnect = True
    default_count = None

    def __init_subclass__(cls):
        if not isinstance(cls.EVENT_TYPES, (list, tuple)):
            raise TypeError(
                "the 'EVENT_TYPES' class attribute must be of type 'list'/'tuple' and"
                " must contain one or more subclasses of `ClientEvent`"
            )
        elif not cls.EVENT_TYPES or not all(
            issubclass(et, events.ClientEvent) for et in cls.EVENT_TYPES
        ):
            raise ValueError(
                "the 'EVENT_TYPES' class attribute"
                " must contain one or more subclasses of `ClientEvent`"
            )

    def __init__(
        self,
        count: Optional[int] = None,
        reconnect: Optional[bool] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._event_queue = deque()
        self._count = self.default_count if count is None else count
        self._current_loop_count = 0
        self._reconnect = self.default_reconnect if reconnect is None else reconnect
        self._allow_dispatch = True
        self._task_loop = tasks.Loop(
            self._on_run,
            seconds=0,
            minutes=0,
            hours=0,
            count=None,
            reconnect=self._reconnect,
            loop=None,
        )
        self._task_loop.before_loop(self._on_pre_run)
        self._task_loop.after_loop(self._on_post_run)
        self._task_loop.error(self.on_error)

    def _add_event(self, event: events.ClientEvent):
        if self._allow_dispatch:
            self._event_queue.append(event)
            if not self._task_loop.is_running():
                self._task_loop.start()

    def check_event(self, event: events.ClientEvent):
        """A method for subclasses can override to perform validations on a ClientEvent
        object that is passed to them. Must return a boolean value indicating the
        validaiton result. If not overloaded, this method will always return `True`.

        Args:
            event (events.ClientEvent): The ClientEvent object to run checks upon.
        """
        return True

    async def _on_run(self):
        if not self._event_queue or self._current_loop_count == self._count:
            self._task_loop.stop()
            return

        self._current_loop_count += 1
        output = await self.on_run(self._event_queue.popleft())

        if not self._event_queue or self._current_loop_count == self._count:
            self._task_loop.stop()
        return output

    async def on_run(self, event: events.ClientEvent):
        """The code to run whenever a client event is recieved.
        This method must be overloaded in subclasses.

        Raises:
            NotImplementedError: This method must be overloaded in subclasses.
        """
        raise NotImplementedError()

    async def wait_for_event(
        self,
        *event_types: type,
        check: Optional[Callable[[events.ClientEvent], bool]] = None,
        block_dispatch: bool = True,
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

        if not self.is_alive():
            raise JobError("cannot pass events to job objects that are not alive.")

        if block_dispatch:
            self._allow_dispatch = False
        event = await self.manager.wait_for_client_event(*event_types, check=check)
        if block_dispatch:
            self._allow_dispatch = True
        self._allow_dispatch = True if block_dispatch else False
        return event

    def restart(self):
        old_cur_loop = self._current_loop_count
        self._current_loop_count = 0
        try:
            super().restart()
        except RuntimeError:
            self._current_loop_count = old_cur_loop
            raise

    def queue_is_empty(self):
        return not self._event_queue


class OneTimeJob(IntervalJob):
    """A subclass of `IntervalJob` whose subclasses's
    job objects will only run once, before going into an idle state.
    automatically.
    """

    def __init__(self, job_data: Optional[JobNamespace] = None, **kwargs):
        super().__init__(count=1, job_data=job_data)


class DelayJob(OneTimeJob):
    """A subclass of `OneTimeJob` that
    adds a given set of job objects to its `BotJobManager`
    only after a given period of time in seconds.

    Attributes:
        delay (float):
            The delay for the input jobs in seconds.
    """

    def __init__(
        self, delay: float, *jobs: Union[ClientEventJob, IntervalJob], **kwargs
    ):
        """Create a new DelayJob instance.

        Args:
            delay (float):
                The delay for the input jobs in seconds.
            *jobs Union[ClientEventJob, IntervalJob]:
                The jobs to be delayed.
        """
        super().__init__(**kwargs)
        self.DATA.delay = delay
        self.DATA.jobs = jobs

    async def on_pre_run(self):
        await asyncio.sleep(self.DATA.delay)

    async def on_run(self):
        for job in self.DATA.jobs:
            await job.initialize()
            self.manager.add_job(job)

    async def on_post_run(self):
        self.COMLPLETE()
