"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present pygame-community

This file exports the main AdminCommandCog class
"""

from __future__ import annotations

import asyncio
import datetime
import io
import os
import time
from typing import Optional, Union

import black
import discord
from discord.ext import commands
import psutil
import snakecore

from pgbot import common
import pgbot
from .emsudo import EmsudoCommandCog
from .sudo import SudoCommandCog
from ..utils.checks import admin_only, admin_only_and_custom_parsing
from ..base import CommandMixinCog
from ..utils.converters import (
    CodeBlock,
    String,
)
from pgbot.exceptions import BotException

process = psutil.Process(os.getpid())


class AdminCommandCog(CommandMixinCog, SudoCommandCog, EmsudoCommandCog):
    """
    Base class for all admin commands
    """

    @commands.command(hidden=True)
    @admin_only_and_custom_parsing(inside_class=True, inject_message_reference=True)
    async def test_parser(self, ctx: commands.Context, *args, **kwargs):
        """
        ->skip
        """

        response_message = common.recent_response_messages[ctx.message.id]

        out = ""
        if args:
            out += "__**Args:**__\n"

        for cnt, arg in enumerate(args):
            if isinstance(arg, CodeBlock):
                out += f"{cnt} - Codeblock\n" + snakecore.utils.code_block(
                    arg.code, code_type=arg.lang
                )
            elif isinstance(arg, String):
                out += (
                    f"{cnt} - String\n> " + "\n> ".join(arg.string.splitlines()) + "\n"
                )
            elif isinstance(arg, tuple):
                out += f"{cnt} - tuple\n {snakecore.utils.code_block(repr(arg), code_type='py')}\n"
            else:
                out += f"{cnt} - arg\n> {arg}\n"

        out += "\n"
        if kwargs:
            out += "__**Kwargs:**__\n\n"

        for name, arg in kwargs.items():
            if isinstance(arg, CodeBlock):
                out += f"{name} - Codeblock\n" + snakecore.utils.code_block(
                    arg.code, code_type=arg.lang
                )
            elif isinstance(arg, String):
                out += (
                    f"{name} - String\n> " + "\n>".join(arg.string.splitlines()) + "\n"
                )
            elif isinstance(arg, tuple):
                out += f"{name} - tuple\n {snakecore.utils.code_block(repr(arg), code_type='py')}\n"
            else:
                out += f"{name} - arg\n> {arg}\n"

        out += "\n"
        await snakecore.utils.embeds.replace_embed_at(
            response_message,
            title="Here are the args and kwargs you passed",
            description=out,
            color=common.DEFAULT_EMBED_COLOR,
        )

    @commands.group(invoke_without_command=True)
    @admin_only()
    async def storage(self, ctx: commands.Context):
        """
        ->type Admin commands
        ->signature pg!storage
        ->description List contents of storages (table names)
        -----
        Implement pg!storage, list contents of storages
        """

        response_message = common.recent_response_messages[ctx.message.id]

        await snakecore.utils.embeds.replace_embed_at(
            response_message,
            title="Tables:",
            description="\n".join(
                snakecore.storage.DiscordStorage._storage_records.keys()
            ),
            color=common.DEFAULT_EMBED_COLOR,
        )

    @storage.command(name="read")
    @admin_only_and_custom_parsing(inside_class=True, inject_message_reference=True)
    async def storage_read(self, ctx: commands.Context, name: str):
        """
        ->type Admin commands
        ->signature pg!storage read <name>
        ->description Visualize storage
        -----
        Implement pg!storage_read, to visualise storage messages
        """

        response_message = common.recent_response_messages[ctx.message.id]

        async with snakecore.storage.DiscordStorage(name) as storage_obj:
            str_obj = black.format_str(
                repr(storage_obj.obj or None),
                mode=black.FileMode(),
            )

        with io.StringIO(str_obj) as fobj:
            await ctx.channel.send(
                f"Here are the contents of the table `{name}`:",
                file=discord.File(fobj, filename=f"{name}_storage.py"),
            )

        try:
            await response_message.delete()
        except discord.NotFound:
            pass

    @storage.command(name="write")
    @admin_only_and_custom_parsing(inside_class=True, inject_message_reference=True)
    async def storage_write(
        self, ctx: commands.Context, name: str, data: Union[discord.Message, CodeBlock]
    ):
        """
        ->type Admin commands
        ->signature pg!storage write <name> <data>
        ->description Overwrite storage. Do not use unless you know what you are doing
        -----
        Implement pg!storage_write, to overwrite storage messages
        """
        # make typecheckers happy
        if not isinstance(ctx.author, discord.Member):
            return

        response_message = common.recent_response_messages[ctx.message.id]

        evalable = False
        for role in ctx.author.roles:
            if role.id in common.GuildConstants.EVAL_ROLES:
                evalable = True

        if common.TEST_MODE and ctx.author.id in common.TEST_USER_IDS:
            evalable = True

        if not evalable:
            raise BotException(
                "Insufficient Permissions!",
                "You do not have enough permissions to run this command.",
            )

        if isinstance(data, CodeBlock):
            obj_str = data.code
        elif data.attachments:
            obj_str = (await data.attachments[0].read()).decode()
        else:
            raise BotException(
                "Failed to overwrite storage", "File attachment was not found"
            )

        async with snakecore.storage.DiscordStorage(name) as storage_obj:
            storage_obj.obj = eval(obj_str)  # pylint: disable = eval-used

        await snakecore.utils.embeds.replace_embed_at(
            response_message,
            title="Storage overwritten!",
            description="Storage contents have been overwritten successfully",
            color=common.DEFAULT_EMBED_COLOR,
        )

    @storage.command(name="del")
    @admin_only_and_custom_parsing(inside_class=True, inject_message_reference=True)
    async def storage_del(self, ctx: commands.Context, name: str):
        """
        ->type Admin commands
        ->signature pg!storage del <name>
        ->description Delete storage. Do not use unless you know what you are doing
        -----
        Implement pg!storage_del, to delete storage messages
        """

        response_message = common.recent_response_messages[ctx.message.id]

        async with snakecore.storage.DiscordStorage(name) as storage_obj:
            try:
                del storage_obj.obj
            except AttributeError:
                raise BotException(
                    "Could not delete storage", "Deletion has already occured"
                )

        await snakecore.utils.embeds.replace_embed_at(
            response_message,
            title="Storage has been deleted!",
            description="Storage contents have been deleted successfully",
            color=common.DEFAULT_EMBED_COLOR,
        )

    @commands.command()
    @admin_only()
    async def whitelist_cmd(self, ctx: commands.Context, *cmds: str):
        """
        ->type Admin commands
        ->signature pg!whitelist_cmd [*cmds]
        ->description Whitelist commands
        -----
        Implement pg!whitelist_cmd, to whitelist commands
        """

        response_message = common.recent_response_messages[ctx.message.id]

        cmds = tuple(
            cmd_str.string if isinstance(cmd_str, String) else cmd_str
            for cmd_str in cmds
        )

        for cmd_qualname in cmds:
            cmd = self.bot.get_command(cmd_qualname)
            if cmd is None:
                raise BotException(
                    "Unrecognized command!",
                    f"could not find a command named '{cmd_qualname}'",
                )

        async with snakecore.storage.DiscordStorage("blacklist", list) as storage_obj:
            commands = storage_obj.obj
            cnt = 0
            for cmd_qualname in cmds:
                if cmd_qualname in commands:
                    cmd = self.bot.get_command(cmd_qualname)
                    if cmd is not None:
                        cmd.enabled = True

                    cnt += 1
                    commands.remove(cmd_qualname)

            storage_obj.obj = commands

        await snakecore.utils.embeds.replace_embed_at(
            response_message,
            title="Whitelisted!",
            description=f"Successfully whitelisted {cnt} command(s)",
            color=common.DEFAULT_EMBED_COLOR,
        )

    @commands.command()
    @admin_only()
    async def blacklist_cmd(self, ctx: commands.Context, *cmds: str):
        """
        ->type Admin commands
        ->signature pg!blacklist_cmd [*cmds]
        ->description Blacklist commands
        -----
        Implement pg!blacklist_cmd, to blacklist commands
        """

        response_message = common.recent_response_messages[ctx.message.id]

        cmds = tuple(
            cmd_str.string if isinstance(cmd_str, String) else cmd_str
            for cmd_str in cmds
        )

        for cmd_qualname in cmds:
            cmd = self.bot.get_command(cmd_qualname)
            if cmd is None:
                raise BotException(
                    "Unrecognized command!",
                    f"could not find a command named '{cmd_qualname}'",
                )

        async with snakecore.storage.DiscordStorage("blacklist", list) as storage_obj:
            commands = storage_obj.obj
            cnt = 0
            for cmd_qualname in cmds:
                if cmd_qualname not in commands and cmd_qualname != "whitelist_cmd":
                    cmd = self.bot.get_command(cmd_qualname)
                    if cmd is not None:
                        cmd.enabled = False

                    cnt += 1
                    commands.append(cmd_qualname)

            storage_obj.obj = commands

        await snakecore.utils.embeds.replace_embed_at(
            response_message,
            title="Blacklisted!",
            description=f"Successfully blacklisted {cnt} command(s)",
            color=common.DEFAULT_EMBED_COLOR,
        )

    @commands.command()
    @admin_only_and_custom_parsing(inside_class=True, inject_message_reference=True)
    async def admin_clock(
        self,
        ctx: commands.Context,
        *,
        action: str = "",
        timezone: float = 0,
        color: Optional[discord.Color] = None,
        member: Optional[discord.Member] = None,
    ):
        """
        ->type Get help
        ->signature pg!admin_clock [action=""] [timezone=] [color=] [member=]
        ->description 24 Hour Clock showing <@&778205389942030377> s who are available to help
        ->extended description
        Admins can run this command with more arguments, to add/update/remove other members.
        `pg!admin_clock update [timezone in hours] [color as hex string] [mention member]`
        `pg!admin_clock remove [mention member]`
        -----
        Implement pg!clock, to display a clock of helpfulies/mods/wizards
        """
        return await self.clock_func(
            ctx, action=action, timezone=timezone, color=color, _member=member
        )

    @commands.command()
    @admin_only_and_custom_parsing(inside_class=True, inject_message_reference=True)
    async def eval(self, ctx: commands.Context, code: CodeBlock):
        """
        ->type Admin commands
        ->signature pg!eval <command>
        ->description Execute a line of command without restrictions
        -----
        Implement pg!eval, for admins to run arbitrary code on the bot
        """
        # make typecheckers happy
        if not isinstance(ctx.author, discord.Member):
            return

        response_message = common.recent_response_messages[ctx.message.id]

        evalable = False
        for role in ctx.author.roles:
            if role.id in common.GuildConstants.EVAL_ROLES:
                evalable = True

        if common.TEST_MODE and ctx.author.id in common.TEST_USER_IDS:
            evalable = True

        if not evalable:
            raise BotException(
                "Insufficient Permissions!",
                "You do not have enough permissions to run this command.",
            )

        try:
            script = compile(code.code, "<string>", "eval")  # compile script

            script_start = time.perf_counter()
            eval_output = eval(script)  # pylint: disable = eval-used
            total = time.perf_counter() - script_start

        except Exception as ex:
            raise BotException(
                "An exception occured:",
                snakecore.utils.code_block(
                    type(ex).__name__ + ": " + ", ".join(map(str, ex.args))
                ),
            )

        await snakecore.utils.embeds.replace_embed_at(
            response_message,
            title=f"Return output (code executed in {snakecore.utils.format_time_by_units(total)}):",
            description=snakecore.utils.code_block(repr(eval_output)),
            color=common.DEFAULT_EMBED_COLOR,
        )

    @commands.command()
    @admin_only()
    async def heap(self, ctx: commands.Context):
        """
        ->type Admin commands
        ->signature pg!heap
        ->description Show the memory usage of the bot
        -----
        Implement pg!heap, for admins to check memory taken up by the bot
        """
        mem = process.memory_info().rss

        response_message = common.recent_response_messages[ctx.message.id]

        await snakecore.utils.embeds.replace_embed_at(
            response_message,
            title="Total memory used:",
            description=f"**{snakecore.utils.format_byte(mem, 4)}**\n({mem} B)",
            color=common.DEFAULT_EMBED_COLOR,
        )

    @commands.command()
    @admin_only()
    async def stop(self, ctx: commands.Context):
        """
        ->type Admin commands
        ->signature pg!stop [*ids]
        ->description Stop the bot
        ->extended description
        Any additional arguments are IDs of members running test bots, to stop
        the test bots of particular wizards
        -----
        The actual pg!stop function is implemented elsewhere, this is just
        a stub for the docs
        """

    @commands.command()
    @admin_only_and_custom_parsing(inside_class=True, inject_message_reference=True)
    async def archive(
        self,
        ctx: commands.Context,
        origin: discord.TextChannel,
        quantity: Optional[int] = None,
        mode: int = 0,
        destination: Optional[Union[discord.TextChannel, discord.Thread]] = None,
        before: Optional[Union[discord.PartialMessage, datetime.datetime]] = None,
        after: Optional[Union[discord.PartialMessage, datetime.datetime]] = None,
        around: Optional[Union[discord.PartialMessage, datetime.datetime]] = None,
        raw: bool = False,
        show_header: bool = True,
        show_author: bool = True,
        divider: String = String("-" * 56),
        group_by_author: bool = True,
        group_by_author_timedelta: float = 600.0,
        message_links: bool = True,
        oldest_first: bool = True,
        same_channel: bool = False,
    ):
        """
        ->type Admin commands
        ->signature pg!archive <origin> <quantity> [mode=0] [destination=]
        [before=] [after=] [around=] [raw=False] [show_header=True] [show_author=True]
        [divider=("-"*56)] [group_by_author=True] [group_by_author_timedelta=600]
        [message_links=True] [oldest_first=True] [same_channel=False]
        ->description Archive messages to another channel
        -----
        Implement pg!archive, for admins to archive messages
        """

        response_message = common.recent_response_messages[ctx.message.id]

        if destination is None:
            destination = ctx.channel

        if not snakecore.utils.have_permissions_in_channels(
            ctx.author,
            origin,
            "view_channel",
        ) or not snakecore.utils.have_permissions_in_channels(
            ctx.author,
            destination,
            "view_channel",
            "send_messages",
        ):
            raise BotException(
                "Not enough permissions",
                "You do not have enough permissions to run this command on the specified channel(s).",
            )

        archive_header_msg = None
        archive_header_msg_embed = None

        if origin.id == destination.id and not same_channel:
            raise BotException(
                "Cannot execute command:", "Origin and destination channels are same"
            )

        divider_str = divider.string

        if (
            isinstance(before, discord.PartialMessage)
            and before.channel.id != origin.id
        ):
            raise BotException(
                "Invalid `before` argument",
                "`before` has to be an ID to a message from the origin channel",
            )

        if isinstance(after, discord.PartialMessage) and after.channel.id != origin.id:
            raise BotException(
                "Invalid `after` argument",
                "`after` has to be an ID to a message from the origin channel",
            )

        if (
            isinstance(around, discord.PartialMessage)
            and around.channel.id != origin.id
        ):
            raise BotException(
                "Invalid `around` argument",
                "`around` has to be an ID to a message from the origin channel",
            )

        quantity = quantity or 0

        if quantity <= 0:
            if quantity == 0 and not after:
                raise BotException(
                    "Invalid `quantity` argument",
                    "`quantity` must be above 0 when `after=` is not specified.",
                )
            elif quantity != 0:
                raise BotException(
                    "Invalid `quantity` argument",
                    "Quantity has to be a positive integer (or `0` when `after=` is specified).",
                )

        await destination.typing()
        messages = [
            msg
            async for msg in origin.history(
                limit=quantity if quantity != 0 else None,
                before=before,
                after=after,
                around=around,
            )
        ]

        message_id_cache = {}

        if not messages:
            raise BotException(
                "Invalid time range",
                "No messages were found for the specified timestamps.",
            )

        if not after and oldest_first:
            messages.reverse()

        if show_header and not raw:
            start_date = messages[0].created_at
            end_date = messages[-1].created_at

            if start_date == end_date:
                header_fields = (
                    {
                        "name": f"On: {snakecore.utils.create_markdown_timestamp(start_date)}",
                        "value": "\u200b",
                        "inline": True,
                    },
                )
            else:
                header_fields = (
                    {
                        "name": f"From: {snakecore.utils.create_markdown_timestamp(start_date)}",
                        "value": "\u200b",
                        "inline": True,
                    },
                    {
                        "name": f"To: {snakecore.utils.create_markdown_timestamp(end_date)}",
                        "value": "\u200b",
                        "inline": True,
                    },
                )

            archive_header_msg_embed = snakecore.utils.embeds.create_embed(
                title=f"__Archive of `#{origin.name}`__",
                description=f"\nAn archive of **{origin.mention}**"
                f"({len(messages)} message(s))\n\u200b",
                fields=header_fields,
                color=0xFFFFFF,
                footer_text="Status: Incomplete",
            )

            archive_header_msg = await destination.send(embed=archive_header_msg_embed)

        no_mentions = discord.AllowedMentions.none()

        load_embed = snakecore.utils.embeds.create_embed(
            title="Your command is being processed:",
            color=common.DEFAULT_EMBED_COLOR,
            fields=[dict(name="\u200b", value="`...`", inline=False)],
        )
        msg_count = len(messages)
        with io.StringIO("This file was too large to be archived.") as fobj:
            msg: discord.Message
            for i, msg in enumerate(
                reversed(messages) if not oldest_first else messages
            ):
                if msg_count > 2 and not i % 2:
                    snakecore.utils.embeds.edit_embed_field_from_dict(
                        load_embed,
                        0,
                        dict(
                            name="Archiving Messages",
                            value=f"`{i}/{msg_count}` messages archived\n"
                            f"{(i / msg_count) * 100:.01f}% | "
                            + snakecore.utils.progress_bar(i / msg_count, divisions=30),
                        ),
                    )

                    await response_message.edit(embed=load_embed)

                author = msg.author
                msg_reference_id = None
                if msg.reference and not isinstance(
                    msg.reference, discord.DeletedReferencedMessage
                ):
                    msg_reference_id = message_id_cache.get(msg.reference.message_id)

                await destination.typing()

                fobj.seek(0)

                filesize_limit = (
                    ctx.guild.filesize_limit
                    if ctx.guild is not None
                    else common.DEFAULT_FILESIZE_LIMIT
                )

                attached_files = [
                    (
                        await a.to_file(spoiler=a.is_spoiler())
                        if a.size <= filesize_limit
                        else discord.File(fobj, f"filetoolarge - {a.filename}.txt")
                    )
                    for a in msg.attachments
                ]

                if not raw:
                    author_embed = None
                    current_divider_str = divider_str
                    if show_author or divider_str:
                        if (
                            group_by_author
                            and i > 0
                            and messages[i - 1].author == author
                            and (
                                msg.created_at - messages[i - 1].created_at
                            ).total_seconds()
                            < group_by_author_timedelta
                        ):
                            # no author info or divider for messages next to
                            # each other sharing an author
                            current_divider_str = None
                        else:
                            shorten = i > 0 and messages[i - 1].author == author
                            if shorten:
                                shorten_style = (
                                    "t"
                                    if messages[i - 1].created_at.day
                                    == msg.created_at.day
                                    else "f"
                                )
                                description_str = (
                                    f"{snakecore.utils.create_markdown_timestamp(msg.created_at, tformat=shorten_style)}"
                                    + (
                                        f" [View]({msg.jump_url})"
                                        if message_links
                                        else ""
                                    )
                                )
                            else:
                                description_str = (
                                    f"{author.mention}"
                                    f" {snakecore.utils.create_markdown_timestamp(msg.created_at)}"
                                    + (
                                        f" [View]({msg.jump_url})"
                                        if message_links
                                        else ""
                                    )
                                )

                            author_embed = snakecore.utils.embeds.create_embed(
                                description=description_str,
                                color=0x36393F,
                                author_name=f"{author.name}#{author.discriminator}"
                                if not shorten
                                else None,
                                author_icon_url=(author.display_avatar.url)
                                if not shorten
                                else None,
                            )

                        if author_embed or current_divider_str:
                            await destination.send(
                                content=current_divider_str,
                                embed=author_embed,
                                allowed_mentions=no_mentions,
                            )

                if not mode:
                    if msg.content or msg.embeds or attached_files:
                        msg_embed = msg.embeds[0] if msg.embeds else None
                        msg_embed_dict = (
                            msg_embed.to_dict() if msg_embed is not None else None
                        )

                        if msg_embed_dict and msg_embed_dict.get("type") == "gifv":
                            msg_embed = None

                        if len(msg.content) > 2000:
                            start_idx = 0
                            stop_idx = 0
                            for i in range(len(msg.content) // 2000):
                                start_idx = 2000 * i
                                stop_idx = 2000 + 2000 * i

                                if not i:
                                    message_id_cache[msg.id] = await destination.send(
                                        content=msg.content[start_idx:stop_idx],
                                        allowed_mentions=no_mentions,
                                        reference=msg_reference_id,
                                    )
                                else:
                                    await destination.send(
                                        content=msg.content[start_idx:stop_idx],
                                        allowed_mentions=no_mentions,
                                    )

                            with io.StringIO(msg.content) as fobj:
                                await destination.send(
                                    content=msg.content[stop_idx:],
                                    embed=snakecore.utils.embeds.create_embed(
                                        color=common.DEFAULT_EMBED_COLOR,
                                        footer_text="Full message data",
                                    ),
                                    file=discord.File(fobj, filename="messagedata.txt"),
                                    allowed_mentions=no_mentions,
                                )

                            await destination.send(
                                embed=msg_embed,
                                file=attached_files[0] if attached_files else None,
                            )
                        else:
                            message_id_cache[msg.id] = await destination.send(
                                content=msg.content,
                                embed=msg_embed,
                                file=attached_files[0] if attached_files else None,
                                allowed_mentions=no_mentions,
                                reference=msg_reference_id,
                            )

                    elif msg.type == discord.MessageType.pins_add:
                        await snakecore.utils.embeds.send_embed(
                            channel=destination,
                            description=f"**{msg.author.name}#{msg.author.discriminator}** pinned a message in #{origin.name}",
                            color=0x36393F,
                        )

                    elif msg.type == discord.MessageType.premium_guild_subscription:
                        await snakecore.utils.embeds.send_embed(
                            channel=destination,
                            description=f"{msg.author.name}#{msg.author.discriminator} just boosted this server!",
                            color=0x36393F,
                        )

                    if len(attached_files) > 1:
                        for i in range(1, len(attached_files)):
                            await destination.send(
                                content=f"**Message attachment** ({i + 1}):",
                                file=attached_files[i],
                            )

                    for i in range(1, len(msg.embeds)):
                        if not i % 3:
                            await destination.typing()
                        await destination.send(embed=msg.embeds[i])

                elif mode == 1 or mode == 2:
                    if mode == 1:
                        if msg.content:
                            escaped_msg_content = msg.content.replace(
                                "```", "\\`\\`\\`"
                            )
                            if (
                                len(msg.content) > 2000
                                or len(escaped_msg_content) + 7 > 2000
                            ):
                                with io.StringIO(msg.content) as fobj:
                                    message_id_cache[msg.id] = await destination.send(
                                        file=discord.File(fobj, "messagedata.txt"),
                                        reference=msg_reference_id,
                                    )
                            else:
                                message_id_cache[msg.id] = await destination.send(
                                    embed=snakecore.utils.embeds.create_embed(
                                        color=0x36393F,
                                        description=f"```\n{escaped_msg_content}```",
                                    ),
                                    reference=msg_reference_id,
                                )

                        if attached_files:
                            for i in range(len(attached_files)):
                                await destination.send(
                                    content=f"**Message attachment** ({i + 1}):",
                                    file=attached_files[i],
                                )
                    else:
                        if msg.content:
                            with io.StringIO(msg.content) as fobj2:
                                message_id_cache[msg.id] = await destination.send(
                                    file=discord.File(
                                        fobj2, filename="messagedata.txt"
                                    ),
                                    allowed_mentions=no_mentions,
                                    reference=msg_reference_id,
                                )

                        if attached_files:
                            for i in range(len(attached_files)):
                                await destination.send(
                                    content=f"**Message attachment** ({i + 1}):",
                                    file=attached_files[i],
                                )

                    if msg.embeds:
                        embed_data_fobjs = []
                        for embed in msg.embeds:
                            embed_data_fobj = io.StringIO()
                            snakecore.utils.embeds.export_embed_data(
                                embed.to_dict(),
                                fp=embed_data_fobj,
                                indent=4,
                                as_json=True,
                            )
                            embed_data_fobj.seek(0)
                            embed_data_fobjs.append(embed_data_fobj)

                        for i in range(len(embed_data_fobjs)):
                            await destination.send(
                                content=f"**Message embed** ({i + 1}):",
                                file=discord.File(
                                    embed_data_fobjs[i], filename="embeddata.json"
                                ),
                            )

                        for embed_data_fobj in embed_data_fobjs:
                            embed_data_fobj.close()

                await asyncio.sleep(0)

        if divider_str and not raw:
            await destination.send(content=divider_str)

        if show_header and not raw:
            archive_header_msg_embed.set_footer(text="Status: Complete")
            if archive_header_msg is not None:
                await archive_header_msg.edit(embed=archive_header_msg_embed)

        snakecore.utils.embeds.edit_embed_field_from_dict(
            load_embed,
            0,
            dict(
                name=f"Successfully archived {msg_count} message(s)",
                value=f"`{msg_count}/{msg_count}` messages archived\n"
                "100% | " + snakecore.utils.progress_bar(1.0, divisions=30),
            ),
        )

        await response_message.edit(embed=load_embed)

        try:
            await response_message.delete(delay=10.0 if msg_count > 2 else 0.0)
        except discord.NotFound:
            pass

    @commands.group(invoke_without_command=True)
    @admin_only_and_custom_parsing(inside_class=True, inject_message_reference=True)
    async def pin(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
        *msgs: discord.PartialMessage,
        delete_system_messages: bool = True,
        flush_bottom: bool = True,
    ):
        """
        ->type Admin commands
        ->signature pg!pin <channel> <message> <message>... [pin_info=False] [flush_bottom=True]
        ->description Pin a message in the specified channel.
        ->example command pg!pin 123412345567891 23456234567834567 3456734523456734567...
        """

        response_message = common.recent_response_messages[ctx.message.id]

        if not snakecore.utils.have_permissions_in_channels(
            ctx.author,
            channel,
            "view_channel",
            "manage_messages",
        ):
            raise BotException(
                "Not enough permissions",
                "You do not have enough permissions to run this command on the specified channel.",
            )

        if not msgs:
            raise BotException(
                "Invalid arguments!",
                "No message IDs given as input.",
            )
        elif len(msgs) > 50:
            raise BotException(
                "Too many arguments!",
                "Cannot pin more than 50 messages in a channel.",
            )

        elif not all(msg.channel.id == channel.id for msg in msgs):
            raise BotException(
                "Invalid message ID(s) given as input",
                "Each ID must be from a message in the given target channel",
            )

        pinned_msgs = await channel.pins()

        unpin_count = max((len(pinned_msgs) + len(msgs)) - 50, 0)
        if unpin_count > 0:
            for i in range(unpin_count):
                try:
                    await pinned_msgs[i].unpin()
                except discord.HTTPException as e:
                    raise BotException(f"Cannot unpin message at index {i}!", e.args[0])

        load_embed = snakecore.utils.embeds.create_embed(
            title="Your command is being processed:",
            color=common.DEFAULT_EMBED_COLOR,
            fields=[dict(name="\u200b", value="`...`", inline=False)],
        )
        msg_count = len(msgs)
        for i, msg in enumerate(msgs):
            if msg_count > 2 and not i % 3:
                snakecore.utils.embeds.edit_embed_field_from_dict(
                    load_embed,
                    0,
                    dict(
                        name="Processing Messages",
                        value=f"`{i}/{msg_count}` messages processed\n"
                        f"{(i / msg_count) * 100:.01f}% | "
                        + snakecore.utils.progress_bar(i / msg_count, divisions=30),
                    ),
                )

                await response_message.edit(embed=load_embed)
            try:
                await msg.pin()
            except discord.HTTPException as e:
                raise BotException(f"Cannot pin input message {i}!", e.args[0])

            if delete_system_messages:
                try:
                    await (
                        await channel.fetch_message(channel.last_message_id)
                    ).delete()
                except (discord.HTTPException, discord.NotFound):
                    pass

            await asyncio.sleep(0)

        snakecore.utils.embeds.edit_embed_field_from_dict(
            load_embed,
            0,
            dict(
                name=f"Sucessfully pinned {msg_count} message(s) ({unpin_count} removed)!",
                value=f"`{msg_count}/{msg_count}` messages pinned\n"
                "100% | " + snakecore.utils.progress_bar(1.0, divisions=30),
            ),
        )

        await response_message.edit(embed=load_embed)

        try:
            if not delete_system_messages:
                await ctx.message.delete()
            await response_message.delete(delay=10.0 if msg_count > 2 else 0.0)
        except discord.NotFound:
            pass

    @pin.group(name="remove", invoke_without_command=True)
    @admin_only_and_custom_parsing(inside_class=True, inject_message_reference=True)
    async def pin_remove(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
        *msgs: discord.PartialMessage,
    ):
        """
        ->type Admin commands
        ->signature pg!pin remove <channel> <message> <message>...
        ->description Unpin a message in the specified channel.
        ->example command pg!unpin #general 23456234567834567 3456734523456734567...
        """

        response_message = common.recent_response_messages[ctx.message.id]

        if not snakecore.utils.have_permissions_in_channels(
            ctx.author,
            channel,
            "view_channel",
            "manage_messages",
        ):
            raise BotException(
                "Not enough permissions",
                "You do not have enough permissions to run this command on the specified channel.",
            )

        if not msgs:
            raise BotException(
                "Invalid arguments!",
                "No message IDs given as input.",
            )
        elif len(msgs) > 50:
            raise BotException(
                "Too many arguments!",
                "No more than 50 messages can be pinned in a channel.",
            )
        elif not all(msg.channel.id == channel.id for msg in msgs):
            raise BotException(
                "Invalid message ID(s) given as input",
                "Each ID must be from a message in the given target channel",
            )

        pinned_msgs = await channel.pins()
        pinned_msg_id_set = set(msg.id for msg in pinned_msgs)

        load_embed = snakecore.utils.embeds.create_embed(
            title="Your command is being processed:",
            color=common.DEFAULT_EMBED_COLOR,
            fields=[dict(name="\u200b", value="`...`", inline=False)],
        )

        msg_count = len(msgs)
        for i, msg in enumerate(msgs):
            if msg_count > 2 and not i % 3:
                snakecore.utils.embeds.edit_embed_field_from_dict(
                    load_embed,
                    0,
                    dict(
                        name="Processing Messages",
                        value=f"`{i}/{msg_count}` messages processed\n"
                        f"{(i / msg_count) * 100:.01f}% | "
                        + snakecore.utils.progress_bar(i / msg_count, divisions=30),
                    ),
                    0,
                )

                await response_message.edit(embed=load_embed)

            if msg.id in pinned_msg_id_set:
                try:
                    await msg.unpin()
                except discord.HTTPException as e:
                    raise BotException(f"Cannot unpin input message {i}!", e.args[0])

            await asyncio.sleep(0)

        snakecore.utils.embeds.edit_embed_field_from_dict(
            load_embed,
            0,
            dict(
                name=f"Succesfully unpinned {msg_count} message(s)!",
                value=f"`{msg_count}/{msg_count}` messages processed\n"
                "100% | " + snakecore.utils.progress_bar(1.0, divisions=30),
            ),
        )

        await response_message.edit(embed=load_embed)

        try:
            await response_message.delete(delay=10.0 if msg_count > 2 else 0.0)
        except discord.NotFound:
            pass

    @pin_remove.command(name="at")
    @admin_only_and_custom_parsing(inside_class=True, inject_message_reference=True)
    async def pin_remove_at(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
        *indices: Union[int, range],
    ):
        """
        ->type Admin commands
        ->signature pg!pin remove at <channel> <index/range> ...
        ->description Unpin a message in the specified channel.
        ->example command pg!pin remove at #general 3.. range(9, 15)..
        """

        response_message = common.recent_response_messages[ctx.message.id]

        if not snakecore.utils.have_permissions_in_channels(
            ctx.author,
            channel,
            "view_channel",
            "manage_messages",
        ):
            raise BotException(
                "Not enough permissions",
                "You do not have enough permissions to run this command on the specified channel.",
            )

        if not indices:
            raise BotException(
                "Invalid arguments!",
                "No channel pin list indices given as input.",
            )

        pinned_msgs = await channel.pins()

        pinned_msg_count = len(pinned_msgs)

        if not pinned_msgs:
            raise BotException(
                "No messages to unpin!",
                "No messages are currently pinned on the specified channel.",
            )

        unpinned_msg_id_set = set()

        indices_list = []

        for index in indices:
            if isinstance(index, range):
                if len(index) > 50:
                    raise BotException(
                        "Invalid range object!",
                        "The given range object must not contain more than 50 integers.",
                    )
                else:
                    indices_list.extend(index)

            else:
                indices_list.append(index)

        indices_list = sorted(set(indices_list))
        indices_list.reverse()

        load_embed = snakecore.utils.embeds.create_embed(
            title="Your command is being processed:",
            color=common.DEFAULT_EMBED_COLOR,
            fields=[dict(name="\u200b", value="`...`", inline=False)],
        )

        idx_count = len(indices_list)
        for i, unpin_index in enumerate(indices_list):
            if unpin_index < 0:
                unpin_index = pinned_msg_count + unpin_index

            if idx_count > 2 and not i % 3:
                snakecore.utils.embeds.edit_embed_field_from_dict(
                    load_embed,
                    0,
                    dict(
                        name="Processing Messages",
                        value=f"`{i}/{idx_count}` messages processed\n"
                        f"{(i / idx_count) * 100:.01f}% | "
                        + snakecore.utils.progress_bar(i / idx_count, divisions=30),
                    ),
                )

                await response_message.edit(embed=load_embed)

            if 0 <= unpin_index < pinned_msg_count:
                msg = pinned_msgs[unpin_index]

                if msg.id not in unpinned_msg_id_set:
                    try:
                        await msg.unpin()
                        unpinned_msg_id_set.add(msg.id)
                    except discord.HTTPException as e:
                        raise BotException(
                            f"Cannot unpin input message {i}!", e.args[0]
                        )

            await asyncio.sleep(0)

        snakecore.utils.embeds.edit_embed_field_from_dict(
            load_embed,
            0,
            dict(
                name=f"Succesfully unpinned {idx_count} message(s)!",
                value=f"`{idx_count}/{idx_count}` messages processed\n"
                "100% | " + snakecore.utils.progress_bar(1.0, divisions=30),
            ),
        )

        await response_message.edit(embed=load_embed)

        try:
            await response_message.delete(delay=10.0 if idx_count > 2 else 0.0)
        except discord.NotFound:
            pass

    @commands.group(invoke_without_command=True)
    @admin_only_and_custom_parsing(inside_class=True, inject_message_reference=True)
    async def admin_poll(
        self,
        ctx: commands.Context,
        desc: String,
        *emojis: tuple[str, String],
        destination: Optional[Union[discord.TextChannel, discord.Thread]] = None,
        author: Optional[String] = None,
        color: Optional[discord.Color] = None,
        url: Optional[String] = None,
        image_url: Optional[String] = None,
        thumbnail: Optional[String] = None,
        multi_votes: bool = True,
    ):
        """
        ->type Admin commands
        ->signature pg!admin_poll <description> [*emojis] [author] [color] [url] [image_url] [thumbnail] [multi_votes=True]
        ->description Start a poll.
        ->extended description
        The args must series of two element tuples, first element being emoji,
        and second being the description (see example command).
        The emoji must be a default emoji or one from this server. To close the poll see 'pg!poll close'.
        A `multi_votes` arg can also be passed indicating if the user can cast multiple votes in a poll or not
        ->example command pg!admin_poll "Which apple is better?" ( 🍎 "Red apple") ( 🍏 "Green apple")
        """

        if not isinstance(destination, discord.TextChannel):
            destination = ctx.channel

        if not snakecore.utils.have_permissions_in_channels(
            ctx.author,
            destination,
            "view_channel",
            "send_messages",
        ):
            raise BotException(
                "Not enough permissions",
                "You do not have enough permissions to run this command on the specified channel.",
            )

        embed_dict = {}
        if author:
            embed_dict["author"] = {"name": author.string}

        if color:
            embed_dict["color"] = pgbot.utils.color_to_rgb_int(color)

        if url:
            embed_dict["url"] = url.string

        if image_url:
            embed_dict["image"] = {"url": image_url.string}

        if thumbnail:
            embed_dict["thumbnail"] = {"url": thumbnail.string}

        return await self.poll_func(
            ctx,
            desc,
            *emojis,
            multi_votes=multi_votes,
            _destination=destination,
            _admin_embed_dict=embed_dict,
        )

    @admin_poll.command(name="close")
    @admin_only_and_custom_parsing(inside_class=True, inject_message_reference=True)
    async def admin_poll_close(
        self,
        ctx: commands.Context,
        msg: Optional[discord.Message] = None,
        *,
        color: discord.Color = discord.Color(0xA83232),
    ):
        """
        ->type Admin commands
        ->signature pg!admin_poll close <msg> [color]
        ->description Close an ongoing poll.
        ->extended description
        The poll can only be closed by the person who started it or by mods.
        The color is the color of the closed poll embed
        """
        return await self.poll_close_func(ctx, msg, _color=color, _privileged=True)

    @commands.group(invoke_without_commmand=True)
    @admin_only()
    async def admin_stream(self, ctx: commands.Context):
        """
        ->type Admin commands
        ->signature pg!admin_stream
        ->description Show the ping-stream-list
        Send an embed with all the users currently in the ping-stream-list
        """

        return await self.stream_func(ctx)

    @admin_stream.command(name="add")
    @admin_only_and_custom_parsing(inside_class=True, inject_message_reference=True)
    async def admin_stream_add(self, ctx: commands.Context, *members: discord.Member):
        """
        ->type Admin commands
        ->signature pg!admin_stream add [*members]
        ->description Add user(s) to the ping list for stream
        ->extended description
        The command give mods the chance to add users to the ping list manually.
        Without arguments, equivalent to the "user" version of this command
        """
        await self.stream_add_func(_members=members if members else None)

    @admin_stream.command(name="del")
    @admin_only_and_custom_parsing(inside_class=True, inject_message_reference=True)
    async def admin_stream_del(self, ctx: commands.Context, *members: discord.Member):
        """
        ->type Admin commands
        ->signature pg!admin_stream del [*members]
        ->description Remove user(s) to the ping list for stream
        ->extended description
        The command give mods the chance to remove users from the ping list manually.
        Without arguments, equivalent to the "user" version of this command
        """
        await self.stream_del_func(_members=members if members else None)

    @admin_stream.command(name="ping")
    @admin_only_and_custom_parsing(inside_class=True, inject_message_reference=True)
    async def admin_stream_ping(
        self, ctx: commands.Context, message: Optional[String] = None
    ):
        """
        ->type Admin commands
        ->signature pg!admin_stream ping [message]
        ->description Ping users in stream-list with an optional message.
        ->extended description
        Ping all users in the ping list to announce a stream.
        You can pass an optional stream message (like the stream topic).
        The streamer name will be included and many people will be pinged so \
        don't make pranks with this command.
        """
        return await self.stream_ping(ctx, message=message)

    @commands.group(invoke_without_command=True)
    @admin_only_and_custom_parsing(inside_class=True, inject_message_reference=True)
    async def info(
        self,
        ctx: commands.Context,
        *objs: Union[discord.Message, discord.Member, discord.User],
        author: bool = True,
    ):
        """
        ->type More admin commands
        ->signature pg!info <*objects> [author=True]
        ->description Get information about a Discord message/user/member

        ->extended description
        Return an information embed for the given Discord objects.

        __Args__:
            `*objects: (Message|User|Member)`
            > A sequence of Discord ojbects whose info
            > should be retrieved. If no input is given,
            > an information embed on the

            `author_info: (bool) = True`
            > If set to `True`, extra information about
            > the authors of any message given as input
            > will be added to their info embeds.

        __Returns__:
            > One or more embeds containing information about
            > the given inputs.

        __Raises__:
            > `BotException`: One or more given arguments are invalid.
            > `HTTPException`: An invalid operation was blocked by Discord.
        -----
        """

        response_message = common.recent_response_messages[ctx.message.id]

        checked_channels = set()

        for i, obj in enumerate(objs):
            if isinstance(obj, discord.Message):
                if not snakecore.utils.have_permissions_in_channels(
                    ctx.author,
                    obj.channel,
                    "view_channel",
                ):
                    raise BotException(
                        "Not enough permissions",
                        "You do not have enough permissions to run this command on the specified channel.",
                    )
                else:
                    checked_channels.add(obj.channel)

            if not i % 50:
                await asyncio.sleep(0)

        if not objs:
            obj = ctx.author
            embed = pgbot.utils.embed_utils.get_member_info_embed(obj)
            await ctx.channel.send(embed=embed)

        load_embed = snakecore.utils.embeds.create_embed(
            title="Your command is being processed:",
            color=common.DEFAULT_EMBED_COLOR,
            fields=[dict(name="\u200b", value="`...`", inline=False)],
        )
        obj_count = len(objs)
        for i, obj in enumerate(objs):
            if obj_count > 2 and not i % 3:
                await snakecore.utils.embeds.edit_embed_field_from_dict(
                    load_embed,
                    0,
                    dict(
                        name="Processing Inputs",
                        value=f"`{i}/{obj_count}` inputs processed\n"
                        f"{(i / obj_count) * 100:.01f}% | "
                        + snakecore.utils.progress_bar(i / obj_count, divisions=30),
                    ),
                )

                await response_message.edit(embed=load_embed)

            await ctx.channel.typing()
            embed = None
            if isinstance(obj, discord.Message):
                embed = pgbot.utils.embed_utils.get_msg_info_embed(obj, author=author)

            elif isinstance(obj, (discord.Member, discord.User)):
                embed = pgbot.utils.embed_utils.get_member_info_embed(obj)

            if embed is not None:
                await ctx.channel.send(embed=embed)

            await asyncio.sleep(0)

        if obj_count > 2:
            snakecore.utils.embeds.edit_embed_field_from_dict(
                load_embed,
                0,
                dict(
                    name="Processing Complete",
                    value=f"`{obj_count}/{obj_count}` inputs processed\n"
                    "100% | " + snakecore.utils.progress_bar(1.0, divisions=30),
                ),
            )

            await response_message.edit(embed=load_embed)

        try:
            await response_message.delete(delay=10.0 if obj_count > 1 else 0.0)
        except discord.NotFound:
            pass

    @info.command(name="server")
    @admin_only_and_custom_parsing(inside_class=True, inject_message_reference=True)
    async def info_server(
        self, ctx: commands.Context, guild: Optional[discord.Guild] = None
    ):
        """
        ->type More admin commands
        ->signature pg!info server [guild_id=None]
        ->description Get information about a Discord server

        ->extended description
        Return an information embed for the Discord server ID given

        __Args__:
            `guild_id: (int) = None`
            > An integer that should represent
            > a server's ID. If no input is given,
            > the server would be set to the server
            > where the command was invoked

        __Returns__:
            > An embed with the given server's information

        __Raises__:
            > `BotException`: The guild either doesn't exist or is private
            > `HTTPException`: An invalid operation was blocked by Discord.
        -----
        """

        response_message = common.recent_response_messages[ctx.message.id]

        if guild is None:
            guild = ctx.guild
            if guild is None:
                guild = common.guild

        description = (
            f"Server Name: `{guild.name}`\n"
            f"Server ID: `{guild.id}`\n"
            f"Created At: {snakecore.utils.create_markdown_timestamp(guild.created_at)}\n"
        )

        description += f"Number of Members: `{guild.member_count}`\n"

        number_of_bots = len([i for i in guild.members if i.bot])
        number_of_members = len(guild.members) - number_of_bots
        description += f"> - `{number_of_members}` humans\n"
        description += f"> - `{number_of_bots}` bots\n"

        description += f"Number of Channels: `{len(guild.channels)}`\n"

        description += f"Number of Roles: `{len(guild.roles)}`\n"

        if guild.premium_subscription_count != 0:
            description += (
                f"Number of Server Boosts: `{guild.premium_subscription_count}`\n"
            )

        if guild.owner is not None:
            description += (
                f"Owner of Server: `{guild.owner.name}#{guild.owner.discriminator}`\n"
            )

        kwargs = {
            "title": f"Server information for {guild.name}:",
            "thumbnail_url": guild.icon.url if guild.icon is not None else None,
            "description": description,
            "color": common.DEFAULT_EMBED_COLOR,
        }

        await snakecore.utils.embeds.replace_embed_at(response_message, **kwargs)

    @commands.command()
    @admin_only_and_custom_parsing(inside_class=True, inject_message_reference=True)
    async def react(
        self,
        ctx: commands.Context,
        messages: Union[discord.PartialMessage, tuple[discord.PartialMessage, ...]],
        *emojis: str,
    ):
        """
        ->type More admin commands
        ->signature pg!react <message> <emojis>
        ->description Reacts to a Discord message

        ->extended description
        Reacts to a Discord message with the given emojis.

        __Args__:
            `message: Message | (Message ...)`
            > A Discord message or a tuple sequence of them that reactions should be added to.

            `*emojis: str`
            > The emojis to react with, separated by spaces.

        __Raises__:
            > `BotException`: One or more given arguments are invalid.
            > `HTTPException`: An invalid operation was blocked by Discord.
        -----
        """

        if isinstance(messages, discord.PartialMessage):
            messages = (messages,)

        response_message = common.recent_response_messages[ctx.message.id]

        for emoji in emojis:
            try:
                for message in messages:
                    await message.add_reaction(emoji)
            except discord.HTTPException as e:
                e.args = (
                    e.args[0]
                    + "\n\nYou gave me some invalid emojis or I am unable to use them here. "
                    "Remember the emojis have to be separated by spaces. Find help in "
                    "`pg!help react`",
                )
                raise
        try:
            await ctx.message.delete()
            await response_message.delete()
        except discord.NotFound:
            pass

    @commands.command()
    @admin_only_and_custom_parsing(inside_class=True, inject_message_reference=True)
    async def browse(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
        quantity: Optional[int] = None,
        before: Optional[Union[discord.Message, datetime.datetime]] = None,
        after: Optional[Union[discord.Message, datetime.datetime]] = None,
        around: Optional[Union[discord.Message, datetime.datetime]] = None,
        controllers: Optional[tuple[discord.Member, ...]] = None,
        page: int = 1,
    ):
        """
        ->type More admin commands
        ->signature pg!browse <channel> [quantity=] [before=] [after=] [around=] [controllers=]
        ->description Browse through Discord messages

        ->extended description
        Function to help browse through discord messages

        __Args__:
            `channel: discord.TextChannel`
            > The discord channel to browse the messages from.

            `quantity: Optional[int]`
            > The number of messages to get

            `before: Optional[Time | Message]`
            > The message or time before which the messages should be shown.

            `after: Optional[Time | Message]`
            > The message or time after which the messages should be shown.

            `around: Optional[Time | Message]`
            > The message or time around which the messages should be shown.

            `controllers: Optional[User | tuple[user]]`
            > The user(s) who can control the embed.

        __Raises__:
            > `BotException`: One or more given arguments are invalid.
            > `HTTPException`: An invalid operation was blocked by Discord.
        -----
        """

        response_message = common.recent_response_messages[ctx.message.id]

        controllers = controllers or None

        # needed for typecheckers to know that ctx.author is a member
        if isinstance(ctx.author, discord.User):
            return

        if not snakecore.utils.have_permissions_in_channels(
            ctx.author,
            channel,
            "view_channel",
        ):
            raise BotException(
                f"Not enough permissions",
                "You do not have enough permissions to run this command on the specified channel(s).",
            )

        if not (before and after) and quantity is None:
            raise BotException(
                "Missing argument.",
                "Argument quantity must be specified.",
            )

        if isinstance(before, discord.Message) and before.channel.id != channel.id:
            raise BotException(
                "Invalid `before` argument",
                "`before` has to be an ID to a message from the origin channel",
            )

        if isinstance(after, discord.Message) and after.channel.id != channel.id:
            raise BotException(
                "Invalid `after` argument",
                "`after` has to be an ID to a message from the origin channel",
            )

        if isinstance(around, discord.Message) and around.channel.id != channel.id:
            raise BotException(
                "Invalid `around` argument",
                "`around` has to be an ID to a message from the origin channel",
            )

        if quantity is not None:
            if quantity <= 0:
                if quantity == 0 and not after:
                    raise BotException(
                        "Invalid `quantity` argument",
                        "`quantity` must be above 0 when `after=` is not specified.",
                    )
                elif quantity != 0:
                    raise BotException(
                        "Invalid `quantity` argument",
                        "Quantity has to be a positive integer (or `0` when `after=` is specified).",
                    )
            elif quantity > common.BROWSE_MESSAGE_LIMIT:
                raise BotException(
                    "Too many messages",
                    f"{quantity} messages are more than the maximum allowed"
                    f" ({common.BROWSE_MESSAGE_LIMIT}).",
                )

        messages = [
            msg
            async for msg in channel.history(
                limit=quantity if quantity != 0 else None,
                before=before,
                after=after,
                around=around,
            )
        ]

        if not messages:
            raise BotException(
                "Invalid time range",
                "No messages were found for the specified timestamps.",
            )
        if len(messages) > common.BROWSE_MESSAGE_LIMIT:
            raise BotException(
                "Too many messages",
                f"{len(messages)} messages are more than the maximum allowed"
                f" ({common.BROWSE_MESSAGE_LIMIT}).",
            )

        if not after:
            messages.reverse()

        pages = []
        for message in messages:
            desc = message.system_content
            if desc is None:
                desc = message.content

            if message.embeds:
                if desc:
                    desc += f"\n\u200b\n"
                desc += "*Message contains an embed*"

            if message.attachments:
                if desc:
                    desc += f"\n\u200b\n"
                desc += "*Message has one or more attachments*"

            desc += "\n**━━━━━━━━━━━━**"

            if message.edited_at:
                desc += f"\n Last edited on {snakecore.utils.create_markdown_timestamp(message.edited_at)}"
            else:
                desc += f"\n Sent on {snakecore.utils.create_markdown_timestamp(message.created_at)}"

            if message.reference:
                desc += f"\nReplying to [this]({message.reference.jump_url}) message"

            desc += f"\nLink to [Original message]({message.jump_url})"
            desc += "\n**━━━━━━━━━━━━**"

            embed = snakecore.utils.embeds.create_embed(
                author_icon_url=message.author.display_avatar.url,
                author_name=message.author.display_name,
                description=desc,
                color=common.DEFAULT_EMBED_COLOR,
            )
            pages.append(embed)

        if controllers:
            controllers = controllers + (ctx.author,)
        else:
            controllers = ctx.author

        footer_text = f"Refresh this by replying with `{common.COMMAND_PREFIX}refresh`.\n___\ncmd: browse"

        raw_command_input: str = getattr(ctx, "raw_command_input", "")
        # attribute injected by snakecore's custom parser

        if raw_command_input:
            footer_text += f" | args: {raw_command_input}"

        msg_embeds = [
            snakecore.utils.embeds.create_embed(
                color=common.DEFAULT_EMBED_COLOR,
                footer_text=footer_text,
            )
        ]

        target_message = await response_message.edit(embeds=msg_embeds)

        paginator = snakecore.utils.pagination.EmbedPaginator(
            target_message,
            *pages,
            caller=controllers,
            whitelisted_role_ids=common.GuildConstants.ADMIN_ROLES,
            start_page_number=page,
            inactivity_timeout=60,
            theme_color=common.DEFAULT_EMBED_COLOR,
        )

        try:
            await paginator.mainloop()
        except discord.HTTPException:
            pass

    @commands.command()
    @admin_only_and_custom_parsing(inside_class=True, inject_message_reference=True)
    async def feature(
        self,
        ctx: commands.Context,
        name: str,
        *channels: discord.TextChannel,
        enable: bool = False,
        disable: bool = False,
    ):
        """
        ->type More admin commands
        ->signature pg!feature <name> [*channels] [enable=False] [disable=False]
        ->description Finer per-channel control of bot features

        ->extended description

        __Args__:
            `name: (str)`
            > The name of the feature

            `*channels: (discord.TextChannel)`
            > Series of channel mentions to apply the
            > settings to. If empty, applies the feature
            > to the current channel

            `enable: bool = False`
            > Bool that controls whether to enable the
            > feature or not Overrides `disable` if set to `True`.
            `False` by default

            `disable: bool = False`
            > Bool that controls whether to disable the
            > feature or not. `False` by default
        -----
        """

        response_message = common.recent_response_messages[ctx.message.id]

        if not channels:
            channels = (ctx.channel,)

        if enable or disable:
            async with snakecore.storage.DiscordStorage("feature") as storage_obj:
                storage_dict = storage_obj.obj
                if name not in storage_dict:
                    storage_dict[name] = {}

                for chan in channels:
                    storage_dict[name][chan.id] = enable or disable

                storage_obj.obj = storage_dict

        await snakecore.utils.embeds.replace_embed_at(
            response_message,
            title="Successfully executed command!",
            description=f"Changed settings on {len(channels)} channel(s)",
            color=common.DEFAULT_EMBED_COLOR,
        )

    @commands.group(invoke_without_command=True)
    async def admin_events(self, ctx: commands.Context):
        """
        ->type Events
        ->signature pg!admin_events
        ->description Command for keeping up with the events of the server
        -----
        """
        return await self.events_func(ctx)

    @admin_events.group(name="wc", invoke_without_command=True)
    @admin_only_and_custom_parsing(inside_class=True, inject_message_reference=True)
    async def admin_events_wc(
        self, ctx: commands.Context, round_no: Optional[int] = None
    ):
        """
        ->type Events
        ->signature pg!admin_events wc [round_no]
        ->description Show scoreboard of WC along with some info about the event
        ->extended description
        Argument `round_no` is an optional integer, that specifies which round
        of the event, the scoreboard should be displayed. If unspecified, shows
        the final scoreboard of all rounds combined.
        -----
        """
        return self.events_wc_func(ctx, round_no=round_no)

    @admin_events_wc.command(name="set")
    @admin_only_and_custom_parsing(inside_class=True, inject_message_reference=True)
    async def admin_events_wc_set(
        self,
        ctx: commands.Context,
        desc: Optional[String] = None,
        url: Optional[str] = None,
    ):
        """
        ->type Events
        ->signature pg!admin_events wc set [desc] [url]
        ->description Set the description for the WC
        -----
        """

        response_message = common.recent_response_messages[ctx.message.id]

        async with snakecore.storage.DiscordStorage("wc") as storage_obj:
            wc_dict = storage_obj.obj
            if desc is not None:
                wc_dict["description"] = desc.string if desc.string else None

            if url is not None:
                wc_dict["url"] = url if url else None

            storage_obj.obj = wc_dict

        await snakecore.utils.embeds.replace_embed_at(
            response_message,
            title="Successfully updated data!",
            description="Updated Weekly Challenges (WC) Event description and/or url!",
            color=common.DEFAULT_EMBED_COLOR,
        )

    @admin_events_wc.command(name="add")
    @admin_only_and_custom_parsing(inside_class=True, inject_message_reference=True)
    async def admin_events_wc_add(
        self, ctx: commands.Context, round_name: String, description: String
    ):
        """
        ->type Events
        ->signature pg!admin_events wc add <round_name> <description>
        ->description Adds a new WC event round
        -----
        """

        response_message = common.recent_response_messages[ctx.message.id]

        async with snakecore.storage.DiscordStorage("wc") as storage_obj:
            wc_dict = storage_obj.obj
            if "rounds" not in wc_dict:
                wc_dict["rounds"] = []

            wc_dict["rounds"].append(
                {
                    "name": round_name.string,
                    "description": description.string,
                    "scores": {},
                }
            )
            storage_obj.obj = wc_dict
            ind = len(wc_dict["rounds"])

        await snakecore.utils.embeds.replace_embed_at(
            response_message,
            title="Successfully updated events round!",
            description=f"Weekly Challenges got round {ind} - '{round_name.string}'!",
            color=common.DEFAULT_EMBED_COLOR,
        )

    @admin_events_wc.command(name="remove")
    @admin_only_and_custom_parsing(inside_class=True, inject_message_reference=True)
    async def events_wc_remove(self, ctx: commands.Context, round_no: int = 0):
        """
        ->type Events
        ->signature pg!admin_events wc remove [round_no]
        ->description Remove an event round
        -----
        """

        response_message = common.recent_response_messages[ctx.message.id]

        async with snakecore.storage.DiscordStorage("wc") as storage_obj:
            wc_dict = storage_obj.obj
            try:
                round_name = wc_dict["rounds"].pop(round_no - 1)["name"]

            except (IndexError, KeyError):
                raise BotException(
                    "Could not update events round!",
                    "The specified event round does not exist",
                )

            storage_obj.obj = wc_dict

        await snakecore.utils.embeds.replace_embed_at(
            response_message,
            title="Successfully updated events round!",
            description=(
                f"Removed round '{round_name}' from Weekly Challenges (WC) event!"
            ),
            color=common.DEFAULT_EMBED_COLOR,
        )

    @admin_events_wc.command(name="update")
    @admin_only_and_custom_parsing(inside_class=True, inject_message_reference=True)
    async def admin_events_wc_update(
        self,
        ctx: commands.Context,
        *name_and_scores: tuple[discord.Member, tuple[int, ...]],
        round_no: int = 0,
        round_name: Optional[String] = None,
        round_desc: Optional[String] = None,
    ):
        """
        ->type Events
        ->signature pg!admin_events wc update [*names_and_scores] [round_no] [round_name] [round_desc]
        ->description Update scoreboard challenge points
        ->extended description
        Argument `name_and_scores` can accept a variable number of member-score tuple pairs.
        Argument `round_no` is an integer that specifies the round of the event,
        defaults to the last round when empty
        Argument `round_name` is an optional string that can be specified to update the event name.
        Argument `round_desc` is an optional string that can be specified to update the event description.
        -----
        """

        response_message = common.recent_response_messages[ctx.message.id]

        round_no -= 1
        async with snakecore.storage.DiscordStorage("wc") as storage_obj:
            wc_dict = storage_obj.obj
            try:
                if round_name is not None:
                    wc_dict["rounds"][round_no]["name"] = round_name

                if round_desc is not None:
                    wc_dict["rounds"][round_no]["description"] = round_desc

                for mem, scores in name_and_scores:
                    if scores:
                        wc_dict["rounds"][round_no]["scores"][mem.id] = scores
                    else:
                        wc_dict["rounds"][round_no]["scores"].pop(mem.id)

                    total_score = sum(
                        sum(round_dict["scores"].get(mem.id, ()))
                        for round_dict in wc_dict["rounds"]
                    )
                    await pgbot.utils.give_wc_roles(mem, total_score)

            except IndexError:
                raise BotException(
                    "Could not update scoreboard!",
                    "The specified event round does not exist",
                ) from None

            storage_obj.obj = wc_dict

        await snakecore.utils.embeds.replace_embed_at(
            response_message,
            title="Successfully updated data!",
            description="The round related data or the scores have been updated!",
            color=common.DEFAULT_EMBED_COLOR,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCommandCog(bot))
