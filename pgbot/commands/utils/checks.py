"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file defines decorators to perform checks on a command.
"""

import discord
from discord.ext import commands
from snakecore.command_handler.decorators import custom_parsing

import pgbot
from pgbot import common
from pgbot.exceptions import NoFunAllowed


async def _fun_command_predicate(ctx: commands.Context):
    if await pgbot.utils.get_channel_feature("nofun", ctx.channel):
        raise NoFunAllowed(
            f"The command `{ctx.command.qualified_name}` is a 'fun' command, and is not allowed "
            "in this channel. Please try running the command in "
            "some other channel.",
        )
    return True


def fun_command():
    """This decorator marks a function as a 'fun' command only allowed in a subset
    of channels."""

    return commands.check(_fun_command_predicate)


def admin_only_and_custom_parsing(
    inside_class: bool = False, inject_message_reference: bool = False
):
    """A decorator combining admin-only role checks and
    `snakecore.command_handler.decorators.custom_parsing(...)`.
    """
    return commands.has_any_role(*common.ServerConstants.ADMIN_ROLES)(
        custom_parsing(
            inside_class=inside_class, inject_message_reference=inject_message_reference
        )
    )
