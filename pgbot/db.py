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

# Store "name: pickled data" pairs as cache. Do not store unpickled data
db_obj_cache: dict[str, bytes] = {}

# Optimisation: store per-db bool on whether it got updated or not
db_changed: dict[str, bool] = {}

# store per-resource lock
db_locks: dict[str, asyncio.Lock] = {}

# bool to indicate whether db module was init
is_init: bool = False


async def init():
    """
    Initialise local cache and db channel. Call this function when the
    bot boots up
    """
    global is_init

    if is_init or common.TEST_MODE or common.GENERIC:
        is_init = True
        return

    async for msg in common.db_channel.history():
        if msg.attachments:
            db_obj_cache[msg.content] = await msg.attachments[0].read()
            db_changed[msg.content] = False

    is_init = True


async def quit():
    """
    Flushes local cache for storage to the DB, and cleans up
    """
    global is_init
    if not is_init or common.TEST_MODE or common.GENERIC:
        is_init = False
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
    is_init = False


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
        if name not in db_locks:
            db_locks[name] = asyncio.Lock()
        self._lock = db_locks[name]

    async def acquire(self):
        """
        Acquire internal resource lock
        """
        # wait for a maximum of 10 seconds for init to happen if it has not
        for _ in range(1000):
            if is_init:
                break
            await asyncio.sleep(0.01)
        else:
            raise RuntimeError("pgbot.db module was not init")

        await self._lock.acquire()

    def release(self):
        """
        Release internal resource lock
        """
        self._lock.release()

    async def __aenter__(self):
        """
        Aquire lock, "with" statement support
        """
        await self.acquire()
        return self

    async def __aexit__(self, *_):
        """
        Release lock, "with" statement support
        """
        self.release()

    def _check_active(self):
        if not self._lock.locked() or not is_init:
            raise RuntimeError("Invalid operation on unlocked data object")

    def get(self, failobj=None):
        """
        Get object of discord DB
        """
        self._check_active()
        try:
            return pickle.loads(db_obj_cache[self.name])
        except KeyError:
            return failobj

    def write(self, obj):
        """
        Store object in DB
        """
        self._check_active()
        dumped = pickle.dumps(obj)
        if dumped != db_obj_cache.get(self.name):
            db_obj_cache[self.name] = dumped
            db_changed[self.name] = True

    def delete(self):
        """
        Delete DB, returns whether it was deleted successfully
        """
        self._check_active()
        db_changed[self.name] = True
        try:
            db_obj_cache.pop(self.name)
            return True
        except KeyError:
            return False
