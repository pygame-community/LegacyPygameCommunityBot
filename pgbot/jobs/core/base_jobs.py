"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file implements the base classes for a task object system that
can be used to implement background processes for the bot. 
"""

from __future__ import annotations
import asyncio
from aiohttp import ClientError
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
from typing import Any, Callable, Coroutine, Iterable, Optional, Sequence, Type, Union

import discord
from discord.ext import tasks

from pgbot.utils import utils
from pgbot import common

from . import events


_JOB_CLASS_MAP = {}
# """A dictionary of all Job subclasses that were created. Do not access outside of this module."""

_JOB_MANAGER_JOB_CLS = None


def get_job_class_from_id(class_identifier: str, closest_match: bool = True):

    name, timestamp_str = class_identifier.split("-")

    if name in _JOB_CLASS_MAP:
        if timestamp_str in _JOB_CLASS_MAP[name]:
            return _JOB_CLASS_MAP[name][timestamp_str]["class"]
        elif closest_match:
            for ts_str in _JOB_CLASS_MAP[name]:
                return _JOB_CLASS_MAP[name][ts_str]["class"]

    raise KeyError(
        f"cannot find job class with an identifier of "
        f"'{class_identifier}' in the job class registry"
    )


def get_job_class_id(cls: Type[Job], raise_exceptions=True):

    if raise_exceptions and not issubclass(cls, Job):
        raise TypeError("argument 'cls' must be a subclass of a job base class")

    try:
        class_identifier = cls._IDENTIFIER
    except AttributeError:
        raise TypeError(
            "invalid job class, must be" " a subclass of a job base class"
        ) from None

    try:
        name, timestamp_str = class_identifier.split("-")
    except ValueError:
        if raise_exceptions:
            raise ValueError(
                "invalid identifier found in the given job class"
            ) from None
        return

    if name in _JOB_CLASS_MAP:
        if timestamp_str in _JOB_CLASS_MAP[name]:
            if _JOB_CLASS_MAP[name][timestamp_str]["class"] is cls:
                return class_identifier
            else:
                if raise_exceptions:
                    raise ValueError(
                        f"The given job class has the incorrect identifier"
                    )
        else:
            if raise_exceptions:
                ValueError(
                    f"The given job class is registered under"
                    " a different identifier in the job class registry"
                )

    if raise_exceptions:
        raise LookupError(
            f"The given job class does not exist in the job class registry"
        )


def get_job_class_permission_level(cls: Type[Job], raise_exceptions=True):

    if raise_exceptions and not issubclass(cls, Job):
        raise TypeError("argument 'cls' must be a subclass of a job base class")

    try:
        class_identifier = cls._IDENTIFIER
    except AttributeError:
        raise TypeError(
            "invalid job class, must be"
            " a subclass of a job base class with an identifier"
        ) from None

    try:
        name, timestamp_str = class_identifier.split("-")
    except ValueError:
        if raise_exceptions:
            raise ValueError(
                "invalid identifier found in the given job class"
            ) from None
        return

    if _JOB_MANAGER_JOB_CLS is not None and issubclass(cls, _JOB_MANAGER_JOB_CLS):
        return PERMISSION_LEVELS.SYSTEM

    if name in _JOB_CLASS_MAP:
        if timestamp_str in _JOB_CLASS_MAP[name]:
            if _JOB_CLASS_MAP[name][timestamp_str]["class"] is cls:
                return _JOB_CLASS_MAP[name][timestamp_str]["permission_level"]
            else:
                if raise_exceptions:
                    raise ValueError(
                        f"The given job class has the incorrect identifier"
                    )
        else:
            if raise_exceptions:
                ValueError(
                    f"The given job class is registered under"
                    " a different identifier in the job class registry"
                )

    if raise_exceptions:
        raise LookupError(
            f"The given job class does not exist in the job class registry"
        )


DEFAULT_JOB_EXCEPTION_WHITELIST = (
    OSError,
    discord.GatewayNotFound,
    discord.ConnectionClosed,
    ClientError,
    asyncio.TimeoutError,
)
"""The default exceptions handled in discord.ext.tasks.Loop
upon reconnecting."""


class JOB_STATUS:
    FRESH = "FRESH"
    INITIALIZED = "INITIALIZED"

    STARTING = "STARTING"
    RUNNING = "RUNNING"
    AWAITING = "AWAITING"
    IDLING = "IDLING"
    COMPLETING = "COMPLETING"
    DYING = "DYING"
    RESTARTING = "RESTARTING"
    STOPPING = "STOPPING"

    STOPPED = "STOPPED"
    KILLED = "KILLED"
    COMPLETED = "COMPLETED"


class JOB_VERBS:
    CREATE = "CREATE"
    INITIALIZE = "INITIALIZE"
    REGISTER = "REGISTER"
    SCHEDULE = "SCHEDULE"
    GUARD = "GUARD"

    FIND = "FIND"

    START = "START"
    STOP = "STOP"
    RESTART = "RESTART"

    UNSCHEDULE = "UNSCHEDULE"
    UNGUARD = "UNGUARD"

    KILL = "KILL"

    _SIMPLE_PAST_TENSE = dict(
        CREATE="CREATED",
        INITIALIZE="INITIALIZED",
        REGISTER="REGISTERED",
        SCHEDULE="SCHEDULED",
        GUARD="GUARDED",
        FIND="FOUND",
        START="STARTED",
        STOP="STOPPED",
        RESTART="RESTARTED",
        UNSCHEDULE="UNSCHEDULED",
        UNGUARD="UNGUARDED",
        KILL="KILLED",
    )

    _PRESENT_CONTINUOUS_TENSE = dict(
        CREATE="CREATING",
        INITIALIZE="INITIALIZING",
        REGISTER="REGISTERING",
        SCHEDULE="SCHEDULING",
        GUARD="GUARDING",
        FIND="FINDING",
        START="STARTING",
        STOP="STOPPING",
        RESTART="RESTARTING",
        UNSCHEDULE="UNSCHEDULING",
        UNGUARD="UNGUARDING",
        KILL="KILLING",
    )


class STOP_REASONS:
    INTERNAL = "INTERNAL"
    """Job is stopping due to an internal reason.
    """
    INTERNAL_ERROR = "INTERNAL_ERROR"
    """Job is stopping due to an internal error.
    """
    INTERNAL_RESTART = "INTERNAL_RESTART"
    """Job is stopping due to an internal restart.
    """
    INTERNAL_COUNT_LIMIT = "INTERNAL_COUNT_LIMIT"
    """Job is stopping due to hitting its maximimum execution
    count before stopping.
    """
    INTERNAL_COMPLETION = "INTERNAL_COMPLETION"
    """Job is stopping for finishing all execution, it has completed.
    """
    INTERNAL_KILLING = "INTERNAL_KILLING"
    """Job is stopping due to killing itself internally.
    """

    INTERNAL_IDLING_TIMEOUT = "INTERNAL_IDLING_TIMEOUT"
    """Job is stopping after staying idle beyond a specified timeout.
    """

    INTERNAL_EMPTY_QUEUE = "INTERNAL_EMPTY_QUEUE"
    """Job is stopping due to an empty internal queue of recieved events.
    """

    EXTERNAL = "EXTERNAL"
    """Job is stopping due to an unknown external reason.
    """
    EXTERNAL_RESTART = "EXTERNAL_RESTART"
    """Job is stopping due to an external restart.
    """
    EXTERNAL_KILLING = "EXTERNAL_KILLING"
    """Job is stopping due to being killed externally.
    """


class PERMISSION_LEVELS:
    LOWEST = 0
    """The lowest permission level.
    An Isolated job which has no information about other jobs being executed.
    Permissions:
        Can manage its own execution at will.
    """

    LOW = 1 << 1
    """A low permission level.

    Permissions:
        - Can manage its own execution at will.
        - Can discover and view all alive jobs, and request data from them.
    """

    MEDIUM = DEFAULT = 1 << 2
    """The default permission level, with simple job management permissions.

    Permissions:
        - Can manage its own execution at will.
        - Can discover and view all alive jobs, and request data from them.
        - Can instantiate, register, start and schedule jobs of a lower permission level.
        - Can stop, restart, or kill jobs instantiated by itself or unschedule its scheduled jobs.
        - Can unschedule jobs that don't have an alive job as a scheduler.
    """

    HIGH = 1 << 3
    """An elevated permission level, with additional control over jobs
    of a lower permission level.

    Permissions:
        - Can manage its own execution at will.
        - Can discover and view all alive jobs, and request data from them.
        - Can instantiate, register, start and schedule jobs of a lower permission level.
        - Can stop, restart, or kill jobs instantiated by itself or unschedule its scheduled jobs.
        - Can unschedule jobs that don't have an alive job as a scheduler.
        - Can stop, restart, kill or unschedule any job of a lower permission level.
        - Can guard and unguard jobs of a lower permission level instantiated by itself.
    """

    HIGHEST = 1 << 4
    """The highest usable permission level, with additional control over jobs
    of a lower permission level. Lower permissions additionally apply to this level.

    Permissions:
        - Can manage its own execution at will.
        - Can discover and view all alive jobs, and request data from them.
        - Can instantiate, register, start and schedule jobs of a lower permission level.
        - Can stop, restart, or kill jobs instantiated by itself or unschedule its scheduled jobs.
        - Can unschedule jobs that don't have an alive job as a scheduler.
        - Can stop, restart, kill or unschedule any job of a lower permission level.
        - Can guard and unguard jobs of a lower permission level instantiated by itself.
        - Can guard and unguard jobs of the same permission level instantiated by itself.
        - Can instantiate, register, start and schedule jobs of the same permission level.
        - Can stop, restart, kill or unschedule any job of the same permission level.
    """

    SYSTEM = 1 << 5
    """The highest possible permission level reserved for system-level jobs. Cannot be used directly.
    Lower permissions additionally apply to this level.

    Permissions:
        - Can manage its own execution at will.
        - Can discover and view all alive jobs, and request data from them.
        - Can instantiate, register, start and schedule jobs of a lower permission level.
        - Can stop, restart, or kill jobs instantiated by itself or unschedule its scheduled jobs.
        - Can unschedule jobs that don't have an alive job as a scheduler.
        - Can stop, restart, kill or unschedule any job of a lower permission level.
        - Can guard and unguard jobs of a lower permission level instantiated by itself.
        - Can guard and unguard jobs of the same permission level instantiated by itself.
        - Can instantiate, register, start and schedule jobs of the same permission level.
        - Can stop, restart, kill or unschedule any job of the same permission level.
        - Can guard or unguard any job.
    """

    @staticmethod
    def get_name(level: int):
        if not isinstance(level, int):
            raise TypeError(
                "argument 'level' must be" f" of type 'int', not {level.__class__}"
            )
        elif level % 2 or not (
            PERMISSION_LEVELS.LOWEST <= level <= PERMISSION_LEVELS.HIGHEST
        ):
            raise ValueError(
                "argument 'level' must be" " a valid permission level integer"
            )

        if level == PERMISSION_LEVELS.LOWEST:
            return "LOWEST"

        elif level == PERMISSION_LEVELS.LOW:
            return "LOW"

        elif level == PERMISSION_LEVELS.MEDIUM:
            return "MEDIUM"

        elif level == PERMISSION_LEVELS.HIGH:
            return "HIGH"

        elif level == PERMISSION_LEVELS.HIGHEST:
            return "HIGHEST"

        elif level == PERMISSION_LEVELS.SYSTEM:
            return "SYSTEM"


class JobError(Exception):
    """Generic job object run-time error."""

    pass


class JobPermissionError(JobError):
    """Job object permisssion error."""

    pass


class JobStateError(JobError):
    """An invalid job object state is preventing an operation."""

    pass


class JobInitializationError(JobStateError):
    """Initialization of a job object failed."""

    pass


class JobNamespace(SimpleNamespace):
    """A subclass of SimpleNamespace, which is used by job objects
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


