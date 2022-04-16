"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file defines the command handler class for the user commands of the bot
"""

from __future__ import annotations

import copy
import datetime
import io
import os
import re
import time
from typing import Any, List, Optional, Tuple, Union

import discord
from discord.ext import commands
import pygame
import snakecore

from snakecore.command_handler.decorators import custom_parsing, kwarg_command
from snakecore.command_handler.parsing.converters import CodeBlock, String

from pgbot import common, db
import pgbot

from pgbot.commands.utils import commands, get_primary_guild_perms, sandbox
from pgbot.exceptions import BotException

from .fun_commands import FunCommand
from .help_commands import HelpCommandCog


class UserCommandCog(FunCommand, HelpCommandCog):
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

        async with db.DiscordDB("reminders") as db_obj:
            db_data = db_obj.get({})

        desc = "You have no reminders set"
        if ctx.author.id in db_data:
            desc = ""
            cnt = 0
            for on, (reminder, chan_id, _) in db_data[ctx.author.id].items():
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

    @reminders.command(name="add")
    async def reminders_add(
        self,
        ctx: commands.Context,
        msg: str,
        on: datetime.datetime,
        **kwargs,
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

        response_message = common.recent_response_messages[ctx.message.id]
        
        _delta: Optional[datetime.timedelta] = kwargs.get("_delta")

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

        async with db.DiscordDB("reminders") as db_obj:
            db_data = db_obj.get({})
            if ctx.author.id not in db_data:
                db_data[ctx.author.id] = {}

            # user is editing old reminder message, discard the old reminder
            for key, (_, chan_id, msg_id) in tuple(db_data[ctx.author.id].items()):
                if chan_id == ctx.channel.id and msg_id == ctx.message.id:
                    db_data[ctx.author.id].pop(key)

            limit = 25 if get_primary_guild_perms(ctx.author)[1] else 10
            if len(db_data[ctx.author.id]) >= limit:
                raise BotException(
                    "Failed to set reminder!",
                    f"I cannot set more than {limit} reminders for you",
                )

            db_data[ctx.author.id][on] = (
                msg.string.strip(),
                ctx.channel.id,
                ctx.message.id,
            )
            db_obj.write(db_data)

        await snakecore.utils.embed_utils.replace_embed_at(
            response_message,
            title="Reminder set!",
            description=(
                f"Gonna remind {ctx.author.name} in {snakecore.utils.format_time_by_units(_delta)}\n"
                f"And that is on {snakecore.utils.create_markdown_timestamp(on)}"
            ),
            color=common.DEFAULT_EMBED_COLOR,
        )

    @reminders.command(name="set")
    @kwarg_command
    async def reminders_set(
        self,
        ctx: commands.Context,
        msg: str,
        *,
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

        await self.reminders_add(ctx, msg, datetime.datetime.utcnow(), _delta=delta)

    @reminders.command(name="remove")
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

        async with db.DiscordDB("reminders") as db_obj:
            db_data = db_obj.get({})
            db_data_copy = copy.deepcopy(db_data)
            cnt = 0
            if reminder_ids:
                for reminder_id in sorted(set(reminder_ids), reverse=True):
                    if ctx.author.id in db_data:
                        for i, dt in enumerate(db_data_copy[ctx.author.id]):
                            if i == reminder_id:
                                db_data[ctx.author.id].pop(dt)
                                cnt += 1
                                break
                    if (
                        reminder_id >= len(db_data_copy[ctx.author.id])
                        or reminder_id < 0
                    ):
                        raise BotException(
                            "Invalid Reminder ID!",
                            "Reminder ID was not an existing reminder ID",
                        )

                if ctx.author.id in db_data and not db_data[ctx.author.id]:
                    db_data.pop(ctx.author.id)

            elif ctx.author.id in db_data:
                cnt = len(db_data.pop(ctx.author.id))

            db_obj.write(db_data)

        await snakecore.utils.embed_utils.replace_embed_at(
            response_message,
            title="Reminders removed!",
            description=f"Successfully removed {cnt} reminder(s)",
            color=common.DEFAULT_EMBED_COLOR,
        )

    @commands.command()
    async def exec(self, ctx: commands.Context, *, code: CodeBlock):
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
                    embed_dict["description"] += (
                        "\n```\nGIF could not be sent.\n"
                        "The GIF file size is above 4MiB```"
                    )

            elif returned._imgs:
                embed_dict["description"] += "\n**GIF output:**"
                if os.path.getsize(f"temp{tstamp}.gif") < 2**22:
                    embed_dict["image_url"] = f"attachment://temp{tstamp}.gif"
                    file = discord.File(f"temp{tstamp}.gif")
                else:
                    embed_dict["description"] += (
                        "\n```GIF could not be sent.\n"
                        "The GIF file size is above 4MiB```"
                    )

        try:
            await response_message.delete()
        except discord.errors.NotFound:
            # Message already deleted
            pass

        embed = snakecore.utils.embed_utils.create_embed_from_dict(embed_dict)
        await ctx.message.reply(file=file, embed=embed, mention_author=False)

        filesize_limit = ctx.guild.filesize_limit if ctx.guild is not None else common.BASIC_MAX_FILE_SIZE

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

    # @commands.command()
    # async def refresh(self, ctx: commands.Context, msg: discord.Message):
    #     """
    #     ->type Other commands
    #     ->signature pg!refresh <message>
    #     ->description Refresh a message which supports pages.
    #     -----
    #     Implement pg!refresh, to refresh a message which supports pages
    #     """

    #     response_message = common.recent_response_messages[ctx.message.id]

    #     if (
    #         not msg.embeds
    #         or len(msg.embeds) < 3
    #         or not msg.embeds[0].footer
    #         or not msg.embeds[-1].footer
    #         or not isinstance(msg.embeds[0].footer.text, str)
    #         or not isinstance(msg.embeds[-1].footer.text, str)
    #     ):
    #         raise BotException(
    #             "Message does not support pages",
    #             "The message specified does not support pages. Make sure you "
    #             "have replied to the correct message",
    #         )

    #     footer_text = msg.embeds[0].footer.text

    #     cmd_data_match = re.match(r"Command\:\s.+\n", footer_text)

    #     if cmd_data_match is None:
    #         raise BotException(
    #             "Message does not support pages",
    #             "The message specified does not support pages. Make sure "
    #             "the id of the message is correct.",
    #         )

    #     cmd_data_str = footer_text[slice(*cmd_data_match.span())].removesuffix("\n")
        
    #     cmd_str = cmd_data_str.replace("Command: ", "")


    #     arg_data_match = re.match(r"Arguments\:\s.+", footer_text)
    #     arg_data_str = None
    #     arg_str = ()

    #     if cmd_data_match is not None:
    #         raise BotException(
    #             "Message does not support pages",
    #             "The message specified does not support pages. Make sure "
    #             "the id of the message is correct.",
    #         )

        

    #     page_data = msg.embeds[-1].footer.text
    #     page = re.search(r"\d+", page_data).group()

    #     if not page.isdigit() or not cmd_str:
    #         raise BotException(
    #             "Message does not support pages",
    #             "The message specified does not support pages. Make sure "
    #             "the id of the message is correct.",
    #         )

    #     try:
    #         await response_message.delete()
    #     except discord.errors.NotFound:
    #         pass

    #     # Handle the new command, the one that pg!refresh is trying to refresh
        
    #     response_message = msg

    #     cmd = self.bot.get_command(cmd_str)

    #     if cmd is not None and cmd.can_run(ctx):
    #         await cmd(ctx, _page_number=int(page))


    async def poll_func(
        self,
        ctx: commands.Context,
        desc: str,
        *emojis: tuple[str, String],
        multi_votes: bool = False,
        _destination: Optional[Union[discord.abc.GuildChannel, discord.Thread]] = None,
        _admin_embed_dict: Optional[dict] = None,
    ):


        response_message = common.recent_response_messages[ctx.message.id]
        
        _admin_embed_dict = _admin_embed_dict or {}

        destination = ctx.channel if _destination is None else _destination

        base_embed_dict = {
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
                "name": ctx.author.name,
            },
            "color": 0x34A832,
            "footer": {
                "text": f"By {ctx.author.display_name}\n({ctx.author.id})\n"
                f"{'' if multi_votes else common.UNIQUE_POLL_MSG}Started"
            },
            "timestamp": response_message.created_at.isoformat(),
            "description": desc.string,
        }
        base_embed_dict.update(_admin_embed_dict)

        # Make into dict because we want to get rid of emoji repetitions
        emojis_dict = {k.strip(): v.string.strip() for k, v in emojis}
        if emojis_dict:
            if len(emojis_dict) == 1:
                raise BotException(
                    "Invalid arguments for emojis",
                    "Please add at least 2 options in the poll\n"
                    "For more information, see `pg!help poll`",
                )

            base_embed_dict["fields"] = [
                {"name": k, "value": v, "inline": True} for k, v in emojis_dict.items()
            ]

        final_embed = discord.Embed.from_dict(base_embed_dict)
        poll_msg = await destination.send(embed=final_embed)
        try:
            await response_message.delete()
        except discord.errors.NotFound:
            pass

        for field in base_embed_dict["fields"]:
            try:
                emoji_id = snakecore.utils.extract_markdown_custom_emoji_id(
                    field["name"].strip()
                )
                emoji = common.bot.get_emoji(emoji_id)
                if emoji is None:
                    raise ValueError()
            except ValueError:
                emoji = field["name"]

            try:
                await poll_msg.add_reaction(emoji)
            except (discord.errors.HTTPException, discord.errors.NotFound):
                # Either a custom emoji was used (which could not be added by
                # our beloved snek) or some other error happened. Clear the
                # reactions and prompt the user to make sure it is the currect
                # emoji.
                await poll_msg.clear_reactions()
                raise BotException(
                    "Invalid emoji",
                    "The emoji could not be added as a reaction. Make sure it is"
                    " the correct emoji and that it is not from another server",
                )

    @commands.group(invoke_without_command=True)
    @commands.guild_only()
    @custom_parsing(inside_class=True)
    async def poll(
        self,
        ctx: commands.Context,
        desc: String,
        *emojis: tuple[str, String],
        multi_votes: bool = False,
        **kwargs,
    ):
        """
        ->type Other commands
        ->signature pg!poll <description> [*emojis] [multi_votes=True]
        ->description Start a poll.
        ->extended description
        `pg!poll description *args`
        The args must series of two element tuples, first element being emoji,
        and second being the description (see example command).
        The emoji must be a default emoji or one from this server. To close the poll see 'pg!poll close'.
        A `multi_votes` arg can also be passed indicating if the user can cast multiple votes in a poll or not
        ->example command pg!poll "Which apple is better?" ( 🍎 "Red apple") ( 🍏 "Green apple")
        """
        return await self.poll_func(ctx, desc, *emojis, multi_votes=multi_votes, _destination=kwargs.get("_destination"), _admin_embed_dict=kwargs.get("_admin_embed_dict", {}))

    poll.command(name="close")
    @commands.guild_only()
    async def poll_close(
        self,
        ctx: commands.Context,
        msg: discord.Message,
        **kwargs,
    ):
        """
        ->type Other commands
        ->signature pg!poll close <message>
        ->description Close an ongoing poll.
        ->extended description
        The poll can only be closed by the person who started it or by mods.
        """

        response_message = common.recent_response_messages[ctx.message.id]

        _color: Optional[discord.Color] = kwargs.get("_color")
        # needed for typecheckers to know that ctx.author is a member
        if isinstance(ctx.author, discord.User):
            return

        if not pgbot.snakecore.utils.have_permissions_in_channels(
            ctx.author,
            msg.channel,
            "view_channel",
        ):
            raise BotException(
                "Not enough permissions",
                "You do not have enough permissions to run this command with the specified arguments.",
            )

        if not msg.embeds:
            raise BotException(
                "Invalid message",
                "The message specified is not an ongoing vote."
                " Please double-check the id.",
            )

        embed = msg.embeds[0]
        if not isinstance(embed.footer.text, str):
            raise BotException(
                "Invalid message",
                "The message specified is not an ongoing vote."
                " Please double-check the id.",
            )

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

        if _color is None and ctx.author.id != poll_owner:
            raise BotException(
                "You can't stop this vote",
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

        top: list[tuple[int, Any]] = [(0, None)]
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
            if not isinstance(field.name, str):
                continue

            try:
                r_count = (
                    reactions[
                        snakecore.utils.extract_markdown_custom_emoji_id(field.name)
                    ]
                    - 1
                )
            except KeyError:
                # The reactions and the embed fields dont match up.
                # Someone is abusing their mod powers if this happens probably.
                continue

            fields.append(
                dict(
                    name=field.name,
                    value=f"{field.value} ({r_count} votes)",
                    inline=True,
                )
            )

            if (
                snakecore.utils.extract_markdown_custom_emoji_id(field.name)
                == top[0][1]
            ):
                title += (
                    f"\n{field.value}({field.name}) has won with {top[0][0]} votes!"
                )

        if len(top) >= 2:
            title = title.split("\n")[0]
            title += "\nIt's a draw!"

        await snakecore.utils.embed_utils.edit_embed_at(
            msg,
            color=0xA83232 if not _color else _color.value,
            title=title,
            fields=fields,
            footer_text="Ended",
            timestamp=response_message.created_at,
        )
        try:
            await response_message.delete()
        except discord.errors.NotFound:
            pass

    
    async def stream_func(self, ctx: commands.Context):

        response_message = common.recent_response_messages[ctx.message.id]

        async with db.DiscordDB("stream") as db_obj:
            data = db_obj.get([])

        if not data:
            await snakecore.utils.embed_utils.replace_embed_at(
                response_message,
                title="Memento ping list",
                description="Ping list is empty!",
                color=common.DEFAULT_EMBED_COLOR,
            )
            return

        await snakecore.utils.embed_utils.replace_embed_at(
            response_message,
            title="Memento ping list",
            description=(
                "Here is a list of people who want to be pinged when stream starts"
                "\nUse 'pg!stream ping' to ping them if you start streaming\n"
                + "\n".join((f"<@{user}>" for user in data))
            ),
            color=common.DEFAULT_EMBED_COLOR,
        )


    @commands.group(invoke_without_command=True)
    async def stream(self, ctx: commands.Context):
        """
        ->type Reminders
        ->signature pg!stream
        ->description Show the ping-stream-list
        Send an embed with all the users currently in the ping-stream-list
        """
        
        return await self.stream_func(ctx)

    
    async def stream_add_func(self, ctx: commands.Context, *, _members: Optional[tuple[discord.Member, ...]] = None):
        async with db.DiscordDB("stream") as ping_db:
            data: list = ping_db.get([])

            if _members:
                for mem in _members:
                    if mem.id not in data:
                        data.append(mem.id)
            elif ctx.author.id not in data:
                data.append(ctx.author.id)

            ping_db.write(data)

        await self.stream_func(ctx)
        

    @stream.command(name="add")
    async def stream_add(
        self, ctx: commands.Context, **kwargs,
    ):
        """
        ->type Reminders
        ->signature pg!stream add
        ->description Add yourself to the stream-ping-list
        ->extended description
        Add yourself to the stream-ping-list. You can always delete yourself later
        with `pg!stream del`
        """
        
        return await self.stream_add_func(ctx, _members=kwargs.get("_members"))

    
    async def stream_del_func(self, ctx: commands.Context, *, _members: Optional[tuple[discord.Member, ...]] = None):
        async with db.DiscordDB("stream") as ping_db:
            data: list = ping_db.get([])

            try:
                if _members:
                    for mem in _members:
                        data.remove(mem.id)
                else:
                    data.remove(ctx.author.id)
            except ValueError:
                raise BotException(
                    "Could not remove member",
                    "Member was not previously added to the ping list",
                )

            ping_db.write(data)

        await self.stream_func(ctx)

    @stream.command(name="del", aliases=("delete",))
    async def stream_del(
        self, ctx: commands.Context, **kwargs,
    ):
        """
        ->type Reminders
        ->signature pg!stream del
        ->description Remove yourself from the stream-ping-list
        ->extended description
        Remove yourself from the stream-ping-list. You can always add you later
        with `pg!stream add`
        """
        
        return await self.stream_del_func(ctx, _members=kwargs.get("_members"))

    @stream.command(name="ping")
    async def stream_ping(self, ctx: commands.Context, message: Optional[String] = None):
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

        response_message = common.recent_response_messages[ctx.message.id]

        async with db.DiscordDB("stream") as ping_db:
            data: list = ping_db.get([])

        msg = message.string if message else "Enjoy the stream!"
        ping = (
            "Pinging everyone on ping list:\n"
            + "\n".join((f"<@!{user}>" for user in data))
            if data
            else "No one is registered on the ping momento :/"
        )

        try:
            await response_message.delete()
        except discord.errors.NotFound:
            pass
        await ctx.channel.send(f"<@!{ctx.author.id}> is gonna stream!\n{msg}\n{ping}")

    async def events_func(self, ctx: commands.Context):
        """
        ->type Events
        ->signature pg!events
        ->description Command for keeping up with the events of the server
        -----
        """

        response_message = common.recent_response_messages[ctx.message.id]

        await snakecore.utils.embed_utils.replace_embed_at(
            response_message,
            title="Pygame Community Discord Server Events!",
            description=(
                "Check out Weekly Challenges!\n"
                "Run `pg!events wc` to check out the scoreboard for this event!"
            ),
            color=common.DEFAULT_EMBED_COLOR,
        )

    @commands.group(invoke_without_command=True)
    async def events(self, ctx: commands.Context):
        """
        ->type Events
        ->signature pg!events
        ->description Command for keeping up with the events of the server
        -----
        """
        return await self.events_func(ctx)

    
    async def events_wc_func(self, ctx: commands.Context, *, round_no: Optional[int] = None):
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

        response_message = common.recent_response_messages[ctx.message.id]

        async with db.DiscordDB("wc") as db_obj:
            wc_dict: dict[str, Any] = db_obj.get({})

        if not wc_dict.get("rounds"):
            raise BotException(
                "Could not check scoreboard!",
                "The Weekly Challenges Event has not started yet!",
            )

        fields = []
        if round_no is None:
            score_dict: dict[int, int] = {}
            for round_dict in wc_dict["rounds"]:
                for mem, scores in round_dict["scores"].items():
                    try:
                        score_dict[mem] += sum(scores)
                    except KeyError:
                        score_dict[mem] = sum(scores)

        else:
            try:
                rounds_dict = wc_dict["rounds"][round_no - 1]
            except IndexError:
                raise BotException(
                    "Could not check scoreboard!",
                    f"The Weekly Challenges event does not have round {round_no} (yet)!",
                ) from None

            score_dict = {
                mem: sum(scores) for mem, scores in rounds_dict["scores"].items()
            }
            fields.append((rounds_dict["name"], rounds_dict["description"], False))

        if score_dict:
            fields.extend(pgbot.utils.split_wc_scores(score_dict))

        else:
            fields.append(
                ("There are no scores yet!", "Check back after sometime!", False)
            )

        await snakecore.utils.embed_utils.replace_embed_at(
            response_message,
            title=f"Event: Weekly Challenges (WC)",
            description=wc_dict.get(
                "description", "Upcoming Event! Prepare your peepers!"
            ),
            url=wc_dict.get("url"),
            fields=fields,
            color=0xFF8C00,
        )


    @events.command(name="wc")
    @kwarg_command
    async def events_wc(self, ctx: commands.Context, *, round_no: Optional[int] = None):
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
