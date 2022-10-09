"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present pygame-community

This file defines the command handler class for the "help" commands of the bot
"""

from __future__ import annotations

import os
import random
import re
import time
from typing import Optional

import discord
from discord.ext import commands
import pygame
import snakecore
from snakecore.commands.decorators import custom_parsing

from pgbot import common
from ..base import BaseCommandCog, CommandMixinCog
from ..utils import clock, docs, help
from ..utils.converters import String
from pgbot.exceptions import BotException


class UserHelpCommandCog(CommandMixinCog, BaseCommandCog):
    """Base commang cog to handle user-help commands of the bot."""

    @commands.command()
    @custom_parsing(inside_class=True, inject_message_reference=True)
    async def rules(self, ctx: commands.Context, *rules: int):
        """
        ->type Get help
        ->signature pg!rules [*rule_numbers]
        ->description Get rules of the server
        -----
        Implement pg!rules, to get rules of the server
        """

        response_message = common.recent_response_messages[ctx.message.id]

        if not rules:
            raise BotException("Please enter rule number(s)", "")

        if common.GENERIC:
            raise BotException(
                "Cannot execute command!",
                "This command cannot be exected when the bot is on generic mode",
            )

        fields = []
        for rule in sorted(set(rules)):
            if 0 < rule <= len(common.GuildConstants.RULES):
                msg = await common.rules_channel.fetch_message(
                    common.GuildConstants.RULES[rule - 1]
                )
                value = msg.content

            elif rule == 42:
                value = (
                    "*Shhhhh*, you have found an unwritten rule!\n"
                    "Click [here](https://bitly.com/98K8eH) to gain the most "
                    "secret and ultimate info!"
                )

            else:
                value = "Does not exist lol"

            if len(str(rule)) > 200:
                raise BotException(
                    "Overflow in command",
                    "Why would you want to check such a large rule number?",
                )

            fields.append(
                {
                    "name": f"__Rule number {rule}:__",
                    "value": value,
                    "inline": False,
                }
            )

        if len(rules) > 25:
            raise BotException(
                "Overflow in command",
                "Too many rules were requested",
            )

        if len(rules) == 1:
            await snakecore.utils.embeds.replace_embed_at(
                response_message,
                author_name="Pygame Community",
                author_icon_url=common.guild.icon.url,
                title=fields[0]["name"],
                description=fields[0]["value"][:2048],
                color=0x228B22,
            )
        else:
            for field in fields:
                field["value"] = field["value"][:1024]

            await snakecore.utils.embeds.replace_embed_at(
                response_message,
                author_name="Pygame Community",
                author_icon_url=common.guild.icon.url,
                title="Rules",
                fields=fields,
                color=0x228B22,
            )

    @commands.command()
    @custom_parsing(inside_class=True, inject_message_reference=True)
    async def clock(
        self,
        ctx: commands.Context,
        action: str = "",
        timezone: Optional[float] = None,
        color: Optional[discord.Color] = None,
    ):
        """
        ->type Get help
        ->signature pg!clock
        ->description 24 Hour Clock showing <@&778205389942030377> s who are available to help
        -> Extended description
        People on the clock can run the clock with more arguments, to update their data.
        `pg!clock update [timezone in hours] [color as hex string]`
        `timezone` is float offset from GMT in hours.
        `color` optional color argument, that shows up on the clock.
        Note that you might not always display with that colour.
        This happens if more than one person are on the same timezone
        Use `pg!clock remove` to remove yourself from the clock
        -----
        Implement pg!clock, to display a clock of helpfulies/mods/wizards
        """

        return await self.clock_func(ctx, action=action, timezone=timezone, color=color)

    @commands.command()
    @custom_parsing(inside_class=True, inject_message_reference=True)
    async def doc(
        self,
        ctx: commands.Context,
        name: str,
        page: int = 1,
    ):
        """
        ->type Get help
        ->signature pg!doc <object name>
        ->description Look up the docstring of a Python/Pygame object, e.g str or pygame.Rect
        -----
        Implement pg!doc, to view documentation
        """

        # needed for typecheckers to know that ctx.author is a member
        if isinstance(ctx.author, discord.User):
            return

        response_message = common.recent_response_messages[ctx.message.id]

        await docs.put_doc(ctx, name, response_message, ctx.author, page=page)
