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
from pgbot.commands.base import CodeBlock, String
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

    async def cmd_sync_clocks(self):
        """
        ->type Admin commands
        ->signature pg!sync_clocks
        ->description sync test clock and real clock
        -----
        Implement pg!sync_clocks, to sync clock data between clocks
        """
        db_channel = self.invoke_msg.guild.get_channel(common.DB_CHANNEL_ID)

        dest_msg_id = common.DB_CLOCK_MSG_IDS[common.TEST_MODE]
        dest_msg = await db_channel.fetch_message(dest_msg_id)

        src_msg_id = common.DB_CLOCK_MSG_IDS[not common.TEST_MODE]
        src_msg = await db_channel.fetch_message(src_msg_id)

        await dest_msg.edit(content=src_msg.content)
        await embed_utils.replace(
            self.response_msg,
            "Clocks synced!",
            "Test clock and main clock have been synced"
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
        ->signature pg!clock
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
            await embed_utils.replace(
                self.response_msg,
                common.EXC_TITLES[1],
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
        await self.invoke_msg.channel.send(msg.string)
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

    async def cmd_sudo_get(self, msg: discord.Message, attach: bool = False, stats: bool = False):
        """
        ->type More admin commands
        ->signature pg!sudo_get [message] [bool attach] [bool stats]
        ->description Get the text of a message through the bot

        Get the contents of the embed of a message from the given arguments and send it as another message
        (as an embed code block or a message with a `.txt` file attachment containing the message data)
        to the channel where this command was invoked.
        -----
        Implement pg!sudo_get, to return the the contents of a message as an embed or in a text file.
        """
        msg_link = "https://discord.com/channels/"
        msg_link += f"{msg.guild.id}/{msg.channel.id}/{msg.id}"
        if attach:
            try:
                with open("messagedata.txt", "w", encoding="utf-8") as msg_txt:
                    msg_txt.write(msg.content)

                await self.response_msg.channel.send(
                    file=discord.File("messagedata.txt"),
                    embed=await embed_utils.send_2(
                        None,
                        author_name="Message data",
                        description=f"**[View Original Message]({msg_link})**",
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
                        f"**[View Original Message]({msg_link})**",
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
            blank_filename = f"filetoolarge {time.perf_counter_ns()*random.random()}.txt"
            with open(blank_filename, "w", encoding="utf-8") as toolarge_txt:
                toolarge_txt.write("This file is too large to be archived.")

            blank_file = discord.File(blank_filename)
            msg_files = [
                await a.to_file(spoiler=spoiler or a.is_spoiler()) if a.size <= common.GUILD_MAX_FILE_SIZE \
                else blank_file for a in msg.attachments
            ]

            if os.path.exists(blank_filename):
                try:
                    os.remove(blank_filename)
                except PermissionError:
                    pass     

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

    async def cmd_sudo_stats(self, msg: discord.Message):
        """
        ->type More admin commands
        ->signature pg!sudo_stats [message]
        ->description Get information about a message and its author

        Get information about a message and its author in an embed and send it to the channel where this command was invoked.
        -----
        Implement pg!sudo_stats, to get information about a message and its author.
        """

        await self.response_msg.channel.send(
            embed=embed_utils.get_info_embed(msg)
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
            destination = self.invoke_msg.channel

        if origin == destination:
            await embed_utils.replace(
                self.response_msg,
                "Cannot execute command:",
                "Origin and destination channels are same"
            )
            return

        messages = await origin.history(limit=quantity).flatten()
        messages.reverse()
        msg: discord.Message = None
        datetime_format_str = f"%a, %d %b %y - %I:%M:%S %p"

        no_mentions = discord.AllowedMentions.none()

        blank_filename = f"filetoolarge {time.perf_counter_ns()*random.random()}.txt"

        with open(blank_filename, "w", encoding="utf-8") as toolarge_txt:
            toolarge_txt.write("This file is too large to be archived.")
        
        blank_file = discord.File(blank_filename)
        
        if len(messages) > 1:
            start_date_str = messages[0].created_at.replace(tzinfo=datetime.timezone.utc)\
                            .strftime(datetime_format_str)
            end_date_str = messages[-1].created_at.replace(tzinfo=datetime.timezone.utc)\
                            .strftime(datetime_format_str)

            await destination.send(
                embed=embed_utils.create(
                    title=f"Archive of `#{origin.name}`",
                    description=f"From `{start_date_str}` to `{end_date_str}` (UTC)",
                    color=0xffffff,
                )
            )
        
        async with destination.typing():
            for msg in messages:
                author = msg.author
                attached_files = [
                    (await a.to_file(spoiler=a.is_spoiler()) if a.size <= common.GUILD_MAX_FILE_SIZE \
                    else blank_file) for a in msg.attachments
                ]
                
                await destination.send(content="-"*56)
                await destination.send(
                    embed=embed_utils.create(
                        description=f"{author.mention} (`{author.name}#{author.discriminator}`)",
                        color=0x36393F,
                        footer_text=f"\nID: {author.id}",
                        timestamp=msg.created_at.replace(tzinfo=datetime.timezone.utc),
                        footer_icon_url=str(author.avatar_url),
                    ),
                    allowed_mentions=no_mentions,
                )

                await destination.send(
                    content=msg.content,
                    embed=msg.embeds[0] if msg.embeds else None,
                    files=attached_files if attached_files else None,
                    allowed_mentions=no_mentions,
                )

                for i in range(1, len(msg.embeds)):
                    await destination.send(embed=msg.embeds[i])

                async with destination.typing():
                    await asyncio.sleep(0.05)

        if os.path.exists(blank_filename):
            try:
                os.remove(blank_filename)
            except PermissionError:
                pass  

        await embed_utils.replace(
            self.response_msg,
            f"Successfully archived {len(messages)} message(s)!",
            ""
        )

    async def cmd_poll(self, desc: String, *emojis: String, **kwargs):
        """
        ->type Other commands
        ->signature pg!poll [*args]
        ->description Start a poll.
        ->extended description
        `pg!poll description *args`
        The args must be strings with one emoji and one description of said emoji (see example command). \
        The emoji must be a default emoji or one from this server. To close the poll see pg!close_poll.
        ->example command pg!poll "Which apple is better?" "🍎" "Red apple" "🍏" "Green apple"
        """
        return await super().cmd_poll(desc, *emojis, is_admin=True, **kwargs)

    async def cmd_close_poll(self, msg: discord.Message, color:str=None):
        """
        ->type Other commands
        ->signature pg!close_poll [msg_id]
        ->description Close an ongoing poll.
        ->extended description
        The poll can only be closed by the person who started it or by mods.
        """
        return await super().cmd_close_poll(msg, is_admin=True, color=color)
