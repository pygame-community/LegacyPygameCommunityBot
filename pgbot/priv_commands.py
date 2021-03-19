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
from .user_commands import exec_cmd as _exec_cmd


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
    await _exec_cmd(invoke_msg, response_msg, args, string, 10)
