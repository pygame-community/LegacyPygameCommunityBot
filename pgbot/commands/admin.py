from __future__ import annotations

import os
import sys
import time

import discord
import psutil

from pgbot import common, embed_utils, utils
from pgbot.commands.base import CodeBlock, String, MentionableID
from pgbot.commands.user import UserCommand
from pgbot.commands.emsudo import EmsudoCommand

process = psutil.Process(os.getpid())


class AdminCommand(UserCommand, EmsudoCommand):
    async def handle_cmd(self):
        """
        Temporary function, to divert paths for emsudo commands and other
        commands
        """
        if self.cmd_str.startswith("emsudo"):
            await EmsudoCommand.handle_cmd(self)
        else:
            await UserCommand.handle_cmd(self)

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

    async def cmd_sudo_edit(self, msg_id: MentionableID, msg: String):
        """
        ->type More admin commands
        ->signature pg!sudo_edit [msg_id] [message]
        ->description Edit a message that the bot sent.
        -----
        Implement pg!sudo_edit, for admins to edit messages via the bot
        """

        edit_msg = await self.invoke_msg.channel.fetch_message(msg_id.id)
        await edit_msg.edit(content=msg.string)
        await self.response_msg.delete()
        await self.invoke_msg.delete()

    async def cmd_sudo_get(
        self,
        msg_id: MentionableID,
        channel_id: MentionableID = None,
        attach: bool = False,
    ):
        """
        ->type More admin commands
        ->signature pg!sudo_get [msg_id] [channel_id] [attach]
        ->description Get the text of a message through the bot

        Get the contents of the embed of a message from the given arguments and send it as another message
        (as an embed code block or a message with a `.txt` file attachment containing the message data)
        to the channel where this command was invoked.
        -----
        Implement pg!sudo_get, to return the the contents of a message in a text file.
        """
        channel = self.invoke_msg.channel if channel_id is None else \
            self.invoke_msg.guild.get_channel(channel_id.id)

        if channel is None:
            await embed_utils.replace(
                self.response_msg,
                "Cannot execute command:",
                "Invalid channel id!"
            )
            return

        try:
            msg = await channel.fetch_message(msg_id.id)
        except discord.NotFound:
            await embed_utils.replace(
                self.response_msg,
                "Cannot execute command:",
                "Invalid message id!"
            )
            return

        msg_link = f"https://discord.com/channels/{msg.guild.id}/{channel.id}/{msg.id}"
        if attach:
            try:
                with open("messagedata.txt", "w", encoding="utf-8") as msg_txt:
                    msg_txt.write(msg.content)

                await self.response_msg.channel.send(
                    file=discord.File("messagedata.txt"),
                    embed=await embed_utils.send_2(
                        None,
                        author_name="Message data",
                        description=f"**[View Original]({msg_link})**",
                        color=0xFFFFAA
                    )
                )
            finally:
                if os.path.exists("messagedata.txt"):
                    os.remove("messagedata.txt")
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
                        f"**[View Original]({msg_link})**",
                        False
                    ),
                )
            )
        await self.response_msg.delete()

    async def cmd_sudo_clone(
        self,
        msg_id: MentionableID,
        channel_id: MentionableID = None,
        embeds: bool = True,
        attach: bool = True,
        spoiler: bool = False,
    ):
        """
        ->type More admin commands
        ->signature pg!sudo_clone [msg_id] [channel_id] [embeds] [attach] [spoiler]
        ->description Clone a message through the bot

        Get a message from the given arguments and send it as another message to the channel where this command was invoked.
        -----
        Implement pg!sudo_clone, to get the content of a message and send it.
        """
        channel = self.invoke_msg.channel if channel_id is None else \
            self.invoke_msg.guild.get_channel(channel_id.id)

        if channel is None:
            await embed_utils.replace(
                self.response_msg,
                "Cannot execute command:",
                "Invalid channel id!"
            )
            return

        try:
            msg = await channel.fetch_message(msg_id.id)
        except discord.NotFound:
            await embed_utils.replace(
                self.response_msg,
                "Cannot execute command:",
                "Invalid message id!"
            )
            return

        msg_files = None
        if msg.attachments and attach:
            msg_files = [await a.to_file(spoiler=spoiler) for a in msg.attachments]

        await self.response_msg.channel.send(
            content=msg.content,
            embed=msg.embeds[0] if msg.embeds and embeds else None,
            files=msg_files
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
        origin: MentionableID,
        quantity: int,
        destination: MentionableID = None,
    ):
        """
        ->type Admin commands
        ->signature pg!archive [origin] [quantity] [destination]
        ->description Archive messages to another channel
        -----
        Implement pg!archive, for admins to archive messages
        """

        origin_channel = None
        destination_channel = None

        if destination is None:
            destination = MentionableID("0")
            destination.id = self.invoke_msg.channel.id

        if destination.id == origin.id:
            await embed_utils.replace(
                self.response_msg,
                "Cannot execute command:",
                "Origin and destination channels are same"
            )
            return

        for channel in common.bot.get_all_channels():
            if channel.id == origin.id:
                origin_channel = channel
            if channel.id == destination.id:
                destination_channel = channel

        if not origin_channel:
            await embed_utils.replace(
                self.response_msg,
                "Cannot execute command:",
                "Invalid origin channel!"
            )
            return

        elif not destination_channel:
            await embed_utils.replace(
                self.response_msg,
                "Cannot execute command:",
                "Invalid destination channel!"
            )
            return

        messages = await origin_channel.history(limit=quantity).flatten()
        messages.reverse()
        message_list = await utils.format_archive_messages(messages)

        archive_str = f"+{'=' * 40}+\n" + \
            f"+{'=' * 40}+\n".join(message_list) + f"+{'=' * 40}+\n"
        archive_list = utils.split_long_message(archive_str)

        for message in archive_list:
            await destination_channel.send(message)

        await embed_utils.replace(
            self.response_msg,
            f"Successfully archived {len(messages)} message(s)!",
            ""
        )
