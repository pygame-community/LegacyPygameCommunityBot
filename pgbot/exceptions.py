"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present pygame-community

This file defines some exceptions used across the whole codebase
"""

from discord.ext import commands


class BotException(commands.CommandError):
    """Base class for all bot related exceptions, that need to be displayed on
    discord
    """


class NoFunAllowed(commands.CheckFailure):
    """A command check exception for blocking 'fun' related commands in select
    channels.
    """


class AdminOnly(commands.CheckFailure):
    """A command check exception for blocking members from running admin-only
    commands.
    """
