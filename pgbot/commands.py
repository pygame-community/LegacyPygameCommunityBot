import discord

from . import admin_commands, common, user_commands, embed_utils


async def handle(invoke_msg: discord.Message, response_msg: discord.Message):
    """
    Handle a pg! command posted by a user
    """
    await embed_utils.send(
        common.log_channel,
        f"Command invoked by {invoke_msg.author} / {invoke_msg.author.id}",
        invoke_msg.content
    )

    is_priv = False
    cmd = user_commands.UserCommand(invoke_msg, response_msg)
    if invoke_msg.author.id in common.ADMIN_USERS:
        cmd = admin_commands.AdminCommand(invoke_msg, response_msg)
    else:
        for role in invoke_msg.author.roles:
            if role.id in common.ADMIN_ROLES:
                cmd = admin_commands.AdminCommand(invoke_msg, response_msg)
                break
            elif role.id in common.PRIV_ROLES:
                is_priv = True

    cmd.is_priv = is_priv or isinstance(cmd, admin_commands.AdminCommand)

    # Only admins can execute commands to the developer bot
    if common.TEST_MODE and not isinstance(cmd, admin_commands.AdminCommand):
        return

    await cmd.handle_cmd()
