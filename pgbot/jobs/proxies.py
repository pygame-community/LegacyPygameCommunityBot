"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file implements proxy objects used by job and job managers
for extra features and encapsulation. 
"""

from collections import deque
import datetime
from typing import Callable, Optional, Type, Union
from pgbot import events

from pgbot.events import BaseEvent
from .base_jobs import EventJobBase, IntervalJobBase, JobBase


class JobProxy:
    __slots__ = (
        "__j",
        "__job_class",
        "__identifier",
        "__created_at",
        "__registered_at",
    )

    def __init__(self, job: JobBase):
        self.__j = job
        self.__job_class = job.__class__
        self.__identifier = job._identifier
        self.__created_at = job.created_at
        self.__registered_at = job.registered_at

    @property
    def job_class(self):
        return self.__job_class

    @property
    def identifier(self):
        return self.__identifier

    @property
    def creator(self):
        """The `JobProxy` of the creator of this job object."""
        return self.__j._creator

    @property
    def guardian(self):
        """The `JobProxy` of the current guardian of this job object."""
        return self.__j._guardian

    @property
    def created_at(self):
        return self.__created_at

    @property
    def registered_at(self):
        return self.__registered_at

    @property
    def schedule_identifier(self):
        """The identfier of the scheduling operation that instantiated
        this job object, if available.
        """
        return self.__j._schedule_identifier

    @property
    def permission_level(self):
        return self.__job_class._PERMISSION_LEVEL

    def copy(self):
        proxy = self.__class__.__new__(self.__class__)

        for attr in self.__slots__:
            setattr(proxy, attr, getattr(self, attr))

        return proxy

    def loop_count(self):
        """The current amount of `on_run()` calls completed by this job object."""
        return self.__j.loop_count()

    def initialized(self):
        """Whether this job has been initialized.

        Returns:
            bool: True/False
        """
        return self.__j.initialized()

    def is_being_initialized(self):
        """Whether this job object is being initialized.

        Returns:
            bool: True/False
        """

        return self.__j.is_being_initialized()

    def initialized_since(self):
        """The time at which this job object was initialized, if available.

        Returns:
            datetime.datetime: The time, if available.
        """
        return self.__j.initialized_since()

    def is_being_stopped(self, get_reason: bool = False):
        """Whether this job object is being stopped.

        Args:
            get_reason (bool, optional): Whether the reason for stopping should
              be returned as a string. Defaults to False.

        Returns:
            Union[bool, str]: Returns a boolean if `get_reason` is False, otherwise
              a string is returned. If the string is empty, no stopping is occuring.
        """
        return self.__j.is_being_stopped(get_reason=get_reason)

    def get_last_stop_reason(self):
        """Get the last reason this job object stopped, when applicable.

        Returns:
            Optional[str]: The reason for stopping.
        """
        return self.__j.get_last_stop_reason()

    def is_awaiting(self):
        """Whether this job is currently waiting for a coroutine to complete,
        which was awaited using `.wait_for(awaitable)`.

        Returns:
            bool: True/False
        """
        return self.__j.is_awaiting()

    def awaiting_since(self):
        """The last time at which this job object began awaiting, if available.

        Returns:
            datetime.datetime: The time, if available.
        """
        return self.__j.awaiting_since()

    def alive(self):
        """Whether this job is currently alive
        (initialized and bound to a job manager).

        Returns:
            bool: True/False
        """
        return self.__j.alive()

    def alive_since(self):
        """The last time at which this job object became alive, if available.

        Returns:
            datetime.datetime: The time, if available.
        """
        return self.__j.alive_since()

    def is_starting(self):
        """Whether this job is currently starting to run.

        Returns:
            bool: True/False
        """
        return self.__j.is_starting()

    def is_running(self):
        """Whether this job is currently running (alive and not stopped).

        Returns:
            bool: True/False
        """
        return self.__j.is_running()

    def running_since(self):
        """The last time at which this job object started running, if available.

        Returns:
            datetime.datetime: The time, if available.
        """
        return self.__j.running_since()

    def stopped(self):
        """Whether this job is currently stopped (alive and not running).

        Returns:
            bool: True/False
        """
        return self.__j.stopped()

    def stopped_since(self):
        """The last time at which this job object stopped, if available.

        Returns:
            datetime.datetime: The time, if available.
        """
        return self.__j.stopped_since()

    def is_idling(self):
        """Whether this task is currently idling
        (running, waiting for the next opportunity to continue execution)

        Returns:
            bool: True/False
        """
        return self.__j.is_idling()

    def idling_since(self):
        """The last time at which this job object began idling, if available.

        Returns:
            datetime.datetime: The time, if available.
        """
        return self.__j.idling_since()

    def failed(self):
        """Whether this job's `.on_run()` method failed an execution attempt,
        usually due to an exception.

        Returns:
            bool: True/False
        """
        return self.__j.failed()

    def killed(self):
        """Whether this job was killed."""
        return self.__j.killed()

    def killed_at(self):
        """The last time at which this job object was killed, if available.

        Returns:
            datetime.datetime: The time, if available.
        """
        return self.__j.killed_at()

    def is_being_killed(self, get_reason=False):
        """Whether this job is being killed.

        Args:
            get_reason (bool, optional): If set to True, the reason
              for killing will be returned. Defaults to False.

        Returns:
            bool: True/False
            str: 'INTERNAL_KILLING' or 'EXTERNAL_KILLING' or ''
              depending on if this job is being killed or not.
        """
        return self.__j.is_being_killed(get_reason=get_reason)

    def is_being_startup_killed(self):
        """Whether this job was started up only for it to be killed.
        This is useful for knowing if a job skipped `on_start()` and `on_run()`
        due to that, and can be checked for within `on_stop()`.
        """
        return self.__j.is_being_startup_killed()

    def completed(self):
        """Whether this job completed successfully.

        Returns:
            bool: True/False
        """
        return self.__j.completed()

    def completed_at(self):
        """The last time at which this job object completed successfully,
        if available.

        Returns:
            datetime.datetime: The time, if available.
        """
        return self.__j.completed_at()

    def is_being_completed(self):
        """Whether this job is in the process of completing,
        either due to being killed, or due to it ending itself.

        Returns:
            bool: True/False
        """
        return self.__j.is_being_completed()

    def done(self):
        """Whether this job was killed or has completed.

        Returns:
            bool: True/False
        """
        return self.__j.done()

    def done_since(self):
        """The last time at which this job object completed successfully or was killed, if available.

        Returns:
            datetime.datetime: The time, if available.
        """
        return self.__j.done_since()

    def is_being_restarted(self, get_reason=False):
        """Whether this job is being restarted.

        Args:
            get_reason (bool, optional):
                If set to True, the restart reason will be returned.
                Defaults to False.

        Returns:
            bool: True/False
            str: 'INTERNAL_RESTART' or 'EXTERNAL_RESTART' or ''
              depending on if a restart applies.
        """
        return self.__j.is_being_restarted(get_reason=get_reason)

    def is_being_guarded(self):
        """Whether this job object is being guarded.

        Returns:
            bool: True/False
        """
        return self.__j.is_being_guarded()

    def await_done(
        self, timeout: Optional[float] = None, cancel_if_killed: bool = False
    ):
        """Wait for this job object to be done (completed or killed) using the
        coroutine output of this method.

        Args:
            timeout (float, optional): Timeout for awaiting. Defaults to None.
            cancel_if_killed (bool): Whether `asyncio.CancelledError`
              should be raised if the job is killed. Defaults to False.

        Raises:
            JobStateError: This job object is already done or not alive.
            asyncio.TimeoutError: The timeout was exceeded.
            asyncio.CancelledError: The job was killed.

        Returns:
            Coroutine: A coroutine that evaluates to `True`.
        """

        return self.__j.await_done(timeout=timeout, cancel_if_killed=cancel_if_killed)

    def await_unguard(self, timeout: Optional[float] = None):
        """Wait for this job object to be unguarded using the
        coroutine output of this method.

        Args:
            timeout (float, optional):
                Timeout for awaiting. Defaults to None.

        Raises:
            JobStateError: This job object is already done or not alive,
              or isn't being guarded.
            asyncio.TimeoutError: The timeout was exceeded.
            asyncio.CancelledError: The job was killed.

        Returns:
            Coroutine: A coroutine that evaluates to `True`.
        """
        return self.__j.await_unguard(timeout=timeout)

    def get_output_queue_proxy(self):
        """Get a job output queue proxy object for more convenient
        reading of job output queues while this job is running.

        Raises:
            JobStateError: This job object is already done or not alive,
              or isn't being guarded.
            TypeError: Output queues aren't
              defined for this job type.

        Returns:
            JobOutputQueueProxy: The output queue proxy.
        """

        return self.__j.get_output_queue_proxy()

    def verify_output_field_support(self, field_name: str, raise_exceptions=False):
        """Verify if a specified output field name is supported by this job,
        or if it supports output fields at all.

        Args:
            field_name (str): The name of the output field to set.
            raise_exceptions (Optional[bool]): Whether exceptions
              should be raised. Defaults to False.

        Raises:
            TypeError: Output fields aren't supported for this job,
              or `field_name` is not a string.
            LookupError: The specified field name is not defined by this job.
        """
        return self.__j.verify_output_field_support(
            field_name, raise_exceptions=raise_exceptions
        )

    def verify_output_queue_support(self, queue_name: str, raise_exceptions=False):
        """Verify if a specified output queue name is supported by this job,
        or if it supports output queues at all.

        Args:
            queue_name (str): The name of the output queue to set.
            raise_exceptions (Optional[bool]): Whether exceptions should be
              raised. Defaults to False.

        Raises:
            TypeError: Output fields aren't supported for this job,
              or `queue_name` is not a string.
            LookupError: The specified queue name is not defined by this job.
        """
        return self.__j.verify_output_queue_support(
            queue_name, raise_exceptions=raise_exceptions
        )

    def get_output_field(self, field_name: str, default=Ellipsis):
        """Get the value of a specified output field.

        Args:
            field_name (str): The name of the target output field.
            default (str): The value to return if the specified
              output field does not exist, has not been set,
              or if this job doesn't support them at all.
              Defaults to the `Ellipsis` singleton, which will
              trigger an exception.

        Raises:
            TypeError: Output fields aren't supported for this job,
              or `field_name` is not a string.
            LookupError: The specified field name is not defined by this job.
            JobStateError: An output field value is not set.

        Returns:
            object: The output field value.
        """

        return self.__j.get_output_field(field_name, default=default)

    def get_output_queue_contents(self, queue_name: str, default=Ellipsis):
        """Get a list of all values present in the specified output queue.
        For continuous access to job output queues, consider requesting
        a `JobOutputQueueProxy` object using `.get_output_queue_proxy()`.

        Args:
            queue_name (str): The name of the target output queue.
            default (str): The value to return if the specified
              output queue does not exist, is empty,
              or if this job doesn't support them at all.
              Defaults to the `Ellipsis` singleton, which will
              trigger an exception.

        Raises:
            TypeError: Output fields aren't supported for this job,
              or `queue_name` is not a string.
            LookupError: The specified queue name is not defined by this job.
            JobStateError: The specified output queue is empty.

        Returns:
            list: A list of values.
        """

        return self.__j.get_output_queue_contents(queue_name, default=default)

    def get_output_field_names(self):
        """Get all output field names that this job supports.

        Returns:
            tuple: A tuple of the supported output fields.
        """
        return self.__j.get_output_field_names()

    def get_output_queue_names(self):
        """Get all output queue names that this job supports.

        Returns:
            tuple: A tuple of the supported output queues.
        """
        return self.__j.get_output_queue_names()

    def has_output_field_name(self, field_name: str):
        """Whether the specified field name is supported as an
        output field.

        Args:
            field_name (str): The name of the target output field.

        Returns:
            bool: True/False
        """

        return self.__j.has_output_field_name(field_name)

    def has_output_queue_name(self, queue_name: str):
        """Whether the specified queue name is supported as an
        output queue.

        Args:
            queue_name (str): The name of the target output queue.

        Returns:
            bool: True/False
        """

        return self.__j.has_output_queue_name(queue_name)

    def output_field_is_set(self, field_name: str):
        """Whether a value for the specified output field
        has been set.

        Args:
            field_name (str): The name of the target output field.

        Raises:
            TypeError: Output fields aren't supported for this job,
              or `field_name` is not a string.
            LookupError: The specified field name is not defined by this job.

        Returns:
            bool: True/False
        """

        return self.__j.output_field_is_set(field_name)

    def output_queue_is_empty(self, queue_name: str):
        """Whether the specified output queue is empty.

        Args:
            queue_name (str): The name of the target output queue.

        Raises:
            TypeError: Output queues aren't supported for this job,
              or `queue_name` is not a string.
            LookupError: The specified queue name is not defined by this job.

        Returns:
            bool: True/False
        """

        return self.__j.output_queue_is_empty(queue_name)

    def await_output_field(self, field_name: str, timeout: Optional[float] = None):
        """Wait for this job object to release the value of a
        specified output field while it is running, using the
        coroutine output of this method.

        Args:
            timeout (float, optional): The maximum amount of
              time to wait in seconds. Defaults to None.

        Raises:
            TypeError: Output fields aren't supported for this job,
              or `field_name` is not a string.
            LookupError: The specified field name is not defined by this job.
            JobStateError: This job object is already done.
            asyncio.TimeoutError: The timeout was exceeded.
            asyncio.CancelledError: The job was killed.

        Returns:
            Coroutine: A coroutine that evaluates to the value of specified
              output field.
        """

        return self.__j.await_output_field(field_name, timeout=timeout)

    def await_output_queue_update(
        self,
        queue_name: str,
        timeout: Optional[float] = None,
        cancel_if_cleared: bool = True,
    ):
        """Wait for this job object to update the specified output queue while
        it is running, using the coroutine output of this method.

        Args:
            timeout (float, optional): The maximum amount of time to wait in
              seconds. Defaults to None.
            cancel_if_cleared (bool): Whether `asyncio.CancelledError` should
              be raised if the output queue is cleared. If set to `False`,
              `Ellipsis` will be the result of the coroutine. Defaults to False.

        Raises:
            TypeError: Output fields aren't supported for this job,
              or `field_name` is not a string.
            LookupError: The specified field name is not defined by this job
            JobStateError: This job object is already done.
            asyncio.TimeoutError: The timeout was exceeded.
            asyncio.CancelledError: The job was killed, or the output queue
              was cleared.

        Returns:
            Coroutine: A coroutine that evaluates to the most recent output
              queue value, or `Ellipsis` if the queue is cleared.
        """

        return self.__j.await_output_queue_update(
            queue_name, timeout=timeout, cancel_if_cleared=cancel_if_cleared
        )

    def interval_job_next_iteration(self):
        """
        THIS METHOD WILL ONLY WORK ON PROXIES TO JOB OBJECTS
        THAT ARE INSTANCES OF `IntervalJobBase`.

        When the next iteration of `.on_run()` will occur.
        If not known, this method will return `None`.

        Raises:
            TypeError: The class of this job proxy's job is not an 'IntervalJobBase' subclass.

        Returns:
            datetime.datetime: The time at which the next iteration will occur,
            if available.
        """
        try:
            return self.__j.next_iteration()
        except AttributeError:
            raise TypeError(
                f"The '{self.__job_class.__name__}' job class of this job object's"
                " proxy is not an 'IntervalJobBase' subclass"
            ) from None

    def interval_job_get_interval(self):
        """
        THIS METHOD WILL ONLY WORK ON PROXIES TO JOB OBJECTS
        THAT ARE `IntervalJobBase` SUBCLASSES.

        Returns a tuple of the seconds, minutes and hours at which this job
        object is executing its `.on_run()` method.

        Raises:
            TypeError: The class of this job proxy's job is not an 'IntervalJobBase' subclass.

        Returns:
            tuple: `(seconds, minutes, hours)`
        """
        try:
            return self.__j.get_interval()
        except AttributeError:
            raise TypeError(
                f"The '{self.__job_class.__name__}' job class of this job object's"
                " proxy is not an 'IntervalJobBase' subclass"
            ) from None

    def __repr__(self):
        return f"<JobProxy ({self.__j})>"


class JobOutputQueueProxy:
    """A helper class for job objects to share
    data with other jobs in a continuous manner.
    """

    __slots__ = ("__j", "__job_proxy", "_output_queue_proxy_dict")

    def __init__(self, job: JobBase):
        self.__j = job
        self.__job_proxy = job._proxy
        job_output_queues = self.__j._output_queues
        self._output_queue_proxy_dict: dict[
            str, list[Union[int, Optional[deque], list]]
        ] = {
            queue_name: [0, None, job_output_queues[queue_name]]
            for queue_name in self.__j.OUTPUT_QUEUES
        }

    @property
    def job_proxy(self):
        """The job this output queue proxy is pointing to.

        Returns:
            JobProxy: The job proxy.
        """
        return self.__job_proxy

    def verify_queue_name(self, queue_name: str, raise_exceptions=False):
        """Verify if a specified output queue name is supported by this
        output queue proxy's job.

        Args:
            queue_name (str): The name of the output queue to set.
            raise_exceptions (Optional[bool]): Whether exceptions should
              be raised. Defaults to False.

        Raises:
            TypeError: `queue_name` is not a string.
            LookupError: The specified queue name is not defined by this
              output queue proxy's job.
        """

        if queue_name not in self._output_queue_proxy_dict:
            if raise_exceptions:
                raise (
                    LookupError(
                        f"queue name '{queue_name}' is not defined in"
                        f" 'OUTPUT_FIELDS' of the {self.__class__.__name__}"
                        " class of this job output queue proxy"
                    )
                    if isinstance(queue_name, str)
                    else TypeError(
                        f"'queue_name' argument must be of type str,"
                        f" not {queue_name.__class__.__name__}"
                    )
                )
            return False

        return True

    def config_queue(self, queue_name: str, use_rescue_buffer: Optional[bool] = None):
        """Configure settings for a speficied output queue.

        Args:
            queue_name (str): The name of the output queue to set.
            use_rescue_buffer (Optional[bool]): Set up a rescue buffer for the
              specified output queue, which automatically collects queue values
              when a job cleares a queue. Defaults to None.
        """
        self.verify_queue_name(queue_name, raise_exceptions=True)

        if use_rescue_buffer:
            self._output_queue_proxy_dict[queue_name][1] = deque()
        elif use_rescue_buffer is False:
            self._output_queue_proxy_dict[queue_name][1] = None

    def _queue_clear_alert(self, queue_name: str):
        queue_list = self._output_queue_proxy_dict[queue_name]

        if queue_list[1] is not None:
            queue_list[1].extend(queue_list[2])

    def pop_output_queue(self, queue_name: str):
        """Get the oldest value in the speficied output queue.


        Args:
            queue_name (str): The name of the target output queue.

        Raises:
            LookupError: The target queue is exhausted, or empty.

        Returns:
            object: The oldest value.
        """
        self.verify_queue_name(queue_name, raise_exceptions=True)

        queue_list = self._output_queue_proxy_dict[queue_name]

        if queue_list[1]:
            return queue_list[1].popleft()
        elif queue_list[2]:
            if queue_list[0] < len(queue_list[2]):
                output = queue_list[2][queue_list[0]]
                queue_list[0] += 1
                return output

            raise LookupError(f"the target queue with name '{queue_name}' is exhausted")

        else:
            raise LookupError(f"the target queue with name '{queue_name}' is empty")

    def output_queue_is_empty(self, queue_name: str, ignore_rescue_buffer=False):
        """Whether the specified output queue is empty.

        Args:
            queue_name (str):
                The name of the target output queue.
            ignore_rescue_buffer (bool): Whether the contents of the rescue buffer
              should be consideredas well. Defaults to False.

        Raises:
            TypeError:
                `queue_name` is not a string.
            LookupError:
                The specified queue name is not defined by this
                output queue proxy's job.

        Returns:
            bool: True/False
        """

        self.verify_queue_name(queue_name, raise_exceptions=True)

        if ignore_rescue_buffer:
            return not self._output_queue_proxy_dict[queue_name][2]

        queue_list = self._output_queue_proxy_dict[queue_name]
        return not queue_list[1] and not queue_list[2]

    def queue_is_exhausted(self, queue_name: str):
        """Whether the specified output queue is esxhausted,
        meaning that no new values are available.

        Args:
            queue_name (str):
                The name of the target output queue.
            ignore_rescue_buffer (bool):
                Whether the contents of the rescue buffer should be considered
                as well. Defaults to False.

        Raises:
            TypeError:
                `queue_name` is not a string.
            LookupError:
                The specified queue name is not defined by this
                output queue proxy's job.

        Returns:
            bool: True/False
        """

        self.verify_queue_name(queue_name, raise_exceptions=True)
        queue_list = self._output_queue_proxy_dict[queue_name]

        if queue_list[2] and queue_list[0] >= len(queue_list[2]):
            return True
        return False

    def await_output_queue_update(
        self,
        queue_name: str,
        timeout: Optional[float] = None,
        cancel_if_cleared: bool = True,
    ):
        """Wait for the job object of this output queue proxy to update the specified
        output queue while it is running, using the coroutine output of this method.

        Args:
            timeout (float, optional):
                The maximum amount of time to wait in seconds. Defaults to None.
            cancel_if_cleared (bool):
                Whether `asyncio.CancelledError` should be raised if the
                output queue is cleared. If set to `False`, `Ellipsis`
                will be the result of the coroutine. Defaults to False.

        Raises:
            TypeError:
                Output fields aren't supported for this job,
                or `field_name` is not a string.
            LookupError: The specified field name is not defined by this job
            JobStateError: This job object is already done.
            asyncio.TimeoutError: The timeout was exceeded.
            asyncio.CancelledError:
                The job was killed, or the output queue was cleared.

        Returns:
            Coroutine:
                A coroutine that evaluates to the most recent output queue
                value, or `Ellipsis` if the queue is cleared.
        """

        return self.__j.await_output_queue_update(
            queue_name, timeout=timeout, cancel_if_cleared=cancel_if_cleared
        )


class JobManagerProxy:

    __slots__ = ("__mgr", "__j", "_job_stop_timeout")

    def __init__(self, mgr, job: Union[EventJobBase, IntervalJobBase]):
        self.__mgr = mgr
        self.__j = job
        self._job_stop_timeout = None

    def get_job_stop_timeout(self):
        """Get the maximum time period in seconds for the job object managed
        by this `JobManagerProxy` to stop when halted from the
        `JobManager`, either due to being stopped, restarted or killed.
        By default, this method returns the global job timeout set for the
        current `JobManager`, but that can be overridden with a custom
        timeout when trying to stop the job object.

        Returns:
            float: The timeout in seconds.
            None:
                No timeout was set for the job object or globally for the
                current `JobManager`.
        """

        return (
            self._job_stop_timeout
            if self._job_stop_timeout
            else self.__mgr.get_global_job_stop_timeout()
        )

    def verify_permissions(
        self,
        op: str,
        target: Optional[JobProxy] = None,
        target_cls: Optional[Union[Type[EventJobBase], Type[IntervalJobBase]]] = None,
        schedule_identifier: Optional[str] = None,
        scheduler_identifier: Optional[str] = None,
    ):
        """Check if the permissions of the job of this `JobManagerProxy` object
        are sufficient for carrying out the specified operation on the given input.

        Args:
            op (str):
                The operation. Must be one of the operations defined in the `JOB_VERBS`
                class namespace.

            target (Optional[JobProxy]):
                The target job for an operation. Defaults to None.

            target_cls (Optional[Union[Type[EventJobBase], Type[IntervalJobBase]]]):
                The target job class for an operation. Defaults to None.

            schedule_identifier (Optional[str]):
                A target schedule identifier. Defaults to None.

            scheduler_identifier (Optional[str]):
                A target job with this specific identifier if existent,
                but can also be an enpty string. Defaults to None.

        Returns:
            bool: The result of the permission check.
        """

        return self.__mgr._verify_permissions(
            self.__j,
            op,
            target=self.__mgr._get_job_from_proxy(target)
            if target is not None
            else target,
            target_cls=target_cls,
            schedule_identifier=schedule_identifier,
            scheduler_identifier=scheduler_identifier,
            raise_exceptions=False,
        )

    def create_job(
        self, cls: Union[Type[EventJobBase], Type[IntervalJobBase]], *args, **kwargs
    ):
        """Create an instance of a job class, and return it.

        Args:
            cls (Union[Type[EventJobBase], Type[IntervalJobBase]]):
               The job class to instantiate a job object from.

        Raises:
            RuntimeError: This job manager object is not initialized.

        Returns:
            JobProxy: A job proxy object.
        """
        return self.__mgr.create_job(
            cls, *args, _return_proxy=True, _invoker=self.__j, **kwargs
        )

    async def initialize_job(self, job_proxy: JobProxy, raise_exceptions: bool = True):
        """Initialize a job object.

        Args:
            job_proxy (JobProxy): The job object's proxy.
            raise_exceptions (bool, optional): Whether exceptions should be raised.
              Defaults to True.

        Raises:
            JobInitializationError: The job given was already initialized.

        Returns:
            bool: Whether the initialization attempt was successful.
        """
        job = self.__mgr._get_job_from_proxy(job_proxy)
        return await self.__mgr.initialize_job(job, raise_exceptions=raise_exceptions)

    async def register_job(self, job_proxy: JobProxy):
        """Register a job object to this JobManager,
        while initializing it if necessary.

        Args:
            job_proxy (JobProxy): The job object's proxy.
            start (bool): Whether the given job object should start automatically
              upon registration.

        Raises:
            JobStateError: Invalid job state for registration.
            JobError: job-specific errors preventing registration.
            RuntimeError: This job manager object is not initialized.
        """
        job = self.__mgr._get_job_from_proxy(job_proxy)
        return await self.__mgr.register_job(job, _invoker=self.__j)

    async def create_and_register_job(
        self, cls: Union[Type[EventJobBase], Type[IntervalJobBase]], *args, **kwargs
    ):
        """Create an instance of a job class, and register it to this `BotTaskManager`.

        Args:
            cls (Union[Type[EventJobBase], Type[IntervalJobBase]]):
                The job class to be used for instantiation.

        Returns:
            JobProxy: A job proxy object.
        """

        return await self.__mgr.create_and_register_job(
            cls,
            *args,
            _return_proxy=True,
            _invoker=self.__j,
            **kwargs,
        )

    def job_scheduling_is_initialized(self):
        """Whether the job scheduling process of this job manager is initialized."""
        return self.__mgr.job_scheduling_is_initialized()

    async def wait_for_job_scheduling_initialization(self):
        """This method returns a coroutine that can be used to wait until job
        scheduling is initialized.

        Raises:
            RuntimeError: Job scheduling is already initialized.

        Returns:
            Coroutine: A coroutine that evaluates to `True`.
        """
        return await self.__mgr.wait_for_job_scheduling_initialization()

    async def wait_for_job_scheduling_uninitialization(self):
        """This method returns a coroutine that can be used to wait until job
        scheduling is uninitialized.

        Raises:
            RuntimeError: Job scheduling is not initialized.

        Returns:
            Coroutine: A coroutine that evaluates to `True`.
        """

        return await self.__mgr.wait_for_job_scheduling_uninitialization()

    async def create_job_schedule(
        self,
        cls: Union[Type[EventJobBase], Type[IntervalJobBase]],
        timestamp: Union[datetime.datetime, datetime.timedelta],
        recur_interval: Union[int, datetime.timedelta] = 0,
        max_recurrences: int = 1,
        job_args: tuple = (),
        job_kwargs: Optional[dict] = None,
    ):
        """Schedule a job of a specific type to be instantiated and to run at
        one or more specific periods of time. Each job can receive positional
        or keyword arguments which are passed to this method.
        Those arguments must be pickleable.

        Args:
            cls (Union[Type[EventJobBase], Type[IntervalJobBase]]): The job type to
              schedule.
            timestamp (Union[int, float, datetime.datetime]): The exact timestamp
              or offset at which to instantiate a job.
            recur_interval (Optional[Union[int, float, datetime.timedelta]]): The
              interval at which a job should be rescheduled in seconds. `None` or
              0 means that no recurrences will occur. -1 means that the smallest
              possible recur interval should be used. Defaults to None.
            max_recurrences (int): The maximum amount of recurrences for
              rescheduling. A value of -1 means that no maximum is set. Otherwise,
              the value of this argument must be a non-zero positive integer. If no
              `recur_interval` value was provided, the value of this argument will
              be ignored during scheduling and set to -1. Defaults to -1.
            job_args (tuple, optional): Positional arguments to pass to the
              scheduled job upon instantiation. Defaults to ().
            job_kwargs (dict, optional): Keyword arguments to pass to the scheduled
              job upon instantiation. Defaults to None.

        Raises:
            RuntimeError: The job manager has not yet initialized job scheduling,
              or this job manager object is not initialized.
            TypeError: Invalid argument types were given.

        Returns:
            str: The string identifier of the scheduling operation
        """
        return await self.__mgr.create_job_schedule(
            cls=cls,
            timestamp=timestamp,
            recur_interval=recur_interval,
            max_recurrences=max_recurrences,
            job_args=job_args,
            job_kwargs=job_kwargs,
            _invoker=self.__j,
        )

    def get_job_schedule_identifiers(self):
        """Return a tuple of all job schedule identifiers pointing to
        scheduling data.

        Returns:
            tuple: All job schedule identifiers.
        """

        return self.__mgr.get_job_schedule_identifiers()

    def job_schedule_has_failed(self, schedule_identifier: str):
        """Whether the job schedule operation with the specified schedule
        identifier failed.

        Args:
            schedule_identifier (str): A string identifier following this structure:
              'JOB_MANAGER_IDENTIFIER-TARGET_TIMESTAMP_IN_NS-SCHEDULING_TIMESTAMP_IN_NS'

        Raises:
            ValueError: Invalid schedule identifier.

        Returns:
            bool: True/False
        """
        return self.__mgr.job_schedule_has_failed(schedule_identifier)

    def has_job_schedule(self, schedule_identifier: str):
        """Whether the job schedule operation with the specified schedule
        identifier exists.

        Args:
            schedule_identifier (str): A string identifier following this structure:
              'JOB_MANAGER_IDENTIFIER-TARGET_TIMESTAMP_IN_NS-SCHEDULING_TIMESTAMP_IN_NS'

        Raises:
            ValueError: Invalid schedule identifier.

        Returns:
            bool: Whether the schedule identifier leads to existing scheduling data.
        """

        return self.__mgr.has_job_schedule(schedule_identifier)

    async def remove_job_schedule(
        self,
        schedule_identifier: str,
    ):
        """Remove a job schedule operation using the string identifier
        of the schedule operation.

        Args:
            schedule_identifier (str): A string identifier following
              this structure:
              'JOB_MANAGER_IDENTIFIER-TARGET_TIMESTAMP_IN_NS-SCHEDULING_TIMESTAMP_IN_NS'

        Raises:
            ValueError: Invalid schedule identifier.
            KeyError: No operation matching the given schedule identifier was found.
        """

        return self.__mgr.remove_job_schedule(schedule_identifier, _invoker=self.__j)

    def restart_job(
        self, job_proxy: JobProxy, stopping_timeout: Optional[float] = None
    ):
        """Restart the given job object. This provides a cleaner way
        to forcefully stop a job and restart it, or to wake it up from
        a stopped state.

        Args:
            job_proxy (JobProxy): The job object's proxy.
            stopping_timeout (Optional[float]): An optional timeout in seconds
              for the maximum time period
              for stopping the job while it is restarting. This overrides
              the global timeout of this `JobManager` if present.
        Returns:
            bool: Whether the operation was initiated by the job.
        """

        job = self.__mgr._get_job_from_proxy(job_proxy)

        if job is self.__j:
            job.RESTART()

        return self.__mgr.restart_job(
            job, stopping_timeout=stopping_timeout, _invoker=self.__j
        )

    def start_job(
        self,
        job_proxy: JobProxy,
    ):
        """Start the given job object, if is hasn't already started.

        Args:
            job_proxy (JobProxy): The job object's proxy.

        Returns:
            bool: Whether the operation was successful.
        """

        return self.__mgr.start_job(job_proxy, _invoker=self.__j)

    def stop_job(
        self,
        job_proxy: JobProxy,
        stopping_timeout: Optional[float] = None,
        force=False,
    ):
        """Stop the given job object.

        Args:
            job_proxy (JobProxy): The job object's proxy.
            force (bool): Whether to suspend all operations of the job forcefully.
            stopping_timeout (Optional[float]): An optional timeout in seconds for
              the maximum time period for stopping the job. This overrides the
              global timeout of this `JobManager` if present.

        Returns:
            bool: Whether the operation was successful.
        """
        job = self.__mgr._get_job_from_proxy(job_proxy)

        if job is self.__j:
            job.STOP(force=force)

        return self.__mgr.stop_job(
            job, stopping_timeout=stopping_timeout, force=force, _invoker=self.__j
        )

    def kill_job(self, job_proxy: JobProxy, stopping_timeout: Optional[float] = None):
        """Stops a job's current execution unconditionally and remove it from its
        `JobManager`. In order to check if a job was ended by killing it, one
        can call `.is_killed()`.

        Args:
            job_proxy (JobProxy): The job object's proxy.
            stopping_timeout (Optional[float]): An optional timeout in seconds
              for the maximum time period for stopping the job while it is being
              killed. This overrides the
              global timeout of this `JobManager` if present.

        Returns:
            bool: Whether the operation was initiated by the job.
        """
        job = self.__mgr._get_job_from_proxy(job_proxy)

        if job is self.__j:
            job.KILL()

        return self.__mgr.kill_job(
            job, stopping_timeout=stopping_timeout, _invoker=self.__j
        )

    def get_guarded_jobs(self):
        return tuple(self.__j._guarded_job_proxies_set)

    def guard_job(
        self,
        job_proxy: JobProxy,
    ):
        """Place a guard on the given job object, to prevent unintended state
        modifications by other jobs.

        Args:
            job_proxy (JobProxy): The job object's proxy.

        Raises:
            JobStateError: The given target job object is already being guarded by a job.
            JobStateError: The given target job object is already being guarded by the
            invoker job object.
        """
        return self.__mgr.guard_job(job_proxy, _invoker=self.__j)

    def unguard_job(
        self,
        job_proxy: JobProxy,
    ):
        """Remove the guard on the given job object, to prevent unintended state
        modifications by other jobs.

        Args:
            job_proxy (JobProxy): The job object's proxy.

        Raises:
            JobStateError: The given target job object is not being guarded by a job.
            JobStateError: The given target job object is already being guarded by
              the invoker job object.
        """

        return self.__mgr.unguard_job(job_proxy, _invoker=self.__j)

    def _eject(self):
        """
        Irreversible job death. Do not call this method without ensuring that
        a job is killed.
        """
        if not self.__j.alive():
            self.__mgr._remove_job(self.__j)
            self.__j._manager = None
            self.__j = None
            self.__mgr = None

    def _unguard(self):
        """
        Unguard the job of this job manager proxy.
        """
        if self.__j._is_being_guarded:
            guardian = self.__mgr._get_job_from_proxy(self.__j._guardian)
            self.__mgr.unguard_job(self.__j, _invoker=guardian)

    def find_job(
        self,
        *,
        identifier: Optional[str] = None,
        created_at: Optional[datetime.datetime] = None,
    ):
        """Find the first job that matches the given criteria specified as arguments,
        and return a proxy to it, otherwise return `None`.

        Args:

            identifier (Optional[str]): The exact identifier of the job to find. This
              argument overrides any other parameter below. Defaults to None.

            created_at (Optional[datetime.datetime]): The exact creation date of the
              job to find. Defaults to None.

        Raises:
            TypeError: One of the arguments must be specified.

        Returns:
            JobProxy: The proxy of the job object, if present.
        """
        return self.__mgr.find_job(
            identifier=identifier,
            created_at=created_at,
            _return_proxy=True,
            _invoker=self.__j,
        )

    def find_jobs(
        self,
        *,
        classes: Optional[
            Union[
                Type[EventJobBase],
                Type[IntervalJobBase],
                tuple[Union[Type[EventJobBase], Type[IntervalJobBase]]],
            ]
        ] = None,
        exact_class_match: bool = False,
        created_before: Optional[datetime.datetime] = None,
        created_after: Optional[datetime.datetime] = None,
        permission_level: Optional[int] = None,
        above_permission_level: Optional[int] = None,
        below_permission_level: Optional[int] = None,
        alive: Optional[bool] = None,
        is_starting: Optional[bool] = None,
        is_running: Optional[bool] = None,
        is_idling: Optional[bool] = None,
        is_awaiting: Optional[bool] = None,
        is_being_stopped: Optional[bool] = None,
        stopped: Optional[bool] = None,
        is_being_restarted: Optional[bool] = None,
        is_being_killed: Optional[bool] = None,
        is_being_completed: Optional[bool] = None,
    ):
        """Find jobs that match the given criteria specified as arguments,
        and return a tuple of proxy objects to them.

        Args:
            classes: (
                 Optional[
                    Union[
                        Type[EventJobBase],
                        Type[IntervalJobBase],
                        tuple[
                            Union[
                                Type[EventJobBase],
                                Type[IntervalJobBase]
                            ]
                        ]
                    ]
                ]
            ): The class(es) of the job objects to limit the job search to, excluding
              subclasses. Defaults to None.
            exact_class_match (bool): Whether an exact match is required for the
              classes in the previous parameter, or subclasses are allowed too.
              Defaults to False.

            created_before (Optional[datetime.datetime]): The lower age limit of the
              jobs to find. Defaults to None.
            created_after (Optional[datetime.datetime]): The upper age limit of the
              jobs to find. Defaults to None.
            permission_level (Optional[int]): The permission level of the jobs to
              find. Defaults to None.
            above_permission_level (Optional[int]): The lower permission level
              value of the jobs to find. Defaults to None.
            below_permission_level (Optional[int]): The upper permission level
              value of the jobs to find. Defaults to None.
            created_after (Optional[datetime.datetime]): The upper age limit
              of the jobs to find. Defaults to None.
            created_after (Optional[datetime.datetime]): The upper age limit
              of the jobs to find. Defaults to None.
            alive (Optional[bool]): A boolean that a job's state should match.
              Defaults to None.
            is_running (Optional[bool]): A boolean that a job's state should
              match. Defaults to None.
            is_idling (Optional[bool]): A boolean that a job's state should
              match. Defaults to None.
            is_awaiting (Optional[bool]): A boolean that a job's state should
              match. Defaults to None.
            is_being_stopped (Optional[bool]): A boolean that a job's state
              should match. Defaults to None.
            stopped (Optional[bool]): A boolean that a job's state should
              match. Defaults to None.
            is_being_restarted (Optional[bool]): A boolean that a job's
              state should match. Defaults to None.
            is_being_killed (Optional[bool]): A boolean that a job's
              state should match. Defaults to None.
            is_being_completed (Optional[bool]): A boolean that a job's state
              should match. Defaults to None.

        Returns:
            tuple: A tuple of the job object proxies that were found.
        """

        return self.__mgr.find_jobs(
            classes=classes,
            exact_class_match=exact_class_match,
            created_before=created_before,
            created_after=created_after,
            permission_level=permission_level,
            above_permission_level=above_permission_level,
            below_permission_level=below_permission_level,
            alive=alive,
            is_starting=is_starting,
            is_running=is_running,
            is_idling=is_idling,
            is_awaiting=is_awaiting,
            is_being_stopped=is_being_stopped,
            is_being_restarted=is_being_restarted,
            is_being_killed=is_being_killed,
            is_being_completed=is_being_completed,
            stopped=stopped,
            _return_proxy=True,
            _invoker=self.__j,
        )

    def wait_for_event(
        self,
        *event_types: Type[BaseEvent],
        check: Optional[Callable[[events.BaseEvent], bool]] = None,
        timeout: Optional[float] = None,
    ):
        """Wait for specific type of event to be dispatched
        and return it as an event object using the given coroutine.

        Args:
            *event_types (Type[events.BaseEvent]): The event type/types to wait for. If
              any of its/their instances is dispatched, that instance will be returned.
            check (Optional[Callable[[events.BaseEvent], bool]]): A callable obejct
              used to validate if a valid event that was recieved meets specific
              conditions. Defaults to None.
            timeout: (Optional[float]): An optional timeout value in seconds for
              the maximum waiting period.

        Raises:
            TimeoutError: The timeout value was exceeded.
            CancelledError: The future used to wait for an event was cancelled.

        Returns:
            Coroutine: A coroutine that evaluates to a valid `BaseEvent` event object.
        """

        return self.__mgr.wait_for_event(
            *event_types,
            check=check,
            timeout=timeout,
        )

    async def dispatch_event(self, event: events.BaseEvent):
        """Dispatch an instance of a `BaseEvent` subclass to all event job
        objects in this job manager that are listening for it.

        Args:
            event (BaseEvent): The event to be dispatched.

        Raises:
            JobPermissionError: Insufficient permissions.
        """

        event._dispatcher = self.__j._proxy
        return self.__mgr.dispatch_event(event, _invoker=self.__j)

    def has_job(self, job_proxy: JobProxy):
        """Whether a specific job object is currently in this
        job manager.

        Args:
            job_proxy (JobProxy): The target job's proxy.

        Returns:
            bool: True/False
        """
        job = self.__mgr._get_job_from_proxy(job_proxy)
        return self.__mgr.has_job(job)

    __contains__ = has_job

    def has_identifier(self, identifier: str):
        """Whether a job with the given identifier is contained in this job manager.

        Args:
            identifier (str): The job identifier.

        Returns:
            bool: True/False
        """
        return self.__mgr.has_identifier(identifier)
