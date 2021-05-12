from __future__ import annotations

import asyncio
import discord

from pgbot import common, embed_utils
from pgbot.commands import admin, user


async def handle(invoke_msg: discord.Message, response_msg: discord.Message):
    """
    Handle a pg! command posted by a user
    """
    await embed_utils.send_2(
        common.log_channel,
        title=f"Command invoked by {invoke_msg.author} / {invoke_msg.author.id}",
        description=invoke_msg.content,
        fields=(("\u200b", f"**[View Original]({invoke_msg.jump_url})**", False),),
    )

    is_priv = False
    cmd = user.UserCommand(invoke_msg, response_msg)
    if invoke_msg.author.id in common.ADMIN_USERS:
        cmd = admin.AdminCommand(invoke_msg, response_msg)
    else:
        for role in invoke_msg.author.roles:
            if role.id in common.ADMIN_ROLES:
                cmd = admin.AdminCommand(invoke_msg, response_msg)
                break
            elif role.id in common.PRIV_ROLES:
                is_priv = True

    cmd.is_priv = is_priv or isinstance(cmd, admin.AdminCommand)

    # Only admins can execute commands to the developer bot
    if common.TEST_MODE and not isinstance(cmd, admin.AdminCommand):
        return

    await cmd.handle_cmd()
