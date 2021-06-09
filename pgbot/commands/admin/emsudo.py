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

from pgbot import common
from pgbot.commands.base import (
    BaseCommand,
    BotException,
    CodeBlock,
    String,
    add_group,
)
from pgbot.utils import embed_utils, utils


class EmsudoCommand(BaseCommand):
    """
    Base class to handle emsudo commands.
    """

    @add_group("emsudo")
    async def cmd_emsudo(
        self,
        *datas: Optional[Union[discord.Message, CodeBlock, String, bool]],
        destination: Optional[discord.TextChannel] = None,
    ):
        """
        ->type emsudo commands
        ->signature pg!emsudo <*datas> [destination=]
        ->description Send embeds through the bot
        ->extended description
        Generate embeds from the given arguments
        and send them with a message
        to the given destination channel.

        __Args__:
            `*datas: (Message|CodeBlock|String|bool)`
            > A sequence of data to create embeds from.
            > Each can be a discord message whose first attachment contains
            > JSON or Python embed data, a string
            > (will only affect a embed description field),
            > a code block containing JSON embed data
            > (use the \\`\\`\\`json prefix), or a Python
            > code block containing embed data as a
            > dictionary, or a condensed embed data list.
            > If `*datas` is omitted or the only given input is `False`,
            > assume that embed data (Python or JSON embed data)
            > is contained in the invocation message.

            `destination: (Channel) =`
            > A destination channel to send the generated outputs to.
            > If omitted, the destination will be the channel where
            > this command was invoked.

        __Returns__:
            > One or more generated embeds based on the given input.

        __Raises__:
            > `BotException`: One or more given arguments are invalid.
            > `HTTPException`: An invalid operation was blocked by Discord.

        +===+

        Syntax for a condensed embed data list (only works inside of Discord):
        \\`\\`\\`py
        ```py
        # Condensed embed data list syntax. String elements that are empty "" will be ignored.
        # The list must contain at least one argument.
        [
            'author.name' or ('author.name', 'author.url') or ('author.name', 'author.url', 'author.icon_url'),   # embed author

            'title' or ('title', 'url') or ('title', 'url', 'thumbnail.url'),  #embed title, url, thumbnail

            '''desc.''' or ('''desc.''', 'image.url'),  # embed description, image

            0xabcdef, # or -1 for default embed color

            [   # embed fields
            '''
            <field.name|
            ...field.value....
            |field.inline>
            ''',
            ],

            'footer.text' or ('footer.text', 'footer.icon_url'),   # embed footer

            datetime(year, month, day[, hour[, minute[, second[, microsecond]]]]) or '2021-04-17T17:36:00.553' # embed timestamp
        ]
        ```
        \\`\\`\\`

        +===+
        Syntax for a Python dictionary embed:
        \\`\\`\\`py
        ```py
        {
            "title": "title `(<= 256 chars.)`",
            "description":  "this supports [named links](https://discordapp.com) on top of the previously shown subset of markdown."
            "An embed cannot exceed the character count of 6000. (<=2048 chars)",
            "url": "https://discordapp.com",
            "color": 0xABCDEF,    # must be between [0, 0xFFFFFF)
            "timestamp": "1970-01-01T00:00:00.000",  # please use UTC
            "footer": {
            "icon_url": "https://cdn.discordapp.com/embed/avatars/0.png",
            "text": "footer text `(<= 256 chars)` (No markdown support here sorry)"
            },
            "thumbnail": {
            "url": "https://cdn.discordapp.com/embed/avatars/0.png"
            },
            "image": {
            "url": "https://cdn.discordapp.com/embed/avatars/0.png"
            },
            "author": {
            "name": "author name `(<= 256 chars)` (No markdown support here sorry)",
            "url": "https://discordapp.com",
            "icon_url": "https://cdn.discordapp.com/embed/avatars/0.png"
            },
            "fields": [
            {
                "name": ":thinking:",
                "value": "some of these properties have certain limits..."
            },
            {
                "name": ":scream: `(<=256 chars)`",
                "value": "try exceeding some of them! (spoiler: embed fields can't contain more than 1024 chars.)"
            },
            {
                "name": ":rolling_eyes:",
                "value": "Discord will show you a big fat error. :smirk:"
            },
            {
                "name": " :snake: ",
                "value": "these last two",
                "inline": True
            },
            {
                "name": " :pensive: ",
                "value": "are inline fields",
                "inline": True
            }
            ]
        }
        ```
        \\`\\`\\`

        Note: The JSON embed syntax is very similar, however multiline strings,
        and hexadecimal integers and other Python features aren't supported,
        since they would be seen as invalid JSON syntax.
        +===+

        ->example command
        pg!emsudo "This is one embed" "This is another"
        pg!emsudo 987654321987654321
        pg!emsudo
        \\`\\`\\`py
        (
            "Author",
            "Title",
            "desc."
        )
        \\`\\`\\`
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
        """

        if not isinstance(destination, discord.TextChannel):
            destination = self.channel

        if not utils.check_channel_permissions(
            self.author, destination, permissions=("view_channel", "send_messages")
        ):
            raise BotException(
                f"Not enough permissions",
                "You do not have enough permissions to run this command with the specified arguments.",
            )

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

            send_embed_args = dict(description=EmptyEmbed)

            attachment_msg = None
            only_description = False

            if data is False:
                attachment_msg = self.invoke_msg

            elif isinstance(data, String):
                if not data.string:
                    attachment_msg = self.invoke_msg
                else:
                    only_description = True
                    send_embed_args.update(description=data.string)

            elif isinstance(data, discord.Message):
                if not utils.check_channel_permissions(
                    self.author,
                    data.channel,
                    permissions=("view_channel",),
                ):
                    raise BotException(
                        f"Not enough permissions",
                        "You do not have enough permissions to run this command with the specified arguments.",
                    )
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

                    elif isinstance(args, (list, tuple)):
                        try:
                            send_embed_args.update(
                                embed_utils.parse_condensed_embed_list(args)
                            )
                        except ValueError as v:
                            raise BotException(
                                f"Condensed Embed Syntax Error at Input {i}:", v.args[0]
                            )
                        except TypeError:
                            raise BotException(
                                f"Input {i}:",
                                f"Invalid arguments! The condensed embed syntax is:\n\n\\`\\`\\`py\n"
                                f"```py\n{embed_utils.CONDENSED_EMBED_DATA_LIST_SYNTAX}\n```\\`\\`\\`\n"
                                "The input Python `list` or `tuple` must contain at least 1 element.",
                            )

                        output_embeds.append(embed_utils.create(**send_embed_args))
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
                    embed_utils.create(description=send_embed_args["description"])
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
            await destination.send(embed=embed)

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
        try:
            await self.invoke_msg.delete()
            await self.response_msg.delete(delay=10.0 if data_count > 2 else 0)
        except discord.NotFound:
            pass

    @add_group("emsudo", "add")
    async def cmd_emsudo_add(
        self,
        msg: discord.Message,
        data: Optional[Union[discord.Message, CodeBlock, String, bool]] = None,
        overwrite: bool = False,
    ):
        """
        ->type emsudo commands
        ->signature pg!emsudo add <message> [data] [overwrite=False]
        ->description Add an embed through the bot
        ->extended description
        Add an embed to a message.

        __Args__:
            `data: (Message|CodeBlock|String|bool) =`
            > Data to create an embed from.
            > Can be a discord message whose first attachment contains
            > JSON or Python embed data, a string
            > (will only affect a embed description field),
            > a code block containing JSON embed data
            > (use the \\`\\`\\`json prefix), or a Python
            > code block containing embed data as a
            > dictionary, or a condensed embed data list.
            > If omitted or the only input is `False`,
            > assume that embed data (Python or JSON embed data)
            > is contained in the invocation message.

            `overwrite: (bool) = False`
            > If set to `True`, replace the previously
            > existing embed of the target message.
            > `False` will trigger a `BotException`.

        __Raises__:
            > `BotException`: One or more given arguments are invalid.
            > `HTTPException`: An invalid operation was blocked by Discord.

        ->example command
        pg!emsudo add 987654321987654321 "A wild __Embed__ appeared!"
        pg!emsudo add 987654321987654321 123456789012345678
        pg!emsudo add 987654321987654321
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
        """

        if not msg.embeds or overwrite:
            await self.cmd_emsudo_replace(msg=msg, data=data, _add=True)
        else:
            raise BotException(
                "Cannot overwrite embed!",
                "The given message's embed cannot be overwritten when"
                " `overwrite=` is set to `False`",
            )

    @add_group("emsudo", "remove")
    async def cmd_emsudo_remove(
        self,
        *msgs: discord.Message,
        a: String = String(""),
        attributes: String = String(""),
    ):
        """
        ->type emsudo commands
        ->signature pg!emsudo remove <*messages> [a|attributes=""]
        ->description Remove embeds (or their attributes) through the bot
        ->extended description
        Remove an embed or only their specified attributes from several messages.

        __Args__:
            `*messages: (Message)`
            > A sequence of messages with an embed.

            `a|attributes: (String) =`
            > A string containing the attributes to delete
            > from the target embeds. If those attributes
            > have attributes themselves
            > (e.g. `author`, `fields`, `footer`),
            > then those can be specified using the dot `.`
            > operator inside this string.
            > If omitted or empty, all target message
            > embeds will be deleted as a whole.
            > Embed attributes that become invalid
            > upon the deletion of their sub-attributes
            > (if present) will be deleted as a whole, and
            > the deletion of too many attributes might lead
            > to the complete deletion of a target embed.

        __Raises__:
            > `BotException`: One or more given arguments are invalid.
            > `HTTPException`: An invalid operation was blocked by Discord.

        ->example command
        pg!emsudo remove 98765432198765444321
        pg!emsudo remove 123456789123456789/98765432198765444321 a="description fields.0 fields.1.name author.url"
        pg!emsudo remove 123456789123456789/98765432198765444321 attributes="fields author footer.icon_url"
        -----
        """

        checked_channels = set()
        for i, msg in enumerate(msgs):
            if not msg.channel in checked_channels:
                if not utils.check_channel_permissions(
                    self.author,
                    msg.channel,
                    permissions=("view_channel", "send_messages"),
                ):
                    raise BotException(
                        f"Not enough permissions",
                        "You do not have enough permissions to run this command with the specified arguments.",
                    )
                elif not msg.embeds:
                    raise BotException(
                        f"Input {i}: Cannot execute command:",
                        "No embed data found in message.",
                    )
                else:
                    checked_channels.add(msg.channel)

            if not i % 50:
                await asyncio.sleep(0)

        if not msgs:
            raise BotException(
                f"Invalid arguments!",
                "No messages given as input.",
            )

        load_embed = embed_utils.create(
            title=f"Your command is being processed:",
            fields=(("\u2800", "`...`", False),),
        )

        attribs = (
            a.string if a.string else attributes.string if attributes.string else ""
        )

        try:
            embed_mask_dict = embed_utils.create_embed_mask_dict(
                attributes=attribs,
                allow_system_attributes=True,
                fields_as_field_dict=True,
            )
        except ValueError as v:
            raise BotException("An attribute string parsing error occured:", v.args[0])
        msg_count = len(msgs)

        if attribs:
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
                msg_embed = msg.embeds[0]
                embed_dict = msg_embed.to_dict()

                if embed_mask_dict:
                    if "fields" in embed_dict and "fields" in embed_mask_dict:
                        field_list = embed_dict["fields"]
                        embed_dict["fields"] = {
                            str(i): field_list[i] for i in range(len(field_list))
                        }

                        embed_utils.recursive_delete(embed_dict, embed_mask_dict)

                        if "fields" in embed_dict:
                            field_dict = embed_dict["fields"]
                            embed_dict["fields"] = [
                                field_dict[i] for i in sorted(field_dict.keys())
                            ]
                    else:
                        embed_utils.recursive_delete(embed_dict, embed_mask_dict)
                else:
                    embed_utils.recursive_delete(embed_dict, embed_mask_dict)

                if embed_dict:
                    embed_dict = embed_utils.clean_embed_dict(embed_dict)
                    if embed_dict:
                        final_embed = discord.Embed.from_dict(embed_dict)
                    else:
                        final_embed = None
                else:
                    final_embed = None

                await msg.edit(embed=final_embed)
                await asyncio.sleep(0)
        else:
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
                await msg.edit(embed=None)
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

        try:
            await self.invoke_msg.delete()
            await self.response_msg.delete(delay=10.0 if msg_count > 2 else 0.0)
        except discord.NotFound:
            pass

    @add_group("emsudo", "replace")
    async def cmd_emsudo_replace(
        self,
        msg: discord.Message,
        data: Optional[Union[discord.Message, CodeBlock, String, bool]] = None,
        *,
        _add: bool = False,
    ):
        """
        ->type emsudo commands
        ->signature pg!emsudo replace <message> [data]
        ->description Replace an embed through the bot
        ->extended description
        Replace the embed of a message with a new one using the given arguments.

        __Args__:
            `data: (Message|CodeBlock|String|bool) =`
            > Data to replace the target embed from.
            > Can be a discord message whose first attachment contains
            > JSON or Python embed data, a string
            > (will only affect a embed description field),
            > a code block containing JSON embed data
            > (use the \\`\\`\\`json prefix), or a Python
            > code block containing embed data as a
            > dictionary, or a condensed embed data list.
            > If omitted or the only input is `False`,
            > assume that embed data (Python or JSON embed data)
            > is contained in the invocation message.

        __Raises__:
            > `BotException`: One or more given arguments are invalid.
            > `HTTPException`: An invalid operation was blocked by Discord.

        ->example command
        pg!emsudo replace 987654321987654321 "Whoops the embed is boring now"
        pg!emsudo replace 987654321987654321 123456789012345678
        pg!emsudo replace 987654321987654321/123456789123456789
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

        replace_embed_args = dict(
            description=EmptyEmbed,
        )

        if not msg.embeds and not _add:
            raise BotException(
                "No embed data found", "No embed data to be replaced was found"
            )

        attachment_msg = None
        only_description = False

        if data is None or data is False:
            attachment_msg = self.invoke_msg

        elif isinstance(data, String):
            if not data.string:
                attachment_msg = self.invoke_msg
            else:
                only_description = True
                replace_embed_args.update(description=data.string)

        elif isinstance(data, discord.Message):
            if not utils.check_channel_permissions(
                self.author,
                data.channel,
                permissions=("view_channel",),
            ):
                raise BotException(
                    f"Not enough permissions",
                    "You do not have enough permissions to run this command with the specified arguments.",
                )
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
                    try:
                        replace_embed_args.update(
                            embed_utils.parse_condensed_embed_list(args)
                        )
                    except ValueError as v:
                        raise BotException(f"Condensed Embed Syntax Error:", v.args[0])
                    except TypeError:
                        raise BotException(
                            "Invalid arguments!",
                            f"The condensed embed syntax is:\n\n\\`\\`\\`py\n"
                            f"```py\n{embed_utils.CONDENSED_EMBED_DATA_LIST_SYNTAX}\n```\\`\\`\\`\n"
                            "The input Python `list` or `tuple` must contain at least 1 element.",
                        )

                    await embed_utils.replace_2(msg, **replace_embed_args)
                else:
                    raise BotException(
                        f"Invalid arguments!",
                        "A code block given as input must"
                        " contain either a Python `tuple`/`list` of embed data, or a"
                        " Python `dict` of embed data matching the JSON structure of"
                        " a Discord embed object, or JSON embed data (\n\\`\\`\\`json\n"
                        "data\n\\`\\`\\`\n)",
                    )

        try:
            await self.invoke_msg.delete()
            await self.response_msg.delete()
        except discord.NotFound:
            pass

    @add_group("emsudo", "edit")
    async def cmd_emsudo_edit(
        self,
        msg: discord.Message,
        *datas: Optional[Union[discord.Message, CodeBlock, String, bool]],
        add_attributes: bool = True,
        inner_fields: bool = False,
    ):
        """
        ->type emsudo commands
        ->signature pg!emsudo edit <message> <*datas> [add_atributes=True] [inner_fields=False]
        ->description Edit an embed through the bot
        ->extended description
        Edit the embed of a message using the given inputs.

        __Args__:
            `*datas: (Message|CodeBlock|String|bool)`
            > A sequence of data to modify the target embed from.
            > Each can be a discord message whose first attachment contains
            > JSON or Python embed data, a string
            > (will only affect a embed description field),
            > a code block containing JSON embed data
            > (use the \\`\\`\\`json prefix), or a Python
            > code block containing embed data as a
            > dictionary, or a condensed embed data list.
            > If `*datas` is omitted or the only given input is `False`,
            > assume that embed data (Python or JSON embed data)
            > is contained in the invocation message.
            > The given embed data must not represent
            > a valid and complete embed, as only the
            > attributes that are meant to change
            > need to be supplied.

            `add_attributes: (bool) = True`
            > Whether the input embed data should add new
            > attributes to the embed in the target message.
            > If set to `False`, only the attributes present
            > in the target embed will be changed.

            `inner_fields: (bool) = False`
            > If set to `True`, the embed fields of the target
            > embed (if present) also will be able to be
            > individually modified by the given input
            > embed data. If `False`, all embed fields will
            > be modified as a single embed attribute.

        +===+

        __Raises__:
            > `BotException`: One or more given arguments are invalid.
            > `HTTPException`: An invalid operation was blocked by Discord.

        ->example command pg!emsudo_edit 987654321987654321 "Lol only the embed description changed"
        pg!emsudo edit 987654321987654321 123456789012345678 251613726327333621
        pg!emsudo edit 987654321987654321
        \\`\\`\\`json
        {
            "title": "An Embed Edit",
            "footer": {
                "text": "yet another footer text"
                }
        }
        \\`\\`\\`
        -----
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

            edit_embed_args = dict(
                description=EmptyEmbed,
            )

            attachment_msg: Optional[discord.Message] = None
            only_description = False

            if not data:
                attachment_msg = self.invoke_msg

            elif isinstance(data, String):
                if not data.string:
                    attachment_msg = self.invoke_msg
                else:
                    only_description = True
                    edit_embed_args.update(description=data.string)

            elif isinstance(data, discord.Message):
                if not utils.check_channel_permissions(
                    self.author,
                    data.channel,
                    permissions=("view_channel",),
                ):
                    raise BotException(
                        f"Not enough permissions",
                        "You do not have enough permissions to run this command with the specified arguments.",
                    )
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
                    inner_fields=inner_fields,
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
                        inner_fields=inner_fields,
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
                            inner_fields=inner_fields,
                        )

                    elif isinstance(args, (list, tuple)):
                        try:
                            edit_embed_args.update(
                                embed_utils.parse_condensed_embed_list(args)
                            )
                        except ValueError as v:
                            raise BotException(f"Input {i}:", v.args[0])
                        except TypeError:
                            raise BotException(
                                f"Input {i}:",
                                f"Invalid arguments! The condensed embed syntax is:\n\n\\`\\`\\`py\n"
                                f"```py\n{embed_utils.CONDENSED_EMBED_DATA_LIST_SYNTAX}\n```\\`\\`\\`\n"
                                "The input Python `list` or `tuple` must contain at least 1 element.",
                            )

                        embed_dict = embed_utils.create_as_dict(
                            **edit_embed_args,
                        )
                        edited_embed_dict = embed_utils.edit_dict_from_dict(
                            edited_embed_dict,
                            embed_dict,
                            add_attributes=add_attributes,
                            inner_fields=inner_fields,
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
                    description=edit_embed_args["description"],
                    color=-1,
                )
                edited_embed_dict = embed_utils.edit_dict_from_dict(
                    edited_embed_dict,
                    embed_dict,
                    add_attributes=add_attributes,
                    inner_fields=inner_fields,
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
                inner_fields=inner_fields,
            )

            await embed_utils.edit_from_dict(
                msg,
                msg_embed,
                edited_embed_dict,
                add_attributes=add_attributes,
                inner_fields=inner_fields,
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
        try:
            await self.invoke_msg.delete()
            await self.response_msg.delete(delay=10.0 if data_count > 2 else 0.0)
        except discord.NotFound:
            pass

    @add_group("emsudo", "swap")
    async def cmd_emsudo_swap(
        self,
        msg_a: discord.Message,
        msg_b: discord.Message,
    ):
        """
        ->type More emsudo commands
        ->signature pg!emsudo swap <message> <message>
        ->description Swap embeds between messages through the bot
        ->extended description
        Swap the embeds of two given messages.

        __Args__:
            `message_a: (Message)`
            > A discord message whose embed
            > should be swapped with that of `message_b`.

            `message_b: (Message)`
            > Another discord message whose embed
            > should be swapped with that of `message_a`.

        __Raises__:
            > `BotException`: One or more given arguments are invalid.
            > `HTTPException`: An invalid operation was blocked by Discord.

        ->example command pg!emsudo swap 123456789123456789 69696969969669420
        -----
        """

        if not utils.check_channel_permissions(
            self.author,
            msg_a.channel,
            permissions=("view_channel", "send_messages"),
        ) or not utils.check_channel_permissions(
            self.author,
            msg_b.channel,
            permissions=("view_channel", "send_messages"),
        ):
            raise BotException(
                f"Not enough permissions",
                "You do not have enough permissions to run this command with the specified arguments.",
            )

        bot_id = common.bot.user.id

        if not msg_a.embeds or not msg_b.embeds:
            raise BotException(
                "Cannot execute command:",
                "No embed data found in on of the given messages.",
            )

        elif bot_id not in (msg_a.author.id, msg_b.author.id):
            raise BotException(
                "Cannot execute command:",
                f"Both messages must have been authored by me, {common.bot.user.mention}.",
            )

        msg_embed_a = msg_a.embeds[0]
        msg_embed_b = msg_b.embeds[0]

        await msg_a.edit(embed=msg_embed_b)
        await msg_b.edit(embed=msg_embed_a)

        try:
            await self.invoke_msg.delete()
            await self.response_msg.delete()
        except discord.NotFound:
            pass

    @add_group("emsudo", "clone")
    async def cmd_emsudo_clone(
        self, *msgs: discord.Message, destination: Optional[discord.TextChannel] = None
    ):
        """
        ->type emsudo commands
        ->signature pg!emsudo clone <*messages> [destination]
        ->description Clone all embeds.
        ->extended description
        Get a message's embeds from the given arguments and send them
        as another message (each only containing embeds) to the specified destination channel.

        __Args__:
            `*messages: (Message)`
            > A sequence of discord messages whose embeds should be cloned

            `inner_fields: (bool) = False`
            > If set to `True`, the embed fields of the target
            > embed (if present) also will be able to be
            > individually modified by the given input
            > embed data. If `False`, all embed fields will
            > be modified as a single embed attribute.

        __Returns__:
            > One or more clones of embeds in messages based on the given input.

        __Raises__:
            > `BotException`: One or more given arguments are invalid.
            > `HTTPException`: An invalid operation was blocked by Discord.

        ->example command
        pg!emsud clone 987654321987654321 123456789123456789
        https://discord.com/channels/772505616680878080/841726972841558056/846870368672546837
        -----
        """

        if not isinstance(destination, discord.TextChannel):
            destination = self.channel

        if not utils.check_channel_permissions(
            self.author, destination, permissions=("view_channel", "send_messages")
        ):
            raise BotException(
                f"Not enough permissions",
                "You do not have enough permissions to run this command with the specified arguments.",
            )

        checked_channels = set()
        for i, msg in enumerate(msgs):
            if not msg.channel in checked_channels:
                if not utils.check_channel_permissions(
                    self.author, msg.channel, permissions=("view_channel",)
                ):
                    raise BotException(
                        f"Not enough permissions",
                        "You do not have enough permissions to run this command with the specified arguments.",
                    )
                elif not msg.embeds:
                    raise BotException(
                        f"Input {i}: Cannot execute command:",
                        "No embed data found in message.",
                    )
                else:
                    checked_channels.add(msg.channel)

            if not i % 50:
                await asyncio.sleep(0)

        if not msgs:
            raise BotException(
                f"Invalid arguments!",
                "No messages given as input.",
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
            await destination.trigger_typing()
            embed_count = len(msg.embeds)
            for j, embed in enumerate(msg.embeds):
                if msg_count > 2 and not j % 3:
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
                    await destination.trigger_typing()

                await destination.send(embed=embed)

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

        try:
            await self.response_msg.delete(delay=10.0 if msg_count > 2 else 0.0)
        except discord.NotFound:
            pass

    @add_group("emsudo", "get")
    async def cmd_emsudo_get(
        self,
        *msgs: discord.Message,
        a: String = String(""),
        attributes: String = String(""),
        mode: int = 0,
        destination: Optional[discord.TextChannel] = None,
        output_name: String = String("(add a title by editing this embed)"),
        pop: bool = False,
        system_attributes: bool = False,
        as_json: bool = True,
        as_python: bool = False,
    ):
        """
        ->type emsudo commands
        ->signature pg!emsudo get <*messages> [a|attributes=""] [mode=0] [destination=] [output_name=""] [system_attributes=False] [as_json=True] [as_python=False]

        ->description Get the embed data of a message
        ->extended description
        Get the contents of the embed of a message from the given arguments and send it as another message
        to a given destination channel in a serialized form.

        __Args__:
            `*messages: (Message)`
            > A sequence of discord messages whose embeds should
            > be serialized into a JSON or Python format.

            `destination (TextChannel) = `
            > A destination channel to send the output to.

            `a|attributes: (String) =`
            > A string containing the attributes to extract
            > from the target embeds. If those attributes
            > have attributes themselves
            > (e.g. `author`, `fields`, `footer`),
            > then those can be specified using the dot `.`
            > operator inside this string.
            > If omitted or empty, the attributes of
            > all target message embeds will be serialized.
            > Embed attributes that become invalid
            > upon their extraction (missing required sub-attributes, etc.)
            > will still be included in the serialized output,
            > but that output might not be enough
            > to successfully generate embeds anymore.

            `mode: (bool) = 0`
            > `0`: Embed serialization only.
            > `1`: Embed creation from the selected
            > attributes (when possible).
            > `2`: `0` and `1` together.

            +===+

            `output_name (String) =`
            > A name for the first output data.

            `system_attributes: (bool) = True`
            > Whether to include Discord generated embed
            > attributes in the serialized output.

            `as_python (bool) = False``as_json (bool) = True`
            > If `as_python=` is `True` send `.py` output,
            > else if `as_json=` is `True` send `.json` output,
            > otherwise send `.txt` output.


        __Raises__:
            > `BotException`: One or more given arguments are invalid.
            > `HTTPException`: An invalid operation was blocked by Discord.
        ->example command
        pg!emsudo get 98765432198765444321
        pg!emsudo get 123456789123456789/98765432198765444321 a="description fields.0 fields.1.name author.url"
        pg!emsudo get 123456789123456789/98765432198765444321 attributes="fields author footer.icon_url"
        -----
        """

        output_name = output_name.string
        if not isinstance(destination, discord.TextChannel):
            destination = self.channel

        if not utils.check_channel_permissions(
            self.author, destination, permissions=("view_channel", "send_messages")
        ):
            raise BotException(
                f"Not enough permissions",
                "You do not have enough permissions to run this command with the specified arguments.",
            )

        checked_channels = set()
        for i, msg in enumerate(msgs):
            if not msg.channel in checked_channels:
                if not utils.check_channel_permissions(
                    self.author, msg.channel, permissions=("view_channel",)
                ):
                    raise BotException(
                        f"Not enough permissions",
                        "You do not have enough permissions to run this command with the specified arguments.",
                    )
                elif not msg.embeds:
                    raise BotException(
                        f"Input {i}: Cannot execute command:",
                        "No embed data found in message.",
                    )
                else:
                    checked_channels.add(msg.channel)

            if not i % 50:
                await asyncio.sleep(0)

        if not msgs:
            raise BotException(
                f"Invalid arguments!",
                "No messages given as input.",
            )

        if mode < 0 or mode > 2:
            raise BotException(
                f"Invalid arguments!",
                "`mode=` must be either `0` or `1`",
            )

        attribs = (
            a.string if a.string else attributes.string if attributes.string else ""
        )

        try:
            embed_mask_dict = embed_utils.create_embed_mask_dict(
                attributes=attribs,
                allow_system_attributes=system_attributes,
                fields_as_field_dict=True,
            )
        except ValueError as v:
            raise BotException("An attribute string parsing error occured:", v.args[0])

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
            await destination.trigger_typing()
            embed_count = len(msg.embeds)
            for j, embed in enumerate(msg.embeds):
                if msg_count > 2 and embed_count > 2 and not j % 3:
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
                pop_embed_dict = embed_utils.copy_embed_dict(embed_dict)  # circumvents discord.py bug
                corrected_embed_dict = None
                corrected_pop_embed_dict = None
                if embed_mask_dict:
                    if "fields" in embed_dict and "fields" in embed_mask_dict:
                        field_list = embed_dict["fields"]
                        embed_dict["fields"] = {
                            str(i): field_list[i] for i in range(len(field_list))
                        }
                        field_list = pop_embed_dict["fields"]
                        pop_embed_dict["fields"] = {
                            str(i): field_list[i] for i in range(len(field_list))
                        }

                        print("pop_embed_dict (before filter):", pop_embed_dict)

                        if not system_attributes:
                            embed_utils.recursive_delete(
                                embed_dict,
                                embed_utils.EMBED_SYSTEM_ATTRIBUTES_MASK_DICT,
                            )
                        
                        embed_utils.recursive_delete(
                            embed_dict, embed_mask_dict, inverse=True
                        )
                        if "fields" in embed_dict:
                            field_dict = embed_dict["fields"]
                            embed_dict["fields"] = [
                                field_dict[i] for i in sorted(field_dict.keys())
                            ]

                        embed_utils.recursive_delete(
                            pop_embed_dict, embed_mask_dict
                        )

                        if "fields" in pop_embed_dict:
                            field_dict = pop_embed_dict["fields"]
                            pop_embed_dict["fields"] = [
                                field_dict[i] for i in sorted(field_dict.keys())
                            ]
                    else:
                        if not system_attributes:
                            embed_utils.recursive_delete(
                                embed_dict,
                                embed_utils.EMBED_SYSTEM_ATTRIBUTES_MASK_DICT,
                            )
                        embed_utils.recursive_delete(
                            embed_dict, embed_mask_dict, inverse=True
                        )
                        embed_utils.recursive_delete(
                            pop_embed_dict, embed_mask_dict
                        )
                else:
                    if not system_attributes:
                        embed_utils.recursive_delete(
                            embed_dict, embed_utils.EMBED_SYSTEM_ATTRIBUTES_MASK_DICT
                        )

                if embed_dict and embed_mask_dict:
                    if mode == 1 or mode == 2:
                        corrected_embed_dict = embed_utils.clean_embed_dict(
                            embed_utils.copy_embed_dict(embed_dict)
                        )
                else:
                    raise BotException(
                        "Cannot execute command:",
                        "Could not find data that matches"
                        " the pattern of the given embed attribute filter string.",
                    )

                if pop and pop_embed_dict and embed_mask_dict:
                    #corrected_pop_embed_dict = embed_utils.clean_embed_dict(
                    #    embed_utils.copy_embed_dict(pop_embed_dict)
                    #)
                    corrected_pop_embed_dict = embed_utils.copy_embed_dict(pop_embed_dict)

                if mode == 0 or mode == 2:
                    if mode == 2 and corrected_embed_dict and embed_utils.validate_embed_dict(
                        corrected_embed_dict
                    ):
                        await destination.send(
                            embed=discord.Embed.from_dict(corrected_embed_dict)
                        )
                    with io.StringIO() as fobj:
                        embed_utils.export_embed_data(
                            {
                                k: embed_dict[k]
                                for k in embed_utils.EMBED_TOP_LEVEL_ATTRIBUTES_MASK_DICT
                                if k in embed_dict
                            },
                            fp=fobj,
                            indent=4,
                            as_json=True if as_json and not as_python else False,
                        )
                        fobj.seek(0)
                        await destination.send(
                            embed=embed_utils.create(
                                author_name="Embed Data",
                                title=(output_name)
                                if len(msgs) < 2
                                else "(add a title by editing this embed)",
                                fields=(
                                    (
                                        "\u2800",
                                        f"**[View Original Message]({msg.jump_url})**",
                                        True,
                                    ),
                                ),
                                footer_text="Structural validity: "
                                + (
                                    "Valid."
                                    if embed_utils.validate_embed_dict(embed_dict)
                                    else "Invalid.\nMight lead to embed creation errors when used alone."
                                ),
                            ),
                            file=discord.File(
                                fobj,
                                filename=(
                                    "embeddata.py"
                                    if as_python
                                    else "embeddata.json"
                                    if as_json
                                    else "embeddata.txt"
                                ),
                            ),
                        )

                elif mode == 1:
                    if corrected_embed_dict and embed_utils.validate_embed_dict(corrected_embed_dict):
                        await destination.send(
                            embed=discord.Embed.from_dict(corrected_embed_dict)
                        )
                    else:
                        raise BotException(
                            "Invalid embed creation data",
                            "Could not generate a valid embed from the extracted embed attributes.",
                        )

                if pop and corrected_pop_embed_dict:
                    await msg.edit(embed=discord.Embed.from_dict(corrected_pop_embed_dict))
                    

            if embed_count > 2:
                await embed_utils.edit_field_from_dict(
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

        try:
            await self.response_msg.delete(delay=10.0 if msg_count > 2 else 0.0)
        except discord.NotFound:
            pass

    @add_group("emsudo", "add", "field")
    async def cmd_emsudo_add_field(
        self,
        msg: discord.Message,
        data: Union[CodeBlock, String],
    ):
        """
        ->type More emsudo commands
        ->signature pg!emsudo add field <message> <data>
        ->description Add an embed field through the bot
        ->extended description
        Add an embed field to the embed of the given message.

        __Args__:
            `message: (Message)`
            > A discord message whose embed
            > should be modified.

            `data: (CodeBlock|String)`
            > Data to modify the target embed with.
            > Can be a string matching the 'condensed
            > embed data list' syntax for an embed field
            > `"<name|value[|inline]>"`, or a code block
            > containing JSON embed field data
            > (use the \\`\\`\\`json prefix), or a Python
            > code block containing embed field data as a
            > dictionary, or a condensed embed data list.

        __Raises__:
            > `BotException`: One or more given arguments are invalid.
            > `HTTPException`: An invalid operation was blocked by Discord.

        ->example command
        pg!emsudo add field 987654321987654321/123456789123456789
        \\`\\`\\`json
        {
           "name": "Mr Field",
           "value": "I value nothing",
           "inline": false
        }
        \\`\\`\\`
        -----
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
        try:
            await self.invoke_msg.delete()
            await self.response_msg.delete()
        except discord.NotFound:
            pass

    @add_group("emsudo", "add", "fields")
    async def cmd_emsudo_add_fields(
        self,
        msg: discord.Message,
        data: Optional[Union[discord.Message, CodeBlock, String, bool]] = None,
    ):
        """
        ->type More emsudo commands
        ->signature pg!emsudo add fields <message> [data]
        ->description Add embed fields through the bot
        ->extended description
        Add multiple embed fields to the embed of a message using the given arguments.

        __Args__:
            `message: (Message)`
            > A discord message whose embed
            > should be modified.

            `data: (Message|CodeBlock|String|bool) =`
            > Data to modify the target embed with.
            > Can be a discord message whose first attachment contains
            > JSON or Python embed field data, an empty string
            > (retrieves embed data from to the
            > invocation message of this command),
            > a code block containing JSON embed field data
            > (use the \\`\\`\\`json prefix), or a Python
            > code block containing embed field data as a
            > dictionary or the 'condensed embed data list'
            > syntax for multiuple embed fields
            > `["<name|value[|inline]>",...]`.
            > If omitted or the only input is `False`,
            > assume that embed data (Python or JSON embed data)
            > is contained in the invocation message.

        __Raises__:
            > `BotException`: One or more given arguments are invalid.
            > `HTTPException`: An invalid operation was blocked by Discord.

        ->example command
        pg!emsudo add fields 987654321987654321/123456789123456789
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

        if data is None or data is False:
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
            if not utils.check_channel_permissions(
                self.author,
                data.channel,
                permissions=("view_channel",),
            ):
                raise BotException(
                    f"Not enough permissions",
                    "You do not have enough permissions to run this command with the specified arguments.",
                )
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

        try:
            await self.invoke_msg.delete()
            await self.response_msg.delete()
        except discord.NotFound:
            pass

    @add_group("emsudo", "add", "field", "at")
    async def cmd_emsudo_add_field_at(
        self,
        msg: discord.Message,
        index: int,
        data: Union[CodeBlock, String],
    ):
        """
        ->type More emsudo commands
        ->signature pg!emsudo add field at <message> <index> <data>
        ->description Insert an embed field through the bot
        ->extended description
        Insert an embed field to the embed of the given message at the specified index.

        __Args__:
            `message: (Message)`
            > A discord message whose embed
            > should be modified.

            `index: (int)`
            > The index to insert the input embed field at.

            `data: (CodeBlock|String)`
            > Data to modify the target embed with.
            > Can be a string matching the 'condensed
            > embed data list' syntax for an embed field
            > `"<name|value[|inline]>"`, or a code block
            > containing JSON embed field data
            > (use the \\`\\`\\`json prefix), or a Python
            > code block containing embed field data as a
            > dictionary, or a condensed embed data list.

        __Raises__:
            > `BotException`: One or more given arguments are invalid.
            > `HTTPException`: An invalid operation was blocked by Discord.

        ->example command
        pg!emsudo add field at https://discord.com/channels/772505616680878080/775317562715406336/846955385688031282 2
        \\`\\`\\`json
        {
            "name": "Mrs Field",
            "value": "I value nothing more than my husband",
            "inline": true
        }
        \\`\\`\\`
        -----
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
        try:
            await self.invoke_msg.delete()
            await self.response_msg.delete()
        except discord.NotFound:
            pass

    @add_group("emsudo", "add", "fields", "at")
    async def cmd_emsudo_add_fields_at(
        self,
        msg: discord.Message,
        index: int,
        data: Optional[Union[discord.Message, CodeBlock, String, bool]] = None,
    ):
        """
        ->type More emsudo commands
        ->signature pg!emsudo add fields at <message> <index> [data]
        ->description Insert embed fields through the bot
        ->extended description
        Insert several embed fields into the embed of the given message at the specified index.

        __Args__:
            `message: (Message)`
            > A discord message whose embed
            > should be modified.

            `index: (int)`
            > The index to insert the input embed field at.

            `data: (Message|CodeBlock|String|bool) =`
            > Data to modify the target embed with.
            > Can be a discord message whose first attachment contains
            > JSON or Python embed field data, an empty string
            > (retrieves embed data from to the
            > invocation message of this command),
            > a code block containing JSON embed field data
            > (use the \\`\\`\\`json prefix), or a Python
            > code block containing embed field data as a
            > dictionary or the 'condensed embed data list'
            > syntax for multiuple embed fields
            > `["<name|value[|inline]>",...]`.
            > If omitted or the only input is `False`,
            > assume that embed data (Python or JSON embed data)
            > is contained in the invocation message.

        __Raises__:
            > `BotException`: One or more given arguments are invalid.
            > `HTTPException`: An invalid operation was blocked by Discord.

        ->example command
        pg!emsudo add fields at 2 987654321987654321/123456789123456789
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

        if data is None or data is False:
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
            if not utils.check_channel_permissions(
                self.author,
                data.channel,
                permissions=("view_channel",),
            ):
                raise BotException(
                    f"Not enough permissions",
                    "You do not have enough permissions to run this command with the specified arguments.",
                )
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

        try:
            await self.invoke_msg.delete()
            await self.response_msg.delete()
        except discord.NotFound:
            pass

    @add_group("emsudo", "edit", "field")
    async def cmd_emsudo_edit_field(
        self,
        msg: discord.Message,
        index: int,
        data: Union[CodeBlock, String],
    ):
        """
        ->type More emsudo commands
        ->signature pg!emsudo edit field <message> <index> <data>
        ->description Edit an embed field through the bot
        ->extended description
        Edit an embed field of the embed of the given message at the specified index.

        __Args__:
            `message: (Message)`
            > A discord message whose embed
            > should be modified.

            `index: (int)`
            > The index to insert the input embed field at.

            `data: (CodeBlock|String)`
            > Data to modify the target embed with.
            > Can be a string matching the 'condensed
            > embed data list' syntax for an embed field
            > `"<name|value[|inline]>"`, or a code block
            > containing JSON embed field data
            > (use the \\`\\`\\`json prefix), or a Python
            > code block containing embed field data as a
            > dictionary, or a condensed embed data list.
            > Note that the given embed field data musn't
            > represent a valid embed field, as only the
            > attributes that should change need to be
            > specified.

        __Raises__:
            > `BotException`: One or more given arguments are invalid.
            > `HTTPException`: An invalid operation was blocked by Discord.

        pg!emsudo edit field 7 987654321987654321/123456789123456789
        \\`\\`\\`json
        {
           "name": "Boy Field",
           "value": "I value nothing",
           "inline": false
        }
        \\`\\`\\`
        -----
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

        try:
            await self.invoke_msg.delete()
            await self.response_msg.delete()
        except discord.NotFound:
            pass

    @add_group("emsudo", "edit", "fields")
    async def cmd_emsudo_edit_fields(
        self,
        msg: discord.Message,
        data: Optional[Union[discord.Message, CodeBlock, String, bool]] = None,
    ):
        """
        ->type More emsudo commands
        ->signature pg!emsudo edit fields <message> [data]
        ->description Edit multiple embed fields through the bot
        ->extended description
        Edit multiple embed fields in the embed of the given message using the specified arguments.
        Combining the new fields with the old fields works like a bitwise OR operation from the
        first to the last embed field, where any embed field argument that is passed
        to this command that is empty (empty `dict` `{}` or empty `str` `''`)
        will not modify the embed field at its index when passed to this command.

        __Args__:
            `message: (Message)`
            > A discord message whose embed
            > should be modified.

            `data: (Message|CodeBlock|String|bool) =`
            > Data to modify the target embed with.
            > Can be a discord message whose first attachment contains
            > JSON or Python embed field data, an empty string
            > (retrieves embed data from to the
            > invocation message of this command),
            > a code block containing JSON embed field data
            > (use the \\`\\`\\`json prefix), or a Python
            > code block containing embed field data as a
            > dictionary or the 'condensed embed data list'
            > syntax for multiuple embed fields
            > `["<name|value[|inline]>",...]`.
            > If omitted or the only input is `False`,
            > assume that embed data (Python or JSON embed data)
            > is contained in the invocation message.

        __Raises__:
            > `BotException`: One or more given arguments are invalid.
            > `HTTPException`: An invalid operation was blocked by Discord.


        ->example command
        pg!emsudo edit fields 987654321987654321/123456789123456789
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

        if data is None or data is False:
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
            if not utils.check_channel_permissions(
                self.author,
                data.channel,
                permissions=("view_channel",),
            ):
                raise BotException(
                    f"Not enough permissions",
                    "You do not have enough permissions to run this command with the specified arguments.",
                )
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

        try:
            await self.invoke_msg.delete()
            await self.response_msg.delete()
        except discord.NotFound:
            pass

    @add_group("emsudo", "replace", "field")
    async def cmd_emsudo_replace_field(
        self,
        msg: discord.Message,
        index: int,
        data: Union[CodeBlock, String],
    ):
        """
        ->type More emsudo commands
        ->signature pg!emsudo replace field <message> <index> <data>
        ->description Replace an embed field through the bot
        ->extended description
        Replace an embed field of the embed of the given message at the specified index.

        __Args__:
            `message: (Message)`
            > A discord message whose embed
            > should be modified.

            `index: (int)`
            > The index to insert the input embed field at.

            `data: (CodeBlock|String)`
            > Data to modify the target embed with.
            > Can be a string matching the 'condensed
            > embed data list' syntax for an embed field
            > `"<name|value[|inline]>"`, or a code block
            > containing JSON embed field data
            > (use the \\`\\`\\`json prefix), or a Python
            > code block containing embed field data as a
            > dictionary, or a condensed embed data list.

        __Raises__:
            > `BotException`: One or more given arguments are invalid.
            > `HTTPException`: An invalid operation was blocked by Discord.

        ->example command
        pg!emsudo replace field 2 987654321987654321/123456789123456789
        \\`\\`\\`json
        {
           "name": "Uncle Field",
           "value": "values.",
           "inline": false
        }
        \\`\\`\\`
        Replace an embed field at the given index in the embed of a message in the channel where this command was invoked using the given arguments.
        -----
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

        try:
            await self.invoke_msg.delete()
            await self.response_msg.delete()
        except discord.NotFound:
            pass

    @add_group("emsudo", "swap", "fields")
    async def cmd_emsudo_swap_fields(
        self, msg: discord.Message, index_a: int, index_b: int
    ):
        """
        ->type More emsudo commands
        ->signature pg!emsudo swap fields <message> <index_a> <index_b>
        ->description Swap embed fields through the bot
        ->extended description
        Swap the positions of embed fields at the given indices of
        the embed of a message, using the given arguments.

        __Args__:
            `message: (Message)`
            > A discord message whose embed
            > should be modified.

            `index_a: (int)`
            > An index of an existing embed field.

            `index_b: (int)`
            > An index of another existing embed field.

        __Raises__:
            > `BotException`: One or more given arguments are invalid.
            > `HTTPException`: An invalid operation was blocked by Discord.

        ->example command pg!emsudo swap fields 123456789123456789 6 9
        -----
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

        try:
            await self.invoke_msg.delete()
            await self.response_msg.delete()
        except discord.NotFound:
            pass

    @add_group("emsudo", "clone", "fields")
    async def cmd_emsudo_clone_fields(
        self,
        msg: discord.Message,
        *indices: Union[range, int],
        multi_indices: bool = False,
        clone_to: Optional[int] = None,
    ):
        """
        ->type More emsudo commands
        ->signature pg!emsudo clone fields <message> <*indices> [multi_indices=False] [clone_to=]
        ->description Clone multiple embed fields through the bot
        ->extended description
        Clone embed fields at the given indices of the embed of a message using the specified arguments.

        __Args__:
            `message: (Message)`
            > A discord message whose embed
            > should be modified.

            `*indices: (int|range)`
            > The indices of the embed fields that should be cloned.
            > Can either be a sequence of `int`egers or
            > `range(start, stop[, step])` objects matching those
            > found in Python.

            `multi_indices: (bool) = False`
            > Whether indices are allowed to be specified
            > twice in the `*indices` argument. If set to `False`,
            > all duplicate indices will be ignored.

            `clone_to: (int)=`
            > The index that all embed field clones should be inserted at.
            > If excluded, all embed field clones will be inserted at
            > the index where they were cloned from.

        __Raises__:
            > `BotException`: One or more given arguments are invalid.
            > `HTTPException`: An invalid operation was blocked by Discord.

        ->example command
        pg!emsudo clone fields 987654321987654321 range(4, 10, 2) clone_to=1
        pg!emsudo clone fields 987654321987654321 3 6 9 12 clone_to=8
        pg!emsudo clone fields 123456674923481222/987654321987654321 range(6)
        -----
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

        field_indices = field_indices if multi_indices else list(set(field_indices))
        try:
            await embed_utils.clone_fields(
                msg, msg_embed, field_indices, insertion_index=clone_to
            )
        except IndexError:
            raise BotException("Invalid field index/indices!", "")

        try:
            await self.invoke_msg.delete()
            await self.response_msg.delete()
        except discord.NotFound:
            pass

    @add_group("emsudo", "remove", "fields")
    async def cmd_emsudo_remove_fields(
        self,
        msg: discord.Message,
        *indices: Union[range, int],
        multi_indices: bool = False,
    ):
        """
        ->type More emsudo commands
        ->signature pg!emsudo remove fields <message> <*indices> [multi_indices=False]
        ->description Remove an embed field through the bot
        ->extended description
        Remove embed fields at the given indices of the embed of a message using the given arguments.

        __Args__:
            `message: (Message)`
            > A discord message whose embed
            > should be modified.

            `*indices: (int|range)`
            > The indices of the embed fields that should be removed.
            > Can either be a sequence of `int`egers or
            > `range(start, stop[, step])` objects matching those
            > found in Python.

            `multi_indices: (bool) = False`
            > Whether indices are allowed to be specified
            > twice in the `*indices` argument. If set to `False`,
            > all duplicate indices will be ignored.

        __Raises__:
            > `BotException`: One or more given arguments are invalid.
            > `HTTPException`: An invalid operation was blocked by Discord.

        ->example command
        pg!emsudo remove fields 987654321987654321/123456789123456789 range(0, 10, 2)
        pg!emsudo remove fields 987654321987654321 5
        -----
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

        field_indices = field_indices if multi_indices else list(set(field_indices))
        try:
            await embed_utils.remove_fields(msg, msg_embed, field_indices)
        except IndexError:
            raise BotException("Invalid field index/indices!", "")

        try:
            await self.invoke_msg.delete()
            await self.response_msg.delete()
        except discord.NotFound:
            pass

    @add_group("emsudo", "remove", "fields", "all")
    async def cmd_emsudo_remove_fields_all(
        self,
        msg: discord.Message,
    ):
        """
        ->type More emsudo commands
        ->signature pg!emsudo remove fields all <message>
        ->description Remove all embed fields through the bot
        ->extended description
        Remove all embed fields of the embed of a message.

        __Args__:
            `message: (Message)`
            > A discord message whose embed fields
            > should be deleted.

        __Raises__:
            > `BotException`: One or more given arguments are invalid.
            > `HTTPException`: An invalid operation was blocked by Discord.
        -----
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

        try:
            await self.invoke_msg.delete()
            await self.response_msg.delete()
        except discord.NotFound:
            pass
