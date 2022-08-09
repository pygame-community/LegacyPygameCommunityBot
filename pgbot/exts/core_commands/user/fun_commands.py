"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present pygame-community

This file defines the command handler class for the "fun" commands of the bot
"""

from __future__ import annotations

import os
import random
import time

import discord
from discord.ext import commands
import pygame
import snakecore
from snakecore.command_handler.decorators import custom_parsing
import unidecode

from pgbot import common
from ..base import (
    BaseCommandCog,
)
from ..utils.checks import fun_command
from ..utils.converters import String
from pgbot.exceptions import BotException


class FunCommandCog(BaseCommandCog):
    """
    Command cog defining "fun" commands.
    """

    @commands.command()
    @fun_command()
    async def version(self, ctx: commands.Context):
        """
        ->type Other commands
        ->signature pg!version
        ->description Get the version of <@&822580851241123860>
        -----
        Implement pg!version, to report bot version
        """

        response_message = common.recent_response_messages[ctx.message.id]

        await snakecore.utils.embed_utils.replace_embed_at(
            response_message,
            title="Current bot's version",
            description=f"`{common.__version__}`",
            color=common.DEFAULT_EMBED_COLOR,
        )

    @commands.command()
    @fun_command()
    async def ping(self, ctx: commands.Context):
        """
        ->type Other commands
        ->signature pg!ping
        ->description Get the ping of the bot
        -----
        Implement pg!ping, to get ping
        """

        response_message = common.recent_response_messages[ctx.message.id]

        timedelta = response_message.created_at - ctx.message.created_at
        sec = timedelta.total_seconds()
        sec2 = self.bot.latency  # This does not refresh that often
        if sec < sec2:
            sec2 = sec

        await snakecore.utils.embed_utils.replace_embed_at(
            response_message,
            title=random.choice(("Pingy Pongy", "Pong!")),
            description=f"The bot's ping is `{snakecore.utils.format_time_by_units(sec, decimal_places=0)}`\n"
            f"The Discord API latency is `{snakecore.utils.format_time_by_units(sec2, decimal_places=0)}`",
            color=common.DEFAULT_EMBED_COLOR,
        )

    @commands.group(invoke_without_command=True)
    @fun_command()
    @custom_parsing(inside_class=True, inject_message_reference=True)
    async def fontify(self, ctx: commands.Context, text: String):
        """
        ->type Play With Me :snake:
        ->signature pg!fontify <text>
        ->description Display message in pygame font
        """

        response_message = common.recent_response_messages[ctx.message.id]

        fontified = ""

        emojis = ()
        if common.guild is not None:
            emojis = tuple(sorted(common.guild.emojis, key=lambda x: x.name))

        for char in unidecode.unidecode(text.string):
            if char.isalnum():
                for emoji in emojis:
                    if (
                        emoji.name == f"pg_char_{char}"
                        or emoji.name == f"pg_char_{char}".lower()
                    ):
                        fontified += str(emoji)
                        break
                else:
                    fontified += ":heavy_multiplication_x:"

            elif char.isspace():
                fontified += " " * 5

            else:
                fontified += ":heavy_multiplication_x:"

        if len(fontified) > 2000:
            raise BotException(
                "Could not execute comamnd",
                "Input text width exceeded maximum character limit of 2000",
            )

        if not fontified:
            raise BotException(
                "Could not execute comamnd",
                "Text cannot be empty",
            )

        await snakecore.utils.embed_utils.replace_embed_at(
            response_message,
            description=ctx.author.mention,
            color=0x40E32D,
        )

        await response_message.edit(content=fontified)

    @fontify.command(name="remove")
    @fun_command()
    @custom_parsing(inside_class=True, inject_message_reference=True)
    async def fontify_remove(self, ctx: commands.Context, reply: discord.Message):
        """
        ->type Play With Me :snake:
        ->signature pg!fontify remove
        ->description Delete your fontified message by replying to it
        """

        response_message = common.recent_response_messages[ctx.message.id]

        if (
            reply.author.id != self.bot.user.id
            or not reply.embeds
            or reply.embeds[0].description != ctx.author.mention
        ):
            raise BotException(
                "Could not execute comamnd", "Please reply to a fontified message"
            )

        await reply.delete()
        try:
            await ctx.message.delete()
            await response_message.delete()
        except discord.NotFound:
            pass