class JobProxy:
    __slots__ = (
        "__j",
        "__job_class",
        "__identifier",
        "__created_at",
        "__registered_at",
    )

    def __init__(self, job):
        self.__j = job
        self.__job_class = job.__class__
        self.__identifier = job._identifier
        self.__created_at = job.created_at
        self.__registered_at = job.registered_at

    @property
    def job_class(self):
        return self.__job_class

    @property
    def identifier(self):
        return self.__identifier

    @property
    def creator(self):
        """The `JobProxy` of the creator of this job object."""
        return self.__j._creator

    @property
    def guardian(self):
        """The `JobProxy` of the current guardian of this job object."""
        return self.__j._guardian

    @property
    def created_at(self):
        return self.__created_at

    @property
    def registered_at(self):
        return self.__registered_at

    @property
    def schedule_identifier(self):
        """The identfier of the scheduling operation that instantiated
        this job object.
        """
        return self.__j._schedule_identifier

    @property
    def permission_level(self):
        return self.__job_class._PERMISSION_LEVEL

    def copy(self):
        proxy = self.__class__.__new__(self.__class__)

        for attr in self.__slots__:
            setattr(proxy, attr, getattr(self, attr))

        return proxy

    def loop_count(self):
        """The current amount of `on_run()` calls completed by this job object."""
        return self._loop_count

    def is_being_stopped(self, get_reason: bool = False):
        """Whether this job object's task loop is being stopped.

        Args:
            get_reason (bool, optional):
                Whether the reason for stopping should be returned as a string.
                Defaults to False.

        Returns:
            Union[bool, str]:
                Returns a boolean if `get_reason` is False, otherwise a string
                is returned. If the string is empty, no stopping is occuring.
        """
        return self.__j.is_being_stopped(get_reason=get_reason)

    def get_last_stop_reason(self):
        """Get the last reason this job object stopped, when applicable.

        Returns:
            Optional[str]: The reason for stopping.
        """
        return self.__j.get_last_stop_reason()

    def is_awaiting(self):
        """Whether this job is currently waiting for a coroutine to complete,
        which was awaited using `.wait_for(awaitable)`.

        Returns:
            bool: True/False
        """
        return self.__j.is_awaiting()

    def awaiting_since(self):
        """The last time at which this job object began awaiting, if available.

        Returns:
            datetime.datetime: The time, if available.
        """
        return self.__j.awaiting_since()

    def alive(self):
        """Whether this job is currently alive
        (initialized and bound to a job manager).

        Returns:
            bool: True/False
        """
        return self.__j.alive()

    def alive_since(self):
        """The last time at which this job object became alive, if available.

        Returns:
            datetime.datetime: The time, if available.
        """
        return self.__j.alive_since()

    def is_starting(self):
        """Whether this job is currently starting to run.

        Returns:
            bool: True/False
        """
        return self.__j.is_starting()

    def is_running(self):
        """Whether this job is currently running (alive and not stopped).

        Returns:
            bool: True/False
        """
        return self.__j.running()

    def running_since(self):
        """The last time at which this job object started running, if available.

        Returns:
            datetime.datetime: The time, if available.
        """
        return self.__j.running_since()

    def stopped(self):
        """Whether this job is currently stopped (alive and not running).

        Returns:
            bool: True/False
        """
        return self.__j.stopped()

    def stopped_since(self):
        """The last time at which this job object stopped, if available.

        Returns:
            datetime.datetime: The time, if available.
        """
        return self.__j.stopped_since()

    def is_idling(self):
        """Whether this task is currently idling
        (running, waiting for the next opportunity to continue execution)

        Returns:
            bool: True/False
        """
        return self.__j.idling()

    def idling_since(self):
        """The last time at which this job object began idling, if available.

        Returns:
            datetime.datetime: The time, if available.
        """
        return self.__j.idling_since()

    def failed(self):
        """Whether this job's `.on_run()` method failed an execution attempt,
        usually due to an exception.

        Returns:
            bool: True/False
        """
        return self.__j.failed()

    def killed(self):
        """Whether this job was killed."""
        return self.__j.killed()

    def killed_at(self):
        """The last time at which this job object was killed, if available.

        Returns:
            datetime.datetime: The time, if available.
        """
        return self.__j.killed_at()

    def is_being_killed(self, get_reason=False):
        """Whether this job is being killed.

        Args:
            get_reason (bool, optional):
                If set to True, the reason for killing will be returned.
                Defaults to False.

        Returns:
            bool: True/False
            str:
                'INTERNAL_KILLING' or 'EXTERNAL_KILLING' or ''
                depending on if this job is being killed or not.
        """
        return self.__j.is_being_killed(get_reason=get_reason)

    def is_being_startup_killed(self):
        """Whether this job was started up only for it to be killed.
        This is useful for knowing if a job skipped `on_start()` and `on_run()`
        due to that, and can be checked for within `on_stop()`.
        """
        return self.__j.is_being_startup_killed()

    def completed(self):
        """Whether this job completed successfully.

        Returns:
            bool: True/False
        """
        return self.__j.completed()

    def completed_at(self):
        """The last time at which this job object completed successfully,
        if available.

        Returns:
            datetime.datetime: The time, if available.
        """
        return self.__j.completed_at()

    def is_being_completed(self):
        """Whether this job is in the process of completing,
        either due to being killed, or due to it ending itself.

        Returns:
            bool: True/False
        """
        return self.__j.is_being_completed()

    def done(self):
        """Whether this job was killed or has completed.

        Returns:
            bool: True/False
        """
        return self.__j.done()

    def done_since(self):
        """The last time at which this job object completed successfully or was killed, if available.

        Returns:
            datetime.datetime: The time, if available.
        """
        return self.__j.done_since()

    def is_being_restarted(self, get_reason=False):
        """Whether this job is being restarted.

        Args:
            get_reason (bool, optional):
                If set to True, the restart reason will be returned.
                Defaults to False.

        Returns:
            bool: True/False
            str:
                'INTERNAL_RESTART' or 'EXTERNAL_RESTART' or ''
                depending on if a restart applies.
        """
        return self.__j.is_being_restarted(get_reason=get_reason)

    def is_being_guarded(self):
        """Whether this job object is being guarded.

        Returns:
            bool: True/False
        """
        return self.__j.is_being_guarded()

    def await_done(self, timeout: float = None):
        """Wait for this job object to be done (completed or killed).

        Args:
            timeout (float, optional):
                Timeout for awaiting. Defaults to None.
            cancel_if_killed (bool):
                Whether `asyncio.CancelledError` should be raised if the
                job is killed. Defaults to False.

        Raises:
            JobStateError: This job object is already done or not alive.
            asyncio.TimeoutError: The timeout was exceeded.
            asyncio.CancelledError: The job was killed.
        """

        return self.__j.await_done(timeout=timeout)

    def await_unguard(self, timeout: float = None):
        """Wait for this job object to be unguarded.

        Args:
            timeout (float, optional):
                Timeout for awaiting. Defaults to None.

        Raises:
            JobStateError: This job object is already done or not alive.
            asyncio.TimeoutError: The timeout was exceeded.
            asyncio.CancelledError: The job was killed.
        """
        return self.__j.await_unguard(timeout=timeout)

    async def await_output_field(self, field_name: str, timeout: float = None):
        """Wait for this job object to release the data of a specified output field.

        Args:
            timeout (float, optional):
                The maximum amount of time to wait in seconds. Defaults to None.

        Raises:
            asyncio.TimeoutError: The timeout was exceeded.
            asyncio.CancelledError: The job was killed.
        """
        return await self.__j.await_output_field(field_name, timeout=timeout)

    def interval_job_next_iteration(self):
        """
        THIS METHOD WILL ONLY WORK ON PROXIES TO JOB OBJECTS
        THAT ARE `IntervalJob` SUBCLASSES.

        When the next iteration of `.on_run()` will occur.
        If not known, this method will return `None`.

        Returns:
            datetime.datetime: The time at which the next iteration will occur,
            if available.

        Raises:
            TypeError: The class of this job proxy's job is not an 'IntervalJob' subclass.
        """
        if hasattr(self.__j, IntervalJob):
            return self.__j.next_iteration()

        raise TypeError(
            f"The '{self.__job_class}' job class of this job object's"
            " proxy is not an 'IntervalJob' subclass"
        ) from None

    def __repr__(self):
        return f"<JobProxy ({self.__j})>"


