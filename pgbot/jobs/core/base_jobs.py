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
from contextlib import contextmanager
import datetime
import enum
import functools
import itertools
import inspect
import pickle
from random import getrandbits
import re
import sys
import time
import traceback
from types import SimpleNamespace
from typing import Any, Callable, Coroutine, Iterable, Optional, Sequence, Union

import discord
from discord.ext import tasks

from pgbot.utils import utils
from pgbot.db import DiscordDB
from pgbot import common

from . import events

JOB_CLASS_MAP = {}
"""A dictionary of all BotJob subclasses that were created."""


class JobError(Exception):
    """Generic job object run-time error."""

    pass


class JobPermissionError(JobError):
    """Job object permisssion error."""

    pass


class JobStateError(JobError):
    pass


class JobInitializationError(JobError):
    """Initialisation of a job object failed."""

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
        return dict(self.__dict__)

    @staticmethod
    def from_dict(d):
        return JobNamespace(**d)

    __copy__ = copy


class JobWarning(RuntimeWarning):
    """Base class for warnings about dubious job object runtime behavior."""


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
            The order in which the methods should be called, which can be
            "before" or "after".
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


class BotJobProxy:

    __slots__ = (
        "_j",
        "__job_class",
        "__identifier",
        "__created_at",
        "__registered_at",
    )

    def __init__(self, job):
        self._j = job
        self.__job_class = job.__class__
        self.__identifier = job._identifier
        self.__created_at = job._created_at
        self.__registered_at = job._registered_at

    @property
    def job_class(self):
        return self.__job_class

    @property
    def identifier(self):
        return self.__identifier

    @property
    def created_at(self):
        return self.__created_at

    @property
    def registered_at(self):
        return self.__registered_at

    def copy(self):
        proxy = self.__class__.__new__(self.__class__)

        for attr in self.__slots__:
            setattr(proxy, attr, getattr(self, attr))

        return proxy

    def is_being_stopped(self, get_reason: bool = False):
        """Whether this job object's task loop is being stopped.

        Args:
            get_reason (bool, optional): Whether the reason for stopping should be returned as a string. Defaults to False.

        Returns:
            Union[bool, str]: Returns a boolean if `get_reason` is False, otherwise a string is returned. If the string is empty,
                then no stopping is occuring.
        """
        return self._j.is_being_stopped(get_reason=get_reason)

    def get_last_stop_reason(self):
        """Get the last reason this job object stopped, when applicable.

        Returns:
            Optional[str]: The reason for stopping.
        """
        return self._j.get_last_stop_reason()

    def is_awaiting(self):
        """Whether this job is currently waiting
        for a coroutine to complete, which was awaited using `.wait_for(awaitable)`.

        Returns:
            bool: True/False
        """
        return self._j.is_awaiting()

    def is_alive(self):
        """Whether this job is currently alive (initialized and bound to a job manager).

        Returns:
            bool: True/False
        """
        return self._j.is_alive()

    def is_running(self):
        """Whether this job is currently running (alive and not idle).

        Returns:
            bool: True/False
        """
        return self._j.is_running()

    def is_sleeping(self):
        """Whether this job is currently idling (alive and not running).

        Returns:
            bool: True/False
        """
        return self._j.is_sleeping()

    def is_idling(self):
        """Whether this task is currently idling

        Returns:
            bool: [description]
        """
        return self._j.is_idling()

    def job_run_has_failed(self):
        """Whether this job's `.on_run()` method failed an execution attempt, usually due to an
        exception.

        Returns:
            bool: True/False
        """
        return self._j.job_run_has_failed()

    def is_killed(self):
        """Whether this job was killed."""
        return self._j.is_killed()

    def is_being_killed(self):
        """Whether this job is being killed."""
        return self.is_being_killed()

    def is_being_startup_killed(self):
        """Whether this job is being killed."""
        return self._j.is_being_startup_killed()

    def is_completed(self):
        """Whether this job has ended, either due to being killed, or due to it ending itself.

        Returns:
            bool: True/False
        """
        return self._j.is_completed()

    def is_being_completed(self):
        """Whether this job has ended, either due to being killed, or due to it ending itself.

        Returns:
            bool: True/False
        """
        return self._j.is_being_completed()

    def is_being_restarted(self, get_reason=False):
        return self._j.is_being_restarted(get_reason=get_reason)

    def get_output(self):
        """Get the data that this job has marked as its output, if present.

        Returns:
            (JobNamespace, optional): The output namespace of this job, if present.
        """
        return self._j.get_output()

    def await_output_field(self, field_name: str, timeout: float = None):
        """Wait for this job object to release the data of a specified output field.

        Args:
            timeout (float, optional): The maximum amount of time to wait
            in seconds. Defaults to None.

        Raises:
            asyncio.TimeoutError: The timeout was exceeded.
            asyncio.CancelledError: The job was killed.
        """
        return self._j.await_output_field(field_name, timeout=timeout)

    def await_completion(self, timeout: float = None):
        """Wait for this job to complete.

        Args:
            timeout (float, optional): Timeout for completion in seconds. Defaults to None.

        Raises:
            asyncio.TimeoutError: The timeout was exceeded.
            asyncio.CancelledError: The job was killed.
        """

        return self._j.await_completion(timeout=timeout)

    def next_iteration(self):
        """When the next iteration of `.on_run()` will occur.
        If not known, this method will return `None`.

        Returns:
            Optional[datetime.datetime]:
                The time at which the next iteration will occur.
        """
        return self._j.next_iteration()

    def __repr__(self):
        return f"<BotJobProxy ({self.__job_class})>"


