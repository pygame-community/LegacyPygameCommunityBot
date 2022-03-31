"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

A module for creating asynchronous task execution system based on OOP principles.
"""

from .jobs import (
    get_job_class_from_runtime_identifier,
    get_job_class_permission_level,
    DEFAULT_JOB_EXCEPTION_WHITELIST,
    JobStatus,
    JobVerbs,
    JobStopReasons,
    JobPermissionLevels,
    JobError,
    JobPermissionError,
    JobStateError,
    JobInitializationError,
    JobWarning,
    JobNamespace,
    singletonjob,
    publicjobmethod,
    JobBase,
    IntervalJobBase,
    EventJobBase,
    JobManagerJob,
)
from .manager import JobManager
from .proxies import JobProxy, JobOutputQueueProxy, JobManagerProxy
from .groupings import JobGroup
from . import jobutils
