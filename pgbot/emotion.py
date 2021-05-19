"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file defines some utitities and functions for the bots emotion system
"""

import discord

from . import common, db, embed_utils

EMOTION_CAPS = {
    "happy": (-100, 100),
    "anger": (0, 100),
    "bored": (-1000, 1000),
}


db_obj = db.DiscordDB("emotions")


async def update(emotion_name: str, value: int):
    """
    Update emotion characteristic 'emotion_name' with value 'value' integer
    """
    emotions = await db_obj.get({})
    try:
        emotions[emotion_name] += value
    except KeyError:
        emotions[emotion_name] = value

    if emotions[emotion_name] < EMOTION_CAPS[emotion_name][0]:
        emotions[emotion_name] = EMOTION_CAPS[emotion_name][0]

    if emotions[emotion_name] > EMOTION_CAPS[emotion_name][1]:
        emotions[emotion_name] = EMOTION_CAPS[emotion_name][1]

    await db_obj.write(emotions)


async def get(emotion_name: str):
    """
    Get emotion characteristic 'emotion_name'
    """
    emotions = await db_obj.get({})
    try:
        return emotions[emotion_name]
    except KeyError:
        return 0


async def check_bonk(msg: discord.Message):
    if common.BONK not in msg.content:
        return

    bonks = msg.content.count(common.BONK)
    if (await get("anger")) + bonks > 30:
        await embed_utils.send_2(
            msg.channel,
            title="Did you hit the snek?",
            description="You mortal mammal! How you dare to boncc a snake?",
            thumbnail_url="https://cdn.discordapp.com/emojis/779775305224159232.gif",
        )

    await update("anger", bonks)
    await update("happy", -bonks)