class JobBase:
    __slots__ = ()

    _CREATED_AT = datetime.datetime.now(datetime.timezone.utc)
    _IDENTIFIER = f"JobBase-{int(_CREATED_AT.timestamp()*1_000_000_000)}"
    _PERMISSION_LEVEL = PERMISSION_LEVELS.MEDIUM

    OUTPUT_FIELDS = ()

    NAMESPACE_CLASS = JobNamespace

    def __init_subclass__(cls, permission_level=None):
        for field in cls.OUTPUT_FIELDS:
            if re.search(r"\s", field):
                raise ValueError(
                    "field names in 'OUTPUT_FIELDS'" " cannot contain any whitespace"
                )

        if cls is not _JOB_MANAGER_JOB_CLS:
            cls._CREATED_AT = datetime.datetime.now(datetime.timezone.utc)

        name = cls.__name__
        timestamp = f"{int(cls._CREATED_AT.timestamp()*1_000_000_000)}"

        if permission_level is not None:
            if isinstance(permission_level, int):
                if (
                    not permission_level % 2
                    and PERMISSION_LEVELS.LOWEST
                    <= permission_level
                    <= PERMISSION_LEVELS.HIGHEST
                ) or (
                    _JOB_MANAGER_JOB_CLS is not None
                    and issubclass(cls, _JOB_MANAGER_JOB_CLS)
                    and permission_level == PERMISSION_LEVELS.SYSTEM
                ):
                    cls._PERMISSION_LEVEL = permission_level
                else:
                    raise ValueError(
                        "argument 'permission_level' must be a usable permission level from the 'PERMISSION_LEVELS' class namespace"
                    )
            else:
                raise TypeError(
                    "argument 'permission_level' must be a usable permission level from the 'PERMISSION_LEVELS' class namespace"
                )
        else:
            permission_level = cls._PERMISSION_LEVEL

        cls._IDENTIFIER = f"{name}-{timestamp}"

        if name not in _JOB_CLASS_MAP:
            _JOB_CLASS_MAP[name] = {}

        _JOB_CLASS_MAP[name][timestamp] = {
            "class": cls,
            "permission_level": permission_level,
        }


