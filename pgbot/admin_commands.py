import time

import discord
import pygame

from . import (
    common,
    clock,
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
