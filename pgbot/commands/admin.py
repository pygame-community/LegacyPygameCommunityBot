from __future__ import annotations

import asyncio
import os
import random
import sys
import time
from typing import Optional

import discord
import psutil
import pygame

from pgbot import common, embed_utils, utils
import datetime
from pgbot.commands.base import CodeBlock, String, BotException
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

    async def cmd_sync_db(self, name: str):
        """
        ->type Admin commands
        ->signature pg!sync_db [name]
        ->description sync 'db' messages between testbot and real bot
        ->extended description
        `pg!sync_db clock`
        `pg!sync_db command_blacklist`
        Are the available commands now
        -----
        Implement pg!sync_clocks, sync 'db' messages between testbot and real bot
        """
        db_channel = self.guild.get_channel(common.DB_CHANNEL_ID)

        if name == "clock":
            dest_msg_id = common.DB_CLOCK_MSG_IDS[common.TEST_MODE]
            src_msg_id = common.DB_CLOCK_MSG_IDS[not common.TEST_MODE]
        elif name == "command_blacklist":
            dest_msg_id = common.DB_BLACKLIST_MSG_IDS[common.TEST_MODE]
            src_msg_id = common.DB_BLACKLIST_MSG_IDS[not common.TEST_MODE]
        else:
            raise BotException("Invalid Name!", "")

        dest_msg = await db_channel.fetch_message(dest_msg_id)
        src_msg = await db_channel.fetch_message(src_msg_id)

        await dest_msg.edit(content=src_msg.content)
        await embed_utils.replace(
            self.response_msg,
            "DB messages synced!",
            "DB messages have been synced between both the bots"
        )

    async def cmd_whitelist_cmd(self, *cmds: str):
        """
        ->type Admin commands
        ->signature pg!whitelist_cmd [*cmds]
        ->description Whitelist commands
        -----
        Implement pg!whitelist_cmd, to whitelist commands
        """
        db_channel = self.guild.get_channel(common.DB_CHANNEL_ID)
        db_message = await db_channel.fetch_message(
            common.DB_BLACKLIST_MSG_IDS[common.TEST_MODE]
        )
        splits = db_message.content.split(":")
        commands = splits[1].strip().split(" ") if len(splits) == 2 else []

        cnt = 0
        for cmd in cmds:
            if cmd in commands:
                cnt += 1
                commands.remove(cmd)

        await db_message.edit(
            content="Blacklisted Commands: " + " ".join(commands)
        )

        await embed_utils.replace(
            self.response_msg,
            "Whitelisted!",
            f"Successfully whitelisted {cnt} command(s)"
        )

    async def cmd_blacklist_cmd(self, *cmds: str):
        """
        ->type Admin commands
        ->signature pg!blacklist_cmd [*cmds]
        ->description Blacklist commands
        -----
        Implement pg!blacklist_cmd, to blacklist commands
        """
        db_channel = self.guild.get_channel(common.DB_CHANNEL_ID)
        db_message = await db_channel.fetch_message(
            common.DB_BLACKLIST_MSG_IDS[common.TEST_MODE]
        )

        splits = db_message.content.split(":")
        commands = splits[1].strip().split(" ") if len(splits) == 2 else []

        cnt = 0
        for cmd in cmds:
            if cmd not in commands and cmd != "whitelist_cmd":
                cnt += 1
                commands.append(cmd)

        await db_message.edit(
            content="Blacklisted Commands: " + " ".join(commands)
        )

        await embed_utils.replace(
            self.response_msg,
            "Blacklisted!",
            f"Successfully blacklisted {cnt} command(s)"
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
                utils.code_block(repr(eval_output))
            )
        except Exception as ex:
            raise BotException(
                "An exception occured:",
                utils.code_block(
                    type(ex).__name__ + ": " + ", ".join(map(str, ex.args))
                )
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
        self,
        msg: discord.Message,
        attach: bool = False,
        stats: bool = False
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
                        color=0xFFFFAA
                    )
                )
            finally:
                if os.path.exists("messagedata.txt"):
                    os.remove("messagedata.txt")

        elif stats:
            stats_embed = embed_utils.get_info_embed(msg)
            stats_embed.set_author(name="Message data & stats")
            stats_embed.title = ""
            stats_embed.description = f"```\n{msg.content}```\n\u2800"
            await self.response_msg.channel.send(
                embed=stats_embed
            )

        else:
            await embed_utils.send_2(
                self.response_msg.channel,
                author_name="Message data",
                description="```\n{0}```".format(
                    msg.content.replace("```", "\\`\\`\\`")
                ),
                fields=(
                    (
                        "\u2800",
                        f"**[View Original Message]({msg.jump_url})**",
                        False
                    ),
                )
            )

        await self.response_msg.delete()

    async def cmd_sudo_clone(
        self,
        msg: discord.Message,
        embeds: bool = True,
        attach: bool = True,
        spoiler: bool = False,
        stats: bool = False,
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
            blank_filename = f"filetoolarge{time.perf_counter_ns()}.txt"
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
                content=msg.content,
                embed=msg.embeds[0],
                files=msg_files
            )

            for i in range(1, len(msg.embeds)):
                await self.response_msg.channel.send(
                    embed=msg.embeds[i],
                )
        else:
            cloned_msg = await self.response_msg.channel.send(
                content=msg.content,
                embed=msg.embeds[0] if msg.embeds and embeds else None,
                files=msg_files
            )

        if stats:
            await self.response_msg.channel.send(
                embed=embed_utils.get_info_embed(msg),
                reference=cloned_msg,
            )
        await self.response_msg.delete()

    async def cmd_sudo_stats(self, msg: discord.Message, author: bool = True):
        """
        ->type More admin commands
        ->signature pg!sudo_stats [message] [author_bool]
        ->description Get information about a message and its author

        Get information about a message and its author in an embed and send it to the channel where this command was invoked.
        -----
        Implement pg!sudo_stats, to get information about a message and its author.
        """

        await self.response_msg.channel.send(
            embed=embed_utils.get_msg_info_embed(msg, author=author)
        )
        await self.response_msg.delete()

    async def cmd_member_info(self, member: discord.Member):
        """
        ->type More admin commands
        ->signature pg!member_info [member]
        ->description Get information about a message and its author

        Get information about a member in an embed and send it to the channel where this command was invoked.
        -----
        Implement pg!member_info, to get information about a member.
        """

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
            f"**{utils.format_byte(mem, 4)}**\n({mem} B)"
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
            "Change da world,\nMy final message,\nGoodbye."
        )
        sys.exit(0)

    async def cmd_archive(
        self,
        origin: discord.TextChannel,
        quantity: int,
        destination: Optional[discord.TextChannel] = None,
    ):
        """
        ->type Admin commands
        ->signature pg!archive [origin channel] [quantity] [destination channel]
        ->description Archive messages to another channel
        -----
        Implement pg!archive, for admins to archive messages
        """

        if destination is None:
            destination = self.channel

        if origin == destination:
            raise BotException(
                "Cannot execute command:",
                "Origin and destination channels are same"
            )

        if quantity <= 0:
            raise BotException(
                "Invalid quantity argument",
                "Quantity has to be a positive integer",
            )

        datetime_format_str = f"%a, %d %b %y - %I:%M:%S %p"
        blank_filename = f"filetoolarge{time.perf_counter_ns()}.txt"

        await destination.trigger_typing()
        messages = await origin.history(limit=quantity).flatten()
        messages.reverse()

        try:
            with open(blank_filename, "w") as toolarge_txt:
                toolarge_txt.write("This file is too large to be archived.")

            if messages:
                start_date_str = messages[0].created_at.replace(
                    tzinfo=datetime.timezone.utc
                ).strftime(datetime_format_str)
                end_date_str = messages[-1].created_at.replace(
                    tzinfo=datetime.timezone.utc
                ).strftime(datetime_format_str)

                if start_date_str == end_date_str:
                    msg = f"On `{start_date_str}` (UTC)"
                else:
                    msg = f"From `{start_date_str}` to `{end_date_str}` (UTC)"

                await destination.send(
                    embed=embed_utils.create(
                        title=f"Archive of `#{origin.name}`",
                        description=msg,
                        color=0xffffff,
                    )
                )

            for msg in messages:
                msg_link = f"https://discord.com/channels/{msg.guild.id}/{msg.channel.id}/{msg.id}"
                author = msg.author
                await destination.trigger_typing()

                with open(blank_filename) as toolarge:
                    attached_files = [
                        (
                            await a.to_file(spoiler=a.is_spoiler())
                            if a.size <= common.GUILD_MAX_FILE_SIZE
                            else discord.File(toolarge)
                        )
                        for a in msg.attachments
                    ]

                await destination.send(
                    content="-" * 56,
                    embed=embed_utils.create(
                        description=f"{author.mention} (`{author.name}#{author.discriminator}`)\n"
                                    f"**[View Original]({msg_link})**",
                        color=0x36393F,
                        footer_text=f"\nID: {author.id}",
                        timestamp=msg.created_at.replace(
                            tzinfo=datetime.timezone.utc
                        ),
                        footer_icon_url=str(author.avatar_url),
                    ),
                    allowed_mentions=discord.AllowedMentions.none(),
                )
                await destination.trigger_typing()

                await destination.send(
                    content=msg.content,
                    embed=msg.embeds[0] if msg.embeds else None,
                    files=attached_files if attached_files else None,
                    allowed_mentions=discord.AllowedMentions.none(),
                )

                for i in range(1, len(msg.embeds)):
                    await destination.trigger_typing()
                    await destination.send(embed=msg.embeds[i])

                await destination.trigger_typing()

        finally:
            if os.path.exists(blank_filename):
                os.remove(blank_filename)

        await destination.send(content="-" * 56)
        await embed_utils.replace(
            self.response_msg,
            f"Successfully archived {len(messages)} message(s)!",
            ""
        )

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
