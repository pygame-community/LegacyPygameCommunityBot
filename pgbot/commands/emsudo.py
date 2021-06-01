"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file defines the command handler class for the emsudo commands of the bot
"""

from __future__ import annotations

import asyncio
import io
import json
from ast import literal_eval
from typing import Optional, Union

import discord
from discord.embeds import EmptyEmbed

from pgbot import embed_utils, utils
from pgbot.commands.base import BaseCommand, BotException, CodeBlock, String, add_group


class EmsudoCommand(BaseCommand):
    """
    Base class to handle emsudo commands.
    """

    @add_group("emsudo")
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
        ->example command pg!emsudo "This is one embed" "This is another"
        pg!emsudo 987654321987654321
        pg!emsudo
        \\`\\`\\`json
        {
            "title": "An Embed",
            "description": "Lol",
            "footer": {
                "icon_url": "https://cdn.discordapp.com/embed/avatars/0.png",
                "text": "footer text"
                }
        }
        \\`\\`\\`
        -----
        Implement pg!emsudos, for admins to send multiple embeds via the bot
        """

        for i, data in enumerate(datas):
            if isinstance(data, discord.Message):
                if not utils.check_channel_permissions(
                    self.author,
                    data.channel,
                    permissions=("view_channel",),
                ):
                    raise BotException(
                        f"Not enough permissions",
                        "You do not have enough permissions to run this command with the specified arguments.",
                    )
            if not i % 50:
                await asyncio.sleep(0)

        data_count = len(datas)
        output_embeds = []
        load_embed = embed_utils.create(
            title=f"Your command is being processed:",
            fields=(("\u2800", "`...`", False), ("\u2800", "`...`", False)),
        )

        for i, data in enumerate(datas):
            if data_count > 1 and not i % 3:
                await embed_utils.edit_field_from_dict(
                    self.response_msg,
                    load_embed,
                    dict(
                        name="Processing Inputs",
                        value=f"`{i}/{data_count}` inputs processed\n"
                        f"{(i/data_count)*100:.01f}% | "
                        + utils.progress_bar(i / data_count, divisions=30),
                    ),
                    0,
                )
                await self.invoke_msg.channel.trigger_typing()

            util_send_embed_args = dict(
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

            attachment_msg = None
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
                    raise BotException(
                        f"Input {i}: No valid attachment found in message.",
                        "It must be a `.txt`, `.py` file containing a Python dictionary,"
                        " or a `.json` file containing embed data.",
                    )

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
                    raise BotException(
                        f"Input {i}: No valid attachment found in message.",
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
                    embed_dict = embed_utils.import_embed_data(
                        embed_data, from_string=True
                    )

                output_embeds.append(embed_utils.create_from_dict(embed_dict))

            elif not only_description:
                if data.lang == "json":
                    try:
                        embed_dict = embed_utils.import_embed_data(
                            data.code, from_json_string=True
                        )
                    except json.JSONDecodeError as j:
                        raise BotException(
                            f"Input {i}: Invalid JSON data",
                            f"```\n{j.args[0]}\n```",
                        )

                    output_embeds.append(embed_utils.create_from_dict(embed_dict))
                else:
                    try:
                        args = literal_eval(data.code)
                    except Exception as e:
                        raise BotException(f"Invalid arguments!", e.args[0])

                    if isinstance(args, dict):
                        output_embeds.append(embed_utils.create_from_dict(args))
                    
                    elif not isinstance(args, (list, tuple)):
                        arg_count = len(args)

                        if arg_count > 0:
                            if isinstance(args[0], (tuple, list)):
                                if len(args[0]) == 3:
                                    util_send_embed_args.update(
                                        author_name=args[0][0],
                                        author_url=args[0][0],
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
                            raise BotException(f"Input {i}: Invalid arguments!", "")

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
                                util_send_embed_args.update(fields=fields)
                            except TypeError:
                                raise BotException(
                                    f"Input {i}: Invalid format for field string(s)!",
                                    'The format should be `"<name|value|inline>"`',
                                )

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

                        output_embeds.append(embed_utils.create(**util_send_embed_args))

                    else:
                        raise BotException(
                            f"Input {i}: Invalid arguments!",
                            "A code block given as input must"
                            " contain either a Python `tuple`/`list` of embed data, or a"
                            " Python `dict` of embed data matching the JSON structure of"
                            " a Discord embed object, or JSON embed data (\n\\`\\`\\`json\n"
                            "data\n\\`\\`\\`\n)",
                        )
            else:
                output_embeds.append(
                    embed_utils.create(description=util_send_embed_args["description"])
                )

            await asyncio.sleep(0)

        if not datas:
            data_count = 1
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

            output_embeds.append(embed_utils.create_from_dict(embed_dict))

        else:
            await embed_utils.edit_field_from_dict(
                self.response_msg,
                load_embed,
                dict(
                    name="Processing Completed",
                    value=f"`{data_count}/{data_count}` inputs processed\n"
                    f"100% | " + utils.progress_bar(1.0, divisions=30),
                ),
                0,
            )

        output_embed_count = len(output_embeds)
        for j, embed in enumerate(output_embeds):
            if data_count > 2 and not j % 3:
                await embed_utils.edit_field_from_dict(
                    self.response_msg,
                    load_embed,
                    dict(
                        name="Generating Embeds",
                        value=f"`{j}/{output_embed_count}` embeds generated\n"
                        f"{(j/output_embed_count)*100:.01f}% | "
                        + utils.progress_bar(j / output_embed_count, divisions=30),
                    ),
                    1,
                )
            await self.invoke_msg.channel.send(embed=embed)

        if data_count > 2:
            await embed_utils.edit_field_from_dict(
                self.response_msg,
                load_embed,
                dict(
                    name="Generation Completed",
                    value=f"`{output_embed_count}/{output_embed_count}` embeds generated\n"
                    f"100% | " + utils.progress_bar(1.0, divisions=30),
                ),
                1,
            )
        await self.invoke_msg.delete()
        await self.response_msg.delete(delay=10.0 if data_count > 2 else 0)

    @add_group("emsudo", "replace")
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
        ->example command pg!emsudo_replace 987654321987654321 "Whoops the embed is boring now"
        pg!emsudo_replace 987654321987654321 123456789012345678
        pg!emsudo_replace 987654321987654321/123456789123456789
        \\`\\`\\`json
        {
            "title": "An Embed Replacement",
            "description": "Lolz",
            "footer": {
                "icon_url": "https://cdn.discordapp.com/embed/avatars/0.png",
                "text": "another footer text"
                }
        }
        \\`\\`\\`
        -----
        Implement pg!emsudo_replace, for admins to replace embeds via the bot
        """

        if not utils.check_channel_permissions(
            self.author,
            msg.channel,
            permissions=("view_channel", "send_messages"),
        ):
            raise BotException(
                f"Not enough permissions",
                "You do not have enough permissions to run this command on the specified channel.",
            )

        util_replace_embed_args = dict(
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

        attachment_msg = None
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

        elif not only_description:
            if data.lang == "json":
                try:
                    embed_dict = embed_utils.import_embed_data(
                        data.code, from_json_string=True
                    )
                except json.JSONDecodeError as j:
                    raise BotException(
                        f"Invalid JSON data",
                        f"```\n{j.args[0]}\n```",
                    )
                await embed_utils.replace_from_dict(msg, embed_dict)
            else:
                try:
                    args = literal_eval(data.code)
                except Exception as e:
                    raise BotException(f"Invalid arguments!", e.args[0])

                if isinstance(args, dict):
                    await embed_utils.replace_from_dict(msg, args)

                elif isinstance(args, (list, tuple)):
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
                            util_replace_embed_args.update(fields=fields)
                        except TypeError:
                            raise BotException(
                                "Invalid format for field string(s)!",
                                'The format should be `"<name|value|inline>"`',
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
                else:
                    raise BotException(
                        f"Invalid arguments!",
                        "A code block given as input must"
                        " contain either a Python `tuple`/`list` of embed data, or a"
                        " Python `dict` of embed data matching the JSON structure of"
                        " a Discord embed object, or JSON embed data (\n\\`\\`\\`json\n"
                        "data\n\\`\\`\\`\n)",
                    )

        await self.invoke_msg.delete()
        await self.response_msg.delete()

    @add_group("emsudo", "add")
    async def cmd_emsudo_add(
        self,
        msg: discord.Message,
        data: Optional[Union[discord.Message, CodeBlock, String]] = None,
        overwrite: bool = False,
    ):
        """
        ->type emsudo commands
        ->signature pg!emsudo_add <message> [data] [overwrite=False]
        ->description Add an embed through the bot
        ->extended description
        Add an embed to a message in the channel where this command was invoked using the given arguments.
        If the optional argument `[data]` is omitted, attempt to read input data from an attachment in the message that invoked
        this command.
        ->example command pg!emsudo_add 987654321987654321 "A wild __Embed__ appeared!"
        pg!emsudo_add 987654321987654321 123456789012345678
        pg!emsudo_add 987654321987654321
        \\`\\`\\`json
        {
            "title": "An Embed Replacement",
            "description": "Lolz",
            "footer": {
                "icon_url": "https://cdn.discordapp.com/embed/avatars/0.png",
                "text": "another footer text"
                }
        }
        \\`\\`\\`
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

    @add_group("emsudo", "remove")
    async def cmd_emsudo_remove(self, *msgs: discord.Message):
        """
        ->type emsudo commands
        ->signature pg!emsudo_remove <message> [<message>...]
        ->description Remove an embed through the bot
        -----
        Implement pg!emsudo_remove, for admins to remove embeds from messages via the bot
        """

        for i, msg in enumerate(msgs):
            if not utils.check_channel_permissions(
                self.author, msg.channel, permissions=("view_channel",)
            ):
                raise BotException(
                    f"Not enough permissions",
                    "You do not have enough permissions to run this command with the specified arguments.",
                )

            if not i % 50:
                await asyncio.sleep(0)

        if not msgs:
            raise BotException(
                f"Invalid arguments!",
                "No message IDs given as input.",
            )

        load_embed = embed_utils.create(
            title=f"Your command is being processed:",
            fields=(("\u2800", "`...`", False),),
        )
        msg_count = len(msgs)
        for i, msg in enumerate(msgs):
            await embed_utils.edit_field_from_dict(
                self.response_msg,
                load_embed,
                dict(
                    name="Processing Messages",
                    value=f"`{i}/{msg_count}` messages processed\n"
                    f"{(i/msg_count)*100:.01f}% | "
                    + utils.progress_bar(i / msg_count, divisions=30),
                ),
                0,
            )
            await self.channel.trigger_typing()
            if not msg.embeds:
                raise BotException(
                    f"Input {i}: Cannot execute command:",
                    "No embed data found in message.",
                )
            await msg.edit(embed=None)
            await asyncio.sleep(0)

        await embed_utils.edit_field_from_dict(
            self.response_msg,
            load_embed,
            dict(
                name="Processing Completed",
                value=f"`{msg_count}/{msg_count}` messages processed\n"
                f"100% | " + utils.progress_bar(1.0, divisions=30),
            ),
            0,
        )

        await self.response_msg.delete(delay=10.0 if msg_count > 1 else 0.0)
        await self.invoke_msg.delete()

    @add_group("emsudo", "edit")
    async def cmd_emsudo_edit(
        self,
        msg: discord.Message,
        *datas: Optional[Union[discord.Message, CodeBlock, String, bool]],
        add_attributes: bool = True,
        inner_fields: bool = False
    ):
        """
        ->type emsudo commands
        ->signature pg!emsudo_edit <message> [data] [data]...
        ->description Edit an embed through the bot
        ->extended description
        Update the given attributes of an embed of a message in the channel where this command was invoked using the given arguments.
        ->example command pg!emsudo_edit 987654321987654321 "Lol only the embed description changed"
        pg!emsudo_edit 987654321987654321 123456789012345678 251613726327333621
        pg!emsudo_edit 987654321987654321
        \\`\\`\\`json
        {
            "title": "An Embed Edit",
            "footer": {
                "text": "yet another footer text"
                }
        }
        \\`\\`\\`
        -----
        Implement pg!emsudo_edit, for admins to replace embeds via the bot
        """

        if not utils.check_channel_permissions(
            self.author,
            msg.channel,
            permissions=("view_channel", "send_messages"),
        ):
            raise BotException(
                f"Not enough permissions",
                "You do not have enough permissions to run this command with the specified arguments.",
            )

        for i, data in enumerate(datas):
            if isinstance(data, discord.Message):
                if not utils.check_channel_permissions(
                    self.author,
                    data.channel,
                    permissions=("view_channel",),
                ):
                    raise BotException(
                        f"Not enough permissions",
                        "You do not have enough permissions to run this command with the specified arguments.",
                    )
            if not i % 50:
                await asyncio.sleep(0)

        if not msg.embeds:
            raise BotException(
                "Cannot execute command:",
                "No embed data found in message.",
            )

        msg_embed = msg.embeds[0]
        edited_embed_dict = msg_embed.to_dict()
        data_count = len(datas)

        load_embed = embed_utils.create(
            title=f"Your command is being processed:",
            fields=(("\u2800", "`...`", False),),
        )
        for i, data in enumerate(datas):
            if data_count > 2 and not i % 3:
                await embed_utils.edit_field_from_dict(
                    self.response_msg,
                    load_embed,
                    dict(
                        name="Processing Inputs",
                        value=f"`{i}/{data_count}` inputs processed\n"
                        f"{(i/data_count)*100:.01f}% | "
                        + utils.progress_bar(i / data_count, divisions=30),
                    ),
                    0,
                )
            await self.invoke_msg.channel.trigger_typing()

            util_edit_embed_args = dict(
                author_name=EmptyEmbed,
                author_url=EmptyEmbed,
                author_icon_url=EmptyEmbed,
                title=EmptyEmbed,
                url=EmptyEmbed,
                thumbnail_url=EmptyEmbed,
                description=EmptyEmbed,
                image_url=EmptyEmbed,
                color=-1,
                fields=(),
                footer_text=EmptyEmbed,
                footer_icon_url=EmptyEmbed,
                timestamp=None,
            )

            attachment_msg: discord.Message = None
            only_description = False

            if not data:
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
                    raise BotException(
                        f"Input {i}: No valid attachment found in message.",
                        "It must be a `.txt`, `.py` file containing a Python dictionary,"
                        " or a `.json` file containing embed data.",
                    )

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
                    raise BotException(
                        f"Input {i}: No valid attachment found in message.",
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
                    embed_dict = embed_utils.import_embed_data(
                        embed_data, from_string=True
                    )
                
                edited_embed_dict = embed_utils.edit_dict_from_dict(
                    edited_embed_dict,
                    embed_dict,
                    add_attributes=add_attributes,
                    inner_fields=inner_fields
                )

            elif not only_description:
                if data.lang == "json":
                    try:
                        embed_dict = embed_utils.import_embed_data(
                            data.code, from_json_string=True
                        )
                    except json.JSONDecodeError as j:
                        raise BotException(
                            f"Input {i}: Invalid JSON data",
                            f"```\n{j.args[0]}\n```",
                        )
                    edited_embed_dict = embed_utils.edit_dict_from_dict(
                        edited_embed_dict,
                        embed_dict,
                        add_attributes=add_attributes,
                        inner_fields=inner_fields
                    )
                else:
                    try:
                        args = literal_eval(data.code)
                    except Exception as e:
                        raise BotException(f"Input {i}: Invalid arguments!", e.args[0])

                    if isinstance(args, dict):
                        edited_embed_dict = embed_utils.edit_dict_from_dict(
                            edited_embed_dict,
                            args,
                            add_attributes=add_attributes,
                            inner_fields=inner_fields
                        )
                    elif isinstance(args, (list, tuple)):
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
                            raise BotException(f"Input {i}: Invalid arguments!", "")

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
                        
                        if arg_count > 4:
                            try:
                                fields = embed_utils.get_fields(*args[4])
                                util_edit_embed_args.update(fields=fields)
                            except TypeError:
                                raise BotException(
                                    f"Input {i}: Invalid format for field string(s)!",
                                    ' The format should be `"<name|value|inline>"`',
                                )

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


                        embed_dict = embed_utils.create_as_dict(
                            **util_edit_embed_args,
                        )
                        edited_embed_dict = embed_utils.edit_dict_from_dict(
                            edited_embed_dict,
                            embed_dict,
                            add_attributes=add_attributes,
                            inner_fields=inner_fields
                        )

                    else:
                        raise BotException(
                            f"Input {i}: Invalid arguments!",
                            "A code block given as input must"
                            " contain either a Python `tuple`/`list` of embed data, or a"
                            " Python `dict` of embed data matching the JSON structure of"
                            " a Discord embed object, or JSON embed data (\n\\`\\`\\`json\n"
                            "data\n\\`\\`\\`\n)",
                        )
            else:
                embed_dict = embed_utils.create_as_dict(
                    description=util_edit_embed_args["description"],
                    color=-1,
                )
                edited_embed_dict = embed_utils.edit_dict_from_dict(
                    edited_embed_dict,
                    embed_dict,
                    add_attributes=add_attributes,
                    inner_fields=inner_fields
                )

            await asyncio.sleep(0)

        if not datas:
            data_count = 1
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

            edited_embed_dict = embed_utils.edit_dict_from_dict(
                edited_embed_dict,
                embed_dict,
                add_attributes=add_attributes,
                inner_fields=inner_fields
            )

            await embed_utils.edit_from_dict(
                msg, msg_embed, edited_embed_dict, add_attributes=add_attributes, inner_fields=inner_fields
            )

        else:
            await msg.edit(embed=discord.Embed.from_dict(edited_embed_dict))

        if data_count > 2:
            await embed_utils.edit_field_from_dict(
                self.response_msg,
                load_embed,
                dict(
                    name="Processing Complete",
                    value=f"`{data_count}/{data_count}` inputs processed\n"
                    f"100% | " + utils.progress_bar(1.0, divisions=30),
                ),
                0,
            )
        await self.invoke_msg.delete()
        await self.response_msg.delete(delay=10.0 if data_count > 1 else 0.0)

    @add_group("emsudo", "clone")
    async def cmd_emsudo_clone(self, *msgs: discord.Message):
        """
        ->type emsudo commands
        ->signature pg!emsudo_clone <message> [<message>...]
        ->description Clone all embeds.
        ->extended description
        Get a message from the given arguments and send it as another message (only containing its embed) to the channel where this command was invoked.
        ->example command
        pg!emsudo_clone 987654321987654321 123456789123456789 https://discord.com/channels/772505616680878080/841726972841558056/846870368672546837
        -----
        Implement pg!_emsudo_clone, to get the embed of a message and send it.
        """

        for i, msg in enumerate(msgs):
            if not utils.check_channel_permissions(
                self.author, msg.channel, permissions=("view_channel",)
            ):
                raise BotException(
                    f"Not enough permissions",
                    "You do not have enough permissions to run this command with the specified arguments.",
                )

            if not i % 50:
                await asyncio.sleep(0)

        if not msgs:
            raise BotException(
                f"Invalid arguments!",
                "No message IDs given as input.",
            )

        load_embed = embed_utils.create(
            title=f"Your command is being processed:",
            fields=(
                ("\u2800", "`...`", False),
                ("\u2800", "`...`", False),
            ),
        )

        msg_count = len(msgs)
        for i, msg in enumerate(msgs):
            if msg_count > 2 and not i % 3:
                await embed_utils.edit_field_from_dict(
                    self.response_msg,
                    load_embed,
                    dict(
                        name="Processing Messages",
                        value=f"`{i}/{msg_count}` messages processed\n"
                        f"{(i/msg_count)*100:.01f}% | "
                        + utils.progress_bar(i / msg_count, divisions=30),
                    ),
                    0,
                )
            await self.channel.trigger_typing()

            if not msg.embeds:
                raise BotException(
                    f"Input {i}: Cannot execute command:",
                    "No embed data found in message.",
                )

            embed_count = len(msg.embeds)
            for j, embed in enumerate(msg.embeds):
                if msg_count > 1 and not j % 3:
                    await embed_utils.edit_field_from_dict(
                        self.response_msg,
                        load_embed,
                        dict(
                            name="Cloning Embeds",
                            value=f"`{j}/{embed_count}` embeds cloned\n"
                            f"{(i/embed_count)*100:.01f}% | "
                            + utils.progress_bar(j / embed_count, divisions=30),
                        ),
                        1,
                    )
                    await self.channel.trigger_typing()

                await self.channel.send(embed=embed)

            await embed_utils.edit_field_from_dict(
                self.response_msg,
                load_embed,
                dict(
                    name="Cloning Completed",
                    value=f"`{embed_count}/{embed_count}` embeds cloned\n"
                    f"100% | " + utils.progress_bar(1.0, divisions=30),
                ),
                1,
            )

            await asyncio.sleep(0)

        if msg_count > 2:
            await embed_utils.edit_field_from_dict(
                self.response_msg,
                load_embed,
                dict(
                    name="Processing Completed",
                    value=f"`{msg_count}/{msg_count}` messages processed\n"
                    f"100% | " + utils.progress_bar(1.0, divisions=30),
                ),
                0,
            )

        await self.response_msg.delete(delay=10.0 if msg_count > 1 else 0.0)

    @add_group("emsudo", "get")
    async def cmd_emsudo_get(
        self,
        *msgs: discord.Message,
        a: String = String(""),
        attributes: String = String(""),
        name: String = String("(add a title by editing this embed)"),
        system_attributes: bool = False,
        as_json: bool = True,
        as_python: bool = False,
    ):
        """
        ->type emsudo commands
        ->signature pg!emsudo_get <message> [<message>...] [a/attributes=""] [name=""] [system_attributes=False] [as_json=True]
        [as_python=False]
        ->description Get the embed data of a message
        ->extended description
        Get the contents of the embed of a message from the given arguments and send it as another message
        (with a `.txt` file attachment containing the embed data as a Python dictionary) to the channel where this command was invoked.
        If specific embed attributes are specified, then only those will be fetched from the embed of the given message, otherwise all attributes will be fetched.
        ->example command pg!emsudo_get 98765432198765444321
        pg!emsudo_get 123456789123456789/98765432198765444321 a="description fields.0 fields.1.name author.url"
        pg!emsudo_get 123456789123456789/98765432198765444321 attributes="fields author footer.icon_url"
        -----
        Implement pg!emsudo_get, to return the embed of a message as a dictionary in a text file.
        """

        for i, msg in enumerate(msgs):
            if not utils.check_channel_permissions(
                self.author, msg.channel, permissions=("view_channel",)
            ):
                raise BotException(
                    f"Not enough permissions",
                    "You do not have enough permissions to run this command with the specified arguments.",
                )

            if not i % 50:
                await asyncio.sleep(0)

        if not msgs:
            raise BotException(
                f"Invalid arguments!",
                "No message IDs given as input.",
            )

        embed_attr_order_dict = {  # a dictionary will maintain this order when exported
            "provider": None,
            "type": None,
            "title": None,
            "description": None,
            "url": None,
            "color": None,
            "timestamp": None,
            "footer": None,
            "thumbnail": None,
            "image": None,
            "author": None,
            "fields": None,
        }

        system_attribs_dict = {
            "provider": {
                "name": None,
                "url": None,
            },
            "type": None,
            "footer": {
                "proxy_icon_url": None,
            },
            "thumbnail": {
                "proxy_url": None,
                "width": None,
                "height": None,
            },
            "image": {
                "proxy_url": None,
                "width": None,
                "height": None,
            },
            "author": {
                "proxy_icon_url": None,
            },
        }

        all_system_attribs_set = {
            "provider",
            "proxy_url",
            "proxy_icon_url",
            "width",
            "height",
        }

        embed_mask_dict = {}

        attribs = (
            a.string if a.string else attributes.string if attributes.string else ""
        )

        attribs_tuple = tuple(
            attr_str.split(sep=".") if "." in attr_str else attr_str
            for attr_str in attribs.split()
        )

        all_attribs_set = {
            "provider",
            "name",
            "value",
            "inline",
            "url",
            "image",
            "thumbnail",
            "proxy_url",
            "type",
            "title",
            "description",
            "color",
            "timestamp",
            "footer",
            "text",
            "icon_url",
            "proxy_icon_url",
            "author",
            "fields",
        } | set(str(i) for i in range(25))

        attribs_with_sub_attribs = {
            "author",
            "thumbnail",
            "image",
            "fields",
            "footer",
            "provider",
        }  # 'fields' is a special case

        for attr in attribs_tuple:
            if isinstance(attr, list):
                if len(attr) > 3:
                    raise BotException(
                        "Cannot execute command:",
                        "Invalid embed attribute filter string!"
                        " Sub-attributes do not propagate beyond 3 levels.",
                    )
                bottom_dict = {}
                for i in range(len(attr)):
                    if attr[i] not in all_attribs_set:
                        raise BotException(
                            "Cannot execute command:",
                            f"`{attr[i]}` is not a valid embed (sub-)attribute name!",
                        )
                    elif attr[i] in all_system_attribs_set and not system_attributes:
                        raise BotException(
                            "Cannot execute command:",
                            f"The given attribute `{attr[i]}` cannot be retrieved when `system_attributes=`"
                            " is set to `False`.",
                        )
                    if not i:
                        if attribs_tuple.count(attr[i]):
                            raise BotException(
                                "Cannot execute command:",
                                "Invalid embed attribute filter string!"
                                f" Do not specify upper level embed attributes twice! {attr[i]}",
                            )
                        elif attr[i] not in attribs_with_sub_attribs:
                            raise BotException(
                                "Cannot execute command:",
                                "Invalid embed attribute filter string!"
                                f" The embed attribute `{attr[i]}` does not have any sub-attributes!",
                            )

                        if attr[i] not in embed_mask_dict:
                            embed_mask_dict[attr[i]] = bottom_dict
                        else:
                            bottom_dict = embed_mask_dict[attr[i]]

                    elif i == len(attr) - 1:
                        if i == 1 and attr[i - 1] == "fields":
                            if not attr[i].isnumeric():
                                for sub_attr in ("name", "value", "inline"):
                                    if attr[i] == sub_attr:
                                        for j in range(25):
                                            str_idx = str(j)
                                            if str_idx not in embed_mask_dict["fields"]:
                                                embed_mask_dict["fields"][str_idx] = {
                                                    sub_attr: None
                                                }
                                            else:
                                                embed_mask_dict["fields"][str_idx][
                                                    sub_attr
                                                ] = None
                                        break
                                else:
                                    raise BotException(
                                        "Cannot execute command:",
                                        "Invalid embed attribute filter string!"
                                        f" The given attribute `{attr[i]}` is not an attribute of an embed field!",
                                    )
                                continue

                        if attr[i] not in bottom_dict:
                            bottom_dict[attr[i]] = None
                    else:
                        if attr[i] not in embed_mask_dict[attr[i - 1]]:
                            bottom_dict = {}
                            embed_mask_dict[attr[i - 1]][attr[i]] = bottom_dict
                        else:
                            bottom_dict = embed_mask_dict[attr[i - 1]][attr[i]]

            elif attr in embed_attr_order_dict:
                if attribs_tuple.count(attr) > 1:
                    raise BotException(
                        "Cannot execute command:",
                        "Invalid embed attribute filter string!"
                        f" Do not specify upper level embed attributes twice: `{attr}`",
                    )
                elif attr in all_system_attribs_set and not system_attributes:
                    raise BotException(
                        "Cannot execute command:",
                        f"The given attribute `{attr}` cannot be retrieved when `system_attributes=`"
                        " is set to `False`.",
                    )

                if attr not in embed_mask_dict:
                    embed_mask_dict[attr] = None
                else:
                    raise BotException(
                        "Cannot execute command:",
                        "Invalid embed attribute filter string!"
                        " Do not specify upper level embed attributes twice!",
                    )

            else:
                raise BotException(
                    "Cannot execute command:",
                    f"Invalid embed attribute name `{attr}`!",
                )

        load_embed = embed_utils.create(
            title=f"Your command is being processed:",
            fields=(
                ("\u2800", "`...`", False),
                ("\u2800", "`...`", False),
            ),
        )

        msg_count = len(msgs)
        for i, msg in enumerate(msgs):
            if msg_count > 2 and not i % 3:
                await embed_utils.edit_field_from_dict(
                    self.response_msg,
                    load_embed,
                    dict(
                        name="Processing Messages",
                        value=f"`{i}/{msg_count}` messages processed\n"
                        f"{(i/msg_count)*100:.01f}% | "
                        + utils.progress_bar(i / msg_count, divisions=30),
                    ),
                    0,
                )
            await self.channel.trigger_typing()
            if not msg.embeds:
                raise BotException(
                    f"Input {i}: Cannot execute command:",
                    "No embed data found in message.",
                )

            embed_count = len(msg.embeds)
            for j, embed in enumerate(msg.embeds):
                if embed_count > 2 and not j % 3:
                    await embed_utils.edit_field_from_dict(
                        self.response_msg,
                        load_embed,
                        dict(
                            name="Serializing Embeds",
                            value=f"`{j}/{embed_count}` embeds serialized\n"
                            f"{(j/embed_count)*100:.01f}% | "
                            + utils.progress_bar(j / embed_count, divisions=30),
                        ),
                        1,
                    )
                embed_dict = embed.to_dict()

                if embed_mask_dict:
                    if "fields" in embed_dict and "fields" in embed_mask_dict:
                        field_list = embed_dict["fields"]
                        embed_dict["fields"] = {
                            str(i): field_list[i] for i in range(len(field_list))
                        }

                        if not system_attributes:
                            embed_utils.recursive_delete(
                                embed_dict, system_attribs_dict
                            )
                        embed_utils.recursive_delete(
                            embed_dict, embed_mask_dict, inverse=True
                        )

                        field_dict = embed_dict["fields"]
                        embed_dict["fields"] = [
                            field_dict[i] for i in sorted(field_dict.keys())
                        ]
                    else:
                        if not system_attributes:
                            embed_utils.recursive_delete(
                                embed_dict, system_attribs_dict
                            )
                        embed_utils.recursive_delete(
                            embed_dict, embed_mask_dict, inverse=True
                        )
                else:
                    if not system_attributes:
                        embed_utils.recursive_delete(embed_dict, system_attribs_dict)

                if embed_dict:
                    for k in tuple(embed_dict.keys()):
                        if not embed_dict[k]:
                            del embed_dict[k]
                else:
                    raise BotException(
                        "Cannot execute command:",
                        "Could not find data that matches"
                        " the pattern of the given embed attribute filter string.",
                    )

                with io.StringIO() as fobj:
                    # final_embed_dict = {k: embed_dict[k] for k in embed_attr_order_dict if k in embed_dict}
                    embed_utils.export_embed_data(
                        {
                            k: embed_dict[k]
                            for k in embed_attr_order_dict
                            if k in embed_dict
                        },
                        fp=fobj,
                        indent=4,
                        as_json=True if as_json and not as_python else False,
                    )
                    fobj.seek(0)
                    await self.channel.send(
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
                                "embeddata.json"
                                if as_python
                                else "embeddata.json"
                                if as_json
                                else "embeddata.txt"
                            ),
                        ),
                    )

            if embed_count > 2:
                await embed_utils.edit_fields_from_dict(
                    self.response_msg,
                    load_embed,
                    dict(
                        name="Serialization Completed",
                        value=f"`{embed_count}/{embed_count}` embeds serialized\n"
                        f"100% | " + utils.progress_bar(1.0, divisions=30),
                    ),
                    1,
                )
            
            await asyncio.sleep(0)

        if msg_count > 2:
            await embed_utils.edit_field_from_dict(
                self.response_msg,
                load_embed,
                dict(
                    name="Processing Completed",
                    value=f"`{msg_count}/{msg_count}` inputs processed\n"
                    f"100% | " + utils.progress_bar(1.0, divisions=30),
                ),
                0,
            )

        await self.response_msg.delete(delay=10.0 if msg_count > 1 else 0.0)

    @add_group("emsudo", "add_field")
    async def cmd_emsudo_add_field(
        self,
        msg: discord.Message,
        data: Union[CodeBlock, String],
    ):
        """
        ->type More emsudo commands
        ->signature pg!emsudo_add_field <message> <data>
        ->description Add an embed field through the bot
        ->extended description
        Add an embed field to the embed of a message in the channel where this command was invoked using the given arguments.
        ->example command
        pg!emsudo_add_field 987654321987654321/123456789123456789
        \\`\\`\\`json
        {
           "name": "Mr Field",
           "value": "I value nothing",
           "inline": false
        }
        \\`\\`\\`
        -----
        Implement pg!emsudo_add_field, for admins to add fields to embeds sent via the bot
        """

        if not utils.check_channel_permissions(
            self.author,
            msg.channel,
            permissions=("view_channel", "send_messages"),
        ):
            raise BotException(
                f"Not enough permissions",
                "You do not have enough permissions to run this command with the specified arguments.",
            )

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
                field_list = embed_utils.get_fields(field_str)[0]
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
            if data.lang == "json":
                try:
                    field_dict = embed_utils.import_embed_data(
                        data.code,
                        from_json_string=True,
                    )
                except json.JSONDecodeError as j:
                    raise BotException(
                        f"Invalid JSON data",
                        f"```\n{j.args[0]}\n```",
                    )
            else:
                try:
                    args = literal_eval(data.code)
                except Exception as e:
                    raise BotException(
                        "Invalid arguments!",
                        utils.code_block(utils.format_code_exception(e)),
                    )

                if isinstance(args, dict):
                    field_dict = args

                elif isinstance(args, str):
                    field_str = args

                    try:
                        field_list = embed_utils.get_fields(field_str)[0]
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
        await self.invoke_msg.delete()
        await self.response_msg.delete()

    @add_group("emsudo", "add_fields")
    async def cmd_emsudo_add_fields(
        self,
        msg: discord.Message,
        data: Optional[Union[discord.Message, CodeBlock, String]] = None,
    ):
        """
        ->type More emsudo commands
        ->signature pg!emsudo_add_fields <message> [data]
        ->description Add embed fields through the bot
        ->extended description
        Add multiple embed fields to the embed of a message in the channel where this command was invoked using the given arguments.
        ->example command
        pg!emsudo_add_fields 987654321987654321/123456789123456789
        \\`\\`\\`json
        {
            "fields": [
                {
                    "name": "Mrs Field",
                    "value": "I value nothing more than my husband",
                    "inline": true
                },
                {
                    "name": "Mr Field",
                    "value": "I value nothing more than being embedded",
                    "inline": false
                }
            ]
        }
        \\`\\`\\`
        -----
        Implement pg!emsudo_add_fields, for admins to add multiple fields to embeds sent via the bot
        """

        if not utils.check_channel_permissions(
            self.author,
            msg.channel,
            permissions=("view_channel", "send_messages"),
        ):
            raise BotException(
                f"Not enough permissions",
                "You do not have enough permissions to run this command with the specified arguments.",
            )

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

        else:
            if data.lang == "json":
                try:
                    embed_dict = embed_utils.import_embed_data(
                        data.code,
                        from_json_string=True,
                    )
                except json.JSONDecodeError as j:
                    raise BotException(
                        f"Invalid JSON data",
                        f"```\n{j.args[0]}\n```",
                    )

                if "fields" not in embed_dict or not embed_dict["fields"]:
                    raise BotException(
                        "No embed field data found in the given JSON embed data."
                    )

                await embed_utils.add_fields_from_dicts(
                    msg, msg_embed, embed_dict["fields"]
                )
            else:
                try:
                    args = literal_eval(data.code)
                except Exception as e:
                    raise BotException(
                        "Invalid arguments!",
                        utils.code_block(utils.format_code_exception(e)),
                    )

                if isinstance(args, (list, tuple, dict)):
                    if isinstance(args, dict):
                        if "fields" in args:
                            embed_fields_list = args["fields"]
                        else:
                            raise BotException(
                                "Invalid arguments!",
                                'Argument `data` must be omitted or be an empty string `""`,'
                                " a message `[channel_id/]message_id` or a python code block containing"
                                ' a list/tuple of embed field strings `"<name|value|inline>"` or embed field dictionaries'
                                " `{'name: 'name', 'value': 'value'[, 'inline': True/False]}`. It can also be a JSON"
                                " code block containing JSON embed field data.",
                            )
                    else:
                        embed_fields_list = args
                    for i, data in enumerate(embed_fields_list):
                        if isinstance(data, dict):
                            field_dicts_list.append(data)

                        elif isinstance(data, str):
                            try:
                                data_list = embed_utils.get_fields(data)[0]
                            except (TypeError, IndexError):
                                raise BotException(
                                    f"Invalid field string in input list at index {i}!",
                                    ' The format should be `"<name|value|inline>"` or'
                                    " `{'name: 'name', 'value': 'value'[, 'inline': True/False]}`.",
                                )

                            if data_list:
                                data_dict = {
                                    "name": data_list[0],
                                    "value": data_list[1],
                                    "inline": data_list[2],
                                }
                            else:
                                raise BotException(
                                    f"Invalid field string in input list at index {i}!",
                                    ' The format should be `"<name|value|inline>"` or'
                                    " `{'name: 'name', 'value': 'value'[, 'inline': True/False]}`.",
                                )

                            field_dicts_list.append(data_dict)
                        else:
                            raise BotException(
                                f"Invalid field string in input list at index {i}!",
                                ' The format should be `"<name|value|inline>"` or'
                                " `{'name: 'name', 'value': 'value'[, 'inline': True/False]}`.",
                            )

                else:
                    raise BotException(
                        "Invalid arguments!",
                        'Argument `data` must be omitted or be an empty string `""`,'
                        " a message `[channel_id/]message_id` or a python code block containing"
                        ' a list/tuple of embed field strings `"<name|value|inline>"` or embed field dictionaries'
                        " `{'name: 'name', 'value': 'value'[, 'inline': True/False]}`. It can also be a JSON"
                        " code block containing JSON embed field data.",
                    )

                await embed_utils.add_fields_from_dicts(
                    msg, msg_embed, field_dicts_list
                )

        await self.invoke_msg.delete()
        await self.response_msg.delete()

    @add_group("emsudo", "insert_field")
    async def cmd_emsudo_insert_field(
        self,
        msg: discord.Message,
        index: int,
        data: Union[CodeBlock, String],
    ):
        """
        ->type More emsudo commands
        ->signature pg!emsudo_insert_field <message> <index> <data>
        ->description Insert an embed field through the bot
        ->extended description
        Insert an embed field at the given index into the embed of a message in the channel where this command was invoked using the given arguments.
        ->example command
        pg!emsudo_insert_field https://discord.com/channels/772505616680878080/775317562715406336/846955385688031282 2
        \\`\\`\\`json
        {
            "name": "Mrs Field",
            "value": "I value nothing more than my husband",
            "inline": true
        }
        \\`\\`\\`
        -----
        Implement pg!emsudo_insert_field, for admins to insert fields into embeds sent via the bot
        """

        if not utils.check_channel_permissions(
            self.author,
            msg.channel,
            permissions=("view_channel", "send_messages"),
        ):
            raise BotException(
                f"Not enough permissions",
                "You do not have enough permissions to run this command with the specified arguments.",
            )

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
                field_list = embed_utils.get_fields(field_str)[0]
            except (TypeError, IndexError):
                raise BotException(
                    "Invalid format for field string(s)!",
                    ' The format should be `"<name|value|inline>"`.',
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
                    ' The format should be `"<name|value|inline>"`.',
                )

        elif isinstance(data, CodeBlock):
            if data.lang == "json":
                try:
                    field_dict = embed_utils.import_embed_data(
                        data.code,
                        from_json_string=True,
                    )
                except json.JSONDecodeError as j:
                    raise BotException(
                        f"Invalid JSON data",
                        f"```\n{j.args[0]}\n```",
                    )
            else:
                try:
                    args = literal_eval(data.code)
                except Exception as e:
                    raise BotException(
                        "Invalid arguments!",
                        utils.code_block(utils.format_code_exception(e)),
                    )

                if isinstance(args, dict):
                    field_dict = args

                elif isinstance(args, str):
                    field_str = args

                    try:
                        field_list = embed_utils.get_fields(field_str)[0]
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
        await self.invoke_msg.delete()
        await self.response_msg.delete()

    @add_group("emsudo", "insert_fields")
    async def cmd_emsudo_insert_fields(
        self,
        msg: discord.Message,
        index: int,
        data: Optional[Union[discord.Message, CodeBlock, String]] = None,
    ):
        """
        ->type More emsudo commands
        ->signature pg!emsudo_insert_fields <message> <index> [data]
        ->description Insert embed fields through the bot
        ->extended description
        Insert multiple embed fields at the given index into the embed of a message in the channel where this command was invoked using the given arguments.
        ->example command
        pg!emsudo_insert_fields 2 987654321987654321/123456789123456789
        \\`\\`\\`json
        {
            "fields": [
                {
                    "name": "Mrs Field",
                    "value": "I value nothing more than my husband",
                    "inline": true
                },
                {
                    "name": "Baby Field",
                    "value": "uwu",
                    "inline": false
                }
            ]
        }
        \\`\\`\\`
        -----
        Implement pg!emsudo_insert_fields, for admins to insert multiple fields to embeds sent via the bot
        """

        if not utils.check_channel_permissions(
            self.author,
            msg.channel,
            permissions=("view_channel", "send_messages"),
        ):
            raise BotException(
                f"Not enough permissions",
                "You do not have enough permissions to run this command on the specified channel.",
            )

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

        else:
            if data.lang == "json":
                try:
                    embed_dict = embed_utils.import_embed_data(
                        data.code,
                        from_json_string=True,
                    )
                except json.JSONDecodeError as j:
                    raise BotException(
                        f"Invalid JSON data",
                        f"```\n{j.args[0]}\n```",
                    )

                if "fields" not in embed_dict or not embed_dict["fields"]:
                    raise BotException(
                        "No embed field data found in the given JSON embed data."
                    )

                await embed_utils.insert_fields_from_dicts(
                    msg, msg_embed, embed_dict["fields"], index
                )
            else:
                try:
                    args = literal_eval(data.code)
                except Exception as e:
                    raise BotException(
                        "Invalid arguments!",
                        utils.code_block(utils.format_code_exception(e)),
                    )

                if isinstance(args, (list, tuple, dict)):
                    if isinstance(args, dict):
                        if "fields" in args:
                            embed_fields_list = args["fields"]
                        else:
                            raise BotException(
                                "Invalid arguments!",
                                'Argument `data` must be omitted or be an empty string `""`,'
                                " a message `[channel_id/]message_id` or a python code block containing"
                                ' a list/tuple of embed field strings `"<name|value|inline>"` or embed field dictionaries'
                                " `{'name: 'name', 'value': 'value'[, 'inline': True/False]}`. It can also be a JSON"
                                " code block containing JSON embed field data.",
                            )
                    else:
                        embed_fields_list = args
                    for i, data in enumerate(embed_fields_list):
                        if isinstance(data, dict):
                            field_dicts_list.append(data)

                        elif isinstance(data, str):
                            try:
                                data_list = embed_utils.get_fields(data)[0]
                            except (TypeError, IndexError):
                                raise BotException(
                                    f"Invalid field string in input list at index {i}!",
                                    ' The format should be `"<name|value|inline>"` or'
                                    " `{'name: 'name', 'value': 'value'[, 'inline': True/False]}`.",
                                )

                            if data_list:
                                data_dict = {
                                    "name": data_list[0],
                                    "value": data_list[1],
                                    "inline": data_list[2],
                                }
                            else:
                                raise BotException(
                                    f"Invalid field string in input list at index {i}!",
                                    ' The format should be `"<name|value|inline>"` or'
                                    " `{'name: 'name', 'value': 'value'[, 'inline': True/False]}`.",
                                )

                            field_dicts_list.append(data_dict)
                        else:
                            raise BotException(
                                f"Invalid field string in input list at index {i}!",
                                ' The format should be `"<name|value|inline>"` or'
                                " `{'name: 'name', 'value': 'value'[, 'inline': True/False]}`.",
                            )

                else:
                    raise BotException(
                        "Invalid arguments!",
                        'Argument `data` must be omitted or be an empty string `""`,'
                        " a message `[channel_id/]message_id` or a python code block containing"
                        ' a list/tuple of embed field strings `"<name|value|inline>"` or embed field dictionaries'
                        " `{'name: 'name', 'value': 'value'[, 'inline': True/False]}`. It can also be a JSON"
                        " code block containing JSON embed field data.",
                    )

                await embed_utils.insert_fields_from_dicts(
                    msg, msg_embed, reversed(field_dicts_list), index
                )

        await self.invoke_msg.delete()
        await self.response_msg.delete()

    @add_group("emsudo", "edit_field")
    async def cmd_emsudo_edit_field(
        self,
        msg: discord.Message,
        index: int,
        data: Union[CodeBlock, String],
    ):
        """
        ->type More emsudo commands
        ->signature pg!emsudo_edit_field <message> <index> <data>
        ->description Replace an embed field through the bot
        ->extended description
        Edit parts of an embed field at the given index in the embed of a message in the channel where this command was invoked using the given arguments.
        ->example command
        pg!emsudo_edit_field 7 987654321987654321/123456789123456789
        \\`\\`\\`json
        {
           "name": "Boy Field",
           "value": "I value nothing",
           "inline": false
        }
        \\`\\`\\`
        -----
        Implement pg!emsudo_edit_field, for admins to update fields of embeds sent via the bot
        """

        if not utils.check_channel_permissions(
            self.author,
            msg.channel,
            permissions=("view_channel", "send_messages"),
        ):
            raise BotException(
                f"Not enough permissions",
                "You do not have enough permissions to run this command on the specified channel.",
            )

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
                field_list = embed_utils.get_fields(field_str)[0]
            except (TypeError, IndexError):
                raise BotException(
                    "Invalid format for field string(s)!",
                    ' The format should be `"<name|value|inline>"`.',
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
                    ' The format should be `"<name|value|inline>"`.',
                )

        elif isinstance(data, CodeBlock):
            if data.lang == "json":
                try:
                    field_dict = embed_utils.import_embed_data(
                        data.code,
                        from_json_string=True,
                    )
                except json.JSONDecodeError as j:
                    raise BotException(
                        f"Invalid JSON data",
                        f"```\n{j.args[0]}\n```",
                    )
            else:
                try:
                    args = literal_eval(data.code)
                except Exception as e:
                    raise BotException(
                        "Invalid arguments!",
                        utils.code_block(utils.format_code_exception(e)),
                    )

                if isinstance(args, dict):
                    field_dict = args

                elif isinstance(args, str):
                    field_str = args

                    try:
                        field_list = embed_utils.get_fields(field_str)[0]
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

        await self.invoke_msg.delete()
        await self.response_msg.delete()

    @add_group("emsudo", "edit_fields")
    async def cmd_emsudo_edit_fields(
        self,
        msg: discord.Message,
        data: Optional[Union[discord.Message, CodeBlock, String]] = None,
    ):
        """
        ->type More emsudo commands
        ->signature pg!emsudo_edit_fields <message> [data]
        ->description Edit multiple embed fields through the bot
        ->extended description
        Edit multiple embed fields in the embed of a message in the channel where this command was invoked using the given arguments.
        Combining the new fields with the old fields works like a bitwise OR operation from the first to the last embed field, where any embed field argument that is passed
        to this command that is empty (empty `dict` `{}` or empty `str` `''`) will not modify the embed field at its index when passed to this command.
        ->example command
        pg!emsudo_edit_fields 987654321987654321/123456789123456789
        \\`\\`\\`json
        {
            "fields": [
                {},
                {
                    "name": "Girl Field",
                    "value": "I value...",
                    "inline": False
                }
            ]
        }
        \\`\\`\\`
        -----
        Implement pg!emsudo_edit_fields, for admins to edit multiple embed fields of embeds sent via the bot
        """

        if not utils.check_channel_permissions(
            self.author,
            msg.channel,
            permissions=("view_channel", "send_messages"),
        ):
            raise BotException(
                f"Not enough permissions",
                "You do not have enough permissions to run this command on the specified channel.",
            )

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

        else:
            if data.lang == "json":
                try:
                    embed_dict = embed_utils.import_embed_data(
                        data.code,
                        from_json_string=True,
                    )
                except json.JSONDecodeError as j:
                    raise BotException(
                        f"Invalid JSON data",
                        f"```\n{j.args[0]}\n```",
                    )

                if "fields" not in embed_dict or not embed_dict["fields"]:
                    raise BotException(
                        "No embed field data found in the given JSON embed data."
                    )

                await embed_utils.edit_fields_from_dicts(
                    msg, msg_embed, embed_dict["fields"]
                )
            else:
                try:
                    args = literal_eval(data.code)
                except Exception as e:
                    raise BotException(
                        "Invalid arguments!",
                        utils.code_block(utils.format_code_exception(e)),
                    )

                if isinstance(args, (list, tuple, dict)):
                    if isinstance(args, dict):
                        if "fields" in args:
                            embed_fields_list = args["fields"]
                        else:
                            raise BotException(
                                "Invalid arguments!",
                                'Argument `data` must be omitted or be an empty string `""`,'
                                " a message `[channel_id/]message_id` or a python code block containing"
                                ' a list/tuple of embed field strings `"<name|value|inline>"` or embed field dictionaries'
                                " `{'name: 'name', 'value': 'value'[, 'inline': True/False]}`. It can also be a JSON"
                                " code block containing JSON embed field data.",
                            )
                    else:
                        embed_fields_list = args
                    for i, data in enumerate(embed_fields_list):
                        if isinstance(data, dict):
                            field_dicts_list.append(data)

                        elif isinstance(data, str):
                            try:
                                data_list = embed_utils.get_fields(data)[0]
                            except (TypeError, IndexError):
                                raise BotException(
                                    f"Invalid field string in input list at index {i}!",
                                    ' The format should be `"<name|value|inline>"` or'
                                    " `{'name: 'name', 'value': 'value'[, 'inline': True/False]}`.",
                                )

                            if data_list:
                                data_dict = {
                                    "name": data_list[0],
                                    "value": data_list[1],
                                    "inline": data_list[2],
                                }
                            else:
                                raise BotException(
                                    f"Invalid field string in input list at index {i}!",
                                    ' The format should be `"<name|value|inline>"` or'
                                    " `{'name: 'name', 'value': 'value'[, 'inline': True/False]}`.",
                                )

                            field_dicts_list.append(data_dict)
                        else:
                            raise BotException(
                                f"Invalid field string in input list at index {i}!",
                                ' The format should be `"<name|value|inline>"` or'
                                " `{'name: 'name', 'value': 'value'[, 'inline': True/False]}`.",
                            )

                else:
                    raise BotException(
                        "Invalid arguments!",
                        'Argument `data` must be omitted or be an empty string `""`,'
                        " a message `[channel_id/]message_id` or a python code block containing"
                        ' a list/tuple of embed field strings `"<name|value|inline>"` or embed field dictionaries'
                        " `{'name: 'name', 'value': 'value'[, 'inline': True/False]}`. It can also be a JSON"
                        " code block containing JSON embed field data.",
                    )

                await embed_utils.edit_fields_from_dicts(
                    msg, msg_embed, field_dicts_list
                )

        await self.invoke_msg.delete()
        await self.response_msg.delete()

    @add_group("emsudo", "replace_field")
    async def cmd_emsudo_replace_field(
        self,
        msg: discord.Message,
        index: int,
        data: Union[CodeBlock, String],
    ):
        """
        ->type More emsudo commands
        ->signature pg!emsudo_replace_field <message> <index> <data>
        ->description Replace an embed field through the bot
        ->extended description
        ->example command
        pg!emsudo_replace_field 2 987654321987654321/123456789123456789
        \\`\\`\\`json
        {
           "name": "Uncle Field",
           "value": "values.",
           "inline": false
        }
        \\`\\`\\`
        Replace an embed field at the given index in the embed of a message in the channel where this command was invoked using the given arguments.
        -----
        Implement pg!emsudo_replace_field, for admins to update fields of embeds sent via the bot
        """

        if not utils.check_channel_permissions(
            self.author,
            msg.channel,
            permissions=("view_channel", "send_messages"),
        ):
            raise BotException(
                f"Not enough permissions",
                "You do not have enough permissions to run this command on the specified channel.",
            )

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
                field_list = embed_utils.get_fields(field_str)[0]
            except (TypeError, IndexError):
                raise BotException(
                    "Invalid format for field string(s)!",
                    ' The format should be `"<name|value|inline>"`.',
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
                    ' The format should be `"<name|value|inline>"`.',
                )

        elif isinstance(data, CodeBlock):
            if data.lang == "json":
                try:
                    field_dict = embed_utils.import_embed_data(
                        data.code,
                        from_json_string=True,
                    )
                except json.JSONDecodeError as j:
                    raise BotException(
                        f"Invalid JSON data",
                        f"```\n{j.args[0]}\n```",
                    )
            else:
                try:
                    args = literal_eval(data.code)
                except Exception as e:
                    raise BotException(
                        "Invalid arguments!",
                        utils.code_block(utils.format_code_exception(e)),
                    )

                if isinstance(args, dict):
                    field_dict = args

                elif isinstance(args, str):
                    field_str = args

                    try:
                        field_list = embed_utils.get_fields(field_str)[0]
                    except (TypeError, IndexError):
                        raise BotException(
                            "Invalid format for field string(s)!",
                            ' The format should be `"<name|value|inline>"` or'
                            " `{'name: 'name', 'value': 'value'[, 'inline': True/False]}`.",
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
                        ' The format should be `"<name|value|inline>"` or'
                        " `{'name: 'name', 'value': 'value'[, 'inline': True/False]}`.",
                    )

        await embed_utils.replace_field_from_dict(msg, msg_embed, field_dict, index)

        await self.invoke_msg.delete()
        await self.response_msg.delete()

    @add_group("emsudo", "swap_fields")
    async def cmd_emsudo_swap_fields(
        self, msg: discord.Message, index_a: int, index_b: int
    ):
        """
        ->type More emsudo commands
        ->signature pg!emsudo_swap_fields <message> <index_a> <index_b>
        ->description Swap embed fields through the bot
        ->extended description
        Swap the positions of embed fields at the given indices of the embed of a message in the channel where this command was invoked using the given arguments.
        ->example command pg!emsudo_swap_fields 123456789123456789 6 9
        -----
        Implement pg!emsudo_swap_fields, for admins to swap fields in embeds sent via the bot
        """

        if not utils.check_channel_permissions(
            self.author,
            msg.channel,
            permissions=("view_channel", "send_messages"),
        ):
            raise BotException(
                f"Not enough permissions",
                "You do not have enough permissions to run this command on the specified channel.",
            )

        if not msg.embeds:
            raise BotException(
                "Cannot execute command:",
                "No embed data found in message.",
            )

        msg_embed = msg.embeds[0]

        await embed_utils.swap_fields(msg, msg_embed, index_a, index_b)

        await self.invoke_msg.delete()
        await self.response_msg.delete()

    @add_group("emsudo", "clone_fields")
    async def cmd_emsudo_clone_fields(
        self,
        msg: discord.Message,
        *indices: Union[range, int],
        clone_to: Optional[int] = None,
    ):
        """
        ->type More emsudo commands
        ->signature pg!emsudo_clone_fields <message> <index> [<index>...] [clone_to=None]
        ->description Clone multiple embed fields through the bot
        ->extended description
        Remove embed fields at the given indices of the embed of a message in the channel where this command was invoked using the given arguments.
        If `clone_to` is excluded, the cloned fields will be inserted at the index where they were cloned from.
        ->example command
        pg!emsudo_clone_fields 987654321987654321 range(4, 10, 2) clone_to=1
        pg!emsudo_clone_fields 987654321987654321 3 6 9 12 clone_to=8
        pg!emsudo_clone_fields 123456674923481222/987654321987654321 range(6)
        -----
        Implement pg!emsudo_clone_fields, for admins to remove fields in embeds sent via the bot
        """

        if not utils.check_channel_permissions(
            self.author,
            msg.channel,
            permissions=("view_channel", "send_messages"),
        ):
            raise BotException(
                f"Not enough permissions",
                "You do not have enough permissions to run this command on the specified channel.",
            )

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

        await self.invoke_msg.delete()
        await self.response_msg.delete()

    @add_group("emsudo", "remove_fields")
    async def cmd_emsudo_remove_fields(
        self,
        msg: discord.Message,
        *indices: Union[range, int],
    ):
        """
        ->type More emsudo commands
        ->signature pg!emsudo_remove_fields <message> <index> [<index>...]
        ->description Remove an embed field through the bot
        ->extended description
        Remove embed fields at the given indices of the embed of a message in the channel where this command was invoked using the given arguments.
        ->example command
        pg!emsudo_remove_fields 987654321987654321/123456789123456789 range(0, 10, 2)
        pg!emsudo_remove_fields 987654321987654321 5
        -----
        Implement pg!emsudo_remove_fields, for admins to remove fields in embeds sent via the bot
        """

        if not utils.check_channel_permissions(
            self.author,
            msg.channel,
            permissions=("view_channel", "send_messages"),
        ):
            raise BotException(
                f"Not enough permissions",
                "You do not have enough permissions to run this command on the specified channel.",
            )

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

        await self.invoke_msg.delete()
        await self.response_msg.delete()

    @add_group("emsudo", "clear_fields")
    async def cmd_emsudo_clear_fields(
        self,
        msg: discord.Message,
    ):
        """
        ->type More emsudo commands
        ->signature pg!emsudo_clear_fields <message>
        ->description Remove all embed fields through the bot
        ->extended description
        Remove all embed fields of the embed of a message in the channel where this command was invoked using the given arguments.
        -----
        Implement pg!emsudo_clear_fields, for admins to remove fields in embeds sent via the bot
        """

        if not utils.check_channel_permissions(
            self.author,
            msg.channel,
            permissions=("view_channel", "send_messages"),
        ):
            raise BotException(
                f"Not enough permissions",
                "You do not have enough permissions to run this command on the specified channel.",
            )

        if not msg.embeds:
            raise BotException(
                "Cannot execute command:",
                "No embed data found in message.",
            )

        msg_embed = msg.embeds[0]

        await embed_utils.clear_fields(msg, msg_embed)

        await self.invoke_msg.delete()
        await self.response_msg.delete()
