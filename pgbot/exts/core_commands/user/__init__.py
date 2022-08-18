"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present pygame-community

This file defines the command handler class for the user commands of the bot
"""

from __future__ import annotations
import asyncio

import copy
import datetime
import io
import os
import re
import time
from typing import Any, Optional, Union

import discord
from discord.ext import commands
import snakecore

from snakecore.commands.decorators import custom_parsing
from snakecore.commands.converters import CodeBlock, String

from pgbot import common
import pgbot

from pgbot.utils import get_primary_guild_perms
from ..utils import sandbox
from pgbot.exceptions import BotException
from pgbot.utils import message_delete_reaction_listener

from .fun_commands import FunCommandCog
from .help_commands import UserHelpCommandCog


class UserCommandCog(FunCommandCog, UserHelpCommandCog):
    """Base class to handle user commands."""

    @commands.group(invoke_without_command=True)
    async def reminders(self, ctx: commands.Context):
        """
        ->type Reminders
        ->signature pg!reminders
        ->description View all the reminders you have set
        -----
        Implement pg!reminders, for users to view their reminders
        """

        response_message = common.recent_response_messages[ctx.message.id]

        async with snakecore.storage.DiscordStorage("reminders") as storage_obj:
            storage_data = storage_obj.obj

        desc = "You have no reminders set"
        if ctx.author.id in storage_data:
            desc = ""
            cnt = 0
            for on, (reminder, chan_id, _) in storage_data[ctx.author.id].items():
                channel = None
                if common.guild is not None:
                    channel = common.guild.get_channel(chan_id)

                cin = channel.mention if channel is not None else "DM"
                desc += (
                    f"Reminder ID: `{cnt}`\n"
                    f"**On {snakecore.utils.create_markdown_timestamp(on)} in {cin}:**\n> {reminder}\n\n"
                )
                cnt += 1

        await snakecore.utils.embed_utils.replace_embed_at(
            response_message,
            title=f"Reminders for {ctx.author.display_name}:",
            description=desc,
            color=common.DEFAULT_EMBED_COLOR,
        )

    async def reminders_add_func(
        self,
        ctx: commands.Context,
        msg: String,
        on: datetime.datetime,
        _delta: Optional[datetime.timedelta] = None,
    ):

        response_message = common.recent_response_messages[ctx.message.id]

        if _delta is None:
            now = datetime.datetime.utcnow()
            _delta = on - now
        else:
            now = on
            on = now + _delta

        if on < now:
            raise BotException(
                "Failed to set reminder!",
                "Time cannot go backwards, negative time does not make sense..."
                "\n Or does it? \\*vsauce music plays in the background\\*",
            )

        elif _delta <= datetime.timedelta(seconds=10):
            raise BotException(
                "Failed to set reminder!",
                "Why do you want me to set a reminder for such a small duration?\n"
                "Pretty sure you can remember that one yourself :wink:",
            )

        # remove microsecond precision of the 'on' variable
        on -= datetime.timedelta(microseconds=on.microsecond)

        async with snakecore.storage.DiscordStorage("reminders") as storage_obj:
            storage_data = storage_obj.obj
            if ctx.author.id not in storage_data:
                storage_data[ctx.author.id] = {}

            # user is editing old reminder message, discard the old reminder
            for key, (_, chan_id, msg_id) in tuple(storage_data[ctx.author.id].items()):
                if chan_id == ctx.channel.id and msg_id == ctx.message.id:
                    storage_data[ctx.author.id].pop(key)

            limit = 25 if get_primary_guild_perms(ctx.author)[1] else 10
            if len(storage_data[ctx.author.id]) >= limit:
                raise BotException(
                    "Failed to set reminder!",
                    f"I cannot set more than {limit} reminders for you",
                )

            storage_data[ctx.author.id][on] = (
                msg.string.strip(),
                ctx.channel.id,
                ctx.message.id,
            )
            storage_obj.obj = storage_data

        await snakecore.utils.embed_utils.replace_embed_at(
            response_message,
            title="Reminder set!",
            description=(
                f"Gonna remind {ctx.author.name} in {snakecore.utils.format_time_by_units(_delta)}\n"
                f"And that is on {snakecore.utils.create_markdown_timestamp(on)}"
            ),
            color=common.DEFAULT_EMBED_COLOR,
        )

    @reminders.command(name="add")
    @custom_parsing(inside_class=True, inject_message_reference=True)
    async def reminders_add(
        self,
        ctx: commands.Context,
        msg: String,
        on: datetime.datetime,
    ):
        """
        ->type Reminders
        ->signature pg!reminders add <message> <datetime in iso format>
        ->description Set a reminder to yourself
        ->extended description
        Allows you to set a reminder to yourself
        The date-time must be an ISO time formatted string, in UTC time
        string
        ->example command pg!reminders add "do the thing" "2034-10-26 11:19:36"
        -----
        Implement pg!reminders_add, for users to set reminders for themselves
        """

        return await self.reminders_add_func(ctx, msg, on=on)

    @reminders.command(name="set")
    @custom_parsing(inside_class=True, inject_message_reference=True)
    async def reminders_set(
        self,
        ctx: commands.Context,
        msg: String,
        timestr: Union[String, str] = "",
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
        timestr = (
            timestr.string.strip() if isinstance(timestr, String) else timestr.strip()
        )

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
                month_results = re.search(r"\d+mo", timestr).group()
                parsed_month_time = int(month_results.replace("mo", ""))
                sec += (
                    ctx.message.created_at.replace(
                        month=ctx.message.created_at.month + parsed_month_time
                    )
                    - ctx.message.created_at
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

        await self.reminders_add_func(
            ctx, msg, datetime.datetime.utcnow(), _delta=delta
        )

    @reminders.command(name="remove")
    @custom_parsing(inside_class=True, inject_message_reference=True)
    async def reminders_remove(self, ctx: commands.Context, *reminder_ids: int):
        """
        ->type Reminders
        ->signature pg!reminders remove [*ids]
        ->description Remove reminders
        ->extended description
        Remove variable number of reminders, corresponding to each datetime argument
        The reminder id argument must be an integer
        If no arguments are passed, the command clears all reminders
        ->example command pg!reminders remove 1
        -----
        Implement pg!reminders_remove, for users to remove their reminders
        """

        response_message = common.recent_response_messages[ctx.message.id]

        async with snakecore.storage.DiscordStorage("reminders") as storage_obj:
            storage_data = storage_obj.obj
            storage_data_copy = copy.deepcopy(storage_data)
            cnt = 0
            if reminder_ids:
                for reminder_id in sorted(set(reminder_ids), reverse=True):
                    if ctx.author.id in storage_data:
                        for i, dt in enumerate(storage_data_copy[ctx.author.id]):
                            if i == reminder_id:
                                storage_data[ctx.author.id].pop(dt)
                                cnt += 1
                                break
                    if (
                        reminder_id >= len(storage_data_copy[ctx.author.id])
                        or reminder_id < 0
                    ):
                        raise BotException(
                            "Invalid Reminder ID!",
                            "Reminder ID was not an existing reminder ID",
                        )

                if ctx.author.id in storage_data and not storage_data[ctx.author.id]:
                    storage_data.pop(ctx.author.id)

            elif ctx.author.id in storage_data:
                cnt = len(storage_data.pop(ctx.author.id))

            storage_obj.obj = storage_data

        await snakecore.utils.embed_utils.replace_embed_at(
            response_message,
            title="Reminders removed!",
            description=f"Successfully removed {cnt} reminder(s)",
            color=common.DEFAULT_EMBED_COLOR,
        )

    @commands.command()
    @custom_parsing(inside_class=True, inject_message_reference=True)
    async def exec(self, ctx: commands.Context, code: CodeBlock):
        """
        ->type Play With Me :snake:
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

        response_message = common.recent_response_messages[ctx.message.id]

        async with ctx.channel.typing():
            tstamp = time.perf_counter_ns()

            returned = await sandbox.exec_sandbox(
                code.code, tstamp, 10 if get_primary_guild_perms(ctx.author)[1] else 5
            )
            dur = returned.duration  # the execution time of the script alone
            embed_dict = {
                "color": pgbot.ut,
                "description": "",
                "author": {
                    "name": f"Code executed in {snakecore.utils.format_time_by_units(dur)}",
                    "url": ctx.message.jump_url,
                },
            }

            file = None
            if returned.exc:
                embed_dict["description"] += "**Exception output:**\n"
                embed_dict["description"] += snakecore.utils.code_block(
                    returned.exc, 500
                )
                embed_dict["description"] += "\n"

            if returned.text:
                embed_dict["description"] += "**Text output:**\n"
                embed_dict["description"] += snakecore.utils.code_block(
                    returned.text, 1500
                )

            if returned.img:
                embed_dict["description"] += "\n**Image output:**"
                if os.path.getsize(f"temp{tstamp}.png") < 2**22:
                    embed_dict["image_url"] = f"attachment://temp{tstamp}.png"
                    file = discord.File(f"temp{tstamp}.png")
                else:
                    embed_dict[
                        "description"
                    ] += "\n```\nGIF could not be sent.\nThe GIF file size is above 4MiB```"

            elif returned._imgs:
                embed_dict["description"] += "\n**GIF output:**"
                if os.path.getsize(f"temp{tstamp}.gif") < 2**22:
                    embed_dict["image_url"] = f"attachment://temp{tstamp}.gif"
                    file = discord.File(f"temp{tstamp}.gif")
                else:
                    embed_dict[
                        "description"
                    ] += "\n```GIF could not be sent.\nThe GIF file size is above 4MiB```"

        try:
            await response_message.delete()
        except discord.errors.NotFound:
            # Message already deleted
            pass

        embed = snakecore.utils.embed_utils.create_embed_from_dict(embed_dict)
        await ctx.message.reply(file=file, embed=embed, mention_author=False)

        filesize_limit = (
            ctx.guild.filesize_limit
            if ctx.guild is not None
            else common.DEFAULT_FILESIZE_LIMIT
        )

        if len(returned.text) > 1500:
            with io.StringIO(
                returned.text
                if len(returned.text) - 40 < filesize_limit
                else returned.text[: filesize_limit - 40]
            ) as fobj:
                await ctx.channel.send(file=discord.File(fobj, filename="output.txt"))

        if file:
            file.close()

        for extension in ("gif", "png"):
            if os.path.isfile(f"temp{tstamp}.{extension}"):
                os.remove(f"temp{tstamp}.{extension}")

    @commands.command()
    @custom_parsing(inside_class=True, inject_message_reference=True)
    async def refresh(self, ctx: commands.Context, msg: discord.Message):
        """
        ->type Other commands
        ->signature pg!refresh <message>
        ->description Refresh a message which supports pages.
        -----
        Implement pg!refresh, to refresh a message which supports pagination
        """

        if (
            not msg.embeds
            or len(msg.embeds) < 3
            or not msg.embeds[0].footer
            or not msg.embeds[-1].footer
            or not isinstance(msg.embeds[0].footer.text, str)
            or not isinstance(msg.embeds[-1].footer.text, str)
        ):
            raise BotException(
                "Message does not support pagination",
                "The message specified does not support pagination. Make sure you "
                "have replied to the correct message",
            )

        footer_text = msg.embeds[0].footer.text

        cmd_data_match = re.search(r"cmd\:\s.+\|?", footer_text)

        if cmd_data_match is None:
            raise BotException(
                "Message does not support pagination",
                "The message specified does not support pagination. Make sure the id of the message is correct.",
            )

        cmd_data_str = footer_text[slice(*cmd_data_match.span())].removesuffix("\n")

        cmd_str = cmd_data_str.replace("cmd: ", "")

        arg_data_match = re.search(r"args\:\s.+", footer_text)
        arg_str = ""

        if arg_data_match is not None:
            arg_str = arg_data_match.group().replace("args: ", "")

        page_data = msg.embeds[-1].footer.text
        page_num_str_match = re.search(r"\d+", page_data)
        page_num_str = ""
        if page_num_str_match is not None:
            page_num_str = page_num_str_match.group()

        if page_num_str_match is None or not page_num_str.isdigit() or not cmd_str:
            raise BotException(
                "Message does not support pagination",
                "The message specified does not support pagination. Make sure the id of the message is correct.",
            )

        if "page=" not in arg_str:
            arg_str += f" page={page_num_str}"
        else:
            old_page_kwarg_match = re.search(r"page\=\d+", arg_str)

            if old_page_kwarg_match is not None:
                page_kwarg = old_page_kwarg_match.group()
                arg_str = arg_str.replace(page_kwarg, f"page={page_num_str}")

        response_message = common.recent_response_messages[ctx.message.id]

        try:
            await response_message.delete()
        except discord.errors.NotFound:
            pass

        # Handle the new command, the one that pg!refresh is trying to refresh

        response_message = common.recent_response_messages[ctx.message.id] = msg

        cmd = self.bot.get_command(cmd_str)
        # only supports commands using snakecore's
        # custom parser

        if cmd is not None:
            await cmd(ctx, raw_command_input=arg_str)
            common.hold_task(
                asyncio.create_task(
                    message_delete_reaction_listener(
                        response_message,
                        ctx.author,
                        emoji="🗑",
                        role_whitelist=common.GuildConstants.ADMIN_ROLES,
                        timeout=30,
                    )
                )
            )
            return

        raise commands.CommandNotFound(
            "Could not find the original command of the specified message to restart pagination."
        )

    @commands.group(invoke_without_command=True)
    @custom_parsing(inside_class=True, inject_message_reference=True)
    async def poll(
        self,
        ctx: commands.Context,
        description: String,
        *emojis: tuple[str, String],
        multi_votes: bool = True,
    ):
        """
        ->type Other commands
        ->signature pg!poll <description> [*emojis] [multi_votes=True]
        ->description Start a poll.
        ->extended description
        `pg!poll description *args`
        The args must be a series of two element tuples, first element being an emoji,
        and second being the choice the emoji represents (see example command).
        The emoji must be a default emoji or one from this server. To close the poll see 'pg!poll close'.
        A `multi_votes` arg can also be passed indicating if the user can cast multiple votes in a poll or not
        ->example command pg!poll "Which apple is better?" ( 🍎 "Red apple") ( 🍏 "Green apple")
        """
        return await self.poll_func(
            ctx,
            description,
            *emojis,
            multi_votes=multi_votes,
        )

    @poll.command(name="close")
    @custom_parsing(inside_class=True, inject_message_reference=True)
    async def poll_close(
        self,
        ctx: commands.Context,
        msg: discord.Message,
    ):
        """
        ->type Other commands
        ->signature pg!poll close <message>
        ->description Close an ongoing poll.
        ->extended description
        The poll can only be closed by the person who started it or by mods.
        """

        return await self.poll_close_func(ctx, msg)

    @commands.group(invoke_without_command=True)
    async def stream(self, ctx: commands.Context):
        """
        ->type Reminders
        ->signature pg!stream
        ->description Show the ping-stream-list
        Send an embed with all the users currently in the ping-stream-list
        """

        return await self.stream_func(ctx)

    @stream.command(name="add")
    @custom_parsing(inside_class=True, inject_message_reference=True)
    async def stream_add(
        self,
        ctx: commands.Context,
    ):
        """
        ->type Reminders
        ->signature pg!stream add
        ->description Add yourself to the stream-ping-list
        ->extended description
        Add yourself to the stream-ping-list. You can always delete yourself later
        with `pg!stream del`
        """

        return await self.stream_add_func(ctx)

    @stream.command(name="del", aliases=("delete",))
    async def stream_del(
        self,
        ctx: commands.Context,
    ):
        """
        ->type Reminders
        ->signature pg!stream del
        ->description Remove yourself from the stream-ping-list
        ->extended description
        Remove yourself from the stream-ping-list. You can always add you later
        with `pg!stream add`
        """

        return await self.stream_del_func(ctx)

    @stream.command(name="ping")
    @custom_parsing(inside_class=True, inject_message_reference=True)
    async def stream_ping(
        self, ctx: commands.Context, message: Optional[String] = None
    ):
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

        return await self.stream_ping_func(ctx, message=message)

    @commands.group(invoke_without_command=True)
    async def events(self, ctx: commands.Context):
        """
        ->type Events
        ->signature pg!events
        ->description Command for keeping up with the events of the server
        -----
        """
        return await self.events_func(ctx)

    @events.command(name="wc")
    @custom_parsing(inside_class=True, inject_message_reference=True)
    async def events_wc(self, ctx: commands.Context, round_no: Optional[int] = None):
        """
        ->type Events
        ->signature pg!events wc [round_no]
        ->description Show scoreboard of WC along with some info about the event
        ->extended description
        Argument `round_no` is an optional integer, that specifies which round
        of the event, the scoreboard should be displayed. If unspecified, shows
        the final scoreboard of all rounds combined.
        -----
        """
        return await self.events_wc_func(ctx, round_no=round_no)


async def setup(bot: commands.Bot):
    await bot.add_cog(UserCommandCog(bot))
