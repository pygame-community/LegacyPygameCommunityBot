from typing import Any, Callable, Coroutine, Iterable, Optional, Sequence, Union

import discord
from pgbot.tasks.core import SingletonTask
from pgbot import common


class SendMessage(SingletonTask):
    """A task class for sending a message into a
    discord text channel.
    """

    default_reconnect = False

    def __init__(self, channel_id: Optional[int] = None, **kwargs):
        super().__init__()
        if channel_id:
            super().setup(channel_id=channel_id, kwargs=kwargs)

    def setup(self, channel_id: int, **kwargs):
        """Setup this task ojbect's namespace.

        Args:
            channel_id (int): The ID of a channel to message to.
            **kwargs: the keyword arguments to pass to the `.send()`
            coroutine method of the channel.

        Returns:
            This task object.
        """
        return super().setup(channel_id=channel_id, kwargs=kwargs)

    async def before_run(self):
        self.data.channel = common.bot.get_channel(self.data.channel_id)
        if self.data.channel is None:
            self.data.channel = await common.bot.fetch_channel(self.data.channel_id)
        self.data.message = None

    async def run(self):
        self.data.message = await self.data.channel.send(**self.data.kwargs)

    async def after_run(self):
        self.kill()


class EditMessage(SingletonTask):
    """A task class for editing a message in a
    Discord text channel.
    """

    default_reconnect = False

    def __init__(self, channel_id: int, message_id: int, **kwargs):
        super().__init__()
        super().setup(channel_id=channel_id, message_id=message_id, kwargs=kwargs)

    def setup(self, channel_id: int, message_id: int, **kwargs):
        """Setup this task ojbect's namespace.

        Args:
            channel_id (int):
                The ID of a channel to get
                a message from.
            message_id (int): The ID of a message to edit.
            **kwargs:
                The keyword arguments to pass to the `.edit()`
                coroutine method of the message.

        Returns:
            This task object.
        """
        super().setup(channel_id=channel_id, message_id=message_id, kwargs=kwargs)

    async def before_run(self):
        channel: discord.abc.Messageable = common.bot.get_channel(self.data.channel_id)
        if channel is None:
            channel = await common.bot.fetch_channel(self.data.channel_id)
        self.data.channel = channel
        self.data.message = await channel.fetch_message(self.data.message_id)

    async def run(self):
        await self.data.message.edit(**self.data.kwargs)

    async def after_run(self):
        self.kill()


class DeleteMessage(EditMessage):
    """A task class for deleting a message in a
    Discord text channel.
    """

    async def run(self):
        await self.data.message.delete(**self.data.kwargs)

    async def after_run(self):
        self.kill()
