import os
import time

import discord
import pygame

from . import (
    common,
    clock,
    docs,
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


@export_command("version", 0)
async def version_cmd(invoke_msg: discord.Message, response_msg: discord.Message, args, string):
    await util.edit_embed(response_msg, "Current bot's version", f"`{common.VERSION}`")


@export_command("clock", 0)
async def clock_cmd(invoke_msg: discord.Message, response_msg: discord.Message, args, string):
    t = time.time()
    pygame.image.save(clock.user_clock(t), f"temp{t}.png")
    common.cmd_logs[invoke_msg.id] = await response_msg.channel.send(file=discord.File(f"temp{t}.png"))
    await response_msg.delete()
    os.remove(f"temp{t}.png")


@export_command("doc", 1)
async def docs_cmd(invoke_msg: discord.Message, response_msg: discord.Message, args, string):
    title, body = docs.get(args[0])
    await util.edit_embed(response_msg, title, body)
