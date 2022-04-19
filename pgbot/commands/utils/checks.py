"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file defines decorators to perform checks on a command.
"""

import discord
from discord.ext import commands

import pgbot
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
