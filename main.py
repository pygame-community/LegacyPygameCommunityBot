"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file is the main file of the PygameCommunityBot source. Running this
starts the bot
"""
import datetime
import discord

import pgbot
from pgbot.common import bot
from pgbot import common
from pgbot.tasks import events


@bot.event
async def on_ready():
    """
    Startup routines when the bot starts
    """
    await pgbot.init()
    await common.task_manager.dispatch_client_event(
        events.OnReady(client=bot, timestamp=datetime.datetime.now())
    )


@bot.event
async def on_member_join(member: discord.Member):
    """
    This function handles the greet message when a new member joins
    """
    if member.bot:
        return

    await pgbot.member_join(member)
    await common.task_manager.dispatch_client_event(
        events.OnMemberJoin(member, client=bot, timestamp=datetime.datetime.now())
    )


@bot.event
async def on_member_leave(member: discord.Member):
    """
    Routines to run when people leave the server
    """
    await pgbot.clean_db_member(member)


@bot.event
async def on_message(message: discord.Message):
    """
    This function is called for every message by user.
    """
    if message.author.bot:
        return

    await pgbot.handle_message(message)
    await common.task_manager.dispatch_client_event(
        events.OnMessage(message, client=bot, timestamp=datetime.datetime.now())
    )


@bot.event
async def on_message_delete(message: discord.Message):
    """
    This function is called for every message deleted by user.
    """
    await pgbot.message_delete(message)
    await common.task_manager.dispatch_client_event(
        events.OnMessageDelete(message, client=bot, timestamp=datetime.datetime.now())
    )


@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    """
    This function is called for every message edited by user.
    """
    if after.author.bot:
        return

    await pgbot.message_edit(before, after)
    await common.task_manager.dispatch_client_event(
        events.OnMessageEdit(
            before, after, client=bot, timestamp=datetime.datetime.now()
        )
    )


@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    """
    This function is called for every reaction added by user.
    """
    if payload.member is None or payload.member.bot:
        return

    await pgbot.raw_reaction_add(payload)
    await common.task_manager.dispatch_client_event(
        events.OnRawReactionAdd(payload, client=bot, timestamp=datetime.datetime.now())
    )


if __name__ == "__main__":
    pgbot.run()
