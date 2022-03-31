"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file is the main file of the PygameCommunityBot source. Running this
starts the bot
"""
import datetime
import discord
import pickle
from pgbot import common
from pgbot import events
import pgbot

from typing import Any, Callable, Coroutine, Iterable, Optional, Sequence, Union

bot = common.bot


@bot.event
async def on_ready():
    """
    Startup routines when the bot starts
    """
    await pgbot.init()
    if common.job_manager is not None and common.job_manager.is_running():
        common.job_manager.dispatch_event(events.OnReady())


@bot.event
async def on_member_join(member: discord.Member):
    """
    This function handles the greet message when a new member joins
    """
    if member.bot:
        return

    await pgbot.member_join(member)
    if common.job_manager is not None and common.job_manager.is_running():
        common.job_manager.dispatch_event(
            events.OnMemberJoin(
                member,
                event_created_at=member.joined_at.astimezone(datetime.timezone.utc),
            )
        )


@bot.event
async def on_member_remove(member: discord.Member):
    """
    Routines to run when people leave the server
    """
    await pgbot.clean_db_member(member)
    if common.job_manager is not None and common.job_manager.is_running():
        common.job_manager.dispatch_event(events.OnMemberRemove(member))


@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    if common.job_manager is not None and common.job_manager.is_running():
        common.job_manager.dispatch_event(events.OnMemberUpdate(before, after))


@bot.event
async def on_member_ban(
    guild: discord.Guild, user: Union[discord.Member, discord.User]
):
    if common.job_manager is not None and common.job_manager.is_running():
        common.job_manager.dispatch_event(events.OnMemberBan(guild, user))


@bot.event
async def on_member_unban(guild: discord.Guild, user: discord.User):
    if common.job_manager is not None and common.job_manager.is_running():
        common.job_manager.dispatch_event(events.OnMemberUnban(guild, user))


@bot.event
async def on_message(message: discord.Message):
    """
    This function is called for every message by user.
    """
    if message.author.bot:
        return

    await pgbot.handle_message(message)
    if common.job_manager is not None and common.job_manager.is_running():
        common.job_manager.dispatch_event(
            events.OnMessage(
                message,
                event_created_at=message.created_at.astimezone(datetime.timezone.utc),
            )
        )


@bot.event
async def on_message_delete(message: discord.Message):
    """
    This function is called for every message deleted by user.
    """
    await pgbot.message_delete(message)
    if common.job_manager is not None and common.job_manager.is_running():
        common.job_manager.dispatch_event(events.OnMessageDelete(message))


@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    """
    This function is called for every message edited by user.
    """
    if after.author.bot:
        return

    await pgbot.message_edit(before, after)

    if common.job_manager is not None and common.job_manager.is_running():
        common.job_manager.dispatch_event(
            events.OnMessageEdit(
                before,
                after,
            )
        )


@bot.event
async def on_reaction_add(
    reaction: discord.Reaction, user: Union[discord.Member, discord.User]
):
    if common.job_manager is not None and common.job_manager.is_running():
        common.job_manager.dispatch_event(events.OnReactionAdd(reaction, user))


@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    """
    This function is called for every reaction added by user.
    """
    if payload.member is None or payload.member.bot:
        return

    await pgbot.raw_reaction_add(payload)
    if common.job_manager is not None and common.job_manager.is_running():
        common.job_manager.dispatch_event(events.OnRawReactionAdd(payload))


@bot.event
async def on_reaction_remove(
    reaction: discord.Reaction, user: Union[discord.Member, discord.User]
):
    if common.job_manager is not None and common.job_manager.is_running():
        common.job_manager.dispatch_event(events.OnReactionRemove(reaction, user))


@bot.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
    """
    This function is called for every reaction added by user.
    """
    if payload.member is None or payload.member.bot:
        return

    await pgbot.raw_reaction_add(payload)

    if common.job_manager is not None and common.job_manager.is_running():
        common.job_manager.dispatch_event(events.OnRawReactionRemove(payload))


@bot.event
async def on_reaction_clear(
    message: discord.Message, reactions: list[discord.Reaction]
):
    if common.job_manager is not None and common.job_manager.is_running():
        common.job_manager.dispatch_event(events.OnReactionClear(message, reactions))


@bot.event
async def on_raw_reaction_clear(payload: discord.RawReactionClearEvent):
    if common.job_manager is not None and common.job_manager.is_running():
        common.job_manager.dispatch_event(events.OnRawReactionClear(payload))


@bot.event
async def on_reaction_clear_emoji(reaction: discord.Reaction):
    if common.job_manager is not None and common.job_manager.is_running():
        common.job_manager.dispatch_event(events.OnReactionClearEmoji(reaction))


@bot.event
async def on_raw_reaction_clear_emoji(payload: discord.RawReactionClearEmojiEvent):
    if common.job_manager is not None and common.job_manager.is_running():
        common.job_manager.dispatch_event(events.OnRawReactionClearEmoji(payload))


@bot.event
async def on_private_channel_create(channel: discord.abc.PrivateChannel):
    if common.job_manager is not None and common.job_manager.is_running():
        common.job_manager.dispatch_event(events.OnPrivateChannelCreate(channel))


@bot.event
async def on_private_channel_delete(channel: discord.abc.PrivateChannel):
    if common.job_manager is not None and common.job_manager.is_running():
        common.job_manager.dispatch_event(events.OnPrivateChannelDelete(channel))


@bot.event
async def on_private_channel_update(
    before: discord.GroupChannel, after: discord.GroupChannel
):
    if common.job_manager is not None and common.job_manager.is_running():
        common.job_manager.dispatch_event(events.OnPrivateChannelUpdate(before, after))


@bot.event
async def on_private_channel_pins_update(
    channel: discord.abc.PrivateChannel, last_pin: Optional[datetime.datetime]
):
    if common.job_manager is not None and common.job_manager.is_running():
        common.job_manager.dispatch_event(
            events.OnPrivateChannelPinsUpdate(channel, last_pin)
        )


@bot.event
async def on_guild_channel_create(channel: discord.abc.GuildChannel):
    if common.job_manager is not None and common.job_manager.is_running():
        common.job_manager.dispatch_event(events.OnGuildChannelCreate(channel))


@bot.event
async def on_guild_channel_delete(channel: discord.abc.GuildChannel):
    if common.job_manager is not None and common.job_manager.is_running():
        common.job_manager.dispatch_event(events.OnGuildChannelDelete(channel))


@bot.event
async def on_guild_channel_update(
    before: discord.abc.GuildChannel, after: discord.abc.GuildChannel
):
    if common.job_manager is not None and common.job_manager.is_running():
        common.job_manager.dispatch_event(events.OnGuildChannelUpdate(before, after))


@bot.event
async def on_guild_channel_pins_update(
    channel: discord.abc.GuildChannel, last_pin: Optional[datetime.datetime]
):
    if common.job_manager is not None and common.job_manager.is_running():
        common.job_manager.dispatch_event(
            events.OnGuildChannelPinsUpdate(channel, last_pin)
        )


@bot.event
async def on_guild_integrations_update(guild: discord.Guild):
    if common.job_manager is not None and common.job_manager.is_running():
        common.job_manager.dispatch_event(events.OnGuildIntegrationsUpdate(guild))


@bot.event
async def on_webhooks_update(channel: discord.abc.GuildChannel):
    if common.job_manager is not None and common.job_manager.is_running():
        common.job_manager.dispatch_event(events.OnWebhooksUpdate(channel))


@bot.event
async def on_user_update(before: discord.User, after: discord.User):
    if common.job_manager is not None and common.job_manager.is_running():
        common.job_manager.dispatch_event(events.OnUserUpdate(before, after))


@bot.event
async def on_guild_join(guild: discord.Guild):
    if common.job_manager is not None and common.job_manager.is_running():
        common.job_manager.dispatch_event(events.OnGuildJoin(guild))


@bot.event
async def on_guild_remove(guild: discord.Guild):
    if common.job_manager is not None and common.job_manager.is_running():
        common.job_manager.dispatch_event(events.OnGuildRemove(guild))


@bot.event
async def on_guild_update(before: discord.Guild, after: discord.Guild):
    if common.job_manager is not None and common.job_manager.is_running():
        common.job_manager.dispatch_event(events.OnGuildUpdate(before, after))


@bot.event
async def on_guild_role_create(role: discord.Role):
    if common.job_manager is not None and common.job_manager.is_running():
        common.job_manager.dispatch_event(events.OnGuildRoleCreate(role))


@bot.event
async def on_guild_role_delete(role: discord.Role):
    if common.job_manager is not None and common.job_manager.is_running():
        common.job_manager.dispatch_event(events.OnGuildRoleDelete(role))


@bot.event
async def on_guild_role_update(before: discord.Role, after: discord.Role):
    if common.job_manager is not None and common.job_manager.is_running():
        common.job_manager.dispatch_event(events.OnGuildRoleUpdate(before, after))


@bot.event
async def on_guild_emojis_update(
    guild: discord.Guild,
    before: Sequence[discord.Emoji],
    after: Sequence[discord.Emoji],
):
    if common.job_manager is not None and common.job_manager.is_running():
        common.job_manager.dispatch_event(
            events.OnGuildEmojisUpdate(guild, before, after)
        )


@bot.event
async def on_guild_available(guild: discord.Guild):
    if common.job_manager is not None and common.job_manager.is_running():
        common.job_manager.dispatch_event(events.OnGuildAvailable(guild))


@bot.event
async def on_guild_unavailable(guild: discord.Guild):
    if common.job_manager is not None and common.job_manager.is_running():
        common.job_manager.dispatch_event(events.OnGuildUnavailable(guild))


@bot.event
async def on_voice_state_update(
    member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
):
    if common.job_manager is not None and common.job_manager.is_running():
        common.job_manager.dispatch_event(
            events.OnVoiceStateUpdate(member, before, after)
        )


@bot.event
async def on_invite_create(invite: discord.Invite):
    if common.job_manager is not None and common.job_manager.is_running():
        common.job_manager.dispatch_event(events.OnInviteCreate(invite))


@bot.event
async def on_invite_delete(invite: discord.Invite):
    if common.job_manager is not None and common.job_manager.is_running():
        common.job_manager.dispatch_event(events.OnInviteDelete(invite))


if __name__ == "__main__":
    pgbot.run()
