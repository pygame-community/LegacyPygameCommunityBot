"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present pygame-community

This file defines a "routine" function, that gets called on routine.
It gets called every 5 seconds or so.
"""

import asyncio
import datetime
import os
import sys
import time

import discord
from discord.ext import tasks
import snakecore

from pgbot import common
from pgbot.utils.utils import (
    fetch_last_thread_activity_dt,
    fetch_last_thread_message,
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
    for forum_channel in [
        common.bot.get_channel(fid) or (await common.bot.fetch_channel(fid))
        for fid in common.GuildConstants.HELP_FORUM_CHANNEL_IDS.values()
    ]:
        if not isinstance(forum_channel, discord.ForumChannel):
            return

        now_ts = time.time()
        for _, help_thread in {
            thread.id: thread
            for thread in forum_channel.threads
            + [thr async for thr in forum_channel.archived_threads(limit=20)]
        }.items():
            try:
                if not help_thread.created_at:
                    continue
                last_active_ts = help_thread.created_at.timestamp()

                if not (help_thread.locked or help_thread.flags.pinned) and not any(
                    tag.name.lower().startswith("solved")
                    for tag in help_thread.applied_tags
                ):
                    last_active_ts = (
                        await fetch_last_thread_activity_dt(help_thread)
                    ).timestamp()

                    if (now_ts - last_active_ts) > (3600 * 23 + 1800):  # 23h30m
                        if (
                            help_thread.id not in common.inactive_help_thread_data
                            or common.inactive_help_thread_data[help_thread.id][
                                "last_active_ts"
                            ]
                            < last_active_ts
                        ):
                            alert_message = await help_thread.send(
                                f"help-post-inactive(<@{help_thread.owner_id}>, **{help_thread.name}**)",
                                embed=discord.Embed(
                                    title="Your help post has gone inactive... 💤",
                                    description=f"Your help post was last active **<t:{int(last_active_ts)}:R>** ."
                                    "\nHas your issue been solved? If so, mark it as **Solved** by "
                                    "doing one of these:\n\n"
                                    "  **• React on your starter message with ✅**.\n"
                                    "  **• Right-click on your post (click and hold on mobile), "
                                    "go to 'Edit Tags', select the `✅ Solved` tag and save your changes.**\n\n"
                                    "**Mark all messages you find helpful here with a ✅ reaction please** "
                                    "<:pg_robot:837389387024957440>\n\n"
                                    "*If your issue has't been solved, you may "
                                    "either wait for help or close this post.*",
                                    color=0x888888,
                                ),
                            )
                            common.inactive_help_thread_data[help_thread.id] = {
                                "thread_id": help_thread.id,
                                "last_active_ts": alert_message.created_at.timestamp(),
                                "alert_message_id": alert_message.id,
                            }
                    elif (
                        help_thread.id in common.inactive_help_thread_data
                        and (
                            alert_message_id := common.inactive_help_thread_data[
                                help_thread.id
                            ].get("alert_message_id", None)
                        )
                    ) and (
                        (
                            partial_alert_message := help_thread.get_partial_message(
                                alert_message_id
                            )
                        ).created_at.timestamp()
                        < last_active_ts  # someone messaged into the channel
                    ):
                        try:
                            last_message = await fetch_last_thread_message(help_thread)
                            if last_message and not last_message.is_system():
                                try:
                                    await partial_alert_message.delete()
                                except discord.NotFound:
                                    pass
                                finally:
                                    del common.inactive_help_thread_data[
                                        help_thread.id
                                    ]["alert_message_id"]
                        except discord.NotFound:
                            pass

            except discord.HTTPException:
                pass


@tasks.loop(hours=1, reconnect=True)
async def delete_help_threads_without_starter_message():
    for forum_channel in [
        common.bot.get_channel(fid) or (await common.bot.fetch_channel(fid))
        for fid in common.GuildConstants.HELP_FORUM_CHANNEL_IDS.values()
    ]:
        if not isinstance(forum_channel, discord.ForumChannel):
            return

        for help_thread in forum_channel.threads:
            try:
                try:
                    starter_message = (
                        help_thread.starter_message
                        or await help_thread.fetch_message(help_thread.id)
                    )
                except discord.NotFound:
                    pass
                else:
                    continue  # starter message still exists, skip

                member_msg_count = 0
                async for thread_message in help_thread.history(
                    limit=max(help_thread.message_count, 60)
                ):
                    if (
                        not thread_message.author.bot
                        and thread_message.type is discord.MessageType.default
                    ):
                        member_msg_count += 1
                        if member_msg_count > 29:
                            break

                if member_msg_count < 30:
                    common.hold_task(
                        asyncio.create_task(_schedule_help_thread_deletion(help_thread))
                    )
            except discord.HTTPException:
                pass


async def _schedule_help_thread_deletion(thread: discord.Thread):
    await thread.send(
        embed=discord.Embed(
            title="Post scheduled for deletion",
            description=(
                "Someone deleted the starter message of this post.\n\n"
                "Since it contains less than 30 messages sent by "
                "server members, it will be deleted "
                f"**<t:{int(time.time()+300)}:R>**."
            ),
            color=0x551111,
        )
    )
    await asyncio.sleep(300)
    await thread.delete()


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

                        thread_edits = {}
                        thread_edits["archived"] = True

                        if (
                            any(
                                tag.name.lower().startswith("solved")
                                for tag in help_thread.applied_tags
                            )
                            and help_thread.slowmode_delay
                            == forum_channel.default_thread_slowmode_delay
                        ):
                            # solved and no overridden slowmode
                            thread_edits["slowmode_delay"] = 60  # seconds

                        if not (
                            help_thread.name.endswith(
                                owner_id_suffix := f" | {help_thread.owner_id}"
                            )
                            or str(help_thread.owner_id) in help_thread.name
                        ):  # wait for a few event loop iterations, before doing a second,
                            # check, to be sure that a bot edit hasn't already occured
                            thread_edits["archived"] = False
                            thread_edits["name"] = (
                                help_thread.name
                                if len(help_thread.name) < 72
                                else help_thread.name[:72] + "..."
                            ) + owner_id_suffix

                        await help_thread.edit(
                            reason="This help thread has been closed "
                            "after exceeding its inactivity timeout.",
                            **thread_edits,
                        )
            except discord.HTTPException:
                pass
