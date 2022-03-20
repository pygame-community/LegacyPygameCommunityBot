"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file implements wrapper classes used to pickle Discord models and dataclasses. 
"""

from __future__ import annotations
import io
from typing import Optional, Type

import discord

from pgbot import common
from pgbot.utils.utils import recursive_dict_compare

global_client = common.bot

if not isinstance(global_client, discord.Client):
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

    DATA_FORMAT = {}

    def __init__(self):
        self._dict = None

    def __getstate__(self):
        return self.to_dict()

    def __setstate__(self, state):
        self._dict = state

    @classmethod
    def is_valid_data(cls, data: dict):
        if cls.DATA_FORMAT:
            return recursive_dict_compare(
                data,
                cls.DATA_FORMAT,
                compare_func=lambda a, b: isinstance(a, b),
                ignore_keys_missing_in_source=True,
                ignore_keys_missing_in_target=True,
            )

        return False

    @classmethod
    def from_dict(cls, data: dict, _verify_format: bool = True):
        """Create a new serializer object of this type from the
        serialized input data.

        Args:
            data (dict): The serialized input data.

        Raises:
            TypeError: Invalid argument for `data`.
            ValueError: Invalid data format.

        Returns:
            object: The serializer object.
        """
        if not isinstance(data, dict):
            raise TypeError(
                f"argument data must be of type 'dict', not {type(data).__name__}"
            ) from None

        elif _verify_format and not cls.is_valid_data(data):
            raise ValueError(
                f"The format of the given 'data' dictionary does not match the supported format of class {cls.__name__}"
            ) from None

        instance = cls.__new__(cls)
        instance._dict = data.copy()
        return instance

    def to_dict(self):
        """Return the serialized data of this serializer object as a dictionary.

        Returns:
            dict: The serialized data.
        """
        return dict(**self._dict)

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


class DiscordObjectBaseSerializer(BaseSerializer):
    ALWAYS_FETCH_ON_ASYNC_RECONSTRUCT = False


class UserSerializer(DiscordObjectBaseSerializer):
    IS_ASYNC = True
    DATA_FORMAT = {"user_id": int}

    def __init__(self, user: discord.User):
        self._dict = {
            "user_id": user.id,
        }

    async def deserialized_async(
        self,
        client: Optional[discord.Client] = None,
        always_fetch: Optional[bool] = None,
    ):
        if always_fetch is None:
            always_fetch = self.ALWAYS_FETCH_ON_ASYNC_RECONSTRUCT

        client: discord.Client = global_client if client is None else client

        user = client.get_user(self._dict["user_id"])
        if user is None:
            if always_fetch:
                user = await client.fetch_user(self._dict["user_id"])
            else:
                raise DeserializationError(
                    f'could not restore User object with ID {self._dict["user_id"]}'
                ) from None
        return user


class MemberSerializer(DiscordObjectBaseSerializer):
    IS_ASYNC = True
    DATA_FORMAT = {
        "member_id": int,
        "guild_id": int,
    }

    def __init__(self, member: discord.Member):
        self._dict = {"member_id": member.id, "guild_id": member.guild.id}

    async def deserialized_async(
        self,
        client: Optional[discord.Client] = None,
        always_fetch: Optional[bool] = None,
    ):
        if always_fetch is None:
            always_fetch = self.ALWAYS_FETCH_ON_ASYNC_RECONSTRUCT

        client: discord.Client = global_client if client is None else client

        guild = client.get_guild(self._dict["guild_id"])
        if guild is None:
            if always_fetch:
                guild = await client.fetch_guild(self._dict["member_id"])
            else:
                raise DeserializationError(
                    f'could not restore Guild object with ID {self._dict["guild_id"]} for Member object with ID {self._dict["member_id"]}'
                ) from None

        member = guild.get_member(self._dict["member_id"])
        if member is None:
            if always_fetch:
                member = await guild.fetch_member(self._dict["member_id"])
            else:
                raise DeserializationError(
                    f'could not restore Member object with ID {self._dict["member_id"]} from Guild object with ID {self._dict["guild_id"]}'
                ) from None
        return member


class GuildSerializer(DiscordObjectBaseSerializer):
    IS_ASYNC = True
    DATA_FORMAT = {
        "guild_id": int,
    }

    def __init__(self, guild: discord.Guild):
        self._dict = {
            "guild_id": guild.id,
        }

    async def deserialized_async(
        self,
        client: Optional[discord.Client] = None,
        always_fetch: Optional[bool] = None,
    ):
        if always_fetch is None:
            always_fetch = self.ALWAYS_FETCH_ON_ASYNC_RECONSTRUCT

        client: discord.Client = global_client if client is None else client

        guild = client.get_guild(self._dict["guild_id"])
        if guild is None:
            if always_fetch:
                guild = await client.fetch_guild(self._dict["guild_id"])
            else:
                raise DeserializationError(
                    f'could not restore Guild object with ID {self._dict["guild_id"]}'
                ) from None
        return guild


class EmojiSerializer(DiscordObjectBaseSerializer):
    DATA_FORMAT = {
        "emoji_id": int,
    }

    def __init__(self, emoji: discord.Emoji):
        self._dict = {
            "emoji_id": emoji.id,
        }

    def deserialized(self, client: Optional[discord.Client] = None):
        client: discord.Client = global_client if client is None else client
        emoji = client.get_emoji(self._dict["emoji_id"])
        if emoji is None:
            raise DeserializationError(
                f'could not restore Emoji object with ID {self._dict["emoji_id"]}'
            ) from None

        return emoji


class PartialEmojiSerializer(DiscordObjectBaseSerializer):
    DATA_FORMAT = {
        "partial_emoji": {
            "name": str,
            "id": int,
            "animated": bool,
        },
    }

    def __init__(self, emoji: discord.PartialEmoji):
        self._dict = {
            "partial_emoji": emoji.to_dict(),
        }

    def deserialized(self):
        return discord.PartialEmoji.from_dict(self._dict["partial_emoji"])


class FileSerializer(DiscordObjectBaseSerializer):
    DATA_FORMAT = {
        "filename": (str, type(None)),
        "fp": (str, io.IOBase, io.StringIO, io.BytesIO, type(None)),
        "data": (str, bytes, type(None)),
        "spoiler": bool,
    }

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


class RoleSerializer(DiscordObjectBaseSerializer):
    IS_ASYNC = True
    DATA_FORMAT = {
        "role_id": int,
        "guild_id": int,
    }

    def __init__(self, role: discord.Role):
        self._dict = {"role_id": role.id, "guild_id": role.guild.id}

    async def deserialized_async(
        self,
        client: Optional[discord.Client] = None,
        always_fetch: Optional[bool] = None,
    ):
        if always_fetch is None:
            always_fetch = self.ALWAYS_FETCH_ON_ASYNC_RECONSTRUCT

        client: discord.Client = global_client if client is None else client

        guild = client.get_guild(self._dict["guild_id"])

        if guild is None:
            if always_fetch:
                guild = await client.fetch_guild(self._dict["guild_id"])
        else:
            raise DeserializationError(
                f'could not restore Guild object with ID {self._dict["guild_id"]} for Role object with ID {self._dict["role_id"]}'
            ) from None

        role = guild.get_role(self._dict["role_id"])
        if role is None:
            if always_fetch:
                roles = await guild.fetch_roles()
                for r in roles:
                    if r.id == self._dict["role_id"]:
                        role = r
                        break

                if role is None:
                    raise DeserializationError(
                        f'could not find Role object with ID {self._dict["role_id"]}'
                    ) from None
            else:
                raise DeserializationError(
                    f'could not restore Role object with ID {self._dict["role_id"]}'
                ) from None

        return role


class PermissionsSerializer(DiscordObjectBaseSerializer):
    DATA_FORMAT = {
        "permission_value": int,
    }

    def __init__(self, permissions: discord.Permissions):
        self._dict = {"permission_value": permissions.value}

    def deserialized(self):
        return discord.Permissions(permissions=self._dict["permission_value"])


class PermissionOverwriteSerializer(DiscordObjectBaseSerializer):
    DATA_FORMAT = {
        "permission_overwrite_allow_value": int,
        "permission_overwrite_deny_value": int,
    }

    def __init__(self, permission_overwrite: discord.PermissionOverwrite):
        allow, deny = permission_overwrite.pair()
        self._dict = {
            "permission_overwrite_allow_value": allow.value,
            "permission_overwrite_deny_value": deny.value,
        }

    def deserialized(self):
        permission_overwrite = discord.PermissionOverwrite.from_pair(
            self._dict["permission_overwrite_allow_value"],
            self._dict["permission_overwrite_deny_value"],
        )
        return permission_overwrite


class AllowedMentionsSerializer(DiscordObjectBaseSerializer):
    IS_ASYNC = True
    DATA_FORMAT = {
        "everyone": bool,
        "replied_user": bool,
        "roles": (bool, list),
        "users": (bool, list),
    }

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
                (await RoleSerializer.from_dict(role_data).deserialized_async())
                for role_data in self._dict["roles"]
            ]
            if isinstance(self._dict["roles"], list)
            else self._dict["roles"],
            users=[
                (await UserSerializer.from_dict(user_data).deserialized_async())
                for user_data in self._dict["users"]
            ]
            if isinstance(self._dict["users"], list)
            else self._dict["users"],
        )


class ColorSerializer(DiscordObjectBaseSerializer):
    DATA_FORMAT = {"color": int}

    def __init__(self, color: discord.Color):
        self._dict = {"color": color.value}

    def deserialized(self):
        return discord.Color(self._dict["color"])


class ActivitySerializer(DiscordObjectBaseSerializer):
    DATA_FORMAT = {"dict": dict}

    def __init__(self, activity: discord.Activity):
        self._dict = {"dict": activity.to_dict()}

    def deserialized(self):
        return discord.Activity(**self._dict["dict"])


class GameSerializer(DiscordObjectBaseSerializer):
    DATA_FORMAT = {
        "game": {"type": int, "name": str, "timestamps": {"start": int, "end": int}}
    }

    def __init__(self, game: discord.Game):
        self._dict = {"game": game.to_dict()}

    def deserialized(self):
        return discord.Game(**self._dict["game"])


class StreamingSerializer(DiscordObjectBaseSerializer):
    DATA_FORMAT = {
        "streaming": {
            "type": int,
            "name": str,
            "url": str,
            "assets": dict,
            "details": str,
        }
    }

    def __init__(self, streaming: discord.Streaming):
        self._dict = {"streaming": streaming.to_dict()}

    def deserialized(self):
        return discord.Streaming(**self._dict["streaming"])


class IntentsSerializer(DiscordObjectBaseSerializer):
    DATA_FORMAT = {"intents": int}

    def __init__(self, intents: discord.Intents):
        self._dict = {"intents": intents.value}

    def deserialized(self):
        i = discord.Intents()
        i.value = self._dict["intents"]
        return i


class MemberCacheFlagsSerializer(DiscordObjectBaseSerializer):
    DATA_FORMAT = {"member_cache_flags": int}

    def __init__(self, member_cache_flags: discord.MemberCacheFlags):
        self._dict = {"member_cache_flags": member_cache_flags.value}

    def deserialized(self):
        f = discord.MemberCacheFlags()
        f.value = self._dict["member_cache_flags"]
        return f


class SystemChannelFlagsSerializer(DiscordObjectBaseSerializer):
    DATA_FORMAT = {"system_channel_flags": int}

    def __init__(self, system_channel_flags: discord.SystemChannelFlags):
        self._dict = {"system_channel_flags": system_channel_flags.value}

    def deserialized(self):
        f = discord.SystemChannelFlags()
        f.value = self._dict["system_channel_flags"]
        return f


class MessageFlagsSerializer(DiscordObjectBaseSerializer):
    DATA_FORMAT = {"message_flags": int}

    def __init__(self, message_flags: discord.MessageFlags):
        self._dict = {"message_flags": message_flags.value}

    def deserialized(self):
        f = discord.MessageFlags()
        f.value = self._dict["message_flags"]
        return f


class PublicUserFlagsSerializer(DiscordObjectBaseSerializer):
    DATA_FORMAT = {"public_user_flags": int}

    def __init__(self, public_user_flags: discord.PublicUserFlags):
        self._dict = {"public_user_flags": public_user_flags.value}

    def deserialized(self):
        f = discord.PublicUserFlags()
        f.value = self._dict["public_user_flags"]
        return f


class MessageSerializer(DiscordObjectBaseSerializer):
    IS_ASYNC = True
    ALWAYS_FETCH_ON_ASYNC_RECONSTRUCT = True
    DATA_FORMAT = {
        "message_id": int,
        "channel_id": int,
    }

    def __init__(self, message: discord.Message):
        self._dict = {
            "message_id": message.id,
            "channel_id": message.channel.id,
        }

    async def deserialized_async(
        self,
        client: Optional[discord.Client] = None,
        always_fetch: Optional[bool] = None,
    ):
        if always_fetch is None:
            always_fetch = self.ALWAYS_FETCH_ON_ASYNC_RECONSTRUCT

        client: discord.Client = global_client if client is None else client

        channel = client.get_channel(self._dict["channel_id"])

        if channel is None:
            if always_fetch:
                channel = await client.fetch_channel(self._dict["channel_id"])
            else:
                raise DeserializationError(
                    f'could not restore Messageable object (channel) with ID {self._dict["channel_id"]} for Message with ID {self._dict["message_id"]}'
                ) from None

        message = await channel.fetch_message(self._dict["message_id"])
        return message


class MessageReferenceSerializer(DiscordObjectBaseSerializer):
    DATA_FORMAT = {
        "message_id": int,
        "channel_id": int,
        "guild_id": int,
        "fail_if_not_exists": bool,
    }

    def __init__(self, message_reference: discord.MessageReference):
        self._dict = {"dict": message_reference.to_dict()}

    def deserialized(self):
        return discord.MessageReference(**self._dict["dict"])


class EmbedSerializer(DiscordObjectBaseSerializer):
    DATA_FORMAT = {"embed": dict}

    def __init__(self, embed: discord.Embed):
        self._dict = {
            "embed": embed.to_dict(),
        }

    def deserialized(self):
        return discord.Embed.from_dict(self._dict["embed"])


class ChannelSerializer(DiscordObjectBaseSerializer):
    IS_ASYNC = True
    DATA_FORMAT = {"channel_id": int}

    def __init__(self, channel: discord.abc.Messageable):
        self._dict = {
            "channel_id": channel.id,
        }

    async def deserialized_async(
        self,
        client: Optional[discord.Client] = None,
        always_fetch: Optional[bool] = None,
    ):
        if always_fetch is None:
            always_fetch = self.ALWAYS_FETCH_ON_ASYNC_RECONSTRUCT

        client: discord.Client = global_client if client is None else client

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
    DATA_FORMAT = {"channel_id": int, "guild_id": int}

    def __init__(self, channel: discord.abc.GuildChannel):
        super().__init__(channel=channel)
        self._dict.update(guild_id=channel.guild.id)

    async def deserialized_async(
        self,
        client: Optional[discord.Client] = None,
        always_fetch: Optional[bool] = None,
    ):
        if always_fetch is None:
            always_fetch = self.ALWAYS_FETCH_ON_ASYNC_RECONSTRUCT

        client: discord.Client = global_client if client is None else client

        guild = client.get_guild(self._dict["guild_id"])
        if guild is None:
            if always_fetch:
                guild = await client.fetch_guild(self._dict["guild_id"])
            else:
                raise DeserializationError(
                    f'could not restore Guild object with ID {self._dict["guild_id"]} for GuildChannel object with ID {self._dict["channel_id"]}'
                ) from None

        channel = guild.get_channel(self._dict["channel_id"])
        if channel is None:
            if always_fetch:
                channels = await guild.fetch_channels()
                for ch in channels:
                    if ch.id == self._dict["channel_id"]:
                        channel = ch
            else:
                raise DeserializationError(
                    f'could not restore GuildChannel object with ID {self._dict["channel_id"]}'
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
