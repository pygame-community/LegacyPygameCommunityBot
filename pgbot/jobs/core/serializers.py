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
import time
from types import SimpleNamespace
from typing import Any, Callable, Coroutine, Iterable, Optional, Sequence, Union

import discord
from discord.ext import tasks

from pgbot.utils import utils
from pgbot.db import DiscordDB
from pgbot import common

client = common.bot


class DeserializationError(Exception):
    pass


class SerializationError(Exception):
    pass


class BaseSerial:
    IS_ASYNC = False

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
            raise ValueError("Cannot identify format of the given 'data' dictionary") from None

        instance = cls.__new__(cls)
        instance._data = data.copy()
        return instance

    def to_dict(self):
        return dict(_class_name=self.__class__.__name__, **self._dict)

    serialized = to_dict


class UserSerial(BaseSerial):
    IS_ASYNC = True

    def __init__(self, user: discord.User):
        self._dict = {
            "id": user.id,
        }

    async def reconstructed(self, always_fetch=False):
        user = client.get_user(self._dict["id"])
        if user is None:
            if always_fetch:
                user = await client.fetch_user(self._dict["id"])
            else:
                raise DeserializationError(
                    f'could not restore User object with ID {self._dict["id"]}'
                ) from None
        return user


class MemberSerial(BaseSerial):
    IS_ASYNC = True

    def __init__(self, member: discord.Member):
        self._dict = {"id": member.id, "guild_id": member.guild.id}

    async def reconstructed(self, always_fetch=False):
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


class GuildSerial(BaseSerial):
    IS_ASYNC = True

    def __init__(self, guild: discord.Guild):
        self._dict = {
            "id": guild.id,
        }

    async def reconstructed(self, always_fetch=False):
        guild = client.get_guild(self._dict["id"])
        if guild is None:
            if always_fetch:
                guild = await client.fetch_guild(self._dict["id"])
            else:
                raise DeserializationError(
                    f'could not restore Guild object with ID {self._dict["id"]}'
                ) from None
        return guild


class EmojiSerial(BaseSerial):
    def __init__(self, emoji: discord.Emoji):
        self._dict = {
            "id": emoji.id,
        }

    def reconstructed(self):
        emoji = client.get_emoji(self._dict["id"])
        if emoji is None:
            raise DeserializationError(
                f'could not restore Emoji object with ID {self._dict["id"]}'
            ) from None

        return emoji


class PartialEmojiSerial(BaseSerial):
    def __init__(self, emoji: discord.PartialEmoji):
        self._dict = {
            "dict": emoji.to_dict(),
        }

    def reconstructed(self):
        return discord.PartialEmoji.from_dict(self._dict["dict"])


class FileSerial(BaseSerial):
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

    def reconstructed(self):
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


class RoleSerial(BaseSerial):
    IS_ASYNC = True

    def __init__(self, role: discord.Role):
        self._dict = {"id": role.id, "guild_id": role.guild.id}

    async def reconstructed(self, always_fetch=False):
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


class PermissionSerial(BaseSerial):
    def __init__(self, permissions: discord.Permissions):
        self._dict = {"value": permissions.value}

    def reconstructed(self):
        return discord.Permissions(permissions=self._dict["value"])


class PermissionOverwriteSerial(BaseSerial):
    def __init__(self, permission_overwrite: discord.PermissionOverwrite):
        self._dict = {"_values": permission_overwrite._values}

    def reconstructed(self):
        permission_overwrite = discord.PermissionOverwrite()
        permission_overwrite._values = self._dict["_values"].copy()
        return permission_overwrite


