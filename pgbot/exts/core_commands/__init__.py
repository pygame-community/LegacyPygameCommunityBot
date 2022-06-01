"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present pygame-community

This file exports a handle function, to handle commands posted by the users
"""

from __future__ import annotations
import snakecore


async def setup(bot: snakecore.command_handler.Bot):
    await bot.load_extension(".help", package="core_commands")
    await bot.load_extension(".admin", package="core_commands")
    await bot.load_extension(".user", package="core_commands")


async def teardown(bot: snakecore.command_handler.Bot):
    await bot.unload_extension(".help", package="core_commands")
    await bot.unload_extension(".admin", package="core_commands")
    await bot.unload_extension(".user", package="core_commands")
