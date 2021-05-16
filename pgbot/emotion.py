import asyncio
import time
from . import common, embed_utils, utils, db

last_pet = time.time() - 3600
pet_anger = 0.1
boncc_count = 0
db_obj = db.DiscordDB("emotion")


async def check_bonk(msg):
    global boncc_count
    if boncc_count > 2 * common.BONCC_THRESHOLD:
        boncc_count = 2 * common.BONCC_THRESHOLD

    if common.BONK not in msg.content:
        return

    boncc_count += msg.content.count(common.BONK)
    if (
        msg.content.count(common.BONK) > common.BONCC_THRESHOLD / 2
        or boncc_count > common.BONCC_THRESHOLD
    ):
        await embed_utils.send_2(
            msg.channel,
            title="Did you hit the snek?",
            description="You mortal mammal! How you dare to boncc a snake?",
            thumbnail_url="https://cdn.discordapp.com/emojis/779775305224159232.gif",
        )

        emotion_stuff = await db_obj.get([])
        await db_obj.write(
            {
                "cmd_in_past_day": emotion_stuff["cmd_in_past_day"],
                "bonk_in_past_day": emotion_stuff["bonk_in_past_day"] + 1
            }
        )

        await asyncio.sleep(24*60*60)
        # NOTE: Heroku would restart the bot erratically, so
        #       there may be "ghost" commands that would never reset.
        #       To reset them, just reset all the values to 0 in the DB

        emotion_stuff = await db_obj.get([])
        await db_obj.write(
            {
                "cmd_in_past_day": emotion_stuff["cmd_in_past_day"],
                "bonk_in_past_day": emotion_stuff["bonk_in_past_day"] - 1
            }
        )
