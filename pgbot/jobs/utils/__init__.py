"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This module implements utility job classes. 
"""

from __future__ import annotations
from typing import Any, Callable, Coroutine, Iterable, Optional, Sequence, Type, Union
from pgbot.jobs.core import IntervalJob, PERMISSION_LEVELS
from pgbot.utils import embed_utils
from pgbot import common, serializers
from pgbot import serializers as serials
from . import messaging


class MethodCall(IntervalJob, permission_level=PERMISSION_LEVELS.LOWEST):
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
        kill_if_failed: bool = True,
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
            self.data.instance = await self.data.instance.reconstructed_async(
                always_fetch=False
            )
            getattr(self.data.instance, self.data.method_name)

        for i, arg in enumerate(tuple(self.data.instance_args)):
            if isinstance(arg, serials.BaseSerializer):
                self.data.instance_args[i] = await arg.reconstructed_async(
                    always_fetch=False
                )

        for key, kwarg in enumerate(tuple(self.data.instance_kwargs.items())):
            if isinstance(kwarg, serials.BaseSerializer):
                self.data.instance_kwargs[key] = await kwarg.reconstructed_async(
                    always_fetch=False
                )

    async def on_run(self):
        output = getattr(self.data.instance, self.data.method_name)(
            *self.data.instance_args, **self.data.instance_kwargs
        )
        if self.data.is_async:
            output = await output

        self.set_output_field("output", output)

    async def on_stop(self, reason, by_force):
        if self.failed():
            if self.data.kill_if_failed:
                self.KILL()
        else:
            self.COMPLETE()
