"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file implements wrapper classes used to capture Discord api events.
"""

from __future__ import annotations
import asyncio
from collections import deque
import datetime
from typing import Any, Callable, Coroutine, Iterable, Optional, Sequence, Union

import discord
from discord.ext import tasks
from pgbot.common import bot

client = bot


class ClientEvent:
    """The base class for all discord API websocket event wrapper objects."""

    def __init__(self, _timestamp: datetime.datetime = None):
        self._timestamp = _timestamp or datetime.datetime.utcnow()

    @property
    def created(self):
        return self._timestamp

    def copy(self):
        return self.__class__(**self.__dict__)

    __copy__ = copy

    def __repr__(self):
        attrs = ' '.join(f"{attr}={val}" for attr, val in self.__dict__.items())
        return f"<{self.__class__.__name__}({attrs})>"


class OnReady(ClientEvent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class OnTypingBase(ClientEvent):
    pass


class OnTyping(OnTypingBase):
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


# class OnGuildTyping(OnTyping):
#     pass

# class OnDMTyping(OnTyping):
#     pass

# class OnGroupTyping(OnDMTyping):
#     pass


class OnMessageBase(ClientEvent):
    pass


class OnMessage(OnMessageBase):
    def __init__(self, message: discord.Message, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.message = message


class OnMessageDelete(OnMessageBase):
    def __init__(self, message: discord.Message, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.message = message


class OnMessageEdit(OnMessageBase):
    def __init__(
        self, before: discord.Message, after: discord.Message, *args, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.before = before
        self.after = after


class OnReactionBase(ClientEvent):
    pass


class OnRawReactionBase(ClientEvent):
    pass


class _OnReactionToggle(OnReactionBase):
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
    pass


class OnReactionRemove(_OnReactionToggle):
    pass


class OnRawReactionAdd(_OnRawReactionToggle):
    pass


class OnRawReactionRemove(_OnRawReactionToggle):
    pass


class OnReactionClear(OnReactionBase):
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
    def __init__(self, reaction: discord.Reaction, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.reaction = reaction


class OnRawReactionClearEmoji(OnRawReactionBase):
    def __init__(
        self,
        payload: discord.RawReactionClearEmojiEvent,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.payload = payload


class OnRawReactionClear(OnRawReactionBase):
    def __init__(
        self,
        payload: discord.RawReactionClearEvent,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.payload = payload


class OnPrivateChannelBase(ClientEvent):
    pass


class _OnPrivateChannelLifeCycle(OnPrivateChannelBase):
    def __init__(self, channel: discord.abc.PrivateChannel, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.channel = channel


class OnPrivateChannelCreate(_OnPrivateChannelLifeCycle):
    pass


class OnPrivateChannelDelete(_OnPrivateChannelLifeCycle):
    pass


class OnPrivateChannelUpdate(OnPrivateChannelBase):
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
    pass


class OnGuildChannelBase(OnGuildBase):
    pass


class _OnGuildChannelLifeCycle(OnGuildChannelBase):
    def __init__(self, channel: discord.abc.GuildChannel, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.channel = channel


class OnGuildChannelCreate(_OnGuildChannelLifeCycle):
    pass


class OnGuildChannelDelete(_OnGuildChannelLifeCycle):
    pass


class OnGuildChannelUpdate(OnGuildChannelBase):
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
    def __init__(self, guild: discord.abc.GuildChannel, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.guild = guild


class OnWebhooksUpdate(OnGuildBase):
    def __init__(self, channel: discord.abc.GuildChannel, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.channel = channel


class OnMemberBase(OnGuildBase):
    pass


class OnMemberTraffic(OnMemberBase):
    def __init__(self, member: discord.Member, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.member = member


class OnMemberJoin(OnMemberTraffic):
    pass


class OnMemberRemove(OnMemberTraffic):
    pass


class OnMemberUpdate(OnMemberBase):
    def __init__(self, before: discord.Member, after: discord.Member, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.before = before
        self.after = after


class OnUserUpdate(ClientEvent):
    def __init__(self, before: discord.User, after: discord.User, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.before = before
        self.after = after


class OnGuildTraffic(OnGuildBase):
    def __init__(self, guild: discord.Guild, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.guild = guild


class OnGuildJoin(OnGuildTraffic):
    pass


class OnGuildRemove(OnGuildTraffic):
    pass


class OnGuildUpdate(OnGuildBase):
    def __init__(self, before: discord.Guild, after: discord.Guild, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.before = before
        self.after = after


class OnGuildRoleBase(OnGuildBase):
    pass


class _OnGuildRoleLifeCycle(OnGuildRoleBase):
    def __init__(self, role: discord.Role, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.role = role


class OnGuildRoleCreate(_OnGuildRoleLifeCycle):
    pass


class OnGuildRoleDelete(_OnGuildRoleLifeCycle):
    pass


class OnGuildRoleUpdate(OnGuildRoleBase):
    def __init__(self, before: discord.Role, after: discord.Role, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.before = before
        self.after = after


class OnGuildEmojisUpdate(OnGuildBase):
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
    pass


class OnGuildAvailability(OnGuildBase):
    def __init__(self, guild: discord.Guild, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.guild = guild


class OnGuildAvailable(OnGuildAvailability):
    pass


class OnGuildUnavailable(OnGuildAvailability):
    pass


class OnVoiceStateUpdate(OnGuildBase):
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


class OnMemberBanBase(OnGuildBase):
    pass


class _OnMemberBanToggle(OnMemberBanBase):
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
    pass


class OnMemberUnban(_OnMemberBanToggle):
    pass


class OnInviteBase(OnGuildBase):
    pass


class _OnInviteLifeCycle(OnInviteBase):
    def __init__(self, invite: discord.Invite, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.invite = invite


class OnInviteCreate(_OnInviteLifeCycle):
    pass


class OnInviteDelete(_OnInviteLifeCycle):
    pass


class OnGroupBase(ClientEvent):
    pass


class _OnGroupLifeCycle(OnGroupBase):
    def __init__(
        self, channel: discord.GroupChannel, user: discord.User, *args, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.channel = channel
        self.user = user


class OnGroupJoin(_OnGroupLifeCycle):
    pass


class OnGroupRemove(_OnGroupLifeCycle):
    pass


class OnRelationshipBase(ClientEvent):
    pass


class _OnRelationshipLifeCycle(OnInviteBase):
    def __init__(self, relationship: discord.Relationship, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.relationship = relationship


class OnRelationshipAdd(_OnRelationshipLifeCycle):
    pass


class OnRelationshipRemove(_OnRelationshipLifeCycle):
    pass


class OnRelationshipUpdate(OnRelationshipBase):
    def __init__(
        self,
        before: discord.Relationship,
        after: discord.Relationship,
        *args,
        **kwargs,
    ):
        self.before = before
        self.after = after
