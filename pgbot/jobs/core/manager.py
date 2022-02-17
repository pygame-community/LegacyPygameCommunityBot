"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file implements a job manager class for running and managing job objects
at runtime. 
"""

from __future__ import annotations
import asyncio
from collections import deque
import datetime
import itertools
import inspect
import pickle
import time
from typing import Any, Callable, Coroutine, Iterable, Optional, Sequence, Union, Type

import discord
from discord.ext import tasks

from pgbot.utils import utils
from pgbot import db
from pgbot import common
from pgbot.common import bot as client

# from . import base_jobs, events, serializers

from . import events, base_jobs

BotJobProxy = base_jobs.BotJobProxy
BotJob = base_jobs.BotJob
EventJob = base_jobs.EventJob
ClientEventJob = base_jobs.ClientEventJob
IntervalJob = base_jobs.IntervalJob
JobError = base_jobs.JobError
JobInitializationError = base_jobs.JobInitializationError


class JobLookupError(LookupError):
    """A job lookup operation failed."""


class BotJobManager:
    """The job manager for all interval jobs and event jobs.
    It acts as a container for interval and event job objects, whilst also being responsible dispatching
    events to event job objects. Each of the jobs that a bot job manager
    contains can use a proxy to register new job objects that they instantiate at runtime.
    """

    def __init__(self, loop=None):
        """Create a new bot job manager instance.

        Args:
            *jobs: Union[EventJob, IntervalJob]:
                The job objects to add during initiation.
        """
        if loop is None:
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                self._loop = asyncio.get_event_loop()

        self._loop = loop
        self._event_job_pool = {}
        self._interval_job_pool = set()
        self._job_id_map = {}
        self._job_class_data = base_jobs.JOB_CLASS_MAP
        self._event_waiting_queues = {}
        self._schedule_dict = {}
        self._schedule_dict_fails = {}
        self._running = True
        self._schedule_init = False

    def set_event_loop(self, loop):
        """
        Args:
            loop (AbstractEventLoop): The loop this job is meant to use.

        Raises:
            TypeError: Invalid object given as input
        """
        if not isinstance(loop, asyncio.AbstractEventLoop):
            raise TypeError(
                "Invalid event loop, must be a subclass of asyncio.AbstractEventLoop"
            ) from None
        self._loop = loop

    def is_running(self):
        """Whether this bot task manager is currently running.

        Returns:
            bool: True/False
        """
        return self._running

    @tasks.loop(seconds=2.5, reconnect=False)
    async def job_scheduling_loop(self):
        deletion_list = []
        for i, timestamp in enumerate(tuple(self._schedule_dict.keys())):
            now = datetime.datetime.now(datetime.timezone.utc)
            if now >= timestamp:
                for j, d in enumerate(self._schedule_dict[timestamp]):
                    if d["recur_interval"] is not None:
                        try:
                            if now < (
                                timestamp + (d["recur_interval"] * d["recurrences"])
                            ):
                                continue
                        except OverflowError:
                            deletion_list.append(j)
                            continue

                    if d["class_name"] in self._job_class_data:
                        try:
                            job = self.create_job(
                                base_jobs.JOB_CLASS_MAP[d["class_name"]],
                                *d["job_args"],
                                **d["job_kwargs"],
                            )
                        except Exception as e:
                            print(
                                "Job initiation failed due to an exception:",
                                e.__class__.__name__ + ":",
                                e,
                            )
                            if d["class_name"] not in self._schedule_dict_fails:
                                self._schedule_dict_fails[d["class_name"]] = []

                            self._schedule_dict_fails[d["class_name"]].append(d)
                            deletion_list.append(j)
                            continue
                        else:
                            if not isinstance(job, (EventJob, IntervalJob)):
                                print(
                                    f"Invalid job type found in job class scheduling data: '{type(job).__name__}'"
                                )
                            await self.register_job(job)
                            d["recurrences"] += 1
                    else:
                        print(
                            f"Job initiation failed: Could not find job type called '{d['class']}'"
                        )

                    if not d["recur_interval"] or (
                        d["max_recurrences"] is not None
                        and d["recurrences"] >= d["max_recurrences"]
                    ):
                        deletion_list.append(j)

                    if j % 20:
                        await asyncio.sleep(0)

                for idx in deletion_list:
                    del self._schedule_dict[timestamp][idx]

                deletion_list.clear()
                if not self._schedule_dict[timestamp]:
                    del self._schedule_dict[timestamp]

            if i % 10:
                await asyncio.sleep(0)

    @job_scheduling_loop.before_loop
    async def _job_scheduling_start(self):
        if not self._schedule_init:
            async with db.DiscordDB("job_schedule") as db_obj:
                self._schedule_dict = db_obj.get({})
            self._schedule_init = True

    @job_scheduling_loop.after_loop
    async def _job_scheduling_end(self):
        async with db.DiscordDB("job_schedule") as db_obj:
            db_obj.write(self._schedule_dict)

    def create_job(
        self,
        cls: Type[BotJob],
        *args,
        return_proxy=False,
        **kwargs,
    ):
        """Create an instance of a job class, and return it.

        Args:
            cls (Type[BotJob]): The job class to
            instantiate a job object from.
            return_proxy (bool, optional): Whether a proxy of the job object
            should be returned. Defaults to False.

        Returns:
            BotJobProxy: A job proxy object.
        """

        job = cls(*args, **kwargs)
        job.manager = BotJobManagerProxy(self, job)
        proxy = job._proxy
        proxy._j = job

        if return_proxy:
            return proxy
        return job

    def _get_job_from_proxy(self, job_proxy: BotJobProxy):
        try:
            job = job_proxy._j
        except AttributeError:
            raise JobInitializationError("this job proxy is invalid") from None
        return job

    async def initialize_job(
        self, job: Union[EventJob, IntervalJob], raise_exceptions: bool = True
    ):
        """This initializes a job object.
        registered.

        Args:
            raise_exceptions (bool, optional):
                Whether exceptions should be raised. Defaults to True.

        Returns:
            bool: Whether the initialization attempt was successful.
        """
        if not job._is_initialized:
            try:
                await job._INITIALIZE_EXTERNAL()
                job._is_initialized = True
            except Exception:
                job._is_initialized = False
                if raise_exceptions:
                    raise
        else:
            if raise_exceptions:
                raise JobInitializationError(
                    "this bot job is already initialized"
                ) from None
            else:
                return False

        return job._is_initialized

    async def register_job(
        self,
        job: Union[EventJob, IntervalJob],
        _invoker: Optional[Union[EventJob, IntervalJob]] = None,
    ):
        """Register a job object to this BotJobManager, while initializing it if necessary.

        Args:
            job (BotJob): The job object to be registered.
        """
        if not job._is_initialized:
            await self.initialize_job(job)

        self._add_job(job, _invoker=_invoker)

    async def create_and_register_job(
        self,
        cls: Type[BotJob],
        *args,
        return_proxy: bool = False,
        _invoker: Optional[Union[EventJob, IntervalJob]] = None,
        **kwargs,
    ):
        """Create an instance of a job class, and register it to this `BotTaskManager`.

        Args:
            cls (Type[BotJob]): The job class to be used for instantiation.
            return_proxy (bool, optional): Whether a proxy of the job object
            should be returned. Defaults to False.

        Returns:
            BotJobProxy: A job proxy object.
        """
        j = self.create_job(cls, *args, return_proxy=False, **kwargs)
        await self.register_job(j, _invoker=_invoker)
        if return_proxy:
            return j._proxy

    def schedule_job(
        self,
        cls: Type[BotJob],
        timestamp: Union[datetime.datetime, datetime.timedelta],
        recur_interval: Optional[datetime.timedelta] = None,
        max_recurrences: Optional[int] = None,
        job_args: tuple = (),
        job_kwargs: dict = None,
        data: dict = None,
        _invoker: Optional[Union[EventJob, IntervalJob]] = None,
    ):
        """Schedule a job of a specific type to be instantiated and executed at specific periods of time.

        Args:
            cls (Type[BotJob]): _description_
            timestamp (Union[datetime.datetime, datetime.timedelta]): _description_
            recur_interval (Optional[datetime.timedelta], optional): _description_. Defaults to None.
            max_recurrences (Optional[int], optional): _description_. Defaults to None.
            job_args (tuple, optional): _description_. Defaults to ().
            job_kwargs (dict, optional): _description_. Defaults to None.
            data (dict, optional): _description_. Defaults to None.
            _invoker (Optional[Union[EventJob, IntervalJob]], optional): _description_. Defaults to None.

        Raises:
            RuntimeError: The bot job manager has not initiated bot job scheduling.
            TypeError: Invalid argument types were given.

        Returns:
            _type_: _description_
        """

        NoneType = type(None)

        if self._schedule_dict is None:
            raise RuntimeError(
                "BotJobManager scheduling has not been initiated"
            ) from None

        if isinstance(timestamp, datetime.datetime):
            timestamp = timestamp.astimezone(datetime.timezone.utc)
        elif isinstance(timestamp, datetime.timedelta):
            timestamp = datetime.datetime.now(datetime.timezone.utc) + timestamp
        else:
            raise TypeError(
                "argument 'timestamp' must be a datetime.datetime or datetime.timedelta object"
            ) from None

        if timestamp not in self._schedule_dict:
            self._schedule_dict[timestamp] = []

        if not isinstance(recur_interval, (datetime.timedelta, NoneType)):
            raise TypeError(
                "argument 'recur_interval' must be None or a datetime.timedelta object"
            ) from None

        if not isinstance(max_recurrences, (int, float, NoneType)):
            raise TypeError(
                "argument 'max_recurrences' must be None or an int/float object"
            ) from None

        if not isinstance(job_args, (list, tuple)):
            if job_args is None:
                job_args = ()
            else:
                raise TypeError(
                    f"'job_args' must be of type 'tuple', not {type(job_args)}"
                ) from None

        elif not isinstance(job_kwargs, dict):
            if job_kwargs is None:
                job_kwargs = {}
            else:
                raise TypeError(
                    f"'job_kwargs' must be of type 'dict', not {type(job_kwargs)}"
                ) from None

        elif not isinstance(data, dict):
            if data is None:
                data = {}
            else:
                raise TypeError(
                    f"'data' must be of type 'dict', not {type(data)}"
                ) from None

        if not issubclass(cls, (EventJob, IntervalJob)):
            raise TypeError(
                f"argument 'cls' must be of type 'EventJob' or 'IntervalJob', not '{cls}'"
            ) from None

        new_data = {
            "schedule_id": None,
            "schedule_timestamp": None,
            "timestamp": timestamp + datetime.timedelta(),  # quick copy
            "recur_interval": recur_interval,
            "recurrences": 0,
            "max_recurrences": max_recurrences,
            "class_name": cls.__name__,
            "job_args": tuple(job_args),
            "job_kwargs": job_kwargs,
            "data": data,
        }

        pickle.dumps(new_data)  # validation

        self._schedule_dict[timestamp].append(new_data)
        new_data["schedule_id"] = schedule_id = f"{id(self)}-{int(time.time_ns())}"
        new_data["schedule_timestamp"] = datetime.datetime.now(datetime.timezone.utc)
        return schedule_id

    def __iter__(self):
        return iter(self._job_id_map)

    def _add_job(
        self,
        job: Union[EventJob, IntervalJob],
        _invoker: Optional[Union[EventJob, IntervalJob]] = None,
    ):
        """Add the given job object to this bot job manager, and start it.

        Args:
            job: Union[EventJob, IntervalJob]:
                The job to add.
            start (bool, optional):
                Whether a given interval job object should start immediately after being added.
                Defaults to True.
        Raises:
            TypeError: An invalid object was given as a job.
            ValueError: A job was given that had already ended.
            RuntimeError: A job was given that was already present in the manager.
            JobInitializationError: An uninitialized job was given as input.
        """

        if isinstance(job, BotJob) and job._is_completed:
            raise ValueError(
                "cannot add a job that has ended to a BotJobManager instance"
            ) from None

        elif job._identifier in self._job_id_map:
            raise RuntimeError(
                "the given job is already present in this manager"
            ) from None

        elif not job._is_initialized:
            raise JobInitializationError("the given job was not initialized") from None

        if isinstance(job, EventJob):
            for ce_type in job.CLASS_EVENT_TYPES:
                if ce_type.__name__ not in self._event_job_pool:
                    self._event_job_pool[ce_type.__name__] = set()
                self._event_job_pool[ce_type.__name__].add(job)

        elif isinstance(job, IntervalJob):
            self._interval_job_pool.add(job)
        else:
            raise TypeError(
                f"expected an instance of EventJob or IntervalJob subclasses, not {job.__class__.__name__}"
            ) from None

        self._job_id_map[job._identifier] = job
        job._mgr = BotJobManagerProxy(self, job)

        job._registered_at = datetime.datetime.now(datetime.timezone.utc)
        if not job._task_loop.is_running():
            job._task_loop.start()

    def _remove_job(self, job: Union[EventJob, IntervalJob]):
        """Remove the given job object from this bot job manager.

        Args:
            *jobs: Union[EventJob, IntervalJob]:
                The job to be removed, if present.
        Raises:
            TypeError: An invalid object was given as a job.
        """
        if not isinstance(job, (EventJob, IntervalJob)):
            raise TypeError(
                f"expected an instance of class EventJob or IntervalJob, not {job.__class__.__name__}"
            ) from None

        if isinstance(job, IntervalJob) and job in self._interval_job_pool:
            self._interval_job_pool.remove(job)

        elif isinstance(job, EventJob):
            for ce_type in job.CLASS_EVENT_TYPES:
                if (
                    ce_type.__name__ in self._event_job_pool
                    and job in self._event_job_pool[ce_type.__name__]
                ):
                    self._event_job_pool[ce_type.__name__].remove(job)
                if not self._event_job_pool[ce_type.__name__]:
                    del self._event_job_pool[ce_type.__name__]

        if job in self._job_id_map:
            del self._job_id_map[job._identifier]

        if job._mgr:
            job._mgr = None

    def _remove_jobs(self, *jobs: Union[EventJob, IntervalJob]):
        """Remove the given job objects from this bot job manager.

        Args:
            *jobs: Union[EventJob, IntervalJob]:
                The jobs to be removed, if present.
            cancel (bool, optional):
                Whether the given interval job objects should be cancelled immediately after being removed.
                Defaults to True.
        Raises:
            TypeError: An invalid object was given as a job.
        """
        for job in jobs:
            self._remove_job(job)

    def has_job(self, job: Union[EventJob, IntervalJob]):
        """Whether a job is contained in this bot job manager.

        Args:
            job (Union[EventJob, IntervalJob]): The job object to look for.

        Returns:
            bool: True/False
        """
        return job._identifier in self._job_id_map

    async def find_jobs(
        self,
        cls: Optional[Type[BotJob]] = None,
        identifier: Optional[str] = None,
        created_at: Optional[datetime.datetime] = None,
        created_before: Optional[datetime.datetime] = None,
        created_after: Optional[datetime.datetime] = None,
        is_running: Optional[bool] = None,
        is_idling: Optional[bool] = None,
        is_sleeping: Optional[bool] = None,
        is_awaiting: Optional[bool] = None,
        is_being_stopped: Optional[bool] = None,
        is_being_killed: Optional[bool] = None,
        is_being_completed: Optional[bool] = None,
    ):
        if identifier is not None:
            if isinstance(identifier, str):
                if identifier in self._job_id_map:
                    return self._job_id_map[identifier]._proxy
                raise JobLookupError(
                    "cound not find a job with the specified identifier"
                )
            raise TypeError(
                f"'identifier' must be of type 'str', not {type(identifier)}"
            ) from None

        elif created_at is not None:
            if isinstance(created_at, datetime.datetime):
                for job in self._job_id_map.values():
                    if job._created_at == created_at:
                        return job._proxy
                raise JobLookupError(
                    "cound not find a job with the specified creation time"
                )

            raise TypeError(
                f"'create_at' must be of type 'datetime.datetime', not {type(created_at)}"
            ) from None

        else:

            filter_lambdas = []

            if created_before is not None:
                filter_lambdas.append(lambda job: job.created_at < created_before)

            if created_after is not None:
                filter_lambdas.append(lambda job: job.created_at > created_after)

            if is_running is not None:
                filter_lambdas.append(lambda job: job.is_running())

            if is_idling is not None:
                filter_lambdas.append(lambda job: job.is_idling())

            if is_sleeping is not None:
                filter_lambdas.append(lambda job: job.is_sleeping())

            if is_awaiting is not None:
                filter_lambdas.append(lambda job: job.is_awaiting())

            if is_being_stopped is not None:
                filter_lambdas.append(lambda job: job.is_being_stopped())

            if is_being_killed is not None:
                filter_lambdas.append(lambda job: job.is_being_killed())

            if is_being_completed is not None:
                filter_lambdas.append(lambda job: job.is_being_completed())

            jobs = []

            for job in self._job_id_map.values():
                if all(filter_func(job) for filter_func in filter_lambdas):
                    jobs.append(job._proxy)

            if not jobs:
                raise JobLookupError(
                    "could not find any job objects matching the speficied arguments"
                )

            return jobs

    def restart_job(
        self,
        job: Union[IntervalJob, EventJob],
        _invoker: Optional[Union[EventJob, IntervalJob]] = None,
    ):
        return job._RESTART_LOOP_EXTERNAL()

    def stop_job(
        self,
        job: Union[EventJob, IntervalJob],
        force=False,
        _invoker: Optional[Union[EventJob, IntervalJob]] = None,
    ):
        return job._STOP_LOOP_EXTERNAL(force=force)

    def kill_job(
        self,
        job: Union[EventJob, IntervalJob],
        _invoker: Optional[Union[EventJob, IntervalJob]] = None,
    ):
        """Stops this job's current execution unconditionally and remove it from its `BotJobManager`.
        In order to check if a job was ended by killing it, on can call `.was_killed()`."""
        return job._KILL_EXTERNAL(awaken=True)

    def __contains__(self, job: Union[EventJob, IntervalJob]):
        return job._identifier in self._job_id_map

    async def dispatch_event(self, event: events.BaseEvent):
        """Dispatch a `BaseEvent` subclass to all event job objects
        in this bot job manager.

        Args:
            event (events.BaseEvent): The subclass to be dispatched.
        """
        event_class_name = type(event).__name__

        if event_class_name in self._event_waiting_queues:
            target_event_waiting_queue = self._event_waiting_queues[event_class_name]
            deletion_queue_indices = []
            deletion_idx = 0
            if len(target_event_waiting_queue) > 256:

                def add_to_waiting_list(waiting_list):
                    nonlocal deletion_idx
                    if (
                        isinstance(event, waiting_list[0])
                        and waiting_list[1](event)
                        and not waiting_list[2].cancelled()
                    ):
                        if not waiting_list[2].cancelled():
                            waiting_list[2].set_result(event.copy())
                        deletion_queue_indices.append(deletion_idx)
                        deletion_idx += 1

                await self._loop.run_in_executor(
                    None, map, add_to_waiting_list, tuple(target_event_waiting_queue)
                )
            else:
                for i, waiting_list in enumerate(target_event_waiting_queue):
                    if isinstance(event, waiting_list[0]) and waiting_list[1](event):
                        if not waiting_list[2].cancelled():
                            waiting_list[2].set_result(event.copy())
                        deletion_queue_indices.append(i)

            for idx in reversed(deletion_queue_indices):
                del target_event_waiting_queue[idx]

        if event_class_name in self._event_job_pool:
            target_jobs = self._event_job_pool[event_class_name]

            if len(target_jobs) > 256:

                def add_to_jobs(client_event_job):
                    if client_event_job.check_event(event):
                        client_event_job._add_event(event.copy())

                await self._loop.run_in_executor(
                    None, map, add_to_jobs, tuple(target_jobs)
                )
            else:
                for client_event_job in target_jobs:
                    if client_event_job.check_event(event):
                        client_event_job._add_event(event.copy())

    def wait_for_event(
        self,
        *CLASS_EVENT_TYPES: Type[BotJob],
        check: Optional[Callable[[events.BaseEvent], bool]] = None,
        timeout: Optional[float] = None,
    ):
        """Wait for specific type of event to be dispatched, and return that.

        Args:
            *CLASS_EVENT_TYPES (events.BaseEvent):
                The event type/types to wait for. If any of its/their
                instances is dispatched, that instance will be returned.
            check (Optional[Callable[[events.BaseEvent], bool]], optional):
                A callable obejct used to validate if a valid event that was recieved meets specific conditions.
                Defaults to None.

        Returns:
            BaseEvent: A valid event object
        """

        check = (lambda x: True) if check is None else check
        future = self._loop.create_future()
        wait_list = [CLASS_EVENT_TYPES, check, future]

        for event_type in CLASS_EVENT_TYPES:
            if (
                not issubclass(event_type, events.BaseEvent)
                and event_type is not events.BaseEvent
            ):
                for event_type in CLASS_EVENT_TYPES:  # undo everything
                    d = self._event_waiting_queues[event_type.__name__]
                    d.remove(wait_list)
                    if not d:
                        del self._event_waiting_queues[event_type.__name__]

                raise TypeError(
                    "argument 'CLASS_EVENT_TYPES' must contain only subclasses of 'BaseEvent'"
                ) from None

            elif event_type.__name__ not in self._event_waiting_queues:
                self._event_waiting_queues[event_type.__name__] = []

            self._event_waiting_queues[event_type.__name__].append(wait_list)

        return asyncio.wait_for(future, timeout)

    async def kill_all(self):
        """Kill all job objects that are in this bot job manager."""
        await asyncio.get_event_loop().run_in_executor(
            None,
            map,
            lambda x: x._KILL_EXTERNAL(awaken=True),
            itertools.chain(
                tuple(t for t in (ce_set for ce_set in self._event_job_pool.values())),
                tuple(self._interval_job_pool),
            ),
        )

    async def kill_all_interval_jobs(self):
        """Kill all interval job objects that are in this bot job manager."""
        await asyncio.get_event_loop().run_in_executor(
            None,
            map,
            lambda x: x._KILL_EXTERNAL(awaken=True),
            tuple(self._interval_job_pool),
        )

    async def kill_all_client_event_jobs(self):
        """Kill all event job objects that are in this bot job manager."""
        await asyncio.get_event_loop().run_in_executor(
            None,
            map,
            lambda x: x._KILL_EXTERNAL(awaken=True),
            tuple(j for j in (cej_set for cej_set in self._event_job_pool.values())),
        )

    def quit(self, kill_all_jobs=True):
        self._running = False
        self.job_scheduling_loop.stop()
        if kill_all_jobs:
            self.kill_all()


class BotJobManagerProxy:
    def __init__(self, mgr: BotJobManager, job):
        self._mgr = mgr
        self._job = job

    def create_job(self, cls: Type[BotJob], *args, **kwargs):
        """Create an instance of a job class.

        Args:
            cls (Type[BotJob]): The job class to
            instantiate a job object from.

        Returns:
            BotJobProxy: A job proxy object.
        """
        return self._mgr.create_job(cls, *args, return_proxy=True, **kwargs)

    async def initialize_job(
        self, job_proxy: BotJobProxy, raise_exceptions: bool = True
    ):
        """This initializes a job object from its proxy.
        registered.

        Args:
            raise_exceptions (bool, optional):
                Whether exceptions should be raised. Defaults to True.

        Returns:
            bool: Whether the initialization attempt was successful.
        """
        job = self._mgr._get_job_from_proxy(job_proxy)
        return await self._mgr.initialize_job(job, raise_exceptions=raise_exceptions)

    async def register_job(self, job_proxy: BotJobProxy):
        job = self._mgr._get_job_from_proxy(job_proxy)
        return await self._mgr.register_job(job, _invoker=self._job)

    async def create_and_register_job(self, cls: Type[BotJob], *args, **kwargs):
        """Create an instance of a job class, and register it to this `BotTaskManager`.

        Args:
            cls (Type[BotJob]): The job class to be used for instantiation.
            return_proxy (bool, optional): Whether a proxy of the job object
            should be returned. Defaults to False.

        Returns:
            BotJobProxy: A job proxy object.
        """

        return await self._mgr.create_and_register_job(
            cls,
            *args,
            return_proxy=True,
            _invoker=self._job,
            **kwargs,
        )

    def restart_job(self, job_proxy: BotJobProxy):
        job = self._mgr._get_job_from_proxy(job_proxy)
        return self._mgr.restart_job(job, _invoker=self._job)

    def stop_job(self, job_proxy: BotJobProxy, force=False):
        job = self._mgr._get_job_from_proxy(job_proxy)
        return self._mgr.stop_job(job, force=force, _invoker=self._job)

    def kill_job(self, job_proxy: BotJobProxy):
        """Stops this job's current execution unconditionally and remove it from its `BotJobManager`.
        In order to check if a job was ended by killing it, on can call `.was_killed()`."""
        job = self._mgr._get_job_from_proxy(job_proxy)
        return self._mgr.kill_job(job, _invoker=self._job)

    def _eject(self):
        self._mgr._remove_job(self._job)

    def schedule_job(
        self,
        cls: Type[BotJob],
        timestamp: Union[datetime.datetime, datetime.timedelta],
        recur_interval: Optional[datetime.timedelta] = None,
        max_recurrences: Optional[int] = None,
        job_args: tuple = (),
        job_kwargs: dict = None,
        data: dict = None,
    ):
        return self._mgr.schedule_job(
            cls=cls,
            timestamp=timestamp,
            recur_interval=recur_interval,
            max_recurrences=max_recurrences,
            job_args=job_args,
            job_kwargs=job_kwargs,
            data=data,
            _invoker=self._job,
        )

    def wait_for_event(
        self,
        *CLASS_EVENT_TYPES: type,
        check: Optional[Callable[[events.BaseEvent], bool]] = None,
        timeout: Optional[float] = None,
    ):
        return self._mgr.wait_for_event(
            *CLASS_EVENT_TYPES,
            check=check,
            timeout=timeout,
        )

    async def dispatch_custom_event(self, event: events.CustomEvent):
        """Dispatch a `CustomEvent` subclass to all event job objects
        in this bot job manager that are listining for it.

        Args:
            event (events.BaseEvent): The subclass to be dispatched.
        """

        if not isinstance(event, events.CustomEvent):
            raise TypeError(
                "argument 'event' must have `CustomEvent` as a subclass"
            ) from None

        event._dispatcher = self._job._proxy
        return await self._mgr.dispatch_event(event)

    def __contains__(self, job_proxy: BotJobProxy):
        job = self._mgr._get_job_from_proxy(job_proxy)
        return self._mgr.__contains__(job)

    has_job = __contains__
