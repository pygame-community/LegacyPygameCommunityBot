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

# Store "name: pickled data" pairs as cache. Do not store unpickled data
db_obj_cache = {}

# Optimisation: store per-db bool on whether it got updated or not
db_changed = {}


async def init():
    """
    Initialise local cache and db channel. Call this function when the
    bot boots up
    """

    if common.TEST_MODE or common.GENERIC:
        return

    async for msg in common.db_channel.history():
        if msg.attachments:
            db_obj_cache[msg.content] = await msg.attachments[0].read()
            db_changed[msg.content] = False


async def quit():
    """
    Flushes local cache for storage to the DB, and cleans up
    """
    if common.TEST_MODE or common.GENERIC:
        return

    print("Calling cleanup functions!")
    async for msg in common.db_channel.history():
        if msg.content in db_obj_cache and db_changed[msg.content]:
            await msg.delete()

    for name, picked in db_obj_cache.items():
        if not db_changed[name]:
            continue

        with io.BytesIO(picked) as fobj:
            await common.db_channel.send(name, file=discord.File(fobj))

    print("Successfully called cleanup functions")


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
        dumped = pickle.dumps(obj)
        if dumped != db_obj_cache.get(self.name):
            db_obj_cache[self.name] = dumped
            db_changed[self.name] = True

    def delete(self):
        """
        Delete DB, returns whether it was deleted successfully
        """
        db_changed[self.name] = True
        try:
            db_obj_cache.pop(self.name)
            return True
        except KeyError:
            return False