class Job(JobBase):
    """The base class of all job objects. Do not instantiate
    this class by yourself, use its subclasses"""

    __slots__ = (
        "_seconds",
        "_minutes",
        "_hours",
        "_count",
        "_reconnect",
        "_loop_count",
        "_manager",
        "_creator",
        "_created_at_ts",
        "_registered_at_ts",
        "_completed_at_ts",
        "_killed_at_ts",
        "_identifier",
        "_schedule_identifier",
        "_data",
        "_output",
        "_done_futures",
        "_output_futures",
        "_unguard_futures",
        "_task_loop",
        "_proxy",
        "_guarded_job_proxies_dict",
        "_guardian",
        "_is_being_guarded",
        "_on_start_exception",
        "_on_run_exception",
        "_on_stop_exception",
        "_initialized",
        "_is_starting",
        "_completed",
        "_is_being_completed",
        "_killed",
        "_is_being_killed",
        "_startup_kill",
        "_stopping_by_self",
        "_stopping_by_force",
        "_is_being_stopped",
        "_last_stop_reason",
        "_is_awaiting",
        "_is_being_restarted",
        "_stopped",
        "_is_idling",
        "_alive_since_ts",
        "_awaiting_since_ts",
        "_idling_since_ts",
        "_running_since_ts",
        "_stopped_since_ts",
    )

    def __init__(self):
        self._seconds = 0
        self._minutes = 0
        self._hours = 0
        self._count = None
        self._reconnect = False

        self._manager: JobManagerProxy = None
        self._creator: JobProxy = None
        self._created_at_ts = time.time()
        self._registered_at_ts = None
        self._completed_at_ts = None
        self._killed_at_ts = None
        self._identifier = f"{id(self)}-{int(self._created_at_ts*1_000_000_000)}"
        self._schedule_identifier = None
        self._data = self.NAMESPACE_CLASS()

        self._done_futures = []
        self._output_futures = {field: [] for field in self.OUTPUT_FIELDS}
        self._unguard_futures = []

        self._output = self.NAMESPACE_CLASS()

        for field in self.OUTPUT_FIELDS:
            setattr(self.output, field, None)

        self._task_loop: tasks.Loop = None

        self._proxy = JobProxy(self)

        self._guarded_job_proxies_dict = {}

        self._on_start_exception = None
        self._on_run_exception = None
        self._on_stop_exception = None

        self._is_awaiting = False
        self._initialized = False
        self._is_starting = False
        self._completed = False
        self._is_being_completed = False

        self._killed = False
        self._is_being_killed = False
        self._startup_kill = False

        self._stopping_by_self = False
        self._stopping_by_force = True
        self._is_being_stopped = False
        self._last_stop_reason = None

        self._is_being_restarted = False
        self._stopped = False
        self._is_idling = False

        self._alive_since_ts = None
        self._awaiting_since_ts = None
        self._idling_since_ts = None
        self._running_since_ts = None
        self._stopped_since_ts = None

    @property
    def identifier(self):
        return self._identifier

    @property
    def created_at(self):
        if self._created_at_ts:
            return datetime.datetime.fromtimestamp(
                self._created_at_ts, tz=datetime.timezone.utc
            )

    @property
    def registered_at(self):
        if self._registered_at_ts:
            return datetime.datetime.fromtimestamp(
                self._registered_at_ts, tz=datetime.timezone.utc
            )

    @property
    def permission_level(self):
        return self._PERMISSION_LEVEL

    @property
    def data(self):
        """The `JobNamespace` instance bound to this job object for storage."""
        return self._data

    @property
    def output(self):
        """The `JobNamespace` instance bound to this job object for output fields."""
        return self._output

    @property
    def manager(self):
        """The `JobManagerProxy` object bound to this job object."""
        return self._manager

    @property
    def creator(self):
        """The `JobProxy` of the creator of this job object."""
        return self._creator

    @property
    def guardian(self):
        """The `JobProxy` of the current guardian of this job object."""
        return self._guardian

    @property
    def proxy(self):
        """The `JobProxy` object bound to this job object."""
        return self._proxy

    @property
    def schedule_identifier(self):
        """The identfier of the scheduling operation that instantiated
        this job object.
        """
        return self._schedule_identifier

    async def on_init(self):
        """DO NOT CALL THIS METHOD MANUALLY, EXCEPT WHEN USING `super()`
        WITHIN THIS METHOD TO ACCESS THE SUPERCLASS METHOD.

        This method allows subclasses to initialize their job object instances.
        """
        pass

    async def _on_start(self):
        self._on_start_exception = None
        self._on_run_exception = None
        self._on_stop_exception = None

        self._stopped = False
        self._stopped_since_ts = None

        self._is_starting = True

        self._running_since_ts = time.time()

        self._is_idling = False
        self._idling_since_ts = None

        try:
            if not self._startup_kill:
                await self.on_start()
        except Exception as exc:
            self._on_start_exception = exc
            self._stopping_by_self = True
            self._is_being_stopped = True
            self._stopping_by_force = True
            await self.on_start_error(exc)
            self._stop_cleanup(STOP_REASONS.INTERNAL_ERROR)
            self._running_since_ts = None
            raise

        finally:
            self._is_starting = False

    async def on_start(self):
        """DO NOT CALL THIS METHOD MANUALLY, EXCEPT WHEN USING `super()` WITHIN
        OVERLOADED VERSIONS OF THIS METHOD TO ACCESS A SUPERCLASS METHOD.

        A generic hook method that subclasses can use to setup their job objects
        when they start.

        Raises:
            NotImplementedError: This method must be overloaded in subclasses.
        """
        raise NotImplementedError()

    async def _on_run(self):
        """DO NOT CALL THIS METHOD MANUALLY, EXCEPT WHEN USING `super()` WITHIN
        OVERLOADED VERSIONS OF THIS METHOD TO ACCESS A SUPERCLASS METHOD.

        Raises:
            NotImplementedError: This method must be overloaded in subclasses.
        """
        raise NotImplementedError()

    async def on_run(self):
        """DO NOT CALL THIS METHOD MANUALLY, EXCEPT WHEN USING `super()` WITHIN
        OVERLOADED VERSIONS OF THIS METHOD TO ACCESS A SUPERCLASS METHOD.

        Raises:
            NotImplementedError: This method must be overloaded in subclasses.
        """
        raise NotImplementedError()

    def _stop_cleanup(self, reason):
        self._last_stop_reason = reason
        self._startup_kill = False
        self._stopping_by_self = False
        self._stopping_by_force = False
        self._is_being_stopped = False
        self._is_being_restarted = False

        if self._is_being_completed:
            self._completed = True
            self._completed_at_ts = time.time()

            self._alive_since_ts = None

            for fut, cancel_if_killed in self._done_futures:
                if not fut.cancelled():
                    fut.set_result(True)

            for field_name, fut_list in self._output_futures.items():
                output = getattr(self.output, field_name)
                for fut in fut_list:
                    if not fut.cancelled():
                        fut.set_result(output)

                fut_list.clear()

            for fut in self._unguard_futures:
                if not fut.cancelled():
                    fut.set_result(True)

            for job_proxy in self._guarded_job_proxies_dict.values():
                self.manager.unguard_job(job_proxy)

            self._guarded_job_proxies_dict.clear()
            self._done_futures.clear()
            self._output_futures.clear()

            self._is_being_completed = False

        elif self._is_being_killed:
            self._killed = True
            self._killed_at_ts = time.time()

            self._alive_since_ts = None

            for fut, cancel_if_killed in self._done_futures:
                if not fut.cancelled():
                    if cancel_if_killed:
                        fut.cancel(msg=f"Job object '{self}' was killed.")
                    else:
                        fut.set_result(True)

            for fut_list in self._output_futures.values():
                for fut in fut_list:
                    if not fut.cancelled():
                        fut.cancel(
                            msg=f"Job object '{self}' was killed."
                            " Job output might be incomplete."
                        )

                fut_list.clear()

            for fut in self._unguard_futures:
                if not fut.cancelled():
                    fut.set_result(True)

            for job_proxy in self._guarded_job_proxies_dict.values():
                self.manager.unguard_job(job_proxy)

            self._guarded_job_proxies_dict.clear()
            self._done_futures.clear()
            self._output_futures.clear()

            self._is_being_killed = False

        self._is_idling = False
        self._idling_since_ts = None

        self._running_since_ts = None

        if self._killed or self._completed:
            self._stopped = False
            self._stopped_since_ts = None
            self._manager._eject()
        else:
            self._stopped = True
            self._stopped_since_ts = time.time()

    async def _on_stop(self):
        self._is_being_stopped = True
        reason = self.is_being_stopped(get_reason=True)
        try:
            if not self._stopping_by_self:
                await asyncio.wait_for(
                    self.on_stop(reason=reason, by_force=self._stopping_by_force),
                    self._manager.get_job_stop_timeout(),
                )
            else:
                await self.on_stop(reason=reason, by_force=self._stopping_by_force)

        except asyncio.TimeoutError:
            self._on_stop_exception = exc
            if self._stopping_by_self:
                await self.on_stop_error(exc)
            raise

        except Exception as exc:
            self._on_stop_exception = exc
            await self.on_stop_error(exc)
            raise

        finally:
            self._stop_cleanup(reason)

    async def on_stop(self, reason, by_force):
        """DO NOT CALL THIS METHOD MANUALLY, EXCEPT WHEN USING `super()` WITHIN
        OVERLOADED VERSIONS OF THIS METHOD TO ACCESS A SUPERCLASS METHOD.

        A method that subclasses can use to shutdown their job objects
        when they stop.

        Note that `on_stop_error()` will not be called if this method raises
        TimeoutError, and this job did not trigger the stop operation.

        Raises:
            NotImplementedError: This method must be overloaded in subclasses.
        """
        raise NotImplementedError()

    async def on_start_error(self, exc: Exception):
        """DO NOT CALL THIS METHOD MANUALLY, EXCEPT WHEN USING `super()` WITHIN
        OVERLOADED VERSIONS OF THIS METHOD TO ACCESS A SUPERCLASS METHOD.

        This method gets called when an error occurs while this job is starting up.

        Args:
            exc (Exception): The exception that occured.
        """
        print(
            f"{self}:\n" f"An Exception occured in 'on_start':\n\n",
            utils.format_code_exception(exc),
        )

    async def _on_run_error(self, exc: Exception):
        self._on_run_exception = exc
        await self.on_run_error(exc)

    async def on_run_error(self, exc: Exception):
        """DO NOT CALL THIS METHOD MANUALLY, EXCEPT WHEN USING `super()` WITHIN
        OVERLOADED VERSIONS OF THIS METHOD TO ACCESS A SUPERCLASS METHOD.

        Args:
            exc (Exception): The exception that occured.
        """
        print(
            f"{self}:\n" f"An Exception occured in 'on_run':\n\n",
            utils.format_code_exception(exc),
        )

    async def on_stop_error(self, exc: Exception):
        """DO NOT CALL THIS METHOD MANUALLY, EXCEPT WHEN USING `super()` WITHIN
        OVERLOADED VERSIONS OF THIS METHOD TO ACCESS A SUPERCLASS METHOD.

        This method gets called when an error occurs
        while this job is stopping.

        Args:
            exc (Exception): The exception that occured.
        """
        print(
            f"{self}:\n" f"An Exception occured in 'on_stop':\n\n",
            utils.format_code_exception(exc),
        )

    def is_being_stopped(self, get_reason: bool = False):
        """Whether this job object's task loop is being stopped.

        Args:
            get_reason (bool, optional):
                Whether the reason for stopping should be returned as a string.
                Defaults to False.

        Returns:
            Union[bool, str]:
                Returns a boolean if `get_reason` is False, otherwise
                a string is returned. If the string is empty,
                no stopping is occuring.
        """
        output = self._is_being_stopped
        if get_reason:
            reason = None
            if not self._is_being_stopped:
                reason = ""
            elif self._task_loop.failed():
                reason = STOP_REASONS.INTERNAL_ERROR
            elif self._task_loop.current_loop == self._count:
                reason = STOP_REASONS.INTERNAL_COUNT_LIMIT
            elif self._stopping_by_self:
                if self._is_being_restarted:
                    reason = STOP_REASONS.INTERNAL_RESTART
                elif self._is_being_completed:
                    reason = STOP_REASONS.INTERNAL_COMPLETION
                elif self._is_being_killed:
                    reason = STOP_REASONS.INTERNAL_KILLING
                else:
                    reason = STOP_REASONS.INTERNAL
            elif not self._stopping_by_self:
                if self._is_being_restarted:
                    reason = STOP_REASONS.EXTERNAL_RESTART
                elif self._is_being_killed:
                    reason = STOP_REASONS.EXTERNAL_KILLING
                else:
                    reason = STOP_REASONS.EXTERNAL

            output = reason
        return output

    def add_to_exception_whitelist(self, *exception_types):
        """Add exceptions to a whitelist, which allows them to be ignored
        when they are raised, if reconnection is enabled.
        Args:
            *exception_types: The exception types to add.
        """
        self._task_loop.add_exception_type(*exception_types)

    def remove_from_exception_whitelist(self, *exception_types):
        """Remove exceptions from the exception whitelist for reconnection.
        Args:
            *exception_types: The exception types to remove.
        """
        self._task_loop.remove_exception_type(*exception_types)

    def clear_exception_whitelist(self, keep_default=True):
        """Clear all the exceptions whitelisted for reconnection.

        keep_default:
            Preserve the default set of exceptions in the whitelist.
            Defaults to True.

        """
        self._task_loop.clear_exception_types()
        if keep_default:
            self._task_loop.add_exception_type(*DEFAULT_JOB_EXCEPTION_WHITELIST)

    def get_last_stop_reason(self):
        """Get the last reason this job object stopped, when applicable.

        Returns:
            Optional[str]: The reason for stopping.
        """
        return self._last_stop_reason

    def get_start_exception(self):
        """Get the exception that caused this job to fail at startup
        within the `on_start()` method, otherwise return None.

        Returns:
            Exception: The exception instance.
            None: No exception has been raised in `on_start()`.
        """
        return self._on_start_exception

    def get_run_exception(self):
        """Get the exception that caused this job to fail while running
        its main loop within the `on_run()` method. This is the same
        exception passed to `on_run_error()`, otherwise return None.

        Returns:
            Exception: The exception instance.
            None: No exception has been raised in `on_run()`.
        """
        return self._on_run_exception

    def get_stop_exception(self):
        """Get the exception that caused this job to fail while
        shutting down within the `on_stop()` method, otherwise return None.

        Returns:
            Exception: The exception instance.
            None: No exception has been raised in `on_stop()`.
        """
        return self._on_stop_exception

    async def _INITIALIZE_EXTERNAL(self):
        """DO NOT CALL THIS METHOD MANUALLY.

        Use this method to initialize a job using the `on_init` method
        of the base class.
        """
        if self._manager is not None and not self._killed and not self._completed:
            await self.on_init()
            self._alive_since_ts = time.time()

    def STOP(self, force=False):
        """DO NOT CALL THIS METHOD FROM OUTSIDE YOUR JOB SUBCLASS.

        Stop this job object.

        Args:
            force (bool, optional): Whether this job object should be stopped
                forcefully instead of gracefully, thereby ignoring any exceptions
                that it might have handled if reconnecting is enabled for it.
                Defaults to False.
        Returns:
            bool: Whether the call was successful.
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

    def _STOP_EXTERNAL(self, force=False):
        """DO NOT CALL THIS METHOD MANUALLY.

        Stop this job object.

        Args:
            force (bool, optional): Whether this job object should be stopped
                forcefully instead of gracefully, thereby ignoring any exceptions
                that it might have handled when reconnecting is enabled for it.
                Defaults to False.

        Returns:
            bool: Whether the call was successful.
        """
        task = self._task_loop.get_task()
        if not self._is_being_stopped and task and not task.done():
            self._stopping_by_self = False
            self._is_being_stopped = True
            if force:
                self._stopping_by_force = True
                self._task_loop.cancel()
            else:
                self._task_loop.stop()
            return True
        return False

    def RESTART(self):
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

    def _RESTART_EXTERNAL(self):
        """DO NOT CALL THIS METHOD MANUALLY.

        Restart this job object by forcefully stopping it
        (cancelling its task loop), before starting it again automatically.

        This will cause 'EXTERNAL_RESTART' to be passed to `on_stop`.
        """
        task = self._task_loop.get_task()
        if (
            not self._is_being_restarted
            and not self._task_loop.is_being_cancelled()
            and task is not None  # disallow restart without ever starting
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
        """DO NOT CALL THIS METHOD FROM OUTSIDE YOUR JOB SUBCLASS.

        Stops this job object gracefully, before removing it
        from its `JobManager`. Any job that was completed
        has officially finished execution, and all jobs waiting
        for this job to complete will be notified. If a job had
        reconnecting enabled, then it will be silently cancelled
        to ensure that it suspends all execution.
        """

        if not self._is_being_completed:
            self._is_being_completed = True
            if not self._is_being_stopped:
                self.STOP(force=self._reconnect)

            self._stopped = False
            self._stopped_since_ts = None
            return True
        return False

    def KILL(self):
        """
        DO NOT CALL THIS METHOD FROM OUTSIDE YOUR JOB SUBCLASS.

        Stops this job object gracefully like `.stop_run()`, before removing it from its `JobManager`.
        Any job that was closed has officially finished execution, and all jobs waiting for this job
        to close will be notified. If a job had reconnecting enabled, then it will be silently cancelled to ensure
        that it suspends all execution.

        Returns:
            bool: Whether this method was successful.
        """

        if not self._is_being_killed:
            self._is_being_killed = True
            if not self._is_being_stopped:
                self.STOP(force=self._reconnect)

            self._stopped = False
            self._stopped_since_ts = None
            return True
        return False

    def _KILL_EXTERNAL(self, awaken=True):
        """DO NOT CALL THIS METHOD MANUALLY.

        Args:
            awaken (bool, optional):
                Whether to awaken this job object before killing it. Defaults to True.

        Returns:
            bool: Whether this method was successful.
        """

        if not self._is_being_killed:
            if not self._task_loop.is_running() and awaken:
                self._startup_kill = True  # start and kill immediately
                self._task_loop.start()
                return True

            self._is_being_killed = True
            if not self._is_being_stopped:
                self._STOP_EXTERNAL(force=self._reconnect)

            self._stopped = False
            self._stopped_since_ts = None
            return True
        return False

    async def wait_for(self, awaitable, timeout: float = None):
        """Wait for a given awaitable object to complete.
        While awaiting the awaitable, this job object
        will be marked as waiting.

        Args:
            awaitable: An awaitable object

        Returns:
            Any: The result of the given coroutine.

        Raises:
            TypeError: The given object was not a coroutine.
        """
        if inspect.isawaitable(awaitable):
            try:
                self._is_awaiting = True
                self._awaiting_since_ts = time.time()
                result = await asyncio.wait_for(awaitable, timeout)
                return result
            finally:
                self._is_awaiting = False
                self._awaiting_since_ts = None

        raise TypeError("argument 'awaitable' must be an awaitable object")

    def loop_count(self):
        """The current amount of `on_run()` calls completed by this job object."""
        return self._loop_count

    def initialized(self):
        """Whether this job has been initialized.

        Returns:
            bool: True/False
        """
        return self._initialized

    def is_awaiting(self):
        """Whether this job is currently waiting
        for a coroutine to complete, which was awaited
        using `.wait_for(awaitable)`.

        Returns:
            bool: True/False
        """
        return self._is_awaiting

    def awaiting_since(self):
        """The last time at which this job object began awaiting, if available.

        Returns:
            datetime.datetime: The time, if available.
        """
        if self._awaiting_since_ts:
            return datetime.datetime.fromtimestamp(
                self._awaiting_since_ts, tz=datetime.timezone.utc
            )

    def alive(self):
        """Whether this job is currently alive
        (initialized and bound to a job manager, not completed or killed).

        Returns:
            bool: True/False
        """
        return (
            self._manager is not None
            and self._initialized
            and not self._killed
            and not self._completed
        )

    def alive_since(self):
        """The last time at which this job object became alive, if available.

        Returns:
            datetime.datetime: The time, if available.
        """
        if self._alive_since_ts:
            return datetime.datetime.fromtimestamp(
                self._alive_since_ts, tz=datetime.timezone.utc
            )

    def is_starting(self):
        """Whether this job is currently starting to run.

        Returns:
            bool: True/False
        """
        return self._is_starting

    def is_running(self):
        """Whether this job is currently running (alive and not stopped).

        Returns:
            bool: True/False
        """
        return self.alive() and self._task_loop.is_running() and not self._stopped

    def running_since(self):
        """The last time at which this job object started running, if available.

        Returns:
            datetime.datetime: The time, if available.
        """
        if self._running_since_ts:
            return datetime.datetime.fromtimestamp(
                self._running_since_ts, tz=datetime.timezone.utc
            )

    def stopped(self):
        """Whether this job is currently stopped (alive and not running).

        Returns:
            bool: True/False
        """
        return self._stopped

    def stopped_since(self):
        """The last time at which this job object stopped, if available.

        Returns:
            datetime.datetime: The time, if available.
        """
        if self._stopped_since_ts:
            return datetime.datetime.fromtimestamp(
                self._stopped_since_ts, tz=datetime.timezone.utc
            )

    def is_idling(self):
        """Whether this task is currently idling
        (running, waiting for the next opportunity to continue execution)

        Returns:
            bool: True/False
        """
        return self._is_idling

    def idling_since(self):
        """The last time at which this job object began idling, if available.

        Returns:
            datetime.datetime: The time, if available.
        """
        if self._idling_since_ts:
            return datetime.datetime.fromtimestamp(
                self._idling_since_ts, tz=datetime.timezone.utc
            )

    def failed(self):
        """Whether this job's `.on_run()` method failed an execution attempt,
        due to an unhandled exception being raised.

        Returns:
            bool: True/False
        """
        return self._task_loop.failed()

    def killed(self):
        """Whether this job was killed."""
        return self._killed

    def killed_at(self):
        """The last time at which this job object was killed, if available.

        Returns:
            datetime.datetime: The time, if available.
        """
        if self._killed_at_ts:
            return datetime.datetime.fromtimestamp(
                self._killed_at_ts, tz=datetime.timezone.utc
            )

    def is_being_killed(self, get_reason=False):
        """Whether this job is being killed.

        Args:
            get_reason (bool, optional):
                If set to True, the reason for killing will be returned.
                Defaults to False.

        Returns:
            bool: True/False
            str:
                'INTERNAL_KILLING' or 'EXTERNAL_KILLING' or ''
                depending on if this job is being killed or not.
        """
        if get_reason:
            reason = self.is_being_stopped(get_reason=get_reason)
            if reason in ("INTERNAL_KILLING", "EXTERNAL_KILLING"):
                return reason
            else:
                return ""

        return self._is_being_restarted

    def is_being_startup_killed(self):
        """Whether this job was started up only for it to be killed.
        This is useful for knowing if a job skipped `on_start()` and `on_run()`
        due to that, and can be checked for within `on_stop()`.
        """
        return self._is_being_killed and self._startup_kill

    def completed(self):
        """Whether this job completed successfully.

        Returns:
            bool: True/False
        """
        return self._completed

    def completed_at(self):
        """The last time at which this job object completed successfully,
        if available.

        Returns:
            datetime.datetime: The time, if available.
        """
        if self._completed_at_ts:
            return datetime.datetime.fromtimestamp(
                self._completed_at_ts, tz=datetime.timezone.utc
            )

    def is_being_completed(self):
        """Whether this job is currently completing.

        Returns:
            bool: True/False
        """
        return self._is_being_completed

    def done(self):
        """Whether this job was killed or has completed.

        Returns:
            bool: True/False
        """
        return self._killed or self._completed

    def done_since(self):
        """The last time at which this job object completed successfully or was killed, if available.

        Returns:
            datetime.datetime: The time, if available.
        """
        return self._completed_at_ts or self._killed_at_ts

    def is_being_restarted(self, get_reason=False):
        """Whether this job is being restarted.

        Args:
            get_reason (bool, optional):
                If set to True, the restart reason will be returned.
                Defaults to False.

        Returns:
            bool: True/False
            str:
                'INTERNAL_RESTART' or 'EXTERNAL_RESTART' or ''
                depending on if a restart applies.
        """
        if get_reason:
            reason = self.is_being_stopped(get_reason=get_reason)
            if reason in ("INTERNAL_RESTART", "EXTERNAL_RESTART"):
                return reason
            else:
                return ""

        return self._is_being_restarted

    def is_being_guarded(self):
        """Whether this job object is being guarded.

        Returns:
            bool: True/False
        """
        return self._is_being_guarded

    def await_done(self, timeout: float = None, cancel_if_killed: bool = False):
        """Wait for this job object to be done (completed or killed).

        Args:
            timeout (float, optional):
                Timeout for awaiting. Defaults to None.
            cancel_if_killed (bool):
                Whether `asyncio.CancelledError` should be raised if the
                job is killed. Defaults to False.

        Raises:
            JobStateError: This job object is already done or not alive.
            asyncio.TimeoutError: The timeout was exceeded.
            asyncio.CancelledError: The job was killed.
        """
        if not self.alive():
            raise JobStateError("This job object is not alive.")
        elif self.done():
            raise JobStateError("This job object is already done and not alive.")

        fut = self._task_loop.loop.create_future()

        self._done_futures.append((fut, cancel_if_killed))

        return asyncio.wait_for(fut, timeout)

    def await_unguard(self, timeout: float = None):
        """Wait for this job object to be unguarded.

        Args:
            timeout (float, optional):
                Timeout for awaiting. Defaults to None.

        Raises:
            JobStateError: This job object is already done or not alive.
            asyncio.TimeoutError: The timeout was exceeded.
            asyncio.CancelledError: The job was killed.
        """
        if not self.alive():
            raise JobStateError("This job object is not alive.")
        elif self.done():
            raise JobStateError("This job object is already done and not alive.")
        elif not self._is_being_guarded:
            raise JobStateError("this job object is not being guarded by a job")

        fut = self._task_loop.loop.create_future()

        self._unguard_futures.append(fut)

        return asyncio.wait_for(fut, timeout)

    def await_output_field(self, field_name: str, timeout: float = None):
        """Wait for this job object to release the data of a
        specified output field while running.

        Args:
            timeout (float, optional):
            The maximum amount of time to wait in seconds. Defaults to None.

        Raises:
            RuntimeError: This job object is already done.
            asyncio.TimeoutError: The timeout was exceeded.
            asyncio.CancelledError: The job was killed.
        """

        if self.done():
            raise RuntimeError("This job object is already done and not alive.")

        fut = self._task_loop.loop.create_future()

        if field_name not in self._output_futures:
            raise (
                ValueError(
                    f"field name '{field_name}' not defined in"
                    " 'OUTPUT_FIELDS' of {self.__class__.__name__} class"
                )
                if isinstance(field_name, str)
                else ValueError(
                    f"field name argument '{field_name}' must be of type str,"
                    " not {field_name.__class__}"
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
                    f"field name '{field_name}' not defined in"
                    f" 'OUTPUT_FIELDS' of {self.__class__.__name__} class"
                )
                if isinstance(field_name, str)
                else ValueError(
                    f"field name argument '{field_name}' must be"
                    f" of type str, not {field_name.__class__}"
                )
            )

        field_data = getattr(self.output, field_name)
        for fut in self._output_futures[field_name]:
            if not fut.cancelled():
                fut.set_result(field_data)

        self._output_futures[field_name].clear()

    def status(self):
        output = None
        if self.alive():
            if self.is_running():
                if self.is_starting():
                    output = JOB_STATUS.STARTING
                elif self.is_idling():
                    output = JOB_STATUS.IDLING
                elif self.is_awaiting():
                    output = JOB_STATUS.AWAITING
                elif self.is_being_completed():
                    output = JOB_STATUS.COMPLETING
                elif self.is_being_killed():
                    output = JOB_STATUS.DYING
                elif self.is_being_restarted():
                    output = JOB_STATUS.RESTARTING
                elif self.is_being_stopped():
                    output = JOB_STATUS.STOPPING
                else:
                    output = JOB_STATUS.RUNNING
            elif self.stopped():
                output = JOB_STATUS.STOPPED
            elif self.initialized():
                output = JOB_STATUS.INITIALIZED

        elif self.completed():
            output = JOB_STATUS.COMPLETED
        elif self.killed():
            output = JOB_STATUS.KILLED
        else:
            output = JOB_STATUS.FRESH

        return output

    def __repr__(self):
        output_str = (
            f"<{self.__class__.__name__}"
            f" (ID={self._identifier} CREATED_AT={self.created_at}"
            f" STATUS={self.status()})>"
        )

        return output_str


class IntervalJob(Job):
    """Base class for interval based jobs.
    Subclasses are expected to overload the `on_run()` method.
    `on_start()` and `on_stop()` and `on_run_error(exc)`
    can optionally be overloaded.

    One can override the class variables `DEFAULT_SECONDS`,
    `DEFAULT_MINUTES`, `DEFAULT_HOURS`, `DEFAULT_COUNT`
    and `DEFAULT_RECONNECT` in subclasses. They are derived
    from the keyword arguments of the `discord.ext.tasks.Loop`
    constructor. These will act as defaults for each job
    object created from this class.
    """

    DEFAULT_SECONDS = 0
    DEFAULT_MINUTES = 0
    DEFAULT_HOURS = 0
    DEFAULT_COUNT = None
    DEFAULT_RECONNECT = True

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
        self._seconds = self.DEFAULT_SECONDS if seconds is None else seconds
        self._minutes = self.DEFAULT_MINUTES if minutes is None else minutes
        self._hours = self.DEFAULT_HOURS if hours is None else hours
        self._count = self.DEFAULT_COUNT if count is None else count
        self._reconnect = self.DEFAULT_RECONNECT if reconnect is None else reconnect
        self._loop_count = 0
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
        self._task_loop.error(self._on_run_error)

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

    async def on_start(self):
        pass

    async def _on_run(self):
        if self._startup_kill:
            return

        self._is_idling = False
        self._idling_since_ts = None

        await self.on_run()
        if (
            self._seconds or self._minutes or self._hours
        ):  # There is a task loop interval set
            self._is_idling = True
            self._idling_since_ts = time.time()

        self._loop_count += 1

    async def on_run(self):
        """DO NOT CALL THIS METHOD MANUALLY, EXCEPT WHEN USING `super()` WITHIN
        OVERLOADED VERSIONS OF THIS METHOD TO ACCESS A SUPERCLASS METHOD.

        The code to run at the set interval.
        This method must be overloaded in subclasses.

        Raises:
            NotImplementedError: This method must be overloaded in subclasses.
        """
        raise NotImplementedError()

    async def on_stop(self, reason, by_force):
        pass


class EventJob(Job):
    """A job class for jobs that run in reaction to specific events
    passed to them by their `JobManager` object.
    Subclasses are expected to overload the `on_run(self, event)` method.
    `on_start()` and `on_stop()` and `on_run_error(self, exc)` can
    optionally be overloaded.
    One can also override the class variables `DEFAULT_COUNT` and `DEFAULT_RECONNECT`
    in subclasses. They are derived from the keyword arguments of the
    `discord.ext.tasks.loop` decorator. Unlike `IntervalJob` class instances,
    the instances of this class depend on their `JobManager` to trigger
    the execution of their `.on_run()` method, and will stop running if
    all ClientEvent objects passed to them have been processed.

    Attributes:
        EVENT_TYPES:
            A tuple denoting the set of `BaseEvent` classes whose instances
            should be recieved after their corresponding event is registered
            by the `JobManager` of an instance of this class. By default,
            all instances of `BaseEvent` will be propagated.
    """

    EVENT_TYPES: tuple = (events.BaseEvent,)
    DEFAULT_COUNT = None
    DEFAULT_RECONNECT = True
    DEFAULT_MAX_IDLING_DURATION = datetime.timedelta()

    DEFAULT_BLOCK_QUEUE_ON_STOP = False
    DEFAULT_START_ON_DISPATCH = True
    DEFAULT_BLOCK_QUEUE_WHILE_STOPPED = False
    DEFAULT_CLEAR_QUEUE_AT_STARTUP = False

    __slots__ = (
        "_event_queue",
        "_last_event",
        "_max_idling_duration",
        "_block_queue_on_stop",
        "_start_on_dispatch",
        "_block_queue_while_stopped",
        "_clear_queue_at_startup",
        "_allow_dispatch",
        "_stopping_by_empty_queue",
        "_stopping_by_idling_timeout",
    )

    def __init_subclass__(cls, permission_level=None):
        if not cls.EVENT_TYPES:
            raise TypeError("the 'EVENT_TYPES' class attribute must not be empty")

        elif not isinstance(cls.EVENT_TYPES, (list, tuple)):
            raise TypeError(
                "the 'EVENT_TYPES' class attribute must be of type 'list'/'tuple' and"
                " must contain one or more subclasses of `BaseEvent`"
            )
        elif not all(issubclass(et, events.BaseEvent) for et in cls.EVENT_TYPES):
            raise ValueError(
                "the 'EVENT_TYPES' class attribute"
                " must contain one or more subclasses of `BaseEvent`"
            )

        Job.__init_subclass__.__func__(cls, permission_level=permission_level)

    def __init__(
        self,
        count: Optional[int] = None,
        reconnect: Optional[bool] = None,
        max_idling_duration: Optional[datetime.timedelta] = None,
        block_queue_on_stop: Optional[bool] = None,
        block_queue_while_stopped: Optional[bool] = None,
        clear_queue_at_startup: Optional[bool] = None,
        start_on_dispatch: Optional[bool] = None,
    ):
        super().__init__()
        self._event_queue = deque()
        self._last_event = None
        self._count = self.DEFAULT_COUNT if count is None else count
        self._loop_count = 0
        self._reconnect = self.DEFAULT_RECONNECT if reconnect is None else reconnect
        self._max_idling_duration = (
            self.DEFAULT_MAX_IDLING_DURATION
            if max_idling_duration is None
            else max_idling_duration
        )

        self._block_queue_on_stop = (
            self.DEFAULT_BLOCK_QUEUE_ON_STOP
            if block_queue_on_stop is None
            else block_queue_on_stop
        )
        self._start_on_dispatch = (
            self.DEFAULT_START_ON_DISPATCH
            if start_on_dispatch is None
            else start_on_dispatch
        )
        self._block_queue_while_stopped = (
            self.DEFAULT_BLOCK_QUEUE_WHILE_STOPPED
            if block_queue_while_stopped is None
            else block_queue_while_stopped
        )
        self._clear_queue_at_startup = (
            self.DEFAULT_CLEAR_QUEUE_AT_STARTUP
            if clear_queue_at_startup is None
            else clear_queue_at_startup
        )

        if self._block_queue_while_stopped or self._clear_queue_at_startup:
            self._start_on_dispatch = False

        self._allow_dispatch = True

        self._stopping_by_empty_queue = False
        self._stopping_by_idling_timeout = False

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
        self._task_loop.error(self._on_run_error)

    def _add_event(self, event: events.BaseEvent):
        task_is_running = self._task_loop.is_running()
        if (
            not self._allow_dispatch
            or (self._block_queue_on_stop and self._is_being_stopped)
            or (self._block_queue_while_stopped and not task_is_running)
        ):
            return

        self._event_queue.append(event)
        if self._start_on_dispatch and not task_is_running:
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
            BaseEvent: The event object.
        """
        return self._last_event

    def loop_count(self):
        """The current amount of `on_run()` calls completed by this job object."""
        return self._loop_count

    async def _on_start(self):
        if self._clear_queue_at_startup:
            self._event_queue.clear()

        await super()._on_start()

    async def on_start(self):
        pass

    async def _on_run(self):
        if self._startup_kill:
            return

        if not self._event_queue:
            if not self._max_idling_duration:
                if self._max_idling_duration is None:
                    if not self._is_idling:
                        self._is_idling = True
                        self._idling_since_ts = time.time()
                    else:
                        return
                else:  # self._max_idling_duration is a zero timedelta
                    self._stopping_by_empty_queue = True
                    self.STOP()
                    return

            elif not self._is_idling:
                self._is_idling = True
                self._idling_since_ts = time.time()

            if (
                self._is_idling
                and (time.time() - self._idling_since_ts) > self._max_idling_duration
            ):
                self._stopping_by_idling_timeout = True
                self.STOP()
                return
            else:
                return

        elif self._loop_count == self._count:
            self.STOP()
            return

        self._is_idling = False
        self._idling_since_ts = None

        self._stopping_by_idling_timeout = False

        event = self._event_queue.popleft()
        await self.on_run(event=event)
        self._last_event = event

        self._loop_count += 1

    async def on_run(self, event: events.BaseEvent):
        """The code to run whenever an event is recieved.
        This method must be overloaded in subclasses.

        Raises:
            NotImplementedError: This method must be overloaded in subclasses.
        """
        raise NotImplementedError()

    async def _on_stop(self):
        try:
            await super()._on_stop()
        finally:  # reset some attributes in case an exception is raised
            self._loop_count = 0
            self._stopping_by_idling_timeout = False

    async def on_stop(self, reason, by_force):
        pass

    def get_queue_size(self):
        """Get the count of events stored in the queue.

        Returns:
            int: The queue sizee.
        """
        return len(self._event_queue)

    def clear_queue(self):
        """Clear the current event queue."""
        self._event_queue.clear()

    @contextmanager
    def queue_blocker(self):
        """A method to be used as a context manager for
        temporarily blocking the event queue of this event job
        while running an operation, thereby disabling event dispatch to it.
        """
        try:
            self._allow_dispatch = False
            yield
        finally:
            self._allow_dispatch = True

    def queue_is_blocked(self):
        """Whether event dispatching to this event job's event queue
        is disabled and its event queue is blocked.

        Returns:
            bool: True/False
        """
        return not self._allow_dispatch

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
                reason = STOP_REASONS.INTERNAL_ERROR
            elif (
                not self._max_idling_duration
                and self._max_idling_duration is not None
                and self._stopping_by_empty_queue
            ):
                reason = STOP_REASONS.INTERNAL_EMPTY_QUEUE
            elif self._stopping_by_idling_timeout:
                reason = STOP_REASONS.INTERNAL_IDLING_TIMEOUT
            elif self._loop_count == self._count:
                reason = STOP_REASONS.INTERNAL_COUNT_LIMIT
            elif self._stopping_by_self:
                if self._is_being_restarted:
                    reason = STOP_REASONS.INTERNAL_RESTART
                elif self._is_being_completed:
                    reason = STOP_REASONS.INTERNAL_COMPLETION
                elif self._is_being_killed:
                    reason = STOP_REASONS.INTERNAL_KILLING
                else:
                    reason = STOP_REASONS.INTERNAL
            elif not self._stopping_by_self:
                if self._is_being_restarted:
                    reason = STOP_REASONS.EXTERNAL_RESTART
                elif self._is_being_killed:
                    reason = STOP_REASONS.EXTERNAL_KILLING
                else:
                    reason = STOP_REASONS.EXTERNAL

            output = reason
        return output


