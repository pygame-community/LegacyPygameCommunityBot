import datetime
from functools import partial
import functools
import inspect
import types
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from discord.ext.commands.converter import CONVERTER_MAPPING
import pygame
from snakecore.command_handler.converters import (
    CodeBlock,
    DateTime,
    Range,
    String,
)


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
