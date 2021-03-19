import os
import time
import sys

import discord
import psutil
import pygame

from . import (
    common,
    clock,
    util
)


process = psutil.Process(os.getpid())
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


@export_command("eval", -1)
async def eval_cmd(invoke_msg: discord.Message, response_msg: discord.Message, args, string):
    try:
        script = compile(
            string, "<string>", "eval"
        )  # compile script first

        script_start = time.perf_counter()
        eval_output = eval(script)  # pylint: disable = eval-used
        script_duration = time.perf_counter() - script_start

        enhanced_eval_output = repr(eval_output).replace(
            "```", common.ESC_CODE_BLOCK_QUOTE
        )

        if len(enhanced_eval_output) + 11 > 2048:
            await util.edit_embed(
                response_msg,
                f"Return output (code executed in {util.format_time(script_duration)}):",
                "```\n" + enhanced_eval_output[:2037] + " ...```",
            )
        else:
            await util.edit_embed(
                response_msg,
                f"Return output (code executed in {util.format_time(script_duration)}):",
                "```\n" + enhanced_eval_output + "```",
            )
    except Exception as ex:
        exp = (
                type(ex).__name__.replace("```", common.ESC_CODE_BLOCK_QUOTE)
                + ": "
                + ", ".join(str(t) for t in ex.args).replace(
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


@export_command("sudo", -1)
async def sudo_cmd(invoke_msg: discord.Message, response_msg: discord.Message, args, string):
    await invoke_msg.channel.send(string)
    await response_msg.delete()
    await invoke_msg.delete()


@export_command("heap", 0)
async def heap_cmd(invoke_msg: discord.Message, response_msg: discord.Message, args, string):
    mem = process.memory_info().rss
    await util.edit_embed(
        response_msg,
        "Total memory used:",
        f"**{util.format_byte(mem, 4)}**\n({mem} B)"
    )


@export_command("stop", 0)
async def stop_cmd(invoke_msg: discord.Message, response_msg: discord.Message, args, string):
    await util.edit_embed(
        response_msg,
        "Stopping bot...",
        "Change da world,\nMy final message,\nGoodbye."
    )
    sys.exit(0)
