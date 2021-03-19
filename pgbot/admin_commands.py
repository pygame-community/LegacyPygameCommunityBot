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
