"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file implements a job manager class for running and managing job objects
at runtime. 
"""

from __future__ import annotations
import asyncio
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from collections import deque
import datetime
from functools import partial
import itertools
import inspect
import pickle
import re
import time
from typing import (
    Any,
    Callable,
    Coroutine,
    Iterable,
    Literal,
    Optional,
    Sequence,
    Type,
    Union,
)

import discord
from discord.ext import tasks
from pgbot.jobs.core.events.base_events import BaseEvent

from pgbot.utils import utils
from pgbot import common, db

from . import events, base_jobs
from .base_jobs import (
    JobProxy,
    Job,
    EventJob,
    ClientEventJob,
    IntervalJob,
    SingletonJobBase,
    JobManagerJob,
    JobError,
    JobStateError,
    JobInitializationError,
    JobPermissionError,
    JOB_VERBS,
    PERMISSION_LEVELS,
    get_job_class_id,
    get_job_class_permission_level,
)

client = common.bot


class JobManager:
    """The job manager for all interval jobs and event jobs.
    It acts as a container for interval and event job objects,
    whilst also being responsible dispatching events to event job objects.
    Each of the jobs that a job manager contains can use a proxy to
    register new job objects that they instantiate at runtime.
    """

    def __init__(self, loop=None, global_job_timeout: Optional[float] = None):
        """Create a new job manager instance.

        Args:
            loop: The event loop to use. Defaults to None.
            global_job_timeout (Optional[float]):
                The default global job timeout in seconds.
                Defaults to None.
        """
        if loop is None:
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                self._loop = asyncio.get_event_loop()

        self._created_at = datetime.datetime.now(datetime.timezone.utc)
        self._identifier = (
            f"{id(self)}-" f"{int(self._created_at.timestamp()*1_000_000_000)}"
        )

        self._loop = loop
        self._event_job_ids = {}
        self._interval_job_ids = set()
        self._job_type_count_dict = {}
        self._job_id_map = {}
        self._manager_job = None
        self._thread_pool_executor = ThreadPoolExecutor(max_workers=4)
        self._thread_pool_executor_lock = asyncio.Lock()
        self._process_pool_executor = ProcessPoolExecutor(max_workers=4)
        self._process_pool_executor_lock = asyncio.Lock()
        self._event_waiting_queues = {}
        self._schedule_dict = {0: {}}
        # zero timestamp for failed scheduling attempts
        self._schedule_ids = set()
        self._schedule_dict_fails = {}
        self._schedule_dict_lock = asyncio.Lock()
        self._running = True
        self._initialized = False
        self._scheduling_is_initialized = False
        self._scheduling_initialized_futures = []
        self._scheduling_uninitialized_futures = []

        if global_job_timeout:
            global_job_timeout = float(global_job_timeout)

        self._global_job_stop_timeout = global_job_timeout

    @property
    def identifier(self):
        return self._identifer

    def set_event_loop(self, loop):
        """
        Args:
            loop (AbstractEventLoop): The loop this job is meant to use.

        Raises:
            TypeError: Invalid object given as input
        """
        if not isinstance(loop, asyncio.AbstractEventLoop):
            raise TypeError(
                "invalid event loop, must be a subclass of asyncio.AbstractEventLoop"
            ) from None
        self._loop = loop

    def is_running(self):
        """Whether this job manager is currently running.

        Returns:
            bool: True/False
        """
        return self._running

    def initialized(self):
        """Whether this job manager is currently running.

        Returns:
            bool: True/False
        """
        return self._initialized

    def get_global_job_stop_timeout(self):
        """Get the maximum time period in seconds for job objects to stop
        when halted from this manager, either due to being stopped,
        restarted or killed.

        Returns:
            float: The timeout in seconds.
            None: No timeout is currently set.
        """
        return self._global_job_stop_timeout

    def set_global_job_stop_timeout(self, timeout: Optional[float]):
        """Set the maximum time period in seconds for job objects to stop
        when halted from this manager, either due to being stopped,
        restarted or killed.

        Args:
            timeout (Union[float, None]): The timeout in seconds,
            or None to clear any previous timeout.
        """

        if timeout:
            timeout = float(timeout)
        self._global_job_stop_timeout = timeout

    @staticmethod
    def unpickle_dict(byte_data):
        unpickled_data = pickle.loads(byte_data)

        if not isinstance(unpickled_data, dict):
            raise TypeError(
                f"invalid object of type '{unpickled_data.__class__}' in pickle data, must be of type 'dict'"
            )
        return unpickled_data

    @staticmethod
    def pickle_dict(target_dict):
        if not isinstance(target_dict, dict):
            raise TypeError(
                f"argument 'target_dict' must be of type 'dict',"
                f" not {target_dict.__class__}"
            )

        pickled_data = pickle.dumps(target_dict)
        return pickled_data

    async def initialize(self):
        """Initialize this job manager, if it hasn't yet been initialized."""

        if not self._initialized:
            self._initialized = True
            self._manager_job = self._get_job_from_proxy(
                await self.create_and_register_job(JobManagerJob)
            )

    async def job_scheduling_loop(self):
        """Run one iteration of the job scheduling loop of this
        job manager object.
        """

        async with self._schedule_dict_lock:
            deletion_list = []
            for i, timestamp_ns_str in enumerate(tuple(self._schedule_dict.keys())):
                timestamp_ns = int(timestamp_ns_str)
                if timestamp_ns <= 0:
                    continue
                if isinstance(self._schedule_dict[timestamp_ns_str], bytes):
                    timestamp_num_pickle_data = self._schedule_dict[timestamp_ns_str]
                    async with self._process_pool_executor_lock:
                        self._schedule_dict[
                            timestamp_ns
                        ] = await self._loop.run_in_executor(
                            self._process_pool_executor,
                            self.unpickle_dict,
                            timestamp_num_pickle_data,
                        )

                timestamp = timestamp_ns / 1_000_000_000
                now = time.time()
                if now >= timestamp:
                    for j, schedule_kv_pair in enumerate(
                        self._schedule_dict[timestamp_ns_str].items()
                    ):
                        schedule_identifier, schedule_data = schedule_kv_pair

                        if isinstance(schedule_data, bytes):
                            schedule_pickle_data = schedule_data
                            async with self._process_pool_executor_lock:
                                self._schedule_dict[timestamp_ns_str][
                                    schedule_identifier
                                ] = schedule_data = await self._loop.run_in_executor(
                                    self._process_pool_executor,
                                    self.unpickle_dict,
                                    schedule_pickle_data,
                                )

                        if schedule_data["recur_interval"]:
                            try:
                                if now < timestamp + (
                                    (schedule_data["recur_interval"] / 1_000_000_000)
                                    * schedule_data["occurences"]
                                ):
                                    continue
                            except OverflowError as e:
                                print(
                                    f"Job scheduling for {schedule_identifier} failed: Too high recurring timestamp value",
                                    utils.format_code_exception(e),
                                )
                                deletion_list.append(schedule_identifier)
                                self._schedule_ids.remove(schedule_identifier)
                                self._schedule_dict[0][
                                    schedule_identifier
                                ] = schedule_data
                                continue

                        try:
                            job_class = base_jobs.get_job_class_from_id(
                                schedule_data["class_id"], closest_match=True
                            )
                        except KeyError:
                            print(
                                f"Job initiation failed: Could not find job type called '{schedule_data['class_id']}'"
                            )
                            deletion_list.append(schedule_identifier)
                            self._schedule_ids.remove(schedule_identifier)
                            self._schedule_dict[0][schedule_identifier] = schedule_data
                            continue

                        try:
                            job = self.create_job(
                                job_class,
                                *schedule_data["job_args"],
                                _return_proxy=False,
                                **schedule_data["job_kwargs"],
                            )
                            job._schedule_identifier = schedule_identifier
                        except Exception as e:
                            print(
                                "Job initiation failed due to an exception:\n"
                                + utils.format_code_exception(e),
                            )

                            deletion_list.append(schedule_identifier)
                            self._schedule_ids.remove(schedule_identifier)
                            self._schedule_dict[0][schedule_identifier] = schedule_data
                            continue
                        else:
                            try:
                                await self.register_job(job)
                            except Exception as e:
                                print(
                                    "Job registration failed due to an exception:\n"
                                    + utils.format_code_exception(e),
                                )

                                deletion_list.append(schedule_identifier)
                                self._schedule_ids.remove(schedule_identifier)
                                self._schedule_dict[0][
                                    schedule_identifier
                                ] = schedule_data
                                continue

                            schedule_data["occurences"] += 1

                        if not schedule_data["recur_interval"] or (
                            schedule_data["max_recurrences"] != -1
                            and schedule_data["occurences"]
                            > schedule_data["max_recurrences"]
                        ):
                            deletion_list.append(schedule_identifier)
                            self._schedule_ids.remove(schedule_identifier)

                        # if j % 20:
                        #    await asyncio.sleep(0)

                    for schedule_id_key in deletion_list:
                        del self._schedule_dict[timestamp_ns_str][schedule_id_key]

                    deletion_list.clear()

                if not self._schedule_dict[timestamp_ns_str]:
                    del self._schedule_dict[timestamp_ns_str]

                # if i % 10:
                #    await asyncio.sleep(0)

    @staticmethod
    def _dump_job_scheduling_data_helper(data_set, data_dict):
        return pickle.dumps({"identifiers": list(data_set), "data": data_dict})

    async def dump_job_scheduling_data(self):
        """Return the current job scheduling data as
        a `bytes` object of pickled data.

        Returns:
            bytes: The scheduling data.
        """

        dump_dict = {}

        async with self._schedule_dict_lock:
            for timestamp_ns_str, schedules_dict in self._schedule_dict.items():
                if timestamp_ns_str not in dump_dict:
                    dump_dict[timestamp_ns_str] = {}

                if isinstance(schedules_dict, dict):
                    for scheduling_id, schedule_dict in schedules_dict.items():
                        if isinstance(schedule_dict, dict):
                            async with self._process_pool_executor_lock:
                                dump_dict[timestamp_ns_str][
                                    scheduling_id
                                ] = await self._loop.run_in_executor(
                                    self._process_pool_executor,
                                    self.pickle_dict,
                                    schedule_dict,
                                )

                        elif isinstance(schedule_dict, bytes):
                            dump_dict[timestamp_ns_str][scheduling_id] = schedule_dict

                    async with self._process_pool_executor_lock:
                        dump_dict[timestamp_ns_str] = await self._loop.run_in_executor(
                            self._process_pool_executor,
                            self.pickle_dict,
                            dump_dict[timestamp_ns_str],
                        )

                elif isinstance(schedules_dict, bytes):
                    dump_dict[timestamp_ns_str] = schedules_dict

        result = None

        del dump_dict[0]  # don't export error schedulings

        async with self._process_pool_executor_lock:
            result = await self._loop.run_in_executor(
                self._process_pool_executor,
                self._dump_job_scheduling_data_helper,
                self._schedule_ids.copy(),
                dump_dict,
            )
        return result

    async def load_job_scheduling_data(
        self,
        data: Union[bytes, dict],
        dezerialize_mode: Union[Literal["PARTIAL"], Literal["FULL"]] = "PARTIAL",
        overwrite=False,
    ):
        """Load the job scheduling data for this job object from pickled
        `bytes` data, or an unpickled dictionary.

        The job scheduling data must be structured as follows:

        ```py
        {
            "identifiers": [..., '123456789-42069-69420', '556456789-52069-6969', ...],
            "data": {
                ...: ...,
                "420": { # unix integer timestamp string in nanoseconds
                    ...: ...,
                    '123456789-42069-69420': ...,
                    '556456789-52069-6969': {
                        "schedule_identifier": '556456789-52069-6969696969',
                        "scheduler_identifier": '556456789-53223236969',
                        "schedule_timestamp_ns_str": "6969",
                        "timestamp_ns_str": "52069",
                        "recur_interval": 878787, # in seconds
                        "occurences": 0,
                        "max_recurrences": 10,
                        "class_id": "AddReaction-1234567876",
                        "job_args": (..., ...),
                        "job_kwargs": {...: ..., ...},
                        }
                    },
                    ...: ...,
                },
                ...: ...,
            }
        }
        ```

        Args:
            data (Union[bytes, dict]):
                The data.

            overwrite (bool):
                Whether any previous schedule data should be overwritten with new data.
                If set to `False`, attempting to add unto preexisting data will
                raise a `RuntimeError`. Defaults to False.

        Raises:
            RuntimeError:
                Job scheduling is already initialized, or there is
                potential schedule data that might be unintentionally overwritten.

            TypeError: Invalid type for `data`.
            TypeError: Invalid structure of `data`.
        """

        if self._scheduling_is_initialized:
            raise RuntimeError(
                "cannot load scheduling data" f" while job scheduling is initialized."
            )

        elif len(self._schedule_dict) > 1 and not overwrite:
            raise RuntimeError(
                "unintentional overwrite of preexisting scheduling data"
                " was prevented"
            )

        data_dict = None
        data_set = None

        if isinstance(data, bytes):
            async with self._process_pool_executor_lock:
                data = await self._loop.run_in_executor(
                    self._process_pool_executor, pickle.loads, data
                )

        if isinstance(data, dict):
            data_set, data_dict = data["identifiers"].copy(), data["data"].copy()
            # copy for the case where unpickled data was passed in
            data_set = set(data_set)
        else:
            raise TypeError(
                f"argument 'data' must be of type 'dict' or 'bytes'"
                f" (pickle data of a list), not {data.__class__.__name__}"
            )

        for timestamp_ns_str, schedules_dict in data_dict.items():
            if isinstance(schedules_dict, bytes) and dezerialize_mode.startswith(
                ("PARTIAL", "FULL")
            ):
                async with self._process_pool_executor_lock:
                    data_dict[
                        timestamp_ns_str
                    ] = schedules_dict = await self._loop.run_in_executor(
                        self._process_pool_executor,
                        self.unpickle_dict,
                        schedules_dict,
                    )

            if isinstance(schedules_dict, dict):
                for scheduling_id, schedule_dict in schedules_dict.items():
                    if isinstance(schedule_dict, bytes) and dezerialize_mode == "FULL":
                        async with self._process_pool_executor_lock:
                            data_dict[timestamp_ns_str][
                                scheduling_id
                            ] = await self._loop.run_in_executor(
                                self._process_pool_executor,
                                self.unpickle_dict,
                                schedule_dict,
                            )

        async with self._schedule_dict_lock:
            self._schedule_ids = data_set
            self._schedule_dict.clear()
            self._schedule_dict.update(data_dict)
            if 0 not in self._schedule_dict:
                self._schedule_dict[0] = {}

    def initialize_job_scheduling(self):
        """Initialize the job scheduling process of this job manager."""
        if not self._scheduling_is_initialized:
            self._scheduling_is_initialized = True
            for fut in self._scheduling_initialized_futures:
                if not fut.cancelled():
                    fut.set_result(True)

    def job_scheduling_is_initialized(self):
        """Whether the job scheduling process of this job manager is initialized."""
        return self._scheduling_is_initialized

    def wait_for_job_scheduling_initialization(self, timeout: Optional[float] = None):
        """This method returns a coroutine that can be used to wait until job scheduling
        is initialized.

        Raises:
            RuntimeError: Job scheduling is already initialized.

        Returns:
            Coroutine: A coroutine that evaluates to `True`.
        """

        if not self._scheduling_is_initialized:
            fut = self._loop.create_future()
            self._scheduling_initialized_futures.append(fut)
            return asyncio.wait_for(fut, timeout)

        raise RuntimeError("Job scheduling is already initialized.")

    def wait_for_job_scheduling_uninitialization(self, timeout: Optional[float] = None):
        """This method returns a coroutine that can be used to wait until job scheduling
        is uninitialized.

        Raises:
            RuntimeError: Job scheduling is not initialized.

        Returns:
            Coroutine: A coroutine that evaluates to `True`.
        """

        if self._scheduling_is_initialized:
            fut = self._loop.create_future()
            self._scheduling_uninitialized_futures.append(fut)
            return asyncio.wait_for(fut, timeout)

        raise RuntimeError("Job scheduling is not initialized.")

    def uninitialize_job_scheduling(self):
        """End the job scheduling process of this job manager."""
        if self._scheduling_is_initialized:
            self._scheduling_is_initialized = False

        for fut in self._scheduling_initialized_futures:
            if not fut.cancelled():
                fut.cancel(f"initialization was aborted")

        for fut in self._scheduling_uninitialized_futures:
            if not fut.cancelled():
                fut.set_result(True)

    def _verify_permissions(
        self,
        invoker: Union[EventJob, IntervalJob],
        op: str,
        target: Union[EventJob, IntervalJob] = None,
        target_cls=None,
        schedule_identifier=None,
        scheduler_identifier=None,
        raise_exceptions=True,
    ):

        invoker_cls = invoker.__class__

        target_cls = target.__class__ if target else target_cls

        invoker_cls_permission_level = get_job_class_permission_level(invoker_cls)

        target_cls_permission_level = None
        if not isinstance(op, str):
            raise TypeError(
                "argument 'op' must be a string defined in the 'JOB_VERBS' class namespace"
            )

        elif op not in JOB_VERBS.__dict__:
            raise ValueError(
                "argument 'op' must be a string defined in the 'JOB_VERBS' class namespace"
            )

        elif (
            op.startswith(JOB_VERBS.FIND)
            and invoker_cls_permission_level < PERMISSION_LEVELS.LOW
        ):
            if raise_exceptions:
                raise JobPermissionError(
                    f"insufficient permission level of {invoker_cls.__name__}"
                    f" ({PERMISSION_LEVELS.get_name(invoker_cls_permission_level)})"
                    f" for {JOB_VERBS._PRESENT_CONTINUOUS_TENSE[op]} job objects"
                )
            return False

        elif op.startswith(JOB_VERBS.UNSCHEDULE):
            if schedule_identifier is None or scheduler_identifier is None:
                raise TypeError(
                    "argument 'schedule_identifier' and 'scheduler_identifier'"
                    " cannot be None if argument 'op' is 'UNSCHEDULE'"
                )

            if invoker_cls_permission_level < PERMISSION_LEVELS.MEDIUM:
                if raise_exceptions:
                    raise JobPermissionError(
                        f"insufficient permission level of {invoker_cls.__name__}"
                        f" ({PERMISSION_LEVELS.get_name(invoker_cls_permission_level)})"
                        f" for {JOB_VERBS._PRESENT_CONTINUOUS_TENSE[op]} job objects"
                    )
                return False

            if (
                scheduler_identifier in self._job_id_map
            ):  # the schedule operation belongs to an alive job
                target = self._job_id_map[scheduler_identifier]
                # the target is now the job that scheduled a specific operation
                target_cls = target.__class__

                target_cls_permission_level = get_job_class_permission_level(target_cls)

                if (
                    invoker_cls_permission_level == PERMISSION_LEVELS.MEDIUM
                    and invoker._identifier != scheduler_identifier
                ):
                    if raise_exceptions:
                        raise JobPermissionError(
                            f"insufficient permission level of '{invoker_cls.__name__}'"
                            f" ({PERMISSION_LEVELS.get_name(invoker_cls_permission_level)})"
                            f" for {JOB_VERBS._PRESENT_CONTINUOUS_TENSE[op]}"
                            f" jobs that were scheduled by the class '{target_cls.__name__}'"
                            f" ({PERMISSION_LEVELS.get_name(target_cls_permission_level)})"
                            " when the scheduler job is still alive and is not the"
                            " invoker job"
                        )
                    return False

                elif (
                    invoker_cls_permission_level == PERMISSION_LEVELS.HIGH
                    and target_cls_permission_level >= PERMISSION_LEVELS.HIGH
                ):
                    if raise_exceptions:
                        raise JobPermissionError(
                            f"insufficient permission level of '{invoker_cls.__name__}'"
                            f" ({PERMISSION_LEVELS.get_name(invoker_cls_permission_level)})"
                            f" for {JOB_VERBS._PRESENT_CONTINUOUS_TENSE[op]}"
                            f" jobs that were scheduled by the class '{target_cls.__name__}'"
                            f" ({PERMISSION_LEVELS.get_name(target_cls_permission_level)})"
                        )
                    return False

        if op.startswith(
            (
                JOB_VERBS.CREATE,
                JOB_VERBS.INITIALIZE,
                JOB_VERBS.REGISTER,
                JOB_VERBS.SCHEDULE,
            )
        ):
            target_cls_permission_level = get_job_class_permission_level(target_cls)

            if invoker_cls_permission_level < PERMISSION_LEVELS.MEDIUM:
                if raise_exceptions:
                    raise JobPermissionError(
                        f"insufficient permission level of {invoker_cls.__name__}"
                        f" ({PERMISSION_LEVELS.get_name(invoker_cls_permission_level)})"
                        f" for {JOB_VERBS._PRESENT_CONTINUOUS_TENSE[op]} job objects"
                    )
                return False

            elif invoker_cls_permission_level == PERMISSION_LEVELS.MEDIUM:
                if target_cls_permission_level >= PERMISSION_LEVELS.MEDIUM:
                    if raise_exceptions:
                        raise JobPermissionError(
                            f"insufficient permission level of '{invoker_cls.__name__}'"
                            f" ({PERMISSION_LEVELS.get_name(invoker_cls_permission_level)})"
                            f" for {JOB_VERBS._PRESENT_CONTINUOUS_TENSE[op]}"
                            f" job objects of the specified class '{target_cls.__name__}'"
                            f" ({PERMISSION_LEVELS.get_name(target_cls_permission_level)})"
                        )
                    return False

            elif (
                invoker_cls_permission_level == PERMISSION_LEVELS.HIGH
                and target_cls_permission_level > PERMISSION_LEVELS.HIGH
            ) or (
                invoker_cls_permission_level == PERMISSION_LEVELS.HIGHEST
                and target_cls_permission_level > PERMISSION_LEVELS.HIGHEST
            ):
                if raise_exceptions:
                    raise JobPermissionError(
                        f"insufficient permission level of '{invoker_cls.__name__}'"
                        f" ({PERMISSION_LEVELS.get_name(invoker_cls_permission_level)})"
                        f" for {JOB_VERBS._PRESENT_CONTINUOUS_TENSE[op]}"
                        f" job objects of the specified class '{target_cls.__name__}'"
                        f" ({PERMISSION_LEVELS.get_name(target_cls_permission_level)})"
                    )
                return False

        elif op.startswith((JOB_VERBS.GUARD, JOB_VERBS.UNGUARD)):

            if target is None:
                raise TypeError(
                    "argument 'target'"
                    " cannot be None if argument 'op' is 'START',"
                    " 'RESTART', 'STOP' 'KILL', 'GUARD' or 'UNGUARD'"
                )

            target_cls_permission_level = get_job_class_permission_level(target_cls)

            if invoker_cls_permission_level < PERMISSION_LEVELS.HIGH:
                if raise_exceptions:
                    raise JobPermissionError(
                        f"insufficient permission level of {invoker_cls.__name__}"
                        f" ({PERMISSION_LEVELS.get_name(invoker_cls_permission_level)})"
                        f" for {JOB_VERBS._PRESENT_CONTINUOUS_TENSE[op]} job objects"
                    )
                return False

            elif invoker_cls_permission_level in (
                PERMISSION_LEVELS.HIGH,
                PERMISSION_LEVELS.HIGHEST,
            ):
                if target._creator is not invoker:
                    if raise_exceptions:
                        raise JobPermissionError(
                            f"insufficient permission level of '{invoker_cls.__name__}'"
                            f" ({PERMISSION_LEVELS.get_name(invoker_cls_permission_level)})"
                            f" for {JOB_VERBS._PRESENT_CONTINUOUS_TENSE[op]}"
                            f" job objects of the specified class '{target_cls.__name__}'"
                            f" ({PERMISSION_LEVELS.get_name(target_cls_permission_level)})"
                            " its instance did not create."
                        )
                    return False

        elif op.startswith(
            (
                JOB_VERBS.START,
                JOB_VERBS.RESTART,
                JOB_VERBS.STOP,
                JOB_VERBS.KILL,
            )
        ):
            if target is None:
                raise TypeError(
                    "argument 'target'"
                    " cannot be None if argument 'op' is 'START',"
                    " 'RESTART', 'STOP' 'KILL' or 'GUARD'"
                )

            target_cls_permission_level = get_job_class_permission_level(target_cls)

            if invoker_cls_permission_level < PERMISSION_LEVELS.MEDIUM:
                raise JobPermissionError(
                    f"insufficient permission level of {invoker_cls.__name__}"
                    f" ({PERMISSION_LEVELS.get_name(invoker_cls_permission_level)})"
                    f" for {JOB_VERBS._PRESENT_CONTINUOUS_TENSE[op]} job objects"
                )
            elif invoker_cls_permission_level == PERMISSION_LEVELS.MEDIUM:
                if (
                    target_cls_permission_level < PERMISSION_LEVELS.MEDIUM
                    and target._creator is not invoker
                ):
                    if raise_exceptions:
                        raise JobPermissionError(
                            f"insufficient permission level of '{invoker_cls.__name__}'"
                            f" ({PERMISSION_LEVELS.get_name(invoker_cls_permission_level)})"
                            f" for {JOB_VERBS._PRESENT_CONTINUOUS_TENSE[op]}"
                            f" job objects of the specified class '{target_cls.__name__}'"
                            f" ({PERMISSION_LEVELS.get_name(target_cls_permission_level)}) that"
                            " its instance did not create."
                        )
                    return False

                elif target_cls_permission_level >= PERMISSION_LEVELS.MEDIUM:
                    if raise_exceptions:
                        raise JobPermissionError(
                            f"insufficient permission level of '{invoker_cls.__name__}'"
                            f" ({PERMISSION_LEVELS.get_name(invoker_cls_permission_level)})"
                            f" for {JOB_VERBS._PRESENT_CONTINUOUS_TENSE[op]}"
                            f" job objects of the specified class '{target_cls.__name__}'"
                            f" ({PERMISSION_LEVELS.get_name(target_cls_permission_level)})"
                        )
                    return False

            elif invoker_cls_permission_level == PERMISSION_LEVELS.HIGH:
                if target_cls_permission_level >= PERMISSION_LEVELS.HIGH:
                    if raise_exceptions:
                        raise JobPermissionError(
                            f"insufficient permission level of '{invoker_cls.__name__}'"
                            f" ({PERMISSION_LEVELS.get_name(invoker_cls_permission_level)})"
                            f" for {JOB_VERBS._PRESENT_CONTINUOUS_TENSE[op]}"
                            f" job objects of the specified class '{target_cls.__name__}'"
                            f" ({PERMISSION_LEVELS.get_name(target_cls_permission_level)})"
                        )
                    return False

            elif invoker_cls_permission_level == PERMISSION_LEVELS.HIGHEST:
                if target_cls_permission_level > PERMISSION_LEVELS.HIGHEST:
                    if raise_exceptions:
                        raise JobPermissionError(
                            f"insufficient permission level of '{invoker_cls.__name__}'"
                            f" ({PERMISSION_LEVELS.get_name(invoker_cls_permission_level)})"
                            f" for {JOB_VERBS._PRESENT_CONTINUOUS_TENSE[op]}"
                            f" job objects of the specified class '{target_cls.__name__}'"
                            f" ({PERMISSION_LEVELS.get_name(target_cls_permission_level)})"
                        )
                    return False

        return True

    def create_job(
        self,
        cls: Union[Type[EventJob], Type[IntervalJob]],
        *args,
        _return_proxy=True,
        _invoker: Optional[Union[EventJob, IntervalJob]] = None,
        **kwargs,
    ):
        """Create an instance of a job class, and return it.

        Args:
            cls (Union[Type[EventJob], Type[IntervalJob]]):
               The job class to instantiate a job object from.

        Raises:
            RuntimeError: This job manager object is not initialized.

        Returns:
            JobProxy: A job proxy object.
        """

        if not self._initialized:
            raise RuntimeError("This job manager object is not initialized.")

        if isinstance(_invoker, (EventJob, IntervalJob)):
            self._verify_permissions(_invoker, op=JOB_VERBS.CREATE, target_cls=cls)
        else:
            _invoker = self._manager_job

        job = cls(*args, **kwargs)
        job._manager = JobManagerProxy(self, job)
        job._creator = _invoker
        proxy = job._proxy

        if _return_proxy:
            return proxy
        return job

    def _get_job_from_proxy(self, job_proxy: JobProxy) -> Union[EventJob, IntervalJob]:
        try:
            job = job_proxy._JobProxy__j
        except AttributeError:
            raise TypeError("invalid job proxy") from None
        return job

    async def initialize_job(
        self,
        job_or_proxy: Union[EventJob, IntervalJob, JobProxy],
        raise_exceptions: bool = True,
        _invoker: Optional[Union[EventJob, IntervalJob]] = None,
    ):
        """Initialize this job object.

        Args:
            raise_exceptions (bool, optional):
                Whether exceptions should be raised. Defaults to True.

        Raises:
            JobInitializationError: The job given was already initialized.

        Returns:
            bool: Whether the initialization attempt was successful.
        """

        job = (
            self._get_job_from_proxy(job_or_proxy)
            if isinstance(job_or_proxy, JobProxy)
            else job_or_proxy
        )

        if isinstance(_invoker, (EventJob, IntervalJob)):
            self._verify_permissions(_invoker, op=JOB_VERBS.INITIALIZE, target=job)
        else:
            _invoker = self._manager_job

        if job._is_being_guarded and _invoker is not job._guardian:
            raise JobStateError(
                "the given target job object is being guarded by another job"
            ) from None

        if not job._initialized:
            try:
                await job._INITIALIZE_EXTERNAL()
                job._initialized = True
            except Exception:
                job._initialized = False
                if raise_exceptions:
                    raise
        else:
            if raise_exceptions:
                raise JobInitializationError(
                    "this job object is already initialized"
                ) from None
            else:
                return False

        return job._initialized

    async def register_job(
        self,
        job_or_proxy: Union[EventJob, IntervalJob, JobProxy],
        start: bool = True,
        _invoker: Optional[Union[EventJob, IntervalJob]] = None,
    ):
        """Register a job object to this JobManager,
        while initializing it if necessary.

        Args:
            job (Union[EventJob, IntervalJob, JobProxy]):
                The job object to be registered.
            start (bool):
                Whether the given job object should start automatically
                upon registration.

        Raises:
            JobStateError: Invalid job state for registration.
            JobError: job-specific errors preventing registration.
            RuntimeError: This job manager object is not initialized.
        """

        if not self._initialized:
            raise RuntimeError("This job manager object is not initialized.")

        job = (
            self._get_job_from_proxy(job_or_proxy)
            if isinstance(job_or_proxy, JobProxy)
            else job_or_proxy
        )

        if isinstance(_invoker, (EventJob, IntervalJob)):
            self._verify_permissions(_invoker, op=JOB_VERBS.REGISTER, target=job)
        else:
            _invoker = self._manager_job

        if job._is_being_guarded and _invoker is not job._guardian:
            raise JobStateError(
                "the given target job object is being guarded by another job"
            ) from None

        if job._killed:
            raise JobStateError("cannot register a killed job object")

        if not job._initialized:
            await self.initialize_job(job)

        if (
            isinstance(job, SingletonJobBase)
            and job.__class__._IDENTIFIER in self._job_type_count_dict
            and self._job_type_count_dict[job.__class__._IDENTIFIER]
        ):
            raise JobError(
                "cannot have more than one instance of a"
                " 'SingletonJobBase' job registered at a time."
            )

        self._add_job(job, start=start)
        job._registered_at_ts = time.time()

    async def create_and_register_job(
        self,
        cls: Union[Type[EventJob], Type[IntervalJob]],
        *args,
        start: bool = True,
        _return_proxy: bool = True,
        _invoker: Optional[Union[EventJob, IntervalJob]] = None,
        **kwargs,
    ):
        """Create an instance of a job class, and register it to this `BotTaskManager`.

        Args:
            cls (Union[Type[EventJob], Type[IntervalJob]]):
                The job class to be used for instantiation.
            start (bool):
                Whether the given job object should start automatically
                upon registration.

        Returns:
            JobProxy: A job proxy object.
        """
        j = self.create_job(cls, *args, _return_proxy=False, **kwargs)
        await self.register_job(j, start=start, _invoker=_invoker)
        if _return_proxy:
            return j._proxy

    async def create_job_schedule(
        self,
        cls: Union[Type[EventJob], Type[IntervalJob]],
        timestamp: Union[int, float, datetime.datetime],
        recur_interval: Optional[Union[int, float, datetime.timedelta]] = None,
        max_recurrences: int = -1,
        job_args: tuple = (),
        job_kwargs: Optional[dict] = None,
        _invoker: Optional[Union[EventJob, IntervalJob]] = None,
    ):
        """Schedule a job of a specific type to be instantiated and to run at
        one or more specific periods of time. Each job can receive positional
        or keyword arguments which are passed to this method.
        Those arguments must be pickleable.

        Args:
            cls (Union[Type[EventJob], Type[IntervalJob]]): The job type to schedule.
            timestamp (Union[int, float, datetime.datetime]):
                The exact timestamp or offset at which to instantiate a job.
            recur_interval (Optional[Union[int, float, datetime.timedelta]]):
                The interval at which a job should be rescheduled in seconds.
                `None` or 0 means that no recurrences will occur. -1 means that
                the smallest possible recur interval should be used.
                Defaults to None.
            max_recurrences (int):
                The maximum amount of recurrences for rescheduling.
                A value of -1 means that no maximum is set. Otherwise, the value
                of this argument must be a non-zero positive integer.
                If no `recur_interval` value was provided, the value of this argument
                will be ignored during scheduling and set to -1.
                Defaults to -1.
            job_args (tuple, optional):
                Positional arguments to pass to the scheduled job upon
                instantiation. Defaults to ().
            job_kwargs (dict, optional):
                Keyword arguments to pass to the scheduled job upon instantiation.
                Defaults to None.

        Raises:
            RuntimeError:
                The job manager has not yet initialized job scheduling,
                or this job manager object is not initialized.
            TypeError: Invalid argument types were given.

        Returns:
            str: The string identifier of the scheduling operation
        """

        if not issubclass(cls, (EventJob, IntervalJob)):
            raise TypeError(
                f"argument 'cls' must be of a subclass of 'EventJob' or 'IntervalJob', not '{cls}'"
            ) from None

        if isinstance(_invoker, (EventJob, IntervalJob)):
            self._verify_permissions(_invoker, op=JOB_VERBS.SCHEDULE, target_cls=cls)
        else:
            _invoker = self._manager_job

        if not self._initialized:
            raise RuntimeError("This job manager object is not initialized.")

        elif not self._scheduling_is_initialized:
            raise RuntimeError(
                "JobManager scheduling has not been initialized"
            ) from None

        if isinstance(timestamp, datetime.datetime):
            timestamp = timestamp.astimezone(datetime.timezone.utc)
        elif isinstance(timestamp, (int, float)):
            timestamp = datetime.datetime.fromtimestamp(
                timestamp, tz=datetime.timezone.utc
            )
        else:
            raise TypeError(
                "argument 'timestamp' must be a datetime.datetime or a positive real number"
            ) from None

        timestamp_ns = int(timestamp.timestamp() * 1_000_000_000)  # save time in ns
        timestamp_ns_str = f"{timestamp_ns}"

        recur_interval_num = None

        if recur_interval is None or recur_interval == 0:
            recur_interval_num = 0

        elif isinstance(recur_interval, (int, float)) and (
            recur_interval == -1 or recur_interval > 0
        ):
            if recur_interval > 0:
                recur_interval_num = int(recur_interval * 1_000_000_000)
                # save time difference in ns
            else:
                recur_interval_num = -1

        elif isinstance(recur_interval, datetime.timedelta) and (
            recur_interval.total_seconds() == -1 or recur_interval.total_seconds() >= 0
        ):
            if recur_interval.total_seconds() >= 0:
                recur_interval_num = int(recur_interval.total_seconds() * 1_000_000_000)
            else:
                recur_interval_num = -1
        else:
            raise TypeError(
                "argument 'recur_interval' must be None, 0, -1, a positive real number"
                " (in seconds) or a datetime.timedelta object with either a value"
                " of -1 seconds, or a positive value"
            ) from None

        if not isinstance(max_recurrences, int) or (
            max_recurrences != -1 and max_recurrences <= 0
        ):
            raise TypeError(
                "argument 'max_recurrences' must be -1 or a non-zero positive real"
                f" number of type 'int', not {type(job_args).__name__}"
            ) from None

        if not isinstance(job_args, (list, tuple)):
            if job_args is None:
                job_args = ()
            else:
                raise TypeError(
                    f"'job_args' must be of type 'tuple', not {type(job_args).__name__}"
                ) from None

        elif not isinstance(job_kwargs, dict):
            if job_kwargs is None:
                job_kwargs = {}
            else:
                raise TypeError(
                    f"'job_kwargs' must be of type 'dict', not {type(job_kwargs)}"
                ) from None

        schedule_timestamp_ns_str = str(
            int(
                datetime.datetime.now(datetime.timezone.utc).timestamp() * 1_000_000_000
            )
        )

        new_data = {
            "scheduler_identifier": _invoker.identifier if _invoker is not None else "",
            "schedule_identifier": "",
            "schedule_timestamp_ns_str": schedule_timestamp_ns_str,
            "timestamp_ns_str": timestamp_ns_str,
            "recur_interval": recur_interval_num,
            "occurences": 0,
            "max_recurrences": max_recurrences,
            "class_id": get_job_class_id(cls),
            "job_args": tuple(job_args),
            "job_kwargs": job_kwargs if job_kwargs is not None else {},
        }

        new_data["schedule_identifier"] = schedule_identifier = (
            f"{self._identifier}-" f"{timestamp_ns_str}-" f"{schedule_timestamp_ns_str}"
        )

        async with self._schedule_dict_lock:
            if timestamp_ns_str not in self._schedule_dict:
                self._schedule_dict[timestamp_ns_str] = {}

            self._schedule_dict[timestamp_ns_str][schedule_identifier] = new_data
            self._schedule_ids.add(schedule_identifier)

        return schedule_identifier

    def get_job_schedule_identifiers(self):
        """Return a tuple of all job schedule identifiers pointing to
        scheduling data.

        Returns:
            tuple: The job schedule identifiers.
        """

        return tuple(self._schedule_ids)

    def job_schedule_has_failed(self, schedule_identifier: str):
        """Whether the job schedule operation with the specified schedule
        identifier failed.

        Args:
            schedule_identifier (str):
                A string identifier following this structure:
                'JOB_MANAGER_IDENTIFIER-TARGET_TIMESTAMP_IN_NS-SCHEDULING_TIMESTAMP_IN_NS'

        Raises:
            ValueError: Invalid schedule identifier.

        Returns:
            bool: True/False
        """

        split_id = schedule_identifier.split("-")

        if len(split_id) != 4 and not all(s.isnumeric() for s in split_id):
            raise ValueError("invalid schedule identifier")

        return schedule_identifier in self._schedule_dict[0]

    def has_job_schedule(self, schedule_identifier: str):
        """Whether the job schedule operation with the specified schedule
        identifier exists.

        Args:
            schedule_identifier (str):
                A string identifier following this structure:
                'JOB_MANAGER_IDENTIFIER-TARGET_TIMESTAMP_IN_NS-SCHEDULING_TIMESTAMP_IN_NS'

        Raises:
            ValueError: Invalid schedule identifier.

        Returns:
            bool: Whether the schedule identifier leads to existing scheduling data.
        """

        split_id = schedule_identifier.split("-")

        if len(split_id) != 4 and not all(s.isnumeric() for s in split_id):
            raise ValueError("invalid schedule identifier")

        return schedule_identifier in self._schedule_ids

    async def remove_job_schedule(
        self,
        schedule_identifier: str,
        _invoker: Optional[Union[EventJob, IntervalJob]] = None,
    ):
        """Remove a job schedule operation using the string identifier
        of the schedule operation.

        Args:
            schedule_identifier (str):
                A string identifier following this structure:
                'JOB_MANAGER_IDENTIFIER-TARGET_TIMESTAMP_IN_NS-SCHEDULING_TIMESTAMP_IN_NS'

        Raises:
            ValueError: Invalid schedule identifier.
            KeyError: No operation matching the given schedule identifier was found.
        """

        split_id = schedule_identifier.split("-")

        if len(split_id) != 4 and not all(s.isnumeric() for s in split_id):
            raise ValueError("invalid schedule identifier")

        (
            mgr_id_start,
            mgr_id_end,
            timestamp_num_str,
            schedule_num_str,
        ) = split_id

        mgr_identifier = f"{mgr_id_start}-{mgr_id_end}"

        target_timestamp_num = int(timestamp_num_str)

        async with self._schedule_dict_lock:
            if target_timestamp_num in self._schedule_dict:
                schedules_data = self._schedule_dict[target_timestamp_num]
                if isinstance(schedules_data, bytes):
                    async with self._process_pool_executor_lock:
                        self._schedule_dict[
                            target_timestamp_num
                        ] = await self._loop.run_in_executor(
                            self._process_pool_executor,
                            self.unpickle_dict,
                            schedules_data,
                        )

                if schedule_identifier in self._schedule_dict[target_timestamp_num]:
                    if isinstance(_invoker, (EventJob, IntervalJob)):
                        scheduler_identifier = self._schedule_dict[
                            target_timestamp_num
                        ][schedule_identifier]["scheduler_identifier"]
                        self._verify_permissions(
                            _invoker,
                            op=JOB_VERBS.UNSCHEDULE,
                            schedule_identifier=schedule_identifier,
                            scheduler_identifier=scheduler_identifier,
                        )
                    else:
                        _invoker = None

                    del self._schedule_dict[target_timestamp_num][schedule_identifier]
                    self._schedule_ids.remove(schedule_identifier)

            raise KeyError(
                f"cannot find any scheduled operation with the identifier '{schedule_identifier}'"
            )

    async def clear_job_schedules(
        self,
        _invoker: Optional[Union[EventJob, IntervalJob]] = None,
    ):
        """Remove all job schedule operations. This obviously can't
        be undone. This will stop job scheduling, clear data, and restart
        it again when done if it was running.
        """

        was_init = self._scheduling_is_initialized

        if was_init:
            self.uninitialize_job_scheduling()
            await self.wait_for_job_scheduling_uninitialization()

        async with self._schedule_dict_lock:
            fails = self._schedule_dict[0]
            fails.clear()
            self._schedule_dict.clear()
            self._schedule_dict[0] = fails
            self._schedule_ids.clear()

        if was_init:
            self.initialize_job_scheduling()

    def __iter__(self):
        return iter(self._job_id_map)

    def _add_job(
        self,
        job: Union[EventJob, IntervalJob],
        start: bool = True,
    ):
        """
        THIS METHOD IS ONLY MEANT FOR INTERNAL USE BY THIS CLASS.
        Add the given job object to this job manager, and start it.

        Args:
            job: Union[EventJob, IntervalJob]:
                The job to add.
            start (bool, optional):
                Whether a given interval job object should start immediately
                after being added. Defaults to True.
        Raises:
            TypeError: An invalid object was given as a job.
            JobStateError: A job was given that had already ended.
            RuntimeError:
                A job was given that was already present in the
                manager, or this job manager has not been initialized.
            JobInitializationError: An uninitialized job was given as input.
        """

        if not self._initialized:
            raise RuntimeError("This job manager object is not initialized.")

        elif job._completed or job._killed:
            raise JobStateError(
                "cannot add a job that has is not alive to a JobManager instance"
            ) from None

        elif job._identifier in self._job_id_map:
            raise RuntimeError(
                "the given job is already present in this manager"
            ) from None

        elif not job._initialized:
            raise JobInitializationError("the given job was not initialized") from None

        if isinstance(job, EventJob):
            for ce_type in job.EVENT_TYPES:
                if ce_type._IDENTIFIER not in self._event_job_ids:
                    self._event_job_ids[ce_type._IDENTIFIER] = set()
                self._event_job_ids[ce_type._IDENTIFIER].add(job._identifier)

        elif isinstance(job, IntervalJob):
            self._interval_job_ids.add(job._identifier)
        else:
            raise TypeError(
                f"expected an instance of EventJob or IntervalJob subclasses,"
                f" not {job.__class__.__name__}"
            ) from None

        if job.__class__._IDENTIFIER not in self._job_type_count_dict:
            self._job_type_count_dict[job.__class__._IDENTIFIER] = 0

        self._job_type_count_dict[job.__class__._IDENTIFIER] += 1

        self._job_id_map[job._identifier] = job
        job._manager = JobManagerProxy(self, job)

        job._registered_at_ts = time.time()

        if start:
            job._task_loop.start()

    def _remove_job(self, job: Union[EventJob, IntervalJob]):
        """THIS METHOD IS ONLY MEANT FOR INTERNAL USE BY THIS CLASS.
        Remove the given job object from this job manager.

        Args:
            *jobs: Union[EventJob, IntervalJob]:
                The job to be removed, if present.
        Raises:
            TypeError: An invalid object was given as a job.
        """
        if not isinstance(job, (EventJob, IntervalJob)):
            raise TypeError(
                f"expected an instance of class EventJob or IntervalJob"
                f" , not {job.__class__.__name__}"
            ) from None

        if isinstance(job, IntervalJob) and job._identifier in self._interval_job_ids:
            self._interval_job_ids.remove(job._identifier)

        elif isinstance(job, EventJob):
            for ce_type in job.EVENT_TYPES:
                if (
                    ce_type._IDENTIFIER in self._event_job_ids
                    and job._identifier in self._event_job_ids[ce_type._IDENTIFIER]
                ):
                    self._event_job_ids[ce_type._IDENTIFIER].remove(job._identifier)
                if not self._event_job_ids[ce_type._IDENTIFIER]:
                    del self._event_job_ids[ce_type._IDENTIFIER]

        if job._identifier in self._job_id_map:
            del self._job_id_map[job._identifier]

        self._job_type_count_dict[job.__class__._IDENTIFIER] -= 1

        if not self._job_type_count_dict[job.__class__._IDENTIFIER]:
            del self._job_type_count_dict[job.__class__._IDENTIFIER]

    def _remove_jobs(self, *jobs: Union[EventJob, IntervalJob]):
        """
        THIS METHOD IS ONLY MEANT FOR INTERNAL USE BY THIS CLASS.
        Remove the given job objects from this job manager.

        Args:
            *jobs: Union[EventJob, IntervalJob]:
                The jobs to be removed, if present.
        Raises:
            TypeError: An invalid object was given as a job.
        """
        for job in jobs:
            self._remove_job(job)

    def has_job(self, job_or_proxy: Union[EventJob, IntervalJob, JobProxy]):
        """Whether a job is contained in this job manager.

        Args:
            job_or_proxy (Union[EventJob, IntervalJob]): The job object to look for.

        Returns:
            bool: True/False
        """
        job = (
            self._get_job_from_proxy(job_or_proxy)
            if isinstance(job_or_proxy, JobProxy)
            else job_or_proxy
        )
        return job._identifier in self._job_id_map

    def has_identifier(self, identifier: str):
        """Whether a job with the given identifier is contained in this job manager.

        Args:
            identifier (str): The job identifier.

        Returns:
            bool: True/False
        """
        return identifier in self._job_id_map

    def find_job(
        self,
        *,
        identifier: Optional[str] = None,
        created_at: Optional[datetime.datetime] = None,
        _return_proxy: bool = True,
        _invoker: Optional[Union[EventJob, IntervalJob]] = None,
    ):
        """Find the first job that matches the given criteria specified as arguments,
        and return a proxy to it, otherwise return `None`.

        Args:

            identifier (Optional[str]):
                The exact identifier of the job to find. This argument overrides any other parameter below. Defaults to None.

            created_at (Optional[datetime.datetime]):
                The exact creation date of the job to find. Defaults to None.

        Raises:
            TypeError: One of the arguments must be specified.

        Returns:
            JobProxy: The proxy of the job object, if present.
        """

        if isinstance(_invoker, (EventJob, IntervalJob)):
            self._verify_permissions(_invoker, op=JOB_VERBS.FIND)
        else:
            _invoker = self._manager_job

        if identifier is not None:
            if isinstance(identifier, str):
                if identifier in self._job_id_map:
                    if _return_proxy:
                        return self._job_id_map[identifier]._proxy
                    return self._job_id_map[identifier]
                return None

            raise TypeError(
                f"'identifier' must be of type 'str', not {type(identifier)}"
            ) from None

        elif created_at is not None:
            if isinstance(created_at, datetime.datetime):
                for job in self._job_id_map.values():
                    if job.created_at == created_at:
                        return job._proxy if _return_proxy else job
                return None

            raise TypeError(
                f"'created_at' must be of type 'datetime.datetime', not {type(created_at)}"
            ) from None

        raise TypeError(
            f"the arguments 'identifier' and 'created_at' cannot both be None"
        ) from None

    def find_jobs(
        self,
        *,
        classes: Optional[
            Union[
                Type[EventJob],
                Type[IntervalJob],
                tuple[Union[Type[EventJob], Type[IntervalJob]]],
            ]
        ] = None,
        exact_class_match: bool = False,
        created_before: Optional[datetime.datetime] = None,
        created_after: Optional[datetime.datetime] = None,
        permission_level: Optional[int] = None,
        above_permission_level: Optional[int] = None,
        below_permission_level: Optional[int] = None,
        is_starting: Optional[bool] = None,
        is_running: Optional[bool] = None,
        is_idling: Optional[bool] = None,
        is_awaiting: Optional[bool] = None,
        is_being_stopped: Optional[bool] = None,
        is_being_restarted: Optional[bool] = None,
        is_being_killed: Optional[bool] = None,
        is_being_completed: Optional[bool] = None,
        stopped: Optional[bool] = None,
        _return_proxy: bool = True,
        _invoker: Optional[Union[EventJob, IntervalJob]] = None,
    ):
        """Find jobs that match the given criteria specified as arguments,
        and return a tuple of proxy objects to them.

        Args:
            classes: (
                 Optional[
                    Union[
                        Type[EventJob],
                        Type[IntervalJob],
                        tuple[
                            Union[
                                Type[EventJob],
                                Type[IntervalJob]
                            ]
                        ]
                    ]
                ]
            ):
                The class(es) of the job objects to limit the job search to, excluding subclasses. Defaults to None.
            exact_class_match (bool):
                Whether an exact match is required for the classes in the previous parameter,
                or subclasses are allowed too. Defaults to False.

            created_before (Optional[datetime.datetime]):
                The lower age limit of the jobs to find. Defaults to None.
            created_after (Optional[datetime.datetime]):
                The upper age limit of the jobs to find. Defaults to None.
            permission_level (Optional[int]):
                The permission level of the jobs to find. Defaults to None.
            above_permission_level (Optional[int]):
                The lower permission level value of the jobs to find. Defaults to None.
            below_permission_level (Optional[int]):
                The upper permission level value of the jobs to find. Defaults to None.
            created_after (Optional[datetime.datetime]):
                The upper age limit of the jobs to find. Defaults to None.
            created_after (Optional[datetime.datetime]):
                The upper age limit of the jobs to find. Defaults to None.
            is_running (Optional[bool]):
                A boolean that a job's state should match. Defaults to None.
            is_idling (Optional[bool]):
                A boolean that a job's state should match. Defaults to None.
            is_awaiting (Optional[bool]):
                A boolean that a job's state should match. Defaults to None.
            is_being_stopped (Optional[bool]):
                A boolean that a job's state should match. Defaults to None.
            is_being_restarted (Optional[bool]):
                A boolean that a job's state should match. Defaults to None.
            is_being_killed (Optional[bool]):
                A boolean that a job's state should match. Defaults to None.
            is_being_completed (Optional[bool]):
                A boolean that a job's state should match. Defaults to None.
            stopped (Optional[bool]):
                A boolean that a job's state should match. Defaults to None.

        Returns:
            tuple: A tuple of the job object proxies that were found.
        """

        if isinstance(_invoker, (EventJob, IntervalJob)):
            self._verify_permissions(_invoker, op=JOB_VERBS.FIND)
        else:
            _invoker = self._manager_job

        filter_functions = []

        if classes:
            if isinstance(classes, type):
                if issubclass(classes, (EventJob, IntervalJob)):
                    classes = (classes,)
                else:
                    raise TypeError(
                        f"'classes' must be a tuple of 'EventJob' or 'IntervalJob' subclasses or a single subclass"
                    ) from None

            elif isinstance(classes, tuple):
                if not all(issubclass(c, (EventJob, IntervalJob)) for c in classes):
                    raise TypeError(
                        f"'classes' must be a tuple of 'EventJob' or 'IntervalJob' subclasses or a single subclass"
                    ) from None

            if exact_class_match:
                filter_functions.append(
                    lambda job: any(job.__class__ is c for c in classes)
                )
            else:
                filter_functions.append(lambda job: isinstance(job, classes))

        if created_before is not None:
            if isinstance(created_before, datetime.datetime):
                filter_functions.append(lambda job: job.created_at < created_before)
            else:
                raise TypeError(
                    f"'created_before' must be of type 'datetime.datetime', not {type(created_before)}"
                ) from None

        if created_after is not None:
            if isinstance(created_after, datetime.datetime):
                filter_functions.append(
                    lambda job, created_after=None: job.created_at > created_after
                )
            else:
                raise TypeError(
                    f"'created_after' must be of type 'datetime.datetime', not {type(created_after)}"
                ) from None

        if permission_level is not None:
            if not isinstance(permission_level, int):
                raise TypeError(
                    "argument 'permission_level' must be"
                    f" of type 'int', not {below_permission_level.__class__}"
                )

            if (
                not permission_level % 2
                and PERMISSION_LEVELS.LOWEST
                <= permission_level
                <= PERMISSION_LEVELS.HIGHEST
            ):
                filter_functions.append(
                    lambda job: job.permission_level == permission_level
                )
            else:
                raise ValueError(
                    "argument 'permission_level' must be"
                    " a valid permission level integer"
                )

        if below_permission_level is not None:
            if not isinstance(below_permission_level, int):
                raise TypeError(
                    "argument 'below_permission_level' must be"
                    f" of type 'int', not {below_permission_level.__class__}"
                )

            if (
                not below_permission_level % 2
                and PERMISSION_LEVELS.LOWEST
                <= below_permission_level
                <= PERMISSION_LEVELS.HIGHEST
            ):
                filter_functions.append(
                    lambda job: job.permission_level < below_permission_level
                )
            else:
                raise ValueError(
                    "argument 'below_permission_level' must be"
                    " a valid permission level integer"
                )

        if above_permission_level is not None:
            if not isinstance(above_permission_level, int):
                raise TypeError(
                    "argument 'above_permission_level' must be"
                    f" of type 'int', not {above_permission_level.__class__}"
                )

            if (
                not above_permission_level % 2
                and PERMISSION_LEVELS.LOWEST
                <= above_permission_level
                <= PERMISSION_LEVELS.HIGHEST
            ):
                filter_functions.append(
                    lambda job: job.permission_level > above_permission_level
                )
            else:
                raise ValueError(
                    "argument 'above_permission_level' must be"
                    " a valid permission level integer"
                )

        if is_starting is not None:
            is_starting = bool(is_starting)
            filter_functions.append(lambda job: job.is_starting() == is_starting)

        if is_running is not None:
            is_running = bool(is_running)
            filter_functions.append(lambda job: job.is_running() == is_running)

        if is_idling is not None:
            is_running = bool(is_idling)
            filter_functions.append(
                lambda job, is_idling=None: job.is_idling() == is_idling
            )

        if stopped is not None:
            stopped = bool(stopped)
            filter_functions.append(lambda job: job.stopped() == stopped)

        if is_awaiting is not None:
            is_running = bool(is_awaiting)
            filter_functions.append(lambda job: job.is_awaiting() == is_awaiting)

        if is_being_stopped is not None:
            is_running = bool(is_being_stopped)
            filter_functions.append(
                lambda job: job.is_being_stopped() == is_being_stopped
            )

        if is_being_restarted is not None:
            is_being_restarted = bool(is_being_restarted)
            filter_functions.append(
                lambda job: job.is_being_restarted() == is_being_restarted
            )

        if is_being_killed is not None:
            is_being_killed = bool(is_being_killed)
            filter_functions.append(
                lambda job: job.is_being_killed() == is_being_killed
            )

        if is_being_completed is not None:
            is_being_completed = bool(is_being_completed)
            filter_functions.append(
                lambda job: job.is_being_completed() == is_being_completed
            )

        if not filter_functions:
            filter_functions.append(lambda job: True)

        if _return_proxy:
            return tuple(
                job._proxy
                for job in self._job_id_map.values()
                if all(filter_func(job) for filter_func in filter_functions)
            )
        else:
            return tuple(
                job
                for job in self._job_id_map.values()
                if all(filter_func(job) for filter_func in filter_functions)
            )

    def start_job(
        self,
        job_or_proxy: Union[EventJob, IntervalJob, JobProxy],
        _invoker: Optional[Union[EventJob, IntervalJob]] = None,
    ):

        """Start the given job object, if is hasn't already started.

        Args:
            job_or_proxy (Union[IntervalJob, EventJob]): The job object.

        Returns:
            bool: Whether the operation was successful.
        """

        job = (
            self._get_job_from_proxy(job_or_proxy)
            if isinstance(job_or_proxy, JobProxy)
            else job_or_proxy
        )

        if isinstance(_invoker, (EventJob, IntervalJob)):
            self._verify_permissions(_invoker, op=JOB_VERBS.START, target=job)
        else:
            _invoker = self._manager_job

        if job._is_being_guarded and _invoker is not job._guardian:
            raise JobStateError(
                "the given target job object is being guarded by another job"
            ) from None

        if not job._task_loop.is_running():
            job._task_loop.start()
            return True

        return False

    def restart_job(
        self,
        job_or_proxy: Union[IntervalJob, EventJob],
        stopping_timeout: Optional[float] = None,
        _invoker: Optional[Union[EventJob, IntervalJob]] = None,
    ):
        """Restart the given job object. This provides a cleaner way
        to forcefully stop a job and restart it, or to wake it up from
        a stopped state.

        Args:
            job_or_proxy (Union[IntervalJob, EventJob]): The job object.
            stopping_timeout (Optional[float]):
                An optional timeout in seconds for the maximum time period
                for stopping the job while it is restarting. This overrides
                the global timeout of this `JobManager` if present.
        Returns:
            bool: Whether the operation was initiated by the job.
        """

        job = (
            self._get_job_from_proxy(job_or_proxy)
            if isinstance(job_or_proxy, JobProxy)
            else job_or_proxy
        )

        if isinstance(_invoker, (EventJob, IntervalJob)):
            self._verify_permissions(_invoker, op=JOB_VERBS.RESTART, target=job)
        else:
            _invoker = self._manager_job

        if job._is_being_guarded and _invoker is not job._guardian:
            raise JobStateError(
                "the given target job object is being guarded by another job"
            ) from None

        if stopping_timeout:
            stopping_timeout = float(stopping_timeout)
            job._manager._job_stop_timeout = stopping_timeout

        return job._RESTART_EXTERNAL()

    def stop_job(
        self,
        job_or_proxy: Union[EventJob, IntervalJob, JobProxy],
        stopping_timeout: Optional[float] = None,
        force: bool = False,
        _invoker: Optional[Union[EventJob, IntervalJob]] = None,
    ):
        """Stop the given job object.

        Args:
            job_or_proxy (Union[IntervalJob, EventJob]): The job object.
            force (bool): Whether to suspend all operations of the job forcefully.
            stopping_timeout (Optional[float]):
                An optional timeout in seconds for the maximum time period
                for stopping the job. This overrides the global timeout of this
                `JobManager` if present.

        Returns:
            bool: Whether the operation was successful.
        """

        job = (
            self._get_job_from_proxy(job_or_proxy)
            if isinstance(job_or_proxy, JobProxy)
            else job_or_proxy
        )

        if isinstance(_invoker, (EventJob, IntervalJob)):
            self._verify_permissions(_invoker, op=JOB_VERBS.STOP, target=job)
        else:
            _invoker = self._manager_job

        if job._is_being_guarded and _invoker is not job._guardian:
            raise JobStateError(
                "the given target job object is being guarded by another job"
            ) from None

        if stopping_timeout:
            stopping_timeout = float(stopping_timeout)
            job._manager._job_stop_timeout = stopping_timeout

        return job._STOP_EXTERNAL(force=force)

    def kill_job(
        self,
        job_or_proxy: Union[EventJob, IntervalJob, JobProxy],
        stopping_timeout: Optional[float] = None,
        _invoker: Optional[Union[EventJob, IntervalJob]] = None,
    ):
        """Stops a job's current execution unconditionally and remove it from its
        `JobManager`. In order to check if a job was ended by killing it, one
        can call `.is_killed()`.

        Args:
            job_or_proxy (Union[IntervalJob, EventJob]): The job object.
            stopping_timeout (Optional[float]):
                An optional timeout in seconds for the maximum time period
                for stopping the job while it is being killed. This overrides the
                global timeout of this `JobManager` if present.

        Returns:
            bool: Whether the operation was initiated by the job.
        """

        job = (
            self._get_job_from_proxy(job_or_proxy)
            if isinstance(job_or_proxy, JobProxy)
            else job_or_proxy
        )

        if isinstance(_invoker, (EventJob, IntervalJob)):
            self._verify_permissions(_invoker, op=JOB_VERBS.KILL, target=job)
        else:
            _invoker = self._manager_job

        if job._is_being_guarded and _invoker is not job._guardian:
            raise JobStateError(
                "the given target job object is being guarded by another job"
            ) from None

        if stopping_timeout:
            stopping_timeout = float(stopping_timeout)
            job._manager._job_stop_timeout = stopping_timeout

        return job._KILL_EXTERNAL(awaken=True)

    def guard_job(
        self,
        job_or_proxy: Union[EventJob, IntervalJob, JobProxy],
        _invoker: Optional[Union[EventJob, IntervalJob]] = None,
    ):
        """Place a guard on the given job object, to prevent unintended state
        modifications by other jobs.

        Args:
            job_or_proxy (Union[EventJob, IntervalJob, JobProxy]): The job object.

        Raises:
            JobStateError:
                The given target job object is already being guarded by a job.
            JobStateError:
                The given target job object is already
                being guarded by the invoker job object.
        """

        job = (
            self._get_job_from_proxy(job_or_proxy)
            if isinstance(job_or_proxy, JobProxy)
            else job_or_proxy
        )

        if isinstance(_invoker, (EventJob, IntervalJob)):
            self._verify_permissions(_invoker, op=JOB_VERBS.GUARD, target=job)
        else:
            _invoker = self._manager_job

        if job._is_being_guarded:
            raise JobStateError(
                "the given target job object is already being guarded by a job"
            )

        if _invoker._guarded_job_proxies_dict is None:
            _invoker._guarded_job_proxies_dict = {}

        if job._identifier not in _invoker._guarded_job_proxies_dict:
            job._guardian = _invoker
            _invoker._guarded_job_proxies_dict[job._identifier] = job._proxy
            job._is_being_guarded = True
        else:
            raise JobStateError(
                "the given target job object is already"
                " being guarded by the invoker job object"
            )

    def unguard_job(
        self,
        job_or_proxy: Union[EventJob, IntervalJob, JobProxy],
        _invoker: Optional[Union[EventJob, IntervalJob]] = None,
    ):
        """Remove the guard on the given job object, to prevent unintended state
        modifications by other jobs.

        Args:
            job_or_proxy (Union[EventJob, IntervalJob, JobProxy]): The job object.

        Raises:
            JobStateError:
                The given target job object is not being guarded by a job.
            JobStateError:
                The given target job object is already
                being guarded by the invoker job object.
        """
        job = (
            self._get_job_from_proxy(job_or_proxy)
            if isinstance(job_or_proxy, JobProxy)
            else job_or_proxy
        )

        if isinstance(_invoker, (EventJob, IntervalJob)):
            self._verify_permissions(_invoker, op=JOB_VERBS.UNGUARD, target=job)
        else:
            _invoker = self._manager_job

        if not job._is_being_guarded:
            raise JobStateError("the given job object is not being guarded by a job")

        if (
            _invoker._guarded_job_proxies_dict is not None
            and job._identifier in _invoker._guarded_job_proxies_dict
        ):
            job._guardian = None
            job._is_being_guarded = False
            del _invoker._guarded_job_proxies_dict[job._identifier]

        elif _invoker is self._manager_job:
            guardian = job._guardian
            job._guardian = None
            job._is_being_guarded = False

            del guardian._guarded_job_proxies_dict[job._identifier]

        else:
            raise JobStateError(
                "the given target job object is not"
                " being guarded by the invoker job object"
            )

        for fut in job._unguard_futures:
            if not fut.cancelled():
                fut.set_result(True)

        job._unguard_futures.clear()

    def __contains__(self, job_or_proxy: Union[EventJob, IntervalJob, JobProxy]):
        job = (
            self._get_job_from_proxy(job_or_proxy)
            if isinstance(job_or_proxy, JobProxy)
            else job_or_proxy
        )
        return job._identifier in self._job_id_map

    @staticmethod
    def _dispatch_add_to_waiting_list(
        event, target_event_waiting_queue, deletion_queue_indices
    ):
        for i, waiting_list in enumerate(target_event_waiting_queue):
            if isinstance(event, waiting_list[0]) and waiting_list[1](event):
                if not waiting_list[2].cancelled():
                    waiting_list[2].set_result(event.copy())
                deletion_queue_indices.append(i)

    def _dispatch_add_to_jobs(event, job_dict, job_identifiers):
        for identifier in job_identifiers:
            event_job = job_dict[identifier]
            if event_job.check_event(event):
                event_job._add_event(event.copy())

    def dispatch_event(self, event: events.BaseEvent):
        """Dispatch a `BaseEvent` subclass to all event job objects
        in this job manager.

        Args:
            event (events.BaseEvent): The event instance to be dispatched.
        """
        event_class_identifier = event.__class__._IDENTIFIER

        if event_class_identifier in self._event_waiting_queues:
            target_event_waiting_queue = self._event_waiting_queues[
                event_class_identifier
            ]
            deletion_queue_indices = []

            for i, waiting_list in enumerate(target_event_waiting_queue):
                if isinstance(event, waiting_list[0]) and waiting_list[1](event):
                    if not waiting_list[2].cancelled():
                        waiting_list[2].set_result(event.copy())
                    deletion_queue_indices.append(i)

            for idx in reversed(deletion_queue_indices):
                del target_event_waiting_queue[idx]

        if event_class_identifier in self._event_job_ids:
            jobs_identifiers = self._event_job_ids[event_class_identifier]

            for identifier in jobs_identifiers:
                event_job = self._job_id_map[identifier]
                if event_job.check_event(event):
                    event_job._add_event(event.copy())

    def wait_for_event(
        self,
        *event_types: Type[events.BaseEvent],
        check: Optional[Callable[[events.BaseEvent], bool]] = None,
        timeout: Optional[float] = None,
    ):
        """Wait for specific type of event to be dispatched
        and return it as an event object using the given coroutine.

        Args:
            *event_types (Type[events.BaseEvent]):
                The event type/types to wait for. If any of its/their
                instances is dispatched, that instance will be returned.
            check (Optional[Callable[[events.BaseEvent], bool]]):
                A callable obejct used to validate if a valid event that was recieved meets specific conditions.
                Defaults to None.
            timeout: (Optional[float]):
                An optional timeout value in seconds for the maximum waiting period.

        Raises:
            TimeoutError: The timeout value was exceeded.
            CancelledError: The future used to wait for an event was cancelled.

        Returns:
            Coroutine:
                A coroutine that evaluates to a valid `BaseEvent` event object.
        """

        check = (lambda _: True) if check is None else check
        future = self._loop.create_future()

        if not all(
            issubclass(event_type, events.BaseEvent) for event_type in event_types
        ):
            raise TypeError(
                "argument 'event_types' must contain only subclasses of 'BaseEvent'"
            ) from None

        wait_list = [event_types, check, future]

        for event_type in event_types:
            if event_type._IDENTIFIER not in self._event_waiting_queues:
                self._event_waiting_queues[event_type._IDENTIFIER] = []

            self._event_waiting_queues[event_type._IDENTIFIER].append(wait_list)

        return asyncio.wait_for(future, timeout)

    def kill_all_jobs(self):
        """Kill all job objects that are in this job manager."""
        for job in self._job_id_map.values():
            job._KILL_EXTERNAL(awaken=True)

    def kill_all_interval_jobs(self):
        """Kill all job objects inheriting from `IntervalJob` that are in this job manager."""
        for job in (
            ij
            for ij in (
                self._job_id_map[identifier] for identifier in self._interval_job_ids
            )
        ):
            if not job.is_being_killed():
                job._KILL_EXTERNAL(awaken=True)

    def kill_all_event_jobs(self):
        """Kill all job objects inheriting from `EventJob` that are in this job manager."""
        for ej_id_set in self._event_job_ids.values():
            for job_identifier in ej_id_set:
                job = self._job_id_map[job_identifier]
                if not job.is_being_killed():
                    job._KILL_EXTERNAL(awaken=True)

    def quit(self):
        self.uninitialize_job_scheduling()
        self._thread_pool_executor.shutdown()
        self._process_pool_executor.shutdown()
        self.kill_all_jobs()
        self._running = False


