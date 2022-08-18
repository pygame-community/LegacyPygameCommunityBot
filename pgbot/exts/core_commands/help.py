"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present pygame-community

This file defines the base class for the command handler classes and also
defines argument casting utilities
"""


from __future__ import annotations

import discord
from discord.ext import commands
import snakecore
from snakecore.commands.converters import String
from snakecore.commands.decorators import custom_parsing

from pgbot import common
from .utils.help import send_help_message


@commands.command()
@custom_parsing(inject_message_reference=True)
async def help(
    ctx: commands.Context,
    *names: str,
    page: int = 1,
):
    """
    ->type Get help
    ->signature pg!help [command]
    ->description Ask me for help
    ->example command pg!help help
    -----
    Implement pg!help, to display a help message
    """

    # needed for typecheckers to know that ctx.author is a member
    if isinstance(ctx.author, discord.User):
        return

    response_message = common.recent_response_messages[ctx.message.id]

    await send_help_message(
        ctx,
        common.bot,
        response_message,
        ctx.author,
        " ".join(names),
        page=page,
    )


async def setup(bot: snakecore.commands.Bot):
    bot.add_command(help)
