from __future__ import annotations

import asyncio
import os
import random
import re
import time
from typing import Optional

import discord
import pygame

from pgbot import clock, common, docs, embed_utils, emotion, sandbox, utils
from pgbot.commands.base import (
    BaseCommand, CodeBlock, HiddenArg, String, BotException
)


class UserCommand(BaseCommand):
    """ Base class to handle user commands. """

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
            "Pingy Pongy",
            f"The bots ping is `{utils.format_time(sec, 0)}`\n"
            + f"The Discord API latency is `{utils.format_time(sec2, 0)}`"
        )

    async def cmd_remind(self, msg: String, time: int):
        """
        ->type Other commands
        ->signature pg!remind [message string] [time in minutes]
        ->description Set a reminder to yourself
        -----
        Implement pg!remind, for users to set reminders for themselves
        """
        if time < 0:
            raise BotException(
                "Failed to set reminder!",
                "Time cannot go backwards, negative time does not make sense..."
                + "\n Or can it? *vsauce music plays in the background*"
            )

        if time > 360:
            raise BotException(
                "Failed to set reminder!",
                "The maximum time for which you can set reminder is 6 hours"
            )

        await embed_utils.replace(
            self.response_msg,
            f"Reminder set!",
            f"Gonna remind {self.author.name} in {time} minutes.\n"
            + "But do not solely rely on me though, cause I might forget to "
            + "remind you incase I am down."
        )
        await asyncio.sleep(time * 60)

        sendmsg = "__**Reminder for "
        sendmsg += self.author.mention + ":**__\n" + msg.string
        await self.channel.send(sendmsg)

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
        msg_id = common.DB_CLOCK_MSG_IDS[common.TEST_MODE]
        db_msg = await self.guild.get_channel(
            common.DB_CHANNEL_ID).fetch_message(msg_id)

        timezones = await clock.decode_from_msg(db_msg)
        if action:
            if member is None:
                member = self.author
                for mem, _, _ in timezones:
                    if mem.id == member.id:
                        break
                else:
                    raise BotException(
                        "Cannot update clock!",
                        "You cannot run clock update commands because you are "
                        + "not on the clock"
                    )

            if action == "update":
                for cnt, (mem, _, _) in enumerate(timezones):
                    if mem.id == member.id:
                        timezones[cnt][1] = timezone
                        if color is not None:
                            timezones[cnt][2] = color
                        break
                else:
                    if color is None:
                        raise BotException(
                            "Failed to update clock!",
                            "Color argument is required when adding new people"
                        )
                    timezones.append([member, timezone, color])
                    timezones.sort(key=lambda x: x[1])

            elif action == "remove":
                for cnt, (mem, _, _) in enumerate(timezones):
                    if mem.id == member.id:
                        timezones.pop(cnt)
                        break
                else:
                    raise BotException(
                        "Failed to update clock!",
                        "Cannot remove non-existing person from clock"
                    )

            else:
                raise BotException(
                    "Failed to update clock!",
                    f"Invalid action specifier {action}"
                )

            await db_msg.edit(content=clock.encode_to_msg(timezones))

        t = time.time()
        pygame.image.save(clock.user_clock(t, timezones), f"temp{t}.png")
        common.cmd_logs[self.invoke_msg.id] = \
            await self.response_msg.channel.send(file=discord.File(
                f"temp{t}.png"
            )
        )
        await self.response_msg.delete()
        os.remove(f"temp{t}.png")

    async def cmd_doc(
        self, name: str, page: HiddenArg = 0, msg: HiddenArg = None
    ):
        """
        ->type Get help
        ->signature pg!doc [module.Class.method]
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
        ->signature pg!exec [python code block]
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
        tstamp = time.perf_counter_ns()
        await self.channel.trigger_typing()

        returned = await sandbox.exec_sandbox(
            code.code, tstamp, 10 if self.is_priv else 5
        )
        dur = returned.duration  # the execution time of the script alone

        if returned.exc is None:
            if returned.img:
                if os.path.getsize(f"temp{tstamp}.png") < 2 ** 22:
                    await self.channel.send(
                        file=discord.File(f"temp{tstamp}.png")
                    )
                else:
                    await embed_utils.send(
                        self.channel,
                        "Image could not be sent:",
                        "The image file size is above 4MiB",
                        0xFF0000,
                    )
                os.remove(f"temp{tstamp}.png")

            await embed_utils.replace(
                self.response_msg,
                f"Returned text (code executed in {utils.format_time(dur)}):",
                utils.code_block(returned.text)
            )

        else:
            await embed_utils.replace(
                self.response_msg,
                "An exception occured:",
                utils.code_block(", ".join(map(str, returned.exc.args)))
            )

        # To reset the trigger_typing counter
        await (await self.channel.send("\u200b")).delete()

    async def cmd_help(
        self,
        name: Optional[str] = None,
        page: HiddenArg = 0,
        msg: HiddenArg = None
    ):
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

        if name is None:
            await utils.send_help_message(
                msg,
                self.author,
                self.cmds_and_funcs,
                page=page
            )
        else:
            await utils.send_help_message(
                msg,
                self.author,
                self.cmds_and_funcs,
                name
            )

    async def cmd_pet(self):
        """
        ->type Play With Me :snake:
        ->signature pg!pet
        ->description Pet me :3 . Don't pet me too much or I will get mad.
        -----
        Implement pg!pet, to pet the bot
        """
        emotion.pet_anger -= (time.time() - emotion.last_pet - common.PET_INTERVAL) * (
            emotion.pet_anger / common.JUMPSCARE_THRESHOLD
        ) - common.PET_COST

        if emotion.pet_anger < common.PET_COST:
            emotion.pet_anger = common.PET_COST
        emotion.last_pet = time.time()

        fname = "die.gif" if emotion.pet_anger > common.JUMPSCARE_THRESHOLD else "pet.gif"
        await embed_utils.replace(
            self.response_msg,
            "",
            "",
            0xFFFFAA,
            "https://raw.githubusercontent.com/PygameCommunityDiscord/"
            + f"PygameCommunityBot/main/assets/images/{fname}"
        )

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
            "Vibe Check, snek?",
            f"Previous petting anger: {emotion.pet_anger:.2f}/{common.JUMPSCARE_THRESHOLD:.2f}"
            + f"\nIt was last pet {utils.format_long_time(round(time.time() - emotion.last_pet))} ago",
        )

    async def cmd_sorry(self):
        """
        ->type Play With Me :snake:
        ->signature pg!sorry
        ->description You were hitting me <:pg_bonk:780423317718302781> and you're now trying to apologize?
        Let's see what I'll say :unamused:
        -----
        Implement pg!sorry, to ask forgiveness from the bot after bonccing it
        """
        if not emotion.boncc_count:
            await embed_utils.replace(
                self.response_msg,
                "Ask forgiveness from snek?",
                "Snek is happy. Awww, don't be sorry."
            )
            return

        num = random.randint(0, 3)
        if num:
            emotion.boncc_count -= num
            if emotion.boncc_count < 0:
                emotion.boncc_count = 0
            await embed_utils.replace(
                self.response_msg,
                "Ask forgiveness from snek?",
                "Your pythonic lord accepts your apology.\n"
                + f"Now go to code again.\nThe boncc count is {emotion.boncc_count}"
            )
        else:
            await embed_utils.replace(
                self.response_msg,
                "Ask forgiveness from snek?",
                "How did you dare to boncc a snake?\nBold of you to assume "
                + "I would apologize to you, two-feet-standing being!\nThe "
                + f"boncc count is {emotion.boncc_count}"
            )

    async def cmd_bonkcheck(self):
        """
        ->type Play With Me :snake:
        ->signature pg!bonkcheck
        ->description Check how many times you have done me harm.
        -----
        Implement pg!bonkcheck, to check how much the snek has been boncced
        """
        if emotion.boncc_count:
            await embed_utils.replace(
                self.response_msg,
                "The snek is hurt and angry:",
                f"The boncc count is {emotion.boncc_count}"
            )
        else:
            await embed_utils.replace(
                self.response_msg,
                "The snek is right",
                "Please, don't hit the snek"
            )

    async def cmd_refresh(self, msg: discord.Message):
        """
        ->type Other commands
        ->signature pg!refresh [message]
        ->description Refresh a message which support pages.
        -----
        Implement pg!refresh, to refresh a message which supports pages
        """

        if not msg.embeds or not msg.embeds[0].footer or not msg.embeds[0].footer.text:
            raise BotException(
                "Message does not support pages",
                "The message specified does not support pages. Make sure "
                "the id of the message is correct."
            )

        data = msg.embeds[0].footer.text.split("\n")

        page = re.search(r'\d+', data[0]).group()
        command = data[2].replace("Command: ", "").split()

        if not page or not command or not self.cmds_and_funcs.get(command[0]):
            raise BotException(
                "Message does not support pages",
                "The message specified does not support pages. Make sure "
                "the id of the message is correct."
            )

        await self.response_msg.delete()
        await self.invoke_msg.delete()

        if command[0] == "help":
            if len(command) == 1:
                command.append(None)

            await self.cmd_help(
                command[1], page=int(page) - 1, msg=msg
            )
        elif command[0] == "doc":
            await self.cmd_doc(
                command[1], page=int(page) - 1, msg=msg
            )

    async def cmd_poll(
        self,
        desc: String,
        *emojis: String,
        admin_embed: HiddenArg = {},
    ):
        """
        ->type Other commands
        ->signature pg!poll [description] [*args]
        ->description Start a poll.
        ->extended description
        `pg!poll description *args`
        The args must be strings with one emoji and one description of said emoji (see example command). \
        The emoji must be a default emoji or one from this server. To close the poll see pg!close_poll.
        ->example command pg!poll "Which apple is better?" "🍎" "Red apple" "🍏" "Green apple"
        """
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
            "color": 0x34a832,
            "footer": {
                "text": f"By {self.author.display_name}{newline}"
                        f"({self.author.id}){newline}Started"
            },
            "timestamp": self.response_msg.created_at.isoformat(),
            "description": desc.string
        }
        base_embed.update(admin_embed)

        if emojis:
            if len(emojis) <= 3 or len(emojis) % 2:
                raise BotException(
                    "Invalid arguments for emojis.",
                    "Please add at least 2 emojis with 2 descriptions."
                    " Each emoji should have their own description."
                    " Make sure each argument is a different string. For more"
                    " information see `pg!help poll`"
                )

            base_embed["fields"] = []
            for i, substr in enumerate(emojis):
                if not i % 2:
                    base_embed["fields"].append({
                        "name": substr.string.strip(),
                        "value": common.ZERO_SPACE,
                        "inline": True
                    })
                else:
                    base_embed["fields"][i // 2]["value"] = \
                        substr.string.strip()

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
                    " the correct emoji and that it is not from another server"
                )

    async def cmd_close_poll(
        self,
        msg: discord.Message,
        color: HiddenArg = None,
    ):
        """
        ->type Other commands
        ->signature pg!close_poll [message]
        ->description Close an ongoing poll.
        ->extended description
        The poll can only be closed by the person who started it or by mods.
        """
        newline = "\n"
        if not msg.embeds:
            raise BotException(
                "Invalid message",
                "The message specified is not an ongiong vote."
                " Please double-check the id."
            )
        embed = msg.embeds[0]
        # Take the second line remove the parenthesies
        if embed.footer.text and embed.footer.text.count("\n"):
            poll_owner = int(embed.footer.text.split("\n")[1]
                             .replace("(", "").replace(")", ""))
        else:
            raise BotException(
                "Invalid message",
                "The message specified is not an ongiong vote."
                " Please double-check the id."
            )

        if color is None and self.author.id != poll_owner:
            raise BotException(
                "You cant stop this vote",
                "The vote was not started by you."
                " Ask the person who started it to close it."
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
            if reaction.emoji not in reactions:
                continue

            if reaction.count - 1 > top[0][0]:
                top = [(reaction.count - 1, reaction.emoji)]
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

            fields.append([
                field.name,
                f"{field.value} ({r_count} votes)",
                True
            ])

            if field.name == top[0][1]:
                title += (
                    f"{newline}{field.value}({top[0][1]}) "
                    f"has won with {top[0][0]} votes!"
                )

        if len(top) >= 2:
            title = title.split("\n")[0]
            title += "\nIt's a draw!"

        await embed_utils.edit_2(
            msg,
            embed,
            color=0xa83232 if not color else utils.color_to_rgb_int(color),
            title=title,
            fields=fields,
            footer_text="Ended",
            timestamp=self.response_msg.created_at.isoformat()
        )
        await self.response_msg.delete()
