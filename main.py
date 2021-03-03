import asyncio
import os

import discord
import pygame

import pgbot.commands
import pgbot.util
from pgbot.constants import *
import random

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
            blocked_users.append(pgbot.util.filter_id(msg.content))
        except ValueError:
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
            blocked_users.append(pgbot.util.filter_id(msg.content))
        except ValueError:
            pass

    if msg.author.bot:
        return

    if BONK in msg.content and not msg.content.startswith(PREFIX):
        pgbot.commands.boncc_count += msg.content.count(BONK)
        if msg.content.count(BONK) > BONCC_THRESHOLD / 2 or pgbot.commands.boncc_count > BONCC_THRESHOLD:
            await pgbot.util.send_embed(
                msg.channel,
                "Did you hit the snek?",
                "You mortal mammal! How you dare to boncc a snake?"
            )
            await msg.channel.send(PG_ANGRY_AN)

        if pgbot.commands.boncc_count > 2 * BONCC_THRESHOLD:
            pgbot.commands.boncc_count = 2 * BONCC_THRESHOLD

    if msg.content.startswith(PREFIX):
        if msg.author.id in blocked_users:
            await pgbot.util.send_embed(
                msg.channel,
                "You are blocked from using the bot",
                "If you're unsure why you are blocked, please contact " + \
                "an admin/moderator"
            )
            return

        in_dm = " in DM" if isinstance(msg.channel, discord.DMChannel) else ""
        await pgbot.util.send_embed(
            log_channel,
            f"Command invoked by {msg.author} / {msg.author.id}{in_dm}",
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
                await pgbot.commands.admin_command(
                    bot, msg, msg.content[len(PREFIX):].split(), PREFIX
                )
            else:
                await pgbot.commands.user_command(
                    bot, msg, msg.content[len(PREFIX):].split(), PREFIX, is_priv
                )
        except discord.errors.Forbidden:
            pass

    if not isinstance(msg.channel, discord.DMChannel):
        has_a_competence_role = False
        for role in msg.author.roles:
            if role.id in COMPETENCE_ROLES:
                has_a_competence_role = True

        if not has_a_competence_role and msg.channel.id in PYGAME_CHANNELS:
            muted_role = discord.utils.get(msg.guild.roles, id=MUTED_ROLE)
            await msg.author.add_roles(muted_role)
            
            response_msg = await pgbot.util.send_embed(
                msg.channel,
                random.choice(ROLE_PROMPT["title"]),
                random.choice(ROLE_PROMPT["message"]).format(msg.author.mention)
            )
            await asyncio.sleep(30)
            await msg.author.remove_roles(muted_role)
            await response_msg.delete()


@bot.event
async def on_message_delete(msg: discord.Message):
    if msg.channel.id == BLOCKLIST_CHANNEL:
        try:
            blocked_users.remove(pgbot.util.filter_id(msg.content))
        except ValueError:
            pass


@bot.event
async def on_message_edit(old: discord.Message, new: discord.Message):
    if old.channel.id == BLOCKLIST_CHANNEL:
        try:
            blocked_users.remove(pgbot.util.filter_id(old.content))
            blocked_users.append(pgbot.util.filter_id(new.content))
        except ValueError:
            pass


if __name__ == "__main__":
    bot.run(TOKEN)
