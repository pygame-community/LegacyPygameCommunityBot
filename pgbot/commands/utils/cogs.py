"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file defines command cog utilities. 
"""


from __future__ import annotations
import datetime
import os
import random
import time
from typing import Any, Optional, Union

import discord
from discord.ext import commands
import pygame
import snakecore
from snakecore.command_handler.converters import String

from pgbot import common
import pgbot
from . import clock
from .utils import get_primary_guild_perms
from pgbot.exceptions import BotException


class CommandUtilsCog(commands.Cog):
    """
    A mixin cog of utility methods to use by other command cogs.
    """

    def __init__(self, bot: commands.Bot):
        """
        Initialise class
        """
        self.bot: commands.Bot = bot

    async def reminders_add_func(
        self,
        ctx: commands.Context,
        msg: str,
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

        async with snakecore.db.DiscordDB("reminders") as db_obj:
            db_data = db_obj.obj
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
            db_obj.obj = db_data

        await snakecore.utils.embed_utils.replace_embed_at(
            response_message,
            title="Reminder set!",
            description=(
                f"Gonna remind {ctx.author.name} in {snakecore.utils.format_time_by_units(_delta)}\n"
                f"And that is on {snakecore.utils.create_markdown_timestamp(on)}"
            ),
            color=common.DEFAULT_EMBED_COLOR,
        )

    async def poll_func(
        self,
        ctx: commands.Context,
        desc: String,
        *emojis: tuple[str, String],
        multi_votes: bool = False,
        _destination: Optional[Union[discord.TextChannel, discord.Thread]] = None,
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
                emoji = self.bot.get_emoji(emoji_id)
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

    async def poll_close_func(
        self,
        ctx: commands.Context,
        msg: discord.Message,
        _color: Optional[discord.Color] = None,
    ):
        """
        ->type Other commands
        ->signature pg!poll close <message>
        ->description Close an ongoing poll.
        ->extended description
        The poll can only be closed by the person who started it or by mods.
        """

        # needed for typecheckers to know that ctx.author is a member
        if isinstance(ctx.author, discord.User):
            return

        response_message = common.recent_response_messages[ctx.message.id]

        if not snakecore.utils.have_permissions_in_channels(
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

            is_custom_emoji = snakecore.utils.is_markdown_custom_emoji(field.name)

            try:
                r_count = (
                    reactions[
                        (
                            snakecore.utils.extract_markdown_custom_emoji_id(field.name)
                            if is_custom_emoji
                            else field.name
                        )
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
                if is_custom_emoji
                else field.name
            ) == top[0][1]:
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

        async with snakecore.db.DiscordDB("stream", list) as db_obj:
            data = db_obj.obj

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

    async def stream_add_func(
        self,
        ctx: commands.Context,
        _members: Optional[tuple[discord.Member, ...]] = None,
    ):
        async with snakecore.db.DiscordDB("stream", list) as ping_db:
            data: list = ping_db.obj

            if _members:
                for mem in _members:
                    if mem.id not in data:
                        data.append(mem.id)
            elif ctx.author.id not in data:
                data.append(ctx.author.id)

            ping_db.obj = data

        await self.stream_func(ctx)

    async def stream_del_func(
        self,
        ctx: commands.Context,
        _members: Optional[tuple[discord.Member, ...]] = None,
    ):
        async with snakecore.db.DiscordDB("stream", list) as ping_db:
            data: list = ping_db.obj

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

            ping_db.obj = data

        await self.stream_func(ctx)

    async def stream_ping_func(
        self, ctx: commands.Context, message: Optional[String] = None
    ):

        response_message = common.recent_response_messages[ctx.message.id]

        async with snakecore.db.DiscordDB("stream", list) as ping_db:
            data: list = ping_db.obj

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

    async def events_wc_func(
        self, ctx: commands.Context, round_no: Optional[int] = None
    ):
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

        async with snakecore.db.DiscordDB("wc") as db_obj:
            wc_dict: dict[str, Any] = db_obj.obj

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

    async def clock_func(
        self,
        ctx: commands.Context,
        action: str = "",
        timezone: Optional[float] = None,
        color: Optional[discord.Color] = None,
        _member: Optional[discord.Member] = None,
    ):

        response_message = common.recent_response_messages[ctx.message.id]

        async with snakecore.db.DiscordDB("clock") as db_obj:
            timezones = db_obj.obj
            if action:
                if _member is None:
                    member = ctx.author
                    if member.id not in timezones:
                        raise BotException(
                            "Cannot update clock!",
                            "You cannot run clock update commands because you are "
                            + "not on the clock",
                        )
                else:
                    member = _member

                if action == "update":
                    if timezone is not None and abs(timezone) > 12:
                        raise BotException(
                            "Failed to update clock!", "Timezone offset out of range"
                        )

                    if member.id in timezones:
                        if timezone is not None:
                            timezones[member.id][0] = timezone
                        if color is not None:
                            timezones[member.id][1] = pgbot.utils.color_to_rgb_int(
                                color
                            )
                    else:
                        if timezone is None:
                            raise BotException(
                                "Failed to update clock!",
                                "Timezone is required when adding new people",
                            )

                        if color is None:
                            color = discord.Color(random.randint(0, 0xFFFFFF))

                        timezones[member.id] = [
                            timezone,
                            color.value,
                        ]

                    # sort timezones dict after an update operation
                    timezones = dict(sorted(timezones.items(), key=lambda x: x[1][0]))

                elif action == "remove":
                    try:
                        timezones.pop(member.id)
                    except KeyError:
                        raise BotException(
                            "Failed to update clock!",
                            "Cannot remove non-existing person from clock",
                        )

                else:
                    raise BotException(
                        "Failed to update clock!", f"Invalid action specifier {action}"
                    )

                db_obj.obj = timezones

        t = time.time()

        pygame.image.save(
            await clock.user_clock(t, timezones, ctx.guild), f"temp{t}.png"
        )
        await response_message.edit(
            embeds=[], attachments=[discord.File(f"temp{t}.png")]
        )
        os.remove(f"temp{t}.png")