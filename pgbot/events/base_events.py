"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file implements base classes used to capture or emit events.
"""

from __future__ import annotations

import time
import datetime
from typing import Any, Callable, Coroutine, Iterable, Optional, Sequence, Type, Union


_EVENT_CLASS_MAP = {}


def get_event_class_from_id(class_identifier: str, closest_match: bool = True):

    name, timestamp_str = class_identifier.split("-")

    if name in _EVENT_CLASS_MAP:
        if timestamp_str in _EVENT_CLASS_MAP[name]:
            return _EVENT_CLASS_MAP[name][timestamp_str]
        elif closest_match:
            for ts_str in _EVENT_CLASS_MAP[name]:
                return _EVENT_CLASS_MAP[name][ts_str]

    raise KeyError(
        f"cannot find event class with an identifier of "
        f"'{class_identifier}' in the event class registry"
    )


def get_event_class_id(cls: Type[BaseEvent], raise_exceptions=True):

    if not issubclass(cls, BaseEvent):
        raise TypeError("argument 'cls' must be a subclass of an event base class")

    try:
        class_identifier = cls._IDENTIFIER
    except AttributeError:
        raise TypeError(
            "invalid event class, must be"
            " a subclass of an event base class with an identifier"
        ) from None

    try:
        name, timestamp_str = class_identifier.split("-")
    except ValueError:
        raise ValueError("invalid identifier found in the given event class") from None

    if name in _EVENT_CLASS_MAP:
        if timestamp_str in _EVENT_CLASS_MAP[name]:
            if _EVENT_CLASS_MAP[name][timestamp_str] is cls:
                return class_identifier
            else:
                if raise_exceptions:
                    raise ValueError(f"The given event class has an invalid identifier")
        else:
            if raise_exceptions:
                ValueError(
                    f"The given event class is registered under"
                    " a different identifier in the event class registry"
                )

    if raise_exceptions:
        raise LookupError(
            f"The given event class does not exist in the event class registry"
        )


def get_all_slot_names(cls):
    slots_list = []
    cls_slot_values = getattr(cls, "__slots__", None)
    if cls_slot_values:
        slots_list.extend(cls_slot_values)
    for base_cls in cls.__bases__:
        slots_list.extend(get_all_slot_names(base_cls))
    return slots_list


class BaseEvent:
    """The base class for all events."""

    _CREATED_AT = datetime.datetime.now(datetime.timezone.utc)
    _IDENTIFIER = f"BaseEvent-{int(_CREATED_AT.timestamp()*1_000_000_000)}"

    __slots__ = ("_event_created_at", "_dispatcher")

    __base_slots__ = __slots__
    # helper class attribute for faster copying by skipping initialization when
    # shallow-copying jobs

    def __init_subclass__(cls):

        cls._CREATED_AT = datetime.datetime.now(datetime.timezone.utc)

        name = cls.__name__
        timestamp = f"{int(cls._CREATED_AT.timestamp()*1_000_000_000)}"

        cls._IDENTIFIER = f"{name}-{timestamp}"

        if name not in _EVENT_CLASS_MAP:
            _EVENT_CLASS_MAP[name] = {}

        _EVENT_CLASS_MAP[name][timestamp] = cls

        cls.__base_slots__ = tuple(get_all_slot_names(cls))

    def __init__(self, event_created_at: datetime.datetime = None):
        if event_created_at:
            self._event_created_at = event_created_at
        else:
            self._event_created_at = datetime.datetime.now(datetime.timezone.utc)

        self._dispatcher = None

    @property
    def event_created_at(self):
        """The time at which this event occured or was
        created at, which can be optionally set
        during instantiation. Defaults to the time
        of instantiation of the event object.

        Returns:
            datetime.datetime: The time.
        """
        return self._event_created_at

    @property
    def dispatcher(self):
        """A proxy of the job object that dispatched this event, if available."""
        return self._dispatcher

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
    """A base class for custom events."""

    __slots__ = ()
