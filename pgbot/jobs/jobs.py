"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file implements the base classes for job objects, which are a core part of the
asynchronous task execution system.
"""

from abc import ABC
import abc
import asyncio
import functools
from optparse import Option
from aiohttp import ClientError
from collections import ChainMap, deque
from contextlib import contextmanager
import datetime
from enum import Enum, IntEnum, auto
import itertools
import inspect
import re
import sys
import time
from types import FunctionType, SimpleNamespace
from typing import Any, Awaitable, Callable, Coroutine, Optional, Type, TypeVar, Union

import discord
from discord.ext import tasks
from matplotlib import collections

from pgbot.utils import utils
from pgbot import common, events
from pgbot.common import STANDARD_JOB_IDENTIFIERS, UNSET, _UnsetType

_JOB_CLASS_MAP = {}
# A dictionary of all Job subclasses that were created. Do not access outside of this module.

_JOB_CLASS_SCHEDULING_MAP = {}


def get_job_class_from_runtime_identifier(
    class_identifier: str, default: Any = UNSET, /, closest_match: bool = False
) -> "JobBase":

    name, timestamp_str = class_identifier.split("-")

    if name in _JOB_CLASS_MAP:
        if timestamp_str in _JOB_CLASS_MAP[name]:
            return _JOB_CLASS_MAP[name][timestamp_str]["class"]
        elif closest_match:
            for ts_str in _JOB_CLASS_MAP[name]:
                return _JOB_CLASS_MAP[name][ts_str]["class"]

    if default is UNSET:
        raise LookupError(
            f"cannot find job class with an identifier of "
            f"'{class_identifier}' in the job class registry"
        )
    return default


def get_job_class_from_scheduling_identifier(
    class_scheduling_identifier: str,
    default: Any = UNSET,
    /,
) -> Union["JobBase", Any]:

    if class_scheduling_identifier in _JOB_CLASS_SCHEDULING_MAP:
        return _JOB_CLASS_SCHEDULING_MAP[class_scheduling_identifier]

    if default is UNSET:
        raise KeyError(
            f"cannot find job class with a scheduling identifier of "
            f"'{class_scheduling_identifier}'in the job class registry for "
            "schedulable classes"
        )

    return default


def get_job_class_scheduling_identifier(
    cls: Type["JobBase"],
    default: Any = UNSET,
    /,
) -> Union[str, Any]:
    """Get a job class by its scheduling identifier string. This is the safe way
    of looking up job class scheduling identifiers.

    Args:
        cls (Type[JobBase]): The job class whose identifier should be fetched.
        default (Any): A default value which will be returned if this function
          fails to produce the desired output. If omitted, exceptions will be
          raised.

    Raises:
        TypeError: 'cls' does not inherit from a job base class.
        LookupError: The given job class does not exist in the job class registry.
          This exception should not occur if job classes inherit their base classes
          correctly.

    Returns:
        str: The string identifier.
    """

    if not issubclass(cls, JobBase):
        if default is UNSET:
            raise TypeError("argument 'cls' must be a subclass of a job base class")
        return default

    try:
        class_scheduling_identifier = cls._SCHEDULING_IDENTIFIER
    except AttributeError:
        if default is UNSET:
            raise TypeError(
                "argument 'cls' must be a subclass of a job base class"
            ) from None
        return default
    else:
        if class_scheduling_identifier is None:
            if default is UNSET:
                raise TypeError(f"job class '{cls.__qualname__}' is not schedulable")

    if (
        class_scheduling_identifier in _JOB_CLASS_SCHEDULING_MAP
        and _JOB_CLASS_SCHEDULING_MAP[class_scheduling_identifier] is cls
    ):
        return class_scheduling_identifier

    if default is UNSET:
        raise LookupError(
            f"The given job class does not exist in the job class registry for "
            "schedulable classes"
        )

    return default


def get_job_class_runtime_identifier(
    cls: Type["JobBase"],
    default: Any = UNSET,
    /,
) -> Union[str, Any]:
    """Get a job class by its runtime identifier string. This is the safe way
    of looking up job class runtime identifiers.

    Args:
        cls (Type[JobBase]): The job class whose identifier should be fetched.
        default (Any): A default value which will be returned if this function
          fails to produce the desired output. If omitted, exceptions will be
          raised.

    Raises:
        TypeError: 'cls' does not inherit from a job base class.
        LookupError: The given job class does not exist in the job class registry.
          This exception should not occur if job classes inherit their base classes
          correctly.

    Returns:
        str: The string identifier.
    """

    if not issubclass(cls, JobBase):
        if default is UNSET:
            raise TypeError("argument 'cls' must be a subclass of a job base class")
        return default

    try:
        class_identifier = cls._IDENTIFIER
    except AttributeError:
        if default is UNSET:
            raise TypeError(
                "argument 'cls' must be a subclass of a job base class"
            ) from None
        return default

    try:
        name, timestamp_str = class_identifier.split("-")
    except (ValueError, AttributeError):
        if default is UNSET:
            raise ValueError(
                "invalid identifier found in the given job class"
            ) from None
        return default

    if name in _JOB_CLASS_MAP:
        if timestamp_str in _JOB_CLASS_MAP[name]:
            if _JOB_CLASS_MAP[name][timestamp_str]["class"] is cls:
                return class_identifier
            else:
                if default is UNSET:
                    raise ValueError(
                        f"The given job class has the incorrect identifier"
                    )
        else:
            if default is UNSET:
                ValueError(
                    f"The given job class is registered under "
                    "a different identifier in the job class registry"
                )

    if default is UNSET:
        raise LookupError(
            f"The given job class does not exist in the job class registry"
        )

    return default


def get_job_class_permission_level(
    cls: Type["JobBase"],
    default: Any = UNSET,
    /,
) -> "JobPermissionLevels":

    if not issubclass(cls, JobBase):
        if default is UNSET:
            raise TypeError("argument 'cls' must be a subclass of a job base class")
        return default

    try:
        class_identifier = cls._IDENTIFIER
    except AttributeError:
        if default is UNSET:
            raise TypeError(
                "argument 'cls' must be a subclass of a job base class"
            ) from None
        return default

    try:
        name, timestamp_str = class_identifier.split("-")
    except (ValueError, AttributeError):
        if default is UNSET:
            raise ValueError(
                "invalid identifier found in the given job class"
            ) from None
        return default

    if name in _JOB_CLASS_MAP:
        if timestamp_str in _JOB_CLASS_MAP[name]:
            if _JOB_CLASS_MAP[name][timestamp_str]["class"] is cls:
                return _JOB_CLASS_MAP[name][timestamp_str]["permission_level"]
            else:
                if default is UNSET:
                    raise ValueError(
                        f"The given job class has the incorrect identifier"
                    )
        else:
            if default is UNSET:
                ValueError(
                    f"The given job class is registered under "
                    "a different identifier in the job class registry"
                )

    if default is UNSET:
        raise LookupError(
            f"The given job class does not exist in the job class registry"
        )

    return default


DEFAULT_JOB_EXCEPTION_WHITELIST = (
    OSError,
    discord.GatewayNotFound,
    discord.ConnectionClosed,
    ClientError,
    asyncio.TimeoutError,
)
"""The default exceptions handled in discord.ext.tasks.Loop
upon reconnecting."""


class JobStatus(Enum):
    """An enum of constants representing the main statuses a job
    object can be in.
    """

    FRESH = auto()
    """This job object is freshly created and unmodified.
    """
    INITIALIZED = auto()

    STARTING = auto()
    RUNNING = auto()
    AWAITING = auto()
    IDLING = auto()
    COMPLETING = auto()
    BEING_KILLED = auto()
    RESTARTING = auto()
    STOPPING = auto()

    STOPPED = auto()
    KILLED = auto()
    COMPLETED = auto()


class JobVerbs(Enum):
    """An enum of constants representing the operations that job
    objects can perform on each other.
    """

    CREATE = auto()
    """The act of creating/instantiating a job object.
    """
    INITIALIZE = auto()
    """The act of initializing a job object.
    """
    REGISTER = auto()
    """The act of registering a job object.
    """
    SCHEDULE = auto()
    """The act of scheduling a job type for instantiation in the future.
    """
    GUARD = auto()
    """The act of placing a modification guard on a job object.
    """

    FIND = auto()
    """The act of finding job objects based on specific parameters.
    """

    CUSTOM_EVENT_DISPATCH = auto()
    """The act of dispatching only custom events to job objects.
    """

    EVENT_DISPATCH = auto()
    """The act of dispatching any type of event to job objects.
    """

    START = auto()
    """The act of starting a job object.
    """
    STOP = auto()
    """The act of stopping a job object.
    """
    RESTART = auto()
    """The act of restarting a job object.
    """

    UNSCHEDULE = auto()
    """The act of unscheduling a specific job schedule operation.
    """
    UNGUARD = auto()
    """The act of removing a modification guard on a job object.
    """

    KILL = auto()
    """The act of killing a job object.
    """


_JOB_VERBS_SIMP_PAST = dict(
    CREATE="CREATED",
    INITIALIZE="INITIALIZED",
    REGISTER="REGISTERED",
    SCHEDULE="SCHEDULED",
    GUARD="GUARDED",
    FIND="FOUND",
    CUSTOM_EVENT_DISPATCH="CUSTOM-EVENT-DISPATCHED",
    EVENT_DISPATCH="EVENT-DISPATCHED",
    START="STARTED",
    STOP="STOPPED",
    RESTART="RESTARTED",
    UNSCHEDULE="UNSCHEDULED",
    UNGUARD="UNGUARDED",
    KILL="KILLED",
)

_JOB_VERBS_PRES_CONT = dict(
    CREATE="CREATING",
    INITIALIZE="INITIALIZING",
    REGISTER="REGISTERING",
    SCHEDULE="SCHEDULING",
    GUARD="GUARDING",
    FIND="FINDING",
    CUSTOM_EVENT_DISPATCH="CUSTOM-EVENT-DISPATCHING",
    EVENT_DISPATCH="EVENT-DISPATCHING",
    START="STARTING",
    STOP="STOPPING",
    RESTART="RESTARTING",
    UNSCHEDULE="UNSCHEDULING",
    UNGUARD="UNGUARDING",
    KILL="KILLING",
)


class JobStopReasons:
    """A class namespace of enums representing the different reasons job
    objects might stop running.
    """

    class Internal(Enum):
        """An enum of constants representing the different internal reasons job
        objects might stop running.
        """

        UNSPECIFIC = auto()
        """Job is stopping due to an unspecific internal reason.
        """
        ERROR = auto()
        """Job is stopping due to an internal error.
        """
        RESTART = auto()
        """Job is stopping due to an internal restart.
        """

        EXECUTION_COUNT_LIMIT = auto()
        """Job is stopping due to hitting its maximimum execution
        count before stopping.
        """

        COMPLETION = auto()
        """Job is stopping for finishing all execution, it has completed.
        """

        KILLING = auto()
        """Job is stopping due to killing itself internally.
        """

        IDLING_TIMEOUT = auto()
        """Job is stopping after staying idle beyond a specified timeout.
        """

        EMPTY_QUEUE = auto()
        """Job is stopping due to an empty internal queue of recieved events.
        """

    class External(Enum):
        """An enum of constants representing the different external reasons job
        objects might stop running.
        """

        UNKNOWN = auto()
        """Job is stopping due to an unknown external reason.
        """

        RESTART = auto()
        """Job is stopping due to an external restart.
        """

        KILLING = auto()
        """Job is stopping due to being killed externally.
        """


class JobPermissionLevels(IntEnum):
    """An enum of constants representing the permission levels
    applicable to job objects.
    """

    LOWEST = 1
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

    MEDIUM = 1 << 2
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
        - Can dispatch custom events to other jobs (`CustomEvent` subclasses).
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
        - Can dispatch custom events to other jobs (`CustomEvent` subclasses).
        - Can dispatch any event to other jobs (`BaseEvent` subclasses).
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
        - Can dispatch custom events to other jobs (`CustomEvent` subclasses).
        - Can dispatch any event to other jobs (`BaseEvent` subclasses).
        - Can instantiate, register, start and schedule jobs of the same permission level.
        - Can stop, restart, kill or unschedule any job of the same permission level.
        - Can guard or unguard any job.
    """


