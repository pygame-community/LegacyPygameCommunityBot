"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file defines some important utility Classes/functions for Discord Database
"""

import io
import pickle

import discord

from pgbot import common

db_channel = None

# Store "name: pickled data" pairs as cache. Do not store unpickled data
db_obj_cache = {}


async def init(db_chan: discord.TextChannel):
    """
    Initialise local cache and db channel. Call this function when the
    bot boots up
    """
    global db_channel
    db_channel = db_chan

    if common.TEST_MODE:
        return

    async for msg in db_channel.history():
        if msg.attachments:
            db_obj_cache[msg.content] = await msg.attachments[0].read()


async def quit():
    """
    Flushes local cache for storage to the DB, and cleans up
    """
    print("Calling cleanup functions!")
    if common.TEST_MODE:
        return

    async for msg in db_channel.history():
        if msg.content in db_obj_cache:
            await msg.delete()

    for name, picked in db_obj_cache.items():
        with io.BytesIO(picked) as fobj:
            await db_channel.send(name, file=discord.File(fobj))


class DiscordDB:
    """
    DiscordDB is a class to interface with a DB like solution, that stores data
    via discord messages. Uses heavy caching, and saves to DB only on program
    exit
    """

    def __init__(self, name: str):
        """
        Initialise Discord DB Object
        """
        self.name = name

    def get(self, failobj=None):
        """
        Get object of discord DB
        """
        try:
            return pickle.loads(db_obj_cache[self.name])
        except KeyError:
            return failobj

    def write(self, obj):
        """
        Store object in DB
        """
        db_obj_cache[self.name] = pickle.dumps(obj)
