from typing import Any, Callable, Coroutine, Iterable, Optional, Sequence, Union

import discord
from pgbot.tasks.core import IntervalTask
from pgbot import common

__all__ = []


class MessageSend(IntervalTask):
    """A task class for sending a message into a
    discord text channel.
    """
    default_count = 1
    default_reconnect = False

    def __init__(self, channel_id: int, **kwargs):
        """Setup this task ojbect's namespace.

        Args:
            channel_id (int): The ID of a channel to message to.
            **kwargs: the keyword arguments to pass to the `.send()`
            coroutine method of the channel.
        """
        super().__init__()
        super().setup(channel_id=channel_id, kwargs=kwargs)

    async def before_run(self):
        self.data.channel = common.bot.get_channel(self.data.channel_id)
        if self.data.channel is None:
            self.data.channel = await common.bot.fetch_channel(self.data.channel_id)
        self.data.message = None

    async def run(self):
        self.data.message = await self.data.channel.send(**self.data.kwargs)

    async def after_run(self):
        self.kill()


class _MessageModify(IntervalTask):
    """A task class for modifying a message in a
    Discord text channel.
    """
    default_count = 1
    default_reconnect = False

    def __init__(self, channel_id: int, message_id: int, **kwargs):
        """Setup this task ojbect.

        Args:
            channel_id (int):
                The ID of a channel to get
                a message from.
            message_id (int): The ID of a message.
            **kwargs:
                The keyword arguments to pass to the
                coroutine methods of the message.
        """
        super().__init__()
        super().setup(channel_id=channel_id, message_id=message_id, kwargs=kwargs)

    async def before_run(self):
        channel: discord.abc.Messageable = common.bot.get_channel(self.data.channel_id)
        if channel is None:
            channel = await common.bot.fetch_channel(self.data.channel_id)
        self.data.message = await channel.fetch_message(self.data.message_id)

    async def after_run(self):
        self.kill()


class MessageEdit(_MessageModify):
    """A task class for editing a message in a
    Discord text channel.
    """

    async def run(self):
        await self.data.message.edit(**self.data.kwargs)


class MessageDelete(_MessageModify):
    """A task class for deleting a message in a
    Discord text channel.
    """

    async def run(self):
        await self.data.message.delete(**self.data.kwargs)


class ReactionAdd(_MessageModify):
    """Adds a given reaction to a message."""

    def __init__(
        self,
        channel_id: int,
        message_id: int,
        emoji: Union[discord.Emoji, discord.Reaction, discord.PartialEmoji, str],
    ):
        """Setup this task ojbect.

        Args:
            channel_id (int):
                The ID of a channel to get
                a message from.
            message_id (int): The ID of a message.
            emoji: (
                Union[
                    discord.Emoji,
                    discord.Reaction,
                    discord.PartialEmoji,
                    str
                ]
            ):
                The emoji to react with.
        """
        super().__init__(channel_id=channel_id, message_id=message_id)
        super().setup(emoji=emoji)

    async def run(self):
        self.data.message.add_reaction(self.data.emoji)


class ReactionRemove(_MessageModify):
    """Removes a given reaction from a message."""

    def __init__(
        self,
        channel_id: int,
        message_id: int,
        emoji: Union[discord.Emoji, discord.Reaction, discord.PartialEmoji, str],
        member: discord.abc.Snowflake,
    ):
        """Setup this task ojbect.

        Args:
            channel_id (int):
                The ID of a channel to get
                a message from.
            message_id (int): The ID of a message.
            emoji: (
                Union[
                    discord.Emoji,
                    discord.Reaction,
                    discord.PartialEmoji,
                    str
                ]
            ):
                The emoji to remove.
            member: (discord.abc.Snowflake):
                The member whose reaction should be removed.
        """
        super().__init__(channel_id=channel_id, message_id=message_id)
        super().setup(emoji=emoji, member=member)

    async def run(self):
        self.data.message.remove_reaction(self.data.emoji, self.data.member)


class ReactionClearEmoji(_MessageModify):
    """Clears a set of reactions from a message."""

    def __init__(
        self,
        channel_id: int,
        message_id: int,
        emoji: Union[discord.Emoji, discord.Reaction, discord.PartialEmoji, str],
    ):
        """Setup this task ojbect.

        Args:
            channel_id (int):
                The ID of a channel to get
                a message from.
            message_id (int): The ID of a message to edit.
            emoji: (
                Union[
                    discord.Emoji,
                    discord.Reaction,
                    discord.PartialEmoji,
                    str
                ]
            ):
                The emoji to clear.
        """
        super().__init__(channel_id=channel_id, message_id=message_id)
        super().setup(emoji=emoji)

    async def run(self):
        self.data.message.clear_reaction(self.data.emoji)


class ReactionClear(_MessageModify):
    """Clears all reactions from a message."""

    async def run(self):
        self.data.message.clear_reactions()


for task_class in (
    MessageSend,
    MessageEdit,
    MessageDelete,
    ReactionAdd,
    ReactionRemove,
    ReactionClearEmoji,
    ReactionClear,
):
    common.task_class_map[task_class.__name__] = task_class
    __all__.append(task_class.__name__)
