import asyncio
import os

import discord
import pygame

import commands
import util
from constants import *

os.environ["SDL_VIDEODRIVER"] = "dummy"
pygame.init()  # pylint: disable=no-member
dummy = pygame.display.set_mode((69, 69))

bot = discord.Client()

log_channel: discord.TextChannel
blocklist_channel: discord.TextChannel

blocked_users = []


@bot.event
async def on_ready():
    global log_channel, blocklist_channel

    print("PygameBot ready!\nThe bot is in:")
    for server in bot.guilds:
        print("-", server.name)
        for channel in server.channels:
            print("  +", channel.name)
            if channel.id == LOG_CHANNEL:
                log_channel = channel
            if channel.id == BLOCKLIST_CHANNEL:
                blocklist_channel = channel

    blocked_user_ids = await blocklist_channel.history(limit=4294967296).flatten()
    for msg in blocked_user_ids:
        try:
            blocked_users.append(int(util.filter_id(msg.content)))
        except Exception:
            pass

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
    if msg.channel.id == BLOCKLIST_CHANNEL:
        try:
            blocked_users.append(int(util.filter_id(msg.content)))
        except Exception:
            pass

    if msg.author.bot:
        return

    if msg.content.startswith(PREFIX):
        if msg.author.id in blocked_users:
            await util.send_embed(
                msg.channel,
                "You are blocked from using the bot",
                "If you're unsure why you are blocked, please contact an admin/moderator"
            )
            return

        await util.send_embed(
            log_channel,
            f"Command invoked by {msg.author} / {msg.author.id} in DM" if isinstance(msg.channel, discord.DMChannel) else
                f"Command invoked by {msg.author} / {msg.author.id}",
            msg.content,
        )

        is_admin = False
        is_priv = False

        if not isinstance(msg.channel, discord.DMChannel):
            for role in msg.author.roles:
                if role.id in ADMIN_ROLES:
                    is_admin = True
                elif role.id in PRIV_ROLES:
                    is_priv = True

        try:
            if is_admin or (msg.author.id in ADMIN_USERS):
                await commands.admin_command(
                    bot, msg, msg.content[len(PREFIX):].split(), PREFIX
                )
            else:
                await commands.user_command(
                    bot, msg, msg.content[len(PREFIX):].split(), PREFIX, is_priv, False
                )
        except discord.errors.Forbidden:
            pass

    if not isinstance(msg.channel, discord.DMChannel):
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


@bot.event
async def on_message_delete(msg: discord.Message):
    if msg.channel.id == BLOCKLIST_CHANNEL:
        try:
            blocked_users.remove(int(util.filter_id(msg.content)))
        except ValueError:
            pass


@bot.event
async def on_message_edit(old: discord.Message, new: discord.Message):
    if old.channel.id == BLOCKLIST_CHANNEL:
        try:
            blocked_users.remove(int(util.filter_id(old.content)))
        except ValueError:
            pass

        blocked_users.append(int(util.filter_id(new.content)))

bot.run(TOKEN)
