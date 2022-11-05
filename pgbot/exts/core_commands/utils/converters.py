"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present pygame-community

This file defines converters for parsing command arguments.
"""

from typing import TYPE_CHECKING

from discord.ext import commands
import pygame
from snakecore.commands.converters import (
    DateTime,
    Interval,
)
from snakecore.commands.parser import CodeBlock, String


class PygameColor(commands.Converter):
    async def convert(self, ctx: commands.Context, argument: str) -> pygame.Color:
        try:
            return pygame.Color(argument)
        except (ValueError, TypeError) as err:
            raise commands.BadArgument(
                f"failed to construct pygame.Color: {err.__class__.__name__}:{err!s}"
            )


if TYPE_CHECKING:
    PygameColor = pygame.Color
