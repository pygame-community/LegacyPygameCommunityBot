"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file defines the command handler class for the emsudo commands of the bot
"""

from __future__ import annotations

import asyncio
import io
from ast import literal_eval
from typing import Optional, Union

import black
import discord
from discord.embeds import EmptyEmbed

from pgbot import embed_utils, utils
from pgbot.commands.base import BaseCommand, BotException, CodeBlock, String


class EmsudoCommand(BaseCommand):
    """
    Base class to handle emsudo commands.
    """

    async def cmd_emsudo(
        self,
        *datas: Optional[Union[discord.Message, CodeBlock, String, bool]],
    ):
        """
        ->type emsudo commands
        ->signature pg!emsudo [data] [data]...
        ->description Send embeds through the bot
        ->extended description
        Generate embeds from the given arguments and send them with a message
        to the channel where this command was invoked. If the optional arguments `[data]`
        are omitted, attempt to read input data from an attachment in the message that invoked
        this command.
        -----
        Implement pg!emsudos, for admins to send multiple embeds via the bot
        """

        for i, data in enumerate(datas):
            await self.invoke_msg.channel.trigger_typing()

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

            attachment_msg: discord.Message = None
            only_description = False

            if data is False:
                attachment_msg = self.invoke_msg

            elif isinstance(data, String):
                if not data.string:
                    attachment_msg = self.invoke_msg
                else:
                    only_description = True
                    util_send_embed_args.update(description=data.string)

            elif isinstance(data, discord.Message):
                attachment_msg = data

            if attachment_msg:
                if not attachment_msg.attachments:
                    await embed_utils.send_2(
                        self.response_msg.channel,
                        title=f"Input {i}: No valid attachment found in message.",
                        description="It must be a `.txt`, `.py` file containing a Python dictionary,"
                        " or a `.json` file containing embed data.",
                        color=0xFF0000,
                    )
                    continue

                for attachment in attachment_msg.attachments:
                    if (
                        attachment.content_type is not None
                        and attachment.content_type.startswith(
                            ("text", "application/json")
                        )
                    ):
                        attachment_obj = attachment
                        break
                else:
                    await embed_utils.send_2(
                        self.response_msg.channel,
                        title=f"Input {i}: No valid attachment found in message.",
                        description="It must be a `.txt`, `.py` file containing a Python dictionary,"
                        " or a `.json` file containing embed data.",
                        color=0xFF0000,
                    )
                    continue

                embed_data = await attachment_obj.read()
                embed_data = embed_data.decode()

                if attachment_obj.content_type.startswith("application/json"):
                    embed_dict = embed_utils.import_embed_data(
                        embed_data, from_json_string=True
                    )
                else:
                    embed_dict = embed_utils.import_embed_data(
                        embed_data, from_string=True
                    )

                await embed_utils.send_from_dict(self.invoke_msg.channel, embed_dict)
                continue

            if not only_description:
                try:
                    args = literal_eval(data.code)
                except Exception as e:
                    await embed_utils.send_2(
                        self.response_msg.channel,
                        title=f"Input {i}: Invalid arguments!",
                        description=f"```\n{''.join(utils.format_code_exception(e))}```",
                        color=0xFF0000,
                    )
                    continue

                if isinstance(args, dict):
                    await embed_utils.send_from_dict(self.invoke_msg.channel, args)
                    continue

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
                    await embed_utils.send_2(
                        self.response_msg.channel,
                        title=f"Input {i}: Invalid arguments!",
                        color=0xFF0000,
                    )
                    continue

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
                        fields = embed_utils.get_fields(*args[4])
                        for f in fields:
                            if isinstance(f, list):
                                util_send_embed_args.update(
                                    fields=fields
                                )
                            else:
                                util_send_embed_args.update(
                                    fields=[fields]
                                )
                            break
                    except TypeError:
                        await embed_utils.send_2(
                            self.response_msg.channel,
                            title=f"Input {i}: Invalid format for field string(s)!",
                            description=' The format should be `"<name|value|inline>"`',
                            color=0xFF0000,
                        )
                        continue

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
            await asyncio.sleep(0)

        if not datas:
            attachment_msg = self.invoke_msg
            if not attachment_msg.attachments:
                raise BotException(
                    f"No valid attachment found in message.",
                    "It must be a `.txt`, `.py` file containing a Python dictionary,"
                    " or a `.json` file containing embed data.",
                )

            for attachment in attachment_msg.attachments:
                if (
                    attachment.content_type is not None
                    and attachment.content_type.startswith(("text", "application/json"))
                ):
                    attachment_obj = attachment
                    break
            else:
                raise BotException(
                    f"No valid attachment found in message.",
                    "It must be a `.txt`, `.py` file containing a Python dictionary,"
                    " or a `.json` file containing embed data.",
                )

            embed_data = await attachment_obj.read()
            embed_data = embed_data.decode()

            if attachment_obj.content_type.startswith("application/json"):
                embed_dict = embed_utils.import_embed_data(
                    embed_data, from_json_string=True
                )
            else:
                embed_dict = embed_utils.import_embed_data(embed_data, from_string=True)

            await embed_utils.send_from_dict(self.invoke_msg.channel, embed_dict)

        await self.response_msg.delete()
        await self.invoke_msg.delete()

    async def cmd_emsudo_replace(
        self,
        msg: discord.Message,
        data: Optional[Union[discord.Message, CodeBlock, String]] = None,
    ):
        """
        ->type emsudo commands
        ->signature pg!emsudo_replace <message> [data]
        ->description Replace an embed through the bot
        ->extended description
        Replace the embed of a message in the channel where this command was invoked using the given arguments.
        If the optional argument `[data]` is omitted, attempt to read input data from an attachment in the message that invoked
        this command.
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

        attachment_msg: discord.Message = None
        only_description = False

        if data is None:
            attachment_msg = self.invoke_msg

        elif isinstance(data, String):
            if not data.string:
                attachment_msg = self.invoke_msg
            else:
                only_description = True
                util_replace_embed_args.update(description=data.string)

        elif isinstance(data, discord.Message):
            attachment_msg = data

        if attachment_msg:
            if not attachment_msg.attachments:
                raise BotException(
                    "No valid attachment found in message.",
                    "It must be a `.txt`, `.py` file containing a Python dictionary,"
                    " or a `.json` file containing embed data.",
                )

            for attachment in attachment_msg.attachments:
                if (
                    attachment.content_type is not None
                    and attachment.content_type.startswith(("text", "application/json"))
                ):
                    attachment_obj = attachment
                    break
            else:
                raise BotException(
                    "No valid attachment found in message.",
                    "It must be a `.txt`, `.py` file containing a Python dictionary,"
                    " or a `.json` file containing embed data.",
                )

            embed_data = await attachment_obj.read()
            embed_data = embed_data.decode()

            if attachment_obj.content_type.startswith("application/json"):
                embed_dict = embed_utils.import_embed_data(
                    embed_data, from_json_string=True
                )
            else:
                embed_dict = embed_utils.import_embed_data(embed_data, from_string=True)

            await embed_utils.replace_from_dict(msg, embed_dict)
            await self.response_msg.delete()
            await self.invoke_msg.delete()
            return

        if not only_description:
            try:
                args = literal_eval(data.code)
            except Exception as e:
                raise BotException(
                    "Invalid arguments!",
                    f"```\n{''.join(utils.format_code_exception(e))}```",
                )

            if isinstance(args, dict):
                await embed_utils.replace_from_dict(msg, args)
                await self.response_msg.delete()
                await self.invoke_msg.delete()
                return

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

                else:
                    util_replace_embed_args.update(
                        author_name=args[0],
                    )
            else:
                raise BotException("Invalid arguments!", "")

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
                    fields = embed_utils.get_fields(*args[4])
                    for f in fields:
                        if isinstance(f, list):
                            util_replace_embed_args.update(
                                fields=fields
                            )
                        else:
                            util_replace_embed_args.update(
                                fields=[fields]
                            )
                        break
                except TypeError:
                    await embed_utils.send_2(
                        self.response_msg.channel,
                        title=f"Input {i}: Invalid format for field string(s)!",
                        description=' The format should be `"<name|value|inline>"`',
                        color=0xFF0000,
                    )

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

        await embed_utils.replace_2(msg, **util_replace_embed_args)
        await self.response_msg.delete()
        await self.invoke_msg.delete()

    async def cmd_emsudo_add(
        self,
        msg: discord.Message,
        data: Optional[Union[discord.Message, CodeBlock, String]] = None,
        overwrite: bool = False,
    ):
        """
        ->type emsudo commands
        ->signature pg!emsudo_add <message> [data] [overwrite]
        ->description Add an embed through the bot
        ->extended description
        Add an embed to a message in the channel where this command was invoked using the given arguments.
        If the optional argument `[data]` is omitted, attempt to read input data from an attachment in the message that invoked
        this command.
        -----
        Implement pg!emsudo_add, for admins to add embeds to messages via the bot
        """

        if not msg.embeds or overwrite:
            await self.cmd_emsudo_replace(msg=msg, data=data)
        else:
            raise BotException(
                "Cannot overwrite embed!",
                "The given message's embed cannot be overwritten when"
                " `overwrite=` is set to `False`",
            )

    async def cmd_emsudo_remove(self, *msgs: discord.Message):
        """
        ->type emsudo commands
        ->signature pg!emsudo_remove <message> [<message>...]
        ->description Remove an embed through the bot
        -----
        Implement pg!emsudo_remove, for admins to remove embeds from messages via the bot
        """

        if not msgs:
            raise BotException(
                f"Invalid arguments!",
                "No message IDs given as input.",
            )

        for i, msg in enumerate(msgs):
            await self.response_msg.channel.trigger_typing()
            if not msg.embeds:
                raise BotException(
                    f"Input {i}: Cannot execute command:",
                    "No embed data found in message.",
                )
            await msg.edit(embed=None)
            await asyncio.sleep(0)

        await self.response_msg.delete()
        await self.invoke_msg.delete()

    async def cmd_emsudo_edit(
        self,
        msg: discord.Message,
        *datas: Optional[Union[discord.Message, CodeBlock, String, bool]],
    ):
        """
        ->type emsudo commands
        ->signature pg!emsudo_edit <message> [data] [data]...
        ->description Edit an embed through the bot
        ->extended description
        Update the given attributes of an embed of a message in the channel where this command was invoked using the given arguments.
        -----
        Implement pg!emsudo_edit, for admins to replace embeds via the bot
        """

        if not msg.embeds:
            raise BotException(
                "Cannot execute command:",
                "No embed data found in message.",
            )

        msg_embed = msg.embeds[0]

        for i, data in enumerate(datas):
            await self.invoke_msg.channel.trigger_typing()

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

            attachment_msg: discord.Message = None
            only_description = False

            if data is False:
                attachment_msg = self.invoke_msg

            elif isinstance(data, String):
                if not data.string:
                    attachment_msg = self.invoke_msg
                else:
                    only_description = True
                    util_edit_embed_args.update(description=data.string)

            elif isinstance(data, discord.Message):
                attachment_msg = data

            if attachment_msg:
                if not attachment_msg.attachments:
                    await embed_utils.send_2(
                        self.response_msg.channel,
                        title=f"Input {i}: No valid attachment found in message.",
                        description="It must be a `.txt`, `.py` file containing a Python dictionary,"
                        " or a `.json` file containing embed data.",
                        color=0xFF0000,
                    )
                    continue

                for attachment in attachment_msg.attachments:
                    if (
                        attachment.content_type is not None
                        and attachment.content_type.startswith(
                            ("text", "application/json")
                        )
                    ):
                        attachment_obj = attachment
                        break
                else:
                    await embed_utils.send_2(
                        self.response_msg.channel,
                        title=f"Input {i}: No valid attachment found in message.",
                        description="It must be a `.txt`, `.py` file containing a Python dictionary,"
                        " or a `.json` file containing embed data.",
                        color=0xFF0000,
                    )
                    continue

                embed_data = await attachment_obj.read()
                embed_data = embed_data.decode()

                if attachment_obj.content_type.startswith("application/json"):
                    embed_dict = embed_utils.import_embed_data(
                        embed_data, from_json_string=True
                    )
                else:
                    embed_dict = embed_utils.import_embed_data(
                        embed_data, from_string=True
                    )

                await embed_utils.edit_from_dict(msg, msg_embed, embed_dict)
                continue

            if not only_description:
                try:
                    args = literal_eval(data.code)
                except Exception as e:
                    await embed_utils.send_2(
                        self.response_msg.channel,
                        title=f"Input {i}: Invalid arguments!",
                        description=f"```\n{''.join(utils.format_code_exception(e))}```",
                        color=0xFF0000,
                    )
                    continue

                if isinstance(args, dict):
                    await embed_utils.edit_from_dict(msg, msg_embed, args)
                    continue

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

                    else:
                        util_edit_embed_args.update(
                            author_name=args[0],
                        )
                else:
                    await embed_utils.send_2(
                        self.response_msg.channel,
                        title=f"Input {i}: Invalid arguments!",
                        color=0xFF0000,
                    )
                    continue

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
                        fields = embed_utils.get_fields(*args[4])
                        for f in fields:
                            if isinstance(f, list):
                                util_edit_embed_args.update(
                                    fields=fields
                                )
                            else:
                                util_edit_embed_args.update(
                                    fields=[fields]
                                )
                            break
                    except TypeError:
                        await embed_utils.send_2(
                            self.response_msg.channel,
                            title=f"Input {i}: Invalid format for field string(s)!",
                            description=' The format should be `"<name|value|inline>"`',
                            color=0xFF0000,
                        )
                        continue

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

            await embed_utils.edit_2(msg, msg_embed, **util_edit_embed_args)
            await asyncio.sleep(0)

        if not datas:
            attachment_msg = self.invoke_msg
            if not attachment_msg.attachments:
                raise BotException(
                    f"No valid attachment found in message.",
                    "It must be a `.txt`, `.py` file containing a Python dictionary,"
                    " or a `.json` file containing embed data.",
                )

            for attachment in attachment_msg.attachments:
                if (
                    attachment.content_type is not None
                    and attachment.content_type.startswith(("text", "application/json"))
                ):
                    attachment_obj = attachment
                    break
            else:
                raise BotException(
                    f"No valid attachment found in message.",
                    "It must be a `.txt`, `.py` file containing a Python dictionary,"
                    " or a `.json` file containing embed data.",
                )

            embed_data = await attachment_obj.read()
            embed_data = embed_data.decode()

            if attachment_obj.content_type.startswith("application/json"):
                embed_dict = embed_utils.import_embed_data(
                    embed_data, from_json_string=True
                )
            else:
                embed_dict = embed_utils.import_embed_data(embed_data, from_string=True)

            await embed_utils.edit_from_dict(msg, msg_embed, embed_dict)

        await self.response_msg.delete()
        await self.invoke_msg.delete()

    async def cmd_emsudo_clone(self, *msgs: discord.Message):
        """
        ->type emsudo commands
        ->signature pg!emsudo_clone <message> [<message>...]
        ->description Clone all embeds.
        ->extended description
        Get a message from the given arguments and send it as another message (only containing its embed) to the channel where this command was invoked.
        -----
        Implement pg!_emsudo_clone, to get the embed of a message and send it.
        """

        if not msgs:
            raise BotException(
                f"Invalid arguments!",
                "No message IDs given as input.",
            )

        for i, msg in enumerate(msgs):
            await self.response_msg.channel.trigger_typing()

            if not msg.embeds:
                await embed_utils.send_2(
                    self.response_msg.channel,
                    title=f"Input {i}: Cannot execute command:",
                    description="No embed data found in message.",
                    color=0xFF0000,
                )
                continue

            for j, embed in enumerate(msg.embeds):
                if not j % 3:
                    await self.response_msg.channel.trigger_typing()
                await self.response_msg.channel.send(embed=embed)

            await asyncio.sleep(0)

        await self.response_msg.delete()

    async def cmd_emsudo_get(
        self,
        *msgs: discord.Message,
        attributes: String = String(""),
        name: String = String("(add a title by editing this embed)"),
        json: bool = True,
        py: bool = False,
    ):
        """
        ->type emsudo commands
        ->signature pg!emsudo_get  <message> [<message>...] [attributes]
        ->description Get the embed data of a message
        ->extended description
        ```
        pg!emsudo_get {message_id} {optional_embed_attr} {optional_embed_attr}...
        pg!emsudo_get {channel_id} {message_id} {optional_embed_attr} {optional_embed_attr}...
        ```
        Get the contents of the embed of a message from the given arguments and send it as another message
        (with a `.txt` file attachment containing the embed data as a Python dictionary) to the channel where this command was invoked.
        If specific embed attributes are specified, then only those will be fetched from the embed of the given message, otherwise all attributes will be fetched.
        ->example command pg!emsudo_get 123456789123456789 title
        pg!emsudo_get 123456789123456789/98765432198765444321 "description fields"
        pg!emsudo_get 123456789123456789/98765432198765444321
        -----
        Implement pg!emsudo_get, to return the embed of a message as a dictionary in a text file.
        """

        if not msgs:
            raise BotException(
                f"Invalid arguments!",
                "No message IDs given as input.",
            )

        embed_attr_keys = {
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
        }

        reduced_embed_attr_keys = set()
        filtered_field_indices = []
        offset_idx = None

        attributes = attributes.string
        attrib_tuple = attributes.split()

        for i in range(len(attrib_tuple)):
            if attrib_tuple[i] == "fields":
                reduced_embed_attr_keys.add("fields")
                for j in range(i + 1, len(attrib_tuple)):
                    if attrib_tuple[j].isnumeric():
                        filtered_field_indices.append(int(attrib_tuple[j]))
                    else:
                        offset_idx = j
                        break
                else:
                    break

                if offset_idx:
                    break

            elif attrib_tuple[i] in attrib_tuple:
                reduced_embed_attr_keys.add(attrib_tuple[i])
            else:
                raise BotException(
                    "Cannot execute command:",
                    "Invalid embed attribute names!",
                )

        if offset_idx:
            for i in range(offset_idx, len(attrib_tuple)):
                if attrib_tuple[i] in embed_attr_keys:
                    reduced_embed_attr_keys.add(attrib_tuple[i])
                else:
                    raise BotException(
                        "Cannot execute command:",
                        "Invalid embed attribute names!",
                    )

        for i, msg in enumerate(msgs):
            await self.response_msg.channel.trigger_typing()
            if not msg.embeds:
                raise BotException(
                    f"Input {i}: Cannot execute command:",
                    "No embed data found in message.",
                )

            for embed in msg.embeds:
                embed_dict = embed.to_dict()
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
                            embed_dict["fields"][idx]
                            for idx in sorted(filtered_field_indices)
                        ]

                with io.StringIO() as fobj:
                    embed_utils.export_embed_data(
                        embed_dict, fp=fobj, indent=4, as_json=json
                    )
                    fobj.seek(0)
                    await self.response_msg.channel.send(
                        embed=await embed_utils.send_2(
                            None,
                            author_name="Embed Data",
                            title=(
                                embed_dict.get(
                                    "title", "(add a title by editing this embed)"
                                )
                            )
                            if len(msgs) < 2
                            else "(add a title by editing this embed)",
                            fields=(
                                (
                                    "\u2800",
                                    f"**[View Original Message]({msg.jump_url})**",
                                    True,
                                ),
                            ),
                        ),
                        file=discord.File(
                            fobj,
                            filename=(
                                "embeddata.py"
                                if py
                                else "embeddata.json"
                                if json
                                else "embeddata.txt"
                            ),
                        ),
                    )
            await asyncio.sleep(0)

        await self.response_msg.delete()

    async def cmd_emsudo_add_field(
        self,
        msg: discord.Message,
        data: Union[CodeBlock, String],
    ):
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

        field_list = None
        field_dict = None

        if not msg.embeds:
            raise BotException(
                "Cannot execute command:",
                "No embed data found in message.",
            )

        msg_embed = msg.embeds[0]

        if isinstance(data, String):
            field_str = data.string

            try:
                field_list = embed_utils.get_fields(field_str)
            except (TypeError, IndexError):
                raise BotException(
                    "Invalid format for field string(s)!",
                    ' The format should be `"<name|value|inline>"`.',
                )

            if len(field_list) == 3:
                field_dict = {
                    "name": field_list[0],
                    "value": field_list[1],
                    "inline": field_list[2],
                }

            elif not field_list:
                raise BotException(
                    "Invalid format for field string(s)!",
                    ' The format should be `"<name|value|inline>"`.',
                )

        elif isinstance(data, CodeBlock):
            try:
                args = literal_eval(data.code)
            except Exception as e:
                raise BotException(
                    "Invalid arguments!",
                    f"```\n{''.join(utils.format_code_exception(e))}```",
                )

            if isinstance(args, dict):
                field_dict = args

            elif isinstance(args, str):
                field_str = args

                try:
                    field_list = embed_utils.get_fields(field_str)
                except (TypeError, IndexError):
                    raise BotException(
                        "Invalid format for field string(s)!",
                        ' The format should be `"<name|value|inline>"` or a code block '
                        "containing `{'name: 'name', 'value': 'value'[, 'inline': True/False]}`.",
                    )

                if field_list:
                    field_dict = {
                        "name": field_list[0],
                        "value": field_list[1],
                        "inline": field_list[2],
                    }

                else:
                    raise BotException(
                        "Invalid format for field string(s)!",
                        ' The format should be `"<name|value|inline>"`',
                    )
            else:
                raise BotException(
                    "Invalid format for field string(s)!",
                    ' The format should be `"<name|value|inline>"` or a code block '
                    "containing `{'name: 'name', 'value': 'value'[, 'inline': True/False]}`.",
                )

        await embed_utils.add_field_from_dict(msg, msg_embed, field_dict)

        await self.response_msg.delete()
        await self.invoke_msg.delete()

    async def cmd_emsudo_add_fields(
        self,
        msg: discord.Message,
        data: Optional[Union[discord.Message, CodeBlock, String]] = None,
    ):
        """
        ->type emsudo commands
        ->signature pg!emsudo_add_fields <message> [data]
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

        attachment_msg = None
        field_dicts_list = []

        if not msg.embeds:
            raise BotException(
                "Cannot execute command:",
                "No embed data found in message.",
            )
        msg_embed = msg.embeds[0]

        if data is None:
            attachment_msg = self.invoke_msg

        elif isinstance(data, String):
            if not data.string:
                attachment_msg = self.invoke_msg
            else:
                raise BotException(
                    "Invalid arguments!",
                    'Argument `data` must be omitted or be an empty string `""`,'
                    " a message `[channel_id/]message_id` or a code block containing"
                    ' a list/tuple of embed field strings `"<name|value|inline>"` or embed dictionaries'
                    " `{'name: 'name', 'value': 'value'[, 'inline': True/False]}`.",
                )

        elif isinstance(data, discord.Message):
            attachment_msg = data

        if attachment_msg:
            if not attachment_msg.attachments:
                raise BotException(
                    "No valid attachment found in message.",
                    "It must be a `.txt`, `.py` file containing a Python dictionary,"
                    " or a `.json` file containing embed data.",
                )

            for attachment in attachment_msg.attachments:
                if (
                    attachment.content_type is not None
                    and attachment.content_type.startswith(("text", "application/json"))
                ):
                    attachment_obj = attachment
                    break
            else:
                raise BotException(
                    "No valid attachment found in message.",
                    "It must be a `.txt`, `.py` file containing a Python dictionary,"
                    " or a `.json` file containing embed data.",
                )

            embed_data = await attachment_obj.read()
            embed_data = embed_data.decode()

            if attachment_obj.content_type.startswith("application/json"):
                embed_dict = embed_utils.import_embed_data(
                    embed_data, from_json_string=True
                )
            else:
                embed_dict = embed_utils.import_embed_data(embed_data, from_string=True)

            if "fields" not in embed_dict or not embed_dict["fields"]:
                raise BotException("No embed field data found in attachment message.")

            await embed_utils.add_fields_from_dicts(
                msg, msg_embed, embed_dict["fields"]
            )
            await self.response_msg.delete()
            await self.invoke_msg.delete()
            return

        try:
            args = literal_eval(data.code)
        except Exception as e:
            raise BotException(
                "Invalid arguments!",
                f"```\n{''.join(utils.format_code_exception(e))}```",
            )

        if isinstance(args, (list, tuple)):
            for i, data in enumerate(args):
                if isinstance(data, dict):
                    field_dicts_list.append(data)

                elif isinstance(data, str):
                    try:
                        data_list = embed_utils.get_fields(data)
                    except (TypeError, IndexError):
                        raise BotException(
                            "Invalid format for field string(s)!",
                            ' The format should be `"<name|value|inline>"` or a code block '
                            "containing `{'name: 'name', 'value': 'value'[, 'inline': True/False]}`.",
                        )

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
                    raise BotException(
                        f"Invalid field data in input list at index {i}! Must be a dictionary or string.",
                        "",
                    )
        else:
            raise BotException(
                "Invalid arguments!",
                'Argument `data` must be omitted or be an empty string `""`,'
                " a message `[channel_id/]message_id` or a code block containing"
                ' a list/tuple of embed field strings `"<name|value|inline>"` or embed dictionaries'
                " `{'name: 'name', 'value': 'value'[, 'inline': True/False]}`.",
            )

        await embed_utils.add_fields_from_dicts(msg, msg_embed, field_dicts_list)

        await self.response_msg.delete()
        await self.invoke_msg.delete()

    async def cmd_emsudo_insert_field(
        self,
        msg: discord.Message,
        index: int,
        data: Union[CodeBlock, String],
    ):
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

        field_list = None
        field_dict = None

        if not msg.embeds:
            raise BotException(
                "Cannot execute command:",
                "No embed data found in message.",
            )

        msg_embed = msg.embeds[0]

        if isinstance(data, String):
            field_str = data.string

            try:
                field_list = embed_utils.get_fields(field_str)
            except (TypeError, IndexError):
                raise BotException(
                    "Invalid format for field string(s)!",
                    ' The format should be `"<name|value|inline>"`.',
                )

            if len(field_list) == 3:
                field_dict = {
                    "name": field_list[0],
                    "value": field_list[1],
                    "inline": field_list[2],
                }

            elif not field_list:
                raise BotException(
                    "Invalid format for field string(s)!",
                    ' The format should be `"<name|value|inline>"`.',
                )

        elif isinstance(data, CodeBlock):
            try:
                args = literal_eval(data.code)
            except Exception as e:
                raise BotException(
                    "Invalid arguments!",
                    f"```\n{''.join(utils.format_code_exception(e))}```",
                )

            if isinstance(args, dict):
                field_dict = args

            elif isinstance(args, str):
                field_str = args

                try:
                    field_list = embed_utils.get_fields(field_str)
                except (TypeError, IndexError):
                    raise BotException(
                        "Invalid format for field string(s)!",
                        ' The format should be `"<name|value|inline>"` or a code block '
                        "containing `{'name: 'name', 'value': 'value'[, 'inline': True/False]}`.",
                    )

                if field_list:
                    field_dict = {
                        "name": field_list[0],
                        "value": field_list[1],
                        "inline": field_list[2],
                    }

                else:
                    raise BotException(
                        "Invalid format for field string(s)!",
                        ' The format should be `"<name|value|inline>"`',
                    )
            else:
                raise BotException(
                    "Invalid format for field string(s)!",
                    ' The format should be `"<name|value|inline>"` or a code block '
                    "containing `{'name: 'name', 'value': 'value'[, 'inline': True/False]}`.",
                )

        await embed_utils.insert_field_from_dict(msg, msg_embed, field_dict, index)

        await self.response_msg.delete()
        await self.invoke_msg.delete()

    async def cmd_emsudo_insert_fields(
        self,
        msg: discord.Message,
        index: int,
        data: Optional[Union[discord.Message, CodeBlock, String]] = None,
    ):
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

        attachment_msg = None
        field_dicts_list = []

        if not msg.embeds:
            raise BotException(
                "Cannot execute command:",
                "No embed data found in message.",
            )
        msg_embed = msg.embeds[0]

        if data is None:
            attachment_msg = self.invoke_msg

        elif isinstance(data, String):
            if not data.string:
                attachment_msg = self.invoke_msg
            else:
                raise BotException(
                    "Invalid arguments!",
                    'Argument `data` must be omitted or be an empty string `""`,'
                    " a message `[channel_id/]message_id` or a code block containing"
                    ' a list/tuple of embed field strings `"<name|value|inline>"` or embed dictionaries'
                    " `{'name: 'name', 'value': 'value'[, 'inline': True/False]}`.",
                )

        elif isinstance(data, discord.Message):
            attachment_msg = data

        if attachment_msg:
            if not attachment_msg.attachments:
                raise BotException(
                    "No valid attachment found in message.",
                    "It must be a `.txt`, `.py` file containing a Python dictionary,"
                    " or a `.json` file containing embed data.",
                )

            for attachment in attachment_msg.attachments:
                if (
                    attachment.content_type is not None
                    and attachment.content_type.startswith(("text", "application/json"))
                ):
                    attachment_obj = attachment
                    break
            else:
                raise BotException(
                    "No valid attachment found in message.",
                    "It must be a `.txt`, `.py` file containing a Python dictionary,"
                    " or a `.json` file containing embed data.",
                )

            embed_data = await attachment_obj.read()
            embed_data = embed_data.decode()

            if attachment_obj.content_type.startswith("application/json"):
                embed_dict = embed_utils.import_embed_data(
                    embed_data, from_json_string=True
                )
            else:
                embed_dict = embed_utils.import_embed_data(embed_data, from_string=True)

            if "fields" not in embed_dict or not embed_dict["fields"]:
                raise BotException("No embed field data found in attachment message.")

            await embed_utils.insert_fields_from_dicts(
                msg, msg_embed, embed_dict["fields"], index
            )
            await self.response_msg.delete()
            await self.invoke_msg.delete()
            return

        try:
            args = literal_eval(data.code)
        except Exception as e:
            raise BotException(
                "Invalid arguments!",
                f"```\n{''.join(utils.format_code_exception(e))}```",
            )

        if isinstance(args, (list, tuple)):
            for i, data in enumerate(args):
                if isinstance(data, dict):
                    field_dicts_list.append(data)

                elif isinstance(data, str):
                    try:
                        data_list = embed_utils.get_fields(data)
                    except (TypeError, IndexError):
                        raise BotException(
                            "Invalid format for field string(s)!",
                            ' The format should be `"<name|value|inline>"` or a code block '
                            "containing `{'name: 'name', 'value': 'value'[, 'inline': True/False]}`.",
                        )

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
                        raise BotException(
                            "Invalid format for field string(s)!",
                            ' The format should be `"<name|value|inline>"` or a code block '
                            "containing `{'name: 'name', 'value': 'value'[, 'inline': True/False]}`.",
                        )

                    field_dicts_list.append(data_dict)
                else:
                    raise BotException(
                        f"Invalid field data in input list at index {i}! Must be a dictionary or string.",
                        "",
                    )
        else:
            raise BotException(
                "Invalid arguments!",
                'Argument `data` must be omitted or be an empty string `""`,'
                " a message `[channel_id/]message_id` or a code block containing"
                ' a list/tuple of embed field strings `"<name|value|inline>"` or embed dictionaries'
                " `{'name: 'name', 'value': 'value'[, 'inline': True/False]}`.",
            )

        await embed_utils.insert_fields_from_dicts(
            msg, msg_embed, reversed(field_dicts_list), index
        )

        await self.response_msg.delete()
        await self.invoke_msg.delete()

    async def cmd_emsudo_edit_field(
        self,
        msg: discord.Message,
        index: int,
        data: Union[CodeBlock, String],
    ):
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

        field_list = None
        field_dict = None

        if not msg.embeds:
            raise BotException(
                "Cannot execute command:",
                "No embed data found in message.",
            )

        msg_embed = msg.embeds[0]

        if isinstance(data, String):
            field_str = data.string

            try:
                field_list = embed_utils.get_fields(field_str)
            except (TypeError, IndexError):
                raise BotException(
                    "Invalid format for field string(s)!",
                    ' The format should be `"<name|value|inline>"`.',
                )

            if len(field_list) == 3:
                field_dict = {
                    "name": field_list[0],
                    "value": field_list[1],
                    "inline": field_list[2],
                }

            elif not field_list:
                raise BotException(
                    "Invalid format for field string(s)!",
                    ' The format should be `"<name|value|inline>"`.',
                )

        elif isinstance(data, CodeBlock):
            try:
                args = literal_eval(data.code)
            except Exception as e:
                raise BotException(
                    "Invalid arguments!",
                    f"```\n{''.join(utils.format_code_exception(e))}```",
                )

            if isinstance(args, dict):
                field_dict = args

            elif isinstance(args, str):
                field_str = args

                try:
                    field_list = embed_utils.get_fields(field_str)
                except (TypeError, IndexError):
                    raise BotException(
                        "Invalid format for field string(s)!",
                        ' The format should be `"<name|value|inline>"` or a code block '
                        "containing `{'name: 'name', 'value': 'value'[, 'inline': True/False]}`.",
                    )

                if field_list:
                    field_dict = {
                        "name": field_list[0],
                        "value": field_list[1],
                        "inline": field_list[2],
                    }

                else:
                    raise BotException(
                        "Invalid format for field string(s)!",
                        ' The format should be `"<name|value|inline>"`',
                    )
            else:
                raise BotException(
                    "Invalid format for field string(s)!",
                    ' The format should be `"<name|value|inline>"` or a code block '
                    "containing `{'name: 'name', 'value': 'value'[, 'inline': True/False]}`.",
                )

        await embed_utils.edit_field_from_dict(msg, msg_embed, field_dict, index)

        await self.response_msg.delete()
        await self.invoke_msg.delete()

    async def cmd_emsudo_edit_fields(
        self,
        msg: discord.Message,
        data: Optional[Union[discord.Message, CodeBlock, String]] = None,
    ):
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

        attachment_msg = None
        field_dicts_list = []

        if not msg.embeds:
            raise BotException(
                "Cannot execute command:",
                "No embed data found in message.",
            )
        msg_embed = msg.embeds[0]

        if data is None:
            attachment_msg = self.invoke_msg

        elif isinstance(data, String):
            if not data.string:
                attachment_msg = self.invoke_msg
            else:
                raise BotException(
                    "Invalid arguments!",
                    'Argument `data` must be omitted or be an empty string `""`,'
                    " a message `[channel_id/]message_id` or a code block containing"
                    ' a list/tuple of embed field strings `"<name|value|inline>"` or embed dictionaries'
                    " `{'name: 'name', 'value': 'value'[, 'inline': True/False]}`.",
                )

        elif isinstance(data, discord.Message):
            attachment_msg = data

        if attachment_msg:
            if not attachment_msg.attachments:
                raise BotException(
                    "No valid attachment found in message.",
                    "It must be a `.txt`, `.py` file containing a Python dictionary,"
                    " or a `.json` file containing embed data.",
                )

            for attachment in attachment_msg.attachments:
                if (
                    attachment.content_type is not None
                    and attachment.content_type.startswith(("text", "application/json"))
                ):
                    attachment_obj = attachment
                    break
            else:
                raise BotException(
                    "No valid attachment found in message.",
                    "It must be a `.txt`, `.py` file containing a Python dictionary,"
                    " or a `.json` file containing embed data.",
                )

            embed_data = await attachment_obj.read()
            embed_data = embed_data.decode()

            if attachment_obj.content_type.startswith("application/json"):
                embed_dict = embed_utils.import_embed_data(
                    embed_data, from_json_string=True
                )
            else:
                embed_dict = embed_utils.import_embed_data(embed_data, from_string=True)

            if "fields" not in embed_dict or not embed_dict["fields"]:
                raise BotException("No embed field data found in attachment message.")

            await embed_utils.edit_fields_from_dicts(
                msg, msg_embed, embed_dict["fields"]
            )
            await self.response_msg.delete()
            await self.invoke_msg.delete()
            return

        try:
            args = literal_eval(data.code)
        except Exception as e:
            raise BotException(
                "Invalid arguments!",
                f"```\n{''.join(utils.format_code_exception(e))}```",
            )

        if isinstance(args, (list, tuple)):
            for i, data in enumerate(args):
                if isinstance(data, dict):
                    field_dicts_list.append(data)

                elif isinstance(data, str):
                    try:
                        data_list = embed_utils.get_fields(data)
                    except (TypeError, IndexError):
                        raise BotException(
                            "Invalid format for field string(s)!",
                            ' The format should be `"<name|value|inline>"` or a code block '
                            "containing `{'name: 'name', 'value': 'value'[, 'inline': True/False]}`.",
                        )

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
                    raise BotException(
                        f"Invalid field data in input list at index {i}! Must be a dictionary or string.",
                        "",
                    )
        else:
            raise BotException(
                "Invalid arguments!",
                'Argument `data` must be omitted or be an empty string `""`,'
                " a message `[channel_id/]message_id` or a code block containing"
                ' a list/tuple of embed field strings `"<name|value|inline>"` or embed dictionaries'
                " `{'name: 'name', 'value': 'value'[, 'inline': True/False]}`.",
            )

        await embed_utils.edit_fields_from_dicts(msg, msg_embed, field_dicts_list)

        await self.response_msg.delete()
        await self.invoke_msg.delete()

    async def cmd_emsudo_replace_field(
        self,
        msg: discord.Message,
        index: int,
        data: Union[CodeBlock, String],
    ):
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

        field_list = None
        field_dict = None

        if not msg.embeds:
            raise BotException(
                "Cannot execute command:",
                "No embed data found in message.",
            )

        msg_embed = msg.embeds[0]

        if isinstance(data, String):
            field_str = data.string

            try:
                field_list = embed_utils.get_fields(field_str)
            except (TypeError, IndexError):
                raise BotException(
                    "Invalid format for field string(s)!",
                    ' The format should be `"<name|value|inline>"`.',
                )

            if len(field_list) == 3:
                field_dict = {
                    "name": field_list[0],
                    "value": field_list[1],
                    "inline": field_list[2],
                }

            elif not field_list:
                raise BotException(
                    "Invalid format for field string(s)!",
                    ' The format should be `"<name|value|inline>"`.',
                )

        elif isinstance(data, CodeBlock):
            try:
                args = literal_eval(data.code)
            except Exception as e:
                raise BotException(
                    "Invalid arguments!",
                    f"```\n{''.join(utils.format_code_exception(e))}```",
                )

            if isinstance(args, dict):
                field_dict = args

            elif isinstance(args, str):
                field_str = args

                try:
                    field_list = embed_utils.get_fields(field_str)
                except (TypeError, IndexError):
                    raise BotException(
                        "Invalid format for field string(s)!",
                        ' The format should be `"<name|value|inline>"` or a code block '
                        "containing `{'name: 'name', 'value': 'value'[, 'inline': True/False]}`.",
                    )

                if field_list:
                    field_dict = {
                        "name": field_list[0],
                        "value": field_list[1],
                        "inline": field_list[2],
                    }

                else:
                    raise BotException(
                        "Invalid format for field string(s)!",
                        ' The format should be `"<name|value|inline>"`',
                    )
            else:
                raise BotException(
                    "Invalid format for field string(s)!",
                    ' The format should be `"<name|value|inline>"` or a code block '
                    "containing `{'name: 'name', 'value': 'value'[, 'inline': True/False]}`.",
                )

        await embed_utils.replace_field_from_dict(msg, msg_embed, field_dict, index)

        await self.response_msg.delete()
        await self.invoke_msg.delete()

    async def cmd_emsudo_swap_fields(
        self, msg: discord.Message, index_a: int, index_b: int
    ):
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

        if not msg.embeds:
            raise BotException(
                "Cannot execute command:",
                "No embed data found in message.",
            )

        msg_embed = msg.embeds[0]

        await embed_utils.swap_fields(msg, msg_embed, index_a, index_b)

        await self.response_msg.delete()
        await self.invoke_msg.delete()

    async def cmd_emsudo_clone_fields(
        self,
        msg: discord.Message,
        *indices: Union[range, int],
        clone_to: Optional[int] = None,
    ):
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

        if not msg.embeds:
            raise BotException(
                "Cannot execute command:",
                "No embed data found in message.",
            )

        msg_embed = msg.embeds[0]

        field_indices = []

        for idx in indices:
            if isinstance(idx, range):
                range_obj = idx
                if len(range_obj) > 25:
                    raise BotException(
                        "Invalid range object passed as an argument!",
                        "",
                    )

                field_indices.extend(range_obj)

            else:
                field_indices.append(idx)

        try:
            await embed_utils.clone_fields(
                msg, msg_embed, field_indices, insertion_index=clone_to
            )
        except IndexError:
            raise BotException("Invalid field index/indices!", "")

        await self.response_msg.delete()
        await self.invoke_msg.delete()

    async def cmd_emsudo_remove_fields(
        self,
        msg: discord.Message,
        *indices: Union[range, int],
    ):
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

        if not msg.embeds:
            raise BotException(
                "Cannot execute command:",
                "No embed data found in message.",
            )

        msg_embed = msg.embeds[0]

        field_indices = []

        for idx in indices:
            if isinstance(idx, range):
                range_obj = idx
                if len(range_obj) > 25:
                    raise BotException(
                        "Invalid range object passed as an argument!",
                        "",
                    )

                field_indices.extend(range_obj)

            else:
                field_indices.append(idx)

        try:
            await embed_utils.remove_fields(msg, msg_embed, field_indices)
        except IndexError:
            raise BotException("Invalid field index/indices!", "")

        await self.response_msg.delete()
        await self.invoke_msg.delete()

    async def cmd_emsudo_clear_fields(
        self,
        msg: discord.Message,
    ):
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

        if not msg.embeds:
            raise BotException(
                "Cannot execute command:",
                "No embed data found in message.",
            )

        msg_embed = msg.embeds[0]

        await embed_utils.clear_fields(msg, msg_embed)

        await self.response_msg.delete()
        await self.invoke_msg.delete()
