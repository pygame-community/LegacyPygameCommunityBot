"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present pygame-community

This file defines Discord gateway event listeners
"""
import asyncio
from dis import dis
import discord
from discord.ext import commands
import snakecore
from snakecore.commands.parser import ArgError, KwargError

import pgbot
from pgbot import common
from pgbot.common import bot
from pgbot.exceptions import AdminOnly, BotException, NoFunAllowed
from pgbot.utils import message_delete_reaction_listener


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
    await pgbot.clean_storage_member(member)


@bot.event
async def on_message(msg: discord.Message):
    """
    This function is called for every message by user.
    """
    if msg.author.bot:
        return

    await pgbot.handle_message(msg)


@bot.event
async def on_message_edit(old: discord.Message, new: discord.Message):
    """
    This function is called for every message edited by user.
    """
    if new.author.bot:
        return

    await pgbot.message_edit(old, new)


@bot.event
async def on_message_delete(msg: discord.Message):
    """
    This function is called for every message deleted by user.
    """
    await pgbot.message_delete(msg)


@bot.event
async def on_thread_create(thread: discord.Thread):
    await pgbot.thread_create(thread)


@bot.event
async def on_thread_update(before: discord.Thread, after: discord.Thread):
    await pgbot.thread_update(before, after)


@bot.event
async def on_raw_thread_delete(payload: discord.RawThreadDeleteEvent):
    await pgbot.raw_thread_delete(payload)


@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    await pgbot.raw_reaction_add(payload)


@bot.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
    await pgbot.raw_reaction_remove(payload)


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):

    title = error.__class__.__name__
    msg = error.args[0]
    footer_text = error.__class__.__name__

    raise_error = False
    has_cause = False

    if isinstance(error, BotException):  # general bot command exception
        title, msg = error.args

    elif isinstance(error, ArgError):  # snakecore parsing error
        title = "Invalid Arguments!"
        msg = f"{msg}\n\nFor help on bot commands, do `{common.COMMAND_PREFIX}help <command>`"

    elif isinstance(error, KwargError):
        title = "Invalid Keyword Arguments!"
        msg = f"{msg}\n\nFor help on bot commands, do `{common.COMMAND_PREFIX}help <command>`"

    elif isinstance(error, commands.CommandNotFound):
        title = "Unrecognized command!"
        msg = f"{msg}\n\nFor help on bot commands, do `{common.COMMAND_PREFIX}help`"
    elif isinstance(error, commands.DisabledCommand):
        title = f"Cannot execute command! ({error.args[0]})"
        msg = (
            f"The specified command has been temporarily blocked from "
            "running, while wizards are casting their spells on it!\n"
            "Please try running the command after the maintenance work "
            "has completed."
        )
    elif isinstance(error, NoFunAllowed):
        title = "No fun allowed!"  # ;P

    elif isinstance(error, AdminOnly):
        title = "Insufficient Permissions!"

    elif error.__cause__ is not None:
        has_cause = True
        if isinstance(error.__cause__, discord.HTTPException):
            title = footer_text = error.__cause__.__class__.__name__
            msg = error.__cause__.args[0] if error.__cause__.args else ""
        else:
            raise_error = True
            has_cause = True
            title = "Unknown exception!"
            msg = (
                "An unhandled exception occured while running the command!\n"
                "This is most likely a bug in the bot itself, and `@Wizard 🝑`s will "
                f"recast magical spells on it soon!\n\n"
                f"```\n{error.__cause__.args[0] if error.__cause__.args else ''}```"
            )
            footer_text = error.__cause__.__class__.__name__

    footer_text = (
        f"{footer_text}\n(React with 🗑 to delete this error message in the next 30s)"
    )

    response_message = common.recent_response_messages.get(ctx.message.id)

    target_message = response_message

    try:
        (
            (
                await snakecore.utils.embeds.replace_embed_at(
                    target_message,
                    title=title,
                    description=msg,
                    color=0xFF0000,
                    footer_text=footer_text,
                )
            )
            if target_message is not None
            else (
                target_message := await snakecore.utils.embeds.send_embed(
                    ctx.channel,
                    title=title,
                    description=msg,
                    color=0xFF0000,
                    footer_text=footer_text,
                )
            )
        )
    except discord.NotFound:
        # response message was deleted, send a new message
        target_message = await snakecore.utils.embeds.send_embed(
            ctx.channel,
            title=title,
            description=msg,
            color=0xFF0000,
            footer_text=footer_text,
        )

    common.hold_task(
        asyncio.create_task(
            message_delete_reaction_listener(
                common.bot,
                target_message,
                ctx.author,
                emoji="🗑",
                role_whitelist=common.GuildConstants.ADMIN_ROLES,
                timeout=30,
            )
        )
    )

    if ctx.message.id in common.recent_response_messages:
        del common.recent_response_messages[ctx.message.id]

    if raise_error:
        if has_cause:
            raise error.__cause__
        raise error


@bot.event
async def on_command_completion(ctx: commands.Context):

    if ctx.message.id in common.recent_response_messages:
        del common.recent_response_messages[ctx.message.id]
