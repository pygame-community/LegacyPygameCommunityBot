"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

A asynchronous job module based on OOP principles.
"""

from .base_jobs import (
    get_job_class_from_id,
    get_job_class_id,
    get_job_class_permission_level,
    DEFAULT_JOB_EXCEPTION_WHITELIST,
    JOB_STATUS,
    JOB_VERBS,
    JOB_STOP_REASONS,
    JOB_PERMISSION_LEVELS,
    JobError,
    JobPermissionError,
    JobStateError,
    JobInitializationError,
    JobWarning,
    JobNamespace,
    singletonjob,
    jobservice,
    JobBase,
    IntervalJobBase,
    EventJobBase,
    JobManagerJob,
)
from .manager import JobManager
from .proxies import *
from . import utils
