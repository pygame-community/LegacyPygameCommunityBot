"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file implements a job manager class for running and managing job objects
at runtime. 
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import datetime
import pickle
from pprint import pprint
import time
from typing import Any, Callable, Coroutine, Literal, Optional, Sequence, Type, Union

import black

from pgbot.utils import utils
from pgbot import common, events
from .jobs import (
    EventJobBase,
    IntervalJobBase,
    _SingletonMixinJobBase,
    JobManagerJob,
    JobError,
    JobStateError,
    JobInitializationError,
    JobPermissionError,
    JobVerbs,
    _JOB_VERBS_PRES_CONT,
    JobPermissionLevels,
    get_job_class_from_scheduling_identifier,
    get_job_class_from_runtime_identifier,
    get_job_class_permission_level,
    get_job_class_scheduling_identifier,
)

from pgbot.jobs import jobs

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
            global_job_timeout (Optional[float]): The default global job timeout
              in seconds. Defaults to None.
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
        self._thread_pool_executor: Optional[ThreadPoolExecutor] = None
        self._thread_pool_executor_lock = asyncio.Lock()
        self._process_pool_executor: Optional[ProcessPoolExecutor] = None
        self._process_pool_executor_lock = asyncio.Lock()
        self._event_waiting_queues = {}
        self._schedule_dict: dict[str, dict[str, Any]] = {"0": {}}
        # zero timestamp for failed scheduling attempts
        self._schedule_ids = set()
        self._schedule_dict_fails = {}
        self._schedule_dict_lock = asyncio.Lock()
        self._initialized = False
        self._is_running = False
        self._scheduling_is_initialized = False
        self._scheduling_initialized_futures = []
        self._scheduling_uninitialized_futures = []

        if global_job_timeout:
            global_job_timeout = float(global_job_timeout)

        self._global_job_stop_timeout = global_job_timeout

    def _check_init(self):
        if not self._initialized:
            raise RuntimeError("this job manager is not initialized")

    def _check_running(self):
        if not self._is_running:
            raise RuntimeError("this job manager is not running")

    def _check_init_and_running(self):
        if not self._initialized:
            raise RuntimeError("this job manager is not initialized")

        elif not self._is_running:
            raise RuntimeError("this job manager is not running")

    def _check_scheduling_init(self):
        if not self._scheduling_is_initialized:
            raise RuntimeError(
                "job scheduling was not initialized for this job manager"
            )

    def _check_has_executors(self):
        if self._thread_pool_executor is None or self._process_pool_executor is None:
            raise RuntimeError("this job manager does not have any executors")

    @property
    def identifier(self) -> str:
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
                "invalid event loop, must be a subclass of 'asyncio.AbstractEventLoop'"
            ) from None
        self._loop = loop

    def is_running(self) -> bool:
        """Whether this job manager is currently running, meaning that it has been
        initialized and has not yet quit.

        Returns:
            bool: True/False
        """
        return self._is_running

    def initialized(self) -> bool:
        """Whether this job manager was initialized.
        This can return True even if a job manager
        has quit. To check if a job manager is running,
        use the `is_running()` method.

        Returns:
            bool: True/False
        """
        return self._initialized

    def get_global_job_stop_timeout(self) -> Optional[float]:
        """Get the maximum time period in seconds for job objects to stop
        when halted from this manager, either due to stopping,
        restarted or killed.

        Returns:
            float: The timeout in seconds.
            None: No timeout is currently set.
        """
        return self._global_job_stop_timeout

    def set_global_job_stop_timeout(self, timeout: Optional[float]):
        """Set the maximum time period in seconds for job objects to stop
        when halted from this manager, either due to stopping,
        restarted or killed.

        Args:
            timeout (Optional[float]): The timeout in seconds,
            or None to clear any previous timeout.
        """

        if timeout:
            timeout = float(timeout)
        self._global_job_stop_timeout = timeout

    @staticmethod
    def _unpickle_dict(byte_data):
        unpickled_data = pickle.loads(byte_data)

        if not isinstance(unpickled_data, dict):
            raise TypeError(
                f"invalid object of type '{unpickled_data.__class__}' in pickle data, "
                "must be of type 'dict'"
            )
        return unpickled_data

    @staticmethod
    def _pickle_dict(target_dict):
        if not isinstance(target_dict, dict):
            raise TypeError(
                f"argument 'target_dict' must be of type 'dict', "
                f"not {target_dict.__class__}"
            )

        pickled_data = pickle.dumps(target_dict)
        return pickled_data

    async def initialize(self) -> bool:
        """Initialize this job manager, if it hasn't yet been initialized.

        Returns:
            bool: Whether the call was successful.
        """

        if not self._initialized:
            self._initialized = True
            self._is_running = True
            self._thread_pool_executor = ThreadPoolExecutor(max_workers=4)
            self._process_pool_executor = ProcessPoolExecutor(max_workers=4)
            self._manager_job = self._get_job_from_proxy(
                await self.create_and_register_job(JobManagerJob)
            )
            return True

        return False

    async def job_scheduling_loop(self):
        """Run one iteration of the job scheduling loop of this
        job manager object.
        """

        self._check_init_and_running()
        self._check_scheduling_init()

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
                            self._unpickle_dict,
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
                                    self._unpickle_dict,
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
                                    f"Job scheduling for {schedule_identifier} failed: "
                                    "Too high recurring timestamp value",
                                    utils.format_code_exception(e),
                                )
                                deletion_list.append(schedule_identifier)
                                self._schedule_ids.remove(schedule_identifier)
                                self._schedule_dict[0][
                                    schedule_identifier
                                ] = schedule_data
                                continue

                        job_class = get_job_class_from_scheduling_identifier(
                            schedule_data["class_scheduling_identifier"], None
                        )
                        if job_class is None:
                            print(
                                f"Job initiation failed: Could not find job class "
                                "with a scheduling identifier of "
                                f'\'{schedule_data["class_scheduling_identifier"]}\''
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
                                await self.register_job(job._proxy)
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

    async def dump_job_scheduling_data(self) -> bytes:
        """Return the current job scheduling data as
        a `bytes` object of pickled data. This is only
        possible while a job manager is running or it
        was quit without its executors being shut down.

        Returns:
            bytes: The scheduling data.
        """

        self._check_init()
        self._check_has_executors()

        dump_dict = {}

        if self._process_pool_executor is None:
            pass

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
                                    self._pickle_dict,
                                    schedule_dict,
                                )

                        elif isinstance(schedule_dict, bytes):
                            dump_dict[timestamp_ns_str][scheduling_id] = schedule_dict

                    async with self._process_pool_executor_lock:
                        dump_dict[timestamp_ns_str] = await self._loop.run_in_executor(
                            self._process_pool_executor,
                            self._pickle_dict,
                            dump_dict[timestamp_ns_str],
                        )

                elif isinstance(schedules_dict, bytes):
                    dump_dict[timestamp_ns_str] = schedules_dict

        result = None

        del dump_dict["0"]  # don't export error schedulings

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
                        "invoker_identifier": '556456789-53223236969',
                        "schedule_timestamp_ns_str": "6969",
                        "timestamp_ns_str": "52069",
                        "recur_interval": 878787, # in seconds
                        "occurences": 0,
                        "max_recurrences": 10,
                        "class_scheduling_identifier": "AddReaction-1234567876",
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

            overwrite (bool): Whether any previous schedule data should be overwritten
              with new data.
              If set to `False`, attempting to add unto preexisting data will
              raise a `RuntimeError`. Defaults to False.

        Raises:
            RuntimeError:
                Job scheduling is already initialized, or there is
                potential schedule data that might be unintentionally overwritten.

            TypeError: Invalid type for `data`.
            TypeError: Invalid structure of `data`.
        """

        self._check_init_and_running()

        if self._scheduling_is_initialized:
            raise RuntimeError(
                "cannot load scheduling data while job scheduling is initialized."
            )

        elif len(self._schedule_dict) > 1 and not overwrite:
            raise RuntimeError(
                "unintentional overwrite of preexisting scheduling data"
                " at risk, aborted"
            )

        data_dict = None
        data_set = None

        if isinstance(data, bytes):
            print("raw job scheduling data:", data)
            async with self._process_pool_executor_lock:
                data = await self._loop.run_in_executor(
                    self._process_pool_executor, pickle.loads, data
                )

            print(
                "deserialised data:",
                black.format_str(repr(data), mode=black.FileMode()),
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
                        self._unpickle_dict,
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
                                self._unpickle_dict,
                                schedule_dict,
                            )

        async with self._schedule_dict_lock:
            self._schedule_ids = data_set
            self._schedule_dict.clear()
            self._schedule_dict.update(data_dict)
            if "0" not in self._schedule_dict:
                self._schedule_dict["0"] = {}

    def initialize_job_scheduling(self) -> bool:
        """Initialize the job scheduling process of this job manager.

        Returns:
            bool: Whether the call was successful.
        """

        self._check_init_and_running()

        if not self._scheduling_is_initialized:
            self._scheduling_is_initialized = True
            for fut in self._scheduling_initialized_futures:
                if not fut.cancelled():
                    fut.set_result(True)

            return True

        return False

    def job_scheduling_is_initialized(self) -> bool:
        """Whether the job scheduling process of this job manager is initialized."""
        return self._scheduling_is_initialized

    def wait_for_job_scheduling_initialization(
        self, timeout: Optional[float] = None
    ) -> Coroutine:
        """This method returns a coroutine that can be used to wait until job
        scheduling is initialized.

        Raises:
            RuntimeError: Job scheduling is already initialized.

        Returns:
            Coroutine: A coroutine that evaluates to `True`.
        """

        if not self._scheduling_is_initialized:
            self._check_init_and_running()
            fut = self._loop.create_future()
            self._scheduling_initialized_futures.append(fut)
            return asyncio.wait_for(fut, timeout)

        raise RuntimeError("Job scheduling is already initialized.")

    def wait_for_job_scheduling_uninitialization(
        self, timeout: Optional[float] = None
    ) -> Coroutine:
        """This method returns a coroutine that can be used to wait until job
        scheduling is uninitialized.

        Raises:
            RuntimeError: Job scheduling is not initialized.

        Returns:
            Coroutine: A coroutine that evaluates to `True`.
        """

        if self._scheduling_is_initialized:
            self._check_init_and_running()
            fut = self._loop.create_future()
            self._scheduling_uninitialized_futures.append(fut)
            return asyncio.wait_for(fut, timeout)

        raise RuntimeError("Job scheduling is not initialized.")

    def uninitialize_job_scheduling(self) -> bool:
        """End the job scheduling process of this job manager.

        Returns:
            bool: Whether the call was successful.
        """

        output = False

        if self._scheduling_is_initialized:
            self._scheduling_is_initialized = False
            output = True

            for fut in self._scheduling_initialized_futures:
                if not fut.cancelled():
                    fut.cancel(
                        f"initialization of {self.__class__.__name__}"
                        f"(ID={self._identifier}) was aborted"
                    )

            for fut in self._scheduling_uninitialized_futures:
                if not fut.cancelled():
                    fut.set_result(True)

        return output

    def _verify_permissions(
        self,
        invoker: Union[EventJobBase, IntervalJobBase],
        op: JobVerbs,
        target: Optional[
            Union[EventJobBase, IntervalJobBase, "proxies.JobProxy"]
        ] = None,
        target_cls=None,
        schedule_identifier=None,
        invoker_identifier=None,
        raise_exceptions=True,
    ) -> bool:

        invoker_cls = invoker.__class__

        if target is not None:
            if isinstance(target, proxies.JobProxy):
                target = self._get_job_from_proxy(target)

            elif not isinstance(target, (EventJobBase, IntervalJobBase)):
                raise TypeError(
                    "argument 'target' must be a an instance of a job object or a job proxy"
                )

        target_cls = target.__class__ if target else target_cls

        invoker_cls_permission_level = get_job_class_permission_level(invoker_cls)

        target_cls_permission_level = None

        if not isinstance(op, JobVerbs):
            raise TypeError(
                "argument 'op' must be an enum value defined in the 'JobVerbs' " "enum"
            )

        elif (
            op is JobVerbs.FIND
            and invoker_cls_permission_level < JobPermissionLevels.LOW
        ):
            if raise_exceptions:
                raise JobPermissionError(
                    f"insufficient permission level of {invoker_cls.__qualname__} "
                    f"({invoker_cls_permission_level.name}) "
                    f"for {_JOB_VERBS_PRES_CONT[op.name].lower()} "
                    "job objects"
                )
            return False

        elif (
            op is JobVerbs.CUSTOM_EVENT_DISPATCH
            and invoker_cls_permission_level < JobPermissionLevels.HIGH
        ):
            if raise_exceptions:
                raise JobPermissionError(
                    f"insufficient permission level of {invoker_cls.__qualname__} "
                    f"({invoker_cls_permission_level.name}) "
                    f"for dispatching custom events to job objects "
                )
            return False

        elif (
            op is JobVerbs.EVENT_DISPATCH
            and invoker_cls_permission_level < JobPermissionLevels.HIGH
        ):
            if raise_exceptions:
                raise JobPermissionError(
                    f"insufficient permission level of {invoker_cls.__qualname__} "
                    f"({invoker_cls_permission_level.name}) "
                    f"for dispatching non-custom events to job objects "
                )
            return False

        elif op is JobVerbs.UNSCHEDULE:
            if schedule_identifier is None or invoker_identifier is None:
                raise TypeError(
                    "argument 'schedule_identifier' and 'invoker_identifier' "
                    "cannot be None if argument 'op' is 'UNSCHEDULE'"
                )

            if invoker_cls_permission_level < JobPermissionLevels.MEDIUM:
                if raise_exceptions:
                    raise JobPermissionError(
                        f"insufficient permission level of {invoker_cls.__qualname__} "
                        f"({invoker_cls_permission_level.name}) "
                        f"for {_JOB_VERBS_PRES_CONT[op.name].lower()} "
                        "job objects"
                    )
                return False

            if (
                invoker_identifier in self._job_id_map
            ):  # the schedule operation belongs to an alive job
                target = self._job_id_map[invoker_identifier]
                # the target is now the job that scheduled a specific operation
                target_cls = target.__class__

                target_cls_permission_level = get_job_class_permission_level(target_cls)

                if (
                    invoker_cls_permission_level == JobPermissionLevels.MEDIUM
                    and invoker._identifier != invoker_identifier
                ):
                    if raise_exceptions:
                        raise JobPermissionError(
                            f"insufficient permission level of '{invoker_cls.__qualname__}' "
                            f"({invoker_cls_permission_level.name}) "
                            f"for {_JOB_VERBS_PRES_CONT[op.name].lower()} "
                            "jobs that were scheduled by the class "
                            f"'{target_cls.__qualname__}' "
                            f"({target_cls_permission_level.name}) "
                            "when the scheduler job is still alive and is not the "
                            "invoker job"
                        )
                    return False

                elif (
                    invoker_cls_permission_level == JobPermissionLevels.HIGH
                    and target_cls_permission_level >= JobPermissionLevels.HIGH
                ):
                    if raise_exceptions:
                        raise JobPermissionError(
                            f"insufficient permission level of '{invoker_cls.__qualname__}' "
                            f"({invoker_cls_permission_level.name}) "
                            f"for {_JOB_VERBS_PRES_CONT[op.name].lower()} "
                            f"jobs that were scheduled by the class '{target_cls.__qualname__}' "
                            f"({target_cls_permission_level.name}) "
                        )
                    return False

        if op in (
            JobVerbs.CREATE,
            JobVerbs.INITIALIZE,
            JobVerbs.REGISTER,
            JobVerbs.SCHEDULE,
        ):
            target_cls_permission_level = get_job_class_permission_level(target_cls)

            if invoker_cls_permission_level < JobPermissionLevels.MEDIUM:
                if raise_exceptions:
                    raise JobPermissionError(
                        f"insufficient permission level of {invoker_cls.__qualname__} "
                        f"({invoker_cls_permission_level.name}) "
                        f"for {_JOB_VERBS_PRES_CONT[op.name].lower()} job objects"
                    )
                return False

            elif invoker_cls_permission_level == JobPermissionLevels.MEDIUM:
                if target_cls_permission_level >= JobPermissionLevels.MEDIUM:
                    if raise_exceptions:
                        raise JobPermissionError(
                            f"insufficient permission level of '{invoker_cls.__qualname__}' "
                            f"({invoker_cls_permission_level.name}) "
                            f"for {_JOB_VERBS_PRES_CONT[op.name].lower()} "
                            f"job objects of the specified class '{target_cls.__qualname__}' "
                            f"({target_cls_permission_level.name})"
                        )
                    return False

            elif (
                invoker_cls_permission_level == JobPermissionLevels.HIGH
                and target_cls_permission_level > JobPermissionLevels.HIGH
            ) or (
                invoker_cls_permission_level == JobPermissionLevels.HIGHEST
                and target_cls_permission_level > JobPermissionLevels.HIGHEST
            ):
                if raise_exceptions:
                    raise JobPermissionError(
                        f"insufficient permission level of '{invoker_cls.__qualname__}' "
                        f"({invoker_cls_permission_level.name}) "
                        f"for {_JOB_VERBS_PRES_CONT[op.name].lower()} "
                        f"job objects of the specified class '{target_cls.__qualname__}' "
                        f"({target_cls_permission_level.name})"
                    )
                return False

        elif op in (JobVerbs.GUARD, JobVerbs.UNGUARD):

            if target is None:
                raise TypeError(
                    "argument 'target'"
                    " cannot be None if argument 'op' is 'START',"
                    " 'RESTART', 'STOP' 'KILL', 'GUARD' or 'UNGUARD'"
                )

            target_cls_permission_level = get_job_class_permission_level(target_cls)

            if invoker_cls_permission_level < JobPermissionLevels.HIGH:
                if raise_exceptions:
                    raise JobPermissionError(
                        f"insufficient permission level of {invoker_cls.__qualname__} "
                        f"({invoker_cls_permission_level.name}) "
                        f"for {_JOB_VERBS_PRES_CONT[op.name].lower()} job objects"
                    )
                return False

            elif invoker_cls_permission_level in (
                JobPermissionLevels.HIGH,
                JobPermissionLevels.HIGHEST,
            ):
                if target._creator is not invoker:
                    if raise_exceptions:
                        raise JobPermissionError(
                            f"insufficient permission level of '{invoker_cls.__qualname__}' "
                            f"({invoker_cls_permission_level.name}) "
                            f"for {_JOB_VERBS_PRES_CONT[op.name].lower()} "
                            f"job objects of the specified class '{target_cls.__qualname__}' "
                            f"({target_cls_permission_level.name}) "
                            "its instance did not create."
                        )
                    return False

        elif op in (
            JobVerbs.START,
            JobVerbs.RESTART,
            JobVerbs.STOP,
            JobVerbs.KILL,
        ):
            if target is None:
                raise TypeError(
                    "argument 'target'"
                    " cannot be None if argument 'op' is 'START',"
                    " 'RESTART', 'STOP' 'KILL' or 'GUARD'"
                )

            target_cls_permission_level = get_job_class_permission_level(target_cls)

            if invoker_cls_permission_level < JobPermissionLevels.MEDIUM:
                raise JobPermissionError(
                    f"insufficient permission level of {invoker_cls.__qualname__}"
                    f" ({invoker_cls_permission_level.name})"
                    f" for {_JOB_VERBS_PRES_CONT[op.name].lower()} job objects"
                )
            elif invoker_cls_permission_level == JobPermissionLevels.MEDIUM:
                if (
                    target_cls_permission_level < JobPermissionLevels.MEDIUM
                    and target._creator is not invoker
                ):
                    if raise_exceptions:
                        raise JobPermissionError(
                            f"insufficient permission level of '{invoker_cls.__qualname__}' "
                            f"({invoker_cls_permission_level.name}) "
                            f"for {_JOB_VERBS_PRES_CONT[op.name].lower()} "
                            f"job objects of the specified class '{target_cls.__qualname__}' "
                            f"({target_cls_permission_level.name}) that "
                            "its instance did not create."
                        )
                    return False

                elif target_cls_permission_level >= JobPermissionLevels.MEDIUM:
                    if raise_exceptions:
                        raise JobPermissionError(
                            f"insufficient permission level of '{invoker_cls.__qualname__}' "
                            f"({invoker_cls_permission_level.name}) "
                            f"for {_JOB_VERBS_PRES_CONT[op.name].lower()} "
                            f"job objects of the specified class '{target_cls.__qualname__}' "
                            f"({target_cls_permission_level.name})"
                        )
                    return False

            elif invoker_cls_permission_level == JobPermissionLevels.HIGH:
                if target_cls_permission_level >= JobPermissionLevels.HIGH:
                    if raise_exceptions:
                        raise JobPermissionError(
                            f"insufficient permission level of '{invoker_cls.__qualname__}' "
                            f"({invoker_cls_permission_level.name}) "
                            f"for {_JOB_VERBS_PRES_CONT[op.name].lower()} "
                            f"job objects of the specified class '{target_cls.__qualname__}' "
                            f"({target_cls_permission_level.name})"
                        )
                    return False

            elif invoker_cls_permission_level == JobPermissionLevels.HIGHEST:
                if target_cls_permission_level > JobPermissionLevels.HIGHEST:
                    if raise_exceptions:
                        raise JobPermissionError(
                            f"insufficient permission level of '{invoker_cls.__qualname__}' "
                            f"({invoker_cls_permission_level.name}) "
                            f"for {_JOB_VERBS_PRES_CONT[op.name].lower()} "
                            f"job objects of the specified class '{target_cls.__qualname__}' "
                            f"({target_cls_permission_level.name})"
                        )
                    return False

        return True

    def create_job(
        self,
        cls: Union[Type[EventJobBase], Type[IntervalJobBase]],
        *args,
        _return_proxy=True,
        _iv: Optional[Union[EventJobBase, IntervalJobBase]] = None,
        **kwargs,
    ) -> "proxies.JobProxy":
        """Create an instance of a job class, and return it.

        Args:
            cls (Union[Type[EventJobBase], Type[IntervalJobBase]]):
               The job class to instantiate a job object from.

        Raises:
            RuntimeError: This job manager object is not initialized.

        Returns:
            JobProxy: A job proxy object.
        """

        self._check_init_and_running()

        if isinstance(_iv, (EventJobBase, IntervalJobBase)):
            self._verify_permissions(_iv, op=JobVerbs.CREATE, target_cls=cls)
        else:
            _iv = self._manager_job

        job = cls(*args, **kwargs)
        job._manager = proxies.JobManagerProxy(self, job)
        job._creator = _iv
        proxy = job._proxy

        if _return_proxy:
            return proxy
        return job

    def _get_job_from_proxy(
        self, job_proxy: "proxies.JobProxy"
    ) -> Union[EventJobBase, IntervalJobBase]:
        try:
            job = job_proxy._JobProxy__j
        except AttributeError:
            raise TypeError("invalid job proxy") from None
        return job

    async def initialize_job(
        self,
        job_proxy: "proxies.JobProxy",
        raise_exceptions: bool = True,
        _iv: Optional[Union[EventJobBase, IntervalJobBase]] = None,
    ) -> bool:
        """Initialize a job object.

        Args:
            job_proxy (JobProxy): The proxy to the job object.
            raise_exceptions (bool, optional): Whether exceptions should be raised.
              Defaults to True.

        Raises:
            JobInitializationError: The job given was already initialized.

        Returns:
            bool: Whether the initialization attempt was successful.
        """

        self._check_init_and_running()

        job = self._get_job_from_proxy(job_proxy)

        if isinstance(_iv, (EventJobBase, IntervalJobBase)):
            self._verify_permissions(_iv, op=JobVerbs.INITIALIZE, target=job)
        else:
            _iv = self._manager_job

        if job._is_being_guarded and _iv is not job._guardian:
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
        job_proxy: "proxies.JobProxy",
        start: bool = True,
        _iv: Optional[Union[EventJobBase, IntervalJobBase]] = None,
    ):
        """Register a job object to this JobManager,
        while initializing it if necessary.

        Args:
            job (JobProxy): The job object to be registered.
            start (bool): Whether the given job object should start automatically
              upon registration.

        Raises:
            JobStateError: Invalid job state for registration.
            JobError: job-specific errors preventing registration.
            RuntimeError: This job manager object is not initialized.
        """

        self._check_init_and_running()

        job = self._get_job_from_proxy(job_proxy)

        if isinstance(_iv, (EventJobBase, IntervalJobBase)):
            self._verify_permissions(_iv, op=JobVerbs.REGISTER, target=job)
        else:
            _iv = self._manager_job

        if job._is_being_guarded and _iv is not job._guardian:
            raise JobStateError(
                "the given target job object is being guarded by another job"
            ) from None

        if job._killed:
            raise JobStateError("cannot register a killed job object")

        if not job._initialized:
            await self.initialize_job(job._proxy)

        if (
            isinstance(job, _SingletonMixinJobBase)
            and job.__class__._IDENTIFIER in self._job_type_count_dict
            and self._job_type_count_dict[job.__class__._IDENTIFIER]
        ):
            raise JobError(
                "cannot have more than one instance of a"
                f" '{job.__class__.__qualname__}' job registered at a time."
            )

        self._add_job(job, start=start)
        job._registered_at_ts = time.time()

    async def create_and_register_job(
        self,
        cls: Union[Type[EventJobBase], Type[IntervalJobBase]],
        *args,
        start: bool = True,
        _return_proxy: bool = True,
        _iv: Optional[Union[EventJobBase, IntervalJobBase]] = None,
        **kwargs,
    ) -> "proxies.JobProxy":
        """Create an instance of a job class, and register it to this `BotTaskManager`.

        Args:
            cls (Union[Type[EventJobBase], Type[IntervalJobBase]]): The job class to be
              used for instantiation.
            start (bool): Whether the given job object should start automatically
              upon registration.

        Returns:
            JobProxy: A job proxy object.
        """
        j = self.create_job(cls, *args, _return_proxy=False, **kwargs)
        await self.register_job(j._proxy, start=start, _iv=_iv)
        if _return_proxy:
            return j._proxy
        return j

    async def create_job_schedule(
        self,
        cls: Union[Type[EventJobBase], Type[IntervalJobBase]],
        timestamp: Union[int, float, datetime.datetime],
        recur_interval: Optional[Union[int, float, datetime.timedelta]] = None,
        max_recurrences: int = -1,
        job_args: tuple = (),
        job_kwargs: Optional[dict] = None,
        _iv: Optional[Union[EventJobBase, IntervalJobBase]] = None,
    ) -> str:
        """Schedule a job of a specific type to be instantiated and to run at
        one or more specific periods of time. Each job can receive positional
        or keyword arguments which are passed to this method.
        Those arguments must be pickleable.

        Args:
            cls (Union[Type[EventJobBase], Type[IntervalJobBase]]): The job type to
              schedule.
            timestamp (Union[int, float, datetime.datetime]): The exact timestamp
              or offset at which to instantiate a job.
            recur_interval (Optional[Union[int, float, datetime.timedelta]], optional):
              The interval at which a job should be rescheduled in seconds. `None` or
              0 means that no recurrences will occur. -1 means that the smallest
              possible recur interval should be used. Defaults to None.
            max_recurrences (int, optional): The maximum amount of recurrences for
              rescheduling. A value of -1 means that no maximum is set. Otherwise,
              the value of this argument must be a non-zero positive integer. If no
              `recur_interval` value was provided, the value of this argument will
              be ignored during scheduling and set to -1. Defaults to -1.
            job_args (tuple, optional): Positional arguments to pass to the
              scheduled job upon instantiation. Defaults to ().
            job_kwargs (dict, optional): Keyword arguments to pass to the scheduled
              job upon instantiation. Defaults to None.

        Returns:
            str: The string identifier of the scheduling operation.

        Raises:
            RuntimeError: The job manager has not yet initialized job scheduling,
              or this job manager object is not initialized.
            TypeError: Invalid argument types were given.
        """

        self._check_init_and_running()
        self._check_scheduling_init()

        if not issubclass(cls, (EventJobBase, IntervalJobBase)):
            raise TypeError(
                f"argument 'cls' must be of a subclass of 'EventJobBase' or 'IntervalJobBase', not '{cls}'"
            ) from None

        if isinstance(_iv, (EventJobBase, IntervalJobBase)):
            self._verify_permissions(_iv, op=JobVerbs.SCHEDULE, target_cls=cls)
        else:
            _iv = self._manager_job

        class_scheduling_identifier = get_job_class_scheduling_identifier(cls, None)
        if class_scheduling_identifier is None:
            raise TypeError(f"job class '{cls.__qualname__}' is not schedulable")

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
            "invoker_identifier": _iv.identifier if _iv is not None else "",
            "schedule_identifier": "",
            "schedule_timestamp_ns_str": schedule_timestamp_ns_str,
            "timestamp_ns_str": timestamp_ns_str,
            "recur_interval": recur_interval_num,
            "occurences": 0,
            "max_recurrences": max_recurrences,
            "class_scheduling_identifier": class_scheduling_identifier,
            "job_args": tuple(job_args),
            "job_kwargs": job_kwargs if job_kwargs is not None else {},
        }

        new_data[
            "schedule_identifier"
        ] = (
            schedule_identifier
        ) = f"{self._identifier}-{timestamp_ns_str}-{schedule_timestamp_ns_str}"

        async with self._schedule_dict_lock:
            if timestamp_ns_str not in self._schedule_dict:
                self._schedule_dict[timestamp_ns_str] = {}

            self._schedule_dict[timestamp_ns_str][schedule_identifier] = new_data
            self._schedule_ids.add(schedule_identifier)

        return schedule_identifier

    def get_job_schedule_identifiers(self) -> Optional[tuple[str]]:
        """Return a tuple of all job schedule identifiers pointing to
        scheduling data.

        Returns:
            tuple: The job schedule identifiers.
        """

        return tuple(self._schedule_ids)

    def job_schedule_has_failed(self, schedule_identifier: str) -> bool:
        """Whether the job schedule operation with the specified schedule
        identifier failed.

        Args:
            schedule_identifier (str): A string identifier following this structure:
              'JOB_MANAGER_IDENTIFIER-TARGET_TIMESTAMP_IN_NS-SCHEDULING_TIMESTAMP_IN_NS'

        Returns:
            bool: True/False

        Raises:
            ValueError: Invalid schedule identifier.
        """

        split_id = schedule_identifier.split("-")

        if len(split_id) != 4 and not all(s.isnumeric() for s in split_id):
            raise ValueError("invalid schedule identifier")

        return schedule_identifier in self._schedule_dict[0]

    def has_job_schedule(self, schedule_identifier: str) -> bool:
        """Whether the job schedule operation with the specified schedule
        identifier exists.

        Args:
            schedule_identifier (str): A string identifier following this structure:
              'JOB_MANAGER_IDENTIFIER-TARGET_TIMESTAMP_IN_NS-SCHEDULING_TIMESTAMP_IN_NS'

        Returns:
            bool: Whether the schedule identifier leads to existing scheduling data.

        Raises:
            ValueError: Invalid schedule identifier.
        """

        split_id = schedule_identifier.split("-")

        if len(split_id) != 4 and not all(s.isnumeric() for s in split_id):
            raise ValueError("invalid schedule identifier")

        return schedule_identifier in self._schedule_ids

    async def remove_job_schedule(
        self,
        schedule_identifier: str,
        _iv: Optional[Union[EventJobBase, IntervalJobBase]] = None,
    ) -> bool:
        """Remove a job schedule operation using the string identifier
        of the schedule operation.

        Args:
            schedule_identifier (str): A string identifier following
              this structure:
              'JOB_MANAGER_IDENTIFIER-TARGET_TIMESTAMP_IN_NS-SCHEDULING_TIMESTAMP_IN_NS'

        Returns:
            bool: Whether the call was successful.

        Raises:
            ValueError: Invalid schedule identifier.
            KeyError: No operation matching the given schedule identifier was found.
            JobPermissionError: Insufficient permissions.
        """

        self._check_init_and_running()
        self._check_scheduling_init()

        split_id = schedule_identifier.split("-")

        if len(split_id) != 4 and not all(s.isnumeric() for s in split_id):
            raise ValueError("invalid schedule identifier")

        (
            mgr_id_start,
            mgr_id_end,
            target_timestamp_num_str,
            schedule_num_str,
        ) = split_id

        mgr_identifier = f"{mgr_id_start}-{mgr_id_end}"

        async with self._schedule_dict_lock:
            if target_timestamp_num_str in self._schedule_dict:
                schedules_data = self._schedule_dict[target_timestamp_num_str]
                if isinstance(schedules_data, bytes):
                    async with self._process_pool_executor_lock:
                        self._schedule_dict[
                            target_timestamp_num_str
                        ] = await self._loop.run_in_executor(
                            self._process_pool_executor,
                            self._unpickle_dict,
                            schedules_data,
                        )

                if schedule_identifier in self._schedule_dict[target_timestamp_num_str]:
                    if isinstance(_iv, (EventJobBase, IntervalJobBase)):
                        invoker_identifier = self._schedule_dict[
                            target_timestamp_num_str
                        ][schedule_identifier]["invoker_identifier"]
                        self._verify_permissions(
                            _iv,
                            op=JobVerbs.UNSCHEDULE,
                            schedule_identifier=schedule_identifier,
                            invoker_identifier=invoker_identifier,
                        )
                    else:
                        _iv = self._manager_job

                    del self._schedule_dict[target_timestamp_num_str][
                        schedule_identifier
                    ]
                    self._schedule_ids.remove(schedule_identifier)
                    return True

            raise KeyError(
                f"cannot find any scheduled operation with the identifier '{schedule_identifier}'"
            )

        return True

    async def clear_job_schedules(
        self,
        _iv: Optional[Union[EventJobBase, IntervalJobBase]] = None,
    ):
        """Remove all job schedule operations. This obviously can't
        be undone. This will stop job scheduling, clear data, and restart
        it again when done if it was running.
        """

        was_init = self._scheduling_is_initialized

        if was_init:
            self.uninitialize_job_scheduling()

        async with self._schedule_dict_lock:
            fails = self._schedule_dict[0]
            fails.clear()
            self._schedule_dict.clear()
            self._schedule_dict[0] = fails
            self._schedule_ids.clear()

        if was_init:
            self.initialize_job_scheduling()

    def __iter__(self):
        return iter(job._proxy for job in self._job_id_map.values())

    def _add_job(
        self,
        job: Union[EventJobBase, IntervalJobBase],
        start: bool = True,
    ):
        """
        THIS METHOD IS ONLY MEANT FOR INTERNAL USE BY THIS CLASS.

        Add the given job object to this job manager, and start it.

        Args:
            job: Union[EventJobBase, IntervalJobBase]:
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

        if job._completed or job._killed:
            raise JobStateError(
                "cannot add a job that has is not alive to a JobManager instance"
            ) from None

        elif job._identifier in self._job_id_map:
            raise RuntimeError(
                "the given job is already present in this manager"
            ) from None

        elif not job._initialized:
            raise JobInitializationError("the given job was not initialized") from None

        if isinstance(job, EventJobBase):
            for ce_type in job.EVENT_TYPES:
                if ce_type._IDENTIFIER not in self._event_job_ids:
                    self._event_job_ids[ce_type._IDENTIFIER] = set()
                self._event_job_ids[ce_type._IDENTIFIER].add(job._identifier)

        elif isinstance(job, IntervalJobBase):
            self._interval_job_ids.add(job._identifier)
        else:
            raise TypeError(
                f"expected an instance of EventJobBase or IntervalJobBase subclasses, "
                f"not {job.__class__.__qualname__}"
            ) from None

        if job.__class__._IDENTIFIER not in self._job_type_count_dict:
            self._job_type_count_dict[job.__class__._IDENTIFIER] = 0

        self._job_type_count_dict[job.__class__._IDENTIFIER] += 1

        self._job_id_map[job._identifier] = job

        job._registered_at_ts = time.time()

        if start:
            job._task_loop.start()

    def _remove_job(self, job: Union[EventJobBase, IntervalJobBase]):
        """THIS METHOD IS ONLY MEANT FOR INTERNAL USE BY THIS CLASS and job manager
        proxies.

        Remove the given job object from this job manager.

        Args:
            *jobs (Union[EventJobBase, IntervalJobBase]):
                The job to be removed, if present.
        Raises:
            TypeError: An invalid object was given as a job.
        """
        if not isinstance(job, (EventJobBase, IntervalJobBase)):
            raise TypeError(
                f"expected an instance of class EventJobBase or IntervalJobBase "
                f", not {job.__class__.__qualname__}"
            ) from None

        if (
            isinstance(job, IntervalJobBase)
            and job._identifier in self._interval_job_ids
        ):
            self._interval_job_ids.remove(job._identifier)

        elif isinstance(job, EventJobBase):
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

    def _remove_jobs(self, *jobs: Union[EventJobBase, IntervalJobBase]):
        """
        THIS METHOD IS ONLY MEANT FOR INTERNAL USE BY THIS CLASS.

        Remove the given job objects from this job manager.

        Args:
            *jobs: Union[EventJobBase, IntervalJobBase]: The jobs to be removed, if
              present.
        Raises:
            TypeError: An invalid object was given as a job.
        """
        for job in jobs:
            self._remove_job(job)

    def has_job(self, job_proxy: "proxies.JobProxy") -> bool:
        """Whether a job is contained in this job manager.

        Args:
            job_proxy (JobProxy): The proxy to the job object to look
              for.

        Returns:
            bool: True/False
        """

        self._check_init_and_running()

        job = self._get_job_from_proxy(job_proxy)

        return job in self._job_id_map.values()

    def has_job_identifier(self, identifier: str) -> bool:
        """Whether a job with the given identifier is contained in this job manager.

        Args:
            identifier (str): The job identifier.

        Returns:
            bool: True/False
        """

        self._check_init_and_running()

        return identifier in self._job_id_map

    def find_job(
        self,
        *,
        identifier: Optional[str] = None,
        created_at: Optional[datetime.datetime] = None,
        _return_proxy: bool = True,
        _iv: Optional[Union[EventJobBase, IntervalJobBase]] = None,
    ) -> Optional["proxies.JobProxy"]:
        """Find the first job that matches the given criteria specified as arguments,
        and return a proxy to it, otherwise return `None`.

        Args:

            identifier (Optional[str], optional): The exact identifier of the job to find. This
              argument overrides any other parameter below. Defaults to None.
            created_at (Optional[datetime.datetime], optional): The exact creation date of the
              job to find. Defaults to None.

        Raises:
            TypeError: One of the arguments must be specified.

        Returns:
            JobProxy: The proxy of the job object, if present.
            None: No matching job object found.
        """

        self._check_init_and_running()

        if isinstance(_iv, (EventJobBase, IntervalJobBase)):
            self._verify_permissions(_iv, op=JobVerbs.FIND)
        else:
            _iv = self._manager_job

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
        classes: tuple[
            Union[
                Type[EventJobBase],
                Type[IntervalJobBase],
            ]
        ] = tuple(),
        exact_class_match: bool = False,
        created_before: Optional[datetime.datetime] = None,
        created_after: Optional[datetime.datetime] = None,
        permission_level: Optional[JobPermissionLevels] = None,
        above_permission_level: Optional[JobPermissionLevels] = None,
        below_permission_level: Optional[
            JobPermissionLevels
        ] = JobPermissionLevels.SYSTEM,
        alive: Optional[bool] = None,
        is_starting: Optional[bool] = None,
        is_running: Optional[bool] = None,
        is_idling: Optional[bool] = None,
        is_awaiting: Optional[bool] = None,
        is_stopping: Optional[bool] = None,
        is_restarting: Optional[bool] = None,
        is_being_killed: Optional[bool] = None,
        is_being_completed: Optional[bool] = None,
        stopped: Optional[bool] = None,
        _return_proxy: bool = True,
        _iv: Optional[Union[EventJobBase, IntervalJobBase]] = None,
    ) -> tuple["proxies.JobProxy"]:
        """Find jobs that match the given criteria specified as arguments,
        and return a tuple of proxy objects to them.

        Args:
            classes: (
                 Optional[
                    Union[
                        Type[EventJobBase],
                        Type[IntervalJobBase],
                        tuple[
                            Union[
                                Type[EventJobBase],
                                Type[IntervalJobBase]
                            ]
                        ]
                    ]
                ]
            , optional): The class(es) of the job objects to limit the job search to,
              excluding subclasses. Defaults to None.
            exact_class_match (bool, optional): Whether an exact match is required for
              the classes in the previous parameter, or subclasses are allowed too.
              Defaults to False.
            created_before (Optional[datetime.datetime], optional): The lower age limit
              of the jobs to find. Defaults to None.
            created_after (Optional[datetime.datetime], optional): The upper age limit
              of the jobs to find. Defaults to None.
            permission_level (Optional[JobPermissionLevels], optional): The permission
              level of the jobs to find. Defaults to None.
            above_permission_level (Optional[JobPermissionLevels], optional): The lower
              permission level value of the jobs to find. Defaults to None.
            below_permission_level (Optional[JobPermissionLevels], optional): The upper
              permission level value of the jobs to find. Defaults to
              `JobPermissionLevels.SYSTEM`.
            created_before (Optional[datetime.datetime], optional): The lower age limit
              of the jobs to find. Defaults to None.
            created_after (Optional[datetime.datetime], optional): The upper age limit
              of the jobs to find. Defaults to None.
            alive (Optional[bool], optional): A boolean that a job's state should
              match. Defaults to None.
            is_running (Optional[bool], optional): A boolean that a job's state
              should match. Defaults to None.
            is_idling (Optional[bool], optional): A boolean that a job's state
              should match. Defaults to None.
            is_awaiting (Optional[bool], optional): A boolean that a job's state
              should match. Defaults to None.
            is_stopping (Optional[bool], optional): A boolean that a job's state
              should match. Defaults to None.
            stopped (Optional[bool], optional): A boolean that a job's state should
              match. Defaults to None.
            is_restarting (Optional[bool], optional): A boolean that a job's
              state should match. Defaults to None.
            is_being_killed (Optional[bool], optional): A boolean that a job's
              state should match. Defaults to None.
            is_being_completed (Optional[bool], optional): A boolean that a job's state
              should match. Defaults to None.

        Returns:
            tuple: A tuple of the job object proxies that were found.
        """

        self._check_init_and_running()

        if isinstance(_iv, (EventJobBase, IntervalJobBase)):
            self._verify_permissions(_iv, op=JobVerbs.FIND)
        else:
            _iv = self._manager_job

        filter_functions = []

        if classes:
            if isinstance(classes, type):
                if issubclass(classes, (EventJobBase, IntervalJobBase)):
                    classes = (classes,)
                else:
                    raise TypeError(
                        f"'classes' must be a tuple of 'EventJobBase' or 'IntervalJobBase' subclasses or a single subclass"
                    ) from None

            elif isinstance(classes, tuple):
                if not all(
                    issubclass(c, (EventJobBase, IntervalJobBase)) for c in classes
                ):
                    raise TypeError(
                        f"'classes' must be a tuple of 'EventJobBase' or 'IntervalJobBase' subclasses or a single subclass"
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
                    f"'created_before' must be of type 'datetime.datetime', not "
                    f"{type(created_before)}"
                ) from None

        if created_after is not None:
            if isinstance(created_after, datetime.datetime):
                filter_functions.append(
                    lambda job, created_after=None: job.created_at > created_after
                )
            else:
                raise TypeError(
                    f"'created_after' must be of type 'datetime.datetime', not "
                    f"{type(created_after)}"
                ) from None

        if permission_level is not None:
            if not isinstance(permission_level, JobPermissionLevels):
                raise TypeError(
                    "argument 'permission_level' must be an enum value from the "
                    f"JobPermissionLevels enum"
                )

            filter_functions.append(
                lambda job: job.permission_level is permission_level
            )

        if below_permission_level is not None:
            if not isinstance(below_permission_level, JobPermissionLevels):
                raise TypeError(
                    "argument 'below_permission_level' must be an enum value from the "
                    f"JobPermissionLevels enum"
                )

            filter_functions.append(
                lambda job: job.permission_level < below_permission_level
            )

        if above_permission_level is not None:
            if not isinstance(above_permission_level, JobPermissionLevels):
                raise TypeError(
                    "argument 'above_permission_level' must be an enum value from the "
                    f"JobPermissionLevels enum"
                )

            filter_functions.append(
                lambda job: job.permission_level > above_permission_level
            )

        if alive is not None:
            alive = bool(alive)
            filter_functions.append(lambda job: job.alive() is alive)

        if is_starting is not None:
            is_starting = bool(is_starting)
            filter_functions.append(lambda job: job.is_starting() is is_starting)

        if is_running is not None:
            is_running = bool(is_running)
            filter_functions.append(lambda job: job.is_running() is is_running)

        if is_idling is not None:
            is_running = bool(is_idling)
            filter_functions.append(
                lambda job, is_idling=None: job.is_idling() is is_idling
            )

        if stopped is not None:
            stopped = bool(stopped)
            filter_functions.append(lambda job: job.stopped() is stopped)

        if is_awaiting is not None:
            is_running = bool(is_awaiting)
            filter_functions.append(lambda job: job.is_awaiting() is is_awaiting)

        if is_stopping is not None:
            is_running = bool(is_stopping)
            filter_functions.append(lambda job: job.is_stopping() is is_stopping)

        if is_restarting is not None:
            is_restarting = bool(is_restarting)
            filter_functions.append(lambda job: job.is_restarting() is is_restarting)

        if is_being_killed is not None:
            is_being_killed = bool(is_being_killed)
            filter_functions.append(
                lambda job: job.is_being_killed() is is_being_killed
            )

        if is_being_completed is not None:
            is_being_completed = bool(is_being_completed)
            filter_functions.append(
                lambda job: job.is_being_completed() is is_being_completed
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
        job_proxy: "proxies.JobProxy",
        _iv: Optional[Union[EventJobBase, IntervalJobBase]] = None,
    ) -> bool:

        """Start the given job object, if is hasn't already started.

        Args:
            job_proxy (JobProxy): The proxy to the job object.

        Returns:
            bool: Whether the operation was successful.
        """

        self._check_init_and_running()

        job = self._get_job_from_proxy(job_proxy)

        if isinstance(_iv, (EventJobBase, IntervalJobBase)):
            self._verify_permissions(_iv, op=JobVerbs.START, target=job)
        else:
            _iv = self._manager_job

        if job._is_being_guarded and _iv is not job._guardian:
            raise JobStateError(
                "the given target job object is being guarded by another job"
            ) from None

        return job._START_EXTERNAL()

    def restart_job(
        self,
        job_proxy: Union[IntervalJobBase, EventJobBase, "proxies.JobProxy"],
        stopping_timeout: Optional[float] = None,
        _iv: Optional[Union[EventJobBase, IntervalJobBase]] = None,
    ) -> bool:
        """Restart the given job object. This provides a cleaner way
        to forcefully stop a job and restart it, or to wake it up from
        a stopped state.

        Args:
            job_proxy (JobProxy): The proxy to the job object.
            stopping_timeout (Optional[float], optional):
              An optional timeout in seconds for the maximum time period
              for stopping the job while it is restarting. This overrides
              the global timeout of this job manager if present.
        Returns:
            bool: Whether the operation was initiated by the job.
        """

        self._check_init_and_running()

        job = self._get_job_from_proxy(job_proxy)

        if isinstance(_iv, (EventJobBase, IntervalJobBase)):
            self._verify_permissions(_iv, op=JobVerbs.RESTART, target=job)
        else:
            _iv = self._manager_job

        if job._is_being_guarded and _iv is not job._guardian:
            raise JobStateError(
                "the given target job object is being guarded by another job"
            ) from None

        if stopping_timeout:
            stopping_timeout = float(stopping_timeout)
            job._manager._job_stop_timeout = stopping_timeout

        return job._RESTART_EXTERNAL()

    def stop_job(
        self,
        job_proxy: "proxies.JobProxy",
        stopping_timeout: Optional[float] = None,
        force: bool = False,
        _iv: Optional[Union[EventJobBase, IntervalJobBase]] = None,
    ) -> bool:
        """Stop the given job object.

        Args:
            job_proxy (JobProxy): The proxy to the job object.
            force (bool): Whether to suspend all operations of the job forcefully.
            stopping_timeout (Optional[float], optional): An optional timeout in
              seconds for the maximum time period for stopping the job. This
              overrides the global timeout of this job manager if present.

        Returns:
            bool: Whether the operation was successful.
        """

        self._check_init_and_running()

        job = self._get_job_from_proxy(job_proxy)

        if isinstance(_iv, (EventJobBase, IntervalJobBase)):
            self._verify_permissions(_iv, op=JobVerbs.STOP, target=job)
        else:
            _iv = self._manager_job

        if job._is_being_guarded and _iv is not job._guardian:
            raise JobStateError(
                "the given target job object is being guarded by another job"
            ) from None

        if stopping_timeout:
            stopping_timeout = float(stopping_timeout)
            job._manager._job_stop_timeout = stopping_timeout

        return job._STOP_EXTERNAL(force=force)

    def kill_job(
        self,
        job_proxy: "proxies.JobProxy",
        stopping_timeout: Optional[float] = None,
        _iv: Optional[Union[EventJobBase, IntervalJobBase]] = None,
    ) -> bool:
        """Stops a job's current execution unconditionally and remove it from its
        job manager.

        Args:
            job_proxy (JobProxy): The proxy to the job object.
            stopping_timeout (Optional[float], optional):
              An optional timeout in seconds for the maximum time period for
              stopping the job while it is being killed. This overrides the
              global timeout of this job manager if present.

        Returns:
            bool: Whether the operation was successful.
        """

        self._check_init_and_running()

        job = self._get_job_from_proxy(job_proxy)

        if isinstance(_iv, (EventJobBase, IntervalJobBase)):
            self._verify_permissions(_iv, op=JobVerbs.KILL, target=job)
        else:
            _iv = self._manager_job

        if job._is_being_guarded and _iv is not job._guardian:
            raise JobStateError(
                "the given target job object is being guarded by another job"
            ) from None

        if stopping_timeout:
            stopping_timeout = float(stopping_timeout)
            job._manager._job_stop_timeout = stopping_timeout

        return job._KILL_EXTERNAL(awaken=True)

    def guard_job(
        self,
        job_proxy: "proxies.JobProxy",
        _iv: Optional[Union[EventJobBase, IntervalJobBase]] = None,
    ):
        """Place a guard on the given job object, to prevent unintended state
        modifications by other jobs. This guard can only be broken by other
        jobs when they have a high enough permission level.

        Args:
            job_proxy (JobProxy): The proxy to the job object.

        Raises:
            JobStateError: The given target job object is already being guarded.
        """

        self._check_init_and_running()

        job = self._get_job_from_proxy(job_proxy)

        if isinstance(_iv, (EventJobBase, IntervalJobBase)):
            self._verify_permissions(_iv, op=JobVerbs.GUARD, target=job)
        else:
            _iv = self._manager_job

        if job._is_being_guarded:
            raise JobStateError(
                "the given target job object is already being guarded by a job"
            )

        if _iv._guarded_job_proxies_dict is None:
            _iv._guarded_job_proxies_dict = {}

        if job._identifier not in _iv._guarded_job_proxies_dict:
            job._guardian = _iv
            _iv._guarded_job_proxies_dict[job._identifier] = job._proxy
            job._is_being_guarded = True
        else:
            raise JobStateError(
                "the given target job object is already"
                " being guarded by the invoker job object"
            )

    def unguard_job(
        self,
        job_proxy: "proxies.JobProxy",
        _iv: Optional[Union[EventJobBase, IntervalJobBase]] = None,
    ):
        """Remove the guard on the given job object, to prevent unintended state
        modifications by other jobs.

        Args:
            job_proxy (JobProxy): The proxy to the job object.

        Raises:
            JobStateError: The given target job object is not being guarded by a job.
            JobStateError: The given target job object is already being guarded by
              the invoker job object.
        """

        self._check_init_and_running()

        job = self._get_job_from_proxy(job_proxy)

        if isinstance(_iv, (EventJobBase, IntervalJobBase)):
            self._verify_permissions(_iv, op=JobVerbs.UNGUARD, target=job)
        else:
            _iv = self._manager_job

        if not job._is_being_guarded:
            raise JobStateError("the given job object is not being guarded by a job")

        if (
            _iv._guarded_job_proxies_dict is not None
            and job._identifier in _iv._guarded_job_proxies_dict
        ):
            job._guardian = None
            job._is_being_guarded = False
            del _iv._guarded_job_proxies_dict[job._identifier]

        elif _iv is self._manager_job:
            guardian = job._guardian
            job._guardian = None
            job._is_being_guarded = False

            del guardian._guarded_job_proxies_dict[job._identifier]

        else:
            raise JobStateError(
                "the given target job object is not "
                "being guarded by the invoker job object"
            )

        for fut in job._unguard_futures:
            if not fut.cancelled():
                fut.set_result(True)

        job._unguard_futures.clear()

    def __contains__(self, job_proxy: "proxies.JobProxy"):
        self._check_init_and_running()

        job = self._get_job_from_proxy(job_proxy)
        return job._identifier in self._job_id_map

    def dispatch_event(
        self,
        event: events.BaseEvent,
        _iv: Optional[Union[EventJobBase, IntervalJobBase]] = None,
    ):
        """Dispatch an instance of a `BaseEvent` subclass to all event job
        objects in this job manager that are listening for it.

        Args:
            event (BaseEvent): The event to be dispatched.
        """

        self._check_init_and_running()

        if isinstance(_iv, (EventJobBase, IntervalJobBase)):
            if isinstance(event, events.BaseEvent):
                if isinstance(event, events.CustomEvent):
                    self._verify_permissions(_iv, op=JobVerbs.CUSTOM_EVENT_DISPATCH)
                else:
                    self._verify_permissions(_iv, op=JobVerbs.EVENT_DISPATCH)
            else:
                raise TypeError("argument 'event' must be an instance of BaseEvent")
        else:
            if not isinstance(event, events.BaseEvent):
                raise TypeError("argument 'event' must be an instance of BaseEvent")
            _iv = self._manager_job

        if _iv is not None:
            # for cases where the default _iv might not yet be set
            event._dispatcher = _iv._proxy

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
                event_job._add_event(event.copy())

    def wait_for_event(
        self,
        *event_types: Type[events.BaseEvent],
        check: Optional[Callable[[events.BaseEvent], bool]] = None,
        timeout: Optional[float] = None,
    ) -> Coroutine[Any, Any, events.BaseEvent]:
        """Wait for specific type of event to be dispatched
        and return it as an event object using the given coroutine.

        Args:
            *event_types (Type[events.BaseEvent]): The event type/types to wait for. If
              any of its/their instances is dispatched, that instance will be returned.
            check (Optional[Callable[[events.BaseEvent], bool]], optional): A callable
              obejct used to validate if a valid event that was recieved meets specific
              conditions. Defaults to None.
            timeout: (Optional[float], optional): An optional timeout value in seconds
              for the maximum waiting period.

        Raises:
            TimeoutError: The timeout value was exceeded.
            CancelledError: The future used to wait for an event was cancelled.

        Returns:
            Coroutine: A coroutine that evaluates to a valid `BaseEvent` event object.
        """

        self._check_init_and_running()

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

    def stop_all_jobs(self, force: bool = False):
        """Stop all job objects that are in this job manager."""

        self._check_init_and_running()

        for job in self._job_id_map.values():
            job._STOP_EXTERNAL(force=force)

    def stop_all_interval_jobs(self, force: bool = True):
        """Stop all job objects inheriting from `IntervalJobBase` that are in this job
        manager.
        """

        self._check_init_and_running()

        for job in (
            ij
            for ij in (
                self._job_id_map[identifier] for identifier in self._interval_job_ids
            )
        ):
            if not job.is_being_killed():
                job._STOP_EXTERNAL(force=force)

    def stop_all_event_jobs(self, force: bool = True):
        """Stop all job objects inheriting from `EventJobBase` that are in this job
        manager.
        """

        self._check_init_and_running()

        for ej_id_set in self._event_job_ids.values():
            for job_identifier in ej_id_set:
                if job_identifier in self._job_id_map:
                    job = self._job_id_map[job_identifier]
                    if not job.is_being_killed():
                        job._STOP_EXTERNAL(force=force)

    def kill_all_jobs(self, awaken: bool = True):
        """Kill all job objects that are in this job manager."""

        self._check_init_and_running()

        for job in self._job_id_map.values():
            job._KILL_EXTERNAL(awaken=awaken)

    def kill_all_interval_jobs(self, awaken: bool = True):
        """Kill all job objects inheriting from `IntervalJobBase` that are in this job
        manager.
        """

        self._check_init_and_running()

        for job in (
            ij
            for ij in (
                self._job_id_map[identifier] for identifier in self._interval_job_ids
            )
        ):
            if not job.is_being_killed():
                job._KILL_EXTERNAL(awaken=awaken)

    def kill_all_event_jobs(self, awaken: bool = True):
        """Kill all job objects inheriting from `EventJobBase` that are in this job
        manager.
        """

        self._check_init_and_running()

        for ej_id_set in self._event_job_ids.values():
            for job_identifier in ej_id_set:
                if job_identifier in self._job_id_map:
                    job = self._job_id_map[job_identifier]
                    if not job.is_being_killed():
                        job._KILL_EXTERNAL(awaken=awaken)

    def has_executors(self):
        return (
            self._thread_pool_executor is not None
            and self._process_pool_executor is not None
        )

    def resume(self):
        """Resume the execution of this job manager.

        Raises:
            RuntimeError: This job manager never stopped, or was never initialized.
        """

        self._check_init()
        if self._is_running:
            raise RuntimeError("this job manager is still running")

        if self._process_pool_executor is None:
            self._process_pool_executor = ProcessPoolExecutor(max_workers=4)

        if self._thread_pool_executor is None:
            self._thread_pool_executor = ThreadPoolExecutor(max_workers=4)

        self._is_running = True

    def stop(
        self,
        job_operation: Union[
            Literal[JobVerbs.KILL], Literal[JobVerbs.STOP]
        ] = JobVerbs.KILL,
        shutdown_executors: bool = True,
    ):
        """Stop this job manager from running, while optionally killing/stopping the jobs in it
        and shutting down its executors.

        Args:
            job_operation (Union[JobVerbs.KILL, JobVerbs.STOP]): The operation to
              perform on the jobs in this job manager. Defaults to JobVerbs.KILL.
              Killing will always be done by starting up jobs and killing them immediately.
              Stopping will always be done by force. For more control, use the standalone
              functions for modifiying jobs.
            shutdown_executors (bool, optional): Whether to shut down executors used by this
              job manager, if they aren't required for any future operations like exporting job
              scheduling data. Defaults to True.

        Raises:
            TypeError: Invalid job operation argument.
        """
        if self._scheduling_is_initialized:
            self.uninitialize_job_scheduling()

        if shutdown_executors:
            self._thread_pool_executor.shutdown()
            self._process_pool_executor.shutdown()
            self._thread_pool_executor = None
            self._process_pool_executor = None

        if not isinstance(job_operation, JobVerbs):
            raise TypeError(
                "argument 'job_operation' must be 'KILL' or 'STOP' from the JobVerbs enum"
            )

        if job_operation is JobVerbs.STOP:
            self.stop_all_jobs(force=True)
        elif job_operation is JobVerbs.KILL:
            self.kill_all_jobs(awaken=True)

        self._is_running = False


from . import proxies
