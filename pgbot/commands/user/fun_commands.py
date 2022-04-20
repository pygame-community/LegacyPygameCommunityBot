"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file defines the command handler class for the "fun" commands of the bot
"""

from __future__ import annotations

import os
import random
import time

import discord
from discord.ext import commands
import pygame
import snakecore
from snakecore.command_handler.decorators import custom_parsing
import unidecode

from pgbot import common, db, emotion
import pgbot
from pgbot.commands.base import (
    BaseCommandCog,
)
from pgbot.commands.utils import vibecheck
from pgbot.commands.utils.checks import fun_command
from pgbot.exceptions import BotException


class FunCommandCog(BaseCommandCog):
    """
    Command cog defining "fun" commands.
    """

    @commands.command()
    @fun_command()
    async def version(self, ctx: commands.Context):
        """
        ->type Other commands
        ->signature pg!version
        ->description Get the version of <@&822580851241123860>
        -----
        Implement pg!version, to report bot version
        """

        response_message = common.recent_response_messages[ctx.message.id]

        await snakecore.utils.embed_utils.replace_embed_at(
            response_message,
            title="Current bot's version",
            description=f"`{common.__version__}`",
            color=common.DEFAULT_EMBED_COLOR,
        )

    @commands.command()
    @fun_command()
    async def ping(self, ctx: commands.Context):
        """
        ->type Other commands
        ->signature pg!ping
        ->description Get the ping of the bot
        -----
        Implement pg!ping, to get ping
        """

        response_message = common.recent_response_messages[ctx.message.id]

        timedelta = response_message.created_at - ctx.message.created_at
        sec = timedelta.total_seconds()
        sec2 = self.bot.latency  # This does not refresh that often
        if sec < sec2:
            sec2 = sec

        await snakecore.utils.embed_utils.replace_embed_at(
            response_message,
            title=random.choice(("Pingy Pongy", "Pong!")),
            description=f"The bot's ping is `{snakecore.utils.format_time_by_units(sec, decimal_places=0)}`\n"
            f"The Discord API latency is `{snakecore.utils.format_time_by_units(sec2, decimal_places=0)}`",
            color=common.DEFAULT_EMBED_COLOR,
        )

    @commands.group(invoke_without_command=True)
    @fun_command()
    @custom_parsing(inside_class=True, inject_message_reference=True)
    async def fontify(self, ctx: commands.Context, msg: str):
        """
        ->type Play With Me :snake:
        ->signature pg!fontify <msg>
        ->description Display message in pygame font
        """

        response_message = common.recent_response_messages[ctx.message.id]

        fontified = ""

        emojis = ()
        if common.guild is not None:
            emojis = tuple(sorted(common.guild.emojis, key=lambda x: x.name))

        for char in unidecode.unidecode(msg.string):
            if char.isalnum():
                for emoji in emojis:
                    if (
                        emoji.name == f"pg_char_{char}"
                        or emoji.name == f"pg_char_{char}".lower()
                    ):
                        fontified += str(emoji)
                        break
                else:
                    fontified += ":heavy_multiplication_x:"

            elif char.isspace():
                fontified += " " * 5

            else:
                fontified += ":heavy_multiplication_x:"

        if len(fontified) > 2000:
            raise BotException(
                "Could not execute comamnd",
                "Input text width exceeded maximum limit (2KB)",
            )

        if not fontified:
            raise BotException(
                "Could not execute comamnd",
                "Text cannot be empty",
            )

        await snakecore.utils.embed_utils.replace_embed_at(
            response_message,
            description=ctx.author.mention,
            color=0x40E32D,
        )

        await response_message.edit(content=fontified)

    fontify.command(name="remove")

    @fun_command()
    @custom_parsing(inside_class=True, inject_message_reference=True)
    async def fontify_remove(self, ctx: commands.Context, reply: discord.Message):
        """
        ->type Play With Me :snake:
        ->signature pg!fontify remove
        ->description Delete your fontified message by replying to it
        """

        response_message = common.recent_response_messages[ctx.message.id]

        if (
            reply.author.id != self.bot.user.id
            or not reply.embeds
            or reply.embeds[0].description != ctx.author.mention
        ):
            raise BotException(
                "Could not execute comamnd", "Please reply to a fontified message"
            )

        await reply.delete()
        try:
            await ctx.message.delete()
            await response_message.delete()
        except discord.NotFound:
            pass

    @commands.command()
    @fun_command()
    async def pet(self, ctx: commands.Context):
        """
        ->type Play With Me :snake:
        ->signature pg!pet
        ->description Pet me :3
        -----
        Implement pg!pet, to pet the bot
        """

        response_message = common.recent_response_messages[ctx.message.id]

        fname = "pet.gif"
        await snakecore.utils.embed_utils.replace_embed_at(
            response_message,
            color=common.DEFAULT_EMBED_COLOR,
            image_url="https://raw.githubusercontent.com/PygameCommunityDiscord/"
            + f"PygameCommunityBot/main/assets/images/{fname}",
        )

    @commands.command()
    @fun_command()
    async def vibecheck(self, ctx: commands.Context):
        """
        ->type Play With Me :snake:
        ->signature pg!vibecheck
        ->description Check my mood.
        -----
        Implement pg!vibecheck, to check the snek's emotion
        """

        response_message = common.recent_response_messages[ctx.message.id]

        async with db.DiscordDB("emotions") as db_obj:
            all_emotions = db_obj.get({})

        emotion_percentage = vibecheck.get_emotion_percentage(all_emotions, round_by=-1)
        all_emotion_response = vibecheck.get_emotion_desc_dict(all_emotions)

        bot_emotion = max(
            emotion_percentage.keys(), key=lambda key: emotion_percentage[key]
        )
        msg = all_emotion_response[bot_emotion]["msg"]
        emoji_link = all_emotion_response[bot_emotion]["emoji_link"]

        if all_emotion_response[bot_emotion].get("override_emotion", None):
            bot_emotion = all_emotion_response[bot_emotion]["override_emotion"]

        color = pygame.Color(vibecheck.EMOTION_COLORS[bot_emotion])

        t = time.time()
        pygame.image.save(
            vibecheck.emotion_pie_chart(all_emotions, 400), f"temp{t}.png"
        )
        file = discord.File(f"temp{t}.png")

        try:
            await response_message.delete()
        except discord.errors.NotFound:
            # Message already deleted
            pass

        embed_dict = {
            "title": f"The snek is {bot_emotion} right now!",
            "description": msg,
            "thumbnail_url": emoji_link,
            "footer_text": "This is currently in beta version, so the end product may look different",
            "footer_icon_url": "https://cdn.discordapp.com/emojis/844513909158969374.png?v=1",
            "image_url": f"attachment://temp{t}.png",
            "color": pgbot.utils.color_to_rgb_int(color),
        }
        embed = snakecore.utils.embed_utils.create_embed(**embed_dict)
        await ctx.message.reply(file=file, embed=embed, mention_author=False)

        os.remove(f"temp{t}.png")

    @commands.command()
    @fun_command()
    async def sorry(self, ctx: commands.Context):
        """
        ->type Play With Me :snake:
        ->signature pg!sorry
        ->description You were hitting me <:pg_bonk:780423317718302781> and you're now trying to apologize?
        Let's see what I'll say :unamused:
        -----
        Implement pg!sorry, to ask forgiveness from the bot after bonccing it
        """

        response_message = common.recent_response_messages[ctx.message.id]

        anger = await emotion.get("anger")
        if not anger:
            await snakecore.utils.embed_utils.replace_embed_at(
                response_message,
                title="Ask forgiveness from snek?",
                description="Snek is not angry. Awww, don't be sorry.",
                color=common.DEFAULT_EMBED_COLOR,
            )
            return

        num = random.randint(0, 20)
        if num:
            await snakecore.utils.embed_utils.replace_embed_at(
                response_message,
                title="Ask forgiveness from snek?",
                description="Your pythonic lord accepts your apology.\n"
                + f"Now go to code again.\nAnger level is {max(anger - num, 0)}",
                color=common.DEFAULT_EMBED_COLOR,
            )
            await emotion.update("anger", -num)
        else:
            await snakecore.utils.embed_utils.replace_embed_at(
                response_message,
                title="Ask forgiveness from snek?",
                description="How did you dare to boncc a snake?\nBold of you to"
                + " assume I would apologize to you, two-feet-standing being!\n"
                + f"The anger level is {anger}",
                color=common.DEFAULT_EMBED_COLOR,
            )
