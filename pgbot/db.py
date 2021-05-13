import asyncio
import discord
import pickle
import io

from pgbot import common


db_channel = None

# Store "name: pickled data" pairs as cache. Do not store unpickled data
db_obj_cache = {}

write_lock = False


async def init(db_chan: discord.TextChannel):
    """
    Initialise local cache and db channel. Call this function when the
    bot boots up
    """
    global db_channel
    db_channel = db_chan

    async for msg in db_channel.history():
        if msg.attachments:
            db_obj_cache[msg.content] = await msg.attachments[0].read()


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
        if common.TEST_MODE:
            # Caches are not reliable on test mode, when more than one testbot runs
            async for msg in db_channel.history():
                if msg.attachments and msg.content == self.name:
                    db_obj_cache[msg.content] = await msg.attachments[0].read()
                    break

        try:
            return pickle.loads(db_obj_cache[self.name])
        except KeyError:
            return failobj

    async def write(self, obj):
        """
        Store object in DB
        """
        global write_lock

        while write_lock:
            await asyncio.sleep(0.002)

        write_lock = True
        try:
            async for msg in db_channel.history():
                if msg.content == self.name:
                    await msg.delete()

            with io.BytesIO() as fobj:
                pickle.dump(obj, fobj)

                fobj.seek(0)
                await db_channel.send(self.name, file=discord.File(fobj))

                fobj.seek(0)
                db_obj_cache[self.name] = fobj.read()
        finally:
            write_lock = False
