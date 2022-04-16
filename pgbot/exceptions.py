import discord
from discord.ext import commands

"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file defines some exceptions used across the whole codebase
"""

class BotException(commands.BadArgument):
    """
    Base class for all bot related exceptions, that need to be displayed on
    discord
    """
