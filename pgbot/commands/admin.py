from __future__ import annotations

import asyncio
import datetime
import os
import sys
import time
from typing import Optional

import discord
import psutil
import pygame
from pgbot import common, embed_utils, utils, db
from pgbot.commands.base import BotException, CodeBlock, String
from pgbot.commands.emsudo import EmsudoCommand
from pgbot.commands.user import UserCommand

process = psutil.Process(os.getpid())


class AdminCommand(UserCommand, EmsudoCommand):
    """
    Base class for all admin commands
    """

    async def handle_cmd(self):
        """
        Temporary function, to divert paths for emsudo commands and other
        commands
        """
        if self.cmd_str.startswith("emsudo"):
            await EmsudoCommand.handle_cmd(self)
        else:
            await UserCommand.handle_cmd(self)

    async def cmd_whitelist_cmd(self, *cmds: str):
        """
        ->type Admin commands
        ->signature pg!whitelist_cmd [*cmds]
        ->description Whitelist commands
        -----
        Implement pg!whitelist_cmd, to whitelist commands
        """
        db_obj = db.DiscordDB("blacklist")
        commands = await db_obj.get([])
        cnt = 0
        for cmd in cmds:
            if cmd in commands:
                cnt += 1
                commands.remove(cmd)

        await db_obj.write(commands)

        await embed_utils.replace(
            self.response_msg,
            "Whitelisted!",
            f"Successfully whitelisted {cnt} command(s)",
        )

    async def cmd_blacklist_cmd(self, *cmds: str):
        """
        ->type Admin commands
        ->signature pg!blacklist_cmd [*cmds]
        ->description Blacklist commands
        -----
        Implement pg!blacklist_cmd, to blacklist commands
        """
        db_obj = db.DiscordDB("blacklist")
        commands = await db_obj.get([])

        cnt = 0
        for cmd in cmds:
            if cmd not in commands and cmd != "whitelist_cmd":
                cnt += 1
                commands.append(cmd)

        await db_obj.write(commands)

        await embed_utils.replace(
            self.response_msg,
            "Blacklisted!",
            f"Successfully blacklisted {cnt} command(s)",
        )

    async def cmd_clock(
        self,
        action: str = "",
        timezone: float = 0,
        color: Optional[pygame.Color] = None,
        member: Optional[discord.Member] = None,
    ):
        """
        ->type Admin commands
        ->signature pg!clock [action] [timezone] [color] [member]
        ->description 24 Hour Clock showing <@&778205389942030377> 's who are available to help
        ->extended description
        Admins can run clock with more arguments, to add/update/remove other members.
        `pg!clock update [timezone in hours] [color as hex string] [mention member]`
        `pg!clock remove [mention member]`
        -----
        Implement pg!clock, to display a clock of helpfulies/mods/wizards
        """
        return await super().cmd_clock(action, timezone, color, member)

    async def cmd_eval(self, code: CodeBlock):
        """
        ->type Admin commands
        ->signature pg!eval [command]
        ->description Execute a line of command without restrictions
        -----
        Implement pg!eval, for admins to run arbitrary code on the bot
        """
        try:
            script = compile(code.code, "<string>", "eval")  # compile script

            script_start = time.perf_counter()
            eval_output = eval(script)  # pylint: disable = eval-used
            total = time.perf_counter() - script_start

            await embed_utils.replace(
                self.response_msg,
                f"Return output (code executed in {utils.format_time(total)}):",
                utils.code_block(repr(eval_output)),
            )
        except Exception as ex:
            raise BotException(
                "An exception occured:",
                utils.code_block(
                    type(ex).__name__ + ": " + ", ".join(map(str, ex.args))
                ),
            )

    async def cmd_sudo(self, msg: String):
        """
        ->type More admin commands
        ->signature pg!sudo [message]
        ->description Send a message trough the bot
        -----
        Implement pg!sudo, for admins to send messages via the bot
        """
        await self.channel.send(msg.string)
        await self.response_msg.delete()
        await self.invoke_msg.delete()

    async def cmd_sudo_edit(self, edit_msg: discord.Message, msg: String):
        """
        ->type More admin commands
        ->signature pg!sudo_edit [edit_message] [message string]
        ->description Edit a message that the bot sent.
        -----
        Implement pg!sudo_edit, for admins to edit messages via the bot
        """
        await edit_msg.edit(content=msg.string)
        await self.response_msg.delete()
        await self.invoke_msg.delete()

    async def cmd_sudo_get(
        self, msg: discord.Message, attach: bool = False, info: bool = False
    ):
        """
        ->type More admin commands
        ->signature pg!sudo_get [message] [attach] [stats]
        ->description Get the text of a message through the bot

        Get the contents of the embed of a message from the given arguments and send it as another message
        (as an embed code block or a message with a `.txt` file attachment containing the message data)
        to the channel where this command was invoked.
        -----
        Implement pg!sudo_get, to return the the contents of a message as an embed or in a text file.
        """
        if attach:
            try:
                with open("messagedata.txt", "w", encoding="utf-8") as msg_txt:
                    msg_txt.write(msg.content)

                await self.response_msg.channel.send(
                    file=discord.File("messagedata.txt"),
                    embed=await embed_utils.send_2(
                        None,
                        author_name="Message data",
                        description=f"**[View Original Message]({msg.jump_url})**",
                        color=0xFFFFAA,
                    ),
                )
            finally:
                if os.path.exists("messagedata.txt"):
                    os.remove("messagedata.txt")

        elif info:
            info_embed = embed_utils.get_msg_info_embed(msg)
            info_embed.set_author(name="Message data & info")
            info_embed.title = ""
            info_embed.description = f"```\n{msg.content}```\n\u2800"
            await self.response_msg.channel.send(embed=info_embed)

        else:
            await embed_utils.send_2(
                self.response_msg.channel,
                author_name="Message data",
                description="```\n{0}```".format(
                    msg.content.replace("```", "\\`\\`\\`")
                ),
                fields=(
                    ("\u2800",
                     f"**[View Original Message]({msg.jump_url})**", False),
                ),
            )

        await self.response_msg.delete()

    async def cmd_sudo_clone(
        self,
        msg: discord.Message,
        embeds: bool = True,
        attach: bool = True,
        spoiler: bool = False,
        info: bool = False,
        author: bool = True,
    ):
        """
        ->type More admin commands
        ->signature pg!sudo_clone [message] [embeds] [attach] [spoiler] [stats]
        ->description Clone a message through the bot

        Get a message from the given arguments and send it as another message to the channel where this command was invoked.
        -----
        Implement pg!sudo_clone, to get the content of a message and send it.
        """

        msg_files = None
        cloned_msg = None

        if msg.attachments and attach:
            blank_filename = f"filetoolarge {int(time.perf_counter_ns())}.txt"
            try:
                with open(blank_filename, "w", encoding="utf-8") as toolarge:
                    toolarge.write("This file is too large to be archived.")

                    msg_files = [
                        await a.to_file(spoiler=spoiler or a.is_spoiler())
                        if a.size <= common.GUILD_MAX_FILE_SIZE
                        else discord.File(toolarge)
                        for a in msg.attachments
                    ]

            finally:
                if os.path.exists(blank_filename):
                    os.remove(blank_filename)

        if msg.embeds and embeds:
            cloned_msg = await self.response_msg.channel.send(
                content=msg.content, embed=msg.embeds[0], files=msg_files
            )

            for i in range(1, len(msg.embeds)):
                await self.response_msg.channel.send(
                    embed=msg.embeds[i],
                )
        else:
            cloned_msg = await self.response_msg.channel.send(
                content=msg.content,
                embed=msg.embeds[0] if msg.embeds and embeds else None,
                files=msg_files,
            )

        if info:
            await self.response_msg.channel.send(
                embed=embed_utils.get_msg_info_embed(msg, author=author),
                reference=cloned_msg,
            )
        await self.response_msg.delete()

    async def cmd_sudo_info(self, msg: discord.Message, author: bool = True):
        """
        ->type More admin commands
        ->signature pg!sudo_info [message] [author_bool]
        ->description Get information about a message and its author

        Get information about a message and its author in an embed and send it to the channel where this command was invoked.
        -----
        Implement pg!sudo_info, to get information about a message and its author.
        """

        await self.response_msg.channel.send(
            embed=embed_utils.get_msg_info_embed(msg, author=author)
        )
        await self.response_msg.delete()

    async def cmd_member_info(self, member: Optional[discord.Member] = None):
        """
        ->type More admin commands
        ->signature pg!member_info [member]
        ->description Get information about a message and its author

        Get information about a member in an embed and send it to the channel where this command was invoked.
        -----
        Implement pg!member_info, to get information about a member.
        """
        if member is None:
            member = self.author

        await self.response_msg.channel.send(
            embed=embed_utils.get_user_info_embed(member)
        )
        await self.response_msg.delete()

    async def cmd_heap(self):
        """
        ->type Admin commands
        ->signature pg!heap
        ->description Show the memory usage of the bot
        -----
        Implement pg!heap, for admins to check memory taken up by the bot
        """
        mem = process.memory_info().rss
        await embed_utils.replace(
            self.response_msg,
            "Total memory used:",
            f"**{utils.format_byte(mem, 4)}**\n({mem} B)",
        )

    async def cmd_stop(self):
        """
        ->type Admin commands
        ->signature pg!stop
        ->description Stop the bot
        -----
        Implement pg!stop, for admins to stop the bot
        """
        await embed_utils.replace(
            self.response_msg,
            "Stopping bot...",
            "Change da world,\nMy final message,\nGoodbye.",
        )
        sys.exit(0)

    async def cmd_archive(
        self,
        origin: discord.TextChannel,
        quantity: int,
        destination: Optional[discord.TextChannel] = None,
        before: String = String(""),
        before_msg: int = 0,
        after: String = String(""),
        after_msg: int = 0,
        around: String = String(""),
        around_msg: int = 0,
        raw: bool = False,
        show_header: bool = True,
        show_author: bool = True,
        divider_str: String = String("-" * 56),
        group_by_author: bool = True,
        oldest_first: bool = True,
        same_channel: bool = False,
    ):
        """
        ->type Admin commands
        ->signature pg!archive [origin channel] [quantity] [destination channel]
[before=""] [before_msg=0] [after=""] [after_msg=0] [around=""] [around_msg=0]
[raw=False] [show_header=True] [show_author=True] [divider_str=("-"*56)]
[group_by_author=True] [oldest_first=True] [same_channel=False]
        ->description Archive messages to another channel
        -----
        Implement pg!archive, for admins to archive messages
        """

        archive_header_msg = None
        archive_header_msg_embed = None

        if destination is None:
            destination = self.channel

        if origin == destination and not same_channel:
            raise BotException(
                "Cannot execute command:", "Origin and destination channels are same"
            )

        tz_utc = datetime.timezone.utc
        datetime_format_str = f"%a, %d %b %Y - %H:%M:%S (UTC)"
        blank_filename = f"filetoolarge {int(time.perf_counter_ns())}.txt"

        divider_str = divider_str.string
        before = before.string.strip()
        after = after.string.strip()
        around = around.string.strip()

        parsed_before = None
        parsed_after = None
        parsed_around = None

        if before:
            try:
                if before.endswith("Z"):
                    before = before[:-1]
                parsed_before = datetime.datetime.fromisoformat(before)
            except ValueError:
                raise BotException(
                    "Invalid `before` argument",
                    "`before` has to be a timestamp in the ISO format.",
                )
        elif before_msg:
            try:
                parsed_before = await origin.fetch_message(before_msg)
            except discord.NotFound:
                raise BotException(
                    "Invalid `before_msg` argument",
                    "`before_msg` has to be an ID to a message from the origin channel",
                )

        if after:
            try:
                if after.endswith("Z"):
                    after = after[:-1]
                parsed_after = datetime.datetime.fromisoformat(after)
            except ValueError:
                raise BotException(
                    "Invalid `after` argument",
                    "`after` has to be a timestamp in the ISO format.",
                )
        elif after_msg:
            try:
                parsed_after = await origin.fetch_message(after_msg)
            except discord.NotFound:
                raise BotException(
                    "Invalid `after_msg` argument",
                    "`after_msg` has to be an ID to a message from the origin channel",
                )

        if around:
            try:
                if around.endswith("Z"):
                    around = around[:-1]
                parsed_around = datetime.datetime.fromisoformat(around)
            except ValueError:
                raise BotException(
                    "Invalid `around` argument",
                    "`around has to be a timestamp in the ISO format.",
                )
        elif around_msg:
            try:
                parsed_around = await origin.fetch_message(around_msg)
            except discord.NotFound:
                raise BotException(
                    "Invalid `around_msg` argument",
                    "`around_msg` has to be an ID to a message from the origin channel",
                )

            if quantity > 101:
                raise BotException(
                    "Invalid `quantity` argument",
                    "`quantity` must be an integer below 102 when `around` is specified.",
                )

        if quantity <= 0:
            if quantity == -1 and not parsed_after:
                raise BotException(
                    "Invalid `quantity` argument",
                    "`quantity` must be above -1 when `after=` is not specified.",
                )
            elif quantity != -1:
                raise BotException(
                    "Invalid `quantity` argument",
                    "Quantity has to be a positive integer (or `-1` when `after=` is specified).",
                )

        await destination.trigger_typing()
        messages = await origin.history(
            limit=quantity if quantity != -1 else None,
            before=parsed_before,
            after=parsed_after,
            around=parsed_around,
        ).flatten()

        if not messages:
            raise BotException(
                "Invalid time range",
                "No messages were found for the specified timestamps.",
            )

        if (not after and not after_msg) and oldest_first:
            messages.reverse()

        with open(blank_filename, "w") as toolarge_txt:
            toolarge_txt.write("This file is too large to be archived.")

        if show_header and not raw:
            start_date = messages[0].created_at.replace(tzinfo=None)
            end_date = messages[-1].created_at.replace(tzinfo=None)
            start_date_str = start_date.strftime(datetime_format_str)
            end_date_str = end_date.strftime(datetime_format_str)

            if start_date == end_date:
                msg = f"On `{start_date_str} | {start_date.isoformat()}`"
            else:
                msg = (
                    f"From\n> `{start_date_str} | {start_date.isoformat()}`\n"
                    + f"to\n> `{end_date_str} | {end_date.isoformat()}`"
                )

            archive_header_msg_embed = embed_utils.create(
                title=f"__Archive of `#{origin.name}`__",
                description=f"\nAn Archive of **{origin.mention}**"
                f" ( {len(messages)} message(s))\n\n" + msg,
                color=0xFFFFFF,
                footer_text="Status: Incomplete"
            )

            archive_header_msg = await destination.send(embed=archive_header_msg_embed)

        no_mentions = discord.AllowedMentions.none()
        try:
            for i, msg in enumerate(
                reversed(messages) if not oldest_first else messages
            ):
                author = msg.author
                await destination.trigger_typing()

                attached_files = [
                    (
                        await a.to_file(spoiler=a.is_spoiler())
                        if a.size <= common.GUILD_MAX_FILE_SIZE
                        else discord.File(blank_filename)
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
                        ):
                            # no author info or divider for mesmages next to each other sharing an author
                            current_divider_str = None
                        else:
                            author_embed = embed_utils.create(
                                description=f"{author.mention}"
                                f" (`{author.name}#{author.discriminator}`)\n"
                                f"**[View Original]({msg.jump_url})**",
                                color=0x36393F,
                                footer_text="\nISO Time: "
                                f"{msg.created_at.replace(tzinfo=None).isoformat()}"
                                f"\nID: {author.id}",
                                timestamp=msg.created_at.replace(tzinfo=tz_utc),
                                footer_icon_url=str(author.avatar_url),
                            )

                        if author_embed or current_divider_str:
                            await destination.send(
                                content=current_divider_str,
                                embed=author_embed,
                                allowed_mentions=no_mentions,
                            )

                await destination.trigger_typing()

                await destination.send(
                    content=msg.content,
                    embed=msg.embeds[0] if msg.embeds else None,
                    files=attached_files if attached_files else None,
                    allowed_mentions=no_mentions,
                )

                for i in range(1, len(msg.embeds)):
                    await destination.trigger_typing()
                    await destination.send(embed=msg.embeds[i])

                await destination.trigger_typing()

        finally:
            if os.path.exists(blank_filename):
                os.remove(blank_filename)

        if divider_str and not raw:
            await destination.send(content=divider_str)

        await embed_utils.replace(
            self.response_msg, f"Successfully archived {len(messages)} message(s)!", ""
        )

        if show_header and not raw:
            archive_header_msg_embed.set_footer(text="Status: Completed")
            await embed_utils.replace_from_dict(
                archive_header_msg, archive_header_msg_embed.to_dict()
            )
        await self.response_msg.delete(delay=5.0)

    async def cmd_poll(
        self,
        desc: String,
        *emojis: String,
        author: Optional[String] = None,
        color: Optional[pygame.Color] = None,
        url: Optional[String] = None,
        img_url: Optional[String] = None,
        thumbnail: Optional[String] = None,
    ):
        """
        ->type Admin commands
        ->signature pg!poll [description] [*args] [author] [color] [url] [image_url] [thumbnail]
        ->description Start a poll.
        ->extended description
        The args must be strings with one emoji and one description of said emoji (see example command). \
        The emoji must be a default emoji or one from this server. To close the poll see pg!close_poll.
        Additionally admins can specify some keyword arguments to improve the appearance of the poll
        ->example command pg!poll "Which apple is better?" "🍎" "Red apple" "🍏" "Green apple"
        """
        embed_dict = {}
        if author:
            embed_dict["author"] = {"name": author.string}

        if color:
            embed_dict["color"] = utils.color_to_rgb_int(color)

        if url:
            embed_dict["url"] = url.string

        if img_url:
            embed_dict["image"] = {"url": img_url.string}

        if thumbnail:
            embed_dict["thumbnail"] = {"url": thumbnail.string}

        return await super().cmd_poll(desc, *emojis, admin_embed=embed_dict)

    async def cmd_close_poll(
        self,
        msg: discord.Message,
        color: pygame.Color = pygame.Color("#A83232"),
    ):
        """
        ->type Admin commands
        ->signature pg!close_poll [message] [color]
        ->description Close an ongoing poll.
        ->extended description
        The poll can only be closed by the person who started it or by mods.
        The color is the color of the closed poll embed
        """
        return await super().cmd_close_poll(msg, color)
