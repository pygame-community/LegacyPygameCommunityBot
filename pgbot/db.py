"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file defines some important utility Classes/functions for Discord Database
"""


import asyncio
import io
import pickle

import discord

from pgbot import common

db_channel = None

# Store "name: pickled data" pairs as cache. Do not store unpickled data
db_obj_cache = {}

# We need a lock because we do not want simultaneous access to DB
lock = asyncio.Lock()


async def init(db_chan: discord.TextChannel):
    """
    Initialise local cache and db channel. Call this function when the
    bot boots up
    """
    global db_channel
    db_channel = db_chan

    async for msg in db_channel.history():
        if msg.author.id == common.bot.user.id and msg.attachments:
            db_obj_cache[msg.content] = await msg.attachments[0].read()


class DiscordDB:
    """
    DiscordDB is a class to interface with a DB like solution, that stores data
    via discord messages
    """

    def __init__(self, name: str):
        """
        Initialise Discord DB Object
        """
        self.name = name

    async def get(self, failobj=None):
        """
        Get object of discord DB
        """
        async with lock:
            if common.TEST_MODE:
                # Caches are not reliable on test mode, when more than one
                # testbot runs
                async for msg in db_channel.history():
                    if msg.author.id != common.bot.user.id:
                        continue

                    if msg.attachments and msg.content == self.name:
                        db_obj_cache[self.name] = await msg.attachments[0].read()
                        break

            try:
                return pickle.loads(db_obj_cache[self.name])
            except KeyError:
                return failobj

    async def write(self, obj):
        """
        Store object in DB
        """

        async with lock:
            async for msg in db_channel.history():
                if msg.author.id != common.bot.user.id:
                    continue

                if msg.content == self.name:
                    await msg.delete()

            db_obj_cache[self.name] = pickle.dumps(obj)
            with io.BytesIO(db_obj_cache[self.name]) as fobj:
                await db_channel.send(self.name, file=discord.File(fobj))
