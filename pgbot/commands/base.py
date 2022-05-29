"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file defines the base class for the command handler classes and also
defines argument casting utilities
"""

from __future__ import annotations
from discord.ext import commands


class BaseCommandCog(commands.Cog):
    """
    Base cog for all command cogs to be used by this bot.
    """

    def __init__(self, bot: commands.Bot):
        """
        Initialise BaseCommandCog class
        """
        self.bot: commands.Bot = bot
