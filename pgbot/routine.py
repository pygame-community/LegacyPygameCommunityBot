"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file defines a "routine" function, that gets called on routine.
It gets called every 5 seconds or so.
"""

import asyncio
import datetime
import io
import os
import random
import sys
from typing import Union

import discord
from discord.ext import tasks

from pgbot import common, db, emotion
from pgbot.utils import utils


async def handle_reminders(reminder_obj: db.DiscordDB):
    """
    Handle reminder routines
    """
    reminders = reminder_obj.get({})

    new_reminders = {}
    for mem_id, reminder_dict in reminders.items():
        for dt, (msg, chan_id, msg_id) in reminder_dict.items():
            if datetime.datetime.utcnow() >= dt:
                content = f"__**Reminder for you:**__\n>>> {msg}"

                channel = None
                if common.guild is not None:
                    channel = common.guild.get_channel(chan_id)
                if not isinstance(channel, discord.TextChannel):
                    # Channel does not exist in the guild, DM the user
                    try:
                        user = await common.bot.fetch_user(mem_id)
                        if user.dm_channel is None:
                            await user.create_dm()

                        await user.dm_channel.send(content=content)
                    except discord.HTTPException:
                        pass
                    continue

                allowed_mentions = discord.AllowedMentions.none()
                allowed_mentions.replied_user = True
                try:
                    message = await channel.fetch_message(msg_id)
                    await message.reply(
                        content=content, allowed_mentions=allowed_mentions
                    )
                except discord.HTTPException:
                    # The message probably got deleted, try to resend in channel
                    allowed_mentions.users = [discord.Object(mem_id)]
                    content = f"__**Reminder for <@!{mem_id}>:**__\n>>> {msg}"
                    try:
                        await channel.send(
                            content=content,
                            allowed_mentions=allowed_mentions,
                        )
                    except discord.HTTPException:
                        pass
            else:
                if mem_id not in new_reminders:
                    new_reminders[mem_id] = {}

                new_reminders[mem_id][dt] = (msg, chan_id, msg_id)

    if reminders != new_reminders:
        reminder_obj.write(new_reminders)


@tasks.loop(seconds=5)
async def handle_console():
    """
    Function for sending the console output to the bot-console channel.
    """
    if common.stdout is None:
        return

    contents = common.stdout.getvalue()
    sys.stdout = sys.stderr = common.stdout = io.StringIO()

    # hide path data
    contents = contents.replace(os.getcwd(), "PgBot")
    if os.name == "nt":
        contents = contents.replace(os.path.dirname(sys.executable), "Python")

    if common.GENERIC or common.console_channel is None:
        # just print error to shell if we cannot sent it on discord
        print(contents, file=sys.__stdout__)
        return

    # the actual message limit is 2000. But since the message is sent with
    # code ticks, we need room for those, so 1980
    for content in utils.split_long_message(contents, 1980):
        content = content.strip()
        if not content:
            continue

        await common.console_channel.send(
            content=utils.code_block(content, code_type="cmd")
        )


async def message_delete_reaction_listener(
    msg: discord.Message,
    cmd_invoker: Union[discord.Member, discord.User],
    emoji_str: str,
):
    try:
        try:
            await msg.add_reaction(emoji_str)
        except discord.HTTPException:
            return

        check = None
        if isinstance(cmd_invoker, discord.Member):
            check = (
                lambda event: event.message_id == msg.id
                and (event.guild_id == getattr(msg.guild, "id", None))
                and (
                    event.user_id == cmd_invoker.id
                    or any(
                        role.id in common.ServerConstants.ADMIN_ROLES
                        for role in cmd_invoker.roles[1:]
                    )
                )
                and event.emoji.is_unicode_emoji()
                and event.emoji.name == emoji_str
            )
        elif isinstance(cmd_invoker, discord.User):
            check = (
                lambda event: event.message_id == msg.id
                and (event.guild_id == getattr(msg.guild, "id", None))
                and (event.user_id == cmd_invoker.id)
                and event.emoji.is_unicode_emoji()
                and event.emoji.name == emoji_str
            )
        else:
            raise TypeError(
                f"argument 'invoker' expected discord.Member/.User, not {cmd_invoker.__class__.__name__}"
            )

        event: discord.RawReactionActionEvent = await common.bot.wait_for(
            "raw_reaction_add", check=check, timeout=20
        )

        try:
            await msg.delete()
        except discord.HTTPException:
            pass

    except (asyncio.TimeoutError, asyncio.CancelledError) as a:
        try:
            await msg.clear_reaction(emoji_str)
        except discord.HTTPException:
            pass

        if isinstance(a, asyncio.CancelledError):
            raise a


@tasks.loop(seconds=3)
async def routine():
    """
    Function that gets called routinely. This function inturn, calles other
    routine functions to handle stuff
    """
    async with db.DiscordDB("reminders") as db_obj:
        await handle_reminders(db_obj)

    if random.randint(0, 4) == 0:
        await emotion.update("bored", 1)

    await common.bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="discord.io/pygame_community",
        )
    )
    await asyncio.sleep(3)
    await common.bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.playing,
            name="in discord.io/pygame_community",
        )
    )
