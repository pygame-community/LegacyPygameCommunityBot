"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file defines a "routine" function, that gets called on routine.
It gets called every 5 seconds or so.
"""
import datetime
import random

import discord

from pgbot import db, emotion, common

reminder_obj = db.DiscordDB("reminders")


async def handle_reminders(guild):
    """
    Handle reminder routines
    """
    reminders = await reminder_obj.get({})

    new_reminders = {}
    for mem_id, reminder_dict in reminders.items():
        for dt, (msg, chan_id, msg_id) in reminder_dict.items():
            if datetime.datetime.utcnow() >= dt:
                # We have to send a reminder. Try to reply to original message
                # if that fails, DM them
                channel = guild.get_channel(chan_id)
                if channel is None:
                    continue

                content = f"__**Reminder for <@!{mem_id}>:**__\n>>> {msg}"
                message = await channel.fetch_message(msg_id)
                allowed_mentions = discord.AllowedMentions()
                allowed_mentions.users = [message.author]
                try:
                    await message.reply(
                        content=content, allowed_mentions=allowed_mentions
                    )
                except discord.HTTPException:
                    # The message probably got deleted, try to resend in channel
                    try:
                        await channel.send(
                            content=content, allowed_mentions=allowed_mentions
                        )
                    except discord.HTTPException:
                        pass
            else:
                if mem_id not in new_reminders:
                    new_reminders[mem_id] = {}

                new_reminders[mem_id][dt] = (msg, chan_id, msg_id)

    if reminders != new_reminders:
        await reminder_obj.write(new_reminders)


async def routine(guild):
    """
    Function that gets called routinely. This function inturn, calles other
    routine functions to handle stuff
    """
    await handle_reminders(guild)
    if not random.randint(0, 3):
        await emotion.update("bored", 1)
