import os
import sys
import time

import discord
import psutil

from . import user_commands, clock, common, util

process = psutil.Process(os.getpid())


class AdminCommand(user_commands.UserCommand):
    """
    Base class to handle admin commands. Inherits all user commands, and also
    implements some more
    """
    async def cmd_eval(self):
        try:
            script = compile(
                self.string, "<string>", "eval"
            )  # compile script first

            script_start = time.perf_counter()
            eval_output = eval(script)  # pylint: disable = eval-used
            script_duration = time.perf_counter() - script_start

            enhanced_eval_output = repr(eval_output).replace(
                "```", common.ESC_CODE_BLOCK_QUOTE
            )

            if len(enhanced_eval_output) + 11 > 2048:
                await util.edit_embed(
                    self.response_msg,
                    f"Return output (code executed in {util.format_time(script_duration)}):",
                    "```\n" + enhanced_eval_output[:2037] + " ...```",
                )
            else:
                await util.edit_embed(
                    self.response_msg,
                    f"Return output (code executed in {util.format_time(script_duration)}):",
                    "```\n" + enhanced_eval_output + "```",
                )
        except Exception as ex:
            exp = (
                    type(ex).__name__.replace("```", common.ESC_CODE_BLOCK_QUOTE)
                    + ": "
                    + ", ".join(str(t) for t in ex.args).replace(
                "```", common.ESC_CODE_BLOCK_QUOTE
            )
            )

            if len(exp) + 11 > 2048:
                await util.edit_embed(
                    self.response_msg,
                    common.EXP_TITLES[1],
                    "```\n" + exp[:2037] + " ...```",
                )
            else:
                await util.edit_embed(
                    self.response_msg, common.EXP_TITLES[1], "```\n" + exp + "```"
                )

    async def cmd_sudo(self):
        await self.invoke_msg.channel.send(self.string)
        await self.response_msg.delete()
        await self.invoke_msg.delete()

    async def cmd_sudo_edit(self):
        edit_msg = await self.invoke_msg.channel.fetch_message(
            util.filter_id(self.args[0])
        )
        await edit_msg.edit(content=self.string[self.string.find(self.args[1]):])
        await self.response_msg.delete()
        await self.invoke_msg.delete()

    async def cmd_heap(self):
        self.check_args(0)
        mem = process.memory_info().rss
        await util.edit_embed(
            self.response_msg,
            "Total memory used:",
            f"**{util.format_byte(mem, 4)}**\n({mem} B)"
        )

    async def cmd_stop(self):
        self.check_args(0)
        await util.edit_embed(
            self.response_msg,
            "Stopping bot...",
            "Change da world,\nMy final message,\nGoodbye."
        )
        sys.exit(0)

    async def cmd_emsudo(self):
        args = eval(self.string)

        if len(args) == 1:
            await util.send_embed(
                self.invoke_msg.channel,
                args[0],
                ""
            )
        elif len(args) == 2:
            await util.send_embed(
                self.invoke_msg.channel,
                args[0],
                args[1]
            )
        elif len(args) == 3:
            await util.send_embed(
                self.invoke_msg.channel,
                args[0],
                args[1],
                args[2]
            )
        elif len(args) == 4:
            await util.send_embed(
                self.invoke_msg.channel,
                args[0],
                args[1],
                args[2],
                args[3]
            )

        await self.response_msg.delete()
        await self.invoke_msg.delete()

    async def cmd_emsudo_edit(self):
        args = eval(self.string)
        edit_msg = await self.invoke_msg.channel.fetch_message(
            util.filter_id(args[0])
        )

        if len(args) == 2:
            await util.edit_embed(
                edit_msg,
                args[1],
                ""
            )
        elif len(args) == 3:
            await util.edit_embed(
                edit_msg,
                args[1],
                args[2]
            )
        elif len(args) == 4:
            await util.edit_embed(
                edit_msg,
                args[1],
                args[2],
                args[3]
            )
        elif len(args) == 5:
            await util.edit_embed(
                edit_msg,
                args[1],
                args[2],
                args[3],
                args[4]
            )

        await self.response_msg.delete()
        await self.invoke_msg.delete()

    async def cmd_archive(self):
        self.check_args(3)
        origin = int(util.filter_id(self.args[0]))
        quantity = int(self.args[1])
        destination = int(util.filter_id(self.args[2]))

        origin_channel = None
        destination_channel = None

        for channel in common.bot.get_all_channels():
            if channel.id == origin:
                origin_channel = channel
            if channel.id == destination:
                destination_channel = channel

        if not origin_channel:
            await util.edit_embed(
                self.response_msg,
                "Cannot execute command:",
                "Invalid origin channel!"
            )
            return
        elif not destination_channel:
            await util.edit_embed(
                self.response_msg,
                "Cannot execute command:",
                "Invalid destination channel!"
            )
            return

        messages = await origin_channel.history(limit=quantity).flatten()
        messages.reverse()
        message_list = await util.format_archive_messages(messages)

        archive_str = f"+{'=' * 40}+\n" + f"+{'=' * 40}+\n".join(message_list) + f"+{'=' * 40}+\n"
        archive_list = util.split_long_message(archive_str)

        for message in archive_list:
            await destination_channel.send(message)

        await util.edit_embed(
            self.response_msg,
            f"Successfully archived {len(messages)} message(s)!",
            ""
        )
