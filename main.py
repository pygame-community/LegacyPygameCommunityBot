import asyncio
import os
import random

import discord
import pygame

from pgbot import commands, common, emotion, util


@common.bot.event
async def on_ready():
    """
    Startup routines when the bot starts
    """
    print("The PygameCommunityBot is now online!")
    print("The bot is present in these server(s):")
    for server in common.bot.guilds:
        print("-", server.name)
        for channel in server.channels:
            print(" +", channel.name)
            if channel.id == common.LOG_CHANNEL_ID:
                common.log_channel = channel
            if channel.id == common.ARRIVALS_CHANNEL_ID:
                common.arrivals_channel = channel
            if channel.id == common.GUIDE_CHANNEL_ID:
                common.guide_channel = channel
            if channel.id == common.ROLES_CHANNEL_ID:
                common.roles_channel = channel
            if channel.id == common.ENTRIES_DISCUSSION_CHANNEL_ID:
                common.entries_discussion_channel = channel
            for key, value in common.ENTRY_CHANNEL_IDS.items():
                if channel.id == value:
                    common.entry_channels[key] = channel

    while True:
        await common.bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="discord.io/pygame_community"
            )
        )
        await asyncio.sleep(2.5)
        await common.bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.playing,
                name="in discord.io/pygame_community"
            )
        )
        await asyncio.sleep(2.5)


@common.bot.event
async def on_member_join(member: discord.Member):
    """
    This function handles the greet message when a new member joins
    """
    if common.TEST_MODE:
        # Do not greet people in test mode
        return

    greet = random.choice(common.BOT_WELCOME_MSG["greet"])
    check = random.choice(common.BOT_WELCOME_MSG["check"])

    grab = random.choice(common.BOT_WELCOME_MSG["grab"])
    end = random.choice(common.BOT_WELCOME_MSG["end"])

    # This function is called right when a member joins, even before the member
    # finishes the join screening. So we wait for that to happen and then send
    # the message. Wait for a maximum of one hour.
    if not member.bot:
        for _ in range(3600):
            await asyncio.sleep(1)

            if not member.pending:
                # Don't use embed here, because pings would not work
                await common.arrivals_channel.send(
                    f"{greet} {member.mention}! {check} "
                    + f"{common.guide_channel.mention}{grab} "
                    + f"{common.roles_channel.mention}{end}"
                )
                return

    # Member did not complete screen within an hour of joining. This is sus,
    # so give sus bot role
    bot_sus = discord.utils.get(member.guild.roles, id=common.BOT_SUS_ROLE)
    await member.add_roles(bot_sus)

@common.bot.event
async def on_message(msg: discord.Message):
    """
    This function is called for every message by user.
    """
    if msg.author.bot:
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
            if len(common.cmd_logs) > 100:
                del common.cmd_logs[common.cmd_logs.keys()[0]]
        except discord.HTTPException:
            pass
    else:
        await emotion.check_bonk(msg)

    if not common.TEST_MODE and msg.channel.id in common.ENTRY_CHANNEL_IDS.values():
        if msg.channel.id == common.ENTRY_CHANNEL_IDS["showcase"]:
            entry_type = "showcase"
            color = 0xFF8800
        else:
            entry_type = "resource"
            color = 0x0000AA

        title, fields = util.format_entries_message(msg, entry_type)
        await util.send_embed(
            common.entries_discussion_channel,
            title,
            "",
            color,
            fields=fields
        )


@common.bot.event
async def on_message_delete(msg: discord.Message):
    """
    This function is called for every message deleted by user.
    """
    if msg.id in common.cmd_logs.keys():
        del common.cmd_logs[msg.id]

    elif msg.author.id == common.bot.user.id:
        for log in common.cmd_logs.keys():
            if common.cmd_logs[log].id == msg.id:
                del common.cmd_logs[log]
                return


@common.bot.event
async def on_message_edit(old: discord.Message, new: discord.Message):
    """
    This function is called for every message edited by user.
    """
    if new.author.bot:
        return

    if new.content.startswith(common.PREFIX):
        try:
            if new.id in common.cmd_logs.keys():
                await commands.handle(new, common.cmd_logs[new.id])
        except discord.HTTPException:
            pass
    else:
        await emotion.check_bonk(new)


if __name__ == "__main__":
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    pygame.init()  # pylint: disable=no-member
    common.window = pygame.display.set_mode((1, 1))
    common.bot.run(common.TOKEN)
