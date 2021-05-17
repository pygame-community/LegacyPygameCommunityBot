"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file defines some utitities and functions for the bots emotion system
"""


import asyncio
import time

from . import common, db, embed_utils

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

        emotion_stuff = await db_obj.get({})
        try:
            emotion_stuff["bonk_in_past_day"] += 1
        except KeyError:
            emotion_stuff["bonk_in_past_day"] = 1

        await db_obj.write(emotion_stuff)

        # Wait 24 hours, then remove one command
        # TODO: refactor this system, because 24 hour sleeps are not reliable at all
        await asyncio.sleep(24 * 60 * 60)

        emotion_stuff = await db_obj.get({})
        emotion_stuff["bonk_in_past_day"] -= 1
        await db_obj.write(emotion_stuff)
