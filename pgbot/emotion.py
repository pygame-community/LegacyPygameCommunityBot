"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file defines some utitities and functions for the bots emotion system
"""
import random
import math
import discord
import unidecode

from pgbot import common, db
from pgbot.utils import embed_utils, utils

EMOTION_CAPS = {
    "happy": (-100, 100),
    "anger": (0, 100),
    "bored": (-100, 100),
    "confused": (0, 100),
}


async def update(emotion_name: str, value: int):
    """
    Update emotion characteristic 'emotion_name' with value 'value' integer
    """
    async with db.DiscordDB("emotions") as db_obj:
        emotions = db_obj.get({})
        try:
            emotions[emotion_name] += value
        except KeyError:
            emotions[emotion_name] = value

        emotions[emotion_name] = utils.clamp(
            emotions[emotion_name], *EMOTION_CAPS[emotion_name]
        )
        db_obj.write(emotions)


async def get(emotion_name: str):
    """
    Get emotion characteristic 'emotion_name'
    """
    async with db.DiscordDB("emotions") as db_obj:
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
    if await get("anger") + bonks > 30:
        await embed_utils.send_2(
            msg.channel,
            title="Did you hit the snek?",
            description="You mortal mammal! How you dare to boncc a snake?",
            thumbnail_url="https://cdn.discordapp.com/emojis/779775305224159232.gif",
        )
    bonks = math.floor(math.log2(msg.content.count(common.BONK)))

    await update("anger", bonks)
    await update("happy", -bonks)


async def dad_joke(msg: discord.Message):
    """
    Utility to handle the bot making dad jokes
    """
    lowered = unidecode.unidecode(msg.content.lower().strip())
    if "i am" in lowered and len(lowered) < 60:
        name = msg.content[lowered.index("i am") + 4 :].strip()
        if name:
            await msg.channel.send(
                f"Hi {name}! I am <@!{common.bot.user.id}>",
                allowed_mentions=discord.AllowedMentions.none(),
            )
        elif lowered == "i am":
            await msg.channel.send(random.choice(common.SHAKESPEARE_QUOTES))


async def euphoria():
    async with db.DiscordDB("emotions") as db_obj:
        db_obj.write(
            {
                "happy": EMOTION_CAPS["happy"][1],
                "anger": EMOTION_CAPS["anger"][0],
                "bored": 0,
                "confused": 0,
            }
        )


async def server_boost(msg: discord.Message):
    await euphoria()
    await msg.channel.send("A LOT OF THANKSSS! :heart: <:pg_party:772652894574084098>")
