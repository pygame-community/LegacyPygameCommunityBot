"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file defines constructs that aid with static type-checking in command
functions.
"""

from typing import TYPE_CHECKING

import discord
from discord.ext import commands

CustomContext = commands.Context

if TYPE_CHECKING:

    class CustomContext(commands.Context):
        """A fake subclass of `Context` from discord.ext.commands
        to show extra attributes to custom type checkers.
        These attributes are injected at runtime into the `Context`
        object provided by `commands.Bot.get_context(...)`.
        """

        response_message: discord.Message
