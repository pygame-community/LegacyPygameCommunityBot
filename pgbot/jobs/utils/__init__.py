"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This module implements utility job classes. 
"""

from __future__ import annotations
import asyncio
from typing import Any, Callable, Coroutine, Iterable, Optional, Sequence, Type, Union
from pgbot.jobs import IntervalJobBase, JobProxy, EventJobBase, JOB_PERMISSION_LEVELS
from pgbot.utils import embed_utils
from pgbot import common, events, serializers
from pgbot import serializers as serials
from . import messaging

class ClientEventJobBase(EventJobBase):
    """A subclass of `EventJobBase` for jobs that run in reaction to specific client events
    (Discord API events) passed to them by their `JobManager` object.
    
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
    automatically. For more control, use `IntervalJobBase` directly.
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
            *jobs Union[ClientEventJob, IntervalJobBase]:
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

class MethodCallJob(IntervalJobBase, permission_level=JOB_PERMISSION_LEVELS.LOWEST):
    """A job class for calling a method on an object."""

    OUTPUT_FIELDS = frozenset(("output",))

    DEFAULT_COUNT = 1
    DEFAULT_RECONNECT = False

    def __init__(
        self,
        instance: object,
        method_name: str,
        is_async: bool = False,
        instance_args: Optional[tuple] = (),
        instance_kwargs: Optional[dict] = None,
    ):

        super().__init__()

        self.data.instance = instance
        self.data.method_name = method_name + ""
        self.data.is_async = is_async

        if not isinstance(instance, serials.BaseSerializer):
            getattr(instance, method_name)

        self.data.instance_args = list(instance_args)
        self.data.instance_kwargs = instance_kwargs

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

    async def on_stop(self, reason, by_force):
        if self.failed():
            self.KILL()
        else:
            self.COMPLETE()