class ClientEventJob(EventJob):
    """A job class for jobs that run in reaction to specific client events
    (Discord API events) passed to them by their `JobManager` object.
    Subclasses are expected to overload the `on_run(self, event)` method.
    `on_start()` and `on_stop()` and `on_run_error(self, exc)` can
    optionally be overloaded. One can also override the class variables
    `DEFAULT_COUNT` and `DEFAULT_RECONNECT` in subclasses.
    They are derived from the keyword arguments of the `discord.ext.tasks.loop`
    decorator. Unlike `IntervalJob` class instances, the instances of this
    class depend on their `JobManager` to trigger the execution of
    their `.on_run()` method, and will stop running if all ClientEvent
    objects passed to them have been processed.

    Attributes:
        EVENT_TYPES:
            A tuple denoting the set of `ClientEvent` classes whose instances
            should be recieved after their corresponding event is registered
            by the `JobManager` of an instance of this class. By default,
            all instances of `ClientEvent` will be propagated.
    """

    EVENT_TYPES: tuple = (events.ClientEvent,)


class SingletonJobBase(Job):
    """A special job base class whose instances can only exist
    one at a time within a `JobManager`. Must be used with
    multiple inheritance, not on its own.
    """

    pass


class JobManagerJob(SingletonJobBase, IntervalJob):
    """A singleton job that represents the job manager. Its very high permission
    level and internal protections prevents it from being instantiated
    or modified by other jobs.
    """

    def __init__(self):
        super().__init__()

    async def on_run(self):
        pass


