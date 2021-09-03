"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file implements task classes for scheduling messaging events as tasks. 
"""

from typing import Any, Callable, Coroutine, Iterable, Optional, Sequence, Union

import io
import discord
from pgbot.tasks.core import IntervalTask
from pgbot.tasks.core import serializers
from pgbot import common

class MessageSend(IntervalTask):
    """A task class for sending a message into a
    discord text channel.
    """
    default_count = 1
    default_reconnect = False

    def __init__(self, channel: Union[int, discord.abc.Messageable, serializers.ChannelSerial], **kwargs):
        """Setup this task ojbect's namespace.

        Args:
            channel (Union[int, discord.abc.Messageable]):
                The channel/channel ID to message to.
            **kwargs:
                The keyword arguments to pass to the `.send()`
            coroutine method of the channel.
        """
        super().__init__()
        super().setup(channel=channel, kwargs=kwargs)

    async def before_run(self):
        if isinstance(self.data.channel, int):
            channel_id = self.data.channel
            self.data.channel = common.bot.get_channel(channel_id)
            if self.data.channel is None:
                self.data.channel = await common.bot.fetch_channel(channel_id)

        elif isinstance(self.data.channel, serializers.ChannelSerial):
            self.data.channel = await self.data.channel.deserialize()

        elif not isinstance(self.data.channel, discord.abc.Messageable):
            raise TypeError("no valid object passed for `.data` attribute")

        if "embed" in self.data.kwargs and isinstance(self.data.kwargs["embed"], dict):
            self.data.kwargs["embed"] = discord.Embed.from_dict(self.data.kwargs["embed"])

        if "embeds" in self.data.kwargs and all(isinstance(embed, dict) for embed in self.data.kwargs["embeds"]):
            self.data.kwargs["embeds"] = [discord.Embed.from_dict(embed_dict) for embed_dict in self.data.kwargs["embeds"]]

        if "file" in self.data.kwargs:
            if isinstance(self.data.kwargs["file"], bytes):
                self.data.kwargs["file"] = discord.File(io.BytesIO(self.data.kwargs["file"]))

            elif isinstance(self.data.kwargs["file"], serializers.FileSerial):
                self.data.kwargs["file"] = await self.data.kwargs["file"].deserialize()

            elif isinstance(self.data.kwargs["file"], dict):
                file_dict = self.data.kwargs["file"]
                self.data.kwargs["file"] = discord.File(fp=io.BytesIO(file_dict["fp"]), filename=file_dict["filename"], spoiler=file_dict["spoiler"])

            if not self.data.kwargs["file"]:
                del self.data.kwargs["file"]
        
        if "files" in self.data.kwargs:
            for file_dict in self.data.kwargs["files"]:
                if isinstance(file_dict, dict):
                    self.data.kwargs["files"] = [discord.File(fp=io.BytesIO(file_dict["fp"]), filename=file_dict["filename"], spoiler=file_dict["spoiler"]) for file_dict in self.data.kwargs["files"] if isinstance(file_dict, dict)]
            
            if not self.data.kwargs["files"]:
                del self.data.kwargs["files"]

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

    def __init__(self, channel: Union[int, discord.abc.Messageable], message: Union[int, discord.Message], **kwargs):
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
        super().setup(channel=channel, message=message, kwargs=kwargs)

    async def before_run(self):
        if isinstance(self.data.channel, int):
            channel_id = self.data.channel
            self.data.channel = common.bot.get_channel(channel_id)
            if self.data.channel is None:
                self.data.channel = await common.bot.fetch_channel(channel_id)
        elif not isinstance(self.data.channel, discord.abc.Messageable):
            raise TypeError("Invalid object for `.data.channel` attribute")
        
        if isinstance(self.data.message, int):
            message_id = self.data.message
            self.data.message = await self.data.channel.fetch_message(message_id)

        elif not isinstance(self.data.message, discord.Message):
            raise TypeError("Invalid object for `.data.message` attribute")

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
        channel: Union[int, discord.abc.Messageable],
        message: Union[int, discord.Message],
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
        super().__init__(channel=channel, message=message)
        super().setup(emoji=emoji)

    async def run(self):
        self.data.message.add_reaction(self.data.emoji)


class ReactionRemove(_MessageModify):
    """Removes a given reaction from a message."""

    def __init__(
        self,
        channel: Union[int, discord.abc.Messageable],
        message: Union[int, discord.Message],
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
        super().__init__(channel=channel, message=message)
        super().setup(emoji=emoji, member=member)

    async def run(self):
        self.data.message.remove_reaction(self.data.emoji, self.data.member)


class ReactionClearEmoji(_MessageModify):
    """Clears a set of reactions from a message."""

    def __init__(
        self,
        channel: Union[int, discord.abc.Messageable],
        message: Union[int, discord.Message],
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
        super().__init__(channel=channel, message=message)
        super().setup(emoji=emoji)

    async def run(self):
        self.data.message.clear_reaction(self.data.emoji)


class ReactionClear(_MessageModify):
    """Clears all reactions from a message."""

    async def run(self):
        self.data.message.clear_reactions()
