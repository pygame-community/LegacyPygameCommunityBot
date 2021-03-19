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


@export_command("sudo-edit", -1)
async def sudo_edit_cmd(invoke_msg: discord.Message, response_msg: discord.Message, args, string):
    edit_msg = await invoke_msg.channel.fetch_message(util.filter_id(args[0]))
    await edit_msg.edit(content=string[string.find(args[1]):])
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


@export_command("emsudo", -1)
async def emsudo_cmd(invoke_msg: discord.Message, response_msg: discord.Message, args, string):
    args = eval(string)

    if len(args) == 1:
        await util.send_embed(
            invoke_msg.channel,
            args[0],
            ""
        )
    elif len(args) == 2:
        await util.send_embed(
            invoke_msg.channel,
            args[0],
            args[1]
        )
    elif len(args) == 3:
        await util.send_embed(
            invoke_msg.channel,
            args[0],
            args[1],
            args[2]
        )
    elif len(args) == 4:
        await util.send_embed(
            invoke_msg.channel,
            args[0],
            args[1],
            args[2],
            args[3]
        )
    else:
        await util.edit_embed(
            response_msg,
            "Invalid arguments!",
            ""
        )
        return

    await response_msg.delete()
    await invoke_msg.delete()


@export_command("emsudo-edit", -1)
async def emsudo_edit_cmd(invoke_msg: discord.Message, response_msg: discord.Message, args, string):
    args = eval(string)
    edit_msg = await invoke_msg.channel.fetch_message(util.filter_id(args[0]))

    if len(args) == 2:
        await util.edit_embed(
            edit_msg,
            args[1],
            ""
        )
    elif len(args) == 3:
        await util.edit_embed(
            edit_msg,
            args[1],
            args[2]
        )
    elif len(args) == 4:
        await util.edit_embed(
            edit_msg,
            args[1],
            args[2],
            args[3]
        )
    elif len(args) == 5:
        await util.edit_embed(
            edit_msg,
            args[1],
            args[2],
            args[3],
            args[4]
        )
    else:
        await util.edit_embed(
            response_msg,
            "Invalid arguments!",
            ""
        )
        return

    await response_msg.delete()
    await invoke_msg.delete()


@export_command("archive", 3)
async def archive_cmd(invoke_msg: discord.Message, response_msg: discord.Message, args, string):
    origin, quantity, destination = int(args[0]), int(args[1]), int(args[2])

    origin_channel = None
    destination_channel = None

    for channel in common.bot.get_all_channels():
        if channel.id == origin:
            origin_channel = channel
        if channel.id == destination:
            destination_channel = channel

    if not origin_channel:
        await util.edit_embed(
            response_msg,
            "Cannot execute command:",
            "Invalid origin channel!"
        )
        return
    elif not destination_channel:
        await util.edit_embed(
            response_msg,
            "Cannot execute command:",
            "Invalid destination channel!"
        )
        return

    messages = await origin_channel.history(limit=quantity).flatten()
    messages.reverse()
    message_list = await util.format_archive_messages(messages)

    archive_str = f"+{'=' * 40}+\n" + f"+{'=' * 40}+\n".join(message_list) + f"+{'=' * 40}+\n"
    archive_list = util.split_long_message(archive_str)

    for message in archive_list:
        await destination_channel.send(message)

    await util.edit_embed(
        response_msg,
        f"Successfully archived {len(messages)} message(s)!",
        ""
    )
