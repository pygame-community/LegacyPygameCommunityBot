import time
from . import common, embed_utils


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
        await embed_utils.send_2(
            msg.channel,
            title="Did you hit the snek?",
            description="You mortal mammal! How you dare to boncc a snake?",
            thumbnail_url="https://cdn.discordapp.com/emojis/779775305224159232.gif"
        )