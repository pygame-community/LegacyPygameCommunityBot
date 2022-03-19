"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file implements job classes for scheduling Discord communication methods as jobs. 
"""

from __future__ import annotations
from typing import Optional, Union
import io
import discord
from pgbot.jobs import IntervalJobBase, JOB_PERMISSION_LEVELS
from pgbot.utils import embed_utils
from pgbot import common
from pgbot import serializers

NoneType = type(None)
client = common.bot


class MessageSend(IntervalJobBase, permission_level=JOB_PERMISSION_LEVELS.LOWEST):
    """A job class for sending a message into a
    discord text channel.
    """

    OUTPUT_FIELDS = frozenset(("message",))

    DEFAULT_COUNT = 1
    DEFAULT_RECONNECT = False

    def __init__(
        self,
        channel: Union[int, discord.abc.Messageable, serializers.ChannelSerializer],
        content: Optional[str] = None,
        tts: bool = False,
        embed: Union[discord.Embed, serializers.EmbedSerializer, dict] = None,
        file: Union[discord.File, serializers.FileSerializer] = None,
        files: list[Union[discord.File, serializers.FileSerializer]] = None,
        delete_after: Optional[float] = None,
        nonce: Optional[int] = None,
        allowed_mentions: Optional[
            Union[discord.AllowedMentions, serializers.AllowedMentionsSerializer]
        ] = None,
        reference: Union[
            discord.Message,
            discord.MessageReference,
            serializers.MessageSerializer,
            serializers.MessageReferenceSerializer,
        ] = None,
        mention_author: Optional[bool] = None,
        kill_if_failed: bool = True,
    ):
        """Setup this job ojbect's namespace.

        Args:
            channel (Union[int, discord.abc.Messageable]):
                The channel/channel ID to message to.
            **kwargs:
                The keyword arguments to pass to the `.send()`
            coroutine method of the channel.
        """
        super().__init__()
        self.data.channel = channel
        self.data.kwargs = dict(
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

        self.data.kill_if_failed = not not kill_if_failed

    async def on_init(self):
        if not isinstance(self.data.channel, discord.abc.Messageable):
            if isinstance(self.data.channel, int):
                channel_id = self.data.channel
                self.data.channel = client.get_channel(channel_id)
                if self.data.channel is None:
                    self.data.channel = await client.fetch_channel(channel_id)
            elif isinstance(self.data.channel, serializers.ChannelSerializer):
                self.data.channel = await self.data.channel.deserialized_async()
            else:
                raise TypeError("Invalid type for argument 'channel'")

        if not isinstance(self.data.kwargs["embed"], (discord.Embed, NoneType)):
            if isinstance(self.data.kwargs["embed"], dict):
                if embed_utils.validate_embed_dict(self.data.kwargs["embed"]):
                    self.data.kwargs["embed"] = discord.Embed.from_dict(
                        self.data.kwargs["embed"]
                    )
                else:
                    raise ValueError("Invalid embed dictionary structure")
            elif isinstance(self.data.kwargs["embed"], serializers.EmbedSerializer):
                self.data.kwargs["embed"] = discord.Embed.from_dict(
                    self.data.kwargs["embed"].deserialized()
                )

        if not isinstance(self.data.kwargs["file"], (discord.File, NoneType)):
            if isinstance(self.data.kwargs["file"], bytes):
                self.data.kwargs["file"] = discord.File(
                    io.BytesIO(self.data.kwargs["file"])
                )

            elif isinstance(self.data.kwargs["file"], serializers.FileSerializer):
                self.data.kwargs["file"] = self.data.kwargs["file"].deserialized()

            elif isinstance(self.data.kwargs["file"], dict):
                file_dict = self.data.kwargs["file"]
                self.data.kwargs["file"] = discord.File(
                    fp=io.BytesIO(file_dict["fp"]),
                    filename=file_dict["filename"],
                    spoiler=file_dict["spoiler"],
                )

        if self.data.kwargs["files"] is not None:
            file_list = []
            for i, obj in enumerate(self.data.kwargs["files"]):
                if isinstance(obj, discord.File):
                    file_list.append(obj)
                elif isinstance(obj, serializers.FileSerializer):
                    file_list.append(obj.deserialized())
                else:
                    raise TypeError(
                        f"Invalid object at index {i} in iterable given as 'files' argument"
                    )

        if not isinstance(
            self.data.kwargs["allowed_mentions"], (discord.AllowedMentions, NoneType)
        ):
            if isinstance(
                self.data.kwargs["allowed_mentions"],
                serializers.AllowedMentionsSerializer,
            ):
                self.data.kwargs["allowed_mentions"] = await self.data.kwargs[
                    "allowed_mentions"
                ].deserialized_async()
            else:
                raise TypeError("Invalid type for argument 'allowed_mentions'")

        if not isinstance(
            self.data.kwargs["reference"],
            (discord.Message, discord.MessageReference, NoneType),
        ):
            if isinstance(
                self.data.kwargs["reference"],
                (serializers.MessageSerializer, serializers.MessageReferenceSerializer),
            ):
                if self.data.kwargs["reference"].IS_ASYNC:
                    self.data.kwargs["reference"] = await self.data.kwargs[
                        "reference"
                    ].deserialized_async()
                else:
                    self.data.kwargs["reference"] = self.data.kwargs[
                        "reference"
                    ].deserialized()
            else:
                raise TypeError("Invalid type for argument 'reference'")

    async def on_run(self):
        msg = await self.data.channel.send(**self.data.kwargs)
        self.set_output_field("message", msg)

    async def on_stop(self, reason, by_force):
        if self.failed():
            if self.data.kill_if_failed:
                self.KILL()
        else:
            self.COMPLETE()


class _MessageModify(IntervalJobBase, permission_level=JOB_PERMISSION_LEVELS.LOWEST):
    """A intermediary job class for modifying a message in a
    Discord text channel. Does not do anything on its own.
    """

    DEFAULT_COUNT = 1
    DEFAULT_RECONNECT = False

    def __init__(
        self,
        channel: Union[
            int, discord.abc.Messageable, serializers.ChannelSerializer, NoneType
        ],
        message: Union[int, discord.Message, serializers.MessageSerializer],
        kill_if_failed: bool = True,
    ):
        """Create a bot job instance.

        Args:
            channel (Union[int, discord.abc.Messageable, serializers.ChannelSerializer]): The target channel.
            message (Union[int, discord.Message, serializers.MessageSerializer]): [description]
        """
        super().__init__()
        self.data.channel = channel
        self.data.message = message
        self.data.kill_if_failed = not not kill_if_failed

    async def on_init(self):
        if not isinstance(self.data.channel, discord.abc.Messageable):
            if isinstance(self.data.channel, int):
                channel_id = self.data.channel
                self.data.channel = client.get_channel(channel_id)
                if self.data.channel is None:
                    self.data.channel = await client.fetch_channel(channel_id)
            elif isinstance(self.data.channel, serializers.ChannelSerializer):
                self.data.channel = await self.data.channel.deserialized_async()
            elif self.data.channel is None:
                if not isinstance(
                    self.data.message, (discord.Message, serializers.MessageSerializer)
                ):
                    raise TypeError(
                        "argument 'channel' cannot be None when 'message' is an integer ID"
                    )
            else:
                raise TypeError("Invalid type for argument 'channel'")

        if not isinstance(self.data.message, discord.Message):
            if isinstance(self.data.message, int):
                channel = client.get_channel(self.data.channel.id)
                if channel is None:
                    channel = await client.fetch_channel(self.data.channel.id)
            elif isinstance(self.data.message, serializers.MessageSerializer):
                self.data.message = await self.data.message.deserialized_async()
            else:
                raise TypeError("Invalid type for argument 'message'")

    async def on_stop(self, reason, by_force):
        if self.failed():
            if self.data.kill_if_failed:
                self.KILL()
        else:
            self.COMPLETE()


class MessageEdit(_MessageModify):
    """A job class for editing a message in a
    Discord text channel.
    """

    def __init__(
        self,
        channel: Union[
            int, discord.abc.Messageable, serializers.ChannelSerializer, NoneType
        ],
        message: Union[int, discord.Message, serializers.MessageSerializer],
        content: Optional[str] = None,
        embed: Union[discord.Embed, serializers.EmbedSerializer, dict] = None,
        delete_after: Optional[float] = None,
        allowed_mentions: Optional[
            Union[discord.AllowedMentions, serializers.AllowedMentionsSerializer]
        ] = None,
        **kwargs,
    ):
        """Setup this job ojbect.

        Args:
            channel_id (int):
                The ID of a channel to get
                a message from.
            message_id (int): The ID of a message.
            **kwargs:
                The keyword arguments to pass to the
                coroutine methods of the message.
        """
        super().__init__(channel=channel, message=message, **kwargs)
        self.data.kwargs = dict(
            content=content,
            embed=embed,
            delete_after=delete_after,
            allowed_mentions=allowed_mentions,
        )

    async def on_init(self):
        await super().on_init()
        if not isinstance(self.data.kwargs["embed"], (discord.Embed, NoneType)):
            if isinstance(self.data.kwargs["embed"], dict):
                if embed_utils.validate_embed_dict(self.data.kwargs["embed"]):
                    self.data.kwargs["embed"] = discord.Embed.from_dict(
                        self.data.kwargs["embed"]
                    )
                else:
                    raise ValueError("Invalid embed dictionary structure")
            elif isinstance(self.data.kwargs["embed"], serializers.EmbedSerializer):
                self.data.kwargs["embed"] = discord.Embed.from_dict(
                    self.data.kwargs["embed"].deserialized()
                )

        if not isinstance(
            self.data.kwargs["allowed_mentions"], (discord.AllowedMentions, NoneType)
        ):
            if isinstance(
                self.data.kwargs["allowed_mentions"],
                serializers.AllowedMentionsSerializer,
            ):
                self.data.kwargs["allowed_mentions"] = await self.data.kwargs[
                    "allowed_mentions"
                ].deserialized_async()
            else:
                raise TypeError("Invalid type for argument 'allowed_mentions'")

    async def on_run(self):
        await self.data.message.edit(**self.data.kwargs)


class MessageDelete(_MessageModify):
    """A job class for deleting a message in a
    Discord text channel.
    """

    def __init__(
        self,
        channel: Union[
            int, discord.abc.Messageable, serializers.ChannelSerializer, NoneType
        ],
        message: Union[int, discord.Message, serializers.MessageSerializer],
        delay: Optional[float] = None,
        **kwargs,
    ):
        """Setup this job ojbect.

        Args:
            channel_id (int): The ID of a channel to get a message from.
            message_id (int): The ID of a message.
            **kwargs:
                The keyword arguments to pass to the
                coroutine methods of the message.
        """
        super().__init__(channel=channel, message=message, **kwargs)
        self.data.kwargs = dict(delay=delay)

    async def on_init(self):
        await super().on_init()
        if not isinstance(self.data.kwargs["delay"], (int, float)):
            raise TypeError("Invalid type given for argument 'delay'")

        self.data.kwargs["delay"] = float(self.data.kwargs["delay"])

    async def on_run(self):
        await self.data.message.delete(**self.data.kwargs)


class ReactionAdd(_MessageModify):
    """Adds a given reaction to a message."""

    def __init__(
        self,
        channel: Union[
            int, discord.abc.Messageable, serializers.ChannelSerializer, NoneType
        ],
        message: Union[int, discord.Message, serializers.MessageSerializer],
        emoji: Union[
            int,
            discord.Reaction,
            discord.Emoji,
            serializers.EmojiSerializer,
            discord.PartialEmoji,
            serializers.PartialEmojiSerializer,
            str,
        ],
        **kwargs,
    ):
        """Setup this job ojbect.

        Args:
            channel_id (int): The ID of a channel to get a message from.
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
            **kwargs:
                The keyword arguments to pass to the
                coroutine methods of the message.
        """
        super().__init__(channel=channel, message=message, **kwargs)
        self.data.emoji = emoji

    async def on_init(self):
        await super().on_init()
        if not isinstance(
            self.data.emoji,
            (discord.Reaction, discord.Emoji, discord.PartialEmoji, str),
        ):
            if isinstance(self.data.emoji, int):
                emoji = client.get_emoji(self.data.emoji)
                if emoji is None:
                    raise ValueError("invalid integer ID for 'emoji' argument")
                self.data.emoji = emoji
            elif isinstance(
                self.data.emoji,
                (serializers.EmojiSerializer, serializers.PartialEmojiSerializer),
            ):
                self.data.emoji = self.data.emoji.deserialized()
            else:
                raise TypeError("Invalid type for argument 'emoji'")

    async def on_run(self):
        await self.data.message.add_reaction(self.data.emoji)


class ReactionsAdd(_MessageModify):
    """Adds a sequence of reactions to a message."""

    def __init__(
        self,
        channel: Union[
            int, discord.abc.Messageable, serializers.ChannelSerializer, NoneType
        ],
        message: Union[int, discord.Message, serializers.MessageSerializer],
        *emojis: Union[
            int,
            discord.Reaction,
            discord.Emoji,
            serializers.EmojiSerializer,
            discord.PartialEmoji,
            serializers.PartialEmojiSerializer,
            str,
        ],
        stop_at_maximum=True,
        **kwargs,
    ):
        """Setup this object.

        Args:
            channel (Union[int, discord.abc.Messageable, serializers.ChannelSerializer, NoneType]):
            The channel to get a message from.
            message (Union[int, discord.Message, serializers.MessageSerializer]): The message to react to.
            *emojis (
                Union[
                    int,
                    discord.Reaction,
                    discord.Emoji,
                    serializers.EmojiSerializer,
                    discord.PartialEmoji,
                    serializers.PartialEmojiSerializer,
                    str]
            ):
                A sequence of emojis to react with.
            stop_at_maximum (bool, optional):
                Whether the reactions will be added until the maxmimum is reached. If False,
                reaction emojis will be added to a target message until an exception is
                raised from Discord. Defaults to True.
            **kwargs:
                The keyword arguments to pass to the
                coroutine methods of the message.
        """
        super().__init__(channel=channel, message=message, **kwargs)
        if len(emojis) > 20:
            raise ValueError(
                "only 20 reaction emojis can be added to a message at a time."
            )
        self.data.emojis = list(emojis)
        self.data.stop_at_maximum = stop_at_maximum

    async def on_init(self):
        await super().on_init()
        for i in range(len(self.data.emojis)):
            emoji = self.data.emojis[i]
            if not isinstance(
                emoji,
                (discord.Reaction, discord.Emoji, discord.PartialEmoji, str),
            ):
                if isinstance(emoji, int):
                    emoji = client.get_emoji(emoji)
                    if emoji is None:
                        raise ValueError(
                            f"Could not find a valid emoji for 'emojis' argument {3+i}"
                        )
                    self.data.emojis[i] = emoji
                elif isinstance(
                    emoji,
                    (serializers.EmojiSerializer, serializers.PartialEmojiSerializer),
                ):
                    self.data.emojis[i] = emoji.deserialized()
                else:
                    raise TypeError(
                        f"Invalid type for argument 'emojis' at argument {3+i}"
                    )

    async def on_run(self):
        message: discord.Message = self.data.message
        emojis: list = self.data.emojis

        if self.data.stop_at_maximum:
            for i in range(min(20 - len(message.reactions), len(emojis))):
                await self.data.message.add_reaction(emojis[i])
        else:
            for i in range(len(emojis)):
                await message.add_reaction(emojis[i])


class ReactionRemove(_MessageModify):
    """Removes a given reaction from a message."""

    def __init__(
        self,
        channel: Union[
            int, discord.abc.Messageable, serializers.ChannelSerializer, NoneType
        ],
        message: Union[int, discord.Message, serializers.MessageSerializer],
        emoji: Union[
            int,
            discord.Reaction,
            discord.Emoji,
            serializers.EmojiSerializer,
            discord.PartialEmoji,
            serializers.PartialEmojiSerializer,
            str,
        ],
        member: Union[
            discord.abc.Snowflake, discord.Member, serializers.MemberSerializer
        ],
        **kwargs,
    ):
        """Setup this job ojbect.

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
            **kwargs:
                The keyword arguments to pass to the
                coroutine methods of the message.
        """
        super().__init__(channel=channel, message=message, **kwargs)
        self.data.emoji = emoji
        self.data.member = member

    async def on_init(self):
        await super().on_init()
        if not isinstance(
            self.data.emoji,
            (discord.Reaction, discord.Emoji, discord.PartialEmoji, str),
        ):
            if isinstance(self.data.emoji, int):
                emoji = client.get_emoji(self.data.emoji)
                if emoji is None:
                    raise ValueError("invalid integer ID for 'emoji' argument")
                self.data.emoji = emoji
            elif isinstance(
                self.data.emoji,
                (serializers.EmojiSerializer, serializers.PartialEmojiSerializer),
            ):
                self.data.emoji = self.data.emoji.deserialized()
            else:
                raise TypeError("Invalid type for argument 'emoji'")

        if not isinstance(self.data.member, (discord.abc.Snowflake, discord.Member)):
            if isinstance(self.data.member, serializers.MemberSerializer):
                self.data.member = await self.data.member.deserialized_async()
            else:
                raise TypeError("Invalid type for argument 'member'")

    async def on_run(self):
        await self.data.message.remove_reaction(self.data.emoji, self.data.member)


class ReactionClearEmoji(_MessageModify):
    """Clears a set of reactions from a message."""

    def __init__(
        self,
        channel: Union[
            int, discord.abc.Messageable, serializers.ChannelSerializer, NoneType
        ],
        message: Union[int, discord.Message],
        emoji: Union[
            int,
            discord.Reaction,
            discord.Emoji,
            serializers.EmojiSerializer,
            discord.PartialEmoji,
            serializers.PartialEmojiSerializer,
            str,
        ],
        **kwargs,
    ):
        """Setup this job ojbect.

        Args:
            channel_id (int): The ID of a channel to get a message from.
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
            **kwargs:
                The keyword arguments to pass to the
                coroutine methods of the message.s
        """
        super().__init__(channel=channel, message=message, **kwargs)
        self.data.emoji = emoji

    async def on_init(self):
        await super().on_init()
        if not isinstance(
            self.data.emoji,
            (discord.Reaction, discord.Emoji, discord.PartialEmoji, str),
        ):
            if isinstance(self.data.emoji, int):
                emoji = client.get_emoji(self.data.emoji)
                if emoji is None:
                    raise ValueError("invalid integer ID for 'emoji' argument")
                self.data.emoji = emoji
            elif isinstance(
                self.data.emoji,
                (serializers.EmojiSerializer, serializers.PartialEmojiSerializer),
            ):
                self.data.emoji = self.data.emoji.deserialized()
            else:
                raise TypeError("Invalid type for argument 'emoji'")

    async def on_run(self):
        await self.data.message.clear_reaction(self.data.emoji)


class ReactionClear(_MessageModify):
    """Clears all reactions from a message."""

    async def on_run(self):
        await self.data.message.clear_reactions()
