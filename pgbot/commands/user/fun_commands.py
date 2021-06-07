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
import pygame
import unidecode

from pgbot import common, db, emotion
from pgbot.commands.base import (
    BaseCommand,
    BotException,
    String,
    add_group,
    fun_command,
)
from pgbot.commands.utils import vibecheck
from pgbot.utils import embed_utils, utils


class FunCommand(BaseCommand):
    """
    Command class to handle "fun" commands.
    """

    @fun_command
    async def cmd_version(self):
        """
        ->type Other commands
        ->signature pg!version
        ->description Get the version of <@&822580851241123860>
        -----
        Implement pg!version, to report bot version
        """
        await embed_utils.replace(
            self.response_msg, "Current bot's version", f"`{common.VERSION}`"
        )

    @fun_command
    async def cmd_ping(self):
        """
        ->type Other commands
        ->signature pg!ping
        ->description Get the ping of the bot
        -----
        Implement pg!ping, to get ping
        """
        timedelta = self.response_msg.created_at - self.invoke_msg.created_at
        sec = timedelta.total_seconds()
        sec2 = common.bot.latency  # This does not refresh that often
        if sec < sec2:
            sec2 = sec

        await embed_utils.replace(
            self.response_msg,
            random.choice(("Pingy Pongy", "Pong!")),
            f"The bot's ping is `{utils.format_time(sec, 0)}`\n"
            f"The Discord API latency is `{utils.format_time(sec2, 0)}`",
        )

    @fun_command
    @add_group("fontify")
    async def cmd_fontify(self, msg: String):
        """
        ->type Play With Me :snake:
        ->signature pg!fontify <msg>
        ->description Display message in pygame font
        """
        fontified = ""

        for char in unidecode.unidecode(msg.string):
            if char.isalnum():
                for emoji in sorted(self.guild.emojis, key=lambda x: x.name):
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

        await embed_utils.replace_2(
            self.response_msg,
            description=self.author.mention,
            color=0x40E32D,
        )

        await self.response_msg.edit(content=fontified)

    @fun_command
    @add_group("fontify", "remove")
    async def cmd_fontify_remove(self, reply: discord.Message):
        """
        ->type Play With Me :snake:
        ->signature pg!fontify remove
        ->description Delete your fontified message by replying to it
        """

        if (
            reply.author.id != common.bot.user.id
            or not reply.embeds
            or reply.embeds[0].description != self.author.mention
        ):
            raise BotException(
                "Could not execute comamnd", "Please reply to a fontified message"
            )

        await reply.delete()
        await self.invoke_msg.delete()
        await self.response_msg.delete()

    @fun_command
    async def cmd_pet(self):
        """
        ->type Play With Me :snake:
        ->signature pg!pet
        ->description Pet me :3
        -----
        Implement pg!pet, to pet the bot
        """
        fname = "die.gif" if emotion.get("anger") > 60 else "pet.gif"
        await embed_utils.replace(
            self.response_msg,
            "",
            "",
            0xFFFFAA,
            "https://raw.githubusercontent.com/PygameCommunityDiscord/"
            + f"PygameCommunityBot/main/assets/images/{fname}",
        )

        emotion.update("happy", 5)

    @fun_command
    async def cmd_vibecheck(self):
        """
        ->type Play With Me :snake:
        ->signature pg!vibecheck
        ->description Check my mood.
        -----
        Implement pg!vibecheck, to check if the bot is angry
        """
        db_obj = db.DiscordDB("emotions")
        all_emotions = db_obj.get({})

        emotion_percentage = vibecheck.get_emotion_percentage(all_emotions, round_by=-1)

        all_emotion_response = {
            "happy": {
                "msg": f"I feel... happi!\n"
                       f"While I am happi, I would make more dad jokes (Spot the dad joke in there?)\n"
                       f'However, don\'t bonk me or say "ded chat", as that would make me sad.\n'
                       f"*The snek's happiness level is `{all_emotions.get('happy', '0')}`, don't let it go to zero!*",
                "emoji_link": "https://cdn.discordapp.com/emojis/837389387024957440.png?v=1",
            },
            "sad": {
                "msg": f"I'm sad...\n"
                       f"I don't feel like making any jokes. This is your fault, **don't make me sad.**\n"
                       f"Pet me pls :3\n*The snek's happiness level is `{all_emotions.get('happy', '0')}`, play with"
                       f" it to cheer it up*",
                "emoji_link": "https://cdn.discordapp.com/emojis/824721451735056394.png?v=1",
            },
            "exhausted": {
                "msg": f"I'm exhausted. \nI ran too many commands, "
                       f"so I'll be resting for a while..\n"
                       f"Don't try to make me run commands for now, I'll most likely just ignore it..\n"
                       f"*The snek's boredom level is `{all_emotions.get('exhausted', '0')}`. To make its "
                       f"exhaustion go down, let it rest for a bit.*",
                "emoji_link": None,
            },
            "bored": {
                "msg": f"I'm booooooooored...\nNo one is spending time with me, "
                       f"and I feel lonely :pg_depressed:\n"
                       f"*The snek's boredom level is `{all_emotions.get('bored', '0')}`, run about"
                       f"`{abs((all_emotions.get('bored', 600) - 600 // 15))}` more command(s) to improve its mood.*",
                "emoji_link": "https://cdn.discordapp.com/emojis/823502668500172811.png?v=1",
            },
            "confused": {
                "msg": f"I'm confused!\nEither there were too many exceptions in my code, "
                       f"or too many commands were used wrongly!\n*The snek's confusion level is "
                       f"`{all_emotions.get('confused', '0')}`.\nTo lower its level of confusion, use proper command "
                       f"syntax.*",
                "emoji_link": "https://cdn.discordapp.com/emojis/837402289709907978.png?v=1",
            },
            "anger": {
                "msg": f"I'm angry!\nI've been bonked too many times, you'd be "
                       f"angry too if someone bonked you 50+ times :unamused:\n"
                       f"No jokes, no quotes. :pg_angry:. Don't you dare pet me!"
                       f"*The snek's anger level is `{all_emotions.get('anger', '0')}`, ask for its forgiveness"
                       f"to calm it down.*",
                "emoji_link": "https://cdn.discordapp.com/emojis/779775305224159232.gif?v=1",
                "override_emotion": "angry",
            },
        }

        bot_emotion = max(
            emotion_percentage.keys(), key=lambda key: emotion_percentage[key]
        )
        msg = all_emotion_response[bot_emotion]["msg"]
        emoji_link = all_emotion_response[bot_emotion]["emoji_link"]

        if all_emotion_response[bot_emotion].get("override_emotion", None):
            bot_emotion = all_emotion_response[bot_emotion]["override_emotion"]

        t = time.time()
        pygame.image.save(
            vibecheck.emotion_pie_chart(all_emotions, 400), f"temp{t}.png"
        )
        file = discord.File(f"temp{t}.png")

        try:
            await self.response_msg.delete()
        except discord.errors.NotFound:
            # Message already deleted
            pass
        embed_dict = {
            "title": f"The snek is {bot_emotion} right now!",
            "description": msg,
            "thumbnail_url": emoji_link,
            "footer_text": "This is currently in beta version, so the end product may look different",
            "footer_icon_url": "https://cdn.discordapp.com/emojis/844513909158969374.png?v=1",
            "image_url": f"attachment://temp{t}.png"
        }
        embed = await embed_utils.send_2(
            None,
            **embed_dict
        )
        await self.invoke_msg.reply(
            file=file, embed=embed, mention_author=False
        )

        os.remove(f"temp{t}.png")

    @fun_command
    async def cmd_sorry(self):
        """
        ->type Play With Me :snake:
        ->signature pg!sorry
        ->description You were hitting me <:pg_bonk:780423317718302781> and you're now trying to apologize?
        Let's see what I'll say :unamused:
        -----
        Implement pg!sorry, to ask forgiveness from the bot after bonccing it
        """
        anger = emotion.get("anger")
        if not anger:
            await embed_utils.replace(
                self.response_msg,
                "Ask forgiveness from snek?",
                "Snek is not angry. Awww, don't be sorry.",
            )
            return

        num = random.randint(0, 10)
        if num:
            await embed_utils.replace(
                self.response_msg,
                "Ask forgiveness from snek?",
                "Your pythonic lord accepts your apology.\n"
                + f"Now go to code again.\nAnger level is {max(anger - num, 0)}",
            )
            emotion.update("anger", -num)
        else:
            await embed_utils.replace(
                self.response_msg,
                "Ask forgiveness from snek?",
                "How did you dare to boncc a snake?\nBold of you to assume "
                + "I would apologize to you, two-feet-standing being!\nThe "
                + f"Anger level is {anger}",
            )