class BotJob:
    """The base class of all bot job objects. Do not instantiate
    this class by yourself, use its subclasses"""

    CLASS_OUTPUT_FIELDS = ()

    def __init_subclass__(cls):
        for field in cls.CLASS_OUTPUT_FIELDS:
            if re.search(r"\s", field):
                raise ValueError(
                    "field names in 'CLASS_OUTPUT_FIELDS' cannot contain any whitespace"
                )

        JOB_CLASS_MAP[cls.__name__] = cls

    def __init__(self):
        self._seconds = 0
        self._minutes = 0
        self._hours = 0
        self._count = None
        self._reconnect = False

        self.manager: BotJobManagerProxy = None
        self._created_at = datetime.datetime.now(datetime.timezone.utc)
        self._registered_at = None
        self._identifier = f"{id(self)}-{int(self._created_at.timestamp()*1000)}"
        self.DATA = JobNamespace()

        self._completion_futures = []
        self._output_futures = {field: [] for field in self.CLASS_OUTPUT_FIELDS}

        self.DATA.OUTPUT = JobNamespace()

        for field in self.CLASS_OUTPUT_FIELDS:
            setattr(self.DATA.OUTPUT, field, None)

        self._task_loop: tasks.Loop = None

        self._proxy = BotJobProxy(self)

        self._is_awaiting = False
        self._is_initialized = False
        self._is_completed = False
        self._is_being_completed = False

        self._has_been_alive = False

        self._is_killed = False
        self._is_being_killed = False
        self._startup_kill = False

        self._stopping_by_self = False
        self._stopping_by_force = True
        self._is_being_stopped = False
        self._last_stop_reason = None

        self._restarting_by_outsider = False
        self._is_being_restarted = False

        self._is_sleeping = False
        self._is_idling = False

    @property
    def identifier(self):
        return self._identifier

    @property
    def created_at(self):
        return self._created_at

    @property
    def registered_at(self):
        return self._registered_at

    async def on_init(self):
        """DO NOT CALL THIS METHOD MANUALLY, EXCEPT WHEN USING `super()`
        WITHIN THIS METHOD TO ACCESS THE SUPERCLASS METHOD.

        This method allows subclasses to initialize their job object instances.
        """
        pass

    async def _on_start(self):
        self._is_sleeping = False
        self._is_idling = False
        try:
            if self._startup_kill:
                self._KILL_EXTERNAL()
                return
            else:
                output = await self.on_start()
        except Exception as exc:
            self._is_sleeping = True
            await self.on_start_error(exc)
            raise

        return output

    async def on_start(self):
        """DO NOT CALL THIS METHOD MANUALLY, EXCEPT WHEN USING `super()` WITHIN
        THIS METHOD TO ACCESS THE SUPERCLASS METHOD.

        A generic hook method that subclasses can use to initialize their job objects
        when their internal task loops start.
        """
        pass

    async def _on_run(self):
        """DO NOT CALL THIS METHOD MANUALLY, EXCEPT WHEN USING `super()` WITHIN
        THIS METHOD TO ACCESS THE SUPERCLASS METHOD.
        """
        pass

    async def on_run(self):
        """DO NOT CALL THIS METHOD MANUALLY, EXCEPT WHEN USING `super()` WITHIN
        THIS METHOD TO ACCESS THE SUPERCLASS METHOD.
        """
        pass

    async def _on_stop(self):
        self._is_being_stopped = True
        reason = self.is_being_stopped(get_reason=True)
        try:
            await self.on_stop(reason=reason, by_force=self._stopping_by_force)
        except Exception as exc:
            await self.on_stop_error(exc)
            raise
        finally:
            self._last_stop_reason = reason
            self._startup_kill = False
            self._stopping_by_self = False
            self._is_being_stopped = False
            self._is_being_restarted = False
            if self._is_being_completed:
                self._is_completed = True
            self._is_being_completed = False
            if self._is_being_killed:
                self._is_killed = True
            self._is_being_killed = False
            self._stopping_by_force = False
            self._is_sleeping = True

    async def on_stop(self, reason, by_force):
        """DO NOT CALL THIS METHOD MANUALLY, EXCEPT WHEN USING `super()` WITHIN
        THIS METHOD TO ACCESS THE SUPERCLASS METHOD.

        A method subclasses can use to uninitialize their job objects
        when their internal task loops end execution.
        """
        pass

    async def on_start_error(self, exc: Exception):
        """DO NOT CALL THIS METHOD MANUALLY, EXCEPT WHEN USING `super()` WITHIN
        THIS METHOD TO ACCESS THE SUPERCLASS METHOD.

        This method gets called when an error occurs while this job is starting up.

        Args:
            exc (Exception): [description]
        """
        print(
            f"An Exception occured before job {self.__class__} could start running its loop:\n\n",
            utils.format_code_exception(exc),
        )

    async def on_run_error(self, exc: Exception):
        """DO NOT CALL THIS METHOD MANUALLY, EXCEPT WHEN USING `super()` WITHIN
        THIS METHOD TO ACCESS THE SUPERCLASS METHOD.

        Args:
            exc (Exception): [description]
        """
        print(
            "Unhandled exception in internal background task {0.__name__!r}.".format(
                self.on_run
            ),
            file=sys.stderr,
        )
        traceback.print_exception(type(exc), exc, exc.__traceback__, file=sys.stderr)

    async def on_stop_error(self, exc: Exception):
        """DO NOT CALL THIS METHOD MANUALLY, EXCEPT WHEN USING `super()` WITHIN
        THIS METHOD TO ACCESS THE SUPERCLASS METHOD.

        This method gets called when an error occurs while this job is stopping.

        Args:
            exc (Exception): [description]
        """
        print(
            "Unhandled exception in internal background task {0.__name__!r}.".format(
                self.on_run
            ),
            file=sys.stderr,
        )
        traceback.print_exception(type(exc), exc, exc.__traceback__, file=sys.stderr)

    def is_being_stopped(self, get_reason: bool = False):
        """Whether this job object's task loop is being stopped.

        Args:
            get_reason (bool, optional): Whether the reason for stopping should be returned as a string. Defaults to False.

        Returns:
            Union[bool, str]: Returns a boolean if `get_reason` is False, otherwise a string is returned. If the string is empty,
                then no stopping is occuring.
        """
        output = self._is_being_stopped
        if get_reason:
            reason = None
            if not self._is_being_stopped:
                reason = ""
            elif self._task_loop.failed():
                reason = "INTERNAL_ERROR"
            elif self._task_loop.current_loop == self._count:
                reason = "INTERNAL_COUNT_LIMIT"
            elif self._stopping_by_self:
                if self._is_being_restarted:
                    reason = "INTERNAL_RESTART"
                elif self._is_being_completed:
                    reason = "INTERNAL_COMPLETION"
                elif self._is_being_killed:
                    reason = "INTERNAL_KILLING"
                else:
                    reason = "INTERNAL"
            elif not self._stopping_by_self:
                if self._is_being_restarted:
                    reason = "EXTERNAL_RESTART"
                elif self._is_being_killed:
                    reason = "EXTERNAL_KILLING"
                else:
                    reason = "EXTERNAL"

            reason = output
        return output

    def get_last_stop_reason(self):
        """Get the last reason this job object stopped, when applicable.

        Returns:
            Optional[str]: The reason for stopping.
        """
        return self._last_stop_reason

    async def _INITIALIZE_EXTERNAL(self):
        """DO NOT CALL THIS METHOD FROM WITHIN YOUR JOB SUBCLASS.

        Use this method to initialize a job using the `on_init` method
        of the base class.
        """
        await self.on_init()

    def STOP_LOOP(self, force=False):
        """DO NOT CALL THIS METHOD FROM OUTSIDE YOUR JOB SUBCLASS.

        Stop this job object.

        Args:
            force (bool, optional): Whether this job object should be stopped
                forcefully instead of gracefully, thereby ignoring any exceptions
                that it might have handled when reconnecting is enabled for it.
                Defaults to False.
        """
        task = self._task_loop.get_task()
        if not self._is_being_stopped and task and not task.done():
            self._stopping_by_self = True
            self._is_being_stopped = True
            if force:
                self._stopping_by_force = True
                self._task_loop.cancel()
            else:
                self._task_loop.stop()
            return True
        return False

    def _STOP_LOOP_EXTERNAL(self, force=False):
        """DO NOT CALL THIS METHOD FROM WITHIN YOUR JOB SUBCLASS.

        Stop this job object.

        Args:
            force (bool, optional): Whether this job object should be stopped
                forcefully instead of gracefully, thereby ignoring any exceptions
                that it might have handled when reconnecting is enabled for it.
                Defaults to False.
        """
        task = self._task_loop.get_task()
        if not self._is_being_stopped and task and not task.done():
            self._is_being_stopped = True
            if force:
                self._stopping_by_force = True
                self._task_loop.cancel()
            else:
                self._task_loop.stop()
            return True
        return False

    def RESTART_LOOP(self):
        """DO NOT CALL THIS METHOD FROM OUTSIDE YOUR JOB SUBCLASS.

        Restart this job object by forcefully stopping it
        (cancelling its task loop), before starting it again automatically.

        This will cause 'INTERNAL_RESTART' to be passed to `on_stop`.
        """
        task = self._task_loop.get_task()
        if (
            not self._is_being_restarted
            and not self._task_loop.is_being_cancelled()
            and task is not None
            and not task.done()
        ):
            self._is_being_restarted = True
            self._is_being_stopped = True
            self._stopping_by_self = True
            self._stopping_by_force = True
            self._task_loop.restart()
            return True
        return False

    def _RESTART_LOOP_EXTERNAL(self):
        """DO NOT CALL THIS METHOD FROM WITHIN YOUR JOB SUBCLASS.

        Restart this job object by forcefully stopping it
        (cancelling its task loop), before starting it again automatically.

        This will cause 'EXTERNAL_RESTART' to be passed to `on_stop`.
        """
        task = self._task_loop.get_task()
        if (
            not self._is_being_restarted
            and not self._task_loop.is_being_cancelled()
            and task is not None
            and not task.done()
        ):
            self._is_being_restarted = True
            self._is_being_stopped = True
            self._stopping_by_self = False
            self._stopping_by_force = True
            self._task_loop.restart()
            return True
        return False

    def COMPLETE(self):
        """
        DO NOT CALL THIS METHOD FROM OUTSIDE YOUR JOB SUBCLASS.

        Stops this job object gracefully, before removing it from its `BotJobManager`.
        Any job that was completed has officially finished execution, and all jobs waiting for this job
        to complete will be notified. If a job had reconnecting enabled, then it will be silently cancelled to ensure
        that it suspends all execution."""

        if not self._is_being_completed:
            self._is_being_completed = True
            if not self._is_being_stopped:
                self.STOP_LOOP(force=self._reconnect)

            for fut in self._completion_futures:
                if not fut.cancelled():
                    fut.set_result(None)

            for field_name, fut_list in self._output_futures.items():
                output = getattr(self.DATA.OUTPUT, field_name)
                for fut in fut_list:
                    if not fut.cancelled():
                        fut.set_result(output)

                fut_list.clear()

            self._completion_futures.clear()

            self._is_sleeping = False
            self.manager._eject()
            return True
        return False

    def KILL(self):
        """
        DO NOT CALL THIS METHOD FROM OUTSIDE YOUR JOB SUBCLASS.

        Stops this job object gracefully like `.stop_run()`, before removing it from its `BotJobManager`.
        Any job that was closed has officially finished execution, and all jobs waiting for this job
        to close will be notified. If a job had reconnecting enabled, then it will be silently cancelled to ensure
        that it suspends all execution."""

        if not self._is_being_killed:
            self._is_being_killed = True
            if not self._is_being_stopped:
                self.STOP_LOOP(force=self._reconnect)

            for fut in self._completion_futures:
                if not fut.cancelled():
                    fut.cancel(msg=f"Job object '{self}' was killed.")

            for fut_list in self._output_futures.values():
                for fut in fut_list:
                    if not fut.cancelled():
                        fut.cancel(
                            msg=f"Job object '{self}' was killed. job output might be incomplete."
                        )

                fut_list.clear()

            self._completion_futures.clear()

            self._is_sleeping = False
            self.manager._eject()
            return True
        return False

    def _KILL_EXTERNAL(self, awaken=False):
        """DO NOT CALL THIS METHOD FROM WITHIN YOUR JOB SUBCLASS.

        Args:
            awaken (bool, optional): Whether to awaken . Defaults to False.

        Returns:
            _type_: _description_
        """

        if not self._is_being_killed:
            if not self._task_loop.is_running() and awaken:
                self._startup_kill = True  # start and kill immediately
                self._task_loop.start()
                return True

            self._is_being_killed = True
            if not self._is_being_stopped:
                self._STOP_LOOP_EXTERNAL(force=self._reconnect)

            for fut in self._completion_futures:
                if not fut.cancelled():
                    fut.cancel(msg=f"Job object '{self}' was killed.")

            for fut in self._output_futures:
                if not fut.cancelled():
                    fut.cancel(
                        msg=f"Job object '{self}' was killed. job output might be incomplete."
                    )

            self._completion_futures.clear()
            self._output_futures.clear()

            self._is_sleeping = False
            self.manager.remove_self(self)
            return True
        return False

    async def wait_for(self, awaitable):
        """Wait for a given awaitable object to complete.
        While the awaitable is active, this job object
        will be marked as waiting.

        Args:
            awaitable: An awaitable object

        Returns:
            Any: The result of the given coroutine.

        Raises:
            TypeError: The given object was not a coroutine.
        """
        if inspect.isawaitable(awaitable):
            self._is_awaiting = True
            result = await awaitable
            self._is_awaiting = False
            return result

        raise TypeError("argument 'awaitable' must be an awaitable object")

    def is_initialized(self):
        """Whether this job has been initialized.

        Returns:
            bool: True/False
        """
        return self._is_initialized

    def is_awaiting(self):
        """Whether this job is currently waiting
        for a coroutine to complete, which was awaited using `.wait_for(awaitable)`.

        Returns:
            bool: True/False
        """
        return self._is_awaiting

    def is_alive(self):
        """Whether this job is currently alive (initialized and bound to a job manager).

        Returns:
            bool: True/False
        """
        return self.manager is not None and self._is_initialized

    def is_running(self):
        """Whether this job is currently running (alive and not idle).

        Returns:
            bool: True/False
        """
        return (
            self.manager is not None
            and self._task_loop.is_running()
            and not self._is_sleeping
        )

    def is_sleeping(self):
        """Whether this job is currently sleeping (alive and not running).

        Returns:
            bool: True/False
        """
        return self.manager is not None and self._is_sleeping

    def is_idling(self):
        """Whether this task is currently idling
        (running, waiting for the next opportunity to continue execution)

        Returns:
            bool: True/False
        """
        return self._is_idling

    def job_run_has_failed(self):
        """Whether this jobs `.on_run()` method failed an execution attempt, usually due to an
        exception.

        Returns:
            bool: True/False
        """
        return self._task_loop.failed()

    def is_killed(self):
        """Whether this job was killed."""
        return self._is_killed

    def is_being_killed(self):
        """Whether this job is being killed."""
        return self._is_being_killed

    def is_being_startup_killed(self):
        """Whether this job is being killed while trying to start up."""
        return self._is_being_killed and self._startup_kill

    def is_completed(self):
        """Whether this job has ended, either due to being killed, or due to it ending itself.

        Returns:
            bool: True/False
        """
        return self._is_completed

    def is_being_completed(self):
        """Whether this job is currently ending, either due to being killed, or due to it ending itself.

        Returns:
            bool: True/False
        """
        return self._is_being_completed

    def is_being_restarted(self, get_reason=False):
        """Whether this job is being restarted.

        Args:
            get_reason (bool, optional): If set to True, the restart reason will be returned. Defaults to False.

        Returns:
            bool: True/False
            str: 'INTERNAL_RESTART' or 'EXTERNAL_RESTART'
        """
        if get_reason:
            reason = self.is_being_stopped(get_reason=get_reason)
            if reason in ("INTERNAL_RESTART", "EXTERNAL_RESTART"):
                return reason
            else:
                return ""

        return self._is_being_restarted

    def await_completion(self, timeout: float = None):
        """Wait for this job object to complete.

        Args:
            timeout (float, optional): Timeout for completion. Defaults to None.

        Raises:
            asyncio.TimeoutError: The timeout was exceeded.
            asyncio.CancelledError: The job was killed.
        """
        if self._task_loop.loop is not None:
            fut = self._task_loop.loop.create_future()
        else:
            fut = asyncio.get_event_loop().create_future()

        self._completion_futures.append(fut)

        return asyncio.wait_for(fut, timeout)

    def await_output_field(self, field_name: str, timeout: float = None):
        """Wait for this job object to release the data of a specified output field.

        Args:
            timeout (float, optional): The maximum amount of time to wait in seconds. Defaults to None.

        Raises:
            asyncio.TimeoutError: The timeout was exceeded.
            asyncio.CancelledError: The job was killed.
        """

        if self._task_loop.loop is not None:
            fut = self._task_loop.loop.create_future()
        else:
            fut = asyncio.get_event_loop().create_future()

        if field_name not in self._output_futures:
            raise (
                ValueError(
                    f"field name '{field_name}' not defined in 'CLASS_OUTPUT_FIELDS' of {self.__class__.__name__} class"
                )
                if isinstance(field_name, str)
                else ValueError(
                    f"field name argument '{field_name}' must be of type str, not {field_name.__class__}"
                )
            )
        else:
            self._output_futures[field_name].append(fut)

        return asyncio.wait_for(fut, timeout=timeout)

    def release_output_field(self, field_name: str):
        """Release the data of an output field to external jobs awaiting it.

        Args:
            field_name (str): The name of the field to release.
        """

        if field_name not in self._output_futures:
            raise (
                ValueError(
                    f"field name '{field_name}' not defined in 'CLASS_OUTPUT_FIELDS' of {self.__class__} class"
                )
                if isinstance(field_name, str)
                else ValueError(
                    f"field name argument '{field_name}' must be of type str, not {field_name.__class__}"
                )
            )

        field_data = getattr(self.DATA.OUTPUT, field_name)
        for fut in self._output_futures[field_name]:
            if not fut.cancelled():
                fut.set_result(field_data)

        self._output_futures[field_name].clear()

    def __str__(self):
        return f"<{self.__class__}: id:{self._identifier}>"


