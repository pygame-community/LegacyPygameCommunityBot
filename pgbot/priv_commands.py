import os
import time

import discord
import pygame

from . import (
    common,
    clock,
    sandbox,
    util
)


EXPORTED_COMMANDS = []


def export_command(identifier: str, args: int):
    def decorator_handler(func):
        global EXPORTED_COMMANDS
        EXPORTED_COMMANDS[-1]["function"] = func

    global EXPORTED_COMMANDS
    EXPORTED_COMMANDS.append({
        "identifier": identifier,
        "args": args
    })
    return decorator_handler


@export_command("exec", -1)
async def exec_cmd(invoke_msg: discord.Message, response_msg: discord.Message, args, string):
    code = string.lstrip().rstrip().lstrip('`').rstrip('`')
    if code.startswith("python\n"):
        code = code[7:]
    elif code.startswith("py\n"):
        code = code[3:]

    start = time.perf_counter()
    returned = await sandbox.exec_sandbox(code, 10)
    duration = returned.duration  # the execution time of the script alone

    if not isinstance(returned.exc, BaseException):
        if isinstance(returned.img, pygame.Surface):
            pygame.image.save(returned.img, f"temp{start}.png")
            if os.path.getsize(f"temp{start}.png") < 2 ** 22:
                await response_msg.channel.send(file=discord.File(f"temp{start}.png"))
            else:
                await util.edit_embed(
                    response_msg,
                    "Image cannot be sent:",
                    "The image file size is above 4MiB",
                )
            os.remove(f"temp{start}.png")

        str_repr = str(returned.text).replace(
            "```", common.ESC_CODE_BLOCK_QUOTE
        )

        # if not str_repr and isinstance(returned.img, pygame.Surface):
        #     return

        if len(str_repr) + 11 > 2048:
            await util.edit_embed(
                response_msg,
                f"Returned text (code executed in {util.format_time(duration)}):",
                "```\n" + str_repr[:2037] + " ...```",
            )
        else:
            await util.edit_embed(
                response_msg,
                f"Returned text (code executed in {util.format_time(duration)}):",
                "```\n" + str_repr + "```",
            )

    else:
        exp = (
                type(returned.exc).__name__.replace(
                    "```", common.ESC_CODE_BLOCK_QUOTE
                )
                + ": "
                + ", ".join(str(t) for t in returned.exc.args).replace(
            "```", common.ESC_CODE_BLOCK_QUOTE
        )
        )

        if len(exp) + 11 > 2048:
            await util.edit_embed(
                response_msg,
                common.EXP_TITLES[1],
                "```\n" + exp[:2037] + " ...```",
            )
        else:
            await util.edit_embed(
                response_msg, common.EXP_TITLES[1], "```\n" + exp + "```"
            )