_JOB_MANAGER_JOB_CLS = JobManagerJob

Job.__init_subclass__.__func__(JobManagerJob, permission_level=PERMISSION_LEVELS.SYSTEM)


class SingleRunJob(IntervalJob):
    """A subclass of `IntervalJob` whose subclasses's
    job objects will only run once and then complete themselves.
    automatically. For more control, use `IntervalJob` directly.
    """

    DEFAULT_COUNT = 1

    async def on_stop(self, reason, by_force):
        self.COMPLETE()


class RegisterDelayedJob(SingleRunJob):
    """A subclass of `SingleRunJob` that
    adds a given set of job proxies to its `JobManager`
    only after a given period of time in seconds.

    Attributes:
        delay (float):
            The delay for the input jobs in seconds.
    """

    def __init__(self, delay: float, *job_proxies: JobProxy, **kwargs):
        """Create a new RegisterDelayedJob instance.

        Args:
            delay (float):
                The delay for the input jobs in seconds.
            *jobs Union[ClientEventJob, IntervalJob]:
                The jobs to be delayed.
        """
        super().__init__(**kwargs)
        self.data.delay = delay
        self.data.jobs = job_proxies

    async def on_start(self):
        await asyncio.sleep(self.data.delay)

    async def on_run(self):
        for job_proxy in self.data.jobs:
            await self.manager.register_job(job_proxy)

    async def on_stop(self, reason, by_force):
        self.COMPLETE()


from .manager import JobManagerProxy