class JobError(Exception):
    """Generic job object error."""

    pass


class JobPermissionError(JobError):
    """Job object permisssion error."""

    pass


class JobStateError(JobError):
    """An invalid job object state is preventing an operation."""

    pass


class JobInitializationError(JobError):
    """Initialization of a job object failed, or is required."""

    pass


class JobWarning(Warning):
    """Base class for job related warnings."""

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
        return self.__class__(**self.__dict__)

    def to_dict(self) -> dict:
        return dict(self.__dict__)

    @staticmethod
    def from_dict(d):
        return JobNamespace(**d)

    __copy__ = copy


class _SystemLevelMixinJobBase(ABC):
    pass


class _SingletonMixinJobBase(ABC):
    """An abstract base class for marking job classes as singletons,
    which can only be scheduled one at a time in a job manager.
    """

    pass


def singletonjob(cls: Type["JobBase"]) -> Type["JobBase"]:
    """A class decorator for marking job classes as singletons,
    meaning that their instances can only be scheduled one at a time in a job manager.
    """
    if issubclass(cls, JobBase):
        _SingletonMixinJobBase.register(cls)
    return cls


def _sysjob(cls: Type["JobBase"]) -> Type["JobBase"]:
    if issubclass(cls, JobBase):
        _SystemLevelMixinJobBase.register(cls)

        name, created_timestamp_ns_str = cls._IDENTIFIER.split("-")

        if name not in _JOB_CLASS_MAP:
            _JOB_CLASS_MAP[name] = {}

        _JOB_CLASS_MAP[name][created_timestamp_ns_str] = {
            "class": cls,
            "permission_level": JobPermissionLevels.SYSTEM,
        }

        cls._PERMISSION_LEVEL = JobPermissionLevels.SYSTEM

    return cls


def publicjobmethod(
    func: Optional[Callable[[Any], Any]] = None,
    is_async: Optional[bool] = None,
    disabled: bool = False,
) -> Callable[[Any], Any]:
    """A special decorator to expose a method as public to other job objects.
    Can be used as a decorator function with or without extra arguments.

    Args:
        func (Optional[Callable[[Any], Any]]): The function to mark as a public method.
          disabled (bool): Whether to mark this public job method as disabled.
          Defaults to False.
        is_async (Optional[bool]): An indicator for whether the returned value of the
          public method should be awaited upon being called, either because of it being a
          coroutine function or it returning an awaitable object. If set to `None`, it
          will be checked for whether it is a coroutine function.
          that the function will be checked.

    """

    def inner_deco(func: Callable[[Any], Any]):
        if isinstance(func, FunctionType):
            func.__public = True
            func.__disabled = bool(disabled)
            func.__is_async = (
                is_async
                if isinstance(is_async, bool)
                else inspect.iscoroutinefunction(func)
            )
            return func

        raise TypeError("first decorator function argument must be a function")

    if func is not None:
        return inner_deco(func)

    return inner_deco


class CustomLoop(tasks.Loop):
    """A small subclass of `discord.ext.tasks.Loop`
    for getting more control over the `Task` cancelling process.
    """

    def cancel(self):
        """Cancels the internal task, if it is running."""
        if self._can_be_cancelled():
            self._task.cancel(msg="CANCEL_BY_TASK_LOOP")

    def restart(self, *args, **kwargs):
        r"""A convenience method to restart the internal task.

        .. note::

            Due to the way this function works, the task is not
            returned like :meth:`start`.

        Parameters
        ------------
        \*args
            The arguments to to use.
        \*\*kwargs
            The keyword arguments to use.
        """

        def restart_when_over(fut, *, args=args, kwargs=kwargs):
            self._task.remove_done_callback(restart_when_over)
            self.start(*args, **kwargs)

        if self._can_be_cancelled():
            self._task.add_done_callback(restart_when_over)
            self._task.cancel(msg="CANCEL_BY_TASK_LOOP")


