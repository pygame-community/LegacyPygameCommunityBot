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
from typing import Any, Callable, Coroutine, Iterable, Optional, Sequence, Union

import discord
from discord.ext import tasks

from pgbot.utils import utils
from pgbot import db
from pgbot import common
from pgbot.common import bot as client

from . import base_jobs, events, serializers
import base_jobs

BotJob = base_jobs.BotJob
ClientEventJob = base_jobs.ClientEventJob
IntervalJob = base_jobs.IntervalJob
JobError = base_jobs.JobError
JobInitializationError = base_jobs.JobInitializationError


class BotJobManagerWrapper:
    def __init__(self, mgr: BotJobManager, job):
        self._mgr = mgr
        self._job = job

    def add_job(self, job: Union[ClientEventJob, IntervalJob]):
        return self._mgr.add_job(job, _invoker=self._job)

    def schedule_job(
        self,
        job_type: type,
        timestamp: Union[datetime.datetime, datetime.timedelta],
        recur_interval: Optional[datetime.timedelta] = None,
        max_recurrences: Optional[int] = None,
        job_args: tuple = (),
        job_kwargs: dict = None,
        data: dict = None,
    ):
        return self._mgr.schedule_job(
            job_type=job_type,
            timestamp=timestamp,
            recur_interval=recur_interval,
            max_recurrences=max_recurrences,
            job_args=job_args,
            job_kwargs=job_kwargs,
            data=data,
            _invoker=self._job,
        )
    
    def wait_for_client_event(
        self,
        *event_types: type,
        check: Optional[Callable[[events.ClientEvent], bool]] = None,
        timeout: Optional[float] = None,
    ):
        return self._mgr.wait_for_client_event(
            *event_types,
            check=check,
            timeout=timeout,
        )

    def has_job(self, job: Union[ClientEventJob, IntervalJob]):
        return self._mgr.has_job(job)

    def __contains__(self, job):
        return self._mgr.__contains__(job)



