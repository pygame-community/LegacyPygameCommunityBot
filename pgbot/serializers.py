"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file implements wrapper classes used to pickle Discord models and dataclasses. 
"""

from __future__ import annotations
import asyncio
from collections import deque
import datetime
import io
import itertools
import pickle
from selectors import BaseSelector
import time
from types import SimpleNamespace
from typing import Any, Callable, Coroutine, Iterable, Optional, Sequence, Type, Union

import discord
from discord.ext import tasks

from pgbot.utils import utils
from pgbot import common

client = common.bot

if not isinstance(client, discord.Client):
    raise RuntimeError("No discord `Client` object could be found in 'common.bot'")

_DISCORD_MODEL_SERIAL_MAP = {}


def get_serializer_class(discord_class: Type):
    class_name = discord_class.__name__

    if class_name in _DISCORD_MODEL_SERIAL_MAP:
        return _DISCORD_MODEL_SERIAL_MAP[class_name]

    raise LookupError(
        "could not find a serializer class for the specified discord class"
    )


class DeserializationError(Exception):
    pass


class SerializationError(Exception):
    pass


class BaseSerializer:
    IS_ASYNC = False

    __slots__ = ("_dict",)

    def __init__(self):
        self._dict = None

    def __getstate__(self):
        return self.to_dict()

    def __setstate__(self, state):
        self._dict = state

    @classmethod
    def from_dict(cls, data: dict):
        if not isinstance(data, dict):
            raise TypeError(
                f"argument data must be of type 'dict', not {type(data).__name__}"
            ) from None

        elif data.get("_class_name") != cls.__name__:
            raise ValueError(
                "Cannot identify format of the given 'data' dictionary"
            ) from None

        instance = cls.__new__(cls)
        instance._dict = data.copy()
        return instance

    def to_dict(self):
        """Return the serialized data of this serializer object as a dictionary.

        Returns:
            dict: The serialized data.
        """
        return dict(_class_name=self.__class__.__name__, **self._dict)

    serialized = to_dict

    def deserialized(self):
        """A method meant to be overloaded,
        which is for deserializing the serialized data of this
        serializer object back into a specific python object
        it was made for.

        Raises:
            NotImplementedError: This method must be overloaded in subclasses.
        """
        raise NotImplementedError()

    async def deserialized_async(self, *args, **kwargs):
        """An asynchronous version of `deserialized()`
        that other `BaseSerializer` subclasses are
        meant to overload. The default implementation
        of this method calls the `deserialized()`
        method and returns its output.

        Returns:
            object: The reconstruction output.

        Raises:
            NotImplementedError: No reconstruction methods were implemented.
        """
        if not self.IS_ASYNC:
            return self.deserialized(*args, **kwargs)

        raise NotImplementedError()


class DiscordObjectSerializer(BaseSerializer):
    ALWAYS_FETCH_ON_ASYNC_RECONSTRUCT = False


class UserSerializer(DiscordObjectSerializer):
    IS_ASYNC = True

    def __init__(self, user: discord.User):
        self._dict = {
            "id": user.id,
        }

    async def deserialized_async(self, always_fetch: Optional[bool] = None):
        if always_fetch is None:
            always_fetch = self.ALWAYS_FETCH_ON_ASYNC_RECONSTRUCT

        user = client.get_user(self._dict["id"])
        if user is None:
            if always_fetch:
                user = await client.fetch_user(self._dict["id"])
            else:
                raise DeserializationError(
                    f'could not restore User object with ID {self._dict["id"]}'
                ) from None
        return user


class MemberSerializer(DiscordObjectSerializer):
    IS_ASYNC = True

    def __init__(self, member: discord.Member):
        self._dict = {"id": member.id, "guild_id": member.guild.id}

    async def deserialized_async(self, always_fetch: Optional[bool] = None):
        if always_fetch is None:
            always_fetch = self.ALWAYS_FETCH_ON_ASYNC_RECONSTRUCT

        guild: discord.Guild = client.get_guild(self._dict["guild_id"])
        if guild is None:
            if always_fetch:
                guild = await client.fetch_guild(self._dict["id"])
            else:
                raise DeserializationError(
                    f'could not restore Guild object with ID {self._dict["guild_id"]} for Member object with ID {self._dict["id"]}'
                ) from None

        member = guild.get_member(self._dict["id"])
        if member is None:
            if always_fetch:
                member = await guild.fetch_member(self._dict["id"])
            else:
                raise DeserializationError(
                    f'could not restore Member object with ID {self._dict["id"]}'
                ) from None
        return member


class GuildSerializer(DiscordObjectSerializer):
    IS_ASYNC = True

    def __init__(self, guild: discord.Guild):
        self._dict = {
            "id": guild.id,
        }

    async def deserialized_async(self, always_fetch: Optional[bool] = None):
        if always_fetch is None:
            always_fetch = self.ALWAYS_FETCH_ON_ASYNC_RECONSTRUCT

        guild = client.get_guild(self._dict["id"])
        if guild is None:
            if always_fetch:
                guild = await client.fetch_guild(self._dict["id"])
            else:
                raise DeserializationError(
                    f'could not restore Guild object with ID {self._dict["id"]}'
                ) from None
        return guild


class EmojiSerializer(DiscordObjectSerializer):
    def __init__(self, emoji: discord.Emoji):
        self._dict = {
            "id": emoji.id,
        }

    def deserialized(self):
        emoji = client.get_emoji(self._dict["id"])
        if emoji is None:
            raise DeserializationError(
                f'could not restore Emoji object with ID {self._dict["id"]}'
            ) from None

        return emoji


class PartialEmojiSerializer(DiscordObjectSerializer):
    def __init__(self, emoji: discord.PartialEmoji):
        self._dict = {
            "dict": emoji.to_dict(),
        }

    def deserialized(self):
        return discord.PartialEmoji.from_dict(self._dict["dict"])


class FileSerializer(DiscordObjectSerializer):
    def __init__(self, file: discord.File):
        self._dict = {"filename": file.filename, "spoiler": file.spoiler}
        if isinstance(file.fp, str):
            self._dict.update(
                fp=file.fp,
                data=None,
            )
        elif isinstance(file.fp, (io.StringIO, io.BytesIO)):
            self._dict.update(fp=None, data=file.fp.getvalue())

        elif isinstance(file.fp, io.IOBase):
            if hasattr(file.fp, "read"):
                self._dict.update(
                    fp=None,
                    data=file.fp.read(),
                )
            else:
                raise ValueError(
                    "Could not serialize File object into pickleable dictionary"
                ) from None

    def deserialized(self):
        if self._dict["fp"] is None:
            data = self._dict["data"]

            if isinstance(data, str):
                fp = io.StringIO(data)

            elif isinstance(data, (bytes, bytearray)):
                fp = io.BytesIO(data)
            else:
                raise DeserializationError(
                    "Could not deserialize File object into pickleable dictionary"
                ) from None

            return discord.File(
                fp=fp, filename=self._dict["filename"], spoiler=self._dict["spoiler"]
            )

        elif isinstance(self._dict["fp"], str):
            return discord.File(
                fp=self._dict["fp"],
                filename=self._dict["filename"],
                spoiler=self._dict["spoiler"],
            )


class RoleSerializer(DiscordObjectSerializer):
    IS_ASYNC = True

    def __init__(self, role: discord.Role):
        self._dict = {"id": role.id, "guild_id": role.guild.id}

    async def deserialized_async(self, always_fetch: Optional[bool] = None):
        if always_fetch is None:
            always_fetch = self.ALWAYS_FETCH_ON_ASYNC_RECONSTRUCT

        guild = client.get_guild(self._dict["guild_id"])

        if guild is None:
            if always_fetch:
                guild = await client.fetch_guild(self._dict["guild_id"])
        else:
            raise DeserializationError(
                f'could not restore Guild object with ID {self._dict["guild_id"]} for Role object with ID {self._dict["id"]}'
            ) from None

        role = guild.get_role(self._dict["id"])
        if role is None:
            if always_fetch:
                roles = await guild.fetch_roles()
                for r in roles:
                    r.id == self._dict["id"]
                    role = r
                    break

                if role is None:
                    raise DeserializationError(
                        f'could not find Role object with ID {self._dict["id"]}'
                    ) from None
            else:
                raise DeserializationError(
                    f'could not restore Role object with ID {self._dict["id"]}'
                ) from None

        return role


class PermissionsSerializer(DiscordObjectSerializer):
    def __init__(self, permissions: discord.Permissions):
        self._dict = {"value": permissions.value}

    def deserialized(self):
        return discord.Permissions(permissions=self._dict["value"])


class PermissionOverwriteSerializer(DiscordObjectSerializer):
    def __init__(self, permission_overwrite: discord.PermissionOverwrite):
        self._dict = {"_values": permission_overwrite._values}

    def deserialized(self):
        permission_overwrite = discord.PermissionOverwrite()
        permission_overwrite._values = self._dict["_values"].copy()
        return permission_overwrite


class AllowedMentionsSerializer(DiscordObjectSerializer):
    IS_ASYNC = True

    def __init__(self, allowed_mentions: discord.AllowedMentions):
        self._dict = {
            "everyone": bool(allowed_mentions.everyone),
            "replied_user": bool(allowed_mentions.replied_user),
            "roles": bool(allowed_mentions.roles)
            if not isinstance(allowed_mentions.roles, list)
            else [RoleSerializer(role).serialized() for role in allowed_mentions.roles],
            "users": bool(allowed_mentions.users)
            if not isinstance(allowed_mentions.users, list)
            else [UserSerializer(user).serialized() for user in allowed_mentions.users],
        }

    async def deserialized_async(self, always_fetch: Optional[bool] = None):
        return discord.AllowedMentions(
            everyone=self._dict["everyone"],
            replied_user=self._dict["replied_user"],
            roles=[
                (await RoleSerializer.from_dict(role_data).deserialize())
                for role_data in self._dict["roles"]
            ]
            if isinstance(self._dict["roles"], list)
            else self._dict["roles"],
            users=[
                (await UserSerializer.from_dict(user_data).deserialize())
                for user_data in self._dict["users"]
            ]
            if isinstance(self._dict["users"], list)
            else self._dict["users"],
        )


class ColorSerializer(DiscordObjectSerializer):
    def __init__(self, color: discord.Color):
        self._dict = {"value": color.value}

    def deserialized(self):
        return discord.Color(self._dict["value"])


class ActivitySerializer(DiscordObjectSerializer):
    def __init__(self, activity: discord.Activity):
        self._dict = {"dict": activity.to_dict()}

    def deserialized(self):
        return discord.Activity(**self._dict["dict"])


class GameSerializer(DiscordObjectSerializer):
    def __init__(self, game: discord.Game):
        self._dict = {"dict": game.to_dict()}

    def deserialized(self):
        return discord.Game(**self._dict["dict"])


class StreamingSerializer(DiscordObjectSerializer):
    def __init__(self, streaming: discord.Streaming):
        self._dict = {"dict": streaming.to_dict()}

    def deserialized(self):
        return discord.Streaming(**self._dict["dict"])


class IntentsSerializer(DiscordObjectSerializer):
    def __init__(self, intents: discord.Intents):
        self._dict = {"value": intents.value}

    def deserialized(self):
        i = discord.Intents()
        i.value = self._dict["value"]
        return i


class MemberCacheFlagsSerializer(DiscordObjectSerializer):
    def __init__(self, member_cache_flags: discord.MemberCacheFlags):
        self._dict = {"value": member_cache_flags.value}

    def deserialized(self):
        f = discord.MemberCacheFlags()
        f.value = self._dict["value"]
        return f


class SystemChannelFlagsSerializer(DiscordObjectSerializer):
    def __init__(self, system_channel_flags: discord.SystemChannelFlags):
        self._dict = {"value": system_channel_flags.value}

    def deserialized(self):
        f = discord.SystemChannelFlags()
        f.value = self._dict["value"]
        return f


class MessageFlagsSerializer(DiscordObjectSerializer):
    def __init__(self, message_flags: discord.MessageFlags):
        self._dict = {"value": message_flags.value}

    def deserialized(self):
        f = discord.SystemChannelFlags()
        f.value = self._dict["value"]
        return f


class PublicUserFlagsSerializer(DiscordObjectSerializer):
    def __init__(self, public_user_flags: discord.PublicUserFlags):
        self._dict = {"value": public_user_flags.value}

    def deserialized(self):
        f = discord.PublicUserFlags()
        f.value = self._dict["value"]
        return f


class MessageSerializer(DiscordObjectSerializer):
    IS_ASYNC = True
    ALWAYS_FETCH_ON_ASYNC_RECONSTRUCT = True

    def __init__(self, message: discord.Message):
        self._dict = {
            "id": message.id,
            "channel_id": message.channel.id,
        }

    async def deserialized_async(self, always_fetch: Optional[bool] = None):
        if always_fetch is None:
            always_fetch = self.ALWAYS_FETCH_ON_ASYNC_RECONSTRUCT

        channel = client.get_channel(self._dict["channel_id"])

        if channel is None:
            if always_fetch:
                channel = await client.fetch_channel(self._dict["channel_id"])
            else:
                raise DeserializationError(
                    f'could not restore Messageable object (channel) with ID {self._dict["channel_id"]} for Message with ID {self._dict["id"]}'
                ) from None

        message = await channel.fetch_message(self._dict["id"])
        return message


class MessageReferenceSerializer(DiscordObjectSerializer):
    def __init__(self, message_reference: discord.MessageReference):
        self._dict = {"dict": message_reference.to_dict()}

    def deserialized(self):
        return discord.MessageReference(**self._dict["dict"])


class EmbedSerializer(DiscordObjectSerializer):
    def __init__(self, embed: discord.Embed):
        self._dict = {
            "dict": embed.to_dict(),
        }

    def deserialized(self):
        return discord.Embed.from_dict(self._dict["dict"])


class ChannelSerializer(DiscordObjectSerializer):
    IS_ASYNC = True

    def __init__(self, channel: discord.abc.Messageable):
        self._dict = {
            "id": channel.id,
        }

    async def deserialized_async(self, always_fetch: Optional[bool] = None):
        if always_fetch is None:
            always_fetch = self.ALWAYS_FETCH_ON_ASYNC_RECONSTRUCT

        channel = client.get_channel(self._dict["id"])
        if channel is None:
            if always_fetch:
                channel = await client.fetch_channel(self._dict["id"])
            else:
                raise DeserializationError(
                    f'could not restore Messageable object (channel) with ID {self._dict["id"]}'
                ) from None
        return channel


class GuildChannelSerializer(ChannelSerializer):
    def __init__(self, channel: discord.abc.GuildChannel):
        super().__init__(channel=channel)
        self._dict.update(guild_id=channel.guild.id)

    async def deserialized_async(self, always_fetch: Optional[bool] = None):
        if always_fetch is None:
            always_fetch = self.ALWAYS_FETCH_ON_ASYNC_RECONSTRUCT

        guild = client.get_guild(self._dict["guild_id"])
        if guild is None:
            if always_fetch:
                guild = await client.fetch_guild(self._dict["guild_id"])
            else:
                raise DeserializationError(
                    f'could not restore Guild object with ID {self._dict["guild_id"]} for GuildChannel object with ID {self._dict["id"]}'
                ) from None

        channel = guild.get_channel(self._dict["id"])
        if channel is None:
            if always_fetch:
                channels = await guild.fetch_channels()
                for ch in channels:
                    if ch.id == self._dict["id"]:
                        channel = ch
            else:
                raise DeserializationError(
                    f'could not restore GuildChannel object with ID {self._dict["id"]}'
                ) from None
        return channel


class TextChannelSerializer(GuildChannelSerializer):
    def __init__(self, channel: discord.TextChannel):
        super().__init__(channel=channel)


class VoiceChannelSerializer(GuildChannelSerializer):
    def __init__(self, channel: discord.VoiceChannel):
        super().__init__(channel=channel)


class StageChannelSerializer(GuildChannelSerializer):
    def __init__(self, channel: discord.StageChannel):
        super().__init__(channel=channel)


class StoreChannelSerializer(GuildChannelSerializer):
    def __init__(self, channel: discord.StoreChannel):
        super().__init__(channel=channel)


class _PrivateChannelSerializer(ChannelSerializer):
    def __init__(self, channel: discord.abc.PrivateChannel):
        super().__init__(channel=channel)


class GroupChannelSerializer(_PrivateChannelSerializer):
    def __init__(self, channel: discord.GroupChannel):
        super().__init__(channel=channel)


class DMChannelSerializer(_PrivateChannelSerializer):
    def __init__(self, channel: discord.DMChannel):
        super().__init__(channel=channel)


_DISCORD_MODEL_SERIAL_MAP.update(
    {
        discord.User.__name__: UserSerializer,
        discord.Member.__name__: MemberSerializer,
        discord.Guild.__name__: GuildSerializer,
        discord.Emoji.__name__: EmojiSerializer,
        discord.PartialEmoji.__name__: PartialEmojiSerializer,
        discord.File.__name__: FileSerializer,
        discord.Role.__name__: RoleSerializer,
        discord.Permissions.__name__: PermissionsSerializer,
        discord.PermissionOverwrite.__name__: PermissionOverwriteSerializer,
        discord.AllowedMentions.__name__: AllowedMentionsSerializer,
        discord.Color.__name__: ColorSerializer,
        discord.Activity.__name__: ActivitySerializer,
        discord.Game.__name__: GameSerializer,
        discord.Streaming.__name__: StreamingSerializer,
        discord.Intents.__name__: IntentsSerializer,
        discord.MemberCacheFlags.__name__: MemberCacheFlagsSerializer,
        discord.SystemChannelFlags.__name__: SystemChannelFlagsSerializer,
        discord.MessageFlags.__name__: MessageFlagsSerializer,
        discord.PublicUserFlags.__name__: PublicUserFlagsSerializer,
        discord.Message.__name__: MessageSerializer,
        discord.MessageReference.__name__: MessageReferenceSerializer,
        discord.Embed.__name__: EmbedSerializer,
        discord.TextChannel.__name__: TextChannelSerializer,
        discord.VoiceChannel.__name__: VoiceChannelSerializer,
        discord.StageChannel.__name__: StageChannelSerializer,
        discord.StoreChannel.__name__: StoreChannelSerializer,
        discord.GroupChannel.__name__: GroupChannelSerializer,
        discord.DMChannel.__name__: DMChannelSerializer,
    }
)
