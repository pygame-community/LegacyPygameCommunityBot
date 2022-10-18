"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present pygame-community

This file defines a "routine" function, that gets called on routine.
It gets called every 5 seconds or so.
"""

import asyncio
from concurrent.futures import thread
import datetime
import io
import os
import sys
import time

import discord
from discord.ext import tasks
import snakecore

from pgbot import common
from pgbot.utils.utils import (
    fetch_last_thread_activity_dt,
    message_delete_reaction_listener,
)


async def handle_reminders(reminder_obj: snakecore.storage.DiscordStorage):
    """
    Handle reminder routines
    """
    new_reminders = {}
    for mem_id, reminder_dict in reminder_obj.obj.items():
        for dt, (msg, chan_id, msg_id) in reminder_dict.items():
            if datetime.datetime.now(datetime.timezone.utc) >= dt:
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

    reminder_obj.obj = new_reminders


@tasks.loop(seconds=5, reconnect=True)
async def handle_console():
    """
    Function for sending the console output to the bot-console channel.
    """
    if common.stdout is None:
        return

    contents = common.stdout.getvalue()
    # reset StringIO object for reuse
    common.stdout.truncate(0)
    common.stdout.seek(0)

    # hide path data
    contents = contents.replace(os.getcwd(), "PgBot")
    if os.name == "nt":
        contents = contents.replace(os.path.dirname(sys.executable), "Python")

    if common.GENERIC or common.console_channel is None:
        # just return if we cannot sent it on discord
        return

    # the actual message limit is 2000. But since the message is sent with
    # code ticks, we need room for those, so 1980
    for content in snakecore.utils.split_long_message(contents, 1980):
        content = content.strip()
        if not content:
            continue

        await common.console_channel.send(
            content=snakecore.utils.code_block(content, code_type="ansi")
        )


@tasks.loop(seconds=3, reconnect=True)
async def routine():
    """
    Function that gets called routinely. This function inturn, calles other
    routine functions to handle stuff
    """
    async with snakecore.storage.DiscordStorage("reminders") as storage_obj:
        await handle_reminders(storage_obj)

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


@tasks.loop(hours=1, reconnect=True)
async def inactive_help_thread_alert():
    async with snakecore.storage.DiscordStorage(
        "inactive_help_threads", dict
    ) as storage_obj:
        # a dict of forum channel IDs mapping to dicts of help thread ids mapping to
        # UNIX timestamps which represent the last time activity occured.
        inactive_help_thread_ids: dict[int, dict[int, int]] = storage_obj.obj

        for forum_channel in [
            common.bot.get_channel(fid) or (await common.bot.fetch_channel(fid))
            for fid in common.GuildConstants.HELP_FORUM_CHANNEL_IDS.values()
        ]:
            if not isinstance(forum_channel, discord.ForumChannel):
                return

            now_ts = time.time()
            for help_thread in forum_channel.threads:
                try:
                    if not help_thread.created_at:
                        continue
                    last_active_ts = help_thread.created_at.timestamp()

                    if not (
                        help_thread.archived
                        or help_thread.locked
                        or help_thread.flags.pinned
                    ) and not any(
                        tag.name.lower() == "solved" for tag in help_thread.applied_tags
                    ):
                        last_active_ts = (
                            await fetch_last_thread_activity_dt(help_thread)
                        ).timestamp()

                        if (now_ts - last_active_ts) > (3600 * 23 + 1800):  # 23h30m
                            if forum_channel.id not in inactive_help_thread_ids:
                                inactive_help_thread_ids[forum_channel.id] = {}

                            if (
                                help_thread.id
                                not in inactive_help_thread_ids[forum_channel.id]
                                or inactive_help_thread_ids[forum_channel.id][
                                    help_thread.id
                                ]
                                < last_active_ts
                            ):
                                caution_message = await help_thread.send(
                                    f"help-post-inactive(<@{help_thread.owner_id}>)",
                                    embed=discord.Embed(
                                        title="Your help post has gone inactive... 💤",
                                        description=f"Your help post was last active **<t:{int(last_active_ts)}:R>** ."
                                        "\nHas your issue been solved? If so, remember to tag your post with a 'Solved' tag.\n\n"
                                        "To make changes to your post's tags, either right-click on "
                                        "it (desktop/web) or click and hold on it (mobile), then click "
                                        "on **'Edit Tags'** to see a tag selection menu. Remember to save "
                                        "your changes after selecting the correct tag(s).\n\n"
                                        "**Mark all messages you find helpful here with a ✅ reaction please** "
                                        "<:pg_robot:837389387024957440>\n\n"
                                        "*If your issue has't been solved, you may "
                                        "either wait for help or close this post.*",
                                        color=0x888888,
                                    ),
                                )
                                inactive_help_thread_ids[forum_channel.id][
                                    help_thread.id
                                ] = caution_message.created_at.timestamp()
                                common.hold_task(
                                    asyncio.create_task(
                                        message_delete_reaction_listener(
                                            caution_message,
                                            (
                                                help_thread.owner
                                                or common.bot.get_user(
                                                    help_thread.owner_id
                                                )
                                                or (
                                                    await common.bot.fetch_user(
                                                        help_thread.owner_id
                                                    )
                                                )
                                            ),
                                            emoji="🗑",
                                            role_whitelist=common.GuildConstants.ADMIN_ROLES,
                                            timeout=120,
                                        )
                                    )
                                )
                except discord.HTTPException:
                    pass

        storage_obj.obj = inactive_help_thread_ids


@tasks.loop(hours=1, reconnect=True)
async def force_help_thread_archive_after_timeout():
    for forum_channel in [
        common.bot.get_channel(fid) or (await common.bot.fetch_channel(fid))
        for fid in common.GuildConstants.HELP_FORUM_CHANNEL_IDS.values()
    ]:
        if not isinstance(forum_channel, discord.ForumChannel):
            return

        now_ts = time.time()
        for help_thread in forum_channel.threads:
            try:
                if not help_thread.created_at:
                    continue

                if not (
                    help_thread.archived
                    or help_thread.locked
                    or help_thread.flags.pinned
                ):
                    last_active_ts = (
                        await fetch_last_thread_activity_dt(help_thread)
                    ).timestamp()
                    if (
                        now_ts - last_active_ts
                    ) / 60.0 > help_thread.auto_archive_duration:
                        await help_thread.edit(
                            archived=True,
                            reason="This help thread has been archived "
                            "after exceeding its inactivity timeout.",
                        )
            except discord.HTTPException:
                pass
