"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present pygame-community

This file defines decorators to perform checks on a command.
"""

from discord.ext import commands
from snakecore.commands.decorators import custom_parsing

import pgbot
from pgbot import common
from pgbot.exceptions import AdminOnly, NoFunAllowed


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


def _admin_only_predicate(ctx: commands.Context):
    if ctx.guild is None:
        raise commands.NoPrivateMessage()

    if any(
        role.id in common.GuildConstants.ADMIN_ROLES
        for role in getattr(ctx.author, "roles", ())
    ):
        return True
    raise AdminOnly(
        f"The command '{ctx.command.qualified_name}' is an admin command, and you do not have access to that"
    )


def admin_only():
    r"""Checks if the member invoking the
    command has an admin role. Raises `AdminOnly`
    if that is not the case.
    """
    return commands.check(_admin_only_predicate)


def admin_only_and_custom_parsing(
    inside_class: bool = False, inject_message_reference: bool = False
):
    """A decorator combining admin-only role checks and
    `snakecore.commands.decorators.custom_parsing(...)`.
    """
    return commands.check(_admin_only_predicate)(
        custom_parsing(
            inside_class=inside_class, inject_message_reference=inject_message_reference
        )
    )
