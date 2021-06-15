"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file is the main file of the PygameCommunityBot source. Running this
starts the bot
"""
import discord

import pgbot
from pgbot.common import bot


@bot.event
async def on_ready():
    """
    Startup routines when the bot starts
    """
    await pgbot.init()


@bot.event
async def on_member_join(member: discord.Member):
    """
    This function handles the greet message when a new member joins
    """
    if member.bot:
        return

    await pgbot.member_join(member)


@bot.event
async def on_member_leave(member: discord.Member):
    """
    Routines to run when people leave the server
    """
    await pgbot.clean_db_member(member)


@bot.event
async def on_message(msg: discord.Message):
    """
    This function is called for every message by user.
    """
    if msg.author.bot:
        return

    await pgbot.handle_message(msg)


@bot.event
async def on_message_delete(msg: discord.Message):
    """
    This function is called for every message deleted by user.
    """
    await pgbot.message_delete(msg)


@bot.event
async def on_message_edit(old: discord.Message, new: discord.Message):
    """
    This function is called for every message edited by user.
    """
    if new.author.bot:
        return

    await pgbot.message_edit(old, new)


@bot.event
async def on_raw_reaction_add(payload):
    """
    This function is called for every reaction added by user.
    """
    if payload.member.bot:
        return

    await pgbot.raw_reaction_add(payload)


if __name__ == "__main__":
    pgbot.run()
