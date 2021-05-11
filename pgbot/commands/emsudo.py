from __future__ import annotations

import os
import sys
import time
import traceback
from datetime import datetime

import black
import discord
import psutil
from discord.embeds import EmptyEmbed

from pgbot import embed_utils
from pgbot.commands.base import OldBaseCommand, CodeBlock

process = psutil.Process(os.getpid())


class EmsudoCommand(OldBaseCommand):
    """
    Base class to handle emsudo commands. Uses old command handler, needs porting
    """

    async def cmd_emsudo_c(self):
        """
        ->type More admin commands
        ->signature pg!emsudo_c [*args]
        ->description Send an embed trough the bot
        -----
        Implement pg!emsudo_c, for admins to send embeds via the bot
        """
        try:
            args = eval(CodeBlock(self.string).code)
        except Exception as e:
            tbs = traceback.format_exception(type(e), e, e.__traceback__)
            # Pop out the first entry in the traceback, because that's
            # this function call itself
            tbs.pop(1)
            await embed_utils.replace(
                self.response_msg, "Invalid arguments!", f"```\n{''.join(tbs)}```"
            )
            return

        if len(args) == 1:
            await embed_utils.send(self.invoke_msg.channel, args[0], "")
        elif len(args) == 2:
            await embed_utils.send(self.invoke_msg.channel, args[0], args[1])
        elif len(args) == 3:
            await embed_utils.send(self.invoke_msg.channel, args[0], args[1], args[2])
        elif len(args) == 4:
            if isinstance(args[3], list):
                fields = embed_utils.get_fields(args[3])
                await embed_utils.send(
                    self.invoke_msg.channel, args[0], args[1], args[2], fields=fields
                )
            else:
                await embed_utils.send(
                    self.invoke_msg.channel, args[0], args[1], args[2], args[3]
                )
        elif len(args) == 5:
            fields = embed_utils.get_fields(args[3])
            await embed_utils.send(
                self.invoke_msg.channel,
                args[0],
                args[1],
                args[2],
                args[3],
                fields=fields,
            )
        else:
            await embed_utils.replace(self.response_msg, "Invalid arguments!", "")
            return

        await self.response_msg.delete()
        await self.invoke_msg.delete()

    async def cmd_emsudo_edit_c(self):
        """
        ->type More admin commands
        ->signature pg!emsudo_edit_c [message_id] [*args]
        ->description Edit an embed sent by the bot
        -----
        Implement pg!emsudo_edit_c, for admins to edit embeds via the bot
        """
        try:
            args = eval(CodeBlock(self.string, strip_lang=True, strip_ticks=True).code)
        except Exception as e:
            tbs = traceback.format_exception(type(e), e, e.__traceback__)
            # Pop out the first entry in the traceback, because that's
            # this function call itself
            tbs.pop(1)
            await embed_utils.replace(
                self.response_msg, "Invalid arguments!", f"```\n{''.join(tbs)}```"
            )
            return
        edit_msg = await self.invoke_msg.channel.fetch_message(args[0])

        if len(args) == 2:
            await embed_utils.replace(edit_msg, args[1], "")
        elif len(args) == 3:
            await embed_utils.replace(edit_msg, args[1], args[2])
        elif len(args) == 4:
            await embed_utils.replace(edit_msg, args[1], args[2], args[3])
        elif len(args) == 5:
            if isinstance(args[4], list):
                fields = embed_utils.get_fields(args[4])
                await embed_utils.replace(
                    edit_msg, args[1], args[2], args[3], fields=fields
                )
            else:
                await embed_utils.replace(edit_msg, args[1], args[2], args[3], args[4])
        elif len(args) == 6:
            fields = embed_utils.get_fields(args[4])
            await embed_utils.replace(
                edit_msg, args[1], args[2], args[3], args[4], fields=fields
            )
        else:
            await embed_utils.replace(self.response_msg, "Invalid arguments!", "")
            return

        await self.response_msg.delete()
        await self.invoke_msg.delete()

    async def cmd_emsudo(self):
        """
        ->type emsudo commands
        ->signature pg!emsudo [*args]
        ->description Send an embed through the bot
        ->extended description
        ```
        pg!emsudo {embed_tuple}
        pg!emsudo {embed_dict}
        pg!emsudo {message_id}
        pg!emsudo {channel_id} {message_id}
        pg!emsudo {empty_str}
        ```
        Generate an embed from the given arguments and send it with a message to the channel where this command was invoked.
        -----
        Implement pg!emsudo, for admins to send embeds via the bot
        """

        util_send_embed_args = dict(
            embed_type="rich",
            author_name=EmptyEmbed,
            author_url=EmptyEmbed,
            author_icon_url=EmptyEmbed,
            title=EmptyEmbed,
            url=EmptyEmbed,
            thumbnail_url=EmptyEmbed,
            description=EmptyEmbed,
            image_url=EmptyEmbed,
            color=0xFFFFAA,
            fields=(),
            footer_text=EmptyEmbed,
            footer_icon_url=EmptyEmbed,
            timestamp=None,
        )

        if len(self.args) == 2:
            if self.args[0].isnumeric() and self.args[1].isnumeric():
                src_channel = self.invoke_msg.author.guild.get_channel(
                    int(self.args[0])
                )

                if not src_channel:
                    await embed_utils.replace(
                        self.response_msg, "Invalid channel id!", ""
                    )
                    return

                try:
                    attachment_msg = await src_channel.fetch_message(int(self.args[1]))
                except discord.NotFound:
                    await embed_utils.replace(
                        self.response_msg, "Invalid message id!", ""
                    )
                    return

                if not attachment_msg.attachments:
                    await embed_utils.replace(
                        self.response_msg,
                        "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                        "",
                    )
                    return

                for attachment in attachment_msg.attachments:
                    if (
                        attachment.content_type is not None
                        and attachment.content_type.startswith("text")
                    ):
                        attachment_obj = attachment
                        break
                else:
                    await embed_utils.replace(
                        self.response_msg,
                        "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                        "",
                    )
                    return

                txt_dict = await attachment_obj.read()
                embed_dict = eval(txt_dict.decode())
                await embed_utils.send_from_dict(self.invoke_msg.channel, embed_dict)
                await self.response_msg.delete()
                await self.invoke_msg.delete()
                return

        try:
            args = eval(CodeBlock(self.string).code)
        except Exception as e:
            tbs = traceback.format_exception(type(e), e, e.__traceback__)
            # Pop out the first entry in the traceback, because that's
            # this function call itself
            tbs.pop(1)
            await embed_utils.replace(
                self.response_msg, "Invalid arguments!", f"```\n{''.join(tbs)}```"
            )
            return

        if isinstance(args, dict):
            await embed_utils.send_from_dict(self.invoke_msg.channel, args)
            await self.response_msg.delete()
            await self.invoke_msg.delete()
            return

        elif isinstance(args, int):
            try:
                attachment_msg = await self.invoke_msg.channel.fetch_message(args)
            except discord.NotFound:
                await embed_utils.replace(self.response_msg, "Invalid message id!", "")
                return

            if not attachment_msg.attachments:
                await embed_utils.replace(
                    self.response_msg,
                    "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                    "",
                )
                return

            for attachment in attachment_msg.attachments:
                if (
                    attachment.content_type is not None
                    and attachment.content_type.startswith("text")
                ):
                    attachment_obj = attachment
                    break
            else:
                await embed_utils.replace(
                    self.response_msg,
                    "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                    "",
                )
                return

            txt_dict = await attachment_obj.read()
            embed_dict = eval(txt_dict.decode())
            await embed_utils.send_from_dict(self.invoke_msg.channel, embed_dict)
            await self.response_msg.delete()
            await self.invoke_msg.delete()
            return

        elif isinstance(args, str) and not args:
            attachment_msg = self.invoke_msg

            if not attachment_msg.attachments:
                await embed_utils.replace(
                    self.response_msg,
                    "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                    "",
                )
                return

            for attachment in attachment_msg.attachments:
                if (
                    attachment.content_type is not None
                    and attachment.content_type.startswith("text")
                ):
                    attachment_obj = attachment
                    break
            else:
                await embed_utils.replace(
                    self.response_msg,
                    "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                    "",
                )
                return

            txt_dict = await attachment_obj.read()
            embed_dict = eval(txt_dict.decode())
            await embed_utils.send_from_dict(self.invoke_msg.channel, embed_dict)
            await self.response_msg.delete()
            await self.invoke_msg.delete()
            return

        arg_count = len(args)

        if arg_count > 0:
            if isinstance(args[0], (tuple, list)):
                if len(args[0]) == 3:
                    util_send_embed_args.update(
                        author_name=args[0][0],
                        author_url=args[0][1],
                        author_icon_url=args[0][2],
                    )
                elif len(args[0]) == 2:
                    util_send_embed_args.update(
                        author_name=args[0][0],
                        author_url=args[0][1],
                    )
                elif len(args[0]) == 1:
                    util_send_embed_args.update(
                        author_name=args[0][0],
                    )

            else:
                util_send_embed_args.update(
                    author_name=args[0],
                )
        else:
            await embed_utils.replace(self.response_msg, "Invalid arguments!", "")
            return

        if arg_count > 1:
            if isinstance(args[1], (tuple, list)):
                if len(args[1]) == 3:
                    util_send_embed_args.update(
                        title=args[1][0],
                        url=args[1][1],
                        thumbnail_url=args[1][2],
                    )

                elif len(args[1]) == 2:
                    util_send_embed_args.update(
                        title=args[1][0],
                        url=args[1][1],
                    )

                elif len(args[1]) == 1:
                    util_send_embed_args.update(
                        title=args[1][0],
                    )

            else:
                util_send_embed_args.update(
                    title=args[1],
                )

        if arg_count > 2:
            if isinstance(args[2], (tuple, list)):
                if len(args[2]) == 2:
                    util_send_embed_args.update(
                        description=args[2][0],
                        image_url=args[2][1],
                    )

                elif len(args[2]) == 1:
                    util_send_embed_args.update(
                        description=args[2][0],
                    )

            else:
                util_send_embed_args.update(
                    description=args[2],
                )

        if arg_count > 3:
            if args[3] > -1:
                util_send_embed_args.update(
                    color=args[3],
                )

        if arg_count > 4:
            try:
                util_send_embed_args.update(fields=embed_utils.get_fields(args[4]))
            except TypeError:
                await embed_utils.replace(
                    self.response_msg, "Invalid format for field string!", ""
                )
                return

        if arg_count > 5:
            if isinstance(args[5], (tuple, list)):
                if len(args[5]) == 2:
                    util_send_embed_args.update(
                        footer_text=args[5][0],
                        footer_icon_url=args[5][1],
                    )

                elif len(args[5]) == 1:
                    util_send_embed_args.update(
                        footer_text=args[5][0],
                    )

            else:
                util_send_embed_args.update(
                    footer_text=args[5],
                )

        if arg_count > 6:
            util_send_embed_args.update(timestamp=args[6])

        await embed_utils.send_2(self.invoke_msg.channel, **util_send_embed_args)
        await self.response_msg.delete()
        await self.invoke_msg.delete()

    async def cmd_emsudo_add(self):
        """
        ->type emsudo commands
        ->signature pg!emsudo_add [*args]
        ->description Add an embed through the bot
        ->extended description
        ```
        pg!emsudo_add ({target_message_id}, *{embed_tuple})
        pg!emsudo_add ({target_message_id}, {embed_dict})
        pg!emsudo_add {target_message_id} {message_id}
        pg!emsudo_add {target_message_id} {channel_id} {message_id}
        pg!emsudo_add ({target_message_id}, {empty_str})
        ```
        Add an embed to a message (even if it has one, it will be replaced) in the channel where this command was invoked using the given arguments.
        -----
        Implement pg!emsudo_add, for admins to add embeds to messages via the bot
        """

        util_add_embed_args = dict(
            embed_type="rich",
            author_name=EmptyEmbed,
            author_url=EmptyEmbed,
            author_icon_url=EmptyEmbed,
            title=EmptyEmbed,
            url=EmptyEmbed,
            thumbnail_url=EmptyEmbed,
            description=EmptyEmbed,
            image_url=EmptyEmbed,
            color=0xFFFFAA,
            fields=(),
            footer_text=EmptyEmbed,
            footer_icon_url=EmptyEmbed,
            timestamp=None,
        )

        if len(self.args) == 3:
            if (
                self.args[0].isnumeric()
                and self.args[1].isnumeric()
                and self.args[2].isnumeric()
            ):
                try:
                    edit_msg = await self.invoke_msg.channel.fetch_message(self.args[0])
                except (discord.NotFound, IndexError, ValueError):
                    await embed_utils.replace(
                        self.response_msg, "Invalid arguments!", ""
                    )
                    return

                src_channel = self.invoke_msg.author.guild.get_channel(
                    int(self.args[1])
                )

                if not src_channel:
                    await embed_utils.replace(
                        self.response_msg, "Invalid source channel id!", ""
                    )
                    return

                try:
                    attachment_msg = await src_channel.fetch_message(int(self.args[2]))
                except discord.NotFound:
                    await embed_utils.replace(
                        self.response_msg, "Invalid source message id!", ""
                    )
                    return

                if not attachment_msg.attachments:
                    await embed_utils.replace(
                        self.response_msg,
                        "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                        "",
                    )
                    return

                for attachment in attachment_msg.attachments:
                    if (
                        attachment.content_type is not None
                        and attachment.content_type.startswith("text")
                    ):
                        attachment_obj = attachment
                        break
                else:
                    await embed_utils.replace(
                        self.response_msg,
                        "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                        "",
                    )
                    return

                txt_dict = await attachment_obj.read()
                embed_dict = eval(txt_dict.decode())
                await embed_utils.replace_from_dict(edit_msg, embed_dict)
                await self.response_msg.delete()
                await self.invoke_msg.delete()
                return

        elif len(self.args) == 2:
            if self.args[0].isnumeric() and self.args[1].isnumeric():
                try:
                    edit_msg = await self.invoke_msg.channel.fetch_message(self.args[0])
                except (discord.NotFound, IndexError, ValueError):
                    await embed_utils.replace(
                        self.response_msg, "Invalid arguments!", ""
                    )
                    return

                src_channel = self.invoke_msg.channel

                try:
                    attachment_msg = await src_channel.fetch_message(int(self.args[1]))
                except discord.NotFound:
                    await embed_utils.replace(
                        self.response_msg, "Invalid message id!", ""
                    )
                    return

                if not attachment_msg.attachments:
                    await embed_utils.replace(
                        self.response_msg,
                        "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                        "",
                    )
                    return

                for attachment in attachment_msg.attachments:
                    if (
                        attachment.content_type is not None
                        and attachment.content_type.startswith("text")
                    ):
                        attachment_obj = attachment
                        break
                else:
                    await embed_utils.replace(
                        self.response_msg,
                        "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                        "",
                    )
                    return

                txt_dict = await attachment_obj.read()
                embed_dict = eval(txt_dict.decode())
                await embed_utils.replace_from_dict(edit_msg, embed_dict)
                await self.response_msg.delete()
                await self.invoke_msg.delete()
                return

        try:
            args = eval(CodeBlock(self.string).code)
        except Exception as e:
            tbs = traceback.format_exception(type(e), e, e.__traceback__)
            # Pop out the first entry in the traceback, because that's
            # this function call itself
            tbs.pop(1)
            await embed_utils.replace(
                self.response_msg, "Invalid arguments!", f"```\n{''.join(tbs)}```"
            )
            return

        try:
            edit_msg = await self.invoke_msg.channel.fetch_message(args[0])
        except (discord.NotFound, IndexError, ValueError):
            await embed_utils.replace(self.response_msg, "Invalid arguments!", "")
            return

        args = args[1:]
        arg_count = len(args)

        if arg_count > 0:
            if isinstance(args[0], (tuple, list)):
                if len(args[0]) == 3:
                    util_add_embed_args.update(
                        author_name=args[0][0],
                        author_url=args[0][1],
                        author_icon_url=args[0][2],
                    )
                elif len(args[0]) == 2:
                    util_add_embed_args.update(
                        author_name=args[0][0],
                        author_url=args[0][1],
                    )
                elif len(args[0]) == 1:
                    util_add_embed_args.update(
                        author_name=args[0][0],
                    )

            elif isinstance(args[0], dict):
                await embed_utils.replace_from_dict(edit_msg, args[0])
                await self.response_msg.delete()
                await self.invoke_msg.delete()
                return

            elif isinstance(args[0], int):
                try:
                    attachment_msg = await self.invoke_msg.channel.fetch_message(
                        args[0]
                    )
                except discord.NotFound:
                    await embed_utils.replace(
                        self.response_msg, "Invalid message id!", ""
                    )
                    return

                if not attachment_msg.attachments:
                    await embed_utils.replace(
                        self.response_msg,
                        "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                        "",
                    )
                    return

                for attachment in attachment_msg.attachments:
                    if (
                        attachment.content_type is not None
                        and attachment.content_type.startswith("text")
                    ):
                        attachment_obj = attachment
                        break
                else:
                    await embed_utils.replace(
                        self.response_msg,
                        "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                        "",
                    )
                    return

                txt_dict = await attachment_obj.read()
                embed_dict = eval(txt_dict.decode())
                await embed_utils.replace_from_dict(edit_msg, embed_dict)
                await self.response_msg.delete()
                await self.invoke_msg.delete()
                return

            elif isinstance(args[0], str) and not args[0]:
                attachment_msg = self.invoke_msg

                if not attachment_msg.attachments:
                    await embed_utils.replace(
                        self.response_msg,
                        "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                        "",
                    )
                    return

                for attachment in attachment_msg.attachments:
                    if (
                        attachment.content_type is not None
                        and attachment.content_type.startswith("text")
                    ):
                        attachment_obj = attachment
                        break
                else:
                    await embed_utils.replace(
                        self.response_msg,
                        "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                        "",
                    )
                    return

                txt_dict = await attachment_obj.read()
                embed_dict = eval(txt_dict.decode())
                await embed_utils.replace_from_dict(edit_msg, embed_dict)
                await self.response_msg.delete()
                await self.invoke_msg.delete()
                return

            else:
                util_add_embed_args.update(
                    author_name=args[0],
                )
        else:
            await embed_utils.replace(self.response_msg, "Invalid arguments!", "")
            return

        if arg_count > 1:
            if isinstance(args[1], (tuple, list)):
                if len(args[1]) == 3:
                    util_add_embed_args.update(
                        title=args[1][0],
                        url=args[1][1],
                        thumbnail_url=args[1][2],
                    )

                elif len(args[1]) == 2:
                    util_add_embed_args.update(
                        title=args[1][0],
                        url=args[1][1],
                    )

                elif len(args[1]) == 1:
                    util_add_embed_args.update(
                        title=args[1][0],
                    )

            else:
                util_add_embed_args.update(
                    title=args[1],
                )

        if arg_count > 2:
            if isinstance(args[2], (tuple, list)):
                if len(args[2]) == 2:
                    util_add_embed_args.update(
                        description=args[2][0],
                        image_url=args[2][1],
                    )

                elif len(args[2]) == 1:
                    util_add_embed_args.update(
                        description=args[2][0],
                    )

            else:
                util_add_embed_args.update(
                    description=args[2],
                )

        if arg_count > 3:
            if args[3] > -1:
                util_add_embed_args.update(
                    color=args[3],
                )

        if arg_count > 4:
            try:
                util_add_embed_args.update(fields=embed_utils.get_fields(args[4]))
            except TypeError:
                await embed_utils.replace(
                    self.response_msg, "Invalid format for field string!", ""
                )
                return

        if arg_count > 5:
            if isinstance(args[5], (tuple, list)):
                if len(args[5]) == 2:
                    util_add_embed_args.update(
                        footer_text=args[5][0],
                        footer_icon_url=args[5][1],
                    )

                elif len(args[5]) == 1:
                    util_add_embed_args.update(
                        footer_text=args[5][0],
                    )

            else:
                util_add_embed_args.update(
                    footer_text=args[5],
                )

        if arg_count > 6:
            util_add_embed_args.update(timestamp=args[6])

        await embed_utils.replace_2(edit_msg, **util_add_embed_args)
        await self.response_msg.delete()
        await self.invoke_msg.delete()

    async def cmd_emsudo_replace(self):
        """
        ->type emsudo commands
        ->signature pg!emsudo_replace [*args]
        ->description Replace an embed through the bot
        ->extended description
        ```
        pg!emsudo_replace ({target_message_id}, *{embed_tuple})
        pg!emsudo_replace ({target_message_id}, {embed_dict})
        pg!emsudo_replace {target_message_id} {message_id}
        pg!emsudo_replace {target_message_id} {channel_id} {message_id}
        pg!emsudo_replace ({target_message_id}, {empty_str})
        ```
        Replace the embed of a message in the channel where this command was invoked using the given arguments.
        -----
        Implement pg!emsudo_replace, for admins to replace embeds via the bot
        """

        util_replace_embed_args = dict(
            embed_type="rich",
            author_name=EmptyEmbed,
            author_url=EmptyEmbed,
            author_icon_url=EmptyEmbed,
            title=EmptyEmbed,
            url=EmptyEmbed,
            thumbnail_url=EmptyEmbed,
            description=EmptyEmbed,
            image_url=EmptyEmbed,
            color=0xFFFFAA,
            fields=(),
            footer_text=EmptyEmbed,
            footer_icon_url=EmptyEmbed,
            timestamp=None,
        )

        if len(self.args) == 3:
            if (
                self.args[0].isnumeric()
                and self.args[1].isnumeric()
                and self.args[2].isnumeric()
            ):
                try:
                    edit_msg = await self.invoke_msg.channel.fetch_message(self.args[0])
                except (discord.NotFound, IndexError, ValueError):
                    await embed_utils.replace(
                        self.response_msg, "Invalid arguments!", ""
                    )
                    return

                src_channel = self.invoke_msg.author.guild.get_channel(
                    int(self.args[1])
                )

                if not src_channel:
                    await embed_utils.replace(
                        self.response_msg, "Invalid source channel id!", ""
                    )
                    return

                try:
                    attachment_msg = await src_channel.fetch_message(int(self.args[2]))
                except discord.NotFound:
                    await embed_utils.replace(
                        self.response_msg, "Invalid source message id!", ""
                    )
                    return

                if not attachment_msg.attachments:
                    await embed_utils.replace(
                        self.response_msg,
                        "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                        "",
                    )
                    return

                for attachment in attachment_msg.attachments:
                    if (
                        attachment.content_type is not None
                        and attachment.content_type.startswith("text")
                    ):
                        attachment_obj = attachment
                        break
                else:
                    await embed_utils.replace(
                        self.response_msg,
                        "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                        "",
                    )
                    return

                txt_dict = await attachment_obj.read()
                embed_dict = eval(txt_dict.decode())
                await embed_utils.replace_from_dict(edit_msg, embed_dict)
                await self.response_msg.delete()
                await self.invoke_msg.delete()
                return

        elif len(self.args) == 2:
            if self.args[0].isnumeric() and self.args[1].isnumeric():
                try:
                    edit_msg = await self.invoke_msg.channel.fetch_message(self.args[0])
                except (discord.NotFound, IndexError, ValueError):
                    await embed_utils.replace(
                        self.response_msg, "Invalid arguments!", ""
                    )
                    return

                src_channel = self.invoke_msg.channel

                try:
                    attachment_msg = await src_channel.fetch_message(int(self.args[1]))
                except discord.NotFound:
                    await embed_utils.replace(
                        self.response_msg, "Invalid message id!", ""
                    )
                    return

                if not attachment_msg.attachments:
                    await embed_utils.replace(
                        self.response_msg,
                        "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                        "",
                    )
                    return

                for attachment in attachment_msg.attachments:
                    if (
                        attachment.content_type is not None
                        and attachment.content_type.startswith("text")
                    ):
                        attachment_obj = attachment
                        break
                else:
                    await embed_utils.replace(
                        self.response_msg,
                        "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                        "",
                    )
                    return

                txt_dict = await attachment_obj.read()
                embed_dict = eval(txt_dict.decode())
                await embed_utils.replace_from_dict(edit_msg, embed_dict)
                await self.response_msg.delete()
                await self.invoke_msg.delete()
                return

        try:
            args = eval(CodeBlock(self.string).code)
        except Exception as e:
            tbs = traceback.format_exception(type(e), e, e.__traceback__)
            # Pop out the first entry in the traceback, because that's
            # this function call itself
            tbs.pop(1)
            await embed_utils.replace(
                self.response_msg, "Invalid arguments!", f"```\n{''.join(tbs)}```"
            )
            return

        try:
            edit_msg = await self.invoke_msg.channel.fetch_message(args[0])
        except (discord.NotFound, IndexError, ValueError, TypeError):
            await embed_utils.replace(self.response_msg, "Invalid arguments!", "")
            return

        args = args[1:]
        arg_count = len(args)

        if arg_count > 0:
            if isinstance(args[0], (tuple, list)):
                if len(args[0]) == 3:
                    util_replace_embed_args.update(
                        author_name=args[0][0],
                        author_url=args[0][1],
                        author_icon_url=args[0][2],
                    )
                elif len(args[0]) == 2:
                    util_replace_embed_args.update(
                        author_name=args[0][0],
                        author_url=args[0][1],
                    )
                elif len(args[0]) == 1:
                    util_replace_embed_args.update(
                        author_name=args[0][0],
                    )

            elif isinstance(args[0], dict):
                await embed_utils.replace_from_dict(edit_msg, args[0])
                await self.response_msg.delete()
                await self.invoke_msg.delete()
                return

            elif isinstance(args[0], int):
                try:
                    attachment_msg = await self.invoke_msg.channel.fetch_message(
                        args[0]
                    )
                except discord.NotFound:
                    await embed_utils.replace(
                        self.response_msg, "Invalid message id!", ""
                    )
                    return

                if not attachment_msg.attachments:
                    await embed_utils.replace(
                        self.response_msg,
                        "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                        "",
                    )
                    return

                for attachment in attachment_msg.attachments:
                    if (
                        attachment.content_type is not None
                        and attachment.content_type.startswith("text")
                    ):
                        attachment_obj = attachment
                        break
                else:
                    await embed_utils.replace(
                        self.response_msg,
                        "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                        "",
                    )
                    return

                txt_dict = await attachment_obj.read()
                embed_dict = eval(txt_dict.decode())
                await embed_utils.replace_from_dict(edit_msg, embed_dict)
                await self.response_msg.delete()
                await self.invoke_msg.delete()
                return

            elif isinstance(args[0], str) and not args[0]:
                if arg_count > 1:
                    util_replace_embed_args.update(
                        author_name=args[0],
                    )

                else:
                    attachment_msg = self.invoke_msg
                    if not attachment_msg.attachments:
                        await embed_utils.replace(
                            self.response_msg,
                            "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                            "",
                        )
                        return

                    for attachment in attachment_msg.attachments:
                        if (
                            attachment.content_type is not None
                            and attachment.content_type.startswith("text")
                        ):
                            attachment_obj = attachment
                            break
                    else:
                        await embed_utils.replace(
                            self.response_msg,
                            "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                            "",
                        )
                        return

                    txt_dict = await attachment_obj.read()
                    embed_dict = eval(txt_dict.decode())
                    await embed_utils.replace_from_dict(edit_msg, embed_dict)
                    await self.response_msg.delete()
                    await self.invoke_msg.delete()
                    return

            elif isinstance(args[0], str) and args[0]:
                util_replace_embed_args.update(
                    author_name=args[0],
                )

            else:
                await embed_utils.replace(self.response_msg, "Invalid arguments!", "")
                return
        else:
            await embed_utils.replace(self.response_msg, "Invalid arguments!", "")
            return

        if arg_count > 1:
            if isinstance(args[1], (tuple, list)):
                if len(args[1]) == 3:
                    util_replace_embed_args.update(
                        title=args[1][0],
                        url=args[1][1],
                        thumbnail_url=args[1][2],
                    )

                elif len(args[1]) == 2:
                    util_replace_embed_args.update(
                        title=args[1][0],
                        url=args[1][1],
                    )

                elif len(args[1]) == 1:
                    util_replace_embed_args.update(
                        title=args[1][0],
                    )

            else:
                util_replace_embed_args.update(
                    title=args[1],
                )

        if arg_count > 2:
            if isinstance(args[2], (tuple, list)):
                if len(args[2]) == 2:
                    util_replace_embed_args.update(
                        description=args[2][0],
                        image_url=args[2][1],
                    )

                elif len(args[2]) == 1:
                    util_replace_embed_args.update(
                        description=args[2][0],
                    )

            else:
                util_replace_embed_args.update(
                    description=args[2],
                )

        if arg_count > 3:
            if args[3] > -1:
                util_replace_embed_args.update(
                    color=args[3],
                )

        if arg_count > 4:
            try:
                util_replace_embed_args.update(fields=embed_utils.get_fields(args[4]))
            except TypeError:
                await embed_utils.replace(
                    self.response_msg, "Invalid format for field string!", ""
                )
                return

        if arg_count > 5:
            if isinstance(args[5], (tuple, list)):
                if len(args[5]) == 2:
                    util_replace_embed_args.update(
                        footer_text=args[5][0],
                        footer_icon_url=args[5][1],
                    )

                elif len(args[5]) == 1:
                    util_replace_embed_args.update(
                        footer_text=args[5][0],
                    )

            else:
                util_replace_embed_args.update(
                    footer_text=args[5],
                )

        if arg_count > 6:
            util_replace_embed_args.update(timestamp=args[6])

        await embed_utils.replace_2(edit_msg, **util_replace_embed_args)
        await self.response_msg.delete()
        await self.invoke_msg.delete()

    async def cmd_emsudo_edit(self):
        """
        ->type emsudo commands
        ->signature pg!emsudo_edit [*args]
        ->description Edit an embed through the bot
        ->extended description
        ```
        pg!emsudo_edit ({target_message_id}, *{embed_tuple})
        pg!emsudo_edit ({target_message_id}, {embed_dict})
        pg!emsudo_edit {target_message_id} {message_id}
        pg!emsudo_edit {target_message_id} {channel_id} {message_id}
        pg!emsudo_edit ({target_message_id}, {empty_str})
        ```
        Update the given attributes of an embed of a message in the channel where this command was invoked using the given arguments.
        -----
        Implement pg!emsudo_edit, for admins to replace embeds via the bot
        """

        util_edit_embed_args = dict(
            embed_type="rich",
            author_name=EmptyEmbed,
            author_url=EmptyEmbed,
            author_icon_url=EmptyEmbed,
            title=EmptyEmbed,
            url=EmptyEmbed,
            thumbnail_url=EmptyEmbed,
            description=EmptyEmbed,
            image_url=EmptyEmbed,
            color=0xFFFFAA,
            fields=(),
            footer_text=EmptyEmbed,
            footer_icon_url=EmptyEmbed,
            timestamp=None,
        )

        if len(self.args) == 3:
            if (
                self.args[0].isnumeric()
                and self.args[1].isnumeric()
                and self.args[2].isnumeric()
            ):
                try:
                    edit_msg = await self.invoke_msg.channel.fetch_message(self.args[0])
                except (discord.NotFound, IndexError, ValueError):
                    await embed_utils.replace(
                        self.response_msg, "Invalid arguments!", ""
                    )
                    return

                if not edit_msg.embeds:
                    await embed_utils.replace(
                        self.response_msg,
                        "Cannot execute command:",
                        "No embed data found in message.",
                    )
                    return

                edit_msg_embed = edit_msg.embeds[0]

                src_channel = self.invoke_msg.author.guild.get_channel(
                    int(self.args[1])
                )

                if not src_channel:
                    await embed_utils.replace(
                        self.response_msg, "Invalid source channel id!", ""
                    )
                    return

                try:
                    attachment_msg = await src_channel.fetch_message(int(self.args[2]))
                except discord.NotFound:
                    await embed_utils.replace(
                        self.response_msg, "Invalid source message id!", ""
                    )
                    return

                if not attachment_msg.attachments:
                    await embed_utils.replace(
                        self.response_msg,
                        "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                        "",
                    )
                    return

                for attachment in attachment_msg.attachments:
                    if (
                        attachment.content_type is not None
                        and attachment.content_type.startswith("text")
                    ):
                        attachment_obj = attachment
                        break
                else:
                    await embed_utils.replace(
                        self.response_msg,
                        "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                        "",
                    )
                    return

                txt_dict = await attachment_obj.read()
                embed_dict = eval(txt_dict.decode())
                await embed_utils.edit_from_dict(edit_msg, edit_msg_embed, embed_dict)
                await self.response_msg.delete()
                await self.invoke_msg.delete()
                return

        elif len(self.args) == 2:
            if self.args[0].isnumeric() and self.args[1].isnumeric():
                try:
                    edit_msg = await self.invoke_msg.channel.fetch_message(self.args[0])
                except (discord.NotFound, IndexError, ValueError):
                    await embed_utils.replace(
                        self.response_msg, "Invalid arguments!", ""
                    )
                    return

                src_channel = self.invoke_msg.channel

                if not edit_msg.embeds:
                    await embed_utils.replace(
                        self.response_msg,
                        "Cannot execute command:",
                        "No embed data found in message.",
                    )
                    return

                edit_msg_embed = edit_msg.embeds[0]

                try:
                    attachment_msg = await src_channel.fetch_message(int(self.args[1]))
                except discord.NotFound:
                    await embed_utils.replace(
                        self.response_msg, "Invalid message id!", ""
                    )
                    return

                if not attachment_msg.attachments:
                    await embed_utils.replace(
                        self.response_msg,
                        "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                        "",
                    )
                    return

                for attachment in attachment_msg.attachments:
                    if (
                        attachment.content_type is not None
                        and attachment.content_type.startswith("text")
                    ):
                        attachment_obj = attachment
                        break
                else:
                    await embed_utils.replace(
                        self.response_msg,
                        "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                        "",
                    )
                    return

                txt_dict = await attachment_obj.read()
                embed_dict = eval(txt_dict.decode())
                await embed_utils.edit_from_dict(edit_msg, edit_msg_embed, embed_dict)
                await self.response_msg.delete()
                await self.invoke_msg.delete()
                return

        try:
            args = eval(CodeBlock(self.string).code)
        except Exception as e:
            tbs = traceback.format_exception(type(e), e, e.__traceback__)
            # Pop out the first entry in the traceback, because that's
            # this function call itself
            tbs.pop(1)
            await embed_utils.replace(
                self.response_msg, "Invalid arguments!", f"```\n{''.join(tbs)}```"
            )
            return

        try:
            edit_msg = await self.invoke_msg.channel.fetch_message(args[0])
        except (discord.NotFound, IndexError, ValueError, TypeError):
            await embed_utils.replace(self.response_msg, "Invalid arguments!", "")
            return

        if not edit_msg.embeds:
            await embed_utils.replace(
                self.response_msg,
                "Cannot execute command:",
                "No embed data found in message.",
            )
            return

        edit_msg_embed = edit_msg.embeds[0]

        args = args[1:]
        arg_count = len(args)

        if arg_count > 0:
            if isinstance(args[0], (tuple, list)):
                if len(args[0]) == 3:
                    util_edit_embed_args.update(
                        author_name=args[0][0],
                        author_url=args[0][1],
                        author_icon_url=args[0][2],
                    )
                elif len(args[0]) == 2:
                    util_edit_embed_args.update(
                        author_name=args[0][0],
                        author_url=args[0][1],
                    )
                elif len(args[0]) == 1:
                    util_edit_embed_args.update(
                        author_name=args[0][0],
                    )

            elif isinstance(args[0], dict):
                await embed_utils.edit_from_dict(edit_msg, edit_msg_embed, args[0])
                await self.response_msg.delete()
                await self.invoke_msg.delete()
                return

            elif isinstance(args[0], int):
                try:
                    attachment_msg = await self.invoke_msg.channel.fetch_message(
                        args[0]
                    )
                except discord.NotFound:
                    await embed_utils.replace(
                        self.response_msg, "Invalid message id!", ""
                    )
                    return

                if not attachment_msg.attachments:
                    await embed_utils.replace(
                        self.response_msg,
                        "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                        "",
                    )
                    return

                for attachment in attachment_msg.attachments:
                    if (
                        attachment.content_type is not None
                        and attachment.content_type.startswith("text")
                    ):
                        attachment_obj = attachment
                        break
                else:
                    await embed_utils.replace(
                        self.response_msg,
                        "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                        "",
                    )
                    return

                txt_dict = await attachment_obj.read()
                embed_dict = eval(txt_dict.decode())
                await embed_utils.edit_from_dict(edit_msg, edit_msg_embed, embed_dict)
                await self.response_msg.delete()
                await self.invoke_msg.delete()
                return

            elif isinstance(args[0], str) and not args[0]:
                if arg_count > 1:
                    util_edit_embed_args.update(
                        author_name=args[0],
                    )

                else:
                    attachment_msg = self.invoke_msg
                    if not attachment_msg.attachments:
                        await embed_utils.replace(
                            self.response_msg,
                            "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                            "",
                        )
                        return

                    for attachment in attachment_msg.attachments:
                        if (
                            attachment.content_type is not None
                            and attachment.content_type.startswith("text")
                        ):
                            attachment_obj = attachment
                            break
                    else:
                        await embed_utils.replace(
                            self.response_msg,
                            "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                            "",
                        )
                        return

                    txt_dict = await attachment_obj.read()
                    embed_dict = eval(txt_dict.decode())
                    await embed_utils.edit_from_dict(
                        edit_msg, edit_msg_embed, embed_dict
                    )
                    await self.response_msg.delete()
                    await self.invoke_msg.delete()
                    return

            elif isinstance(args[0], str) and args[0]:
                util_edit_embed_args.update(
                    author_name=args[0],
                )

            else:
                await embed_utils.replace(self.response_msg, "Invalid arguments!", "")
                return
        else:
            await embed_utils.replace(self.response_msg, "Invalid arguments!", "")
            return

        if arg_count > 1:
            if isinstance(args[1], (tuple, list)):
                if len(args[1]) == 3:
                    util_edit_embed_args.update(
                        title=args[1][0],
                        url=args[1][1],
                        thumbnail_url=args[1][2],
                    )

                elif len(args[1]) == 2:
                    util_edit_embed_args.update(
                        title=args[1][0],
                        url=args[1][1],
                    )

                elif len(args[1]) == 1:
                    util_edit_embed_args.update(
                        title=args[1][0],
                    )

            else:
                util_edit_embed_args.update(
                    title=args[1],
                )

        if arg_count > 2:
            if isinstance(args[2], (tuple, list)):
                if len(args[2]) == 2:
                    util_edit_embed_args.update(
                        description=args[2][0],
                        image_url=args[2][1],
                    )

                elif len(args[2]) == 1:
                    util_edit_embed_args.update(
                        description=args[2][0],
                    )

            else:
                util_edit_embed_args.update(
                    description=args[2],
                )

        if arg_count > 3:
            util_edit_embed_args.update(
                color=args[3],
            )
        else:
            util_edit_embed_args.update(
                color=-1,
            )

        if arg_count > 4:
            try:
                util_edit_embed_args.update(fields=embed_utils.get_fields(args[4]))
            except TypeError:
                await embed_utils.replace(
                    self.response_msg, "Invalid format for field string!", ""
                )
                return

        if arg_count > 5:
            if isinstance(args[5], (tuple, list)):
                if len(args[5]) == 2:
                    util_edit_embed_args.update(
                        footer_text=args[5][0],
                        footer_icon_url=args[5][1],
                    )

                elif len(args[5]) == 1:
                    util_edit_embed_args.update(
                        footer_text=args[5][0],
                    )

            else:
                util_edit_embed_args.update(
                    footer_text=args[5],
                )

        if arg_count > 6:
            util_edit_embed_args.update(timestamp=args[6])

        await embed_utils.edit_2(edit_msg, edit_msg_embed, **util_edit_embed_args)
        await self.response_msg.delete()
        await self.invoke_msg.delete()

    async def cmd_emsudo_replace_field(self):
        """
        ->type emsudo commands
        ->signature pg!emsudo_replace [*args]
        ->description Replace an embed field through the bot
        ->extended description
        ```
        pg!emsudo_replace_field ({target_message_id}, {index}, {field_string})
        pg!emsudo_replace_field ({target_message_id}, {index}, {field_dict})
        ```
        Replace an embed field at the given index in the embed of a message in the channel where this command was invoked using the given arguments.
        -----
        Implement pg!emsudo_replace_field, for admins to update fields of embeds sent via the bot
        """

        try:
            args = eval(CodeBlock(self.string).code)
        except Exception as e:
            tbs = traceback.format_exception(type(e), e, e.__traceback__)
            # Pop out the first entry in the traceback, because that's
            # this function call itself
            tbs.pop(1)
            await embed_utils.replace(
                self.response_msg, "Invalid arguments!", f"```\n{''.join(tbs)}```"
            )
            return

        arg_count = len(args)
        field_list = None
        field_dict = None

        if arg_count == 3:
            try:
                edit_msg_id = int(args[0])
            except ValueError:
                await embed_utils.replace(
                    self.response_msg,
                    "Invalid arguments! A valid integer message id followed by an index and a dictionary or a string is required.",
                    "",
                )
                return

            try:
                edit_msg = await self.invoke_msg.channel.fetch_message(edit_msg_id)
            except discord.NotFound:
                await embed_utils.replace(
                    self.response_msg, "Cannot execute command:", "Invalid message id!"
                )
                return

            if not edit_msg.embeds:
                await embed_utils.replace(
                    self.response_msg,
                    "Cannot execute command:",
                    "No embed data found in message.",
                )
                return

            edit_msg_embed = edit_msg.embeds[0]

            try:
                field_index = int(args[1])
            except ValueError:
                await embed_utils.replace(
                    self.response_msg,
                    "Invalid arguments! A valid integer message id followed by an index and a dictionary or a string is required.",
                    "",
                )
                return

            if isinstance(args[2], dict):
                field_dict = args[2]

            elif isinstance(args[2], str):
                try:
                    field_list = embed_utils.get_fields((args[2],))[0]
                except (TypeError, IndexError):
                    await embed_utils.replace(
                        self.response_msg, "Invalid format for field string!", ""
                    )
                    return

                if len(field_list) == 3:
                    field_dict = {
                        "name": field_list[0],
                        "value": field_list[1],
                        "inline": field_list[2],
                    }

                elif not field_list:
                    await embed_utils.replace(
                        self.response_msg, "Invalid format for field string!", ""
                    )
                    return
            else:
                await embed_utils.replace(
                    self.response_msg,
                    "Invalid arguments! A valid integer message id followed by an index and a dictionary or a string is required.",
                    "",
                )
                return

        else:
            await embed_utils.replace(
                self.response_msg,
                "Invalid arguments! A valid integer message id followed by an index and a dictionary or a string is required.",
                "",
            )
            return

        try:
            await embed_utils.replace_field_from_dict(
                edit_msg, edit_msg_embed, field_dict, field_index
            )
        except IndexError:
            await embed_utils.replace(self.response_msg, "Invalid field index!", "")
            return
        await self.response_msg.delete()
        await self.invoke_msg.delete()

    async def cmd_emsudo_edit_field(self):
        """
        ->type More admin commands
        ->signature pg!emsudo_edit_field [*args]
        ->description Replace an embed field through the bot
        ->extended description
        ```
        pg!emsudo_edit_field ({target_message_id}, {index}, {field_string})
        pg!emsudo_edit_field ({target_message_id}, {index}, {field_dict})
        ```
        Edit parts of an embed field at the given index in the embed of a message in the channel where this command was invoked using the given arguments.
        -----
        Implement pg!emsudo_edit_field, for admins to update fields of embeds sent via the bot
        """

        try:
            args = eval(CodeBlock(self.string).code)
        except Exception as e:
            tbs = traceback.format_exception(type(e), e, e.__traceback__)
            # Pop out the first entry in the traceback, because that's
            # this function call itself
            tbs.pop(1)
            await embed_utils.replace(
                self.response_msg, "Invalid arguments!", f"```\n{''.join(tbs)}```"
            )
            return

        arg_count = len(args)
        field_list = None
        field_dict = None

        if arg_count == 3:
            try:
                edit_msg_id = int(args[0])
            except ValueError:
                await embed_utils.replace(
                    self.response_msg,
                    "Invalid arguments! A valid integer message id followed by an index and a dictionary or a string is required.",
                    "",
                )
                return

            try:
                edit_msg = await self.invoke_msg.channel.fetch_message(edit_msg_id)
            except discord.NotFound:
                await embed_utils.replace(
                    self.response_msg, "Cannot execute command:", "Invalid message id!"
                )
                return

            if not edit_msg.embeds:
                await embed_utils.replace(
                    self.response_msg,
                    "Cannot execute command:",
                    "No embed data found in message.",
                )
                return

            edit_msg_embed = edit_msg.embeds[0]

            try:
                field_index = int(args[1])
            except ValueError:
                await embed_utils.replace(
                    self.response_msg,
                    "Invalid arguments! A valid integer message id followed by an index and a dictionary or a string is required.",
                    "",
                )
                return

            if isinstance(args[2], dict):
                field_dict = args[2]

            elif isinstance(args[2], str):
                try:
                    field_list = embed_utils.get_fields((args[2],))[0]
                except (TypeError, IndexError):
                    await embed_utils.replace(
                        self.response_msg, "Invalid format for field string!", ""
                    )
                    return

                if len(field_list) == 3:
                    field_dict = {
                        "name": field_list[0],
                        "value": field_list[1],
                        "inline": field_list[2],
                    }

                elif not field_list:
                    await embed_utils.replace(
                        self.response_msg, "Invalid format for field string!", ""
                    )
                    return
            else:
                await embed_utils.replace(
                    self.response_msg,
                    "Invalid arguments! A valid integer message id followed by an index and a dictionary or a string is required.",
                    "",
                )
                return
        else:
            await embed_utils.replace(
                self.response_msg,
                "Invalid arguments! A valid integer message id followed by an index and a dictionary or a string is required.",
                "",
            )
            return

        try:
            await embed_utils.edit_field_from_dict(
                edit_msg, edit_msg_embed, field_dict, field_index
            )
        except IndexError:
            await embed_utils.replace(self.response_msg, "Invalid field index!", "")
            return
        except KeyError:
            await embed_utils.replace(
                self.response_msg, "No embed fields found in message.", ""
            )
            return
        await self.response_msg.delete()
        await self.invoke_msg.delete()

    async def cmd_emsudo_edit_fields(self):
        """
        ->type emsudo commands
        ->signature pg!emsudo_edit_fields [*args]
        ->description Edit multiple embed fields through the bot
        ->extended description
        ```
        pg!emsudo_edit_fields ({target_message_id}, {field_string_tuple})
        pg!emsudo_edit_fields ({target_message_id}, {field_dict_tuple})
        pg!emsudo_edit_fields ({target_message_id}, {field_string_or_dict_tuple})
        ```
        Edit multiple embed fields in the embed of a message in the channel where this command was invoked using the given arguments.
        Combining the new fields with the old fields works like a bitwise OR operation, where any embed field argument that is passed
        to this command that is empty (empty `dict` `{}` or empty `str` `''`) will not modify the embed field at it's index when passed to this command.
        -----
        Implement pg!emsudo_edit_fields, for admins to edit multiple embed fields of embeds sent via the bot
        """
        field_dicts_list = []

        if len(self.args) == 3:
            if (
                self.args[0].isnumeric()
                and self.args[1].isnumeric()
                and self.args[2].isnumeric()
            ):
                try:
                    edit_msg = await self.invoke_msg.channel.fetch_message(self.args[0])
                except (discord.NotFound, IndexError, ValueError):
                    await embed_utils.replace(
                        self.response_msg, "Invalid arguments!", ""
                    )
                    return

                if not edit_msg.embeds:
                    await embed_utils.replace(
                        self.response_msg,
                        "Cannot execute command:",
                        "No embed data found in message.",
                    )
                    return

                edit_msg_embed = edit_msg.embeds[0]

                src_channel = self.invoke_msg.author.guild.get_channel(
                    int(self.args[1])
                )

                if not src_channel:
                    await embed_utils.replace(
                        self.response_msg, "Invalid source channel id!", ""
                    )
                    return

                try:
                    attachment_msg = await src_channel.fetch_message(int(self.args[2]))
                except discord.NotFound:
                    await embed_utils.replace(
                        self.response_msg, "Invalid source message id!", ""
                    )
                    return

                if not attachment_msg.attachments:
                    await embed_utils.replace(
                        self.response_msg,
                        "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                        "",
                    )
                    return

                for attachment in attachment_msg.attachments:
                    if (
                        attachment.content_type is not None
                        and attachment.content_type.startswith("text")
                    ):
                        attachment_obj = attachment
                        break
                else:
                    await embed_utils.replace(
                        self.response_msg,
                        "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                        "",
                    )
                    return

                txt_dict = await attachment_obj.read()
                embed_dict = eval(txt_dict.decode())
                if "fields" not in embed_dict:
                    await embed_utils.replace(
                        self.response_msg,
                        "No field attribute found in embed dictionary.",
                        "",
                    )
                    return

                await embed_utils.edit_fields_from_dicts(
                    edit_msg, edit_msg_embed, embed_dict["fields"]
                )
                await self.response_msg.delete()
                await self.invoke_msg.delete()
                return

        elif len(self.args) == 2:
            if self.args[0].isnumeric() and self.args[1].isnumeric():
                try:
                    edit_msg = await self.invoke_msg.channel.fetch_message(self.args[0])
                except (discord.NotFound, IndexError, ValueError):
                    await embed_utils.replace(
                        self.response_msg, "Invalid arguments!", ""
                    )
                    return

                src_channel = self.invoke_msg.channel

                if not edit_msg.embeds:
                    await embed_utils.replace(
                        self.response_msg,
                        "Cannot execute command:",
                        "No embed data found in message.",
                    )
                    return

                edit_msg_embed = edit_msg.embeds[0]

                try:
                    attachment_msg = await src_channel.fetch_message(int(self.args[1]))
                except discord.NotFound:
                    await embed_utils.replace(
                        self.response_msg, "Invalid message id!", ""
                    )
                    return

                if not attachment_msg.attachments:
                    await embed_utils.replace(
                        self.response_msg,
                        "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                        "",
                    )
                    return

                for attachment in attachment_msg.attachments:
                    if (
                        attachment.content_type is not None
                        and attachment.content_type.startswith("text")
                    ):
                        attachment_obj = attachment
                        break
                else:
                    await embed_utils.replace(
                        self.response_msg,
                        "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                        "",
                    )
                    return

                txt_dict = await attachment_obj.read()
                embed_dict = eval(txt_dict.decode())
                if "fields" not in embed_dict:
                    await embed_utils.replace(
                        self.response_msg,
                        "No field attribute found in embed dictionary.",
                        "",
                    )
                    return

                await embed_utils.edit_fields_from_dicts(
                    edit_msg, edit_msg_embed, embed_dict["fields"]
                )
                await self.response_msg.delete()
                await self.invoke_msg.delete()
                return

        try:
            args = eval(CodeBlock(self.string).code)
        except Exception as e:
            tbs = traceback.format_exception(type(e), e, e.__traceback__)
            # Pop out the first entry in the traceback, because that's
            # this function call itself
            tbs.pop(1)
            await embed_utils.replace(
                self.response_msg, "Invalid arguments!", f"```\n{''.join(tbs)}```"
            )
            return

        arg_count = len(args)

        if arg_count == 2:
            try:
                edit_msg_id = int(args[0])
            except ValueError:
                await embed_utils.replace(
                    self.response_msg,
                    "Invalid arguments! A valid integer message id followed by a list/tuple of dictionaries or strings is required.",
                    "",
                )
                return

            try:
                edit_msg = await self.invoke_msg.channel.fetch_message(edit_msg_id)
            except discord.NotFound:
                await embed_utils.replace(
                    self.response_msg, "Cannot execute command:", "Invalid message id!"
                )
                return

            if not edit_msg.embeds:
                await embed_utils.replace(
                    self.response_msg,
                    "Cannot execute command:",
                    "No embed data found in message.",
                )
                return

            edit_msg_embed = edit_msg.embeds[0]

            if isinstance(args[1], (list, tuple)):
                for i, data in enumerate(args[1]):
                    if isinstance(data, dict):
                        field_dicts_list.append(data)

                    elif isinstance(data, str):
                        if data:
                            try:
                                data_list = embed_utils.get_fields((data,))[0]
                            except (TypeError, IndexError):
                                await embed_utils.replace(
                                    self.response_msg,
                                    "Invalid format for field string!",
                                    "",
                                )
                                return

                            if len(data_list) == 3:
                                data_dict = {
                                    "name": data_list[0],
                                    "value": data_list[1],
                                    "inline": data_list[2],
                                }
                            elif len(data_list) == 2:
                                data_dict = {
                                    "name": data_list[0],
                                    "value": data_list[1],
                                    "inline": False,
                                }

                            elif not data_list:
                                await embed_utils.replace(
                                    self.response_msg,
                                    "Invalid format for field string!",
                                    "",
                                )
                                return
                        else:
                            data_dict = {}

                        field_dicts_list.append(data_dict)
                    else:
                        await embed_utils.replace(
                            self.response_msg,
                            f"Invalid field data in input list at index {i}! Must be a dictionary or string.",
                            "",
                        )
                        return

            else:
                await embed_utils.replace(
                    self.response_msg,
                    "Invalid arguments! A valid integer message id followed by a list/tuple of dictionaries or strings is required.",
                    "",
                )
                return

        else:
            await embed_utils.replace(
                self.response_msg,
                "Invalid arguments! A valid integer message id followed by a list/tuple of dictionaries or strings is required.",
                "",
            )
            return

        await embed_utils.edit_fields_from_dicts(
            edit_msg, edit_msg_embed, field_dicts_list
        )

        await self.response_msg.delete()
        await self.invoke_msg.delete()

    async def cmd_emsudo_insert_field(self):
        """
        ->type emsudo commands
        ->signature pg!emsudo_insert_field [*args]
        ->description Insert an embed field through the bot
        ->extended description
        ```
        pg!emsudo_insert_field ({target_message_id}, {index}, {field_string})
        pg!emsudo_insert_field ({target_message_id}, {index}, {field_dict})
        ```
        Insert an embed field at the given index into the embed of a message in the channel where this command was invoked using the given arguments.
        -----
        Implement pg!emsudo_insert_field, for admins to insert fields into embeds sent via the bot
        """

        try:
            args = eval(CodeBlock(self.string).code)
        except Exception as e:
            tbs = traceback.format_exception(type(e), e, e.__traceback__)
            # Pop out the first entry in the traceback, because that's
            # this function call itself
            tbs.pop(1)
            await embed_utils.replace(
                self.response_msg, "Invalid arguments!", f"```\n{''.join(tbs)}```"
            )
            return

        arg_count = len(args)
        field_list = None
        field_dict = None

        if arg_count == 3:
            try:
                edit_msg_id = int(args[0])
            except ValueError:
                await embed_utils.replace(
                    self.response_msg,
                    "Invalid arguments! A valid integer message id followed by an index and a dictionary or a string is required.",
                    "",
                )
                return

            try:
                edit_msg = await self.invoke_msg.channel.fetch_message(edit_msg_id)
            except discord.NotFound:
                await embed_utils.replace(
                    self.response_msg, "Cannot execute command:", "Invalid message id!"
                )
                return

            if not edit_msg.embeds:
                await embed_utils.replace(
                    self.response_msg,
                    "Cannot execute command:",
                    "No embed data found in message.",
                )
                return

            edit_msg_embed = edit_msg.embeds[0]

            try:
                field_index = int(args[1])
            except ValueError:
                await embed_utils.replace(
                    self.response_msg,
                    "Invalid arguments! A valid integer message id followed by an index and a dictionary or a string is required.",
                    "",
                )
                return

            if isinstance(args[2], dict):
                field_dict = args[2]

            elif isinstance(args[2], str):
                try:
                    field_list = embed_utils.get_fields((args[2],))[0]
                except (TypeError, IndexError):
                    await embed_utils.replace(
                        self.response_msg, "Invalid format for field string!", ""
                    )
                    return

                if len(field_list) == 3:
                    field_dict = {
                        "name": field_list[0],
                        "value": field_list[1],
                        "inline": field_list[2],
                    }

                elif not field_list:
                    await embed_utils.replace(
                        self.response_msg, "Invalid format for field string!", ""
                    )
                    return
            else:
                await embed_utils.replace(
                    self.response_msg,
                    "Invalid arguments! A valid integer message id followed by an index and a dictionary or a string is required.",
                    "",
                )
                return

        else:
            await embed_utils.replace(
                self.response_msg,
                "Invalid arguments! A valid integer message id followed by an index and a dictionary or a string is required.",
                "",
            )
            return

        try:
            await embed_utils.insert_field_from_dict(
                edit_msg, edit_msg_embed, field_dict, field_index
            )
        except IndexError:
            await embed_utils.replace(self.response_msg, "Invalid field index!", "")
            return
        await self.response_msg.delete()
        await self.invoke_msg.delete()

    async def cmd_emsudo_insert_fields(self):
        """
        ->type emsudo commands
        ->signature pg!emsudo_insert_fields [*args]
        ->description Insert embed fields through the bot
        ->extended description
        ```
        pg!emsudo_insert_fields {target_message_id} {index} {channel_id}
        pg!emsudo_insert_fields {target_message_id} {index} {channel_id} {message_id}
        pg!emsudo_insert_fields ({target_message_id}, {index}, {field_string_tuple})
        pg!emsudo_insert_fields ({target_message_id}, {index}, {field_dict_tuple})
        pg!emsudo_insert_fields ({target_message_id}, {index}, {field_string_or_dict_tuple})
        ```
        Insert multiple embed fields at the given index into the embed of a message in the channel where this command was invoked using the given arguments.
        -----
        Implement pg!emsudo_insert_fields, for admins to insert multiple fields to embeds sent via the bot
        """

        if len(self.args) == 4:
            if (
                self.args[0].isnumeric()
                and self.args[1].isnumeric()
                and self.args[2].isnumeric()
                and self.args[3].isnumeric()
            ):
                try:
                    edit_msg = await self.invoke_msg.channel.fetch_message(self.args[0])
                except (discord.NotFound, IndexError, ValueError):
                    await embed_utils.replace(
                        self.response_msg, "Invalid arguments!", ""
                    )
                    return

                if not edit_msg.embeds:
                    await embed_utils.replace(
                        self.response_msg,
                        "Cannot execute command:",
                        "No embed data found in message.",
                    )
                    return

                edit_msg_embed = edit_msg.embeds[0]

                try:
                    insert_index = int(self.args[1])
                except ValueError:
                    await embed_utils.replace(
                        self.response_msg, "Invalid field insertion index!", ""
                    )
                    return

                try:
                    src_channel = self.invoke_msg.author.guild.get_channel(
                        int(self.args[2])
                    )
                except ValueError:
                    await embed_utils.replace(
                        self.response_msg, "Invalid source channel id!", ""
                    )
                    return

                if not src_channel:
                    await embed_utils.replace(
                        self.response_msg, "Invalid source channel id!", ""
                    )
                    return

                try:
                    attachment_msg = await src_channel.fetch_message(int(self.args[3]))
                except discord.NotFound:
                    await embed_utils.replace(
                        self.response_msg, "Invalid source message id!", ""
                    )
                    return

                if not attachment_msg.attachments:
                    await embed_utils.replace(
                        self.response_msg,
                        "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                        "",
                    )
                    return

                for attachment in attachment_msg.attachments:
                    if (
                        attachment.content_type is not None
                        and attachment.content_type.startswith("text")
                    ):
                        attachment_obj = attachment
                        break
                else:
                    await embed_utils.replace(
                        self.response_msg,
                        "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                        "",
                    )
                    return

                txt_dict = await attachment_obj.read()
                embed_dict = eval(txt_dict.decode())
                if "fields" not in embed_dict:
                    await embed_utils.replace(
                        self.response_msg,
                        "No field attribute found in embed dictionary.",
                        "",
                    )
                    return

                await embed_utils.insert_fields_from_dicts(
                    edit_msg, edit_msg_embed, embed_dict["fields"], insert_index
                )
                await self.response_msg.delete()
                await self.invoke_msg.delete()
                return

        elif len(self.args) == 3:
            if (
                self.args[0].isnumeric()
                and self.args[1].isnumeric()
                and self.args[2].isnumeric()
            ):
                try:
                    edit_msg = await self.invoke_msg.channel.fetch_message(self.args[0])
                except (discord.NotFound, IndexError, ValueError):
                    await embed_utils.replace(
                        self.response_msg, "Invalid arguments!", ""
                    )
                    return

                if not edit_msg.embeds:
                    await embed_utils.replace(
                        self.response_msg,
                        "Cannot execute command:",
                        "No embed data found in message.",
                    )
                    return

                edit_msg_embed = edit_msg.embeds[0]

                src_channel = self.invoke_msg.channel

                try:
                    insert_index = int(self.args[1])
                except ValueError:
                    await embed_utils.replace(
                        self.response_msg, "Invalid field insertion index!", ""
                    )
                    return

                try:
                    attachment_msg = await src_channel.fetch_message(int(self.args[2]))
                except discord.NotFound:
                    await embed_utils.replace(
                        self.response_msg, "Invalid message id!", ""
                    )
                    return

                if not attachment_msg.attachments:
                    await embed_utils.replace(
                        self.response_msg,
                        "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                        "",
                    )
                    return

                for attachment in attachment_msg.attachments:
                    if (
                        attachment.content_type is not None
                        and attachment.content_type.startswith("text")
                    ):
                        attachment_obj = attachment
                        break
                else:
                    await embed_utils.replace(
                        self.response_msg,
                        "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                        "",
                    )
                    return

                txt_dict = await attachment_obj.read()
                embed_dict = eval(txt_dict.decode())
                if "fields" not in embed_dict:
                    await embed_utils.replace(
                        self.response_msg,
                        "No field attribute found in embed dictionary.",
                        "",
                    )
                    return

                await embed_utils.insert_fields_from_dicts(
                    edit_msg, edit_msg_embed, embed_dict["fields"], insert_index
                )
                await self.response_msg.delete()
                await self.invoke_msg.delete()
                return

        try:
            args = eval(CodeBlock(self.string).code)
        except Exception as e:
            tbs = traceback.format_exception(type(e), e, e.__traceback__)
            # Pop out the first entry in the traceback, because that's
            # this function call itself
            tbs.pop(1)
            await embed_utils.replace(
                self.response_msg, "Invalid arguments!", f"```\n{''.join(tbs)}```"
            )
            return

        arg_count = len(args)

        field_dicts_list = []

        if arg_count == 3:
            try:
                edit_msg_id = int(args[0])
            except ValueError:
                await embed_utils.replace(
                    self.response_msg,
                    "Invalid arguments! A valid integer message id followed by an index and a list/tuple of dictionaries or strings is required.",
                    "",
                )
                return

            try:
                edit_msg = await self.invoke_msg.channel.fetch_message(edit_msg_id)
            except discord.NotFound:
                await embed_utils.replace(
                    self.response_msg, "Cannot execute command:", "Invalid message id!"
                )
                return

            if not edit_msg.embeds:
                await embed_utils.replace(
                    self.response_msg,
                    "Cannot execute command:",
                    "No embed data found in message.",
                )
                return

            edit_msg_embed = edit_msg.embeds[0]

            try:
                field_index = int(args[1])
            except ValueError:
                await embed_utils.replace(
                    self.response_msg,
                    "Invalid arguments! A valid integer message id followed by an index and a list/tuple of dictionaries or strings is required.",
                    "",
                )
                return

            if isinstance(args[2], (list, tuple)):
                for i, data in enumerate(args[2]):
                    if isinstance(data, dict):
                        field_dicts_list.append(data)

                    elif isinstance(data, str):
                        try:
                            data_list = embed_utils.get_fields((data,))[0]
                        except (TypeError, IndexError):
                            await embed_utils.replace(
                                self.response_msg,
                                "Invalid format for field string!",
                                "",
                            )
                            return

                        if len(data_list) == 3:
                            data_dict = {
                                "name": data_list[0],
                                "value": data_list[1],
                                "inline": data_list[2],
                            }

                        elif not data_list:
                            await embed_utils.replace(
                                self.response_msg,
                                "Invalid format for field string!",
                                "",
                            )
                            return

                        field_dicts_list.append(data_dict)
                    else:
                        await embed_utils.replace(
                            self.response_msg,
                            f"Invalid field data in input list at index {i}! Must be a dictionary or string.",
                            "",
                        )
                        return

            else:
                await embed_utils.replace(
                    self.response_msg,
                    "Invalid arguments! A valid integer message id followed by an index and a list/tuple of dictionaries or strings is required.",
                    "",
                )
                return

        else:
            await embed_utils.replace(
                self.response_msg,
                "Invalid arguments! A valid integer message id followed by an index and a list/tuple of dictionaries or strings is required.",
                "",
            )
            return

        await embed_utils.insert_fields_from_dicts(
            edit_msg, edit_msg_embed, reversed(field_dicts_list), field_index
        )
        await self.response_msg.delete()
        await self.invoke_msg.delete()

    async def cmd_emsudo_add_field(self):
        """
        ->type emsudo commands
        ->signature pg!emsudo_add_field [*args]
        ->description Add an embed field through the bot
        ->extended description
        ```
        pg!emsudo_add_field ({target_message_id}, {field_string})
        pg!emsudo_add_field ({target_message_id}, {field_dict})
        ```
        Add an embed field to the embed of a message in the channel where this command was invoked using the given arguments.
        -----
        Implement pg!emsudo_add_field, for admins to add fields to embeds sent via the bot
        """

        try:
            args = eval(CodeBlock(self.string).code)
        except Exception as e:
            tbs = traceback.format_exception(type(e), e, e.__traceback__)
            # Pop out the first entry in the traceback, because that's
            # this function call itself
            tbs.pop(1)
            await embed_utils.replace(
                self.response_msg, "Invalid arguments!", f"```\n{''.join(tbs)}```"
            )
            return

        arg_count = len(args)
        field_list = None
        field_dict = None

        if arg_count == 2:
            try:
                edit_msg_id = int(args[0])
            except ValueError:
                await embed_utils.replace(
                    self.response_msg,
                    "Invalid arguments! A valid integer message id followed by a dictionary or a string is required.",
                    "",
                )
                return

            try:
                edit_msg = await self.invoke_msg.channel.fetch_message(edit_msg_id)
            except discord.NotFound:
                await embed_utils.replace(
                    self.response_msg, "Cannot execute command:", "Invalid message id!"
                )
                return

            if not edit_msg.embeds:
                await embed_utils.replace(
                    self.response_msg,
                    "Cannot execute command:",
                    "No embed data found in message.",
                )
                return

            edit_msg_embed = edit_msg.embeds[0]

            if isinstance(args[1], dict):
                field_dict = args[1]

            elif isinstance(args[1], str):
                try:
                    field_list = embed_utils.get_fields((args[1],))[0]
                except (TypeError, IndexError):
                    await embed_utils.replace(
                        self.response_msg, "Invalid format for field string!", ""
                    )
                    return

                if len(field_list) == 3:
                    field_dict = {
                        "name": field_list[0],
                        "value": field_list[1],
                        "inline": field_list[2],
                    }

                elif not field_list:
                    await embed_utils.replace(
                        self.response_msg, "Invalid format for field string!", ""
                    )
                    return
            else:
                await embed_utils.replace(
                    self.response_msg,
                    "Invalid arguments! A valid integer message id followed by a dictionary or a string is required.",
                    "",
                )
                return

        else:
            await embed_utils.replace(
                self.response_msg,
                "Invalid arguments! A valid integer message id followed by a dictionary or a string is required.",
                "",
            )
            return

        await embed_utils.add_field_from_dict(edit_msg, edit_msg_embed, field_dict)

        await self.response_msg.delete()
        await self.invoke_msg.delete()

    async def cmd_emsudo_add_fields(self):
        """
        ->type emsudo commands
        ->signature pg!emsudo_add_fields [*args]
        ->description Add embed fields through the bot
        ->extended description
        ```
        pg!emsudo_add_fields ({target_message_id}, {field_string_tuple})
        pg!emsudo_add_fields ({target_message_id}, {field_dict_tuple})
        pg!emsudo_add_fields ({target_message_id}, {field_string_or_dict_tuple})
        ```
        Add multiple embed fields to the embed of a message in the channel where this command was invoked using the given arguments.
        -----
        Implement pg!emsudo_add_fields, for admins to add multiple fields to embeds sent via the bot
        """
        field_dicts_list = []

        if len(self.args) == 3:
            if (
                self.args[0].isnumeric()
                and self.args[1].isnumeric()
                and self.args[2].isnumeric()
            ):
                try:
                    edit_msg = await self.invoke_msg.channel.fetch_message(self.args[0])
                except (discord.NotFound, IndexError, ValueError):
                    await embed_utils.replace(
                        self.response_msg, "Invalid arguments!", ""
                    )
                    return

                if not edit_msg.embeds:
                    await embed_utils.replace(
                        self.response_msg,
                        "Cannot execute command:",
                        "No embed data found in message.",
                    )
                    return

                edit_msg_embed = edit_msg.embeds[0]

                src_channel = self.invoke_msg.author.guild.get_channel(
                    int(self.args[1])
                )

                if not src_channel:
                    await embed_utils.replace(
                        self.response_msg, "Invalid source channel id!", ""
                    )
                    return

                try:
                    attachment_msg = await src_channel.fetch_message(int(self.args[2]))
                except discord.NotFound:
                    await embed_utils.replace(
                        self.response_msg, "Invalid source message id!", ""
                    )
                    return

                if not attachment_msg.attachments:
                    await embed_utils.replace(
                        self.response_msg,
                        "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                        "",
                    )
                    return

                for attachment in attachment_msg.attachments:
                    if (
                        attachment.content_type is not None
                        and attachment.content_type.startswith("text")
                    ):
                        attachment_obj = attachment
                        break
                else:
                    await embed_utils.replace(
                        self.response_msg,
                        "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                        "",
                    )
                    return

                txt_dict = await attachment_obj.read()
                embed_dict = eval(txt_dict.decode())
                if "fields" not in embed_dict:
                    await embed_utils.replace(
                        self.response_msg,
                        "No field attribute found in embed dictionary.",
                        "",
                    )
                    return

                await embed_utils.add_fields_from_dicts(
                    edit_msg, edit_msg_embed, embed_dict["fields"]
                )
                await self.response_msg.delete()
                await self.invoke_msg.delete()
                return

        elif len(self.args) == 2:
            if self.args[0].isnumeric() and self.args[1].isnumeric():
                try:
                    edit_msg = await self.invoke_msg.channel.fetch_message(self.args[0])
                except (discord.NotFound, IndexError, ValueError):
                    await embed_utils.replace(
                        self.response_msg, "Invalid arguments!", ""
                    )
                    return

                src_channel = self.invoke_msg.channel

                if not edit_msg.embeds:
                    await embed_utils.replace(
                        self.response_msg,
                        "Cannot execute command:",
                        "No embed data found in message.",
                    )
                    return

                edit_msg_embed = edit_msg.embeds[0]

                try:
                    attachment_msg = await src_channel.fetch_message(int(self.args[1]))
                except discord.NotFound:
                    await embed_utils.replace(
                        self.response_msg, "Invalid message id!", ""
                    )
                    return

                if not attachment_msg.attachments:
                    await embed_utils.replace(
                        self.response_msg,
                        "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                        "",
                    )
                    return

                for attachment in attachment_msg.attachments:
                    if (
                        attachment.content_type is not None
                        and attachment.content_type.startswith("text")
                    ):
                        attachment_obj = attachment
                        break
                else:
                    await embed_utils.replace(
                        self.response_msg,
                        "No valid attachment found in message. It must be a .txt or .py file containing a Python dictionary",
                        "",
                    )
                    return

                txt_dict = await attachment_obj.read()
                embed_dict = eval(txt_dict.decode())
                if "fields" not in embed_dict:
                    await embed_utils.replace(
                        self.response_msg,
                        "No field attribute found in embed dictionary.",
                        "",
                    )
                    return

                await embed_utils.add_fields_from_dicts(
                    edit_msg, edit_msg_embed, embed_dict["fields"]
                )
                await self.response_msg.delete()
                await self.invoke_msg.delete()
                return

        try:
            args = eval(CodeBlock(self.string).code)
        except Exception as e:
            tbs = traceback.format_exception(type(e), e, e.__traceback__)
            # Pop out the first entry in the traceback, because that's
            # this function call itself
            tbs.pop(1)
            await embed_utils.replace(
                self.response_msg, "Invalid arguments!", f"```\n{''.join(tbs)}```"
            )
            return

        arg_count = len(args)

        if arg_count == 2:
            try:
                edit_msg_id = int(args[0])
            except ValueError:
                await embed_utils.replace(
                    self.response_msg,
                    "Invalid arguments! A valid integer message id followed by a list/tuple of dictionaries or strings is required.",
                    "",
                )
                return

            try:
                edit_msg = await self.invoke_msg.channel.fetch_message(edit_msg_id)
            except discord.NotFound:
                await embed_utils.replace(
                    self.response_msg, "Cannot execute command:", "Invalid message id!"
                )
                return

            if not edit_msg.embeds:
                await embed_utils.replace(
                    self.response_msg,
                    "Cannot execute command:",
                    "No embed data found in message.",
                )
                return

            edit_msg_embed = edit_msg.embeds[0]

            if isinstance(args[1], (list, tuple)):
                for i, data in enumerate(args[1]):
                    if isinstance(data, dict):
                        field_dicts_list.append(data)

                    elif isinstance(data, str):
                        try:
                            data_list = embed_utils.get_fields((data,))[0]
                        except (TypeError, IndexError):
                            await embed_utils.replace(
                                self.response_msg,
                                "Invalid format for field string!",
                                "",
                            )
                            return

                        if len(data_list) == 3:
                            data_dict = {
                                "name": data_list[0],
                                "value": data_list[1],
                                "inline": data_list[2],
                            }
                        elif len(data_list) == 2:
                            data_dict = {
                                "name": data_list[0],
                                "value": data_list[1],
                                "inline": False,
                            }

                        elif not data_list:
                            await embed_utils.replace(
                                self.response_msg,
                                "Invalid format for field string!",
                                "",
                            )
                            return

                        field_dicts_list.append(data_dict)
                    else:
                        await embed_utils.replace(
                            self.response_msg,
                            f"Invalid field data in input list at index {i}! Must be a dictionary or string.",
                            "",
                        )
                        return

            else:
                await embed_utils.replace(
                    self.response_msg,
                    "Invalid arguments! A valid integer message id followed by a list/tuple of dictionaries or strings is required.",
                    "",
                )
                return

        else:
            await embed_utils.replace(
                self.response_msg,
                "Invalid arguments! A valid integer message id followed by a list/tuple of dictionaries or strings is required.",
                "",
            )
            return

        await embed_utils.add_fields_from_dicts(
            edit_msg, edit_msg_embed, field_dicts_list
        )

        await self.response_msg.delete()
        await self.invoke_msg.delete()

    async def cmd_emsudo_clone_fields(self):
        """
        ->type emsudo commands
        ->signature pg!emsudo_clone_fields [*args]
        ->description Clone multiple embed fields through the bot
        ->extended description
        ```
        pg!emsudo_clone_fields {target_message_id} {index_1} {index_2}... i={insertion_idx}
        pg!emsudo_clone_fields ({target_message_id}, {range_object}, insertion_idx)
        ```
        Remove embed fields at the given indices of the embed of a message in the channel where this command was invoked using the given arguments.
        If `insertion_idx` is excluded, the cloned fields will be inserted at the index where they were cloned from.
        -----
        Implement pg!emsudo_clone_fields, for admins to remove fields in embeds sent via the bot
        """

        self.check_args(1, 26)

        field_indices = ()
        insertion_index = None
        insertion_index_arg_idx = None
        break_1 = False
        for i, arg in enumerate(self.args):
            if not arg.isnumeric():
                if arg.lower().startswith("i="):
                    try:
                        insertion_index = int(arg[2:])
                    except ValueError:
                        await embed_utils.replace(
                            self.response_msg,
                            "Invalid arguments! A valid integer message id followed by indices and an optional index specifier 'i={n}',"
                            + "or a tuple containing a valid integer message id followed by a `range()` object and an index is required.",
                            "",
                        )
                        return
                    else:
                        insertion_index_arg_idx = i
                else:
                    break_1 = True
                    break

        else:
            if insertion_index_arg_idx:
                self.args.remove(insertion_index_arg_idx)

            try:
                edit_msg_id = int(self.args[0])
            except ValueError:
                await embed_utils.replace(
                    self.response_msg,
                    "Invalid arguments! A valid integer message id followed by indices and an optional index specifier 'i={n}',"
                    + "or a tuple containing a valid integer message id followed by a `range()` object and an index is required.",
                    "",
                )
                return

            try:
                edit_msg = await self.invoke_msg.channel.fetch_message(edit_msg_id)
            except discord.NotFound:
                await embed_utils.replace(
                    self.response_msg, "Cannot execute command:", "Invalid message id!"
                )
                return

            if not edit_msg.embeds:
                await embed_utils.replace(
                    self.response_msg,
                    "Cannot execute command:",
                    "No embed data found in message.",
                )
                return

            edit_msg_embed = edit_msg.embeds[0]

            try:
                field_indices = tuple(int(index) for index in self.args[1:])
            except ValueError:
                await embed_utils.replace(
                    self.response_msg,
                    "Invalid arguments! A valid integer message id followed by indices and an optional index specifier 'i={n}',"
                    + "or a tuple containing a valid integer message id followed by a `range()` object and an index is required.",
                    "",
                )
                return

        if break_1:
            try:
                args = eval(
                    CodeBlock(self.string, strip_lang=True, strip_ticks=True).code
                )
            except Exception as e:
                tbs = traceback.format_exception(type(e), e, e.__traceback__)
                # Pop out the first entry in the traceback, because that's
                # this function call itself
                tbs.pop(1)
                await embed_utils.replace(
                    self.response_msg, "Invalid arguments!", f"```\n{''.join(tbs)}```"
                )
                return

            if isinstance(args, tuple):
                if len(args) >= 2:
                    try:
                        edit_msg_id = int(args[0])
                    except ValueError:
                        await embed_utils.replace(
                            self.response_msg,
                            "Invalid arguments! A valid integer message id followed by indices and an optional index specifier 'i={n}',"
                            + "or a tuple containing a valid integer message id followed by a `range()` object and an index is required.",
                            "",
                        )
                        return

                    try:
                        edit_msg = await self.invoke_msg.channel.fetch_message(
                            edit_msg_id
                        )
                    except discord.NotFound:
                        await embed_utils.replace(
                            self.response_msg,
                            "Cannot execute command:",
                            "Invalid message id!",
                        )
                        return

                    if not edit_msg.embeds:
                        await embed_utils.replace(
                            self.response_msg,
                            "Cannot execute command:",
                            "No embed data found in message.",
                        )
                        return

                    edit_msg_embed = edit_msg.embeds[0]

                    if len(args) > 2:
                        try:
                            insertion_index = int(args[2])
                        except ValueError:
                            await embed_utils.replace(
                                self.response_msg,
                                "Invalid arguments! A valid integer message id followed by indices and an optional index specifier 'i={n}',"
                                + "or a tuple containing a valid integer message id followed by a `range()` object and an index is required.",
                                "",
                            )
                            return

                    if isinstance(args[1], range):
                        if len(args[1]) > 25:
                            await embed_utils.replace(
                                self.response_msg,
                                "Invalid range object passed as an argument!",
                                "",
                            )
                            return

                        field_indices = tuple(args[1])
                    else:
                        await embed_utils.replace(
                            self.response_msg,
                            "Invalid arguments! A valid integer message id followed by indices and an optional index specifier 'i={n}',"
                            + "or a tuple containing a valid integer message id followed by a `range()` object and an index is required.",
                            "",
                        )
                        return

            else:
                await embed_utils.replace(
                    self.response_msg,
                    "Invalid arguments! A valid integer message id followed by indices and an optional index specifier 'i={n}',"
                    + "or a tuple containing a valid integer message id followed by a `range()` object and an index is required.",
                    "",
                )
                return

        try:
            await embed_utils.clone_fields(
                edit_msg, edit_msg_embed, field_indices, insertion_index=insertion_index
            )
        except IndexError:
            await embed_utils.replace(
                self.response_msg, "Invalid field index/indices!", ""
            )
            return

        await self.response_msg.delete()
        await self.invoke_msg.delete()

    async def cmd_emsudo_swap_fields(self):
        """
        ->type emsudo commands
        ->signature pg!emsudo_swap_fields [*args]
        ->description Swap embed fields through the bot
        ->extended description
        ```
        pg!emsudo_swap_fields {target_message_id} {index_a} {index_b}
        ```
        Swap the positions of embed fields at the given indices of the embed of a message in the channel where this command was invoked using the given arguments.
        -----
        Implement pg!emsudo_swap_fields, for admins to swap fields in embeds sent via the bot
        """

        self.check_args(3)

        try:
            edit_msg_id = int(self.args[0])
        except ValueError:
            await embed_utils.replace(
                self.response_msg,
                "Invalid arguments! A valid integer message id followed by two indices is required.",
                "",
            )
            return

        try:
            edit_msg = await self.invoke_msg.channel.fetch_message(edit_msg_id)
        except discord.NotFound:
            await embed_utils.replace(
                self.response_msg, "Cannot execute command:", "Invalid message id!"
            )
            return

        if not edit_msg.embeds:
            await embed_utils.replace(
                self.response_msg,
                "Cannot execute command:",
                "No embed data found in message.",
            )
            return

        edit_msg_embed = edit_msg.embeds[0]

        try:
            field_index_a = int(self.args[1])
        except ValueError:
            await embed_utils.replace(
                self.response_msg,
                "Invalid arguments! A valid integer message id followed by two indices is required.",
                "",
            )
            return

        try:
            field_index_b = int(self.args[2])
        except ValueError:
            await embed_utils.replace(
                self.response_msg,
                "Invalid arguments! A valid integer message id followed by two indices is required.",
                "",
            )
            return

        try:
            await embed_utils.swap_fields(
                edit_msg, edit_msg_embed, field_index_a, field_index_b
            )
        except IndexError:
            await embed_utils.replace(self.response_msg, "Invalid field index!", "")
            return

        await self.response_msg.delete()
        await self.invoke_msg.delete()

    async def cmd_emsudo_remove_fields(self):
        """
        ->type emsudo commands
        ->signature pg!emsudo_remove_fields [*args]
        ->description Remove an embed field through the bot
        ->extended description
        ```
        pg!emsudo_remove_fields {target_message_id} {index_1} {index_2}...
        pg!emsudo_remove_fields ({target_message_id}, {range_object})
        ```
        Remove embed fields at the given indices of the embed of a message in the channel where this command was invoked using the given arguments.
        -----
        Implement pg!emsudo_remove_fields, for admins to remove fields in embeds sent via the bot
        """

        self.check_args(1, 26)

        field_indices = ()
        if all(arg.isnumeric() for arg in self.args):
            try:
                edit_msg_id = int(self.args[0])
            except ValueError:
                await embed_utils.replace(
                    self.response_msg,
                    "Invalid arguments! A valid integer message id followed by indices,"
                    + "or a valid integer message id followed by a comma and a `range()` object is required.",
                    "",
                )
                return

            try:
                edit_msg = await self.invoke_msg.channel.fetch_message(edit_msg_id)
            except discord.NotFound:
                await embed_utils.replace(
                    self.response_msg, "Cannot execute command:", "Invalid message id!"
                )
                return

            if not edit_msg.embeds:
                await embed_utils.replace(
                    self.response_msg,
                    "Cannot execute command:",
                    "No embed data found in message.",
                )
                return

            edit_msg_embed = edit_msg.embeds[0]

            try:
                field_indices = tuple(int(index) for index in self.args[1:])
            except ValueError:
                await embed_utils.replace(
                    self.response_msg,
                    "Invalid arguments! A valid integer message id followed by indices,"
                    + "or a valid integer message id followed by a comma and a `range()` object is required.",
                    "",
                )
                return

        else:
            try:
                args = eval(
                    CodeBlock(self.string, strip_lang=True, strip_ticks=True).code
                )
            except Exception as e:
                tbs = traceback.format_exception(type(e), e, e.__traceback__)
                # Pop out the first entry in the traceback, because that's
                # this function call itself
                tbs.pop(1)
                await embed_utils.replace(
                    self.response_msg, "Invalid arguments!", f"```\n{''.join(tbs)}```"
                )
                return

            if isinstance(args, tuple) and len(args) == 2:
                try:
                    edit_msg_id = int(args[0])
                except ValueError:
                    await embed_utils.replace(
                        self.response_msg,
                        "Invalid arguments! A valid integer message id followed by indices,"
                        + "or a valid integer message id followed by a comma and a `range()` object is required.",
                        "",
                    )
                    return

                try:
                    edit_msg = await self.invoke_msg.channel.fetch_message(edit_msg_id)
                except discord.NotFound:
                    await embed_utils.replace(
                        self.response_msg,
                        "Cannot execute command:",
                        "Invalid message id!",
                    )
                    return

                if not edit_msg.embeds:
                    await embed_utils.replace(
                        self.response_msg,
                        "Cannot execute command:",
                        "No embed data found in message.",
                    )
                    return

                edit_msg_embed = edit_msg.embeds[0]

                if isinstance(args[1], range):
                    if len(args[1]) > 25:
                        await embed_utils.replace(
                            self.response_msg,
                            "Invalid range object passed as an argument!",
                            "",
                        )
                        return

                    field_indices = tuple(args[1])
                else:
                    await embed_utils.replace(
                        self.response_msg,
                        "Invalid arguments! A valid integer message id followed by indices,"
                        + "or a valid integer message id followed by a comma and a `range()` object is required.",
                        "",
                    )
                    return

            else:
                await embed_utils.replace(
                    self.response_msg,
                    "Invalid arguments! A valid integer message id followed by indices,"
                    + "or a valid integer message id followed by a comma and a `range()` object is required.",
                    "",
                )
                return

        try:
            await embed_utils.remove_fields(edit_msg, edit_msg_embed, field_indices)
        except IndexError:
            await embed_utils.replace(self.response_msg, "Invalid field index!", "")
            return

        await self.response_msg.delete()
        await self.invoke_msg.delete()

    async def cmd_emsudo_clear_fields(self):
        """
        ->type emsudo commands
        ->signature pg!emsudo_clear_fields [*args]
        ->description Remove all embed fields through the bot
        ->extended description
        ```
        pg!emsudo_clear_fields {target_message_id}
        ```
        Remove all embed fields of the embed of a message in the channel where this command was invoked using the given arguments.
        -----
        Implement pg!emsudo_clear_fields, for admins to remove fields in embeds sent via the bot
        """

        self.check_args(1)

        try:
            edit_msg_id = int(self.args[0])
        except ValueError:
            await embed_utils.replace(
                self.response_msg,
                "Invalid argument! A valid integer message id is required.",
                "",
            )
            return

        try:
            edit_msg = await self.invoke_msg.channel.fetch_message(edit_msg_id)
        except discord.NotFound:
            await embed_utils.replace(
                self.response_msg, "Cannot execute command:", "Invalid message id!"
            )
            return

        if not edit_msg.embeds:
            await embed_utils.replace(
                self.response_msg,
                "Cannot execute command:",
                "No embed data found in message.",
            )
            return

        edit_msg_embed = edit_msg.embeds[0]

        await embed_utils.clear_fields(edit_msg, edit_msg_embed)
        await self.response_msg.delete()
        await self.invoke_msg.delete()

    async def cmd_emsudo_get(self):
        """
        ->type emsudo commands
        ->signature pg!emsudo_get [*args]
        ->description Get the embed data of a message
        ->extended description
        ```
        pg!emsudo_get {message_id} {optional_embed_attr} {optional_embed_attr}...
        pg!emsudo_get {channel_id} {message_id} {optional_embed_attr} {optional_embed_attr}...
        ```
        Get the contents of the embed of a message from the given arguments and send it as another message (with a `.txt` file attachment containing the embed data as a Python dictionary) to the channel where this command was invoked.
        If specific embed attributes are specified, then only those will be fetched from the embed of the given message, otherwise all attributes will be fetched.
        ->example command pg!emsudo_get 123456789123456789 title
        pg!emsudo_get 123456789123456789 98765432198765444321 description fields
        pg!emsudo_get 123456789123456789 98765432198765444321
        -----
        Implement pg!emsudo_get, to return the embed of a message as a dictionary in a text file.
        """
        self.check_args(1, maxarg=38)

        src_msg_id = None
        src_msg = None
        src_channel_id = self.invoke_msg.channel.id
        src_channel = self.invoke_msg.channel
        embed_attr_keys = set(
            (
                "author",
                "provider",
                "title",
                "url",
                "description",
                "type",
                "color",
                "fields",
                "thumbnail",
                "image",
                "footer",
                "timestamp",
            )
        )
        reduced_embed_attr_keys = set()
        filtered_field_indices = []
        offset_idx_2 = None

        if len(self.args) > 1:
            offset_idx = 0
            if self.args[0].isnumeric():
                if self.args[1].isnumeric():
                    offset_idx = 2
                    try:
                        src_channel_id = int(self.args[0])
                        src_msg_id = int(self.args[1])
                    except ValueError:
                        await embed_utils.replace(
                            self.response_msg,
                            "Cannot execute command:",
                            "Invalid message and/or channel id(s)!",
                        )
                        return

                    src_channel = self.invoke_msg.author.guild.get_channel(
                        src_channel_id
                    )
                    if src_channel is None:
                        await embed_utils.replace(
                            self.response_msg,
                            "Cannot execute command:",
                            "Invalid channel id!",
                        )
                        return
                else:
                    offset_idx = 1
                    try:
                        src_msg_id = int(self.args[0])
                    except ValueError:
                        await embed_utils.replace(
                            self.response_msg,
                            "Cannot execute command:",
                            "Invalid message id!",
                        )
                        return

            for i in range(offset_idx, len(self.args)):
                if self.args[i] == "fields":
                    reduced_embed_attr_keys.add("fields")
                    for j in range(i + 1, len(self.args)):
                        if self.args[j].isnumeric():
                            filtered_field_indices.append(int(self.args[j]))
                        else:
                            offset_idx_2 = j
                            break
                    else:
                        break

                    if offset_idx_2:
                        break

                elif self.args[i] in embed_attr_keys:
                    reduced_embed_attr_keys.add(self.args[i])
                else:
                    await embed_utils.replace(
                        self.response_msg,
                        "Cannot execute command:",
                        "Invalid embed attribute names!",
                    )
                    return

            if offset_idx_2:
                for i in range(offset_idx_2, len(self.args)):
                    if self.args[i] in embed_attr_keys:
                        reduced_embed_attr_keys.add(self.args[i])
                    else:
                        await embed_utils.replace(
                            self.response_msg,
                            "Cannot execute command:",
                            "Invalid embed attribute names!",
                        )
                        return

        elif len(self.args) == 2:
            try:
                src_channel_id = int(self.args[0])
                src_msg_id = int(self.args[1])
            except ValueError:
                await embed_utils.replace(
                    self.response_msg,
                    "Cannot execute command:",
                    "Invalid message and/or channel id(s)!",
                )
                return

            src_channel = self.invoke_msg.author.guild.get_channel(src_channel_id)
            if src_channel is None:
                await embed_utils.replace(
                    self.response_msg, "Cannot execute command:", "Invalid channel id!"
                )
                return
        else:
            try:
                src_msg_id = int(self.args[0])
            except ValueError:
                await embed_utils.replace(
                    self.response_msg, "Cannot execute command:", "Invalid message id!"
                )
                return
        try:
            src_msg = await src_channel.fetch_message(src_msg_id)
        except discord.NotFound:
            await embed_utils.replace(
                self.response_msg, "Cannot execute command:", "Invalid message id!"
            )
            return

        if not src_msg.embeds:
            await embed_utils.replace(
                self.response_msg,
                "Cannot execute command:",
                "No embed data found in message.",
            )
            return

        embed_dict = src_msg.embeds[0].to_dict()

        if reduced_embed_attr_keys:
            for key in tuple(embed_dict.keys()):
                if key not in reduced_embed_attr_keys:
                    del embed_dict[key]

            if (
                "fields" in reduced_embed_attr_keys
                and "fields" in embed_dict
                and filtered_field_indices
            ):
                embed_dict["fields"] = [
                    embed_dict["fields"][idx] for idx in sorted(filtered_field_indices)
                ]

        embed_dict_code = repr({k: embed_dict[k] for k in reversed(embed_dict.keys())})

        with open("embeddata.txt", "w", encoding="utf-8") as embed_txt:
            embed_txt.write(black.format_str(embed_dict_code, mode=black.FileMode()))

        await self.response_msg.channel.send(
            embed=await embed_utils.send_2(
                None,
                author_name="Embed Data",
                title=embed_dict.get("title", "(add a title by editing this embed)"),
                fields=(
                    (
                        "\u2800",
                        f"**[View Original Message](https://discord.com/channels/{src_msg.author.guild.id}/{src_channel.id}/{src_msg.id})**",
                        True,
                    ),
                ),
            ),
            file=discord.File("embeddata.txt"),
        )
        await self.response_msg.delete()

    async def cmd_emsudo_clone(self):
        """
        ->type emsudo commands
        ->signature pg!emsudo_clone [*args]
        ->description Clone all embeds.
        ->extended description
        ```
        pg!emsudo_clone {message_id}
        pg!emsudo_clone {channel_id} {message_id}
        ```
        Get a message from the given arguments and send it as another message (only containing its embed) to the channel where this command was invoked.
        -----
        Implement pg!_emsudo_clone, to get the embed of a message and send it.
        """
        self.check_args(1, maxarg=2)

        src_msg_id = None
        src_msg = None
        src_channel_id = self.invoke_msg.channel.id
        src_channel = self.invoke_msg.channel

        if len(self.args) == 2:
            try:
                src_channel_id = int(self.args[0])
                src_msg_id = int(self.args[1])
            except ValueError:
                await embed_utils.replace(
                    self.response_msg,
                    "Cannot execute command:",
                    "Invalid message and/or channel id(s)!",
                )
                return

            src_channel = self.invoke_msg.author.guild.get_channel(src_channel_id)
            if src_channel is None:
                await embed_utils.replace(
                    self.response_msg, "Cannot execute command:", "Invalid channel id!"
                )
                return
        else:
            try:
                src_msg_id = int(self.args[0])
            except ValueError:
                await embed_utils.replace(
                    self.response_msg, "Cannot execute command:", "Invalid message id!"
                )
                return

        try:
            src_msg = await src_channel.fetch_message(src_msg_id)
        except discord.NotFound:
            await embed_utils.replace(
                self.response_msg, "Cannot execute command:", "Invalid message id!"
            )
            return

        if not src_msg.embeds:
            await embed_utils.replace(
                self.response_msg,
                "Cannot execute command:",
                "No embed data found in message.",
            )
            return

        for embed in src_msg.embeds:
            await self.response_msg.channel.send(embed=embed)

        await self.response_msg.delete()