class AllowedMentionsSerial(BaseSerial):
    IS_ASYNC = True

    def __init__(self, allowed_mentions: discord.AllowedMentions):
        self._dict = {
            "everyone": bool(allowed_mentions.everyone),
            "replied_user": bool(allowed_mentions.replied_user),
            "roles": bool(allowed_mentions.roles)
            if not isinstance(allowed_mentions.roles, list)
            else [RoleSerial(role).serialized() for role in allowed_mentions.roles],
            "users": bool(allowed_mentions.users)
            if not isinstance(allowed_mentions.users, list)
            else [UserSerial(user).serialized() for user in allowed_mentions.users],
        }

    async def reconstructed(self):
        return discord.AllowedMentions(
            everyone=self._dict["everyone"],
            replied_user=self._dict["replied_user"],
            roles=[
                (await RoleSerial.from_dict(role_data).deserialize())
                for role_data in self._dict["roles"]
            ]
            if isinstance(self._dict["roles"], list)
            else self._dict["roles"],
            users=[
                (await UserSerial.from_dict(user_data).deserialize())
                for user_data in self._dict["users"]
            ]
            if isinstance(self._dict["users"], list)
            else self._dict["users"],
        )


class ColorSerial(BaseSerial):
    def __init__(self, color: discord.Color):
        self._dict = {"value": color.value}

    def reconstructed(self):
        return discord.Color(self._dict["value"])


class ActivitySerial(BaseSerial):
    def __init__(self, activity: discord.Activity):
        self._dict = {"dict": activity.to_dict()}

    def reconstructed(self):
        return discord.Activity(**self._dict["dict"])


class GameSerial(BaseSerial):
    def __init__(self, game: discord.Game):
        self._dict = {"dict": game.to_dict()}

    def reconstructed(self):
        return discord.Game(**self._dict["dict"])


class StreamingSerial(BaseSerial):
    def __init__(self, streaming: discord.Streaming):
        self._dict = {"dict": streaming.to_dict()}

    def reconstructed(self):
        return discord.Streaming(**self._dict["dict"])


class MessageSerial(BaseSerial):
    IS_ASYNC = True

    def __init__(self, message: discord.Message):
        self._dict = {
            "id": message.id,
            "channel_id": message.channel.id,
        }

    async def reconstructed(self, always_fetch=False):
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


class MessageReferenceSerial(BaseSerial):
    def __init__(self, message_reference: discord.MessageReference):
        self._dict = {"dict": message_reference.to_dict()}

    def reconstructed(self):
        return discord.MessageReference(*self._dict["dict"])


class EmbedSerial(BaseSerial):
    def __init__(self, embed: discord.Embed):
        self._dict = {
            "dict": embed.to_dict(),
        }

    def reconstructed(self):
        return discord.Embed.from_dict(self._dict["dict"])


class ChannelSerial(BaseSerial):
    IS_ASYNC = True

    def __init__(self, channel: discord.abc.Messageable):
        self._dict = {
            "id": channel.id,
        }

    async def reconstructed(self, always_fetch=False):
        channel = client.get_channel(self._dict["id"])
        if channel is None:
            if always_fetch:
                channel = await client.fetch_channel(self._dict["id"])
            else:
                raise DeserializationError(
                    f'could not restore Messageable object (channel) with ID {self._dict["id"]}'
                ) from None
        return channel


class GuildChannelSerial(ChannelSerial):
    def __init__(self, channel: discord.abc.GuildChannel):
        super().__init__(channel=channel)
        self._dict.update(guild_id=channel.guild.id)

    async def reconstructed(self, always_fetch=False):
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


class TextChannelSerial(GuildChannelSerial):
    def __init__(self, channel: discord.TextChannel):
        super().__init__(channel=channel)


class VoiceChannelSerial(GuildChannelSerial):
    def __init__(self, channel: discord.VoiceChannel):
        super().__init__(channel=channel)


class StageChannelSerial(GuildChannelSerial):
    def __init__(self, channel: discord.StageChannel):
        super().__init__(channel=channel)


class StoreChannelSerial(GuildChannelSerial):
    def __init__(self, channel: discord.StoreChannel):
        super().__init__(channel=channel)


class PrivateChannelSerial(ChannelSerial):
    def __init__(self, channel: discord.abc.PrivateChannel):
        super().__init__(channel=channel)


class GroupChannelSerial(PrivateChannelSerial):
    def __init__(self, channel: discord.GroupChannel):
        super().__init__(channel=channel)


class DMChannelSerial(PrivateChannelSerial):
    def __init__(self, channel: discord.DMChannel):
        super().__init__(channel=channel)