class IntervalJob(BotJob):
    """Base class for interval based jobs.
    Subclasses are expected to overload the `on_run()` method.
    `on_start()` and `on_stop()` and `on_run_error(exc)` can optionally be overloaded.

    One can override the class variables `default_seconds`, `default_minutes`,
    `default_hours`, `CLASS_DEFAULT_COUNT` and `CLASS_DEFAULT_RECONNECT` in subclasses. They are derived
    from the keyword arguments of the `discord.ext.tasks.Loop` constructor.
    These will act as defaults for each bot job object
    created from this class.
    """

    CLASS_DEFAULT_SECONDS = 0
    CLASS_DEFAULT_MINUTES = 0
    CLASS_DEFAULT_HOURS = 0
    CLASS_DEFAULT_COUNT = None
    CLASS_DEFAULT_RECONNECT = True

    def __init__(
        self,
        seconds: Optional[int] = None,
        minutes: Optional[int] = None,
        hours: Optional[int] = None,
        count: Optional[int] = None,
        reconnect: Optional[bool] = None,
    ):
        """Create a new IntervalJob instance.

        Args:
            seconds (Optional[int]):
            minutes (Optional[int]):
            hours (Optional[int]):
            count (Optional[int]):
            reconnect (Optional[bool]):
                Overrides for the default class variables for an IntervalJob instance.
        """

        super().__init__()
        self._seconds = self.CLASS_DEFAULT_SECONDS if seconds is None else seconds
        self._minutes = self.CLASS_DEFAULT_MINUTES if minutes is None else minutes
        self._hours = self.CLASS_DEFAULT_HOURS if hours is None else hours
        self._count = self.CLASS_DEFAULT_COUNT if count is None else count
        self._reconnect = (
            self.CLASS_DEFAULT_RECONNECT if reconnect is None else reconnect
        )

        self._task_loop = tasks.Loop(
            self._on_run,
            seconds=self._seconds,
            minutes=self._minutes,
            hours=self._hours,
            count=self._count,
            reconnect=self._reconnect,
            loop=None,
        )

        self._task_loop.before_loop(self._on_start)
        self._task_loop.after_loop(self._on_stop)
        self._task_loop.error(self.on_run_error)

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
            tuple: `(seconds, minutes, hours)`
        """
        return self._seconds, self._minutes, self._hours

    def change_interval(self, seconds: int = 0, minutes: int = 0, hours: int = 0):
        """Change the interval at which this job will run its `on_run()` method.
        This will only be applied on the next iteration of `.on_run()`

        Args:
            seconds (int, optional): Defaults to 0.
            minutes (int, optional): Defaults to 0.
            hours (int, optional): Defaults to 0.
        """
        self._task_loop.change_interval(
            seconds=seconds,
            minutes=minutes,
            hours=hours,
        )

        self._seconds = seconds
        self._minutes = minutes
        self._hours = hours

    async def _on_run(self):
        if self._startup_kill:
            return

        self._is_idling = False
        await self.on_run()
        if self._seconds or self._minutes or self._hours:
            self._is_idling = True

    async def on_run(self):
        """DO NOT CALL THIS METHOD MANUALLY, EXCEPT WHEN USING `super()` WITHIN
        THIS METHOD TO ACCESS THE SUPERCLASS METHOD.

        The code to run at the set interval.
        This method must be overloaded in subclasses.

        Raises:
            NotImplementedError: This method must be overloaded in subclasses.
        """
        raise NotImplementedError()


class EventJob(BotJob):
    """A job class for jobs that run in reaction to specific events
    passed to them by their `BotJobManager` object.
    Subclasses are expected to overload the `on_run(self, event)` method.
    `on_start(self)` and `on_stop(self)` and `on_run_error(self, exc)` can
    optionally be overloaded.
    One can also override the class variables `CLASS_DEFAULT_COUNT` and `CLASS_DEFAULT_RECONNECT`
    in subclasses. They are derived from the keyword arguments of the
    `discord.ext.tasks.loop` decorator. Unlike `IntervalJob` class instances,
    the instances of this class depend on their `BotJobManager` to trigger
    the execution of their `.on_run()` method, and will stop running if
    all ClientEvent objects passed to them have been processed.

    Attributes:
        CLASS_EVENT_TYPES:
            A tuple denoting the set of `BaseEvent` classes whose instances
            should be recieved after their corresponding event is registered
            by the `BotJobManager` of an instance of this class. By default,
            all instances of `BaseEvent` will be propagated.
    """

    CLASS_EVENT_TYPES: tuple = (events.BaseEvent,)
    CLASS_DEFAULT_RECONNECT = True
    CLASS_DEFAULT_COUNT = None
    CLASS_DEFAULT_MAX_IDLING_DURATION: Optional[
        datetime.timedelta
    ] = datetime.timedelta()

    CLASS_DEFAULT_BLOCK_QUEUE_ON_STOP = False
    CLASS_DEFAULT_WAKEUP_ON_DISPATCH = True
    CLASS_DEFAULT_BLOCK_QUEUE_AT_SLEEP = False
    CLASS_DEFAULT_CLEAR_QUEUE_AT_STARTUP = False

    def __init_subclass__(cls):
        if not isinstance(cls.CLASS_EVENT_TYPES, (list, tuple)):
            raise TypeError(
                "the 'CLASS_EVENT_TYPES' class attribute must be of type 'list'/'tuple' and"
                " must contain one or more subclasses of `BaseEvent`"
            )
        elif not cls.CLASS_EVENT_TYPES or not all(
            issubclass(et, events.BaseEvent) for et in cls.CLASS_EVENT_TYPES
        ):
            raise ValueError(
                "the 'CLASS_EVENT_TYPES' class attribute"
                " must contain one or more subclasses of `BaseEvent`"
            )

    def __init__(
        self,
        count: Optional[int] = None,
        reconnect: Optional[bool] = None,
        max_idling_duration: Optional[datetime.timedelta] = None,
        block_queue_on_stop: Optional[bool] = None,
        block_queue_at_sleep: Optional[bool] = None,
        clear_queue_at_startup: Optional[bool] = None,
        wakeup_on_dispatch: Optional[bool] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._event_queue = deque()
        self._count = self.CLASS_DEFAULT_COUNT if count is None else count
        self._current_loop_count = 0
        self._reconnect = (
            self.CLASS_DEFAULT_RECONNECT if reconnect is None else reconnect
        )
        self._max_idling_duration = (
            self.CLASS_DEFAULT_MAX_IDLING_DURATION
            if max_idling_duration is None
            else max_idling_duration
        )

        self._block_queue_on_stop = (
            self.CLASS_DEFAULT_BLOCK_QUEUE_ON_STOP
            if block_queue_on_stop is None
            else block_queue_on_stop
        )
        self._block_queue_at_sleep = (
            self.CLASS_DEFAULT_BLOCK_QUEUE_AT_SLEEP
            if block_queue_at_sleep is None
            else block_queue_at_sleep
        )
        self._clear_queue_at_startup = (
            self.CLASS_DEFAULT_CLEAR_QUEUE_AT_STARTUP
            if clear_queue_at_startup is None
            else clear_queue_at_startup
        )
        self._wakeup_on_dispatch = (
            self.CLASS_DEFAULT_WAKEUP_ON_DISPATCH
            if wakeup_on_dispatch is None
            else wakeup_on_dispatch
        )

        if self._block_queue_at_sleep or self._clear_queue_at_startup:
            self._wakeup_on_dispatch = False

        self._allow_dispatch = True

        self._stopping_by_empty_queue = False

        self._idle_since = None
        self._stopping_by_idling_timeout = False

        self._last_event = None
        self._task_loop = tasks.Loop(
            self._on_run,
            seconds=0,
            minutes=0,
            hours=0,
            count=None,
            reconnect=self._reconnect,
            loop=None,
        )
        self._task_loop.before_loop(self._on_start)
        self._task_loop.after_loop(self._on_stop)
        self._task_loop.error(self.on_run_error)

    def _add_event(self, event: events.BaseEvent):
        task_is_running = self._task_loop.is_running()
        if (
            not self._allow_dispatch
            or (self._block_queue_on_stop and self._is_being_stopped)
            or (self._block_queue_at_sleep and not task_is_running)
        ):
            return

        self._event_queue.append(event)
        if self._wakeup_on_dispatch and not task_is_running:
            self._task_loop.start()

    def check_event(self, event: events.BaseEvent):
        """A method for subclasses that can be overloaded to perform validations on a `BaseEvent`
        object that is passed to them. Must return a boolean value indicating the
        validaiton result. If not overloaded, this method will always return `True`.

        Args:
            event (events.BaseEvent): The event object to run checks upon.
        """
        return True

    def get_last_event(self):
        """Get the last event dispatched to this event job object.

        Returns:
            _type_: _description_
        """
        return self._last_event

    async def _on_start(self):
        if self._clear_queue_at_startup:
            self._event_queue.clear()

        await super()._on_start()

    async def _on_run(self):
        if self._startup_kill:
            return

        if not self._event_queue:
            if not self._max_idling_duration:
                if self._max_idling_duration is None:
                    if not self._is_idling:
                        self._is_idling = True
                        self._idle_since = datetime.datetime.now(datetime.timezone.utc)
                    else:
                        return
                else:  # self._max_idling_duration is a zero timedelta
                    self._stopping_by_empty_queue = True
                    self.STOP_LOOP()
                    return

            elif not self._is_idling:
                self._is_idling = True
                self._idle_since = datetime.datetime.now(datetime.timezone.utc)

            if (
                self._is_idling
                and (datetime.datetime.now(datetime.timezone.utc) - self._idle_since)
                > self._max_idling_duration
            ):
                self._stopping_by_idling_timeout = True
                self.STOP_LOOP()
                return
            else:
                return

        elif self._current_loop_count == self._count:
            self.STOP_LOOP()
            return

        self._is_idling = False
        self._stopping_by_idling_timeout = False
        self._idle_since = None

        event = self._event_queue.popleft()
        output = await self.on_run(event=event)
        self._last_event = event

        self._current_loop_count += 1

        return output

    async def on_run(self, event: events.ClientEvent):
        """The code to run whenever an event is recieved.
        This method must be overloaded in subclasses.

        Raises:
            NotImplementedError: This method must be overloaded in subclasses.
        """
        raise NotImplementedError()

    async def _on_stop(self):
        try:
            await super()._on_stop()
        finally:
            self._current_loop_count = 0
            self._stopping_by_idling_timeout = False

    def get_queue_size(self):
        return len(self._event_queue)

    def clear_queue(self):
        self._event_queue.clear()

    @contextmanager
    def queue_blocker(self):
        """A method to be used as a context manager for
        temporarily blocking the event queue of this event job
        while running an operation, thereby disabling event dispatch to it.
        """
        self._allow_dispatch = False
        try:
            yield
        finally:
            self._allow_dispatch = True

    def queue_is_blocked(self):
        """Whether event dispatching to this event job's event queue
        is disabled and its event queue is blocked.

        Returns:
            bool: True/False
        """
        return self._allow_dispatch

    def block_queue(self):
        """Block the event queue of this event job, thereby disabling
        event dispatch to it.
        """
        self._allow_dispatch = False

    def unblock_queue(self):
        """Unblock the event queue of this event job, thereby enabling
        event dispatch to it.
        """
        self._allow_dispatch = True

    def is_being_stopped(self, get_reason: bool = False):
        output = self._is_being_stopped
        if get_reason:
            reason = None
            if not self._is_being_stopped:
                reason = ""
            elif self._task_loop.failed():
                reason = "INTERNAL_ERROR"
            elif (
                not self._max_idling_duration
                and self._max_idling_duration is not None
                and self._stopping_by_empty_queue
            ):
                reason = "INTERNAL_EMPTY_QUEUE"
            elif self._stopping_by_idling_timeout:
                reason = "INTERNAL_IDLING_TIMEOUT"
            elif self._current_loop_count == self._count:
                reason = "INTERNAL_COUNT_LIMIT"
            elif self._stopping_by_self:
                if self._is_being_restarted:
                    reason = "INTERNAL_RESTART"
                elif self._is_being_completed:
                    reason = "INTERNAL_COMPLETION"
                elif self._is_being_killed:
                    reason = "INTERNAL_KILLING"
                else:
                    reason = "INTERNAL"
            elif not self._stopping_by_self:
                if self._is_being_restarted:
                    reason = "EXTERNAL_RESTART"
                elif self._is_being_killed:
                    reason = "EXTERNAL_KILLING"
                else:
                    reason = "EXTERNAL"

            reason = output
        return output


class ClientEventJob(EventJob):
    """A job class for jobs that run in reaction to specific client events
    (Discord API events) passed to them by their `BotJobManager` object.
    Subclasses are expected to overload the `on_run(self, event)` method.
    `on_start(self)` and `on_stop(self)` and `on_run_error(self, exc)` can
    optionally be overloaded.
    One can also override the class variables `CLASS_DEFAULT_COUNT` and `CLASS_DEFAULT_RECONNECT`
    in subclasses. They are derived from the keyword arguments of the
    `discord.ext.tasks.loop` decorator. Unlike `IntervalJob` class instances,
    the instances of this class depend on their `BotJobManager` to trigger
    the execution of their `.on_run()` method, and will stop running if
    all ClientEvent objects passed to them have been processed.

    Attributes:
        CLASS_EVENT_TYPES:
            A tuple denoting the set of `ClientEvent` classes whose instances
            should be recieved after their corresponding event is registered
            by the `BotJobManager` of an instance of this class. By default,
            all instances of `ClientEvent` will be propagated.
    """

    CLASS_EVENT_TYPES: tuple = (events.ClientEvent,)


class SingletonJobBase(BotJob):
    pass


class OneTimeJob(IntervalJob):
    """A subclass of `IntervalJob` whose subclasses's
    job objects will only run once, before going into an idle state.
    automatically. For more control, use `IntervalJob` directly.
    """

    CLASS_DEFAULT_COUNT = 1

    def __init__(self):
        super().__init__()

    async def on_stop(self, *args, **kwargs):
        self.COMPLETE()


class RegisterDelayedJob(OneTimeJob):
    """A subclass of `OneTimeJob` that
    adds a given set of job proxies to its `BotJobManager`
    only after a given period of time in seconds.

    Attributes:
        delay (float):
            The delay for the input jobs in seconds.
    """

    def __init__(self, delay: float, *job_proxies: BotJobProxy, **kwargs):
        """Create a new RegisterDelayedJob instance.

        Args:
            delay (float):
                The delay for the input jobs in seconds.
            *jobs Union[ClientEventJob, IntervalJob]:
                The jobs to be delayed.
        """
        super().__init__(**kwargs)
        self.DATA.delay = delay
        self.DATA.jobs = job_proxies

    async def on_start(self):
        await asyncio.sleep(self.DATA.delay)

    async def on_run(self):
        for job_proxy in self.DATA.jobs:
            await self.manager.register_job(job_proxy)

    async def on_stop(self, *args, **kwargs):
        self.COMPLETE()


from .manager import BotJobManagerProxy
