import asyncio
import os
import random
import sys

import discord
import pygame

from pgbot import *


# Aliases
bot = common.bot


def setup():
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    pygame.init()
    common.window = pygame.display.set_mode((1, 1))


def main():
    setup()
    common.bot.run(common.TOKEN)


@bot.event
async def on_ready():
    print("The PygameCommunityBot is now online!")
    print("The bot is present in these server(s):")
    for server in bot.guilds:
        print("-", server.name)
        for channel in server.channels:
            print("+", channel.name)
            if channel.id == common.LOG_CHANNEL_ID:
                common.log_channel = channel

    while True:
        await bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching, name="discord.io/pygame_community"
            )
        )
        await asyncio.sleep(2.5)
        await bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.playing, name="in discord.io/pygame_community"
            )
        )
        await asyncio.sleep(2.5)


@bot.event
async def on_message(msg: discord.Message):
    if msg.author.bot:
        return

    if await moderation.check_sus(msg):
        return

    if msg.content.startswith(common.PREFIX):
        try:
            response = await util.send_embed(
                msg.channel,
                "Your command is being processed!",
                ""
            )

            await commands.handle(msg, response)
            common.cmd_logs[msg.id] = response
        except discord.HTTPException:
            pass


@bot.event
async def on_message_delete(msg: discord.Message):
    if msg.id in common.cmd_logs.keys():
        del common.cmd_logs[msg.id]


@bot.event
async def on_message_edit(old: discord.Message, new: discord.Message):
    if new.author.bot:
        return

    if await moderation.check_sus(new):
        return

    if new.content.startswith(common.PREFIX):
        try:
            if new.id in common.cmd_logs.keys():
                await commands.handle(new, common.cmd_logs[new.id])
        except discord.HTTPException:
            pass


if __name__ == "__main__":
    main()
else:
    raise ImportError("This is not a module")
