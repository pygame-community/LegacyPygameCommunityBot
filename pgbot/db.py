import asyncio
import discord
import json
import io
from copy import deepcopy

from pgbot import common


db_head_message = None
db_head_cache = {}
db_obj_cache = {}

write_lock = False


async def init(db_chan: discord.TextChannel):
    """
    Initialise DB head message and local cache. Call this function when the
    bot boots up
    """
    global db_head_message
    db_head_message = await db_chan.fetch_message(common.DB_HEAD_ID)
    await update(db_chan)


async def update(db_chan: discord.TextChannel):
    """
    Update all local caches to the latest ones from the DB
    """
    db_head_cache.clear()
    db_obj_cache.clear()
    for name, msg_id in json.loads(db_head_message.content).items():
        db_head_cache[name] = await db_chan.fetch_message(msg_id)
        db_obj_cache[name] = json.loads(await db_head_cache[name].attachments[0].read())


class DiscordDB:
    def __init__(self, name: str):
        """
        Initialise Discord DB Object
        """
        self.name = name

    async def get(self, failobj=None):
        """
        Get object of discord DB
        """
        try:
            latest_head = json.loads(db_head_message.content)[self.name]
        except KeyError:
            # DB does not exist, return
            return failobj

        # return cached object if it is the latest version
        if db_head_cache[self.name].id == latest_head:
            return deepcopy(db_obj_cache[self.name])

        # This case is very rare, we are almost guaranteed to already have a
        # cache
        db_head_cache[self.name] = await db_head_message.channel.fetch_message(
            latest_head
        )
        db_obj_cache[self.name] = json.loads(
            await db_head_cache[self.name].attachments[0].read()
        )
        return deepcopy(db_obj_cache[self.name])

    async def write(self, obj):
        """
        Store object in DB
        """
        global write_lock
        # If we already have the same object in the latest updated cache, return
        try:
            if (
                db_obj_cache[self.name] == obj
                and db_head_cache[self.name].id
                == json.loads(db_head_message.content)[self.name]
            ):
                return
        except KeyError:
            pass

        while write_lock:
            await asyncio.sleep(0.002)

        write_lock = True
        try:
            await update(db_head_message.channel)
            if self.name in db_head_cache:
                await db_head_cache[self.name].delete()

            with io.StringIO() as fobj:
                json.dump(obj, fobj)
                fobj.seek(0)

                db_head_cache[self.name] = await db_head_message.channel.send(
                    content=f"__**Table: {self.name}**__",
                    file=discord.File(fobj, filename="dbmsg.txt")
                )

            await db_head_message.edit(
                content=json.dumps({k: v.id for k, v in db_head_cache.items()})
            )
            db_obj_cache[self.name] = obj
        finally:
            write_lock = False
