"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file implements wrapper classes used to capture Discord Gateway events.
All classes inherit from `ClientEvent`, which inherits from `BaseEvents`. 
"""

from __future__ import annotations
import asyncio
from collections import deque
import datetime
from typing import Any, Callable, Coroutine, Iterable, Optional, Sequence, Union

import discord
from discord.ext import tasks
from pgbot import common

from . import base_events

client = common.bot

EVENT_MAP = base_events.EVENT_MAP

class ClientEvent(base_events.BaseEvent):
    """The base class for all discord API websocket event wrapper objects, with values as returned by discord.py."""

    alt_name: str = None

    __slots__ = ()


class OnReady(ClientEvent):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_ready"""

    alt_name = "ready"
    __slots__ = ()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class OnTyping(ClientEvent):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_typing"""

    alt_name = "typing"

    __slots__ = ("channel", "user", "when")

    def __init__(
        self,
        channel: Union[
            discord.TextChannel,
            discord.DMChannel,
            discord.GroupChannel,
            discord.Member,
            discord.User,
        ],
        user: Union[
            discord.Member,
            discord.User,
        ],
        when: datetime.datetime,
        *args,
        **kwargs,
    ):
        super().__init__(_timestamp=when)
        self.channel = channel
        self.user = user
        self.when = when


class OnMessageBase(ClientEvent):
    """Base class for all messaging related events.
    Subclasses:
        `OnMessage`
        `OnMessageEdit`
        `OnMessageDelete`
        `OnBulkMessageDelete`
    """

    __slots__ = ()
    pass


class OnRawMessageBase(ClientEvent):
    """Base class for all raw messaging related events.
    Subclasses:
        `OnRawMessageEdit`
        `OnRawMessageDelete`
        `OnRawBulkMessageDelete`
    """

    __slots__ = ()
    pass


class OnMessage(OnMessageBase):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_message"""

    __slots__ = ("message",)
    alt_name = "message"

    def __init__(self, message: discord.Message, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.message = message


class OnMessageDelete(OnMessageBase):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_message_delete"""

    __slots__ = ("message",)
    alt_name = "message_delete"

    def __init__(self, message: discord.Message, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.message = message


class OnRawMessageDelete(OnRawMessageBase):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_raw_message_delete"""

    __slots__ = ("payload",)
    alt_name = "raw_message_delete"

    def __init__(
        self,
        payload: discord.RawMessageDeleteEvent,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.payload = payload


class OnBulkMessageDelete(OnMessageBase):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_bulk_message_delete"""

    alt_name = "bulk_message_delete"
    __slots__ = ("messages",)

    def __init__(self, messages: list[discord.Message], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.messages = messages


class OnRawBulkMessageDelete(OnRawMessageBase):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_raw_bulk_message_delete"""

    __slots__ = ("payload",)
    alt_name = "raw_bulk_message_delete"

    def __init__(
        self,
        payload: discord.RawBulkMessageDeleteEvent,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.payload = payload


class OnMessageEdit(OnMessageBase):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_message_edit"""

    __slots__ = ("before", "after")
    alt_name = "message_edit"

    def __init__(
        self, before: discord.Message, after: discord.Message, *args, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.before = before
        self.after = after


class OnRawMessageEdit(OnRawMessageBase):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_raw_message_edit"""

    __slots__ = ("payload",)
    alt_name = "raw_message_edit"

    def __init__(
        self,
        payload: discord.RawMessageUpdateEvent,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.payload = payload


class OnReactionBase(ClientEvent):
    """Base class for all message reaction related events.
    Subclasses:
        `OnReactionAdd`
        `OnReactionRemove`
        `OnReactionclear`
        `OnReactionClearEmoji`
    """

    __slots__ = ()
    pass


class OnRawReactionBase(ClientEvent):
    """Base class for all raw message reaction related events.
    Subclasses:
        `OnRawReactionAdd`
        `OnRawReactionRemove`
        `OnRawReactionclear`
        `OnRawReactionClearEmoji`
    """

    __slots__ = ()
    pass


class _OnReactionToggle(OnReactionBase):
    __slots__ = ("reaction", "user")

    def __init__(
        self,
        reaction: discord.Reaction,
        user: Union[
            discord.Member,
            discord.User,
        ],
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.reaction = reaction
        self.user = user


class _OnRawReactionToggle(OnRawReactionBase):
    __slots__ = ("payload",)

    def __init__(
        self,
        payload: discord.RawReactionActionEvent,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.payload = payload

    async def as_unraw(self):
        user = None
        if (
            self.payload.guild_id
            and self.payload.member is not None
            and self.payload.event_type == "REACTION_ADD"
        ):
            user = self.payload.member
        else:
            user = client.get_user(self.payload.user_id)
            if not user:
                user = await client.fetch_user(self.payload.user_id)
            discord.Emoji
            channel = client.get_channel(self.payload.channel_id)
            if not channel:
                channel = await client.fetch_channel(self.payload.channel_id)

            message = await channel.fetch_message(self.payload.message_id)
            partial_emoji = self.payload.emoji
            reaction = None

            for msg_reaction in message.reactions:
                if msg_reaction.emoji == partial_emoji:
                    reaction = msg_reaction
                    break
            else:
                raise LookupError("Cannot find reaction object.")

        if self.payload.event_type == "REACTION_ADD":
            return OnReactionAdd(reaction, user, _timestamp=self._timestamp)
        elif self.payload.event_type == "REACTION_REMOVE":
            return OnReactionRemove(reaction, user, _timestamp=self._timestamp)


class OnReactionAdd(_OnReactionToggle):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_reaction_add"""

    __slots__ = ()
    alt_name = "reaction_add"

    pass


class OnReactionRemove(_OnReactionToggle):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_reaction_remove"""

    __slots__ = ()
    alt_name = "reaction_remove"

    pass


class OnRawReactionAdd(_OnRawReactionToggle):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_raw_reaction_add"""

    __slots__ = ()
    alt_name = "raw_reaction_add"
    pass


class OnRawReactionRemove(_OnRawReactionToggle):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_raw_reaction_remove"""

    __slots__ = ()
    alt_name = "raw_reaction_remove"
    pass


class OnReactionClear(OnReactionBase):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_reaction_clear"""

    __slots__ = ("message", "reactions")
    alt_name = "reaction_clear"

    def __init__(
        self,
        message: discord.Message,
        reactions: list[discord.Reaction],
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.message = message
        self.reactions = reactions


class OnReactionClearEmoji(OnReactionBase):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_reaction_clear_emoji"""

    __slots__ = ("reaction",)
    alt_name = "reaction_clear_emoji"

    def __init__(self, reaction: discord.Reaction, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.reaction = reaction


class OnRawReactionClearEmoji(OnRawReactionBase):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_raw_reaction_clear_emoji"""

    __slots__ = ("payload",)
    alt_name = "raw_reaction_clear_emoji"

    def __init__(
        self,
        payload: discord.RawReactionClearEmojiEvent,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.payload = payload


class OnRawReactionClear(OnRawReactionBase):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_raw_reaction_clear"""

    __slots__ = ("payload",)
    alt_name = "raw_reaction_clear"

    def __init__(
        self,
        payload: discord.RawReactionClearEvent,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.payload = payload


class OnPrivateChannelBase(ClientEvent):
    """Base class for all private channel manipulation related events.
    Subclasses:
        `OnPrivateChannelCreate`
        `OnPrivateChannelDelete`
        `OnPrivateChannelUpdate`
        `OnPrivateChannelPinsUpdate`
    """

    __slots__ = ()
    pass


class _OnPrivateChannelLifeCycle(OnPrivateChannelBase):
    __slots__ = ("channel",)

    def __init__(self, channel: discord.abc.PrivateChannel, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.channel = channel


class OnPrivateChannelCreate(_OnPrivateChannelLifeCycle):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_private_channel_create"""

    __slots__ = ()
    alt_name = "private_channel_create"
    pass


class OnPrivateChannelDelete(_OnPrivateChannelLifeCycle):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_private_channel_delete"""

    __slots__ = ()
    alt_name = "private_channel_delete"
    pass


class OnPrivateChannelUpdate(OnPrivateChannelBase):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_private_channel_update"""

    __slots__ = ("before", "after")
    alt_name = "private_channel_update"

    def __init__(
        self,
        before: discord.abc.PrivateChannel,
        after: discord.abc.PrivateChannel,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.before = before
        self.after = after


class OnPrivateChannelPinsUpdate(OnPrivateChannelBase):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_private_channel_pins_update"""

    alt_name = "private_channel_pins_update"
    __slots__ = ("channel", "last_pin")

    def __init__(
        self,
        channel: discord.abc.PrivateChannel,
        last_pin: datetime.datetime,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.channel = channel
        self.last_pin = last_pin


class OnGuildBase(ClientEvent):
    """Base class for all guild manipulation related events.
    Also includes manipulation of guild channels.
    Subclasses:
        `OnGuildChannelBase`
        `OnGuildIntegrationsUpdate`
        `OnWebhooksUpdate`
        `OnMemberBase`
        `OnGuildTrafficBase`
        `OnGuildUpdate`
        `OnGuildRoleBase`
        `OnGuildEmojisUpdate`
        `OnGuildAvailabilityBase`
        `OnVoiceStateUpdate`
        `OnMemberBanBase`
        `OnInviteBase`
    """

    __slots__ = ()
    pass


class OnGuildChannelBase(OnGuildBase):
    """Base class for all guild channel manipulation related events.
    Subclasses:
        `OnGuildChannelCreate`
        `OnGuildChannelDelete`
        `OnGuildChannelUpdate`
    """

    __slots__ = ()
    pass


class _OnGuildChannelLifeCycle(OnGuildChannelBase):
    __slots__ = ("channel",)

    def __init__(self, channel: discord.abc.GuildChannel, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.channel = channel


class OnGuildChannelCreate(_OnGuildChannelLifeCycle):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_channel_create"""

    __slots__ = ()
    alt_name = "guild_channel_create"
    pass


class OnGuildChannelDelete(_OnGuildChannelLifeCycle):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_channel_delete"""

    __slots__ = ()
    alt_name = "guild_channel_delete"
    pass


class OnGuildChannelUpdate(OnGuildChannelBase):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_channel_update"""

    __slots__ = ("before", "after")
    alt_name = "guild_channel_update"

    def __init__(
        self,
        before: discord.abc.GuildChannel,
        after: discord.abc.GuildChannel,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.before = before
        self.after = after


class OnGuildChannelPinsUpdate(OnGuildChannelBase):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_channel_pins_update"""

    __slots__ = ("channel", "last_pin")
    alt_name = "guild_channel_pins_update"

    def __init__(
        self,
        channel: discord.abc.GuildChannel,
        last_pin: datetime.datetime,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.channel = channel
        self.last_pin = last_pin


class OnGuildIntegrationsUpdate(OnGuildBase):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_integrations_update"""

    __slots__ = ("guild",)
    alt_name = "guild_integrations_update"

    def __init__(self, guild: discord.abc.GuildChannel, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.guild = guild


class OnWebhooksUpdate(OnGuildBase):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_webhooks_update"""

    __slots__ = ("channel",)
    alt_name = "webhooks_update"

    def __init__(self, channel: discord.abc.GuildChannel, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.channel = channel


class OnMemberBase(OnGuildBase):
    """Base class for all guild member related events.
    Subclasses:
        `OnMemberTrafficBase`
        `OnMemberUpdate`
        `OnMemberBanBase`
    """

    __slots__ = ()
    pass


class OnMemberTrafficBase(OnMemberBase):
    """Base class for all guild member traffic, which involve
    members joining and leaving guilds.
    Subclasses:
        `OnMemberJoin`
        `OnMemberRemove`
    """

    __slots__ = ("member",)

    def __init__(self, member: discord.Member, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.member = member


class OnMemberJoin(OnMemberTrafficBase):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_member_join"""

    __slots__ = ()
    alt_name = "member_join"
    pass


class OnMemberRemove(OnMemberTrafficBase):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_member_remove"""

    __slots__ = ()
    alt_name = "member_remove"
    pass


class OnMemberUpdate(OnMemberBase):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_member_update"""

    __slots__ = ("before", "after")
    alt_name = "member_update"

    def __init__(self, before: discord.Member, after: discord.Member, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.before = before
        self.after = after


class OnUserUpdate(ClientEvent):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_user_update"""

    __slots__ = ("before", "after")
    alt_name = "user_update"

    def __init__(self, before: discord.User, after: discord.User, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.before = before
        self.after = after


class OnGuildTrafficBase(OnGuildBase):
    """Base class for all guild traffic related events, such as the client joining and leaving guilds.
    Subclasses:
        `OnGuildJoin`
        `OnGuildRemove`
    """

    __slots__ = ("guild",)

    def __init__(self, guild: discord.Guild, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.guild = guild


class OnGuildJoin(OnGuildTrafficBase):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_join"""

    __slots__ = ()
    alt_name = "guild_join"
    pass


class OnGuildRemove(OnGuildTrafficBase):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_remove"""

    __slots__ = ()
    alt_name = "guild_remove"
    pass


class OnGuildUpdate(OnGuildBase):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_update"""

    __slots__ = ("before", "after")
    alt_name = "guild_update"

    def __init__(self, before: discord.Guild, after: discord.Guild, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.before = before
        self.after = after


class OnGuildRoleBase(OnGuildBase):
    """Base class for all guild role manipulation related events.
    Subclasses:
        `OnGuildRoleCreate`
        `OnGuildRoleDelete`
        `OnGuildRoleUpdate
    """

    __slots__ = ()
    pass


class _OnGuildRoleLifeCycle(OnGuildRoleBase):
    __slots__ = ("role",)

    def __init__(self, role: discord.Role, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.role = role


class OnGuildRoleCreate(_OnGuildRoleLifeCycle):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_role_create"""

    __slots__ = ()
    alt_name = "guild_role_create"
    pass


class OnGuildRoleDelete(_OnGuildRoleLifeCycle):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_role_delete"""

    __slots__ = ()
    alt_name = "guild_role_delete"
    pass


class OnGuildRoleUpdate(OnGuildRoleBase):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_role_update"""

    __slots__ = ("before", "after")
    alt_name = "guild_role_update"

    def __init__(self, before: discord.Role, after: discord.Role, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.before = before
        self.after = after


class OnGuildEmojisUpdate(OnGuildBase):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_emojis_update"""

    __slots__ = ("guild", "before", "after")
    alt_name = "guild_emojis_update"

    def __init__(
        self,
        guild: discord.Guild,
        before: Sequence[discord.Emoji],
        after: Sequence[discord.Emoji],
        *args,
        **kwargs,
    ):
        self.guild = guild
        self.before = before
        self.after = after


class OnGuildAvailabilityBase(OnGuildBase):
    """Base class for all guild availability related events.
    Subclasses:
        `OnGuildAvailable`
        `OnGuildUnavailable`
    """

    __slots__ = ("guild",)

    def __init__(self, guild: discord.Guild, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.guild = guild


class OnGuildAvailable(OnGuildAvailabilityBase):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_available"""

    __slots__ = ()
    alt_name = "guild_available"
    pass


class OnGuildUnavailable(OnGuildAvailabilityBase):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_guild_unavailable"""

    __slots__ = ()
    alt_name = "guild_unavailable"
    pass


class OnVoiceStateUpdate(OnGuildBase):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_voice_state_update"""

    __slots__ = ("member", "before", "after")
    alt_name = "voice_state_update"

    def __init__(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.member = member
        self.before = before
        self.after = after


class OnMemberBanBase(OnMemberBase):
    """Base class for all guild member banning related events.
    Subclasses:
        `OnMemberBan`
        `OnMemberUnBan`
    """

    __slots__ = ()
    pass


class _OnMemberBanToggle(OnMemberBanBase):
    __slots__ = ("guild", "user")

    def __init__(
        self,
        guild: discord.Guild,
        user: Union[discord.Member, discord.User],
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.guild = guild
        self.user = user


class OnMemberBan(_OnMemberBanToggle):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_member_ban"""

    __slots__ = ()
    alt_name = "member_ban"
    pass


class OnMemberUnban(_OnMemberBanToggle):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_member_unban"""

    __slots__ = ()
    alt_name = "member_unban"
    pass


class OnInviteBase(OnGuildBase):
    """Base class for all guild invite related events.
    Subclasses:
        `OnInviteCreate`
        `OnInviteDelete`
    """

    __slots__ = ()
    pass


class _OnInviteLifeCycle(OnInviteBase):
    __slots__ = ("invite",)

    def __init__(self, invite: discord.Invite, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.invite = invite


class OnInviteCreate(_OnInviteLifeCycle):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_invite_create"""

    __slots__ = ()
    alt_name = "invite_create"
    pass


class OnInviteDelete(_OnInviteLifeCycle):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_invite_delete"""

    __slots__ = ()
    alt_name = "invite_delete"
    pass


class OnGroupBase(ClientEvent):
    __slots__ = ()
    pass


class _OnGroupLifeCycle(OnGroupBase):
    __slots__ = ("channel", "user")

    def __init__(
        self, channel: discord.GroupChannel, user: discord.User, *args, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.channel = channel
        self.user = user


class OnGroupJoin(_OnGroupLifeCycle):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_group_join"""

    __slots__ = ()
    alt_name = "group_join"
    pass


class OnGroupRemove(_OnGroupLifeCycle):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_group_remove"""

    __slots__ = ()
    alt_name = "group_remove"
    pass


class OnRelationshipBase(ClientEvent):
    __slots__ = ()
    pass


class _OnRelationshipLifeCycle(OnInviteBase):
    __slots__ = ("relationship",)

    def __init__(self, relationship: discord.Relationship, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.relationship = relationship


class OnRelationshipAdd(_OnRelationshipLifeCycle):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_relationship_add"""

    __slots__ = ()
    alt_name = "relationship_add"
    pass


class OnRelationshipRemove(_OnRelationshipLifeCycle):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_relationship_remove"""

    __slots__ = ()
    alt_name = "relationship_remove"
    pass


class OnRelationshipUpdate(OnRelationshipBase):
    """See https://discordpy.readthedocs.io/en/latest/api.html#discord.on_relationship_update"""

    __slots__ = ("before", "after")
    alt_name = "relationship_update"

    def __init__(
        self,
        before: discord.Relationship,
        after: discord.Relationship,
        *args,
        **kwargs,
    ):
        self.before = before
        self.after = after


if __name__ == "__main__":
    print(OnGuildBase.get_subclass_names())
