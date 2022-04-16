"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file is the main file of the PygameCommunityBot source. Running this
starts the bot
"""
from urllib import response
from black import err
import discord
from discord.ext import commands
import snakecore

import pgbot
from pgbot import common
from pgbot.commands.admin import AdminCommandCog
from pgbot.commands.utils import commands
from pgbot.common import bot
from pgbot.exceptions import BotException


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
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    """
    This function is called for every reaction added by user.
    """
    if payload.member is None or payload.member.bot:
        return

    await pgbot.raw_reaction_add(payload)


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    
    title = "Unknown Error!"
    msg = (
        "An unhandled exception occured while running the command!\n"
        "This is most likely a bug in the bot itself, and wizards will "
        f"recast magical spells on it soon!\n\n"
        f"```\n{snakecore.utils.format_code_exception(error)}```"
    )

    raise_error = True

    if isinstance(error, BotException):
        raise_error = False
        title, msg = error.args
        error.args = (f"{title} {msg}",)
    
    response_message = common.recent_response_messages.get(ctx.message.id)
    
    try:
        ((await snakecore.utils.embed_utils.replace_embed_at(
            response_message,
            title=title,
            description=msg,
            color=0xFF0000,
            footer_text=error.__class__.__name__
            ))
        if response_message is not None  else (await snakecore.utils.embed_utils.send_embed(
            ctx.channel,
            title=title,
            description=msg,
            color=0xFF0000,
            footer_text=error.__class__.__name__,
        )))
    except discord.NotFound:
        # response message was deleted, send a new message
        await snakecore.utils.embed_utils.send_embed(
            ctx.channel,
            title=title,
            description=msg,
            color=0xFF0000,
            footer_text=error.__class__.__name__,
        )

    if ctx.message.id in common.recent_response_messages:
        del common.recent_response_messages[ctx.message.id]

    if raise_error:
        raise error

@bot.event
async def on_command_completion(ctx: commands.Context):

    if ctx.message.id in common.recent_response_messages:
        del common.recent_response_messages[ctx.message.id]


if __name__ == "__main__":
    pgbot.run()
