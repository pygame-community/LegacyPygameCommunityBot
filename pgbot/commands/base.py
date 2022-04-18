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
        self.cmds_and_funcs = {}  # this is a mapping from function name to function
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
                        subcmd.callback.subcmds = tuple(
                            subcmd.qualified_name.split()[1:]
                        )

                if hasattr(func, "groupname"):
                    if func.groupname in self.groups:
                        self.groups[func.groupname].append(func)
                    else:
                        self.groups[func.groupname] = [func]
