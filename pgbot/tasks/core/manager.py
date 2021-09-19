"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file implements a task manager class for running and managing task objects
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

from . import base_tasks, events, serializers

ClientEventTask = base_tasks.ClientEventTask
IntervalTask = base_tasks.IntervalTask
TaskInitializationError = base_tasks.TaskInitializationError
TaskError = base_tasks.TaskError

client = common.bot


class BotTaskManager:
    """The task manager for all interval tasks and client event tasks.
    It acts as a container for interval and client event task objects, whilst also being responsible dispatching
    client events to client event task objects. Each of the tasks that a bot task manager
    contains can use it to register new task objects that they instantiate at runtime.
    """

    def __init__(self, *tasks: Union[ClientEventTask, IntervalTask], loop=None):
        """Create a new bot task manager instance.

        Args:
            *tasks: Union[ClientEventTask, IntervalTask]:
                The task objects to add during initiation.
        """
        if loop is None:
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                self._loop = asyncio.get_event_loop()

        self._loop = loop
        self._client_event_task_pool = {}
        self._interval_task_pool = set()
        self._task_id_map = {}
        self._event_waiting_queues = {}
        self._schedule_dict = {}
        self._schedule_dict_fails = {}
        self._running = True
        self._schedule_init = False

        if tasks:
            self.add_tasks(*tasks)

    def set_event_loop(self, loop):
        """[summary]

        Args:
            loop (AbstractEventLoop): The loop this task is meant to use.

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
    async def task_scheduling_loop(self):
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

                    if d["class_name"] in base_tasks.TASK_CLASS_MAP:
                        try:
                            task = base_tasks.TASK_CLASS_MAP[d["class_name"]](
                                *d["init_args"], **d["init_kwargs"]
                            )
                        except Exception as e:
                            print(
                                "Task initiation failed due to an exception:",
                                e.__class__.__name__ + ":",
                                e,
                            )
                            if d["class_name"] not in self._schedule_dict_fails:
                                self._schedule_dict_fails[d["class_name"]] = []

                            self._schedule_dict_fails[d["class_name"]].append(d)
                            deletion_list.append(j)
                            continue
                        else:
                            if not isinstance(task, (ClientEventTask, IntervalTask)):
                                print(
                                    f"Invalid task type found in task class scheduling data: '{type(task).__name__}'"
                                )
                            self.add_task(await task.as_initialized())
                            d["recurrences"] += 1
                    else:
                        print(
                            f"Task initiation failed: Could not find task type called '{d['class']}'"
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

                deletion_list *= 0
                if not self._schedule_dict[timestamp]:
                    del self._schedule_dict[timestamp]

            if i % 10:
                await asyncio.sleep(0)

    @task_scheduling_loop.before_loop
    async def _task_scheduling_start(self):
        if not self._schedule_init:
            async with db.DiscordDB("task_schedule") as db_obj:
                self._schedule_dict = db_obj.get({})
            self._schedule_init = True

    @task_scheduling_loop.after_loop
    async def _task_scheduling_end(self):
        async with db.DiscordDB("task_schedule") as db_obj:
            db_obj.write(self._schedule_dict)

    def schedule_task(
        self,
        task_type: type,
        timestamp: Union[datetime.datetime, datetime.timedelta],
        recur_interval: Optional[datetime.timedelta] = None,
        max_recurrences: Optional[int] = None,
        init_args: tuple = (),
        init_kwargs: dict = None,
        data: dict = None,
    ):
        """[summary]

        Args:
            task_type (type): [description]
            timestamp (Union[datetime.datetime, datetime.timedelta]): [description]
            recur_interval (Optional[datetime.timedelta], optional): [description]. Defaults to None.
            max_recurrences (Optional[int], optional): [description]. Defaults to None.
            init_args (tuple, optional): [description]. Defaults to an empty tuple.
            init_kwargs (dict, optional): [description]. Defaults to None.
            data (dict, optional): [description]. Defaults to None.

        Raises:
            RuntimeError: The bot task manager has not initiated bot task scheduling.
            TypeError: Invalid argument types were given.
        """

        NoneType = type(None)

        if self._schedule_dict is None:
            raise RuntimeError("BotTaskManager scheduling has not been initiated")

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

        if not isinstance(init_args, (list, tuple)):
            if init_args is None:
                init_args = ()
            else:
                raise TypeError(
                    f"'init_args' must be of type 'tuple', not {type(init_args)}"
                )

        elif not isinstance(init_kwargs, dict):
            if init_kwargs is None:
                init_kwargs = {}
            else:
                raise TypeError(
                    f"'init_kwargs' must be of type 'dict', not {type(init_kwargs)}"
                )

        elif not isinstance(data, dict):
            if data is None:
                data = {}
            else:
                raise TypeError(f"'data' must be of type 'dict', not {type(data)}")

        if not issubclass(task_type, (ClientEventTask, IntervalTask)):
            raise TypeError(
                f"argument 'task_type' must be of type 'ClientEventTask' or 'IntervalTask', not '{task_type}'"
            )

        new_data = {
            "timestamp": timestamp + datetime.timedelta(),  # quick copy
            "recur_interval": recur_interval,
            "recurrences": 0,
            "max_recurrences": max_recurrences,
            "class_name": task_type.__name__,
            "init_args": tuple(init_args),
            "init_kwargs": init_kwargs,
            "data": data,
        }

        pickle.dumps(new_data)  # validation

        self._schedule_dict[timestamp].append(new_data)

    def add_tasks(
        self,
        *tasks: Union[ClientEventTask, IntervalTask],
    ):
        """Add the given task objects to this bot task manager.

        Args:
            *tasks: Union[ClientEventTask, IntervalTask]:
                The tasks to be added.
            start (bool, optional):
                Whether the given interval task objects should start immediately after being added.
                Defaults to True.
        Raises:
            TypeError: An invalid object was given as a task.
        """
        for task in tasks:
            self.add_task(task)

    def __iter__(self):
        return itertools.chain(
            tuple(
                t for t in (ce_set for ce_set in self._client_event_task_pool.values())
            ),
            tuple(self._interval_task_pool),
        )

    def add_task(self, task: Union[ClientEventTask, IntervalTask]):
        """Add the given task object to this bot task manager.

        Args:
            task: Union[ClientEventTask, IntervalTask]:
                The task to add.
            start (bool, optional):
                Whether a given interval task object should start immediately after being added.
                Defaults to True.
        Raises:
            TypeError: An invalid object was given as a task.
            ValueError: A task was given that had already ended.
            RuntimeError: A task was given that was already present in the manager.
            TaskInitializationError: An uninitialized task was given as input.
        """

        if isinstance(task, base_tasks.BotTask) and task._has_ended:
            raise ValueError(
                "cannot add a task that has ended to a BotTaskManager instance"
            )

        elif task._identifier in self._task_id_map:
            raise RuntimeError("the given task is already present in this manager")

        elif not task._is_initialized:
            raise TaskInitializationError("the given task was not initialized")

        if isinstance(task, ClientEventTask):
            for ce_type in task.EVENT_TYPES:
                if ce_type.__name__ not in self._client_event_task_pool:
                    self._client_event_task_pool[ce_type.__name__] = set()
                self._client_event_task_pool[ce_type.__name__].add(task)

        elif isinstance(task, IntervalTask):
            self._interval_task_pool.add(task)
        else:
            raise TypeError(
                f"expected an instance of class ClientEventTask or IntervalTask, not {task.__class__.__name__}"
            )

        self._task_id_map[task._identifier] = task
        task._mgr = self
        if not task._task_loop.is_running():
            task._task_loop.start()

    def _remove_task(self, task: Union[ClientEventTask, IntervalTask]):
        """Remove the given task object from this bot task manager.

        Args:
            *tasks: Union[ClientEventTask, IntervalTask]:
                The task to be removed, if present.
        Raises:
            TypeError: An invalid object was given as a task.
        """
        if not isinstance(task, (ClientEventTask, IntervalTask)):
            raise TypeError(
                f"expected an instance of class ClientEventTask or IntervalTask, not {task.__class__.__name__}"
            )

        if isinstance(task, IntervalTask) and task in self._interval_task_pool:
            self._interval_task_pool.remove(task)

        elif isinstance(task, ClientEventTask):
            for ce_type in task.EVENT_TYPES:
                if (
                    ce_type.__name__ in self._client_event_task_pool
                    and task in self._client_event_task_pool[ce_type.__name__]
                ):
                    self._client_event_task_pool[ce_type.__name__].remove(task)
                if not self._client_event_task_pool[ce_type.__name__]:
                    del self._client_event_task_pool[ce_type.__name__]

        if task in self._task_id_map:
            del self._task_id_map[task._identifier]

        if task._mgr is self:
            task._mgr = None

    def _remove_tasks(self, *tasks: Union[ClientEventTask, IntervalTask]):
        """Remove the given task objects from this bot task manager.

        Args:
            *tasks: Union[ClientEventTask, IntervalTask]:
                The tasks to be removed, if present.
            cancel (bool, optional):
                Whether the given interval task objects should be cancelled immediately after being removed.
                Defaults to True.
        Raises:
            TypeError: An invalid object was given as a task.
        """
        for task in tasks:
            self._remove_task(task)

    def has_task(self, task: Union[ClientEventTask, IntervalTask]):
        """Whether a task is contained in this bot task manager.

        Args:
            task (Union[ClientEventTask, IntervalTask]): The task object to look for.

        Returns:
            bool: True/False
        """
        return task._identifier in self._task_id_map

    def __contains__(self, task: Union[ClientEventTask, IntervalTask]):
        return task._identifier in self._task_id_map

    async def dispatch_client_event(self, event: events.ClientEvent):
        """Dispatch a `ClientEvent` subclass to all client event task objects
        in this bot task manager.

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
                    if isinstance(event, waiting_list[0]) and waiting_list[1](event) and not waiting_list[2].cancelled():
                        waiting_list[2].set_result(event.copy())
                        deletion_queue.append(deletion_idx)
                        deletion_idx += 1

                await self._loop.run_in_executor(
                    None, map, add_to_waiting_list, tuple(target_event_waiting_queue)
                )
            else:
                for i, waiting_list in enumerate(target_event_waiting_queue):
                    if isinstance(event, waiting_list[0]) and waiting_list[1](event) and not waiting_list[2].cancelled():
                        waiting_list[2].set_result(event.copy())
                        deletion_queue.append(i)
            
            for idx in reversed(deletion_queue):
                del target_event_waiting_queue[idx]

        if event_class_name in self._client_event_task_pool:
            target_tasks = self._client_event_task_pool[event_class_name]

            if len(target_tasks) > 256:

                def add_to_tasks(client_event_task):
                    if client_event_task.check_event(event):
                        client_event_task._add_event(event.copy())

                await self._loop.run_in_executor(
                    None, map, add_to_tasks, tuple(target_tasks)
                )
            else:
                for client_event_task in target_tasks:
                    if client_event_task.check_event(event):
                        client_event_task._add_event(event.copy())

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
        """Kill all task objects that are in this bot task manager."""
        await asyncio.get_event_loop().run_in_executor(
            None,
            map,
            lambda x: x.kill(),
            itertools.chain(
                tuple(
                    t
                    for t in (
                        ce_set for ce_set in self._client_event_task_pool.values()
                    )
                ),
                tuple(self._interval_task_pool),
            ),
        )

    async def kill_all_interval_tasks(self):
        """Kill all interval task objects that are in this bot task manager."""
        await asyncio.get_event_loop().run_in_executor(
            None,
            map,
            lambda x: x.kill(),
            tuple(self._interval_task_pool),
        )

    async def kill_all_client_event_tasks(self):
        """Kill all client event task objects that are in this bot task manager."""
        await asyncio.get_event_loop().run_in_executor(
            None,
            map,
            lambda x: x.kill(),
            tuple(
                t for t in (ce_set for ce_set in self._client_event_task_pool.values())
            ),
        )

    def quit(self, kill_all_tasks=True):
        self._running = False
        self.task_scheduling_loop.stop()
        if kill_all_tasks:
            self.kill_all()
