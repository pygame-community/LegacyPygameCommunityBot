"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file implements wrapper classes used to capture or emit events.
"""

from __future__ import annotations

import datetime
from typing import Any, Callable, Coroutine, Iterable, Optional, Sequence, Type, Union


_EVENT_CLASS_MAP = {}


def get_event_class_from_id(class_identifier: str, closest_match: bool = True):

    name, timestamp_str = class_identifier.split("-")

    if name in _EVENT_CLASS_MAP:
        if timestamp_str in _EVENT_CLASS_MAP[name]:
            return _EVENT_CLASS_MAP[name][timestamp_str]["class"]
        elif closest_match:
            for ts_str in _EVENT_CLASS_MAP[name]:
                return _EVENT_CLASS_MAP[name][ts_str]["class"]

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
            if _EVENT_CLASS_MAP[name][timestamp_str]["class"] is cls:
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


def get_event_class_alt_name(cls: Type[BaseEvent], raise_exceptions=True):

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
            if _EVENT_CLASS_MAP[name][timestamp_str]["class"] is cls:
                return _EVENT_CLASS_MAP[name][timestamp_str]["alt_name"]
            else:
                if raise_exceptions:
                    raise ValueError(
                        f"The given event class has the incorrect identifier"
                    )
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
    """The base class for all events that can be dispatched to job objects at runtime."""

    alt_name: str = None

    _CREATED_AT = datetime.datetime.now(datetime.timezone.utc)
    _IDENTIFIER = f"BaseEvent-{int(_CREATED_AT.timestamp()*1_000_000_000)}"

    __slots__ = ("_created_at", "_dispatcher")

    __base_slots__ = (
        "_created_at",
        "_dispatcher",
    )  # helper class attribute for faster copying by skipping initialization

    def __init_subclass__(cls):

        cls._CREATED_AT = datetime.datetime.now(datetime.timezone.utc)

        name = cls.__name__
        timestamp = f"{int(cls._CREATED_AT.timestamp()*1_000_000_000)}"

        cls._IDENTIFIER = f"{name}-{timestamp}"

        if name not in _EVENT_CLASS_MAP:
            _EVENT_CLASS_MAP[name] = {}

        _EVENT_CLASS_MAP[name][timestamp] = {"class": cls, "alt_name": None}

        if isinstance(cls.alt_name, str):
            _EVENT_CLASS_MAP[name][timestamp]["alt_name"] = cls.alt_name

        cls.__base_slots__ = tuple(get_all_slot_names(cls))

    def __init__(self, _created_at: datetime.datetime = None):
        self._created_at = _created_at or datetime.datetime.now(datetime.timezone.utc)
        self._dispatcher = None

    @property
    def created_at(self) -> datetime.datetime:
        return self._created_at

    @property
    def dispatcher(self):
        """A proxy of the job object that dispatched this event. If set to None, a `JobManager`
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
                names.extend(
                    subcls.get_subclass_names(
                        entire_subclass_chain=entire_subclass_chain
                    )
                )
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
