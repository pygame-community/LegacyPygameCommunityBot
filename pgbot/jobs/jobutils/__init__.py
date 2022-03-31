"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This module implements utility job classes. 
"""

from ast import arg
import asyncio
from collections import deque
from typing import Any, Callable, Coroutine, Literal, Optional, Union
from pgbot.jobs import IntervalJobBase, JobProxy, EventJobBase, JobPermissionLevels
from pgbot import events
from pgbot import serializers as serials
from pgbot.jobs.groupings import JobGroup, NameRecord, OutputNameRecord
from pgbot.jobs.jobs import publicjobmethod
from . import messaging


class ClientEventJobBase(EventJobBase):
    """A subclass of `EventJobBase` for jobs that run in reaction to specific client events
    (Discord API events) passed to them by their `JobManager` object by default.

    Excluding the value of the `EVENT_TYPES` class variable, this job object
    is functionally equivalent to `EventJobBase`.

    Attributes:
        EVENT_TYPES:
            A tuple denoting the set of `ClientEvent` classes whose instances
            should be recieved after their corresponding event is registered
            by the `JobManager` of an instance of this class. By default,
            all instances of `ClientEvent` will be propagated.
    """

    EVENT_TYPES: tuple = (events.ClientEvent,)


class SingleRunJob(IntervalJobBase):
    """A subclass of `IntervalJobBase` whose subclasses's
    job objects will only run once and then complete themselves.
    If they fail
    automatically. For more control, use `IntervalJobBase` directly.
    """

    DEFAULT_COUNT = 1

    async def on_stop(self):
        self.COMPLETE()


class RegisterDelayedJobGroup(JobGroup):
    """A group of jobs that add a given set of job proxies
    to their `JobManager` after a given period
    of time in seconds.

    Output Fields:
        'success_failure_tuple': A tuple containing two tuples,
        with the successfully registered job proxies in the
        first one and the failed proxies in the second.
    """

    class _RegisterDelayedJob(IntervalJobBase):
        class OutputFields(OutputNameRecord):
            success_failure_tuple: str
            """A tuple containing two tuples,
            with the successfully registered job proxies in the
            first one and the failed proxies in the second.
            """

        class OutputQueues(OutputNameRecord):
            successes: str

        class PublicMethods(NameRecord):
            get_successes_async: Optional[Callable[[], Coroutine]]
            """get successes lol"""

        DEFAULT_COUNT = 1

        def __init__(self, delay: float, *job_proxies: JobProxy, **kwargs):
            """Create a new instance.

            Args:
                delay (float): The delay for the input jobs in seconds.
                *job_proxies Union[ClientEventJob, IntervalJobBase]: The jobs to be delayed.
            """
            super().__init__(**kwargs)
            self.data.delay = delay
            self.data.jobs = deque(job_proxies)
            self.data.success_jobs = []
            self.data.success_futures = []
            self.data.failure_jobs = []

        async def on_run(self):
            await asyncio.sleep(self.data.delay)
            while self.data.jobs:
                job_proxy = self.data.jobs.popleft()
                try:
                    await self.manager.register_job(job_proxy)
                except Exception:
                    self.data.failure_jobs.append(job_proxy)
                else:
                    self.data.success_jobs.append(job_proxy)
                    self.push_output_queue("successes", job_proxy)

            success_jobs_tuple = tuple(self.data.success_jobs)

            self.set_output_field(
                "success_failure_tuple",
                (success_jobs_tuple, tuple(self.data.failure_jobs)),
            )

            for fut in self.data.success_futures:
                if not fut.cancelled():
                    fut.set_result(success_jobs_tuple)

        @publicjobmethod(is_async=True)
        def get_successes_async(self):
            loop = asyncio.get_event_loop()
            fut = loop.create_future()
            self.data.success_futures.append(fut)
            return asyncio.wait_for(fut, None)

        async def on_stop(self):
            self.COMPLETE()

    class MediumPermLevel(
        _RegisterDelayedJob,
        scheduling_identifier="8d2330f4-7a2a-4fd1-8144-62ca57d4799c",
        permission_level=JobPermissionLevels.MEDIUM,
    ):
        pass

    class HighPermLevel(
        _RegisterDelayedJob,
        scheduling_identifier="129f8662-f72d-4ee3-81ea-f302a15b2cca",
        permission_level=JobPermissionLevels.HIGH,
    ):
        pass

    class HighestPermLevel(
        _RegisterDelayedJob,
        scheduling_identifier="6b7e5a87-1727-4f4b-ae89-418f4e90f3d4",
        permission_level=JobPermissionLevels.HIGHEST,
    ):
        pass


class MethodCallJob(
    IntervalJobBase,
    scheduling_identifier="7d2fee26-d8b9-4e93-b761-4d152d355bae",
    permission_level=JobPermissionLevels.LOWEST,
):
    """A job class for calling the method of a specified name on an object given as
    argument.

    Permission Level:
        JobPermissionLevels.LOWEST

    Output Fields:
        'output': The returned output of the method call.
    """

    class OutputFields(OutputNameRecord):
        output: str
        "The returned output of the method call."

    DEFAULT_COUNT = 1
    DEFAULT_RECONNECT = False

    def __init__(
        self,
        instance: object,
        method_name: str,
        is_async: bool = False,
        instance_args: tuple[Any, ...] = (),
        instance_kwargs: Optional[dict] = None,
    ):

        super().__init__()

        self.data.instance = instance
        self.data.method_name = method_name + ""
        self.data.is_async = is_async

        if not isinstance(instance, serials.BaseSerializer):
            getattr(instance, method_name)

        self.data.instance_args = list(instance_args)
        self.data.instance_kwargs = instance_kwargs or {}

    async def on_init(self):
        if isinstance(self.data.instance, serials.BaseSerializer):
            self.data.instance = await self.data.instance.deserialized_async()
            getattr(self.data.instance, self.data.method_name)

        for i in range(len(self.data.instance_args)):
            arg = self.data.instance_args[i]
            if isinstance(arg, serials.BaseSerializer):
                self.data.instance_args[i] = await arg.deserialized_async()

        for key in self.data.instance_kwargs:
            kwarg = self.data.instance_kwargs[key]
            if isinstance(kwarg, serials.BaseSerializer):
                self.data.instance_kwargs[key] = await kwarg.deserialized_async()

    async def on_run(self):
        output = getattr(self.data.instance, self.data.method_name)(
            *self.data.instance_args, **self.data.instance_kwargs
        )
        if self.data.is_async:
            output = await output

        self.set_output_field("output", output)

    async def on_stop(self):
        if self.run_failed():
            self.KILL()
        else:
            self.COMPLETE()
