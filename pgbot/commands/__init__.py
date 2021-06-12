"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file exports a handle function, to handle commands posted by the users
"""


from __future__ import annotations

import io
import sys
from typing import Union

import discord

from pgbot import common
from pgbot.commands import admin, user
from pgbot.utils import embed_utils, utils


def get_perms(mem: Union[discord.Member, discord.User]):
    """
    Return a tuple (is_admin, is_priv) for a given user
    """
    if mem.id in common.TEST_USER_IDS:
        return True, True

    if not isinstance(mem, discord.Member):
        return False, False

    is_priv = False

    if not common.GENERIC:
        for role in mem.roles:
            if role.id in common.ServerConstants.ADMIN_ROLES:
                return True, True
            elif role.id in common.ServerConstants.PRIV_ROLES:
                is_priv = True

    return False, is_priv


async def handle(invoke_msg: discord.Message, response_msg: discord.Message = None):
    """
    Handle a pg! command posted by a user
    """
    is_admin, is_priv = get_perms(invoke_msg.author)

    if is_admin and invoke_msg.content.startswith(f"{common.PREFIX}stop"):
        splits = invoke_msg.content.strip().split(" ")
        splits.pop(0)
        try:
            if splits:
                for uid in map(utils.filter_id, splits):
                    if uid in common.TEST_USER_IDS:
                        break
                else:
                    return

        except ValueError:
            if response_msg is None:
                await embed_utils.send(
                    invoke_msg.channel,
                    "Invalid arguments!",
                    "All arguments must be integer IDs or member mentions",
                    0xFF0000,
                )
            else:
                await embed_utils.replace(
                    response_msg,
                    "Invalid arguments!",
                    "All arguments must be integer IDs or member mentions",
                    0xFF0000,
                )
            return

        if response_msg is None:
            await embed_utils.send(
                invoke_msg.channel,
                "Stopping bot...",
                "Change da world,\nMy final message,\nGoodbye.",
            )
        else:
            await embed_utils.replace(
                response_msg,
                "Stopping bot...",
                "Change da world,\nMy final message,\nGoodbye.",
            )
        sys.exit(0)

    if (
        common.TEST_MODE
        and common.TEST_USER_IDS
        and invoke_msg.author.id not in common.TEST_USER_IDS
    ):
        return

    if response_msg is None:
        response_msg = await embed_utils.send_2(
            invoke_msg.channel,
            title="Your command is being processed:",
            fields=(("\u2800", "`Loading...`", False),),
        )

    if not common.TEST_MODE and not common.GENERIC:
        log_txt_file = None
        escaped_cmd_text = discord.utils.escape_markdown(invoke_msg.content)
        if len(escaped_cmd_text) > 2047:
            with io.StringIO(invoke_msg.content) as log_buffer:
                log_txt_file = discord.File(log_buffer, filename="command.txt")

        await common.log_channel.send(
            embed=embed_utils.create(
                title=f"Command invoked by {invoke_msg.author} / {invoke_msg.author.id}",
                description=escaped_cmd_text
                if len(escaped_cmd_text) <= 2047
                else escaped_cmd_text[:2044] + "...",
                fields=(
                    (
                        "\u200b",
                        f"by {invoke_msg.author.mention}\n**[View Original]({invoke_msg.jump_url})**",
                        False,
                    ),
                ),
            ),
            file=log_txt_file,
        )

    cmd = (
        admin.AdminCommand(invoke_msg, response_msg)
        if is_admin
        else user.UserCommand(invoke_msg, response_msg)
    )
    cmd.is_priv = is_priv
    await cmd.handle_cmd()
    return response_msg
