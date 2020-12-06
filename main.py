import asyncio
import os

import discord
import pygame

import commands
import util
from constants import (
    CHANNEL_LINKS,
    ALLOWED_SERVERS,
    PREFIX,
    ADMIN_ROLES,
    PRIV_ROLES,
    ADMIN_USERS,
    PGCOMMUNITY,
    COMPETENCE_ROLES,
    PYGAME_CHANNELS,
    TOKEN,
)

os.environ["SDL_VIDEODRIVER"] = "dummy"
pygame.init()  # pylint: disable=no-member
dummy = pygame.display.set_mode((69, 69))
bot = discord.Client()
noted_channels = {}


@bot.event
async def on_ready():
    channels = []
    for channel in CHANNEL_LINKS.keys():
        channels.append(CHANNEL_LINKS[channel])
    channels = set(channels)

    print("PygameBot ready!\nThe bot is in:")
    for server in bot.guilds:
        if server.id not in ALLOWED_SERVERS:
            await server.leave()
            continue
        print("-", server.name)
        for channel in server.channels:
            print("  +", channel.name)
            if channel.id in channels:
                noted_channels[channel.id] = channel

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

    if isinstance(msg.channel, discord.DMChannel):
        await msg.channel.send("Please do commands at the server!")
        return

    if msg.channel.id in CHANNEL_LINKS.keys():
        if not msg.attachments:
            fmsg = f"**<{msg.author}>** {msg.content}"
        else:
            fmsg = f"**<{msg.author}>**\n{chr(10).join([attachment.url for attachment in msg.attachments])}\n {msg.content}"

        if len(fmsg) > 2000:
            await noted_channels[CHANNEL_LINKS[msg.channel.id]].send(
                fmsg[:1996] + " ..."
            )
        else:
            await noted_channels[CHANNEL_LINKS[msg.channel.id]].send(fmsg)

        if msg.content.startswith(PREFIX):
            await util.send_embed(
                msg.channel,
                "Executing commands in a linked channel",
                "WARNING: The command output wouldn't be visible from the other side!",
            )

    if msg.content.startswith(PREFIX):
        is_admin = False
        is_priv = False
        for role in msg.author.roles:
            if role.id in ADMIN_ROLES:
                is_admin = True
            elif role.id in PRIV_ROLES:
                is_priv = True
        try:
            if is_admin or (msg.author.id in ADMIN_USERS):
                await commands.admin_command(
                    msg, msg.content[len(PREFIX) :].split(), PREFIX
                )
            else:
                await commands.user_command(
                    msg, msg.content[len(PREFIX) :].split(), PREFIX, is_priv, False
                )
        except discord.errors.Forbidden:
            pass

    if msg.channel.guild.id == PGCOMMUNITY:
        has_a_competence_role = False
        for role in msg.author.roles:
            if role.id in COMPETENCE_ROLES:
                has_a_competence_role = True

        if not has_a_competence_role and msg.channel.id in PYGAME_CHANNELS:
            response_msg = await util.send_embed(
                msg.channel,
                "Get more roles!",
                "Hey there, are you a beginner, intermediate or pro in pygame, or even a contributor? Tell Carl-Bot in <#772535163195228200>!",
            )
            await asyncio.sleep(15)
            await response_msg.delete()


bot.run(TOKEN)
