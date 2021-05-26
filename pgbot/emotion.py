"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file defines some utitities and functions for the bots emotion system
"""
import random

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
    """
    Function to check bonk, update emotion state, and reply when bonked
    """
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
    bonks = msg.content.count(common.BONK) // 5 + random.randint(0, 8)

    update("anger", bonks)
    update("happy", -bonks)


async def dad_joke(msg: discord.Message):
    """
    Utility to handle the bot making dad jokes
    """
    lowered = unidecode.unidecode(msg.content.lower().strip())
    if (
        " i am " in lowered or lowered.startswith("i am ") or lowered == "i am"
    ) and len(lowered) < 60:
        name = msg.content[msg.content.lower()("i am") + 4 :].strip()
        if name:
            await msg.channel.send(
                f"Hi {name}! I am <@!{common.bot.user.id}>",
                allowed_mentions=discord.AllowedMentions.none(),
            )
        elif lowered == "i am":
            await msg.channel.send(common.SHAKESPEARE_QUOTE)


def euphoria():
    db_obj.write(
        {
            "happy": EMOTION_CAPS["happy"][1],
            "anger": EMOTION_CAPS["anger"][0],
            "bored": 0,
        }
    )


async def server_boost(msg: discord.Message):
    euphoria()
    await msg.channel.send("A LOT OF THANKSSS! :heart: :pg_snake:")