class JobManagerProxy:

    __slots__ = ("__mgr", "__j", "_job_stop_timeout")

    def __init__(self, mgr: JobManager, job: Union[EventJob, IntervalJob]):
        self.__mgr = mgr
        self.__j = job
        self._job_stop_timeout = None

    def get_job_stop_timeout(self):
        """Get the maximum time period in seconds for the job object managed
        by this `JobManagerProxy` to stop when halted from the
        `JobManager`, either due to being stopped, restarted or killed.
        By default, this method returns the global job timeout set for the
        current `JobManager`, but that can be overridden with a custom
        timeout when trying to stop the job object.

        Returns:
            float: The timeout in seconds.
            None:
                No timeout was set for the job object or globally for the
                current `JobManager`.
        """

        return (
            self._job_stop_timeout
            if self._job_stop_timeout
            else self.__mgr.get_global_job_stop_timeout()
        )

    def verify_permissions(
        self,
        op: str,
        target: Optional[JobProxy] = None,
        target_cls: Optional[Union[Type[EventJob], Type[IntervalJob]]] = None,
        schedule_identifier: Optional[str] = None,
        scheduler_identifier: Optional[str] = None,
    ):
        """Check if the permissions of the job of this `JobManagerProxy` object
        are sufficient for carrying out the specified operation on the given input.

        Args:
            op (str):
                The operation. Must be one of the operations defined in the `JOB_VERBS`
                class namespace.

            target (Optional[JobProxy]):
                The target job for an operation. Defaults to None.

            target_cls (Optional[Union[Type[EventJob], Type[IntervalJob]]]):
                The target job class for an operation. Defaults to None.

            schedule_identifier (Optional[str]):
                A target schedule identifier. Defaults to None.

            scheduler_identifier (Optional[str]):
                A target job with this specific identifier if existent,
                but can also be an enpty string. Defaults to None.

        Returns:
            bool: The result of the permission check.
        """

        return self.__mgr._verify_permissions(
            self.__j,
            op,
            target=self.__mgr._get_job_from_proxy(target)
            if target is not None
            else target,
            target_cls=target_cls,
            schedule_identifier=schedule_identifier,
            scheduler_identifier=scheduler_identifier,
            raise_exceptions=False,
        )

    def create_job(
        self, cls: Union[Type[EventJob], Type[IntervalJob]], *args, **kwargs
    ):
        """Create an instance of a job class.

        Args:
            cls (Union[Type[EventJob], Type[IntervalJob]]):
                The job class to instantiate a job object from.

        Returns:
            JobProxy: A job proxy object.
        """
        return self.__mgr.create_job(
            cls, *args, _return_proxy=True, _invoker=self.__j, **kwargs
        )

    async def initialize_job(self, job_proxy: JobProxy, raise_exceptions: bool = True):
        """This initializes a job object.

        Args:
            job_proxy (JobProxy): The job object's proxy.
            raise_exceptions (bool, optional):
                Whether exceptions should be raised. Defaults to True.

        Returns:
            bool: Whether the initialization attempt was successful.
        """
        job = self.__mgr._get_job_from_proxy(job_proxy)
        return await self.__mgr.initialize_job(job, raise_exceptions=raise_exceptions)

    async def register_job(self, job_proxy: JobProxy):
        """Register a job object to this JobManager, while initializing it if necessary.

        Args:
            job_proxy (JobProxy): A job object proxy whose job should be registered.
        """
        job = self.__mgr._get_job_from_proxy(job_proxy)
        return await self.__mgr.register_job(job, _invoker=self.__j)

    async def create_and_register_job(
        self, cls: Union[Type[EventJob], Type[IntervalJob]], *args, **kwargs
    ):
        """Create an instance of a job class, and register it to this `BotTaskManager`.

        Args:
            cls (Union[Type[EventJob], Type[IntervalJob]]):
                The job class to be used for instantiation.

        Returns:
            JobProxy: A job proxy object.
        """

        return await self.__mgr.create_and_register_job(
            cls,
            *args,
            _return_proxy=True,
            _invoker=self.__j,
            **kwargs,
        )

    def restart_job(
        self, job_proxy: JobProxy, stopping_timeout: Optional[float] = None
    ):
        """Restart the given job object. This provides a cleaner way
        to forcefully stop a job and restart it, or to wake it up from
        a stopped state after it was stoppd.

        Args:
            job_proxy (JobProxy): The job object's proxy.
            stopping_timeout (Optional[float]):
                An optional timeout in seconds for the maximum time period
                for stopping the job while it is restarting. This overrides
                the global timeout of this `JobManager` if present.

        Returns:
            bool: Whether the operation was initiated by the job.
        """

        job = self.__mgr._get_job_from_proxy(job_proxy)

        if job is self.__j:
            job.RESTART()

        return self.__mgr.restart_job(
            job, stopping_timeout=stopping_timeout, _invoker=self.__j
        )

    def start_job(
        self,
        job_proxy: JobProxy,
    ):
        """Start the given job object.

        Args:
            job_proxy (JobProxy): The job object's proxy.
        """

        return self.__mgr.start_job(job_proxy, _invoker=self.__j)

    def stop_job(
        self,
        job_proxy: JobProxy,
        stopping_timeout: Optional[float] = None,
        force=False,
    ):
        """Stop the given job object.

        Args:
            job_proxy (JobProxy): The job object's proxy.
            stopping_timeout (Optional[float]):
                An optional timeout in seconds for the maximum time period
                for stopping the job. This overrides the global timeout of this
                `JobManager` if present.
            force (bool): Whether to suspend all operations of the job forcefully.

        Returns:
            bool: Whether the operation was initiated by the job.
        """
        job = self.__mgr._get_job_from_proxy(job_proxy)

        if job is self.__j:
            job.STOP(force=force)

        return self.__mgr.stop_job(
            job, stopping_timeout=stopping_timeout, force=force, _invoker=self.__j
        )

    def kill_job(self, job_proxy: JobProxy, stopping_timeout: Optional[float] = None):
        """Stops a job's current execution unconditionally and remove it from its `JobManager`.
        In order to check if a job was ended by killing it, one can call `.is_killed()`.

        Args:
            job_proxy (JobProxy): The job object's proxy.
            stopping_timeout (Optional[float]):
                An optional timeout in seconds for the maximum time period
                for stopping the job while it is being killed. This overrides the
                global timeout of this `JobManager` if present.

        Returns:
            bool: Whether the operation was initiated by the job.
        """
        job = self.__mgr._get_job_from_proxy(job_proxy)

        if job is self.__j:
            job.KILL()

        return self.__mgr.kill_job(
            job, stopping_timeout=stopping_timeout, _invoker=self.__j
        )

    def get_guarded_jobs(self):
        return tuple(self.__j._guarded_job_proxies_set)

    def guard_job(
        self,
        job_proxy: JobProxy,
    ):
        """Place a guard on the given job object, to prevent unintended state
        modifications by other jobs.

        Args:
            job_proxy (JobProxy): The job object's proxy.

        Raises:
            JobStateError:
                The given target job object is already being guarded by a job.
            JobStateError:
                The given target job object is already
                being guarded by the invoker job object.
        """
        return self.__mgr.guard_job(job_proxy, _invoker=self.__j)

    def unguard_job(
        self,
        job_proxy: JobProxy,
    ):
        """Remove the guard on the given job object, to prevent unintended state
        modifications by other jobs.

        Args:
            job_proxy (JobProxy): The job object's proxy.

        Raises:
            JobStateError:
                The given target job object is not being guarded by a job.
            JobStateError:
                The given target job object is already
                being guarded by the invoker job object.
        """

        return self.__mgr.unguard_job(job_proxy, _invoker=self.__j)

    def _eject(self):
        """
        Irreversible job death. Do not call this method without ensuring that
        a job is killed.
        """
        if not self.__j.alive():
            self.__mgr._remove_job(self.__j)
            self.__j._manager = None
            self.__j = None
            self.__mgr = None

    def _unguard(self):
        """
        Unguard the job of this job manager proxy.
        """
        if self.__j._is_being_guarded:
            guardian = self.__mgr._get_job_from_proxy(self.__j._guardian)
            self.__mgr.unguard_job(self.__j, _invoker=guardian)

    def job_scheduling_is_initialized(self):
        """Whether the job scheduling process of this job manager is initialized."""
        return self.__mgr.job_scheduling_is_initialized()

    async def wait_for_job_scheduling_initialization(self):
        """An awaitable coroutine that can be used to wait until job scheduling
        is initialized.

        Raises:
            RuntimeError: Job scheduling is already initialized.
        """
        return await self.__mgr.wait_for_job_scheduling_initialization()

    async def wait_for_job_scheduling_uninitialization(self):
        """This method returns a `Future` that can be used to wait until job scheduling
        is uninitialized.

        Raises:
            RuntimeError: Job scheduling is not initialized.

        Returns:
            Future: A future object.
        """

        return await self.__mgr.wait_for_job_scheduling_uninitialization()

    async def create_job_schedule(
        self,
        cls: Union[Type[EventJob], Type[IntervalJob]],
        timestamp: Union[datetime.datetime, datetime.timedelta],
        recur_interval: Union[int, datetime.timedelta] = 0,
        max_recurrences: int = 1,
        job_args: tuple = (),
        job_kwargs: Optional[dict] = None,
    ):
        """Schedule a job of a specific type to be instantiated and to run at
        one or more specific periods of time. Each job can receive positional
        or keyword arguments which are passed to this method.
        Those arguments must be pickleable.

        Args:
            cls (Union[Type[EventJob], Type[IntervalJob]]): The job type to schedule.
            timestamp (Union[datetime.datetime, datetime.timedelta]):
                The exact timestamp at which to instantiate a job.
            recur_interval (Optional[datetime.timedelta]):
                The interval at which a job should be rescheduled.
                Defaults to None.
            max_recurrences (int):
                The maximum amount of recur intervals for rescheduling.
                -1 sets the interval maximum to be unlimited.
                Defaults to 1.
            job_args (tuple, optional):
                Positional arguments to pass to the scheduled job upon
                instantiation. Defaults to None.
            job_kwargs (dict, optional):
                Keyword arguments to pass to the scheduled job upon instantiation.
                Defaults to None.

        Raises:
            RuntimeError:
                The job manager has not yet initialized job scheduling.
            TypeError: Invalid argument types were given.

        Returns:
            str: The string identifier of the scheduling operation
        """
        return await self.__mgr.create_job_schedule(
            cls=cls,
            timestamp=timestamp,
            recur_interval=recur_interval,
            max_recurrences=max_recurrences,
            job_args=job_args,
            job_kwargs=job_kwargs,
            _invoker=self.__j,
        )

    def get_job_schedule_identifiers(self):
        """Return a tuple of all job schedule identifiers pointing to
        scheduling data.

        Returns:
            tuple: All job schedule identifiers.
        """

        return self.__mgr.get_job_schedule_identifiers()

    def job_schedule_has_failed(self, schedule_identifier: str):
        """Whether the job schedule operation with the specified schedule
        identifier failed.

        Args:
            schedule_identifier (str):
                A string identifier following this structure:
                'JOB_MANAGER_IDENTIFIER-TARGET_TIMESTAMP_IN_NS-SCHEDULING_TIMESTAMP_IN_NS'

        Raises:
            ValueError: Invalid schedule identifier.

        Returns:
            bool: True/False
        """
        return self.__mgr.job_schedule_has_failed(schedule_identifier)

    def has_job_schedule(self, schedule_identifier: str):
        """Whether the job schedule operation with the specified schedule
        identifier exists.

        Args:
            schedule_identifier (str):
                A string identifier following this structure:
                'JOB_MANAGER_IDENTIFIER-TARGET_TIMESTAMP_IN_NS-SCHEDULING_TIMESTAMP_IN_NS'

        Raises:
            ValueError: Invalid schedule identifier.

        Returns:
            bool: Whether the schedule identifier leads to existing scheduling data.
        """

        return self.__mgr.has_job_schedule(schedule_identifier)

    async def remove_job_schedule(
        self,
        schedule_identifier: str,
    ):
        """Remove a job schedule operation using the string identifier
        of the schedule operation.

        Args:
            schedule_identifier (str):
                A string identifier following this structure:
                'JOB_MANAGER_IDENTIFIER-TARGET_TIMESTAMP_IN_NS-SCHEDULING_TIMESTAMP_IN_NS'

        Raises:
            ValueError: Invalid schedule identifier.
            KeyError: No operation matching the given schedule identifier was found.
        """

        return self.__mgr.remove_job_schedule(schedule_identifier, _invoker=self.__j)

    def find_job(
        self,
        *,
        identifier: Optional[str] = None,
        created_at: Optional[datetime.datetime] = None,
    ):
        """Find the first job that matches the given criteria specified as arguments,
        and return a proxy to it, otherwise return `None`.

        Args:

            identifier (Optional[str]):
                The exact identifier of the job to find. This argument overrides any other parameter below. Defaults to None.

            created_at (Optional[datetime.datetime]):
                The exact creation date of the job to find. Defaults to None.

        Raises:
            TypeError: One of the arguments must be specified.

        Returns:
            JobProxy: The proxy of the job object, if present.
        """
        return self.__mgr.find_job(
            identifier=identifier,
            created_at=created_at,
            _return_proxy=True,
            _invoker=self.__j,
        )

    def find_jobs(
        self,
        *,
        classes: Optional[
            Union[
                Type[EventJob],
                Type[IntervalJob],
                tuple[Union[Type[EventJob], Type[IntervalJob]]],
            ]
        ] = None,
        exact_class_match: bool = False,
        created_before: Optional[datetime.datetime] = None,
        created_after: Optional[datetime.datetime] = None,
        permission_level: Optional[int] = None,
        above_permission_level: Optional[int] = None,
        below_permission_level: Optional[int] = None,
        is_starting: Optional[bool] = None,
        is_running: Optional[bool] = None,
        is_idling: Optional[bool] = None,
        is_awaiting: Optional[bool] = None,
        is_being_stopped: Optional[bool] = None,
        is_being_restarted: Optional[bool] = None,
        is_being_killed: Optional[bool] = None,
        is_being_completed: Optional[bool] = None,
        stopped: Optional[bool] = None,
    ):
        """Find jobs that match the given criteria specified as arguments,
        and return a tuple of proxy objects to them.

        Args:
            classes: (
                 Optional[
                    Union[
                        Type[EventJob],
                        Type[IntervalJob],
                        tuple[
                            Union[
                                Type[EventJob],
                                Type[IntervalJob]
                            ]
                        ]
                    ]
                ]
            ):
                The class(es) of the job objects to limit the job search to, excluding subclasses. Defaults to None.
            exact_class_match (bool):
                Whether an exact match is required for the classes in the previous parameter,
                or subclasses are allowed too. Defaults to False.

            created_before (Optional[datetime.datetime]):
                The lower age limit of the jobs to find. Defaults to None.
            created_after (Optional[datetime.datetime]):
                The upper age limit of the jobs to find. Defaults to None.
            permission_level (Optional[int]):
                The permission level of the jobs to find. Defaults to None.
            above_permission_level (Optional[int]):
                The lower permission level value of the jobs to find. Defaults to None.
            below_permission_level (Optional[int]):
                The upper permission level value of the jobs to find. Defaults to None.
            created_after (Optional[datetime.datetime]):
                The upper age limit of the jobs to find. Defaults to None.
            created_after (Optional[datetime.datetime]):
                The upper age limit of the jobs to find. Defaults to None.
            is_running (Optional[bool]):
                A boolean that a job's state should match. Defaults to None.
            is_idling (Optional[bool]):
                A boolean that a job's state should match. Defaults to None.
            is_awaiting (Optional[bool]):
                A boolean that a job's state should match. Defaults to None.
            is_being_stopped (Optional[bool]):
                A boolean that a job's state should match. Defaults to None.
            is_being_restarted (Optional[bool]):
                A boolean that a job's state should match. Defaults to None.
            is_being_killed (Optional[bool]):
                A boolean that a job's state should match. Defaults to None.
            is_being_completed (Optional[bool]):
                A boolean that a job's state should match. Defaults to None.
            stopped (Optional[bool]):
                A boolean that a job's state should match. Defaults to None.

        Returns:
            tuple: A tuple of the job object proxies that were found.
        """

        return self.__mgr.find_jobs(
            classes=classes,
            exact_class_match=exact_class_match,
            created_before=created_before,
            created_after=created_after,
            permission_level=permission_level,
            above_permission_level=above_permission_level,
            below_permission_level=below_permission_level,
            is_starting=is_starting,
            is_running=is_running,
            is_idling=is_idling,
            is_awaiting=is_awaiting,
            is_being_stopped=is_being_stopped,
            is_being_restarted=is_being_restarted,
            is_being_killed=is_being_killed,
            is_being_completed=is_being_completed,
            stopped=stopped,
            _return_proxy=True,
            _invoker=self.__j,
        )

    def wait_for_event(
        self,
        *event_types: Type[BaseEvent],
        check: Optional[Callable[[events.BaseEvent], bool]] = None,
        timeout: Optional[float] = None,
    ):
        """Wait for specific type of event to be dispatched, and return that.

        Args:
            *event_types (Type[events.BaseEvent]):
                The event type/types to wait for. If any of its/their
                instances is dispatched, that instance will be returned.
            check (Optional[Callable[[events.BaseEvent], bool]]):
                A callable obejct used to validate if a valid event that was recieved meets specific conditions.
                Defaults to None.

        Returns:
            BaseEvent: A valid event object
        """

        return self.__mgr.wait_for_event(
            *event_types,
            check=check,
            timeout=timeout,
        )

    async def dispatch_custom_event(self, event: events.CustomEvent):
        """Dispatch a `CustomEvent` subclass to all event job objects
        in this job manager that are listining for it.

        Args:
            event (events.BaseEvent): The subclass to be dispatched.
        """

        if not isinstance(event, events.CustomEvent):
            raise TypeError(
                "argument 'event' must have `CustomEvent` as a subclass"
            ) from None

        event._dispatcher = self.__j._proxy
        return self.__mgr.dispatch_event(event)

    def has_job(self, job_proxy: JobProxy):
        """Whether a specific job object is currently in this
        JobManager.

        Args:
            job_proxy (JobProxy): The target job's proxy.

        Returns:
            bool: True/False
        """
        job = self.__mgr._get_job_from_proxy(job_proxy)
        return self.__mgr.has_job(job)

    __contains__ = has_job

    def has_identifier(self, identifier: str):
        """Whether a job with the given identifier is contained in this job manager.

        Args:
            identifier (str): The job identifier.

        Returns:
            bool: True/False
        """
        return self.__mgr.has_identifier(identifier)