class JobBase:
    """The base class of all job objects,
    which implements base functionality for its subclasses."""

    __slots__ = (
        "_interval_secs",
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
        "_output_fields",
        "_output_queues",
        "_output_queue_proxies",
        "_output_field_futures",
        "_output_queue_futures",
        "_unguard_futures",
        "_done_futures",
        "_task_loop",
        "_proxy",
        "_guarded_job_proxies_dict",
        "_guardian",
        "_is_being_guarded",
        "_on_start_exception",
        "_on_run_exception",
        "_on_stop_exception",
        "_initialized",
        "_is_initializing",
        "_is_starting",
        "_completed",
        "_told_to_complete",
        "_killed",
        "_told_to_be_killed",
        "_startup_kill",
        "_skip_on_run",
        "_told_to_stop",
        "_stop_by_self",
        "_stop_by_force",
        "_is_stopping",
        "_last_stopping_reason",
        "_is_awaiting",
        "_told_to_restart",
        "_stopped",
        "_is_idling",
        "_initialized_since_ts",
        "_alive_since_ts",
        "_awaiting_since_ts",
        "_idling_since_ts",
        "_running_since_ts",
        "_stopped_since_ts",
    )

    _CREATED_AT = datetime.datetime.now(datetime.timezone.utc)
    _IDENTIFIER = f"JobBase-{int(_CREATED_AT.timestamp()*1_000_000_000)}"
    _SCHEDULING_IDENTIFIER: Optional[str] = None
    _PERMISSION_LEVEL: JobPermissionLevels = JobPermissionLevels.MEDIUM

    OutputFields: Optional[Union[Any, "groupings.OutputNameRecord"]] = None
    OutputQueues: Optional[Union[Any, "groupings.OutputNameRecord"]] = None
    PublicMethods: Optional[Union[Any, "groupings.NameRecord"]] = None

    PUBLIC_METHODS_MAP: Optional[dict[str, Callable[..., Any]]] = None
    PUBLIC_METHODS_CHAINMAP: Optional[ChainMap[str, Callable[..., Any]]] = None

    NAMESPACE_CLASS = JobNamespace

    def __init_subclass__(
        cls,
        scheduling_identifier: Optional[str] = None,
        permission_level: Optional[JobPermissionLevels] = None,
    ):

        if getattr(cls, f"{cls.__qualname__}_INIT", False):
            raise RuntimeError("This job class was already initialized.")

        cls._CREATED_AT = datetime.datetime.now(datetime.timezone.utc)

        is_system_job = issubclass(cls, _SystemLevelMixinJobBase)

        if is_system_job:
            permission_level = JobPermissionLevels.SYSTEM

        name = cls.__qualname__
        created_timestamp_ns_str = f"{int(cls._CREATED_AT.timestamp()*1_000_000_000)}"

        if permission_level is not None:
            if isinstance(permission_level, JobPermissionLevels):
                if (
                    JobPermissionLevels.LOWEST
                    <= permission_level
                    <= JobPermissionLevels.HIGHEST
                ) or (is_system_job and permission_level is JobPermissionLevels.SYSTEM):
                    cls._PERMISSION_LEVEL = permission_level
                else:
                    raise ValueError(
                        "argument 'permission_level' must be a usable permission "
                        "level from the 'JobPermissionLevels' enum"
                    )
            else:
                raise TypeError(
                    "argument 'permission_level' must be a usable permission "
                    "level from the 'JobPermissionLevels' enum"
                )
        else:
            permission_level = JobBase._PERMISSION_LEVEL

        if scheduling_identifier is not None:
            if not isinstance(scheduling_identifier, str):
                raise TypeError(
                    "argument 'scheduling_identifier' must be a string unique to this job class"
                )

            elif scheduling_identifier in _JOB_CLASS_SCHEDULING_MAP:
                raise ValueError(
                    f"the given scheduling identifier for class '{cls.__qualname__}' "
                    "must be unique to it and cannot be used by other job classes"
                )

            cls._SCHEDULING_IDENTIFIER = scheduling_identifier

            _JOB_CLASS_SCHEDULING_MAP[scheduling_identifier] = cls

        cls._IDENTIFIER = f"{name}-{created_timestamp_ns_str}"

        if name not in _JOB_CLASS_MAP:
            _JOB_CLASS_MAP[name] = {}

        _JOB_CLASS_MAP[name][created_timestamp_ns_str] = {
            "class": cls,
            "permission_level": permission_level,
        }

        if isinstance(cls.OutputFields, type):
            if not issubclass(cls.OutputFields, groupings.OutputNameRecord):
                if cls.OutputFields.__base__ is not object:
                    raise TypeError(
                        "the 'OutputFields' variable must be a subclass of 'OutputNameRecord' "
                        "or an immediate subclass of object that acts as a placeholder"
                    )

                cls.OutputFields = type(
                    "OutputFields",
                    (groupings.OutputNameRecord,),
                    dict(**cls.OutputFields.__dict__),
                )

        if isinstance(cls.OutputQueues, type):
            if not issubclass(cls.OutputQueues, groupings.OutputNameRecord):
                if cls.OutputQueues.__base__ is not object:
                    raise TypeError(
                        "the 'OutputQueues' variable must be a subclass of 'OutputNameRecord' "
                        "or an immediate subclass of object that acts as a placeholder"
                    )

                cls.OutputQueues = type(
                    "OutputQueues",
                    (groupings.OutputNameRecord,),
                    dict(**cls.OutputQueues.__dict__),
                )

        if isinstance(cls.PublicMethods, type):
            if not issubclass(cls.PublicMethods, groupings.NameRecord):
                if cls.PublicMethods.__base__ is not object:
                    raise TypeError(
                        "the 'PublicMethods' variable must be a subclass of 'NameRecord' "
                        "or an immediate subclass of object that acts as a placeholder"
                    )

                bases = (
                    groupings.NameRecord,
                    *(
                        utils.class_getattr_unique(
                            cls,
                            "PublicMethods",
                            filter_func=lambda v: isinstance(v, groupings.NameRecord),
                            check_dicts_only=True,
                        ),
                    ),
                )
                cls.PublicMethods = type(
                    "PublicMethods", bases, dict(**cls.PublicMethods.__dict__)
                )
            elif issubclass(cls.PublicMethods, groupings.OutputNameRecord):
                raise TypeError(
                    "the 'PublicMethods' variable must not be a subclass of "
                    "'OutputNameRecord', but a subclass of 'NameRecord' "
                    "or an immediate subclass of object that acts as a placeholder"
                )

        public_methods_map = {}
        for obj in cls.__dict__.values():
            if isinstance(obj, FunctionType) and "__public" in obj.__dict__:
                public_methods_map[obj.__name__] = obj

        cls.PUBLIC_METHODS_MAP = public_methods_map or None

        mro_public_methods = utils.class_getattr_unique(
            cls,
            "PUBLIC_METHODS_MAP",
            filter_func=lambda v: v and isinstance(v, dict),
            check_dicts_only=True,
        )

        if mro_public_methods:
            cls.PUBLIC_METHODS_CHAINMAP = ChainMap(
                *mro_public_methods,
            )

        setattr(cls, f"{cls.__qualname__}_INIT", True)

    def __init__(self):
        self._interval_secs = 0
        self._count = None
        self._reconnect = False

        self._loop_count = 0

        self._manager: Optional["proxies.JobManagerProxy"] = None
        self._creator: Optional["proxies.JobProxy"] = None
        self._created_at_ts = time.time()
        self._registered_at_ts = None
        self._completed_at_ts = None
        self._killed_at_ts = None
        self._identifier = f"{id(self)}-{int(self._created_at_ts*1_000_000_000)}"
        self._schedule_identifier = None
        self._data = self.NAMESPACE_CLASS()

        self._done_futures: list[asyncio.Future] = []
        self._output_field_futures = None

        self._output_fields = None
        self._output_queue_proxies: Optional[list["proxies.JobOutputQueueProxy"]] = None

        if self.OutputFields is not None:
            self._output_field_futures = {}
            self._output_fields = {}

        if self.OutputQueues is not None:
            self._output_queue_proxies = []
            self._output_queue_futures = {}
            self._output_queues = {}

        self._task_loop: Optional[CustomLoop] = None

        self._proxy = proxies.JobProxy(self)

        self._unguard_futures: Optional[list[asyncio.Future]] = None
        self._guardian: Optional[JobBase] = None
        self._guarded_job_proxies_dict: Optional[dict[str, "proxies.JobProxy"]] = None
        # will be assigned by job manager

        self._is_being_guarded = False

        self._on_start_exception = None
        self._on_run_exception = None
        self._on_stop_exception = None

        self._is_awaiting = False
        self._is_initializing = False
        self._initialized = False
        self._is_starting = False
        self._completed = False
        self._told_to_complete = False

        self._killed = False
        self._told_to_be_killed = False
        self._startup_kill = False

        self._told_to_stop = False
        self._stop_by_self = False
        self._stop_by_force = False
        self._skip_on_run = False
        self._is_stopping = False
        self._stopped = False
        self._last_stopping_reason: Optional[
            Union[JobStopReasons.Internal, JobStopReasons.External]
        ] = None

        self._told_to_restart = False

        self._is_idling = False

        self._initialized_since_ts = None
        self._alive_since_ts: Optional[float] = None
        self._awaiting_since_ts: Optional[float] = None
        self._idling_since_ts: Optional[float] = None
        self._running_since_ts: Optional[float] = None
        self._stopped_since_ts: Optional[float] = None

    @classmethod
    def schedulable(cls: Type["JobBase"]) -> bool:
        """Whether this job class is schedulable, meaning that
        it has a scheduling identifier.

        Args:
            cls (Type[JobBase]): The job class.

        Returns:
            bool: True/False
        """
        return bool(get_job_class_scheduling_identifier(cls, False))

    @property
    def identifier(self) -> str:
        return self._identifier

    @property
    def created_at(self) -> Optional[datetime.datetime]:
        if self._created_at_ts:
            return datetime.datetime.fromtimestamp(
                self._created_at_ts, tz=datetime.timezone.utc
            )

    @property
    def registered_at(self) -> Optional[datetime.datetime]:
        if self._registered_at_ts:
            return datetime.datetime.fromtimestamp(
                self._registered_at_ts, tz=datetime.timezone.utc
            )

    @property
    def permission_level(self) -> JobPermissionLevels:
        return self._PERMISSION_LEVEL

    @property
    def data(self):
        """The `JobNamespace` instance bound to this job object for storage."""
        return self._data

    @property
    def manager(self) -> "proxies.JobManagerProxy":
        """The `JobManagerProxy` object bound to this job object."""
        return self._manager

    @property
    def creator(self) -> "proxies.JobProxy":
        """The `JobProxy` of the creator of this job object."""
        return self._creator

    @property
    def guardian(self) -> "proxies.JobProxy":
        """The `JobProxy` of the current guardian of this job object."""
        return self._guardian

    @property
    def proxy(self) -> "proxies.JobProxy":
        """The `JobProxy` object bound to this job object."""
        return self._proxy

    @property
    def schedule_identifier(self) -> Optional[str]:
        """The identfier of the scheduling operation that instantiated
        this job object, if that was the case.
        """
        return self._schedule_identifier

    async def _on_init(self):
        try:
            self._is_initializing = True
            await self.on_init()
        except Exception:
            self._is_initializing = False
            raise
        else:
            self._is_initializing = False
            self._initialized = True
            self._initialized_since_ts = time.time()

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
            self._told_to_stop = True
            self._stop_by_self = True
            self._is_stopping = True
            await self.on_start_error(exc)
            self._stop_cleanup(reason=JobStopReasons.Internal.ERROR)
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

    def _stop_cleanup(
        self,
        reason: Optional[
            Union[JobStopReasons.Internal, JobStopReasons.External]
        ] = None,
    ):
        self._last_stopping_reason = (
            reason
            if isinstance(reason, (JobStopReasons.External, JobStopReasons.Internal))
            else self.get_stopping_reason()
        )

        self._skip_on_run = False
        self._is_starting = False
        self._startup_kill = False

        self._told_to_stop = False
        self._stop_by_self = False
        self._stop_by_force = False
        self._is_stopping = False
        self._told_to_restart = False

        self._loop_count = 0

        if self._told_to_complete or self._told_to_be_killed:
            self._initialized = False
            if self._is_being_guarded:
                if self._unguard_futures is not None:
                    for fut in self._unguard_futures:
                        if not fut.cancelled():
                            fut.set_result(True)

                    self._unguard_futures.clear()
                    self._manager._unguard()

            if self._guarded_job_proxies_dict is not None:
                for job_proxy in self._guarded_job_proxies_dict.values():
                    self.manager.unguard_job(job_proxy)

                self._guarded_job_proxies_dict.clear()

            if self.OutputQueues is not None:
                self._output_queue_proxies.clear()

            if self._told_to_complete:
                self._told_to_complete = False
                self._completed = True
                self._completed_at_ts = time.time()

                self._alive_since_ts = None

                for fut in self._done_futures:
                    if not fut.cancelled():
                        fut.set_result(JobStatus.COMPLETED)

                self._done_futures.clear()

                if self.OutputFields is not None:
                    for field_name, fut_list in self._output_field_futures.items():
                        output = self._output_fields[field_name]
                        for fut in fut_list:
                            if not fut.cancelled():
                                fut.set_result(output)

                        fut_list.clear()

                    self._output_field_futures.clear()

                if self.OutputQueues is not None:
                    for fut_list in self._output_queue_futures.values():
                        for fut, cancel_if_cleared in fut_list:
                            if not fut.cancelled():
                                fut.cancel(msg=f"Job object '{self}' has completed.")

            elif self._told_to_be_killed:
                self._told_to_be_killed = False
                self._killed = True
                self._killed_at_ts = time.time()

                self._alive_since_ts = None

                for fut in self._done_futures:
                    if not fut.cancelled():
                        fut.set_result(JobStatus.KILLED)

                self._done_futures.clear()

                if self.OutputFields is not None:
                    for fut_list in self._output_field_futures.values():
                        for fut in fut_list:
                            if not fut.cancelled():
                                fut.cancel(
                                    msg=f"Job object '{self}' was killed."
                                    " Job output would be incomplete."
                                )

                        fut_list.clear()

                    self._output_field_futures.clear()

                if self.OutputQueues is not None:
                    for fut_list in self._output_queue_futures.values():
                        for fut, cancel_if_cleared in fut_list:
                            if not fut.cancelled():
                                fut.cancel(msg=f"Job object '{self}' was killed.")

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
        self._is_stopping = True
        try:
            if not self._stop_by_self:
                await asyncio.wait_for(
                    self.on_stop(),
                    self._manager.get_job_stop_timeout(),
                )
            else:
                await self.on_stop()

        except asyncio.TimeoutError as exc:
            self._on_stop_exception = exc
            if not self._stop_by_self:
                await self.on_stop_error(exc)
            raise

        except Exception as exc:
            self._on_stop_exception = exc
            await self.on_stop_error(exc)
            raise

        finally:
            self._stop_cleanup()

    async def on_stop(self):
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
            f"An Exception occured in 'on_start' method of job " f"'{self!r}':\n\n",
            utils.format_code_exception(exc),
            file=sys.stderr,
        )

    async def _on_run_error(self, exc: Exception):
        self._on_run_exception = exc
        self._told_to_stop = True
        self._stop_by_self = True
        self._is_stopping = True
        await self.on_run_error(exc)

    async def on_run_error(self, exc: Exception):
        """DO NOT CALL THIS METHOD MANUALLY, EXCEPT WHEN USING `super()` WITHIN
        OVERLOADED VERSIONS OF THIS METHOD TO ACCESS A SUPERCLASS METHOD.

        Args:
            exc (Exception): The exception that occured.
        """
        print(
            f"An Exception occured in 'on_run' method of job " f"'{self!r}':\n\n",
            utils.format_code_exception(exc),
            file=sys.stderr,
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
            f"An Exception occured in 'on_stop' method of job " f"'{self!r}':\n\n",
            utils.format_code_exception(exc),
            file=sys.stderr,
        )

    def is_stopping(self) -> bool:
        """Whether this job object is stopping.

        Returns:
            bool: True/False
        """
        return self._is_stopping

    def is_stopping_by_force(self) -> bool:
        """Whether this job object is stopping forcefully.
        This also applies when it is being restarted, killed or
        completed. Errors that occur during execution and lead
        to a job stopping do not count as being forcefully stopped.

        Returns:
            bool: True/False
        """
        return self._is_stopping and self._stop_by_force

    def get_stopping_reason(
        self,
    ) -> Optional[Union[JobStopReasons.Internal, JobStopReasons.External]]:
        """Get the reason this job is stopping, if it is the case.

        Returns:
            Union[JobStopReasons.Internal, JobStopReasons.External]: An enum value
            from the `Internal` or `External` enums of the `JobStopReasons` namespace.
            None: This job is not stopping.
        """

        if not self._is_stopping:
            return
        elif (
            self._on_start_exception
            or self._on_run_exception
            or self._on_stop_exception
        ):
            return JobStopReasons.Internal.ERROR
        elif self._task_loop.current_loop == self._count:
            return JobStopReasons.Internal.EXECUTION_COUNT_LIMIT
        elif self._stop_by_self:
            if self._told_to_restart:
                return JobStopReasons.Internal.RESTART
            elif self._told_to_complete:
                return JobStopReasons.Internal.COMPLETION
            elif self._told_to_be_killed:
                return JobStopReasons.Internal.KILLING
            else:
                return JobStopReasons.Internal.UNSPECIFIC
        else:
            if self._told_to_restart:
                return JobStopReasons.External.RESTART
            elif self._told_to_be_killed:
                return JobStopReasons.External.KILLING
            else:
                return JobStopReasons.External.UNKNOWN

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

        Args:
            keep_default (bool, optional): Preserve the default set of exceptions
            in the whitelist. Defaults to True.

        """
        self._task_loop.clear_exception_types()
        if keep_default:
            self._task_loop.add_exception_type(*DEFAULT_JOB_EXCEPTION_WHITELIST)

    def get_last_stopping_reason(
        self,
    ) -> Optional[Union[JobStopReasons.Internal, JobStopReasons.External]]:
        """Get the last reason this job object stopped, when applicable.

        Returns:
            Optional[Union[JobStopReasons.Internal, JobStopReasons.External]]:
              The reason for stopping.
        """
        return self._last_stopping_reason

    def get_start_exception(self) -> Optional[Exception]:
        """Get the exception that caused this job to fail at startup
        within the `on_start()` method if it is the case,
        otherwise return None.

        Returns:
            Exception: The exception instance.
            None: No exception has been raised in `on_start()`.
        """
        return self._on_start_exception

    def get_run_exception(self) -> Optional[Exception]:
        """Get the exception that caused this job to fail while running
        its main loop within the `on_run()` method if it is the case,
        otherwise return None.

        Returns:
            Exception: The exception instance.
            None: No exception has been raised in `on_run()`.
        """
        return self._on_run_exception

    def get_stop_exception(self) -> Optional[Exception]:
        """Get the exception that caused this job to fail while shutting
        down with the `on_stop()` method if it is the case,
        otherwise return None.

        Returns:
            Exception: The exception instance.
            None: No exception has been raised in `on_stop()`.
        """
        return self._on_stop_exception

    async def _INITIALIZE_EXTERNAL(self):
        """DO NOT CALL THIS METHOD MANUALLY.

        This method to initializes a job using the `_on_init` method
        of the base class.
        """
        if self._manager is not None and not self._killed and not self._completed:
            await self._on_init()
            self._alive_since_ts = time.time()

    def _START(self) -> bool:
        if not self.is_running():
            self._task_loop.start()
            return True

        return False

    def _START_EXTERNAL(self) -> bool:
        return self._START()

    def STOP(self, force=False) -> bool:
        """DO NOT CALL THIS METHOD FROM OUTSIDE YOUR JOB SUBCLASS.

        Stop this job object.

        Args:
            force (bool, optional): Whether this job object should always
              be stopped forcefully instead of gracefully, thereby ignoring any
              exceptions that it might have handled when reconnecting is enabled
              for it. Job objects that are idling are always stopped forcefully.
              Defaults to False.

        Returns:
            bool: Whether the call was successful.
        """

        task = self._task_loop.get_task()

        if not (
            self._told_to_stop
            and not self._is_stopping
            and not self._stopped
            and task is not None
            and not task.done()
        ):
            self._stop_by_self = True
            if force or self._is_idling:  # forceful stopping is necessary when idling
                self._stop_by_force = True
                self._task_loop.cancel()
            else:
                self._skip_on_run = True
                # graceful stopping doesn't
                # skip `on_run()` when called in `on_start()`
                self._task_loop.stop()

            self._told_to_stop = True
            return True

        return False

    def _STOP_EXTERNAL(self, force=False) -> bool:
        """DO NOT CALL THIS METHOD MANUALLY.
        See `STOP()`.

        Returns:
            bool: Whether the call was successful.
        """

        if self.STOP(force=force):
            self._stop_by_self = False
            return True

        return False

    def RESTART(self) -> bool:
        """DO NOT CALL THIS METHOD FROM OUTSIDE YOUR JOB SUBCLASS.

        Restart this job object by forcefully stopping it, before
        starting it again automatically. Restarting a job object is
        only possible when it isn't being stopped forcefully, being
        killed, being completed or already being restarted. If a job
        object is being stopped gracefully, it will be restarted immediately
        after it stops.

        Returns:
            bool: Whether the call was successful.
        """

        task = self._task_loop.get_task()
        if (
            not self._told_to_restart
            and not self._told_to_be_killed
            and not self._told_to_complete
            and not self._stop_by_force
            and task is not None
            and not task.done()
        ):

            def restart_when_over(fut):
                task.remove_done_callback(restart_when_over)
                self._START()

            if not self._told_to_stop and not self._is_stopping:  # forceful restart
                self.STOP(force=True)

            task.add_done_callback(restart_when_over)
            self._told_to_restart = True
            return True

        return False

    def _RESTART_EXTERNAL(self) -> bool:
        """DO NOT CALL THIS METHOD MANUALLY.

        See `RESTART()`.
        """
        task = self._task_loop.get_task()
        if (
            not self._told_to_restart
            and not self._told_to_be_killed
            and not self._told_to_complete
            and not self._stop_by_force
            and task is not None
            and not task.done()
        ):

            def restart_when_over(fut):
                task.remove_done_callback(restart_when_over)
                self._START_EXTERNAL()

            if not self._told_to_stop and not self._is_stopping:  # forceful restart
                self._STOP_EXTERNAL(force=True)

            task.add_done_callback(restart_when_over)
            self._told_to_restart = True
            return True

        return False

    def COMPLETE(self) -> bool:
        """DO NOT CALL THIS METHOD FROM OUTSIDE YOUR JOB SUBCLASS.

        Stops this job object forcefullys, before removing it
        from its job manager. Any job that was completed
        has officially finished execution, and all jobs waiting
        for this job to complete will be notified. If a job had
        reconnecting enabled, then it will be silently cancelled
        to ensure that it suspends all execution.

        Returns:
            bool: Whether the call was successful.
        """

        if not self._told_to_be_killed and not self._told_to_complete:
            if not self._is_stopping:
                self.STOP(force=True)

            self._told_to_complete = True
            return True

        return False

    def KILL(self) -> bool:
        """
        DO NOT CALL THIS METHOD FROM OUTSIDE YOUR JOB SUBCLASS.

        Stops this job object forcefully, before removing it from its job manager.

        Returns:
            bool: Whether this method was successful.
        """

        if not self._told_to_be_killed and not self._told_to_complete:
            if not self._is_stopping:
                self.STOP(force=True)

            self._told_to_be_killed = True
            return True

        return False

    def _KILL_EXTERNAL(self, awaken=True) -> bool:
        """DO NOT CALL THIS METHOD MANUALLY.

        Stops this job object forcefully, before removing it from its job manager.
        If a job is already stopped, it can be awoken using this method, or simply
        uninitialized and removed from its job manager without it being able to
        react to the process.

        Args:
            awaken (bool, optional): Whether to awaken this job object before
              killing it, if it is stopped. Defaults to True.

        Returns:
            bool: Whether this method was successful.
        """

        if not self._told_to_be_killed and not self._told_to_complete:
            if self.is_running():
                if not self._is_stopping:
                    self._STOP_EXTERNAL(force=True)

            elif awaken:
                self._startup_kill = True  # start and kill as fast as possible
                self._START_EXTERNAL()

            else:
                self._told_to_be_killed = True
                self._stop_cleanup(reason=JobStopReasons.External.KILLING)

            self._told_to_be_killed = True
            return True

        return False

    async def wait_for(
        self, awaitable: Awaitable, timeout: Optional[float] = None
    ) -> Any:
        """Wait for a given awaitable object to complete.
        While awaiting the awaitable, this job object
        will be marked as waiting.

        Args:
            awaitable: An awaitable object

        Returns:
            Any: The result of the given awaitable.

        Raises:
            TypeError: The given object was not awaitable.
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

    def loop_count(self) -> int:
        """The current amount of `on_run()` calls completed by this job object."""
        return self._loop_count

    def is_awaiting(self) -> bool:
        """Whether this job is currently waiting
        for a coroutine to complete, which was awaited
        using `.wait_for(awaitable)`.

        Returns:
            bool: True/False
        """
        return self._is_awaiting

    def awaiting_since(self) -> Optional[datetime.datetime]:
        """The last time at which this job object began awaiting, if available.

        Returns:
            datetime.datetime: The time, if available.
        """
        if self._awaiting_since_ts:
            return datetime.datetime.fromtimestamp(
                self._awaiting_since_ts, tz=datetime.timezone.utc
            )

    def initialized(self) -> bool:
        """Whether this job has been initialized.

        Returns:
            bool: True/False
        """
        return self._initialized

    def is_initializing(self) -> bool:
        """Whether this job object is initializing.

        Returns:
            bool: True/False
        """

        return self._is_initializing

    def initialized_since(self) -> Optional[datetime.datetime]:
        """The time at which this job object was initialized, if available.

        Returns:
            datetime.datetime: The time, if available.
        """
        if self._initialized_since_ts:
            return datetime.datetime.fromtimestamp(
                self._initialized_since_ts, tz=datetime.timezone.utc
            )

    def alive(self) -> bool:
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

    def alive_since(self) -> Optional[datetime.datetime]:
        """The last time at which this job object became alive, if available.

        Returns:
            datetime.datetime: The time, if available.
        """
        if self._alive_since_ts:
            return datetime.datetime.fromtimestamp(
                self._alive_since_ts, tz=datetime.timezone.utc
            )

    def is_starting(self) -> bool:
        """Whether this job is currently starting to run.

        Returns:
            bool: True/False
        """
        return self._is_starting

    def is_running(self) -> bool:
        """Whether this job is currently running (alive and not stopped).

        Returns:
            bool: True/False
        """
        return self.alive() and self._task_loop.is_running() and not self._stopped

    def running_since(self) -> Optional[datetime.datetime]:
        """The last time at which this job object started running, if available.

        Returns:
            datetime.datetime: The time, if available.
        """
        if self._running_since_ts:
            return datetime.datetime.fromtimestamp(
                self._running_since_ts, tz=datetime.timezone.utc
            )

    def stopped(self) -> bool:
        """Whether this job is currently stopped (alive and not running).

        Returns:
            bool: True/False
        """
        return self._stopped

    def stopped_since(self) -> Optional[datetime.datetime]:
        """The last time at which this job object stopped, if available.

        Returns:
            datetime.datetime: The time, if available.
        """
        if self._stopped_since_ts:
            return datetime.datetime.fromtimestamp(
                self._stopped_since_ts, tz=datetime.timezone.utc
            )

    def is_idling(self) -> bool:
        """Whether this task is currently idling
        (running, waiting for the next opportunity to continue execution)

        Returns:
            bool: True/False
        """
        return self._is_idling

    def idling_since(self) -> Optional[datetime.datetime]:
        """The last time at which this job object began idling, if available.

        Returns:
            datetime.datetime: The time, if available.
        """
        if self._idling_since_ts:
            return datetime.datetime.fromtimestamp(
                self._idling_since_ts, tz=datetime.timezone.utc
            )

    def run_failed(self) -> bool:
        """Whether this job's `.on_run()` method failed an execution attempt,
        due to an unhandled exception being raised.

        Returns:
            bool: True/False
        """
        return self._task_loop.failed()

    def killed(self) -> bool:
        """Whether this job was killed."""
        return self._killed

    def killed_at(self) -> Optional[datetime.datetime]:
        """The last time at which this job object was killed, if available.

        Returns:
            datetime.datetime: The time, if available.
        """
        if self._killed_at_ts:
            return datetime.datetime.fromtimestamp(
                self._killed_at_ts, tz=datetime.timezone.utc
            )

    def is_being_killed(self) -> bool:
        """Whether this job is being killed.

        Returns:
            bool: True/False
        """
        return self._is_stopping and self._told_to_be_killed

    def is_being_startup_killed(self) -> bool:
        """Whether this job was started up only for it to be killed.
        This is useful for knowing if a job skipped `on_start()` and `on_run()`
        due to that, and can be checked for within `on_stop()`.
        """
        return self._startup_kill and self._is_stopping and self._told_to_be_killed

    def completed(self) -> bool:
        """Whether this job completed successfully.

        Returns:
            bool: True/False
        """
        return self._completed

    def completed_at(self) -> Optional[datetime.datetime]:
        """The last time at which this job object completed successfully,
        if available.

        Returns:
            datetime.datetime: The time, if available.
        """
        if self._completed_at_ts:
            return datetime.datetime.fromtimestamp(
                self._completed_at_ts, tz=datetime.timezone.utc
            )

    def is_completing(self) -> bool:
        """Whether this job is currently completing.

        Returns:
            bool: True/False
        """
        return self._is_stopping and self._told_to_complete

    def done(self) -> bool:
        """Whether this job was killed or has completed.

        Returns:
            bool: True/False
        """
        return self._killed or self._completed

    def done_since(self) -> Optional[datetime.datetime]:
        """The last time at which this job object completed successfully or was killed, if available.

        Returns:
            datetime.datetime: The time, if available.
        """
        ts = self._completed_at_ts or self._killed_at_ts
        if ts is not None:
            return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)

    def is_restarting(self) -> bool:
        """Whether this job is restarting.

        Returns:
            bool: True/False
        """

        return self._is_stopping and self._told_to_restart

    def was_restarted(self) -> bool:
        """A convenience method to check if a job was restarted.

        Returns:
            bool: True/False

        """
        return self._last_stopping_reason in (
            JobStopReasons.Internal.RESTART,
            JobStopReasons.External.RESTART,
        )

    def is_being_guarded(self) -> bool:
        """Whether this job object is being guarded.

        Returns:
            bool: True/False
        """
        return self._is_being_guarded

    def await_done(
        self, timeout: Optional[float] = None, cancel_if_killed: bool = False
    ) -> Coroutine:
        """Wait for this job object to be done (completed or killed) using the
        coroutine output of this method.

        Args:
            timeout (float, optional): Timeout for awaiting. Defaults to None.

        Raises:
            JobStateError: This job object is already done or not alive.
            asyncio.TimeoutError: The timeout was exceeded.
            asyncio.CancelledError: The job was killed.

        Returns:
            Coroutine: A coroutine that evaluates to either `KILLED`
              or `COMPLETED` from the `JobStatus` enum.
        """
        if not self.alive():
            raise JobStateError("this job object is not alive.")
        elif self.done():
            raise JobStateError("this job object is already done and not alive.")

        fut = self._task_loop.loop.create_future()

        self._done_futures.append(fut)

        return asyncio.wait_for(fut, timeout)

    def await_unguard(self, timeout: Optional[float] = None) -> Coroutine:
        """Wait for this job object to be unguarded using the
        coroutine output of this method.

        Args:
            timeout (float, optional):
                Timeout for awaiting. Defaults to None.

        Raises:
            JobStateError: This job object is already done or not alive,
              or isn't being guarded.
            asyncio.TimeoutError: The timeout was exceeded.
            asyncio.CancelledError: The job was killed.

        Returns:
            Coroutine: A coroutine that evaluates to `True`.
        """

        if not self.alive():
            raise JobStateError("this job object is not alive")
        elif self.done():
            raise JobStateError("this job object is already done and not alive")
        elif not self._is_being_guarded:
            raise JobStateError("this job object is not being guarded by a job")

        fut = self._task_loop.loop.create_future()

        if self._unguard_futures is None:
            self._unguard_futures = []

        self._unguard_futures.append(fut)

        return asyncio.wait_for(fut, timeout)

    def get_output_queue_proxy(self) -> "proxies.JobOutputQueueProxy":
        """Get a job output queue proxy object for more convenient
        reading of job output queues while this job is running.

        Raises:
            JobStateError: This job object is already done or not alive,
              or isn't being guarded.
            TypeError: Output queues aren't
              defined for this job type.

        Returns:
            JobOutputQueueProxy: The output queue proxy.
        """

        if not self.alive():
            raise JobStateError("this job object is not alive")
        elif self.done():
            raise JobStateError("this job object is already done and not alive")

        if self.OutputQueues is not None:
            output_queue_proxy = proxies.JobOutputQueueProxy(self)
            self._output_queue_proxies.append(output_queue_proxy)
            return output_queue_proxy

        raise TypeError("this job object does not support output queues")

    def verify_output_field_support(
        self, field_name: str, raise_exceptions=False
    ) -> bool:
        """Verify if a specified output field name is supported by this job,
        or if it supports output fields at all. Disabled output field names
        are seen as unsupported.

        Args:
            field_name (str): The name of the output field to set.
            raise_exceptions (bool, optional): Whether exceptions
              should be raised. Defaults to False.

        Raises:
            TypeError: Output fields aren't supported for this job,
              or `field_name` is not a string.
              ValueError: The specified field name was marked as disabled.
            LookupError: The specified field name is not defined by this job.

        Returns:
            bool: True/False
        """

        if self.OutputFields is None:
            if raise_exceptions:
                raise TypeError(
                    f"'{self.__class__.__qualname__}' class does not"
                    f" implement or inherit an 'OutputFields' class namespace"
                )
            return False

        value = getattr(self.OutputFields, field_name, None)

        if value is None:
            if raise_exceptions:
                raise (
                    LookupError(
                        f"field name '{field_name}' is not defined in"
                        f" 'OutputFields' class namespace of "
                        f"'{self.__class__.__qualname__}' class"
                    )
                    if isinstance(field_name, str)
                    else TypeError(
                        f"'field_name' argument must be of type str,"
                        f" not {field_name.__class__.__name__}"
                    )
                )
            return False

        elif value == "DISABLED":
            if raise_exceptions:
                raise ValueError(
                    f"the output field name '{field_name}' has been marked as disabled"
                )
            return False

        return True

    def verify_output_queue_support(
        self, queue_name: str, raise_exceptions=False
    ) -> bool:
        """Verify if a specified output queue name is supported by this job,
        or if it supports output queues at all. Disabled output queue names
        are seen as unsupported.

        Args:
            queue_name (str): The name of the output queue to set.
            raise_exceptions (bool, optional): Whether exceptions should be
              raised. Defaults to False.

        Raises:
            TypeError: Output queues aren't supported for this job,
              or `queue_name` is not a string.
            ValueError: The specified queue name was marked as disabled.
            LookupError: The specified queue name is not defined by this job.

        Returns:
            bool: True/False
        """
        if self.OutputQueues is None:
            if raise_exceptions:
                raise TypeError(
                    f"'{self.__class__.__qualname__}' class does not"
                    f" implement or inherit an 'OutputQueues' class namespace"
                )
            return False

        value = getattr(self.OutputQueues, queue_name, None)

        if value is None:
            if raise_exceptions:
                raise (
                    LookupError(
                        f"queue name '{queue_name}' is not defined in"
                        f" 'OutputQueues' class namespace of "
                        f"'{self.__class__.__qualname__}' class"
                    )
                    if isinstance(queue_name, str)
                    else TypeError(
                        f"'queue_name' argument must be of type str,"
                        f" not {queue_name.__class__.__name__}"
                    )
                )
            return False

        elif value == "DISABLED":
            if raise_exceptions:
                raise ValueError(
                    f"the output queue name '{queue_name}' has been marked as disabled"
                )
            return False

        return True

    def set_output_field(self, field_name: str, value: Any):
        """Set the specified output field to have the given value,
        while releasing the value to external jobs awaiting the field.

        Args:
            field_name (str): The name of the output field to set.

        Raises:
            TypeError: Output fields aren't supported for this job,
              or `field_name` is not a string.
            LookupError: The specified field name is not defined by this job.
            JobStateError: An output field value has already been set.
        """

        self.verify_output_field_support(field_name, raise_exceptions=True)

        field_value = self._output_fields.get(field_name, UNSET)

        if field_value is not UNSET:
            raise JobStateError(
                "An output field value has already been set for the field"
                f" '{field_name}'"
            )

        self._output_fields[field_name] = value

        if field_name in self._output_field_futures:
            for fut in self._output_field_futures[field_name]:
                if not fut.cancelled():
                    fut.set_result(value)

            self._output_field_futures[field_name].clear()

    def push_output_queue(self, queue_name: str, value: Any):
        """Add a value to the specified output queue,
        while releasing the value to external jobs
        awaiting the field.

        Args:
            queue_name (str): The name of the target output queue.

        Raises:
            TypeError: Output queues aren't supported for this job,
              or `queue_name` is not a string.
            LookupError: The specified queue name is not defined by this job.
            JobStateError: An output field value has already been set.
        """

        self.verify_output_queue_support(queue_name, raise_exceptions=True)

        if queue_name not in self._output_queues:
            self._output_queues[queue_name] = queue = []
            for proxy in self._output_queue_proxies:
                proxy._new_output_queue_alert(queue_name, queue)

        queue_entries: list = self._output_queues[queue_name]
        queue_entries.append(value)

        if queue_name in self._output_queue_futures:
            for fut, cancel_if_cleared in self._output_queue_futures[queue_name]:
                if not fut.cancelled():
                    fut.set_result(value)

            self._output_queue_futures[queue_name].clear()

    def get_output_field(self, field_name: str, default=UNSET, /) -> Any:
        """Get the value of a specified output field.

        Args:
            field_name (str): The name of the target output field.
            default (object, optional): The value to return if the specified
              output field does not exist, has not been set,
              or if this job doesn't support them at all.
              Defaults to `UNSET`, which will
              trigger an exception.

        Raises:
            TypeError: Output fields aren't supported for this job,
              or `field_name` is not a string.
            LookupError: The specified field name is not defined by this job.
            JobStateError: An output field value is not set.

        Returns:
            object: The output field value.
        """

        if self.OutputFields is None:
            if default is UNSET:
                self.verify_output_field_support(field_name, raise_exceptions=True)
            return default

        elif getattr(self.OutputFields, field_name, None) in (None, "DISABLED"):
            if default is UNSET:
                self.verify_output_field_support(field_name, raise_exceptions=True)
            return default

        if field_name not in self._output_fields:
            if default is UNSET:
                raise JobStateError(
                    "An output field value has not been set for the field"
                    f" '{field_name}'"
                )
            return default

        old_field_data_list: list = self._output_fields[field_name]

        if not old_field_data_list[1]:
            if default is UNSET:
                raise JobStateError(
                    "An output field value has not been set for the field"
                    f" '{field_name}'"
                )
            return default

        return old_field_data_list[0]

    def get_output_queue_contents(self, queue_name: str) -> list[Any]:
        """Get a list of all values present in the specified output queue.
        For continuous access to job output queues, consider requesting
        a `JobOutputQueueProxy` object using `.get_output_queue_proxy()`.

        Args:
            queue_name (str): The name of the target output queue.
            default (object, optional): The value to return if the specified
              output queue does not exist, is empty,
              or if this job doesn't support them at all.
              Defaults to `UNSET`, which will
              trigger an exception.

        Raises:
            TypeError: Output queues aren't supported for this job,
              or `queue_name` is not a string.
            LookupError: The specified queue name is not defined by this job.

        Returns:
            list: A list of values.
        """

        self.verify_output_queue_support(queue_name, raise_exceptions=True)

        if queue_name not in self._output_queues:
            raise JobStateError(f"The specified output queue '{queue_name}' is empty")

        queue_data_list: list = self._output_queues[queue_name]

        if not queue_data_list:
            raise JobStateError(f"The specified output queue '{queue_name}' is empty")

        return queue_data_list[:]

    def clear_output_queue(self, queue_name: str):
        """Clear all values in the specified output queue.

        Args:
            queue_name (str): The name of the target output field.
        """
        self.verify_output_queue_support(queue_name, raise_exceptions=True)

        if queue_name in self._output_queues:
            for output_queue_proxy in self._output_queue_proxies:
                output_queue_proxy._output_queue_clear_alert(queue_name)

            for fut, cancel_if_cleared in self._output_queue_futures[queue_name]:
                if not fut.cancelled():
                    if cancel_if_cleared:
                        fut.cancel(f"The job output queue '{queue_name}' was cleared")
                    else:
                        fut.set_result(f"{queue_name}_CLEARED")

            self._output_queues[queue_name].clear()

    def get_output_field_names(self) -> tuple[str]:
        """Get all output field names that this job supports.
        An empty tuple means that none are supported.

        Returns:
            tuple: A tuple of the supported output fields.
        """

        if self.OutputFields is None:
            return tuple()

        return self.OutputFields.__record_names__

    def get_output_queue_names(self) -> tuple[str]:
        """Get all output queue names that this job supports.
        An empty tuple means that none are supported.

        Returns:
            tuple: A tuple of the supported output queues.
        """
        if self.OutputQueues is None:
            return tuple()

        return self.OutputQueues.__record_names__

    def has_output_field_name(self, field_name: str) -> bool:
        """Whether the specified field name is supported as an
        output field.

        Args:
            field_name (str): The name of the target output field.

        Returns:
            bool: True/False
        """

        if not isinstance(field_name, str):
            raise TypeError(
                f"'field_name' argument must be of type str,"
                f" not {field_name.__class__.__name__}"
            )

        return self.verify_output_field_support(field_name)

    def has_output_queue_name(self, queue_name: str) -> bool:
        """Whether the specified queue name is supported as an
        output queue.

        Args:
            queue_name (str): The name of the target output queue.

        Returns:
            bool: True/False
        """

        if not isinstance(queue_name, str):
            raise TypeError(
                f"'queue_name' argument must be of type str,"
                f" not {queue_name.__class__.__name__}"
            )

        return self.verify_output_queue_support(queue_name)

    def output_field_is_set(self, field_name: str) -> bool:
        """Whether a value for the specified output field
        has been set.

        Args:
            field_name (str): The name of the target output field.

        Raises:
            TypeError: Output fields aren't supported for this job,
              or `field_name` is not a string.
            LookupError: The specified field name is not defined by this job.

        Returns:
            bool: True/False
        """

        self.verify_output_field_support(field_name, raise_exceptions=True)

        field_value = self._output_fields.get(field_name, UNSET)

        return field_value is not UNSET

    def output_queue_is_empty(self, queue_name: str) -> bool:
        """Whether the specified output queue is empty.

        Args:
            queue_name (str): The name of the target output queue.

        Raises:
            TypeError: Output queues aren't supported for this job,
              or `queue_name` is not a string.
            LookupError: The specified queue name is not defined by this job.

        Returns:
            bool: True/False
        """

        self.verify_output_queue_support(queue_name, raise_exceptions=True)

        return not self._output_queues.get(queue_name, None)

    def await_output_field(
        self, field_name: str, timeout: Optional[float] = None
    ) -> Coroutine:
        """Wait for this job object to release the value of a
        specified output field while it is running, using the
        coroutine output of this method.

        Args:
            field_name (str): The name of the target output field.
            timeout (float, optional): The maximum amount of
              time to wait in seconds. Defaults to None.

        Raises:
            TypeError: Output fields aren't supported for this job,
              or `field_name` is not a string.
            LookupError: The specified field name is not defined by this job.
            JobStateError: This job object is already done.
            asyncio.TimeoutError: The timeout was exceeded.
            asyncio.CancelledError: The job was killed.

        Returns:
            Coroutine: A coroutine that evaluates to the value of specified
              output field.
        """

        self.verify_output_field_support(field_name, raise_exceptions=True)

        if self.done():
            raise JobStateError("this job object is already done and not alive.")

        fut = self._task_loop.loop.create_future()

        if field_name not in self._output_field_futures:
            self._output_field_futures[field_name] = []

        self._output_field_futures[field_name].append(fut)

        return asyncio.wait_for(fut, timeout=timeout)

    def await_output_queue_add(
        self,
        queue_name: str,
        timeout: Optional[float] = None,
        cancel_if_cleared: bool = True,
    ) -> Coroutine:
        """Wait for this job object to add to the specified output queue while
        it is running, using the coroutine output of this method.

        Args:
            timeout (float, optional): The maximum amount of time to wait in
              seconds. Defaults to None.
            cancel_if_cleared (bool, optional): Whether `asyncio.CancelledError` should
              be raised if the output queue is cleared. If set to `False`,
              `UNSET` will be the result of the coroutine. Defaults to False.

        Raises:
            TypeError: Output fields aren't supported for this job,
              or `field_name` is not a string.
            LookupError: The specified field name is not defined by this job
            JobStateError: This job object is already done.
            asyncio.TimeoutError: The timeout was exceeded.
            asyncio.CancelledError: The job was killed, or the output queue
              was cleared.

        Returns:
            Coroutine: A coroutine that evaluates to the most recent output
              queue value, or `UNSET` if the queue is cleared.
        """

        self.verify_output_queue_support(queue_name, raise_exceptions=True)

        if self.done():
            raise JobStateError("this job object is already done and not alive.")

        if queue_name not in self._output_queue_futures:
            self._output_queue_futures[queue_name] = []

        fut = self._task_loop.loop.create_future()
        self._output_queue_futures[queue_name].append((fut, cancel_if_cleared))

        return asyncio.wait_for(fut, timeout=timeout)

    def verify_public_method_suppport(
        self, method_name: str, raise_exceptions=False
    ) -> bool:
        """Verify if a job has a public method exposed under the specified name is
        supported by this job, or if it supports public methods at all. Disabled
        public method names are seen as unsupported.


        Args:
            method_name (str): The name of the public method.
            raise_exceptions (bool, optional): Whether exceptions
              should be raised. Defaults to False.

        Raises:
            TypeError: Output fields aren't supported for this job,
              or `field_name` is not a string.
            LookupError: No public method under the specified name is defined by this
              job.

        Returns:
            bool: True/False
        """

        if self.PUBLIC_METHODS_CHAINMAP is None:
            if raise_exceptions:
                raise TypeError(
                    f"'{self.__class__.__qualname__}' class does not"
                    f" support any public methods"
                )
            return False

        elif method_name not in self.PUBLIC_METHODS_CHAINMAP:
            if raise_exceptions:
                raise (
                    LookupError(
                        f"no public method under the specified name '{method_name}' is "
                        "defined by the class of this job"
                    )
                    if isinstance(method_name, str)
                    else TypeError(
                        f"'method_name' argument must be of type str,"
                        f" not {method_name.__class__.__name__}"
                    )
                )
            return False

        elif getattr(self, method_name).__dict__.get("__disabled", False):
            if raise_exceptions:
                raise ValueError(
                    f"the public method of this job of class '{self.__class__.__qualname__} "
                    f"under the name '{method_name}' has been marked as disabled"
                )
            return False

        return True

    def get_public_method_names(self) -> tuple[str]:
        """Get the names of all public methods that this job supports.

        Returns:
            tuple: A tuple of the names of the supported methods.
        """
        if self.PUBLIC_METHODS_CHAINMAP is None:
            return tuple()

        return tuple(self.PUBLIC_METHODS_CHAINMAP.keys())

    def has_public_method_name(self, method_name: str) -> bool:
        """Whether a public method under the specified name is supported by this job.

        Args:
            method_name (str): The name of the target method

        Returns:
            bool: True/False
        """

        if not isinstance(method_name, str):
            raise TypeError(
                f"'method_name' argument must be of type str,"
                f" not {method_name.__class__.__name__}"
            )

        return self.verify_public_method_suppport(method_name)

    def public_method_is_async(self, method_name: str) -> bool:
        """Whether a public method under the specified name is a coroutine function.

        Args:
            method_name (str): The name of the target method.

        Returns:
            bool: True/False
        """

        self.verify_public_method_suppport(method_name, raise_exceptions=True)

        return inspect.iscoroutinefunction(getattr(self, method_name))

    def run_public_method(self, method_name, *args, **kwargs) -> Any:
        """Run a public method under the specified name and return the
        result.

        Args:
            method_name (str): The name of the target method.

        Returns:
            object: The result of the call.
        """

        self.verify_public_method_suppport(method_name, raise_exceptions=True)

        method = getattr(self, method_name)

        return method(*args, **kwargs)

    def status(self) -> JobStatus:
        """Get the job status of this job as a value from the
        `JobStatus` enum.

        Returns:
            str: A status value.
        """
        output = None
        if self.alive():
            if self.is_running():
                if self.is_starting():
                    output = JobStatus.STARTING
                elif self.is_idling():
                    output = JobStatus.IDLING
                elif self.is_awaiting():
                    output = JobStatus.AWAITING
                elif self.is_completing():
                    output = JobStatus.COMPLETING
                elif self.is_being_killed():
                    output = JobStatus.BEING_KILLED
                elif self.is_restarting():
                    output = JobStatus.RESTARTING
                elif self.is_stopping():
                    output = JobStatus.STOPPING
                else:
                    output = JobStatus.RUNNING
            elif self.stopped():
                output = JobStatus.STOPPED
            elif self.initialized():
                output = JobStatus.INITIALIZED

        elif self.completed():
            output = JobStatus.COMPLETED
        elif self.killed():
            output = JobStatus.KILLED
        else:
            output = JobStatus.FRESH

        return output

    def __str__(self):
        output_str = (
            f"<{self.__class__.__qualname__} "
            f"(ID={self._identifier} CREATED_AT={self.created_at} "
            f"PERM_LVL={self._PERMISSION_LEVEL.name} "
            f"STATUS={self.status().name})>"
        )

        return output_str

    def __repr__(self):
        output_str = f"<{self.__class__.__qualname__} " f"(ID={self._identifier})>"

        return output_str


