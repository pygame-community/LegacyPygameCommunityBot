"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file defines a "routine" function, that gets called on routine.
It gets called every 5 seconds or so.
"""
import datetime
import random
import time

import discord

from pgbot import db, emotion

reminder_obj = db.DiscordDB("reminders")


def handle_confused_emotion():
    """
    Handles the routine of the confused emotion
    Every 12h, the confused value would lower by given amount
    """
    now = time.time()
    confused = emotion.get("confused")
    cnt = 0
    try:
        for exception_time in confused["context"]:
            if abs(now - exception_time[0]) > 24 * 60 * 60:
                confused["context"].remove(exception_time)
                cnt += exception_time[1]
        confused["value"] -= cnt
        emotion.override("confused", confused)
    except TypeError:
        pass


async def handle_reminders(guild: discord.Guild):
    """
    Handle reminder routines
    """
    reminders = reminder_obj.get({})

    new_reminders = {}
    for mem_id, reminder_dict in reminders.items():
        for dt, (msg, chan_id, msg_id) in reminder_dict.items():
            if datetime.datetime.utcnow() >= dt:
                content = f"__**Reminder for you:**__\n>>> {msg}"

                channel = guild.get_channel(chan_id)
                if channel is None:
                    # Channel does not exist in the guild, DM the user
                    try:
                        member = await guild.fetch_member(mem_id)
                        if member.dm_channel is None:
                            await member.create_dm()

                        await member.dm_channel.send(content=content)
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


async def routine(guild: discord.Guild):
    """
    Function that gets called routinely. This function inturn, calles other
    routine functions to handle stuff
    """
    handle_confused_emotion()
    await handle_reminders(guild)
    if random.randint(0, 3) == 0:
        emotion.update("bored", 1)
