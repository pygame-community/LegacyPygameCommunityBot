import discord

from . import admin_commands, common, user_commands, util

admincmd = admin_commands.AdminCommand()
usercmd = user_commands.UserCommand()


async def handle(invoke_msg: discord.Message, response_msg: discord.Message):
    """
    Handle a pg! command posted by a user
    """
    await util.send_embed(
        common.log_channel,
        f"Command invoked by {invoke_msg.author} / {invoke_msg.author.id}",
        invoke_msg.content
    )

    is_admin = False
    is_priv = False

    if invoke_msg.author.id in common.ADMIN_USERS:
        is_admin = is_priv = True
    else:
        for role in invoke_msg.author.roles:
            if role.id in common.ADMIN_ROLES:
                is_admin = is_priv = True
            elif role.id in common.PRIV_ROLES:
                is_priv = True

    try:
        cmdobj = admincmd if is_admin else usercmd
        if not cmdobj.handle_cmd(invoke_msg, response_msg, is_priv):
            await util.edit_embed(
                response_msg,
                "Invalid command!",
                "Have you spelt the command name right and put the " + \
                "appropriate amount of arguments?"
            )

    except Exception as exc:
        await util.edit_embed(
            response_msg,
            "An exception occurred while handling your command!",
            f"{type(exc).__name__}: {', '.join(map(str, exc.args))}"
        )
