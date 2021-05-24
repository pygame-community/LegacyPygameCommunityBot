"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file defines some utitities and functions for the bots emotion system
"""

import discord
import unidecode

from . import common, db, embed_utils

EMOTION_CAPS = {
    "happy": (-100, 100),
    "anger": (0, 100),
    "bored": (-1000, 1000),
}


db_obj = db.DiscordDB("emotions")


def update(emotion_name: str, value: int):
    """
    Update emotion characteristic 'emotion_name' with value 'value' integer
    """
    emotions = db_obj.get({})
    try:
        emotions[emotion_name] += value
    except KeyError:
        emotions[emotion_name] = value

    if emotions[emotion_name] < EMOTION_CAPS[emotion_name][0]:
        emotions[emotion_name] = EMOTION_CAPS[emotion_name][0]

    if emotions[emotion_name] > EMOTION_CAPS[emotion_name][1]:
        emotions[emotion_name] = EMOTION_CAPS[emotion_name][1]

    db_obj.write(emotions)


def get(emotion_name: str):
    """
    Get emotion characteristic 'emotion_name'
    """
    emotions = db_obj.get({})
    try:
        return emotions[emotion_name]
    except KeyError:
        return 0


async def check_bonk(msg: discord.Message):
    if common.BONK not in msg.content:
        return

    bonks = msg.content.count(common.BONK)
    if get("anger") + bonks > 30:
        await embed_utils.send_2(
            msg.channel,
            title="Did you hit the snek?",
            description="You mortal mammal! How you dare to boncc a snake?",
            thumbnail_url="https://cdn.discordapp.com/emojis/779775305224159232.gif",
        )

    update("anger", bonks)
    update("happy", -bonks)


async def dad_joke(msg: discord.Message):
    lowered = unidecode.unidecode(msg.content.lower().strip())
    if (" i am " in lowered or lowered.startswith("i am ") or lowered == "i am") and len(lowered) < 60:
        name = msg.content[lowered.index("i am") + 4:].strip()
        if name:
            await msg.channel.send(
                f"Hi {name}! I am <@!{common.BOT_ID}>", allowed_mentions=discord.AllowedMentions.none()
            )
        elif lowered == 'i am':
            await msg.channel.send(common.SHAKESPEARE_QUOTE)