class IntervalJobBase(JobBase):
    """Base class for interval based jobs.
    Subclasses are expected to overload the `on_run()` method.
    `on_start()` and `on_stop()` and `on_run_error(exc)`
    can optionally be overloaded.

    One can override the class variables `DEFAULT_INTERVAL`,
    `DEFAULT_COUNT` and `DEFAULT_RECONNECT` in subclasses.
    They are derived from the keyword arguments of the
    `discord.ext.tasks.Loop` constructor. These will act as
    defaults for each job object created from this class.
    """

    DEFAULT_INTERVAL = datetime.timedelta()

    DEFAULT_COUNT: Optional[int] = None
    DEFAULT_RECONNECT = True

    def __init__(
        self,
        interval: Optional[datetime.timedelta] = None,
        count: Union[int, _UnsetType] = UNSET,
        reconnect: Optional[bool] = None,
    ):
        """Create a new `IntervalJobBase` instance.

        Args:
            interval (Optional[datetime.timedelta], optional):
            count (Optional[int], optional):
            reconnect (Optional[bool], optional): Overrides for the default class
              variables for an `IntervalJobBase` instance.
        """

        super().__init__()
        self._interval_secs = (
            self.DEFAULT_INTERVAL.total_seconds()
            if interval is None
            else interval.total_seconds()
        )
        self._count = self.DEFAULT_COUNT if count is UNSET else count

        self._reconnect = not not (
            self.DEFAULT_RECONNECT if reconnect is None else reconnect
        )

        self._loop_count = 0
        self._task_loop = CustomLoop(
            self._on_run,
            seconds=self._interval_secs,
            hours=0,
            minutes=0,
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
            Optional[datetime.datetime]: The time at which
              the next iteration will occur, if available.
        """
        return self._task_loop.next_iteration()

    def get_interval(self):
        """Returns a tuple of the seconds, minutes and hours at which this job
        object is executing its `.on_run()` method.

        Returns:
            tuple: `(seconds, minutes, hours)`
        """
        return self._task_loop.seconds, self._task_loop.minutes, self._task_loop.hours

    def change_interval(
        self,
        seconds: int = 0,
        minutes: int = 0,
        hours: int = 0,
    ):
        """Change the interval at which this job will run its `on_run()` method.
        This will only be applied on the next iteration of `on_run()`.

        Args:
            seconds (Optional[Union[int, float]], optional): Defaults to 0.
            minutes (Optional[Union[int, float]], optional): Defaults to 0.
            hours (Optional[Union[int, float]], optional): Defaults to 0.
        """
        self._task_loop.change_interval(
            seconds=seconds,
            minutes=minutes,
            hours=hours,
        )

        self._interval_secs = seconds + (minutes * 60.0) + (hours * 3600.0)

    async def on_start(self):  # make this optional for subclasses
        pass

    async def _on_run(self):
        if self._startup_kill:
            self._KILL_EXTERNAL()
            return

        elif self._skip_on_run:
            return

        self._is_idling = False
        self._idling_since_ts = None

        await self.on_run()
        if self._interval_secs:  # There is a task loop interval set
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

    async def on_stop(self):  # make this optional for subclasses
        pass


class EventJobBase(JobBase):
    """A job base class for jobs that run in reaction to specific events
    passed to them by their job manager object.
    Subclasses are expected to overload the `on_run(self, event)` method.
    `on_start()` and `on_stop()` and `on_run_error(self, exc)` can
    optionally be overloaded.
    One can also override the class variables `DEFAULT_COUNT` and `DEFAULT_RECONNECT`
    in subclasses. They are derived from the keyword arguments of the
    `discord.ext.tasks.loop` decorator. Unlike `IntervalJobBase` class instances,
    the instances of this class depend on their job manager to trigger
    the execution of their `.on_run()` method, and will stop running if
    all ClientEvent objects passed to them have been processed.

    Attributes:
        EVENT_TYPES: A tuple denoting the set of `BaseEvent` classes whose
          instances should be recieved after their corresponding event is
          registered by the job manager of an instance of this class. By
          default, all instances of `BaseEvent` will be propagated.
    """

    EVENT_TYPES: tuple[events.BaseEvent] = (events.BaseEvent,)

    DEFAULT_INTERVAL: datetime.timedelta = datetime.timedelta()
    DEFAULT_COUNT: Optional[int] = None
    DEFAULT_RECONNECT: bool = True

    DEFAULT_MAX_EVENT_CHECKS_PER_ITERATION: Optional[int] = None

    DEFAULT_EMPTY_EVENT_QUEUE_TIMEOUT: Optional[datetime.timedelta] = None

    DEFAULT_MAX_EVENT_QUEUE_SIZE: Optional[int] = None

    DEFAULT_ALLOW_EVENT_QUEUE_OVERFLOW: bool = False

    DEFAULT_BLOCK_EVENTS_ON_STOP: bool = True
    DEFAULT_START_ON_DISPATCH: bool = False
    DEFAULT_BLOCK_EVENTS_WHILE_STOPPED: bool = True
    DEFAULT_CLEAR_EVENTS_AT_STARTUP: bool = True

    __slots__ = (
        "_pre_event_queue",
        "_event_queue",
        "_last_event",
        "_max_event_checks_per_iteration",
        "_empty_event_queue_timeout_secs",
        "_max_event_queue_size",
        "_allow_event_queue_overflow",
        "_block_events_on_stop",
        "_start_on_dispatch",
        "_block_events_while_stopped",
        "_clear_events_at_startup",
        "_allow_dispatch",
        "_stopping_by_empty_queue",
        "_stopping_by_idling_timeout",
        "_empty_event_queue_future",
    )

    def __init_subclass__(
        cls,
        scheduling_identifier: Optional[str] = None,
        permission_level: Optional[JobPermissionLevels] = None,
    ):
        if not cls.EVENT_TYPES:
            raise TypeError("the 'EVENT_TYPES' class attribute must not be empty")

        elif not isinstance(cls.EVENT_TYPES, (list, tuple)):
            raise TypeError(
                "the 'EVENT_TYPES' class attribute must be of type 'tuple' and "
                "must contain one or more subclasses of `BaseEvent`"
            )
        elif not all(issubclass(et, events.BaseEvent) for et in cls.EVENT_TYPES):
            raise ValueError(
                "the 'EVENT_TYPES' class attribute "
                "must contain one or more subclasses of `BaseEvent`"
            )

        super().__init_subclass__(
            scheduling_identifier=scheduling_identifier,
            permission_level=permission_level,
        )

    def __init__(
        self,
        interval: Optional[datetime.timedelta] = None,
        count: Union[int, _UnsetType] = UNSET,
        reconnect: Optional[bool] = None,
        max_event_checks_per_iteration: Optional[Union[int, _UnsetType]] = UNSET,
        empty_event_queue_timeout: Optional[
            Union[datetime.timedelta, _UnsetType]
        ] = UNSET,
        max_event_queue_size: Optional[int] = None,
        allow_event_queue_overflow: Optional[bool] = None,
        block_events_on_stop: Optional[bool] = None,
        block_events_while_stopped: Optional[bool] = None,
        clear_events_at_startup: Optional[bool] = None,
        start_on_dispatch: Optional[bool] = None,
    ):
        super().__init__()

        self._interval_secs = (
            self.DEFAULT_INTERVAL.total_seconds()
            if interval is None
            else interval.total_seconds()
        )
        self._count = self.DEFAULT_COUNT if count is UNSET else count

        self._reconnect = not not (
            self.DEFAULT_RECONNECT if reconnect is None else reconnect
        )

        max_event_checks_per_iteration = (
            self.DEFAULT_MAX_EVENT_CHECKS_PER_ITERATION
            if max_event_checks_per_iteration is UNSET
            else max_event_checks_per_iteration
        )
        if isinstance(max_event_checks_per_iteration, (int, float)):
            self._max_event_checks_per_iteration = int(max_event_checks_per_iteration)
            if self._max_event_checks_per_iteration <= 0:
                self._max_event_checks_per_iteration = None
        else:
            self._max_event_checks_per_iteration = None

        empty_event_queue_timeout = (
            self.DEFAULT_EMPTY_EVENT_QUEUE_TIMEOUT
            if empty_event_queue_timeout is UNSET
            else empty_event_queue_timeout
        )

        if isinstance(empty_event_queue_timeout, datetime.timedelta):
            self._empty_event_queue_timeout_secs = (
                empty_event_queue_timeout.total_seconds()
            )
        else:
            self._empty_event_queue_timeout_secs = None

        max_event_queue_size = (
            self.DEFAULT_MAX_EVENT_QUEUE_SIZE
            if max_event_queue_size is UNSET
            else max_event_queue_size
        )
        if isinstance(max_event_queue_size, (int, float)):
            self._max_event_queue_size = int(max_event_queue_size)
        else:
            self._max_event_queue_size = None

        self._allow_event_queue_overflow = not not (
            self.DEFAULT_ALLOW_EVENT_QUEUE_OVERFLOW
            if allow_event_queue_overflow is None
            else allow_event_queue_overflow
        )

        self._block_events_on_stop = not not (
            self.DEFAULT_BLOCK_EVENTS_ON_STOP
            if block_events_on_stop is None
            else block_events_on_stop
        )
        self._start_on_dispatch = not not (
            self.DEFAULT_START_ON_DISPATCH
            if start_on_dispatch is None
            else start_on_dispatch
        )
        self._block_events_while_stopped = not not (
            self.DEFAULT_BLOCK_EVENTS_WHILE_STOPPED
            if block_events_while_stopped is None
            else block_events_while_stopped
        )
        self._clear_events_at_startup = not not (
            self.DEFAULT_CLEAR_EVENTS_AT_STARTUP
            if clear_events_at_startup is None
            else clear_events_at_startup
        )

        if self._block_events_while_stopped or self._clear_events_at_startup:
            self._start_on_dispatch = False

        self._allow_dispatch = True

        self._stopping_by_empty_queue = False
        self._stopping_by_idling_timeout = False

        self._empty_event_queue_future: Optional[asyncio.Future] = None
        # used to idle while no events are available to conserve processing power

        self._pre_event_queue = deque()
        self._event_queue = deque(maxlen=self._max_event_queue_size)
        self._last_event: Optional[events.BaseEvent] = None

        self._task_loop = CustomLoop(
            self._on_run,
            seconds=self._interval_secs,
            hours=0,
            minutes=0,
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
            or (self._block_events_on_stop and self._is_stopping)
            or (self._block_events_while_stopped and not task_is_running)
        ):
            return

        self._pre_event_queue.append(event)
        if self._start_on_dispatch and not task_is_running:
            self._task_loop.start()

        elif (
            self._empty_event_queue_future is not None
            and not self._empty_event_queue_future.done()
            and not self._empty_event_queue_future.cancelled()
        ):
            self._empty_event_queue_future.set_result(True)

    def check_event(self, event: events.BaseEvent):
        """A method for subclasses that can be overloaded to perform validations on a `BaseEvent`
        instance that was dispatched to them. Must return a boolean value indicating the
        validaiton result. If not overloaded, this method will always return `True`.

        Args:
            event (events.BaseEvent): The event object to run checks upon.
        """
        return True

    def get_last_event(self) -> Optional[events.BaseEvent]:
        """Get the last event dispatched to this event job object.

        Returns:
            BaseEvent: The event object.
        """
        return self._last_event

    def _validate_and_pump_events(self):
        iterator_obj = (
            range(self._max_event_checks_per_iteration)
            if self._max_event_checks_per_iteration is not None
            else itertools.count()
        )

        for _ in iterator_obj:
            if not self._pre_event_queue:
                break
            elif (
                len(self._event_queue) == self._max_event_queue_size
                and not self._allow_event_queue_overflow
            ):
                break

            event = self._pre_event_queue.popleft()
            if self.check_event(event):
                self._event_queue.append(event)

    async def _on_start(self):
        if self._clear_events_at_startup:
            self._pre_event_queue.clear()
            self._event_queue.clear()

        await super()._on_start()

    async def on_start(self):  # make this optional for subclasses
        pass

    async def _on_run(self):
        self._is_idling = False
        self._idling_since_ts = None
        self._stopping_by_idling_timeout = False

        if self._startup_kill:
            self._KILL_EXTERNAL()
            return

        elif self._skip_on_run:
            return

        if self._pre_event_queue:  # only if new events are available
            self._validate_and_pump_events()

        if not self._event_queue:
            if not self._empty_event_queue_timeout_secs:
                if (
                    self._empty_event_queue_timeout_secs is None
                ):  # idle indefinitely until an event is recieved.
                    self._is_idling = True
                    self._idling_since_ts = time.time()

                    while not self._event_queue:
                        self._empty_event_queue_future = (
                            self._task_loop.loop.create_future()
                        )
                        try:
                            await self._empty_event_queue_future  # wait till an event is dispatched
                        except asyncio.CancelledError as exc:
                            if exc.args[0] == "CANCEL_BY_TASK_LOOP":
                                # stopping because of task loop cancellation
                                raise

                        self._validate_and_pump_events()

                    self._is_idling = False
                    self._idling_since_ts = None

                else:  # self._empty_event_queue_timeout_secs is zero
                    self._stopping_by_empty_queue = True
                    self.STOP()
                    return
            else:
                while not self._event_queue:
                    if not self._is_idling:
                        self._is_idling = True
                        self._idling_since_ts = time.time()

                    event_was_dispatched = False

                    try:
                        self._empty_event_queue_future = (
                            self._task_loop.loop.create_future()
                        )

                        handle = self._task_loop.loop.call_later(  # copied from asyncio.sleep
                            self._empty_event_queue_timeout_secs,
                            lambda fut: None
                            if fut.cancelled() or fut.done()
                            else fut.set_result(False),
                            self._empty_event_queue_future,
                        )

                        try:
                            event_was_dispatched = (
                                await self._empty_event_queue_future
                            )  # wait till an event is dispatched
                        finally:
                            handle.cancel()

                        self._is_idling = False
                        self._idling_since_ts = None

                    except asyncio.CancelledError as exc:
                        # ignore CancelledError that is not from job task loop object
                        print(repr(exc))
                        if exc.args[0] == "CANCEL_BY_TASK_LOOP":
                            # stopping because of task loop cancellation
                            raise
                    else:
                        if event_was_dispatched:
                            # an event was dispatched, even if that event did not
                            # reach the main event queue
                            continue
                        else:
                            self._stopping_by_idling_timeout = True
                            self.STOP()
                            return

                    self._validate_and_pump_events()

        elif self._loop_count == self._count:
            self.STOP()
            return

        event = self._event_queue.popleft()
        await self.on_run(event)
        self._last_event = event

        self._loop_count += 1

        if self._interval_secs:
            self._is_idling = True
            self._idling_since_ts = time.time()

    async def on_run(self, event: events.BaseEvent):
        """The code to run whenever an event is recieved.
        This method must be overloaded in subclasses.

        Raises:
            NotImplementedError: This method must be overloaded in subclasses.
        """
        raise NotImplementedError()

    def _stop_cleanup(self):
        self._stopping_by_idling_timeout = False
        self._stopping_by_empty_queue = False
        super()._stop_cleanup()

    async def on_stop(self):  # make this optional for subclasses
        pass

    def get_event_queue_size(self) -> int:
        """Get the amount of filtered events
        stored in the event queue of this job object.

        Returns:
            int: The queue sizee.
        """
        return len(self._event_queue)

    def clear_event_queue(self):
        """Clear the current event queue."""
        self._pre_event_queue.clear()
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

    def queue_is_blocked(self) -> bool:
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

    def get_stopping_reason(
        self,
    ) -> Optional[Union[JobStopReasons.Internal, JobStopReasons.External]]:
        if not self._is_stopping:
            return
        elif (
            self._on_start_exception
            or self._on_run_exception
            or self._on_stop_exception
        ):
            return JobStopReasons.Internal.ERROR
        elif (
            not self._empty_event_queue_timeout_secs
            and self._empty_event_queue_timeout_secs is not None
            and self._stopping_by_empty_queue
        ):
            return JobStopReasons.Internal.EMPTY_QUEUE

        elif self._stopping_by_idling_timeout:
            return JobStopReasons.Internal.IDLING_TIMEOUT

        elif self._task_loop.current_loop == self._count:
            return JobStopReasons.Internal.EXECUTION_COUNT_LIMIT
        elif self._stop_by_self:
            if self._told_to_restart:
                return JobStopReasons.Internal.RESTART
            elif self._told_to_complete:
                return JobStopReasons.Internal.COMPLETION
            elif self._told_to_be_killed:
                return JobStopReasons.Internal.KILLING
            else:
                return JobStopReasons.Internal.UNSPECIFIC
        else:
            if self._told_to_restart:
                return JobStopReasons.External.RESTART
            elif self._told_to_be_killed:
                return JobStopReasons.External.KILLING
            else:
                return JobStopReasons.External.UNKNOWN


@singletonjob
@_sysjob
class JobManagerJob(IntervalJobBase):
    """A singleton job that represents the job manager. Its very high permission
    level and internal protections prevents it from being instantiated
    or modified by other jobs.
    """

    def __init__(self):
        super().__init__()
        self._identifier = STANDARD_JOB_IDENTIFIERS["JobManagerJob"]

    async def on_run(self):
        await self.await_done()


from . import proxies, groupings  # allow this module to finish initialization