class BotJobManager:
    """The job manager for all interval jobs and client event jobs.
    It acts as a container for interval and client event job objects, whilst also being responsible dispatching
    client events to client event job objects. Each of the jobs that a bot job manager
    contains can use it to register new job objects that they instantiate at runtime.
    """

    def __init__(self, *jobs: Union[ClientEventJob, IntervalJob], loop=None):
        """Create a new bot job manager instance.

        Args:
            *jobs: Union[ClientEventJob, IntervalJob]:
                The job objects to add during initiation.
        """
        if loop is None:
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                self._loop = asyncio.get_event_loop()

        self._loop = loop
        self._client_event_job_pool = {}
        self._interval_job_pool = set()
        self._job_id_map = {}
        self._job_class_data = {}
        self._event_waiting_queues = {}
        self._schedule_dict = {}
        self._schedule_dict_fails = {}
        self._running = True
        self._schedule_init = False

        for job in jobs:
            self.add_job(job)

    def set_event_loop(self, loop):
        """[summary]

        Args:
            loop (AbstractEventLoop): The loop this job is meant to use.

        Raises:
            TypeError: [description]
        """
        if not isinstance(loop, asyncio.AbstractEventLoop):
            raise TypeError("Invalid event loop")
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

                    if d["class_name"] in base_jobs.JOB_CLASS_MAP:
                        try:
                            job = base_jobs.JOB_CLASS_MAP[d["class_name"]](
                                *d["job_args"], **d["job_kwargs"]
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
                            if not isinstance(job, (ClientEventJob, IntervalJob)):
                                print(
                                    f"Invalid job type found in job class scheduling data: '{type(job).__name__}'"
                                )
                            self.add_job(await job.as_initialized())
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

    def make_job(self, cls: Union[IntervalJob, ClientEventJob], *args, **kwargs):

        job = cls(*args, **kwargs)

        proxy = job._proxy
        proxy.__j = job

        return proxy


    async def initialize_job(self, job_proxy, raise_exceptions: bool = True):
        """This initializes a job object.
        registered.

        Args:
            raise_exceptions (bool, optional):
                Whether exceptions should be raised. Defaults to True.

        Returns:
            bool: Whether the initialization attempt was successful.
        """

        try:
            job = job_proxy.__j
        except AttributeError:
            raise JobInitializationError(
                    "this job proxy cannot be used for initialization"
            ) from None
        
        if not job._is_initialized:
            try:
                await job.on_init()
                job._is_initialized = True
            except Exception:
                job._is_initialized = False
                if raise_exceptions:
                    raise
        else:
            if raise_exceptions:
                raise JobInitializationError(
                    "this bot job proxy's job is already initialized"
                )
            else:
                return False

        return job._is_initialized

    async def register_job(self, job_proxy, _invoker=None):
        try:
            job = job_proxy.__j
        except AttributeError:
            raise JobInitializationError(
                    "this job proxy cannot be used for initialization"
                ) from None
        if not job._is_initialized:
            await self.initialize_job(job)
        
        self.add_job(job, _invoker=_invoker)

    def restart_job_loop(self, job, _invoker=None):
        job._task_loop.restart()

    def stop_job_loop(self, job, force=False, _invoker=None):
        if force:
            job._task_loop.stop()
        else:
            job._task_loop.cancel()
        job._is_idle = True

    def kill_job(self, job, _invoker=None):
        """Stops this job's current execution unconditionally like `.cancel_run()`, before closing it and removing it from its `BotJobManager`.
        In order to check if a job was closed by killing it, on can call `.was_killed()`."""
        job._task_loop.cancel()
        job._idle = False
        job._has_ended = True
        job._was_killed = True

        for fut in job._completion_futures:
            if not fut.cancelled():
                fut.cancel(msg=f"Job object '{job}' was killed.")

        for fut in job._output_futures:
            if not fut.cancelled():
                fut.cancel(
                    msg=f"Job object '{job}' was killed. job output might be corrupted."
                )

        job._completion_futures.clear()
        job._completion_futures = []

        self._remove_job(job)

    def schedule_job(
        self,
        job_type: type,
        timestamp: Union[datetime.datetime, datetime.timedelta],
        recur_interval: Optional[datetime.timedelta] = None,
        max_recurrences: Optional[int] = None,
        job_args: tuple = (),
        job_kwargs: dict = None,
        data: dict = None,
        _invoker: Optional[BotJob] = None,
    ):
        """[summary]

        Args:
            job_type (type): [description]
            timestamp (Union[datetime.datetime, datetime.timedelta]): [description]
            recur_interval (Optional[datetime.timedelta], optional): [description]. Defaults to None.
            max_recurrences (Optional[int], optional): [description]. Defaults to None.
            job_args (tuple, optional): [description]. Defaults to an empty tuple.
            job_kwargs (dict, optional): [description]. Defaults to None.
            data (dict, optional): [description]. Defaults to None.

        Raises:
            RuntimeError: The bot job manager has not initiated bot job scheduling.
            TypeError: Invalid argument types were given.
        """

        NoneType = type(None)

        if self._schedule_dict is None:
            raise RuntimeError("BotJobManager scheduling has not been initiated")

        if isinstance(timestamp, datetime.datetime):
            timestamp = timestamp.astimezone(datetime.timezone.utc)
        elif isinstance(timestamp, datetime.timedelta):
            timestamp = datetime.datetime.now(datetime.timezone.utc) + timestamp
        else:
            raise TypeError(
                "argument 'timestamp' must be a datetime.datetime or datetime.timedelta object"
            )

        if timestamp not in self._schedule_dict:
            self._schedule_dict[timestamp] = []

        if not isinstance(recur_interval, (datetime.timedelta, NoneType)):
            raise TypeError(
                "argument 'recur_interval' must be None or a datetime.timedelta object"
            )

        if not isinstance(max_recurrences, (int, float, NoneType)):
            raise TypeError(
                "argument 'max_recurrences' must be None or an int/float object"
            )

        if not isinstance(job_args, (list, tuple)):
            if job_args is None:
                job_args = ()
            else:
                raise TypeError(
                    f"'job_args' must be of type 'tuple', not {type(job_args)}"
                )

        elif not isinstance(job_kwargs, dict):
            if job_kwargs is None:
                job_kwargs = {}
            else:
                raise TypeError(
                    f"'job_kwargs' must be of type 'dict', not {type(job_kwargs)}"
                )

        elif not isinstance(data, dict):
            if data is None:
                data = {}
            else:
                raise TypeError(f"'data' must be of type 'dict', not {type(data)}")

        if not issubclass(job_type, (ClientEventJob, IntervalJob)):
            raise TypeError(
                f"argument 'job_type' must be of type 'ClientEventJob' or 'IntervalJob', not '{job_type}'"
            )

        new_data = {
            "timestamp": timestamp + datetime.timedelta(),  # quick copy
            "recur_interval": recur_interval,
            "recurrences": 0,
            "max_recurrences": max_recurrences,
            "class_name": job_type.__name__,
            "job_args": tuple(job_args),
            "job_kwargs": job_kwargs,
            "data": data,
        }

        pickle.dumps(new_data)  # validation

        self._schedule_dict[timestamp].append(new_data)

    def __iter__(self):
        return iter(self._job_id_map)

    def add_job(
        self,
        job: Union[ClientEventJob, IntervalJob],
        _invoker: Optional[BotJob] = None,
    ):
        """Add the given job object to this bot job manager.

        Args:
            job: Union[ClientEventJob, IntervalJob]:
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

        if isinstance(job, base_jobs.BotJob) and job._has_ended:
            raise ValueError(
                "cannot add a job that has ended to a BotJobManager instance"
            )

        elif job._identifier in self._job_id_map:
            raise RuntimeError("the given job is already present in this manager")

        elif not job._is_initialized:
            raise JobInitializationError("the given job was not initialized")

        if isinstance(job, ClientEventJob):
            for ce_type in job.EVENT_TYPES:
                if ce_type.__name__ not in self._client_event_job_pool:
                    self._client_event_job_pool[ce_type.__name__] = set()
                self._client_event_job_pool[ce_type.__name__].add(job)

        elif isinstance(job, IntervalJob):
            self._interval_job_pool.add(job)
        else:
            raise TypeError(
                f"expected an instance of class ClientEventJob or IntervalJob, not {job.__class__.__name__}"
            )

        self._job_id_map[job._identifier] = job
        job._mgr = BotJobManagerWrapper(self, job)

        job._registered_at = datetime.datetime.now(datetime.timezone.utc)
        if not job._task_loop.is_running():
            job._task_loop.start()

    def _remove_job(self, job: Union[ClientEventJob, IntervalJob]):
        """Remove the given job object from this bot job manager.

        Args:
            *jobs: Union[ClientEventJob, IntervalJob]:
                The job to be removed, if present.
        Raises:
            TypeError: An invalid object was given as a job.
        """
        if not isinstance(job, (ClientEventJob, IntervalJob)):
            raise TypeError(
                f"expected an instance of class ClientEventJob or IntervalJob, not {job.__class__.__name__}"
            )

        if isinstance(job, IntervalJob) and job in self._interval_job_pool:
            self._interval_job_pool.remove(job)

        elif isinstance(job, ClientEventJob):
            for ce_type in job.EVENT_TYPES:
                if (
                    ce_type.__name__ in self._client_event_job_pool
                    and job in self._client_event_job_pool[ce_type.__name__]
                ):
                    self._client_event_job_pool[ce_type.__name__].remove(job)
                if not self._client_event_job_pool[ce_type.__name__]:
                    del self._client_event_job_pool[ce_type.__name__]

        if job in self._job_id_map:
            del self._job_id_map[job._identifier]

        if job._mgr:
            job._mgr = None

    def _remove_jobs(self, *jobs: Union[ClientEventJob, IntervalJob]):
        """Remove the given job objects from this bot job manager.

        Args:
            *jobs: Union[ClientEventJob, IntervalJob]:
                The jobs to be removed, if present.
            cancel (bool, optional):
                Whether the given interval job objects should be cancelled immediately after being removed.
                Defaults to True.
        Raises:
            TypeError: An invalid object was given as a job.
        """
        for job in jobs:
            self._remove_job(job)

    def has_job(self, job: Union[ClientEventJob, IntervalJob]):
        """Whether a job is contained in this bot job manager.

        Args:
            job (Union[ClientEventJob, IntervalJob]): The job object to look for.

        Returns:
            bool: True/False
        """
        return job._identifier in self._job_id_map

    async def find_job(
        cls,
        id: Optional[str] = None,
        created_before: Optional[datetime.datetime] = None,
        created_on: Optional[datetime.datetime] = None,
        created_after: Optional[datetime.datetime] = None,
    ):
        raise NotImplementedError

    def __contains__(self, job: Union[ClientEventJob, IntervalJob]):
        return job._identifier in self._job_id_map

    async def dispatch_client_event(self, event: events.ClientEvent):
        """Dispatch a `ClientEvent` subclass to all client event job objects
        in this bot job manager.

        Args:
            event (events.ClientEvent): The subclass to be dispatched.
        """
        event_class_name = type(event).__name__

        if event_class_name in self._event_waiting_queues:
            target_event_waiting_queue = self._event_waiting_queues[event_class_name]
            deletion_queue = []
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
                        deletion_queue.append(deletion_idx)
                        deletion_idx += 1

                await self._loop.run_in_executor(
                    None, map, add_to_waiting_list, tuple(target_event_waiting_queue)
                )
            else:
                for i, waiting_list in enumerate(target_event_waiting_queue):
                    if isinstance(event, waiting_list[0]) and waiting_list[1](event):
                        if not waiting_list[2].cancelled():
                            waiting_list[2].set_result(event.copy())
                        deletion_queue.append(i)

            for idx in reversed(deletion_queue):
                del target_event_waiting_queue[idx]

        if event_class_name in self._client_event_job_pool:
            target_jobs = self._client_event_job_pool[event_class_name]

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

    def wait_for_client_event(
        self,
        *event_types: type,
        check: Optional[Callable[[events.ClientEvent], bool]] = None,
        timeout: Optional[float] = None,
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

        check = (lambda x: True) if check is None else check
        future = self._loop.create_future()
        wait_list = [event_types, check, future]

        for event_type in event_types:
            if (
                not issubclass(event_type, events.ClientEvent)
                and event_type is not events.ClientEvent
            ):
                for event_type in event_types:
                    d = self._event_waiting_queues[event_type.__name__]
                    d.remove(wait_list)
                    if not d:
                        del self._event_waiting_queues[event_type.__name__]

                raise TypeError(
                    "Argument 'event_types' must contain only subclasses of 'ClientEvent'"
                )

            elif event_type.__name__ not in self._event_waiting_queues:
                self._event_waiting_queues[event_type.__name__] = []

            self._event_waiting_queues[event_type.__name__].append(wait_list)

        return asyncio.wait_for(future, timeout)

    async def kill_all(self):
        """Kill all job objects that are in this bot job manager."""
        await asyncio.get_event_loop().run_in_executor(
            None,
            map,
            lambda x: x.kill(),
            itertools.chain(
                tuple(
                    t
                    for t in (ce_set for ce_set in self._client_event_job_pool.values())
                ),
                tuple(self._interval_job_pool),
            ),
        )

    async def kill_all_interval_jobs(self):
        """Kill all interval job objects that are in this bot job manager."""
        await asyncio.get_event_loop().run_in_executor(
            None,
            map,
            lambda x: x.kill(),
            tuple(self._interval_job_pool),
        )

    async def kill_all_client_event_jobs(self):
        """Kill all client event job objects that are in this bot job manager."""
        await asyncio.get_event_loop().run_in_executor(
            None,
            map,
            lambda x: x.kill(),
            tuple(
                t for t in (ce_set for ce_set in self._client_event_job_pool.values())
            ),
        )

    def quit(self, kill_all_jobs=True):
        self._running = False
        self.job_scheduling_loop.stop()
        if kill_all_jobs:
            self.kill_all()
