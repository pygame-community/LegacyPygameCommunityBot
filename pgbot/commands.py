import discord

from . import admin_commands, common, user_commands, util


async def handle(invoke_msg: discord.Message, response_msg: discord.Message):
    """
    Handle a pg! command posted by a user
    """
    await util.send_embed(
        common.log_channel,
        f"Command invoked by {invoke_msg.author} / {invoke_msg.author.id}",
        invoke_msg.content
    )

    cmd = user_commands.UserCommand()
    is_priv = False
    if invoke_msg.author.id in common.ADMIN_USERS:
        cmd = admin_commands.AdminCommand()
        is_priv = True
    else:
        for role in invoke_msg.author.roles:
            if role.id in common.ADMIN_ROLES:
                cmd = admin_commands.AdminCommand()
                is_priv = True
                break
            elif role.id in common.PRIV_ROLES:
                is_priv = True

    # Only admins can execute commands to the developer bot
    if common.TEST_MODE and not isinstance(cmd, admin_commands.AdminCommand):
        return

    await cmd.handle_cmd(invoke_msg, response_msg, is_priv)
