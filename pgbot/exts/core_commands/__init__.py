"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present pygame-community

This file exports a handle function, to handle commands posted by the users
"""

from __future__ import annotations
import snakecore


async def setup(bot: snakecore.commands.Bot):
    await bot.load_extension("core_commands.help")
    await bot.load_extension("core_commands.admin")
    await bot.load_extension("core_commands.user")


async def teardown(bot: snakecore.commands.Bot):
    await bot.unload_extension("core_commands.help")
    await bot.unload_extension("core_commands.admin")
    await bot.unload_extension("core_commands.user")
