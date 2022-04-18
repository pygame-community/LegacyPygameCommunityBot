"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file exports a handle function, to handle commands posted by the users
"""


from __future__ import annotations
import asyncio

import io
import sys
import types
from typing import Dict, List, Optional, Tuple, Union
import typing

import discord
import snakecore

from pgbot import common
from pgbot.commands import admin, user
from pgbot.commands.utils import get_primary_guild_perms

from pgbot.utils import message_delete_reaction_listener


async def handle(
    invoke_message: discord.Message, response_message: Optional[discord.Message] = None
):
    """
    Handle a pg! command posted by a user
    """
    is_admin, is_priv = get_primary_guild_perms(invoke_message.author)
    bot_id = common.bot.user.id
    if is_admin and invoke_message.content.startswith(
        (
            f"{common.COMMAND_PREFIX}stop",
            f"<@{bot_id}> stop",
            f"<@{bot_id}>stop",
            f"<@!{bot_id}> stop",
            f"<@!{bot_id}>stop",
        )
    ):
        splits = invoke_message.content.strip().split(" ")
        splits.pop(0)
        try:
            if splits:
                for uid in map(
                    lambda arg: snakecore.utils.extract_markdown_mention_id(arg)
                    if snakecore.utils.is_markdown_mention(arg)
                    else arg,
                    splits,
                ):
                    if uid in common.TEST_USER_IDS:
                        break
                else:
                    return

        except ValueError:
            if response_message is None:
                await snakecore.utils.embed_utils.send_embed(
                    invoke_message.channel,
                    title="Invalid arguments!",
                    description="All arguments must be integer IDs or member mentions",
                    color=0xFF0000,
                )
            else:
                await snakecore.utils.embed_utils.replace_embed_at(
                    response_message,
                    title="Invalid arguments!",
                    description="All arguments must be integer IDs or member mentions",
                    color=0xFF0000,
                )
            return

        if response_message is None:
            await snakecore.utils.embed_utils.send_embed(
                invoke_message.channel,
                title="Stopping bot...",
                description="Change da world,\nMy final message,\nGoodbye.",
                color=common.DEFAULT_EMBED_COLOR,
            )
        else:
            await snakecore.utils.embed_utils.replace_embed_at(
                response_message,
                title="Stopping bot...",
                description="Change da world,\nMy final message,\nGoodbye.",
                color=common.DEFAULT_EMBED_COLOR,
            )
        sys.exit(0)

    if (
        common.TEST_MODE
        and common.TEST_USER_IDS
        and invoke_message.author.id not in common.TEST_USER_IDS
    ):
        return

    if response_message is None:
        response_message = await snakecore.utils.embed_utils.send_embed(
            invoke_message.channel,
            title="Your command is being processed:",
            color=common.DEFAULT_EMBED_COLOR,
            fields=[dict(name="\u2800", value="`Loading...`", inline=False)],
        )

    ctx = await common.bot.get_context(invoke_message)
    setattr(ctx, "response_message", response_message)

    if not common.TEST_MODE and not common.GENERIC:
        log_txt_file = None
        escaped_cmd_text = discord.utils.escape_markdown(invoke_message.content)
        if len(escaped_cmd_text) > 2047:
            with io.StringIO(invoke_message.content) as log_buffer:
                log_txt_file = discord.File(log_buffer, filename="command.txt")

        await common.log_channel.send(
            embed=snakecore.utils.embed_utils.create_embed(
                title=f"Command invoked by {invoke_message.author} / {invoke_message.author.id}",
                description=escaped_cmd_text
                if len(escaped_cmd_text) <= 2047
                else escaped_cmd_text[:2044] + "...",
                color=common.DEFAULT_EMBED_COLOR,
                fields=[
                    dict(
                        name="\u200b",
                        value=f"by {invoke_message.author.mention}\n**[View Original]({invoke_message.jump_url})**",
                        inline=False,
                    ),
                ],
            ),
            file=log_txt_file,
        )

    task = asyncio.create_task(
        message_delete_reaction_listener(
            response_message,
            invoke_message.author,
            emoji="🗑",
            role_whitelist=common.ServerConstants.ADMIN_ROLES,
            timeout=30,
        )
    )

    common.global_task_set.add(task)
    task.add_done_callback(common.global_task_set_remove_callback)

    await common.bot.invoke(ctx)
    # main command handling
    return response_message
