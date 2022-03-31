"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file implements a base class for grouping together job classes
into class namespaces.
"""

from tkinter import DISABLED
from typing import Any, Callable, Generic, Literal, Optional, Type, Union

from pgbot.common import UNSET

from . import proxies
from .jobs import JobBase


class JobGroup:
    """A base class for job groups, which are class namespaces in which job classes can
    be defined. A JobGroup subclass should be a direct subclass of this base class.
    Inheritance of job classes defined in a superclass job group that inherits from
    this class is not supported, as the set of jobs in a job group are not transferrable
    to subclasses.
    """

    __frozen_job_class_members__ = frozenset()
    __job_class_members__ = ()

    def __init_subclass__(cls):
        members = []

        if cls.__base__ is not JobGroup:
            raise ValueError("subclassing subclasses of JobGroup is not supported")

        for obj in cls.__dict__.values():
            if isinstance(obj, type) and issubclass(obj, JobBase):
                if not obj.__qualname__.endswith(f"{cls.__name__}.{obj.__name__}"):
                    raise ValueError(
                        "all job classes in a job group namespace must be defined within it"
                    )
                members.append(obj)

        cls.__frozen_job_class_members__ = frozenset(members)
        cls.__job_class_members__ = tuple(members)

    @classmethod
    def members(cls) -> tuple[Type[JobBase]]:
        """Get the job classes that are members of this job group.

        Returns:
            tuple: The job classes.
        """
        return cls.__job_class_members__

    @classmethod
    def has_class(cls, job_cls: JobBase) -> bool:
        """Whether a specified job class is contained in this job group.

        Args:
            job_cls (JobBase): The target job class.
        """

        return job_cls in cls.__frozen_job_class_members__

    @classmethod
    def is_group_member_instance(cls, obj: Union[JobBase, proxies.JobProxy]) -> bool:
        """Whether the specified job is an instance of one of the jobs
        within this job group.

        Args:
            job_or_proxy (Union[JobBase, proxies.JobProxy]): The target job instance, or its
              proxy.

        Returns:
            bool: True/False
        """

        job_cls = obj.__class__
        if isinstance(obj, proxies.JobProxy):
            job_cls = obj.job_class

        return issubclass(job_cls, cls.__job_class_members__)


class NameRecord:
    """A base class that acts like an extendable enum of strings, which stores
    variables with string values in its class namespace. Variables starting with
    an underscore are automatically ignored. Variables can be defined without
    assignment by annotating them, in which case their value defaults to their name.
    """

    __record_names__: tuple[str] = tuple()
    __frozen_record_names__: frozenset[str] = frozenset()

    def __init_subclass__(cls):

        for key, obj in cls.__dict__.items():
            if key.startswith("_"):
                continue

            if not isinstance(obj, str):
                TypeError(
                    "can only set NameRecord variables to strings, bare "
                    "NameRecord variable definitions whose value should "
                    "match their variable name must be annotations"
                )

        for key in cls.__dict__.get("__annotations__", ()):
            if key.startswith("_") or key in cls.__dict__:
                continue

            setattr(cls, key, key)

        cls.__record_names__ = cls.get_all_names()
        cls.__frozen_record_names__ = frozenset(cls.__record_names__)

    def __new__(cls):
        raise TypeError("cannot instantiate a NameRecord")

    @classmethod
    def has_name(
        cls,
        name: str,
        check_bases: bool = True,
    ):
        if not isinstance(name, str):
            raise TypeError("argument 'name' must be a string")
        elif name.startswith("_"):
            return False

        if check_bases:
            if name in cls.__frozen_record_names__:
                return isinstance(getattr(cls, name, None), str)
            return False

        return name in cls.__dict__ and isinstance((value := cls.__dict__[name]), str)

    @classmethod
    def get_all_names(cls):
        if cls.__record_names__ is not None:
            return cls.__record_names__

        return tuple(
            name
            for name in dir(cls)
            if not name.startswith("_")
            and isinstance((value := getattr(cls, name, None)), str)
        )


class OutputNameRecord(NameRecord):
    """A subclass of NameRecord used for defining names of output fields
    and queues in job classes. Unlike NameRecord, this subclass does not
    allow assigments to variables other than 'DISABLED', which is used
    for marking inherited output types as disabled within job classes.
    Additionally, all annotated must be annotated with the 'str' type
    or 'Literal['DISABLED']', which automatically assigns 'DISABLED'.
    """

    def __init_subclass__(cls):
        bases_dir_set = set().union(*(dir(base_cls) for base_cls in cls.__bases__))

        disabled_type_hint = Literal["DISABLED"]

        for key, obj in cls.__dict__.items():
            if key.startswith("_"):
                continue
            elif key.upper() == "DISABLED":
                raise ValueError("cannot use 'DISABLED' as an output name")

            if isinstance(obj, str) and obj.upper() == "DISABLED":
                if key not in bases_dir_set:
                    raise ValueError(
                        "cannot set an output name to be disabled if it has not been "
                        "defined in a superclass"
                    )

                setattr(cls, key, "DISABLED")
            else:
                TypeError(
                    "can only set output name variables to the 'DISABLED' string, "
                    "bare output name variable definitions must be annotations with "
                    "the 'str' type or 'Literal['DISABLED']'"
                )

        for key, anno in cls.__dict__.get("__annotations__", {}).items():
            if key.startswith("_") or key in cls.__dict__:
                continue

            if anno not in (str, "str", disabled_type_hint):
                raise ValueError(
                    "only annotations with the 'str' type or 'Literal['DISABLED']' "
                    "are supported"
                )
            elif anno == disabled_type_hint:
                setattr(cls, key, "DISABLED")
            else:
                setattr(cls, key, key)

        cls.__record_names__ = cls.get_all_names()
        cls.__frozen_record_names__ = frozenset(cls.__record_names__)

    @classmethod
    def has_name(
        cls, name: str, check_bases: bool = True, include_disabled: bool = True
    ):
        if not isinstance(name, str):
            raise TypeError("argument 'name' must be a string")
        elif name.startswith("_"):
            return False

        if check_bases:
            if name in cls.__frozen_record_names__:
                result = getattr(cls, name, None)
                return (
                    (isinstance(result, str) and result in (name, "DISABLED"))
                    if include_disabled
                    else (isinstance(result, str) and result == name)
                )

            return False

        return name in cls.__dict__ and (
            name in (cls.__dict__[name], "DISABLED")
            if include_disabled
            else name == cls.__dict__[name]
        )

    @classmethod
    def name_is_disabled(cls, name: str):
        """Whether the topmost occurence in this OutputRecordName subclass
        of the specified output name has been marked as disabled, which
        means that the value of the name equals 'DISABLED'.

        Args:
            name (str): The output name.

        Raises:
            ValueError: Invalid output name format.
            LookupError: Output name doesn't yet exist.

        Returns:
            bool: True/False
        """
        if not isinstance(name, str):
            raise TypeError("argument 'name' must be a string")
        elif name.startswith("_"):
            raise ValueError("output names cannot start with underscores")

        if name not in cls.__frozen_record_names__:
            raise LookupError(
                "the specified output name is not contained in this output name class or any of its bases"
            )

        return getattr(cls, name, None) == "DISABLED"

    @classmethod
    def get_all_names(cls, include_disabled: bool = True):
        if include_disabled and cls.__record_names__ is not None:
            return cls.__record_names__

        return (
            tuple(
                name
                for name in dir(cls)
                if not name.startswith("_")
                and isinstance((value := getattr(cls, name, None)), str)
            )
            if include_disabled
            else tuple(
                name
                for name in dir(cls)
                if not name.startswith("_")
                and isinstance((value := getattr(cls, name, None)), str)
                and value != "DISABLED"
            )
        )
