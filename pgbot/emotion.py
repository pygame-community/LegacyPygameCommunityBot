import time
from . import common, util


last_pet = time.time() - 3600
pet_anger = 0.1
boncc_count = 0


async def check_bonk(msg):
    global boncc_count
    if boncc_count > 2 * common.BONCC_THRESHOLD:
        boncc_count = 2 * common.BONCC_THRESHOLD

    if common.BONK not in msg.content:
        return

    boncc_count += msg.content.count(common.BONK)
    if (msg.content.count(common.BONK) > common.BONCC_THRESHOLD / 2
            or boncc_count > common.BONCC_THRESHOLD):
        await util.send_embed(
            msg.channel,
            "Did you hit the snek?",
            "You mortal mammal! How you dare to boncc a snake?"
        )
        await msg.channel.send(common.PG_ANGRY_AN)
