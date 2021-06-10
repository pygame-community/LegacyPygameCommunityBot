"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file is the main file of pgbot subdir 
"""

import discord

import asyncio
import os
import random
import signal
import sys
import io

import discord
from discord.embeds import Embed
import pygame

from pgbot import commands, common, db, emotion, routine
from pgbot.utils import embed_utils


async def _init():
    """
    Startup call helper for pygame bot
    """
    if not common.TEST_MODE:
        # when we are not in test mode, we want stout/stderr to appear on a console
        # in a discord channel
        sys.stdout = sys.stderr = common.stdout = io.StringIO()

    print("The PygameCommunityBot is now online!")
    print("Server(s):")

    for server in common.bot.guilds:
        prim = ""

        if common.guild is None and (
            common.GENERIC or server.id == common.ServerConstants.SERVER_ID
        ):
            prim = "| Primary Guild"
            common.guild = server

        print(" -", server.name, "| Number of channels:", len(server.channels), prim)
        if common.GENERIC:
            continue

        for channel in server.channels:
            if channel.id == common.ServerConstants.DB_CHANNEL_ID:
                common.db_channel = channel
                await db.init()
            elif channel.id == common.ServerConstants.LOG_CHANNEL_ID:
                common.log_channel = channel
            elif channel.id == common.ServerConstants.ARRIVALS_CHANNEL_ID:
                common.arrivals_channel = channel
            elif channel.id == common.ServerConstants.GUIDE_CHANNEL_ID:
                common.guide_channel = channel
            elif channel.id == common.ServerConstants.ROLES_CHANNEL_ID:
                common.roles_channel = channel
            elif channel.id == common.ServerConstants.ENTRIES_DISCUSSION_CHANNEL_ID:
                common.entries_discussion_channel = channel
            elif channel.id == common.ServerConstants.CONSOLE_CHANNEL_ID:
                common.console_channel = channel
            elif channel.id == common.ServerConstants.RULES_CHANNEL_ID:
                common.rules_channel = channel
            for key, value in common.ServerConstants.ENTRY_CHANNEL_IDS.items():
                if channel.id == value:
                    common.entry_channels[key] = channel


async def init():
    """
    Startup call helper for pygame bot
    """
    try:
        await _init()
    except:
        # error happened in the first init sequence. report error to stdout/stderr
        # note that the chances of this happening are pretty slim, but you never know
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        raise

    routine.handle_console.start()
    routine.routine.start()

    if common.guild is None:
        raise RuntimeWarning(
            "Primary guild was not set. Some features of bot would not run as usual."
            " This includes bot reminders and some commands on DM"
        )


def format_entries_message(msg: discord.Message, entry_type: str):
    """
    Formats an entries message to be reposted in discussion channel
    """
    title = f"New {entry_type.lower()} in #{common.ZERO_SPACE}{common.entry_channels[entry_type].name}"

    attachments = ""
    if msg.attachments:
        for i, attachment in enumerate(msg.attachments):
            attachments += f" • [Link {i + 1}]({attachment.url})\n"
    else:
        attachments = "No attachments"

    desc = msg.content if msg.content else "No description provided."

    fields = [
        ["**Posted by**", msg.author.mention, True],
        ["**Original msg.**", f"[View]({msg.jump_url})", True],
        ["**Attachments**", attachments, True],
        ["**Description**", desc, True],
    ]
    return title, fields


async def member_join(member: discord.Member):
    """
    This function handles the greet message when a new member joins
    """
    if common.TEST_MODE or member.bot or common.GENERIC:
        # Do not greet people in test mode, or if a bot joins
        return

    greet = random.choice(common.BOT_WELCOME_MSG["greet"])
    check = random.choice(common.BOT_WELCOME_MSG["check"])

    grab = random.choice(common.BOT_WELCOME_MSG["grab"])
    end = random.choice(common.BOT_WELCOME_MSG["end"])

    # This function is called right when a member joins, even before the member
    # finishes the join screening. So we wait for that to happen and then send
    # the message. Wait for a maximum of six hours.
    for _ in range(10800):
        await asyncio.sleep(2)

        if not member.pending:
            # Don't use embed here, because pings would not work
            await common.arrivals_channel.send(
                f"{greet} {member.mention}! {check} "
                + f"{common.guide_channel.mention}{grab} "
                + f"{common.roles_channel.mention}{end}"
            )
            # new member joined, yaayyy, snek is happi
            emotion.update("happy", 20)
            return


async def clean_db_member(member: discord.Member):
    """
    This function silently removes users from database messages
    """
    for table_name in ("stream", "reminders", "clock"):
        db_obj = db.DiscordDB(table_name)
        data = db_obj.get({})
        if member.id in data:
            data.pop(member)
            db_obj.write(data)


async def message_delete(msg: discord.Message):
    """
    This function is called for every message deleted by user.
    """
    if msg.id in common.cmd_logs.keys():
        del common.cmd_logs[msg.id]

    elif msg.author.id == common.bot.user.id:
        for log in common.cmd_logs.keys():
            if msg.id is not None and common.cmd_logs[log].id is not None:
                if common.cmd_logs[log].id == msg.id:
                    del common.cmd_logs[log]
                    return

    if common.GENERIC:
        return

    if msg.channel in common.entry_channels.values():
        history = await common.entries_discussion_channel.history(
            around=msg.created_at
        ).flatten()
        message: discord.Message
        for message in history:
            embed: discord.embeds.Embed = message.embeds[0]
            link = embed.fields[1].value
            if int(link.split("/")[6][:-1]) == msg.id:
                await message.delete()


async def message_edit(old: discord.Message, new: discord.Message):
    """
    This function is called for every message edited by user.
    """
    if new.content.startswith(common.PREFIX):
        try:
            if new.id in common.cmd_logs.keys():
                await commands.handle(new, common.cmd_logs[new.id])
        except discord.HTTPException:
            pass


async def handle_message(msg: discord.Message):
    """
    Handle a message posted by user
    """
    if msg.type == discord.MessageType.premium_guild_subscription:
        await emotion.server_boost(msg)

    if msg.content.startswith(common.PREFIX):
        ret = await commands.handle(msg)
        if ret is not None:
            common.cmd_logs[msg.id] = ret

        if len(common.cmd_logs) > 100:
            del common.cmd_logs[list(common.cmd_logs.keys())[0]]

        emotion.update("bored", -10)

    elif not common.TEST_MODE:
        await emotion.check_bonk(msg)

        # Check for these specific messages, do not try to generalise, because we do not
        # want the bot spamming the bydariogamer quote
        # no_mentions = discord.AllowedMentions.none()
        # if unidecode.unidecode(msg.content.lower()) in common.DEAD_CHAT_TRIGGERS:
        #     # ded chat makes snek sad
        #     await msg.channel.send(
        #         "good." if emotion.get("anger") >= 60 else common.BYDARIO_QUOTE,
        #         allowed_mentions=no_mentions,
        #     )
        #     emotion.update("happy", -8)
        if common.GENERIC:
            return

        if msg.channel in common.entry_channels.values():
            if msg.channel.id == common.ServerConstants.ENTRY_CHANNEL_IDS["showcase"]:
                entry_type = "showcase"
                color = 0xFF8800
            else:
                entry_type = "resource"
                color = 0x0000AA

            title, fields = format_entries_message(msg, entry_type)
            await embed_utils.send(
                common.entries_discussion_channel, title, "", color, fields=fields
            )
        elif (
            random.random() < emotion.get("happy") / 200
            or msg.author.id == 683852333293109269
        ):
            await emotion.dad_joke(msg)


def cleanup(*_):
    """
    Call cleanup functions
    """

    common.bot.loop.run_until_complete(db.quit())
    common.bot.loop.run_until_complete(common.bot.close())
    common.bot.loop.close()


def run():
    """
    Does what discord.Client.run does, except, handles custom cleanup functions
    and pygame init
    """

    os.environ["SDL_VIDEODRIVER"] = "dummy"
    pygame.init()  # pylint: disable=no-member
    common.window = pygame.display.set_mode((1, 1))

    # use signal.signal to setup SIGTERM signal handler, runs after event loop
    # closes
    signal.signal(signal.SIGTERM, cleanup)

    try:
        common.bot.loop.run_until_complete(common.bot.start(common.TOKEN))

    except KeyboardInterrupt:
        # Silence keyboard interrupt traceback (it contains no useful info)
        pass

    finally:
        cleanup()
