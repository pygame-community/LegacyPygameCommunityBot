"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file implements task classes for scheduling messaging events as tasks. 
"""

from __future__ import annotations
from typing import Any, Callable, Coroutine, Iterable, Optional, Sequence, Union
import io
import discord
from pgbot.tasks.core import IntervalTask
from pgbot.tasks.core import serializers as serials
from pgbot.tasks.core.base_tasks import chain_to_method
from pgbot.utils import embed_utils
from pgbot import common

NoneType = type(None)
client = common.bot

class MessageSend(IntervalTask):
    """A task class for sending a message into a
    discord text channel.
    """

    default_count = 1
    default_reconnect = False

    def __init__(
        self,
        channel: Union[int, discord.abc.Messageable, serials.ChannelSerial],
        content: Optional[str] = None,
        tts: bool = False,
        embed: Union[discord.Embed, serials.EmbedSerial, dict] = None,
        file: Union[discord.File, serials.FileSerial] = None,
        files: list[Union[discord.File, serials.FileSerial]] = None,
        delete_after: Optional[float] = None,
        nonce: Optional[int] = None,
        allowed_mentions: Optional[
            discord.AllowedMentions,
            serials.AllowedMentionsSerial,
        ] = None,
        reference: Union[
            discord.Message,
            discord.MessageReference,
            serials.MessageSerial,
            serials.MessageReferenceSerial,
        ] = None,
        mention_author: Optional[bool] = None,
    ):
        """Setup this task ojbect's namespace.

        Args:
            channel (Union[int, discord.abc.Messageable]):
                The channel/channel ID to message to.
            **kwargs:
                The keyword arguments to pass to the `.send()`
            coroutine method of the channel.
        """
        super().__init__()
        self.DATA.channel = channel
        self.DATA.kwargs = dict(
            content=content,
            tts=tts,
            embed=embed,
            file=file,
            files=files,
            delete_after=delete_after,
            nonce=nonce,
            allowed_mentions=allowed_mentions,
            reference=reference,
            mention_author=mention_author,
        )

    async def on_init(self):
        if not isinstance(self.DATA.channel, discord.abc.Messageable):
            if isinstance(self.DATA.channel, int):
                channel_id = self.DATA.channel
                self.DATA.channel = client.get_channel(channel_id)
                if self.DATA.channel is None:
                    self.DATA.channel = await client.fetch_channel(channel_id)
            elif isinstance(self.DATA.channel, serials.ChannelSerial):
                self.DATA.channel = await self.DATA.channel.reconstructed(True)
            else:
                raise TypeError("Invalid type for argument 'channel'")

        if not isinstance(self.DATA.kwargs["embed"], (discord.Embed, NoneType)):
            if isinstance(self.DATA.kwargs["embed"], dict):
                if embed_utils.validate_embed_dict(self.DATA.kwargs["embed"]):
                    self.DATA.kwargs["embed"] = discord.Embed.from_dict(
                        self.DATA.kwargs["embed"]
                    )
                else:
                    raise ValueError("Invalid embed dictionary structure")
            elif isinstance(self.DATA.kwargs["embed"], serials.EmbedSerial):
                self.DATA.kwargs["embed"] = discord.Embed.from_dict(
                    self.DATA.kwargs["embed"]
                )

        if not isinstance(self.DATA.kwargs["file"], (discord.File, NoneType)):
            if isinstance(self.DATA.kwargs["file"], bytes):
                self.DATA.kwargs["file"] = discord.File(
                    io.BytesIO(self.DATA.kwargs["file"])
                )

            elif isinstance(self.DATA.kwargs["file"], serials.FileSerial):
                self.DATA.kwargs["file"] = await self.DATA.kwargs["file"].reconstructed()

            elif isinstance(self.DATA.kwargs["file"], dict):
                file_dict = self.DATA.kwargs["file"]
                self.DATA.kwargs["file"] = discord.File(
                    fp=io.BytesIO(file_dict["fp"]),
                    filename=file_dict["filename"],
                    spoiler=file_dict["spoiler"],
                )

        if self.DATA.kwargs["files"] is not None:
            file_list = []
            for i, obj in enumerate(self.DATA.kwargs["files"]):
                if isinstance(obj, discord.File):
                    file_list.append(obj)
                elif isinstance(obj, serials.FileSerial):
                    file_list.append(obj.reconstructed())
                else:
                    raise TypeError(f"Invalid object at index {i} in iterable given as 'files' argument")                    

        if not isinstance(
            self.DATA.kwargs["allowed_mentions"], (discord.AllowedMentions, NoneType)
        ):  
            if isinstance(self.DATA.kwargs["allowed_mentions"], serials.AllowedMentionsSerial):
                self.DATA.kwargs["allowed_mentions"] = await self.DATA.kwargs["allowed_mentions"].reconstructed()
            else:
                raise TypeError("Invalid type for argument 'allowed_mentions'")

        if not isinstance(
            self.DATA.kwargs["reference"],
            (discord.Message, discord.MessageReference, NoneType),
        ):
            if isinstance(self.DATA.kwargs["reference"], (serials.MessageSerial, serials.MessageReferenceSerial)):
                if self.DATA.kwargs["reference"].IS_ASYNC:
                    self.DATA.kwargs["reference"] = await self.DATA.kwargs[
                        "reference"
                    ].reconstructed(True)
                else:
                    self.DATA.kwargs["reference"] = self.DATA.kwargs[
                        "reference"
                    ].reconstructed()
            else:
                raise TypeError("Invalid type for argument 'reference'")


        self.DATA.OUTPUT.message = None

    async def on_run(self):
        self.DATA.OUTPUT.message = await self.DATA.channel.send(**self.DATA.kwargs)

    async def on_post_run(self):
        self.END()


class _MessageModify(IntervalTask):
    """A intermediary task class for modifying a message in a
    Discord text channel. Does not do anything on its own.
    """

    default_count = 1
    default_reconnect = False

    def __init__(
        self,
        channel: Union[int, discord.abc.Messageable, serials.ChannelSerial, NoneType],
        message: Union[int, discord.Message, serials.MessageSerial],
    ):
        """Create a bot task instance.

        Args:
            channel (Union[int, discord.abc.Messageable, serials.ChannelSerial]): The target channel.
            message (Union[int, discord.Message, serials.MessageSerial]): [description]
        """
        super().__init__()
        self.DATA.channel = channel
        self.DATA.message = message

    async def on_init(self):
        if not isinstance(self.DATA.channel, discord.abc.Messageable):
            if isinstance(self.DATA.channel, int):
                channel_id = self.DATA.channel
                self.DATA.channel = client.get_channel(channel_id)
                if self.DATA.channel is None:
                    self.DATA.channel = await client.fetch_channel(channel_id)
            elif isinstance(self.DATA.channel, serials.ChannelSerial):
                self.DATA.channel = await self.DATA.channel.reconstructed(True)
            elif self.DATA.channel is None:
                if not isinstance(self.DATA.message, (discord.Message, serials.MessageSerial)):
                    raise TypeError("argument 'channel' cannot be None when 'message' is an integer ID")
            else:
                raise TypeError("Invalid type for argument 'channel'")

        if not isinstance(self.DATA.message, discord.Message):
            if isinstance(self.DATA.message, int):
                channel = client.get_channel(self.DATA.channel.id)
                if channel is None:
                    channel = await client.fetch_channel(self.DATA.channel.id)
            elif isinstance(self.DATA.message, serials.MessageSerial):
                self.DATA.message = await self.DATA.message.reconstructed(True)
            else:
                raise TypeError("Invalid type for argument 'message'")

    async def on_post_run(self):
        self.END()


class MessageEdit(_MessageModify):
    """A task class for editing a message in a
    Discord text channel.
    """

    default_count = 1

    def __init__(
        self,
        channel: Union[int, discord.abc.Messageable, serials.ChannelSerial, NoneType],
        message: Union[int, discord.Message, serials.MessageSerial],
        content: Optional[str] = None,
        embed: Union[discord.Embed, serials.EmbedSerial, dict] = None,
        delete_after: Optional[float] = None,
        allowed_mentions: Optional[
            discord.AllowedMentions,
            serials.AllowedMentionsSerial,
        ] = None,
    ):
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
        super().__init__(channel=channel, message=message)
        self.DATA.kwargs = dict(
                content=content,
                embed=embed,
                delete_after=delete_after,
                allowed_mentions=allowed_mentions,
        )

    @chain_to_method(_MessageModify, name="on_init", mode="after")
    async def on_init(self):
        if not isinstance(self.DATA.kwargs["embed"], (discord.Embed, NoneType)):
            if isinstance(self.DATA.kwargs["embed"], dict):
                if embed_utils.validate_embed_dict(self.DATA.kwargs["embed"]):
                    self.DATA.kwargs["embed"] = discord.Embed.from_dict(
                        self.DATA.kwargs["embed"]
                    )
                else:
                    raise ValueError("Invalid embed dictionary structure")
            elif isinstance(self.DATA.kwargs["embed"], serials.EmbedSerial):
                self.DATA.kwargs["embed"] = discord.Embed.from_dict(
                    self.DATA.kwargs["embed"]
                )

        if not isinstance(
            self.DATA.kwargs["allowed_mentions"], (discord.AllowedMentions, NoneType)
        ):  
            if isinstance(self.DATA.kwargs["allowed_mentions"], serials.AllowedMentionsSerial):
                self.DATA.kwargs["allowed_mentions"] = await self.DATA.kwargs["allowed_mentions"].reconstructed()
            else:
                raise TypeError("Invalid type for argument 'allowed_mentions'")

    async def on_run(self):
        await self.DATA.message.edit(**self.DATA.kwargs)

    async def on_post_run(self):
        self.END()


class MessageDelete(_MessageModify):
    """A task class for deleting a message in a
    Discord text channel.
    """

    default_count = 1

    def __init__(
        self,
        channel: Union[int, discord.abc.Messageable, serials.ChannelSerial, NoneType],
        message: Union[int, discord.Message, serials.MessageSerial],
        delay: Optional[float] = None,
    ):
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
        super().__init__(channel=channel, message=message)
        self.DATA.kwargs = dict(delay=delay)

    @chain_to_method(_MessageModify, name="on_init", mode="after")
    async def on_init(self):
        if not isinstance(self.DATA.kwargs["delay"], (int, float)):
            raise TypeError("Invalid type given for argument 'delay'")
        
        self.DATA.kwargs["delay"] = float(self.DATA.kwargs["delay"])

    async def on_run(self):
        await self.DATA.message.delete(**self.DATA.kwargs)

    async def on_post_run(self):
        self.END()


class ReactionAdd(_MessageModify):
    """Adds a given reaction to a message."""

    def __init__(
        self,
        channel: Union[int, discord.abc.Messageable, serials.ChannelSerial, NoneType],
        message: Union[int, discord.Message, serials.MessageSerial],
        emoji: Union[int, discord.Reaction, discord.Emoji, serials.EmojiSerial, discord.PartialEmoji, serials.PartialEmojiSerial, str],
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
        self.DATA.emoji = emoji

    @chain_to_method(_MessageModify, name="on_init", mode="after")
    async def on_init(self):
        if not isinstance(self.DATA.emoji, (discord.Reaction, discord.Emoji, discord.PartialEmoji, str)):
            if isinstance(self.DATA.emoji, int):
                emoji = client.get_emoji(self.DATA.emoji)
                if emoji is None:
                    raise ValueError("invalid integer ID for 'emoji' argument")
                self.DATA.emoji = emoji
            elif isinstance(self.DATA.emoji, (serials.EmojiSerial, serials.PartialEmojiSerial)):
                self.DATA.emoji = self.DATA.emoji.reconstructed()
            else:
                raise TypeError("Invalid type for argument 'emoji'")

    async def on_run(self):
        await self.DATA.message.add_reaction(self.DATA.emoji)


class ReactionRemove(_MessageModify):
    """Removes a given reaction from a message."""

    def __init__(
        self,
        channel: Union[int, discord.abc.Messageable, serials.ChannelSerial, NoneType],
        message: Union[int, discord.Message, serials.MessageSerial],
        emoji: Union[int, discord.Reaction, discord.Emoji, serials.EmojiSerial, discord.PartialEmoji, serials.PartialEmojiSerial, str],
        member: Union[discord.abc.Snowflake, discord.Member, serials.MemberSerial],
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
        self.DATA.emoji = emoji
        self.DATA.member = member


    @chain_to_method(_MessageModify, name="on_init", mode="after")
    async def on_init(self):
        if not isinstance(self.DATA.emoji, (discord.Reaction, discord.Emoji, discord.PartialEmoji, str)):
            if isinstance(self.DATA.emoji, int):
                emoji = client.get_emoji(self.DATA.emoji)
                if emoji is None:
                    raise ValueError("invalid integer ID for 'emoji' argument")
                self.DATA.emoji = emoji
            elif isinstance(self.DATA.emoji, (serials.EmojiSerial, serials.PartialEmojiSerial)):
                self.DATA.emoji = self.DATA.emoji.reconstructed()
            else:
                raise TypeError("Invalid type for argument 'emoji'")

        if not isinstance(self.DATA.member, (discord.abc.Snowflake, discord.Member)):
            if isinstance(self.DATA.member, serials.MemberSerial):
                self.DATA.member = await self.DATA.member.reconstructed()
            else:
                raise TypeError("Invalid type for argument 'member'")


    async def on_run(self):
        await self.DATA.message.remove_reaction(self.DATA.emoji, self.DATA.member)


class ReactionClearEmoji(_MessageModify):
    """Clears a set of reactions from a message."""

    def __init__(
        self,
        channel: Union[int, discord.abc.Messageable, serials.ChannelSerial, NoneType],
        message: Union[int, discord.Message],
        emoji: Union[int, discord.Reaction, discord.Emoji, serials.EmojiSerial, discord.PartialEmoji, serials.PartialEmojiSerial, str],
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
        self.DATA.emoji = emoji

    @chain_to_method(_MessageModify, name="on_init", mode="after")
    async def on_init(self):
        if not isinstance(self.DATA.emoji, (discord.Reaction, discord.Emoji, discord.PartialEmoji, str)):
            if isinstance(self.DATA.emoji, int):
                emoji = client.get_emoji(self.DATA.emoji)
                if emoji is None:
                    raise ValueError("invalid integer ID for 'emoji' argument")
                self.DATA.emoji = emoji
            elif isinstance(self.DATA.emoji, (serials.EmojiSerial, serials.PartialEmojiSerial)):
                self.DATA.emoji = self.DATA.emoji.reconstructed()
            else:
                raise TypeError("Invalid type for argument 'emoji'")

    async def on_run(self):
        await self.DATA.message.clear_reaction(self.DATA.emoji)


class ReactionClear(_MessageModify):
    """Clears all reactions from a message."""

    async def on_run(self):
        await self.DATA.message.clear_reactions()
