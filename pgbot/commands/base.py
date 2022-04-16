"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file defines the base class for the command handler classes and also
defines argument casting utilities
"""


from __future__ import annotations

import asyncio
import datetime
import inspect
import random
import re
from typing import Any, Optional, Union

import discord
from discord.ext import commands
import pygame
import snakecore

from pgbot import common, db, emotion
import pgbot


def fun_command(func):
    """
    A decorator to indicate a "fun command", one that the bot skips when it is
    'exhausted'
    """
    func.fun_cmd = True
    return func


def no_dm(func):
    """
    A decorator to indicate a command that cannot be run on DM
    """
    func.no_dm = True
    return func


def add_group(groupname: str, *subcmds: str):
    """
    Utility to add a function name to a group command
    """

    def inner(func):
        # patch in group name data and sub command data into the function itself
        if subcmds:
            func.groupname = groupname
            func.subcmds = subcmds
        return func

    return inner


class BaseCommandCog(commands.Cog):
    """
    Base cog for all commands.
    """

    def __init__(self, bot: commands.Bot):
        """
        Initialise UserCommandCog class
        """
        self.bot: commands.Bot = bot
        # Create a dictionary of command names and respective handler functions
        # build self.groups and self.cmds_and_functions from class functions
        self.cmds_and_funcs = {}  # this is a mapping from funtion name to funtion
        self.groups = {}  # This is a mapping from group name to list of sub functions
        for attr in dir(self):
            cmd: commands.Command = self.__getattribute__(attr)
            if isinstance(cmd, commands.Command):
                func = cmd.callback
                name = func.__name__
                self.cmds_and_funcs[name] = func

                if isinstance(cmd, commands.Group) and not cmd.parents:
                    for subcmd in cmd.walk_commands():
                        subcmd.callback.groupname = cmd.name
                        subcmd.callback.subcmds = tuple(subcmd.qualified_name.split()[1:])

                if hasattr(func, "groupname"):
                    if func.groupname in self.groups:
                        self.groups[func.groupname].append(func)
                    else:
                        self.groups[func.groupname] = [func]
        # page number, useful for PagedEmbed commands. 0 by deafult, gets modified
        # in pg!refresh command when invoked

    # async def handle_cmd(self):
    #     """
    #     Command handler, calls the appropriate sub function to handle commands.
    #     """
    #     try:
    #         await self.call_cmd()
    #         await emotion.update("confused", -random.randint(4, 8))
    #         return

    #     except ArgError as exc:
    #         await emotion.update("confused", random.randint(2, 6))
    #         title = "Invalid Arguments!"
    #         if len(exc.args) == 2:
    #             msg, cmd = exc.args
    #             msg += f"\nFor help on this bot command, do `pg!help {cmd}`"
    #         else:
    #             msg = exc.args[0]
    #         excname = "Argument Error"

    #     except KwargError as exc:
    #         await emotion.update("confused", random.randint(2, 6))
    #         title = "Invalid Keyword Arguments!"
    #         if len(exc.args) == 2:
    #             msg, cmd = exc.args
    #             msg += f"\nFor help on this bot command, do `pg!help {cmd}`"
    #         else:
    #             msg = exc.args[0]

    #         excname = "Keyword argument Error"

    #     except BotException as exc:
    #         await emotion.update("confused", random.randint(4, 8))
    #         title, msg = exc.args
    #         excname = "BotException"

    #     except discord.HTTPException as exc:
    #         await emotion.update("confused", random.randint(7, 13))
    #         title, msg = exc.__class__.__name__, exc.args[0]
    #         excname = "discord.HTTPException"

    #     except Exception:
    #         await emotion.update("confused", random.randint(10, 22))
    #         await snakecore.utils.embed_utils.replace_embed_at(
    #             self.response_message,
    #             title="Unknown Error!",
    #             description=(
    #                 "An unhandled exception occured while running the command!\n"
    #                 "This is most likely a bug in the bot itself, and wizards will "
    #                 "recast magical spells on it soon!"
    #             ),
    #             color=0xFF0000,
    #         )
    #         raise

    #     # display bot exception to user on discord
    #     try:
    #         await snakecore.utils.embed_utils.replace_embed_at(
    #             self.response_message,
    #             title=title,
    #             description=msg,
    #             color=0xFF0000,
    #             footer_text=excname,
    #         )
    #     except discord.NotFound:
    #         # response message was deleted, send a new message
    #         await snakecore.utils.embed_utils.send_embed(
    #             self.channel,
    #             title=title,
    #             description=msg,
    #             color=0xFF0000,
    #             footer_text=excname,
    #         )
