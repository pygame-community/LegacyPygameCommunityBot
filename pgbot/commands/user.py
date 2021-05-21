"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file defines the command handler class for the user commands of the bot
"""

from __future__ import annotations

import copy
import datetime
import os
import random
import re
import time
from typing import Optional

import discord
import pygame
from pgbot import clock, common, docs, embed_utils, emotion, sandbox, utils, db
from pgbot.commands.base import (
    BaseCommand,
    BotException,
    CodeBlock,
    HiddenArg,
    String,
    fun_command,
    add_group,
)


class UserCommand(BaseCommand):
    """Base class to handle user commands."""

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
            f"The bots ping is `{utils.format_time(sec, 0)}`\n"
            f"The Discord API latency is `{utils.format_time(sec2, 0)}`",
        )

    async def cmd_rules(self, *rules: int):
        """
        ->type Get help
        ->signature pg!rules [*rule_numbers]
        ->description Get rules of the server
        -----
        Implement pg!rules, to get rules of the server
        """
        if not rules:
            raise BotException("Please enter rule number(s)", "")

        rule_chan = self.guild.get_channel(common.RULES_CHANNEL_ID)
        fields = []
        for rule in sorted(set(rules)):
            if 0 < rule <= len(common.RULES):
                msg = await rule_chan.fetch_message(common.RULES[rule - 1])
                value = msg.content

            elif rule == 42:
                value = (
                    "*Shhhhh*, you have found an unwritten rule!\n"
                    "Click [here](https://bitly.com/98K8eH) to gain the most "
                    "secret and ultimate info!"
                )

            else:
                value = "Does not exist lol"

            fields.append(
                {
                    "name": f"__Rule number {rule}:__",
                    "value": value,
                    "inline": False,
                }
            )

        if len(rules) == 1:
            await embed_utils.replace_2(
                self.response_msg,
                author_name="Pygame Community",
                author_icon_url=common.GUILD_ICON,
                title=fields[0]["name"],
                description=fields[0]["value"][:2048],
                color=0x228B22,
            )
        else:
            for field in fields:
                field["value"] = field["value"][:1024]

            await embed_utils.replace_2(
                self.response_msg,
                author_name="Pygame Community",
                author_icon_url=common.GUILD_ICON,
                title="Rules",
                fields=fields,
                color=0x228B22,
            )

    @add_group("reminders", "add")
    async def cmd_reminders_add(
        self,
        msg: String,
        on: datetime.datetime,
        delta: HiddenArg = None,
    ):
        """
        ->type Reminders
        ->signature pg!reminders add <message> <datetime in iso format>
        ->description Set a reminder to yourself
        ->extended description
        Allows you to set a reminder to yourself
        The date-time must be ISO time formatted string, in UTC time
        string
        ->example command pg!reminders add "do the thing" "2034-10-26 11:19:36"
        -----
        Implement pg!reminders_add, for users to set reminders for themselves
        """
        now = datetime.datetime.utcnow()

        if delta is None:
            delta = on - now
        else:
            on = now + delta

        if on < now:
            raise BotException(
                "Failed to set reminder!",
                "Time cannot go backwards, negative time does not make sense..."
                "\n Or does it? \\*vsauce music plays in the background\\*",
            )

        elif delta <= datetime.timedelta(seconds=10):
            raise BotException(
                "Failed to set reminder!",
                "Why do you want me to set a reminder for such a small duration?\n"
                "Pretty sure you can remember that one yourself :wink:",
            )

        # remove microsecond precision of the 'on' variable
        on -= datetime.timedelta(microseconds=on.microsecond)

        db_obj = db.DiscordDB("reminders")
        db_data = db_obj.get({})
        if self.author.id not in db_data:
            db_data[self.author.id] = {}

        limit = 25 if self.is_priv else 10
        if len(db_data[self.author.id]) >= limit:
            raise BotException(
                "Failed to set reminder!",
                f"I cannot set more than {limit} reminders for you",
            )

        db_data[self.author.id][on] = (
            msg.string.strip(),
            self.channel.id,
            self.invoke_msg.id,
        )
        db_obj.write(db_data)

        await embed_utils.replace(
            self.response_msg,
            "Reminder set!",
            f"Gonna remind {self.author.name} in {utils.format_timedelta(delta)}\n"
            f"And that is on {on} UTC",
        )

    @add_group("reminders", "set")
    async def cmd_reminders_set(
        self,
        msg: String,
        timestr: String = String(""),
        weeks: int = 0,
        days: int = 0,
        hours: int = 0,
        minutes: int = 0,
        seconds: int = 0,
    ):
        """
        ->type Reminders
        ->signature pg!reminders set <message> [time string] [weeks] [days] [hours] [minutes] [seconds]
        ->description Set a reminder to yourself
        ->extended description
        There are two ways you can pass the time duration, one is via a "time string"
        and the other is via keyword arguments
        `weeks`, `days`, `hours`, `minutes` and `seconds` are optional arguments you can
        specify to describe the time duration you want to set the reminder for
        ->example command pg!reminders set "Become pygame expert" weeks=9 days=12 hours=23 minutes=16 seconds=35
        -----
        Implement pg!reminders_set, for users to set reminders for themselves
        """
        timestr = timestr.string.strip()
        if timestr:
            time_formats = {
                "w": 7 * 24 * 60 * 60,
                "d": 24 * 60 * 60,
                "h": 60 * 60,
                "m": 60,
                "s": 1,
            }
            sec = 0

            for time_format, dt in time_formats.items():
                try:
                    results = re.search(rf"\d+{time_format}", timestr).group()
                    parsed_time = int(results.replace(time_format, ""))
                    sec += parsed_time * dt
                except AttributeError:
                    pass

            if "mo" in timestr:
                month_results = re.search(rf"\d+mo", timestr).group()
                parsed_month_time = int(month_results.replace("mo", ""))
                sec += (
                    self.invoke_msg.created_at.replace(
                        month=self.invoke_msg.created_at.month + parsed_month_time
                    )
                    - self.invoke_msg.created_at
                ).total_seconds()

            if sec == 0:
                raise BotException(
                    "Failed to set reminder!",
                    "There is something wrong with your time parameter.\n"
                    "Please check that it is correct and try again",
                )

            delta = datetime.timedelta(seconds=sec)
        else:
            delta = datetime.timedelta(
                weeks=weeks,
                days=days,
                hours=hours,
                minutes=minutes,
                seconds=seconds,
            )

        await self.cmd_reminders_add(msg, None, delta=delta)

    @add_group("reminders")
    async def cmd_reminders(self):
        """
        ->type Reminders
        ->signature pg!reminders
        ->description View all the reminders you have set
        -----
        Implement pg!reminders, for users to view their reminders
        """
        db_data = db.DiscordDB("reminders").get({})

        msg = "You have no reminders set"
        if self.author.id in db_data:
            msg = ""
            cnt = 0
            for on, (reminder, chan_id, _) in db_data[self.author.id].items():
                channel = self.guild.get_channel(chan_id)
                cin = channel.mention if channel is not None else "DM"
                msg += (
                    f"Reminder ID: `{cnt}`\n"
                    f"**On `{on}` in {cin}:**\n> {reminder}\n\n"
                )
                cnt += 1

        await embed_utils.replace(
            self.response_msg,
            f"Reminders for {self.author.display_name}:",
            msg,
        )

    @add_group("reminders", "remove")
    async def cmd_reminders_remove(self, *reminder_ids: int):
        """
        ->type Reminders
        ->signature pg!reminders remove [*datetimes]
        ->description Remove reminders
        ->extended description
        Remove variable number of reminders, corresponding to each datetime argument
        The reminder id argument must be an integer
        If no arguments are passed, the command clears all reminders
        ->example command pg!reminder remove 1
        -----
        Implement pg!reminders_remove, for users to remove their reminders
        """
        db_obj = db.DiscordDB("reminders")
        db_data = db_obj.get({})
        db_data_copy = copy.deepcopy(db_data)
        cnt = 0
        if reminder_ids:
            for reminder_id in sorted(set(reminder_ids), reverse=True):
                if self.author.id in db_data:
                    for i, dt in enumerate(db_data_copy[self.author.id]):
                        if i == reminder_id:
                            db_data[self.author.id].pop(dt)
                            cnt += 1
                            break
                if reminder_id >= len(db_data_copy[self.author.id]) or reminder_id < 0:
                    raise BotException(
                        "Invalid Reminder ID!",
                        "Reminder ID was not an existing reminder ID",
                    )

            if self.author.id in db_data and not db_data[self.author.id]:
                db_data.pop(self.author.id)

        elif self.author.id in db_data:
            cnt = len(db_data.pop(self.author.id))

        db_obj.write(db_data)
        await embed_utils.replace(
            self.response_msg,
            "Reminders removed!",
            f"Successfully removed {cnt} reminder(s)",
        )

    async def cmd_clock(
        self,
        action: str = "",
        timezone: float = 0,
        color: Optional[pygame.Color] = None,
        member: HiddenArg = None,
    ):
        """
        ->type Get help
        ->signature pg!clock
        ->description 24 Hour Clock showing <@&778205389942030377> 's who are available to help
        -> Extended description
        People on the clock can run the clock with more arguments, to update their data.
        `pg!clock update [timezone in hours] [color as hex string]`
        `timezone` is float offset from GMT in hours.
        `color` optional color argument, that shows up on the clock.
        Note that you might not always display with that colour.
        This happens if more than one person are on the same timezone
        Use `pg!clock remove` to remove yourself from the clock
        -----
        Implement pg!clock, to display a clock of helpfulies/mods/wizards
        """
        db_obj = db.DiscordDB("clock")

        timezones = db_obj.get([])
        if action:
            if member is None:
                member = self.author
                for mem_id, _, _ in timezones:
                    if mem_id == member.id:
                        break
                else:
                    raise BotException(
                        "Cannot update clock!",
                        "You cannot run clock update commands because you are "
                        + "not on the clock",
                    )

            if action == "update":
                if abs(timezone) > 12:
                    raise BotException(
                        "Failed to update clock!", "Timezone offset out of range"
                    )

                for cnt, (mem_id, _, _) in enumerate(timezones):
                    if mem_id == member.id:
                        timezones[cnt][1] = timezone
                        if color is not None:
                            timezones[cnt][2] = int(color)
                        break
                else:
                    if color is None:
                        raise BotException(
                            "Failed to update clock!",
                            "Color argument is required when adding new people",
                        )
                    timezones.append([member.id, timezone, int(color)])
                    timezones.sort(key=lambda x: x[1])

            elif action == "remove":
                for cnt, (mem_id, _, _) in enumerate(timezones):
                    if mem_id == member.id:
                        timezones.pop(cnt)
                        break
                else:
                    raise BotException(
                        "Failed to update clock!",
                        "Cannot remove non-existing person from clock",
                    )

            else:
                raise BotException(
                    "Failed to update clock!", f"Invalid action specifier {action}"
                )

            db_obj.write(timezones)

        t = time.time()

        pygame.image.save(
            await clock.user_clock(t, timezones, self.guild), f"temp{t}.png"
        )
        common.cmd_logs[self.invoke_msg.id] = await self.response_msg.channel.send(
            file=discord.File(f"temp{t}.png")
        )
        os.remove(f"temp{t}.png")

        await self.response_msg.delete()

    async def cmd_doc(self, name: str, page: HiddenArg = 0, msg: HiddenArg = None):
        """
        ->type Get help
        ->signature pg!doc <object name>
        ->description Look up the docstring of a Python/Pygame object, e.g str or pygame.Rect
        -----
        Implement pg!doc, to view documentation
        """
        if not msg:
            msg = self.response_msg

        await docs.put_doc(name, msg, self.author, page)

    async def cmd_exec(self, code: CodeBlock):
        """
        ->type Run code
        ->signature pg!exec <python code block>
        ->description Run python code in an isolated environment.
        ->extended description
        Import is not available. Various methods of builtin objects have been disabled for security reasons.
        The available preimported modules are:
        `math, cmath, random, re, time, string, itertools, pygame`
        To show an image, overwrite `output.img` to a surface (see example command).
        To make it easier to read and write code use code blocks (see [HERE](https://discord.com/channels/772505616680878080/774217896971730974/785510505728311306)).
        ->example command pg!exec \\`\\`\\`py ```py
        # Draw a red rectangle on a transparent surface
        output.img = pygame.Surface((200, 200)).convert_alpha()
        output.img.fill((0, 0, 0, 0))
        pygame.draw.rect(output.img, (200, 0, 0), (50, 50, 100, 100))```
        \\`\\`\\`
        -----
        Implement pg!exec, for execution of python code
        """
        async with self.channel.typing():
            tstamp = time.perf_counter_ns()

            returned = await sandbox.exec_sandbox(
                code.code, tstamp, 10 if self.is_priv else 5
            )
            dur = returned.duration  # the execution time of the script alone

            embed_dict = {
                "description": "",
                "author_name": f"Code executed in {utils.format_time(dur)}",
                "author_url": self.invoke_msg.jump_url,
            }
            file = None
            exc = None

            if returned.exc is None:
                if returned.text:
                    embed_dict["description"] += "**Text output:**\n"
                    embed_dict["description"] += utils.code_block(returned.text, 2000)

                if returned.img:
                    if os.path.getsize(f"temp{tstamp}.png") < 2 ** 22:
                        embed_dict["description"] += "\n**Image output:**"
                        embed_dict["image_url"] = f"attachment://temp{tstamp}.png"
                        file = discord.File(f"temp{tstamp}.png")
                    else:
                        exc = (
                            "Image could not be sent",
                            "The image file size is above 4MiB",
                        )

                elif returned.imgs:
                    if os.path.getsize(f"temp{tstamp}.gif") < 2 ** 22:
                        embed_dict["description"] += "\n**GIF output:**"
                        embed_dict["image_url"] = f"attachment://temp{tstamp}.gif"
                        file = discord.File(f"temp{tstamp}.gif")
                    else:
                        exc = ("Unable to send gif", "Gif size is above 4mib")
            else:
                exc = (
                    "An exception occured:",
                    utils.code_block(", ".join(map(str, returned.exc.args))),
                )

        try:
            await self.response_msg.delete()
        except discord.errors.NotFound:
            # Message already deleted
            pass

        if exc is not None:
            embed = await embed_utils.send(
                self.channel,
                exc[0],
                exc[1],
                color=0xFF0000,
                do_return=True,
            )
        else:
            embed = await embed_utils.send_2(None, **embed_dict)

        await self.invoke_msg.reply(file=file, embed=embed, mention_author=False)

        if file:
            file.close()

        if os.path.isfile(f"temp{tstamp}.gif"):
            os.remove(f"temp{tstamp}.gif")

        if os.path.isfile(f"temp{tstamp}.png"):
            os.remove(f"temp{tstamp}.png")

    async def cmd_help(self, *names: str, page: HiddenArg = 0, msg: HiddenArg = None):
        """
        ->type Get help
        ->signature pg!help [command]
        ->description Ask me for help
        ->example command pg!help help
        -----
        Implement pg!help, to display a help message
        """
        if not msg:
            msg = self.response_msg

        name = " ".join(names)
        functions = {}
        for key, func in self.cmds_and_funcs.items():
            if hasattr(func, "groupname"):
                functions[f"{func.groupname} {' '.join(func.subcmds)}"] = func
            else:
                functions[key] = func

        if name:
            await utils.send_help_message(msg, self.author, functions, name)
        else:
            await utils.send_help_message(msg, self.author, functions, page=page)

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
        await embed_utils.replace(
            self.response_msg,
            "TODO",
            "We are working on an upgrade for this",
        )

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

        num = random.randint(0, 7)
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

    async def cmd_refresh(self, msg: discord.Message):
        """
        ->type Other commands
        ->signature pg!refresh <message>
        ->description Refresh a message which support pages.
        -----
        Implement pg!refresh, to refresh a message which supports pages
        """

        if not msg.embeds or not msg.embeds[0].footer or not msg.embeds[0].footer.text:
            raise BotException(
                "Message does not support pages",
                "The message specified does not support pages. Make sure "
                "the id of the message is correct.",
            )

        data = msg.embeds[0].footer.text.split("\n")

        page = re.search(r"\d+", data[0]).group()
        command = data[2].replace("Command: ", "").split()

        if not page or not command or not self.cmds_and_funcs.get(command[0]):
            raise BotException(
                "Message does not support pages",
                "The message specified does not support pages. Make sure "
                "the id of the message is correct.",
            )

        await self.response_msg.delete()
        if command[0] == "help":
            await self.cmd_help(*command[1:], page=int(page) - 1, msg=msg)
        elif command[0] == "doc":
            await self.cmd_doc(command[1], page=int(page) - 1, msg=msg)

    @add_group("poll")
    async def cmd_poll(
        self,
        desc: String,
        *emojis: String,
        admin_embed: HiddenArg = {},
    ):
        """
        ->type Other commands
        ->signature pg!poll <description> [*args]
        ->description Start a poll.
        ->extended description
        `pg!poll description *args`
        The args must be strings with one emoji and one description of said emoji (see example command). \
        The emoji must be a default emoji or one from this server. To close the poll see 'pg!poll close'.
        ->example command pg!poll "Which apple is better?" "🍎" "Red apple" "🍏" "Green apple"
        """
        if self.is_dm:
            raise BotException(
                "Cannot run poll commands on DM",
                "Who are you trying to poll? Yourself? :smiley: \n"
                + "Please run your poll on the Pygame Community Server!",
            )

        newline = "\n"
        base_embed = {
            "title": "Voting in progress",
            "fields": [
                {
                    "name": "🔺",
                    "value": "Agree",
                    "inline": True,
                },
                {
                    "name": "🔻",
                    "value": "Disagree",
                    "inline": True,
                },
            ],
            "author": {
                "name": self.author.name,
            },
            "color": 0x34A832,
            "footer": {
                "text": f"By {self.author.display_name}{newline}"
                f"({self.author.id}){newline}Started"
            },
            "timestamp": self.response_msg.created_at.isoformat(),
            "description": desc.string,
        }
        base_embed.update(admin_embed)

        if emojis:
            if len(emojis) <= 3 or len(emojis) % 2:
                raise BotException(
                    "Invalid arguments for emojis.",
                    "Please add at least 2 emojis with 2 descriptions."
                    " Each emoji should have their own description."
                    " Make sure each argument is a different string. For more"
                    " information, see `pg!help poll`",
                )

            base_embed["fields"] = []
            for i, substr in enumerate(emojis):
                if not i % 2:
                    base_embed["fields"].append(
                        {
                            "name": substr.string.strip(),
                            "value": common.ZERO_SPACE,
                            "inline": True,
                        }
                    )
                else:
                    base_embed["fields"][i // 2]["value"] = substr.string.strip()

        await embed_utils.replace_from_dict(self.response_msg, base_embed)

        for field in base_embed["fields"]:
            try:
                emoji_id = utils.filter_emoji_id(field["name"].strip())
                emoji = common.bot.get_emoji(emoji_id)
                if emoji is None:
                    raise ValueError()
            except ValueError:
                emoji = field["name"]

            try:
                await self.response_msg.add_reaction(emoji)
            except (discord.errors.HTTPException, discord.errors.NotFound):
                # Either a custom emoji was used (which could not be added by
                # our beloved snek) or some other error happened. Clear the
                # reactions and prompt the user to make sure it is the currect
                # emoji.
                await self.response_msg.clear_reactions()
                raise BotException(
                    "Invalid emoji",
                    "The emoji could not be added as a reaction. Make sure it is"
                    " the correct emoji and that it is not from another server",
                )

    async def cmd_close_poll(self, msg):
        """
        ->skip
        Stub for old function
        """
        raise BotException(
            "Command 'pg!close_poll' does not exist",
            "Perhaps you meant, 'pg!poll close'",
        )

    @add_group("poll", "close")
    async def cmd_poll_close(
        self,
        msg: discord.Message,
        color: HiddenArg = None,
    ):
        """
        ->type Other commands
        ->signature pg!poll close <message>
        ->description Close an ongoing poll.
        ->extended description
        The poll can only be closed by the person who started it or by mods.
        """
        newline = "\n"
        if self.is_dm:
            raise BotException(
                "Cannot run poll commands on DM",
                "Who are you trying to poll? Yourself? :smiley: \n"
                + "Please run your poll on the Pygame Community Server!",
            )

        if not msg.embeds:
            raise BotException(
                "Invalid message",
                "The message specified is not an ongoing vote."
                " Please double-check the id.",
            )

        embed = msg.embeds[0]
        # Take the second line remove the parenthesies
        if embed.footer.text and embed.footer.text.count("\n"):
            poll_owner = int(
                embed.footer.text.split("\n")[1].replace("(", "").replace(")", "")
            )
        else:
            raise BotException(
                "Invalid message",
                "The message specified is not an ongiong vote."
                " Please double-check the id.",
            )

        if color is None and self.author.id != poll_owner:
            raise BotException(
                "You cant stop this vote",
                "The vote was not started by you."
                " Ask the person who started it to close it.",
            )

        title = "Voting has ended"
        reactions = {}
        for reaction in msg.reactions:
            if isinstance(reaction.emoji, str):
                reactions[reaction.emoji] = reaction.count
            else:
                reactions[reaction.emoji.id] = reaction.count

        top = [(0, None)]
        for reaction in msg.reactions:
            if getattr(reaction.emoji, "id", reaction.emoji) not in reactions:
                continue

            if reaction.count - 1 > top[0][0]:
                top = [
                    (reaction.count - 1, getattr(reaction.emoji, "id", reaction.emoji))
                ]
                continue

            if reaction.count - 1 == top[0][0]:
                top.append((reaction.count - 1, reaction.emoji))

        fields = []
        for field in embed.fields:
            try:
                r_count = reactions[utils.filter_emoji_id(field.name)] - 1
            except KeyError:
                # The reactions and the embed fields dont match up.
                # Someone is abusing their mod powers if this happens probably.
                continue

            fields.append([field.name, f"{field.value} ({r_count} votes)", True])

            if utils.filter_emoji_id(field.name) == top[0][1]:
                title += (
                    f"{newline}{field.value}({field.name}) "
                    f"has won with {top[0][0]} votes!"
                )

        if len(top) >= 2:
            title = title.split("\n")[0]
            title += "\nIt's a draw!"

        await embed_utils.edit_2(
            msg,
            embed,
            color=0xA83232 if not color else utils.color_to_rgb_int(color),
            title=title,
            fields=fields,
            footer_text="Ended",
            timestamp=self.response_msg.created_at.isoformat(),
        )
        await self.response_msg.delete()

    async def cmd_resources(
        self,
        limit: Optional[int] = None,
        filter_tag: Optional[String] = None,
        filter_member: Optional[discord.Member] = None,
        oldest_first: bool = False,
    ):
        """
        ->type Get help
        ->signature pg!resources [limit] [filter_tag] [filter_member] [oldest_first]
        ->description Browse through resources.
        ->extended description
        pg!resources takes in additional arguments, though they are optional.
        `oldest_first`: Set oldest_first to True to browse through the oldest resources
        `limit=[num]`: Limits the number of resources to the number
        `filter_tag=[tag]`: Includes only the resources with that tag(s)
        `filter_member=[member]`: Includes only the resources posted by that user
        ->example command pg!resources limit=5 oldest_first=True filter_tag="python, gamedev" filter_member=444116866944991236
        """
        # NOTE: It is hardcoded in the bot to remove some messages in resource-entries,
        #       if you want to remove more, add the ID to the list below
        msgs_to_filter = {
            817137523905527889,
            810942002114986045,
            810942043488256060,
        }

        def process_tag(tag: str):
            for to_replace in ("tag_", "tag-", "<", ">", "`"):
                tag = tag.replace(to_replace, "")
            return tag.title()

        def filter_func(x):
            return x.id != msg_to_filter

        resource_entries_channel = self.guild.get_channel(
            common.ENTRY_CHANNEL_IDS["resource"]
        )

        msgs = await resource_entries_channel.history(
            oldest_first=oldest_first
        ).flatten()

        # Filters any messages that have the same ID as the ones provided in msgs_to_filter
        for msg_to_filter in msgs_to_filter:
            msgs = list(filter(filter_func, msgs))

        if filter_tag:
            # Filter messages based on tag
            filter_tag = filter_tag.string.split(",")
            filter_tag = [tag.strip() for tag in filter_tag]
            for tag in filter_tag:
                tag = tag.lower()
                msgs = list(
                    filter(
                        lambda x: f"tag_{tag}" in x.content.lower()
                        or f"tag-<{tag}>" in x.content.lower(),
                        msgs,
                    )
                )

        if filter_member:
            msgs = list(filter(lambda x: x.author.id == filter_member.id, msgs))

        if limit is not None:
            # Uses list slicing instead of TextChannel.history's limit param
            # to include all param specified messages
            msgs = msgs[:limit]

        tags = {}
        old_tags = {}
        links = {}
        for msg in msgs:
            # Stores the tags (tag_{Your tag here}), old tags (tag-<{your tag here}>),
            # And links inside separate dicts with regex
            links[msg.id] = [
                match.group()
                for match in re.finditer("http[s]?://(www.)?[^ \n]+", msg.content)
            ]
            tags[msg.id] = [
                f"`{process_tag(match.group())}` "
                for match in re.finditer("tag_.+", msg.content.lower())
            ]
            old_tags[msg.id] = [
                f"`{process_tag(match.group())}` "
                for match in re.finditer("tag-<.+>", msg.content.lower())
            ]

        pages = []
        copy_msgs = msgs[:]
        i = 1
        while msgs:
            # Constructs embeds based on messages, and store them in pages to be used in the paginator
            top_msg = msgs[:6]
            if len(copy_msgs) > 1:
                title = (
                    f"Retrieved {len(copy_msgs)} entries in "
                    f"#{resource_entries_channel.name}"
                )
            else:
                title = (
                    f"Retrieved {len(copy_msgs)} entry in "
                    f"#{resource_entries_channel.name}"
                )
            current_embed = discord.Embed(title=title)

            for msg in top_msg:
                try:
                    name = msg.content.split("\n")[1].strip().replace("**", "")
                    if not name:
                        continue

                    field_name = f"{i}. {name}, posted by {msg.author.display_name}"
                    # If the field name is > 256 (discord limit), shorten it with list slicing
                    field_name = f"{field_name[:253]}..."

                    value = msg.content.split(name)[1].removeprefix("**").strip()
                    # If the preview of the resources > 80, shorten it with list slicing
                    value = f"{value[:80]}..."
                    value += f"\n\nLinks: **[Message]({msg.jump_url})**"

                    for j, link in enumerate(links[msg.id], 1):
                        value += f", [Link {j}]({link})"

                    value += "\nTags: "
                    if tags[msg.id]:
                        value += "".join(tags[msg.id]).removesuffix(",")
                    elif old_tags[msg.id]:
                        value += "".join(old_tags[msg.id]).removesuffix(",")
                    else:
                        value += "None"

                    current_embed.add_field(
                        name=field_name,
                        value=f"{value}\n{common.ZERO_SPACE}",
                        inline=True,
                    )
                    i += 1
                except IndexError:
                    # Suppresses IndexError because of rare bug
                    pass

            pages.append(current_embed)
            msgs = msgs[6:]

        if len(pages) == 0:
            raise BotException(
                f"Retrieved 0 entries in #{resource_entries_channel.name}",
                "There are no results of resources with those parameters. Please try again.",
            )

        # Creates a paginator for the caller to use
        page_embed = embed_utils.PagedEmbed(
            self.response_msg, pages, caller=self.author
        )

        await page_embed.mainloop()

    @add_group("stream")
    async def cmd_stream(self):
        """
        ->type Reminders
        ->signature pg!stream
        ->description Show the ping-stream-list
        Send an embed with all the users currently in the ping-stream-list
        """
        data = db.DiscordDB("stream").get([])
        if not data:
            await embed_utils.replace(
                self.response_msg,
                "Memento ping list",
                "Ping list is empty!",
            )
            return

        await embed_utils.replace(
            self.response_msg,
            "Memento ping list",
            "Here is a list of people who want to be pinged when stream starts"
            "\nUse 'pg!stream ping' to ping them if you start streaming\n"
            + "\n".join((f"<@{user}>" for user in data)),
        )

    @add_group("stream", "add")
    async def cmd_stream_add(self, members: HiddenArg = None):
        """
        ->type Reminders
        ->signature pg!stream add
        ->description Add yourself to the stream-ping-list
        ->extended description
        Add yourself to the stream-ping-list. You can always delete \
        you later with `pg!stream del`
        """
        ping_db = db.DiscordDB("stream")
        data: list = ping_db.get([])

        if members:
            for mem in members:
                if mem.id not in data:
                    data.append(mem.id)
        elif self.author.id not in data:
            data.append(self.author.id)

        ping_db.write(data)
        await self.cmd_stream()

    @add_group("stream", "del")
    async def cmd_stream_del(self, members: HiddenArg = None):
        """
        ->type Reminders
        ->signature pg!stream del
        ->description Remove yourself from the stream-ping-list
        ->extended description
        Remove yourself from the stream-ping-list. You can always add \
        you later with `pg!stream add`
        """
        ping_db = db.DiscordDB("stream")
        data: list = ping_db.get([])

        try:
            if members:
                for mem in members:
                    data.remove(mem.id)
            else:
                data.remove(self.author.id)
        except ValueError:
            raise BotException(
                "Could not remove member",
                "Member was not previously added to the ping list",
            )

        ping_db.write(data)
        await self.cmd_stream()

    @add_group("stream", "ping")
    async def cmd_stream_ping(self, message: Optional[String] = None):
        """
        ->type Reminders
        ->signature pg!stream ping [message]
        ->description Ping users in stream-list with an optional message.
        ->extended description
        Ping all users in the ping list to announce a stream.
        You can pass an optional stream message (like the stream topic).
        The streamer name will be included and many people will be pinged so \
        don't make pranks with this command.
        """
        data: list = db.DiscordDB("stream").get([])

        msg = message.string if message else "Enjoy the stream!"
        ping = (
            "Pinging everyone on ping list:\n"
            + "\n".join((f"<@!{user}>" for user in data))
            if data
            else "No one is registered on the ping momento :/"
        )

        await self.response_msg.delete()
        await self.channel.send(f"<@!{self.author.id}> is gonna stream!\n{msg}\n{ping}")
