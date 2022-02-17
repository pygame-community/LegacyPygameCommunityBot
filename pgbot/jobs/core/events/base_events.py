"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file implements wrapper classes used to capture Discord Gateway events.
All classes inherit from `ClientEvent`. 
"""

from __future__ import annotations

import datetime
from typing import Any, Callable, Coroutine, Iterable, Optional, Sequence, Union


EVENT_MAP = {}

def get_all_slot_names(cls):
    slots_list = []
    cls_slot_values = getattr(cls, "__slots__", None)
    if cls_slot_values:
        slots_list.extend(cls_slot_values)
    for base_cls in cls.__bases__:
        slots_list.extend(get_all_slot_names(base_cls))
    return slots_list


class BaseEvent:
    """The base class for all events that can be dispatched to job objects at runtime."""

    alt_name: str = None

    __slots__ = ("_timestamp", "_dispatcher")

    __base_slots__ = ("_timestamp", "_dispatcher")

    def __init_subclass__(cls):
        if isinstance(cls.alt_name, str):
            EVENT_MAP[cls.alt_name] = cls

        cls.__base_slots__ = tuple(get_all_slot_names(cls))

    def __init__(self, _timestamp: datetime.datetime = None):
        self._timestamp = _timestamp or datetime.datetime.now(datetime.timezone.utc)
        self._dispatcher = None

    @property
    def created_at(self) -> datetime.datetime:
        return self._timestamp

    @property
    def dispatcher(self):
        """A proxy of the job object that dispatched this event. If set to None, the BotJobManager
        was responsible for dispatching.
        """
        return self._dispatcher

    @classmethod
    def get_subclass_names(cls, entire_subclass_chain=True) -> list:
        """Get the 'alt_name' class variable from all subclasses of this class.

        Args:
            entire_subclass_chain (bool, optional): Whether the entire subclass chain
            should be traversed recursively. Defaults to True.

        Returns:
            list: A list of 'alt_name' strings.
        """
        names = []
        for subcls in cls.__subclasses__():
            if subcls.alt_name is not None:
                names.append(subcls.alt_name)
            
            if entire_subclass_chain:
                names.extend(subcls.get_subclass_names(entire_subclass_chain=entire_subclass_chain))
        return names

    def copy(self) -> BaseEvent:
        new_obj = self.__class__.__new__(self.__class__)
        for attr in self.__base_slots__:
            setattr(new_obj, attr, getattr(self, attr))
        return new_obj

    __copy__ = copy

    def __repr__(self):
        attrs = " ".join(
            f"{attr}={val}"
            for attr, val in ((k, getattr(self, k)) for k in self.__slots__)
        )
        return f"<{self.__class__.__name__}({attrs})>"


class CustomEvent(BaseEvent):
    """The base class for all custom events that can
    be used by jobs to propatage information to other jobs.

        Attributes:
            dispatcher: The job object which dispatched this event.
    """

    __slots__ = ()


