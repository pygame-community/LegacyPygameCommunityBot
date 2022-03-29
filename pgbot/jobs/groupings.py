"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file implements a base class for grouping together job classes
into class namespaces.
"""

from typing import Optional, Type, Union

from pgbot.utils.utils import class_getattr_unique, class_getattr

from . import proxies
from .jobs import JobBase


class JobGroup:
    """A base class for job groups, which are class namespaces in which job classes can
    be defined.
    """

    __frozen_job_class_members__ = frozenset()
    __job_class_members__ = ()

    def __init_subclass__(cls):
        members = []

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


class OutputNameRecord:
    """A custom class that acts like an extendable enum of strings,
    which is used for defining supported types of output fields, queues,
    public methods and more within job classes. A class attribute of a subclass
    of this class that begins with an underscore is automatically ignored.
    """

    __output_names__: tuple[str] = ()
    __frozen_output_names__: frozenset[str] = frozenset()

    def __init_subclass__(cls):
        bases_dir_set = set().union(*(dir(base_cls) for base_cls in cls.__bases__))

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
                    "can only set output name variables to the 'DISABLED' string, bare ",
                    "output name variable definitions must be annotations with the 'str' type",
                )

        for key, anno in cls.__annotations__.items():
            if key.startswith("_") or key in cls.__dict__:
                continue

            if anno not in (str, "str"):
                raise ValueError("only annotations with the 'str' type are supported")
            else:
                setattr(cls, key, key)

        cls.__output_names__ = cls.get_all_output_names()
        cls.__frozen_output_names__ = frozenset(cls.__output_names__)

    @classmethod
    def has_output_name(
        cls, name: str, check_bases: bool = True, include_disabled: bool = True
    ):
        if not isinstance(name, str):
            raise TypeError("argument 'name' must be a string")
        elif name.startswith("_"):
            return False

        if check_bases:
            result = getattr(cls, name, None)
            return (
                (isinstance(result, str) and result in (name, "DISABLED"))
                if include_disabled
                else (isinstance(result, str) and result == name)
            )

        return name in cls.__dict__ and (
            name in (cls.__dict__[name], "DISABLED")
            if include_disabled
            else name == cls.__dict__[name]
        )

    @classmethod
    def output_name_is_disabled(cls, name: str):
        """Whether the topmost occurence of the specified
        output name has been marked as disabled.

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

        value = getattr(cls, name, None)

        if value is None:
            raise LookupError(
                "the specified output name is not contained in this output name class or any of its bases"
            )

        return value == "DISABLED"

    @classmethod
    def get_all_output_names(cls, include_disabled: bool = True):
        if include_disabled and cls.__output_names__ is not None:
            return cls.__output_names__

        return tuple(
            name
            for name in dir(cls)
            if not name.startswith("_")
            and isinstance((value := getattr(cls, name)), str)
            and value != "DISABLED"
        )
