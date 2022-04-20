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
from discord.ext import commands
import snakecore

from pgbot import common
from pgbot.commands.base import (
    BaseCommandCog,
)
from pgbot.commands.utils.checks import admin_only_and_custom_parsing

from pgbot.commands.utils.converters import CodeBlock, String
from pgbot.exceptions import BotException


class EmsudoCommandCog(BaseCommandCog):
    """
    Base class to handle emsudo commands.
    """

    @commands.group(invoke_without_command=True)
    @admin_only_and_custom_parsing(inside_class=True, inject_message_reference=True)
    async def emsudo(
        self,
        ctx: commands.Context,
        *datas: Union[discord.Message, CodeBlock, String, bool],
        content: String = String(""),
        destination: Optional[Union[discord.TextChannel, discord.Thread]] = None,
    ):
        """
        ->type emsudo commands
        ->signature pg!emsudo <*datas> [content=""] [destination=]
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

            `content: (String) = ""`
            > The text content of each output message.

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

        response_message = common.recent_response_messages[ctx.message.id]

        content = content.string

        if destination is None:
            destination = ctx.channel

        if not snakecore.utils.have_permissions_in_channels(
            ctx.author, destination, "view_channel", "send_messages"
        ):
            raise BotException(
                "Not enough permissions",
                "You do not have enough permissions to run this command with the specified arguments.",
            )

        data_count = len(datas)
        output_embeds = []
        load_embed = snakecore.utils.embed_utils.create_embed(
            title="Your command is being processed:",
            color=common.DEFAULT_EMBED_COLOR,
            fields=[
                dict(name="\u2800", value="`...`", inline=False),
                dict(name="\u2800", value="`...`", inline=False),
            ],
        )

        for i, data in enumerate(datas):
            if data_count > 1 and not i % 3:
                snakecore.utils.embed_utils.edit_embed_field_from_dict(
                    load_embed,
                    0,
                    dict(
                        name="Processing Inputs",
                        value=f"`{i}/{data_count}` inputs processed\n"
                        f"{(i/data_count)*100:.01f}% | "
                        + snakecore.utils.progress_bar(i / data_count, divisions=30),
                    ),
                )
                await response_message.edit(embed=load_embed)

                await ctx.message.channel.trigger_typing()

            send_embed_args = dict(description=None)

            attachment_msg = None
            edit_description_only = False

            if data is False:
                attachment_msg = ctx.message

            elif isinstance(data, String):
                if not data.string:
                    attachment_msg = ctx.message
                else:
                    edit_description_only = True
                    send_embed_args.update(description=data.string)

            elif isinstance(data, discord.Message):
                if not snakecore.utils.have_permissions_in_channels(
                    ctx.author,
                    data.channel,
                    "view_channel",
                ):
                    raise BotException(
                        "Not enough permissions",
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
                    embed_dict = snakecore.utils.embed_utils.import_embed_data(
                        embed_data, input_format="JSON_STRING"
                    )
                else:
                    embed_dict = snakecore.utils.embed_utils.import_embed_data(
                        embed_data, input_format="STRING"
                    )

                output_embeds.append(
                    snakecore.utils.embed_utils.create_embed_from_dict(embed_dict)
                )

            elif not edit_description_only:
                if data.lang == "json":
                    try:
                        embed_dict = snakecore.utils.embed_utils.import_embed_data(
                            data.code, input_format="JSON_STRING"
                        )
                    except json.JSONDecodeError as j:
                        raise BotException(
                            f"Input {i}: Invalid JSON data",
                            f"```\n{j.args[0]}\n```",
                        )

                    output_embeds.append(
                        snakecore.utils.embed_utils.create_embed_from_dict(embed_dict)
                    )
                else:
                    try:
                        args = literal_eval(data.code)
                    except Exception as e:
                        raise BotException("Invalid arguments!", e.args[0])

                    if isinstance(args, dict):
                        output_embeds.append(
                            snakecore.utils.embed_utils.create_embed_from_dict(args)
                        )

                    elif isinstance(args, (list, tuple)):
                        try:
                            send_embed_args.update(
                                snakecore.utils.embed_utils.parse_condensed_embed_list(
                                    args
                                )
                            )
                        except ValueError as v:
                            raise BotException(
                                f"Condensed Embed Syntax Error at Input {i}:", v.args[0]
                            )
                        except TypeError as t:
                            raise BotException(
                                f"Input {i}:",
                                "Invalid arguments! The condensed embed syntax is:\n\n\\`\\`\\`py\n"
                                f"```py\n{snakecore.utils.embed_utils.CONDENSED_EMBED_DATA_LIST_SYNTAX}\n```\\`\\`\\`\n"
                                "The input Python `list` or `tuple` must contain at least 1 element.",
                            ) from t

                        output_embeds.append(
                            snakecore.utils.embed_utils.create_embed(**send_embed_args)
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
                output_embeds.append(
                    snakecore.utils.embed_utils.create_embed(
                        description=send_embed_args["description"],
                        color=common.DEFAULT_EMBED_COLOR,
                    )
                )

            await asyncio.sleep(0)

        if not datas:
            data_count = 1
            attachment_msg = ctx.message
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
                embed_dict = snakecore.utils.embed_utils.import_embed_data(
                    embed_data, input_format="JSON_STRING"
                )
            else:
                embed_dict = snakecore.utils.embed_utils.import_embed_data(
                    embed_data, input_format="STRING"
                )

            output_embeds.append(
                snakecore.utils.embed_utils.create_embed_from_dict(embed_dict)
            )

        else:
            snakecore.utils.embed_utils.edit_embed_field_from_dict(
                load_embed,
                0,
                dict(
                    name="Processing Completed",
                    value=f"`{data_count}/{data_count}` inputs processed\n"
                    "100% | " + snakecore.utils.progress_bar(1.0, divisions=30),
                ),
            )

            await response_message.edit(embed=load_embed)

        output_embed_count = len(output_embeds)
        for j, embed in enumerate(output_embeds):
            if data_count > 2 and not j % 3:
                snakecore.utils.embed_utils.edit_embed_field_from_dict(
                    load_embed,
                    1,
                    dict(
                        name="Generating Embeds",
                        value=f"`{j}/{output_embed_count}` embeds generated\n"
                        f"{(j/output_embed_count)*100:.01f}% | "
                        + snakecore.utils.progress_bar(
                            j / output_embed_count, divisions=30
                        ),
                    ),
                )
                await response_message.edit(embed=load_embed)

            await destination.send(content=content, embed=embed)

        if data_count > 2:
            snakecore.utils.embed_utils.edit_embed_field_from_dict(
                load_embed,
                1,
                dict(
                    name="Generation Completed",
                    value=f"`{output_embed_count}/{output_embed_count}` embeds generated\n"
                    "100% | " + snakecore.utils.progress_bar(1.0, divisions=30),
                ),
            )

            await response_message.edit(embed=load_embed)
        try:
            await ctx.message.delete()
            await response_message.delete(delay=10.0 if data_count > 2 else 0)
        except discord.NotFound:
            pass

    @emsudo.group(name="add", invoke_without_command=True)
    @admin_only_and_custom_parsing(inside_class=True, inject_message_reference=True)
    async def emsudo_add(
        self,
        ctx: commands.Context,
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
            await self.emsudo_replace_func(ctx, msg, data, _add=True)
        else:
            raise BotException(
                "Cannot overwrite embed!",
                "The given message's embed cannot be overwritten when"
                " `overwrite=` is set to `False`",
            )

    @emsudo.group(name="remove", invoke_without_command=True)
    @admin_only_and_custom_parsing(inside_class=True, inject_message_reference=True)
    async def emsudo_remove(
        self,
        ctx: commands.Context,
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

        response_message = common.recent_response_messages[ctx.message.id]

        checked_channels = set()
        for i, msg in enumerate(msgs):
            if msg.channel not in checked_channels:
                if not snakecore.utils.have_permissions_in_channels(
                    ctx.author,
                    msg.channel,
                    "view_channel",
                    "send_messages",
                ):
                    raise BotException(
                        "Not enough permissions",
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
                "Invalid arguments!",
                "No messages given as input.",
            )

        load_embed = snakecore.utils.embed_utils.create_embed(
            title="Your command is being processed:",
            color=common.DEFAULT_EMBED_COLOR,
            fields=[dict(name="\u2800", value="`...`", inline=False)],
        )

        attribs = (
            a.string if a.string else attributes.string if attributes.string else ""
        )

        try:
            embed_mask_dict = snakecore.utils.embed_utils.create_embed_mask_dict(
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
                    snakecore.utils.embed_utils.edit_embed_field_from_dict(
                        load_embed,
                        0,
                        dict(
                            name="Processing Messages",
                            value=f"`{i}/{msg_count}` messages processed\n"
                            f"{(i/msg_count)*100:.01f}% | "
                            + snakecore.utils.progress_bar(i / msg_count, divisions=30),
                        ),
                    )

                    await response_message.edit(embed=load_embed)

                await ctx.channel.trigger_typing()
                msg_embed = msg.embeds[0]
                embed_dict = msg_embed.to_dict()

                if embed_mask_dict:
                    if "fields" in embed_dict and "fields" in embed_mask_dict:
                        field_list = embed_dict["fields"]
                        embed_dict["fields"] = {
                            str(i): field_list[i] for i in range(len(field_list))
                        }

                        snakecore.utils.recursive_dict_delete(
                            embed_dict, embed_mask_dict
                        )

                        if "fields" in embed_dict:
                            field_dict = embed_dict["fields"]
                            embed_dict["fields"] = [
                                field_dict[i] for i in sorted(field_dict.keys())
                            ]
                    else:
                        snakecore.utils.recursive_dict_delete(
                            embed_dict, embed_mask_dict
                        )
                else:
                    snakecore.utils.recursive_dict_delete(embed_dict, embed_mask_dict)

                if embed_dict:
                    snakecore.utils.embed_utils.filter_embed_dict(embed_dict)
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
                    snakecore.utils.embed_utils.edit_embed_field_from_dict(
                        load_embed,
                        0,
                        dict(
                            name="Processing Messages",
                            value=f"`{i}/{msg_count}` messages processed\n"
                            f"{(i/msg_count)*100:.01f}% | "
                            + snakecore.utils.progress_bar(i / msg_count, divisions=30),
                        ),
                    )

                    await response_message.edit(embed=load_embed)

                    await ctx.channel.trigger_typing()
                if not msg.embeds:
                    raise BotException(
                        f"Input {i}: Cannot execute command:",
                        "No embed data found in message.",
                    )
                await msg.edit(embed=None)
                await asyncio.sleep(0)

        if msg_count > 2:
            snakecore.utils.embed_utils.edit_embed_field_from_dict(
                load_embed,
                0,
                dict(
                    name="Processing Completed",
                    value=f"`{msg_count}/{msg_count}` messages processed\n"
                    "100% | " + snakecore.utils.progress_bar(1.0, divisions=30),
                ),
            )

            await response_message.edit(embed=load_embed)

        try:
            await ctx.message.delete()
            await response_message.delete(delay=10.0 if msg_count > 2 else 0.0)
        except discord.NotFound:
            pass

    async def emsudo_replace_func(
        self,
        ctx: commands.Context,
        msg: discord.Message,
        data: Optional[Union[discord.Message, CodeBlock, String, bool]] = None,
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

        response_message = common.recent_response_messages[ctx.message.id]

        if not snakecore.utils.have_permissions_in_channels(
            ctx.author,
            msg.channel,
            "view_channel",
            "send_messages",
        ):
            raise BotException(
                "Not enough permissions",
                "You do not have enough permissions to run this command on the specified channel.",
            )

        replace_embed_args = dict(
            description=None,
        )

        if not msg.embeds and not _add:
            raise BotException(
                "No embed data found", "No embed data to be replaced was found"
            )

        attachment_msg = None
        edit_description_only = False

        if data is None or data is False:
            attachment_msg = ctx.message

        elif isinstance(data, String):
            if not data.string:
                attachment_msg = ctx.message
            else:
                edit_description_only = True
                replace_embed_args.update(description=data.string)

        elif isinstance(data, discord.Message):
            if not snakecore.utils.have_permissions_in_channels(
                ctx.author,
                data.channel,
                "view_channel",
            ):
                raise BotException(
                    "Not enough permissions",
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
                embed_dict = snakecore.utils.embed_utils.import_embed_data(
                    embed_data, input_format="JSON_STRING"
                )
            else:
                embed_dict = snakecore.utils.embed_utils.import_embed_data(
                    embed_data, input_format="STRING"
                )

            await snakecore.utils.embed_utils.replace_embed_from_dict_at(
                msg, embed_dict
            )

        elif not edit_description_only:
            if data.lang == "json":
                try:
                    embed_dict = snakecore.utils.embed_utils.import_embed_data(
                        data.code, input_format="JSON_STRING"
                    )
                except json.JSONDecodeError as j:
                    raise BotException(
                        "Invalid JSON data",
                        f"```\n{j.args[0]}\n```",
                    )
                await snakecore.utils.embed_utils.replace_embed_from_dict_at(
                    msg, embed_dict
                )
            else:
                try:
                    args = literal_eval(data.code)
                except Exception as e:
                    raise BotException("Invalid arguments!", e.args[0])

                if isinstance(args, dict):
                    await snakecore.utils.embed_utils.replace_embed_from_dict_at(
                        msg, args
                    )

                elif isinstance(args, (list, tuple)):
                    try:
                        replace_embed_args.update(
                            snakecore.utils.embed_utils.parse_condensed_embed_list(args)
                        )
                    except ValueError as v:
                        raise BotException("Condensed Embed Syntax Error:", v.args[0])
                    except TypeError:
                        raise BotException(
                            "Invalid arguments!",
                            "The condensed embed syntax is:\n\n\\`\\`\\`py\n"
                            f"```py\n{snakecore.utils.embed_utils.CONDENSED_EMBED_DATA_LIST_SYNTAX}\n```\\`\\`\\`\n"
                            "The input Python `list` or `tuple` must contain at least 1 element.",
                        )

                    await snakecore.utils.embed_utils.replace_embed_at(
                        msg, **replace_embed_args
                    )
                else:
                    raise BotException(
                        "Invalid arguments!",
                        "A code block given as input must"
                        " contain either a Python `tuple`/`list` of embed data, or a"
                        " Python `dict` of embed data matching the JSON structure of"
                        " a Discord embed object, or JSON embed data (\n\\`\\`\\`json\n"
                        "data\n\\`\\`\\`\n)",
                    )

        try:
            await ctx.message.delete()
            await response_message.delete()
        except discord.NotFound:
            pass

    @emsudo.group(name="replace", invoke_without_command=True)
    @admin_only_and_custom_parsing(inside_class=True, inject_message_reference=True)
    async def emsudo_replace(
        self,
        ctx: commands.Context,
        msg: discord.Message,
        data: Optional[Union[discord.Message, CodeBlock, String, bool]] = None,
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

        return await self.emsudo_replace_func(ctx, msg, data)

    @emsudo.group(name="edit", invoke_without_command=True)
    @admin_only_and_custom_parsing(inside_class=True, inject_message_reference=True)
    async def emsudo_edit(
        self,
        ctx: commands.Context,
        msg: tuple[discord.Message, ...],
        *datas: Union[discord.Message, CodeBlock, String, bool],
        add_attributes: bool = True,
        edit_inner_fields: bool = False,
    ):
        """
        ->type emsudo commands
        ->signature pg!emsudo edit <message|messages> <*datas> [add_atributes=True] [edit_inner_fields=False]
        ->description Edit embeds through the bot
        ->extended description
        Edit the embeds of the given messages using the given inputs.

        __Args__:
            `msg: (Message|(Message, Message, ...))`
            > A single message or a tuple of messages whose first embeds
            > should be modified.

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

            `edit_inner_fields: (bool) = False`
            > If set to `True`, the embed fields of the target
            > embed (if present) will be able to be
            > individually modified by the given input
            > embed data. If `False`, all embed fields will
            > be modified as a single embed attribute.

        +===+

        __Raises__:
            > `BotException`: One or more given arguments are invalid.
            > `HTTPException`: An invalid operation was blocked by Discord.

        ->example command
        pg!emsudo edit 987654321987654321 "Lol only the embed description changed"
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

        response_message = common.recent_response_messages[ctx.message.id]

        target_msgs = msg

        if not isinstance(msg, tuple):
            target_msgs = (msg,)

        for i, msg in enumerate(target_msgs):
            if not snakecore.utils.have_permissions_in_channels(
                ctx.author,
                msg.channel,
                "view_channel",
                "send_messages",
            ):
                raise BotException(
                    "Not enough permissions",
                    "You do not have enough permissions to run this command with the specified arguments.",
                )

            if not msg.embeds:
                raise BotException(
                    f"Input Target Message {i}: Cannot execute command:",
                    "No embed data found in message.",
                )

            if not i % 50:
                await asyncio.sleep(0)

        for i, data in enumerate(datas):
            if isinstance(data, discord.Message):
                if not snakecore.utils.have_permissions_in_channels(
                    ctx.author,
                    data.channel,
                    "view_channel",
                ):
                    raise BotException(
                        "Not enough permissions",
                        "You do not have enough permissions to run this command with the specified arguments.",
                    )

            if not i % 50:
                await asyncio.sleep(0)

        target_embed_dicts = tuple(msg.embeds[0].to_dict() for msg in target_msgs)
        data_count = len(datas)

        load_embed = snakecore.utils.embed_utils.create_embed(
            title="Your command is being processed:",
            color=common.DEFAULT_EMBED_COLOR,
            fields=[dict(name="\u2800", value="`...`", inline=False)],
        )

        for i, data in enumerate(datas):
            if data_count > 2 and not i % 3:
                snakecore.utils.embed_utils.edit_embed_field_from_dict(
                    load_embed,
                    0,
                    dict(
                        name="Processing Inputs",
                        value=f"`{i}/{data_count}` inputs processed\n"
                        f"{(i/data_count)*100:.01f}% | "
                        + snakecore.utils.progress_bar(i / data_count, divisions=30),
                    ),
                    0,
                )

                await response_message.edit(embed=load_embed)

            await ctx.message.channel.trigger_typing()

            edit_embed_args = dict(
                description=None,
            )

            attachment_msg: Optional[discord.Message] = None
            edit_description_only = False

            if not data:
                attachment_msg = ctx.message

            elif isinstance(data, String):
                if not data.string:
                    attachment_msg = ctx.message
                else:
                    edit_description_only = True
                    edit_embed_args.update(description=data.string)

            elif isinstance(data, discord.Message):
                if not snakecore.utils.have_permissions_in_channels(
                    ctx.author,
                    data.channel,
                    "view_channel",
                ):
                    raise BotException(
                        "Not enough permissions",
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
                    embed_dict = snakecore.utils.embed_utils.import_embed_data(
                        embed_data, input_format="JSON_STRING"
                    )
                else:
                    embed_dict = snakecore.utils.embed_utils.import_embed_data(
                        embed_data, input_format="STRING"
                    )

                for target_embed_dict in target_embed_dicts:
                    snakecore.utils.embed_utils.edit_embed_dict_from_dict(
                        target_embed_dict,
                        embed_dict,
                        add_attributes=add_attributes,
                        edit_inner_fields=edit_inner_fields,
                    )

            elif not edit_description_only:
                if data.lang == "json":
                    try:
                        embed_dict = snakecore.utils.embed_utils.import_embed_data(
                            data.code, input_format="JSON_STRING"
                        )
                    except json.JSONDecodeError as j:
                        raise BotException(
                            f"Input {i}: Invalid JSON data",
                            f"```\n{j.args[0]}\n```",
                        )

                    for target_embed_dict in target_embed_dicts:
                        snakecore.utils.embed_utils.edit_embed_dict_from_dict(
                            target_embed_dict,
                            embed_dict,
                            add_attributes=add_attributes,
                            edit_inner_fields=edit_inner_fields,
                        )
                else:
                    try:
                        args = literal_eval(data.code)
                    except Exception as e:
                        raise BotException(f"Input {i}: Invalid arguments!", e.args[0])

                    if isinstance(args, dict):
                        for target_embed_dict in target_embed_dicts:
                            snakecore.utils.embed_utils.edit_embed_dict_from_dict(
                                target_embed_dict,
                                args,
                                add_attributes=add_attributes,
                                edit_inner_fields=edit_inner_fields,
                            )

                    elif isinstance(args, (list, tuple)):
                        try:
                            edit_embed_args.update(
                                snakecore.utils.embed_utils.parse_condensed_embed_list(
                                    args
                                )
                            )
                        except ValueError as v:
                            raise BotException(f"Input {i}:", v.args[0])
                        except TypeError:
                            raise BotException(
                                f"Input {i}:",
                                "Invalid arguments! The condensed embed syntax is:\n\n\\`\\`\\`py\n"
                                f"```py\n{snakecore.utils.embed_utils.CONDENSED_EMBED_DATA_LIST_SYNTAX}\n```\\`\\`\\`\n"
                                "The input Python `list` or `tuple` must contain at least 1 element.",
                            )

                        embed_dict = snakecore.utils.embed_utils.create_embed_as_dict(
                            **edit_embed_args,
                        )
                        for target_embed_dict in target_embed_dicts:
                            snakecore.utils.embed_utils.edit_embed_dict_from_dict(
                                target_embed_dict,
                                embed_dict,
                                add_attributes=add_attributes,
                                edit_inner_fields=edit_inner_fields,
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
                embed_dict = snakecore.utils.embed_utils.create_embed_as_dict(
                    description=edit_embed_args["description"],
                    color=-1,
                )
                for target_embed_dict in target_embed_dicts:
                    snakecore.utils.embed_utils.edit_embed_dict_from_dict(
                        target_embed_dict,
                        embed_dict,
                        add_attributes=add_attributes,
                        edit_inner_fields=edit_inner_fields,
                    )

            await asyncio.sleep(0)

        if not datas:
            data_count = 1
            attachment_msg = ctx.message
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
                embed_dict = snakecore.utils.embed_utils.import_embed_data(
                    embed_data, input_format="JSON_STRING"
                )
            else:
                embed_dict = snakecore.utils.embed_utils.import_embed_data(
                    embed_data, input_format="STRING"
                )

            for target_embed_dict in target_embed_dicts:
                snakecore.utils.embed_utils.edit_embed_dict_from_dict(
                    target_embed_dict,
                    embed_dict,
                    add_attributes=add_attributes,
                    edit_inner_fields=edit_inner_fields,
                )

            for i, msg in enumerate(target_msgs):
                await msg.edit(
                    embed=discord.Embed.from_dict(
                        snakecore.utils.embed_utils.filter_embed_dict(
                            target_embed_dicts[i], in_place=False
                        )
                    )
                )

        else:
            for i, msg in enumerate(target_msgs):
                await msg.edit(
                    embed=discord.Embed.from_dict(
                        snakecore.utils.embed_utils.filter_embed_dict(
                            target_embed_dicts[i], in_place=False
                        )
                    )
                )

        if data_count > 2:
            snakecore.utils.embed_utils.edit_embed_field_from_dict(
                load_embed,
                0,
                dict(
                    name="Processing Complete",
                    value=f"`{data_count}/{data_count}` inputs processed\n"
                    "100% | " + snakecore.utils.progress_bar(1.0, divisions=30),
                ),
            )

            await response_message.edit(embed=load_embed)

        try:
            await ctx.message.delete()
            await response_message.delete(delay=10.0 if data_count > 2 else 0.0)
        except discord.NotFound:
            pass

    @emsudo.command(name="sum")
    @admin_only_and_custom_parsing(inside_class=True, inject_message_reference=True)
    async def emsudo_sum(
        self,
        ctx: commands.Context,
        *msgs: discord.Message,
        destination: Optional[Union[discord.TextChannel, discord.Thread]] = None,
        edit_inner_fields: bool = False,
        in_place: bool = False,
        remove_inputs: bool = False,
    ):
        """
        ->type emsudo commands
        ->signature pg!emsudo sum <*messages> [destination=] [edit_inner_fields=False] [in_place=False] [remove_inputs=False]
        ->description Combine several embeds into one
        ->extended description
        Create a new embed representing the sum of all embed messages
        given as input.

        __Args__:
            `*messages: (Messages)`
            > A sequence of messages whose first embeds should
            > be merged to create a new embed

            `destination: (Channel) =`
            > A destination channel to send the generated outputs to.
            > If omitted, the destination will be the channel where
            > this command was invoked.

            `edit_inner_fields: (bool) = False`
            > If set to `True`, the individual embed fields
            > of the embeds given as input will be considered
            > in the joining process, otherwise they will all
            > be treated as one entity.

            `add_attributes: (bool) = True`
            > Whether the input embeds should add new
            > attributes to the the data of the first embed
            > given as input. If set to `False`, only the
            > attributes present in the first embed will be changed.

            `in_place: (bool) = True`
            > If set to `True`, the first message's embed
            > given as input will be replaced with the generated
            > output embed.

        +===+
            `remove_inputs: (bool) = False`
            > If set to `True`, all embeds
            > given as input (excluding
            > the first one if `in_place=` is `True`)
            > will be deleted. This can be
            > used to emulate the behavior of
            > 'pushing' one or more embeds into another.

        __Raises__:
            > `BotException`: One or more given arguments are invalid.
            > `HTTPException`: An invalid operation was blocked by Discord.

        ->example command
        pg!emsudo sum 987654321987654321 123456789012345678 251613726327333621
        -----
        """

        response_message = common.recent_response_messages[ctx.message.id]

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
                "You do not have enough permissions to run this command with the specified arguments.",
            )

        if not msgs:
            raise BotException(
                "Invalid arguments!",
                "No messages given as input.",
            )

        msgs_perms = ("view_channel",) + (("send_messages",) if remove_inputs else ())
        checked_channels = set()
        for i, msg in enumerate(msgs):
            if msg.channel not in checked_channels:
                if not snakecore.utils.have_permissions_in_channels(
                    ctx.author,
                    msg.channel,
                    *msgs_perms,
                ):
                    raise BotException(
                        "Not enough permissions",
                        "You do not have enough permissions to run this command with the specified arguments.",
                    )
                elif not msg.embeds:
                    raise BotException(
                        f"Input {i}: Cannot execute command:",
                        "No embed found in message.",
                    )
                else:
                    checked_channels.add(msg.channel)

            if not i % 50:
                await asyncio.sleep(0)

        load_embed = snakecore.utils.embed_utils.create_embed(
            title="Your command is being processed:",
            color=common.DEFAULT_EMBED_COLOR,
            fields=[dict(name="\u2800", value="`...`", inline=False)],
        )

        output_embed_dict = {}
        msg_count = len(msgs)
        for i, msg in enumerate(msgs):
            if msg_count > 2 and not i % 3:
                snakecore.utils.embed_utils.edit_embed_field_from_dict(
                    load_embed,
                    0,
                    dict(
                        name="Processing Messages",
                        value=f"`{i}/{msg_count}` messages processed\n"
                        f"{(i/msg_count)*100:.01f}% | "
                        + snakecore.utils.progress_bar(i / msg_count, divisions=30),
                    ),
                )

                await response_message.edit(embed=load_embed)

            await destination.trigger_typing()

            embed = msg.embeds[0]
            embed_dict = embed.to_dict()

            if output_embed_dict:
                if edit_inner_fields and "fields" in output_embed_dict:
                    output_embed_dict["fields"].extend(embed_dict["fields"])
                    del embed_dict["fields"]

                output_embed_dict = (
                    snakecore.utils.embed_utils.edit_embed_dict_from_dict(
                        output_embed_dict,
                        embed_dict,
                        add_attributes=True,
                        in_place=False,
                    )
                )
            else:
                output_embed_dict = embed_dict

            await asyncio.sleep(0)

        if snakecore.utils.embed_utils.validate_embed_dict(output_embed_dict):
            if in_place:
                await msgs[0].edit(embed=discord.Embed.from_dict(output_embed_dict))
            else:
                await destination.send(embed=discord.Embed.from_dict(output_embed_dict))
        else:
            raise BotException(
                "Ivalid embed sum operation",
                "Could not successfully generate"
                " an embed from the data of those"
                " given as input.",
            )

        if remove_inputs:
            for j, msg in enumerate(msgs[1:] if in_place else msgs):
                if msg.author.id == ctx.author.id:
                    if msg.content:
                        await msg.edit(embed=None)
                    else:
                        await msg.delete()

                    if not j % 5:
                        await asyncio.sleep(0)

        if msg_count > 2:
            snakecore.utils.embed_utils.edit_embed_field_from_dict(
                load_embed,
                0,
                dict(
                    name="Processing Completed",
                    value=f"`{msg_count}/{msg_count}` messages processed\n"
                    "100% | " + snakecore.utils.progress_bar(1.0, divisions=30),
                ),
            )

            await response_message.edit(embed=load_embed)

        try:
            await ctx.message.delete()
            await response_message.delete(delay=10.0 if msg_count > 2 else 0.0)
        except discord.NotFound:
            pass

    @emsudo.group(name="swap", invoke_without_command=True)
    @admin_only_and_custom_parsing(inside_class=True, inject_message_reference=True)
    async def emsudo_swap(
        self,
        ctx: commands.Context,
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

        response_message = common.recent_response_messages[ctx.message.id]

        if not snakecore.utils.have_permissions_in_channels(
            ctx.author,
            msg_a.channel,
            "view_channel",
            "send_messages",
        ) or not snakecore.utils.have_permissions_in_channels(
            ctx.author,
            msg_b.channel,
            "view_channel",
            "send_messages",
        ):
            raise BotException(
                "Not enough permissions",
                "You do not have enough permissions to run this command with the specified arguments.",
            )

        bot_id = self.bot.user.id

        if not msg_a.embeds or not msg_b.embeds:
            raise BotException(
                "Cannot execute command:",
                "No embed data found in on of the given messages.",
            )

        elif bot_id not in (msg_a.author.id, msg_b.author.id):
            raise BotException(
                "Cannot execute command:",
                f"Both messages must have been authored by me, {self.bot.user.mention}.",
            )

        msg_embed_a = msg_a.embeds[0]
        msg_embed_b = msg_b.embeds[0]

        await msg_a.edit(embed=msg_embed_b)
        await msg_b.edit(embed=msg_embed_a)

        try:
            await ctx.message.delete()
            await response_message.delete()
        except discord.NotFound:
            pass

    @emsudo.group(name="clone", invoke_without_command=True)
    @admin_only_and_custom_parsing(inside_class=True, inject_message_reference=True)
    async def emsudo_clone(
        self,
        ctx: commands.Context,
        *msgs: discord.Message,
        destination: Optional[Union[discord.TextChannel, discord.Thread]] = None,
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

            `edit_inner_fields: (bool) = False`
            > If set to `True`, the embed fields of the target
            > embed (if present) will be able to be
            > individually modified by the given input
            > embed data. If `False`, all embed fields will
            > be modified as a single embed attribute.

        __Returns__:
            > One or more clones of embeds in messages based on the given input.

        __Raises__:
            > `BotException`: One or more given arguments are invalid.
            > `HTTPException`: An invalid operation was blocked by Discord.

        ->example command
        pg!emsudo clone 987654321987654321 123456789123456789
        https://discord.com/channels/772505616680878080/841726972841558056/846870368672546837
        -----
        """

        response_message = common.recent_response_messages[ctx.message.id]

        if destination is None:
            destination = ctx.channel

        if not snakecore.utils.have_permissions_in_channels(
            ctx.author,
            destination,
            "view_channel",
            "send_messages",
        ):
            raise BotException(
                "Not enough permissions",
                "You do not have enough permissions to run this command with the specified arguments.",
            )

        checked_channels = set()
        for i, msg in enumerate(msgs):
            if msg.channel not in checked_channels:
                if not snakecore.utils.have_permissions_in_channels(
                    ctx.author,
                    msg.channel,
                    "view_channel",
                ):
                    raise BotException(
                        "Not enough permissions",
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
                "Invalid arguments!",
                "No messages given as input.",
            )

        load_embed = snakecore.utils.embed_utils.create_embed(
            title="Your command is being processed:",
            color=common.DEFAULT_EMBED_COLOR,
            fields=[
                dict(name="\u2800", value="`...`", inline=False),
                dict(name="\u2800", value="`...`", inline=False),
            ],
        )

        msg_count = len(msgs)
        for i, msg in enumerate(msgs):
            if msg_count > 2 and not i % 3:
                snakecore.utils.embed_utils.edit_embed_field_from_dict(
                    load_embed,
                    0,
                    dict(
                        name="Processing Messages",
                        value=f"`{i}/{msg_count}` messages processed\n"
                        f"{(i/msg_count)*100:.01f}% | "
                        + snakecore.utils.progress_bar(i / msg_count, divisions=30),
                    ),
                )

                await response_message.edit(embed=load_embed)

            await destination.trigger_typing()
            embed_count = len(msg.embeds)
            for j, embed in enumerate(msg.embeds):
                if msg_count > 2 and not j % 3:
                    snakecore.utils.embed_utils.edit_embed_field_from_dict(
                        load_embed,
                        1,
                        dict(
                            name="Cloning Embeds",
                            value=f"`{j}/{embed_count}` embeds cloned\n"
                            f"{(i/embed_count)*100:.01f}% | "
                            + snakecore.utils.progress_bar(
                                j / embed_count, divisions=30
                            ),
                        ),
                    )

                    await response_message.edit(embed=load_embed)

                    await destination.trigger_typing()

                await destination.send(embed=embed)

            snakecore.utils.embed_utils.edit_embed_field_from_dict(
                load_embed,
                1,
                dict(
                    name="Cloning Completed",
                    value=f"`{embed_count}/{embed_count}` embeds cloned\n"
                    "100% | " + snakecore.utils.progress_bar(1.0, divisions=30),
                ),
            )

            await response_message.edit(embed=load_embed)

            await asyncio.sleep(0)

        if msg_count > 2:
            snakecore.utils.embed_utils.edit_embed_field_from_dict(
                load_embed,
                1,
                dict(
                    name="Processing Completed",
                    value=f"`{msg_count}/{msg_count}` messages processed\n"
                    "100% | " + snakecore.utils.progress_bar(1.0, divisions=30),
                ),
            )

            await response_message.edit(embed=load_embed)

        try:
            await response_message.delete(delay=10.0 if msg_count > 2 else 0.0)
        except discord.NotFound:
            pass

    async def emsudo_get_func(
        self,
        ctx: commands.Context,
        *msgs: discord.Message,
        a: String = String(""),
        attributes: String = String(""),
        mode: int = 0,
        destination: Optional[Union[discord.TextChannel, discord.Thread]] = None,
        output_name: String = String("(add a title by editing this embed)"),
        pop: bool = False,
        copy_color_with_pop: bool = False,
        system_attributes: bool = False,
        as_json: bool = True,
        as_python: bool = False,
    ):
        """
        ->type emsudo commands
        ->signature pg!emsudo get <*messages> [a|attributes=""] [mode=0] [destination=]
        [output_name=""] [system_attributes=False] [as_json=True] [as_python=False]

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

            `as_python (bool) = False`
            `as_json (bool) = True`
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

        response_message = common.recent_response_messages[ctx.message.id]

        if destination is None:
            destination = ctx.channel

        if not snakecore.utils.have_permissions_in_channels(
            ctx.author,
            destination,
            "view_channel",
            "send_messages",
        ):
            raise BotException(
                "Not enough permissions",
                "You do not have enough permissions to run this command with the specified arguments.",
            )

        checked_channels = set()
        msgs_perms = ("view_channel",) + (("send_messages",) if pop else ())
        for i, msg in enumerate(msgs):
            if msg.channel not in checked_channels:
                if not snakecore.utils.have_permissions_in_channels(
                    ctx.author,
                    msg.channel,
                    *msgs_perms,
                ):
                    raise BotException(
                        "Not enough permissions",
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
                "Invalid arguments!",
                "No messages given as input.",
            )

        if mode < 0 or mode > 2:
            raise BotException(
                "Invalid arguments!",
                "`mode=` must be either `0` or `1`",
            )

        attribs = (
            a.string if a.string else attributes.string if attributes.string else ""
        )

        try:
            embed_mask_dict = snakecore.utils.embed_utils.create_embed_mask_dict(
                attributes=attribs,
                allow_system_attributes=system_attributes,
                fields_as_field_dict=True,
            )
        except ValueError as v:
            raise BotException("An attribute string parsing error occured:", v.args[0])

        load_embed = snakecore.utils.embed_utils.create_embed(
            title="Your command is being processed:",
            color=common.DEFAULT_EMBED_COLOR,
            fields=[
                dict(name="\u2800", value="`...`", inline=False),
                dict(name="\u2800", value="`...`", inline=False),
            ],
        )

        msg_count = len(msgs)
        for i, msg in enumerate(msgs):
            if msg_count > 2 and not i % 3:
                snakecore.utils.embed_utils.edit_embed_field_from_dict(
                    load_embed,
                    0,
                    dict(
                        name="Processing Messages",
                        value=f"`{i}/{msg_count}` messages processed\n"
                        f"{(i/msg_count)*100:.01f}% | "
                        + snakecore.utils.progress_bar(i / msg_count, divisions=30),
                    ),
                )

                await response_message.edit(embed=load_embed)

            await destination.trigger_typing()
            embed_count = len(msg.embeds)
            for j, embed in enumerate(msg.embeds):
                if msg_count > 2 and embed_count > 2 and not j % 3:
                    snakecore.utils.embed_utils.edit_embed_field_from_dict(
                        load_embed,
                        1,
                        dict(
                            name="Serializing Embeds",
                            value=f"`{j}/{embed_count}` embeds serialized\n"
                            f"{(j/embed_count)*100:.01f}% | "
                            + snakecore.utils.progress_bar(
                                j / embed_count, divisions=30
                            ),
                        ),
                    )

                    await response_message.edit(embed=load_embed)

                embed_dict = embed.to_dict()
                pop_target_embed_dict = snakecore.utils.embed_utils.copy_embed_dict(
                    embed_dict
                )  # circumvents discord.py bug
                corrected_embed_dict = None
                corrected_pop_target_embed_dict = None
                if embed_mask_dict:
                    if "fields" in embed_dict and "fields" in embed_mask_dict:
                        field_list = embed_dict["fields"]
                        embed_dict["fields"] = {
                            str(i): field_list[i] for i in range(len(field_list))
                        }
                        field_list = pop_target_embed_dict["fields"]
                        pop_target_embed_dict["fields"] = {
                            str(i): field_list[i] for i in range(len(field_list))
                        }

                        if not system_attributes:
                            snakecore.utils.recursive_dict_delete(
                                embed_dict,
                                snakecore.utils.embed_utils.EMBED_SYSTEM_ATTRIBUTES_MASK_DICT,
                            )

                        snakecore.utils.recursive_dict_delete(
                            embed_dict, embed_mask_dict, inverse=True
                        )
                        if "fields" in embed_dict:
                            field_dict = embed_dict["fields"]
                            embed_dict["fields"] = [
                                field_dict[i] for i in sorted(field_dict.keys())
                            ]

                        snakecore.utils.recursive_dict_delete(
                            pop_target_embed_dict, embed_mask_dict
                        )

                        if "fields" in pop_target_embed_dict:
                            field_dict = pop_target_embed_dict["fields"]
                            pop_target_embed_dict["fields"] = [
                                field_dict[i] for i in sorted(field_dict.keys())
                            ]
                    else:
                        if not system_attributes:
                            snakecore.utils.recursive_dict_delete(
                                embed_dict,
                                snakecore.utils.embed_utils.EMBED_SYSTEM_ATTRIBUTES_MASK_DICT,
                            )
                        snakecore.utils.recursive_dict_delete(
                            embed_dict, embed_mask_dict, inverse=True
                        )
                        snakecore.utils.recursive_dict_delete(
                            pop_target_embed_dict, embed_mask_dict
                        )
                else:
                    if not system_attributes:
                        snakecore.utils.recursive_dict_delete(
                            embed_dict,
                            snakecore.utils.embed_utils.EMBED_SYSTEM_ATTRIBUTES_MASK_DICT,
                        )

                if embed_dict:
                    if mode == 1 or mode == 2:
                        corrected_embed_dict = (
                            snakecore.utils.embed_utils.filter_embed_dict(
                                embed_dict, in_place=False
                            )
                        )
                else:
                    raise BotException(
                        "Cannot execute command:",
                        "Could not find data that matches"
                        " the pattern of the given embed attribute filter string.",
                    )

                if pop and pop_target_embed_dict and embed_mask_dict:
                    corrected_pop_target_embed_dict = (
                        snakecore.utils.embed_utils.filter_embed_dict(
                            pop_target_embed_dict, in_place=False
                        )
                    )

                if mode == 0 or mode == 2:
                    if (
                        mode == 2
                        and corrected_embed_dict
                        and snakecore.utils.embed_utils.validate_embed_dict(
                            corrected_embed_dict
                        )
                    ):
                        if pop and copy_color_with_pop and embed.color:
                            corrected_embed_dict["color"] = embed.color.value
                        await destination.send(
                            embed=discord.Embed.from_dict(corrected_embed_dict)
                        )
                    with io.StringIO() as fobj:
                        snakecore.utils.embed_utils.export_embed_data(
                            {
                                k: embed_dict[k]
                                for k in snakecore.utils.embed_utils.EMBED_TOP_LEVEL_ATTRIBUTES_MASK_DICT
                                if k in embed_dict
                            },
                            fp=fobj,
                            indent=4,
                            as_json=True if as_json and not as_python else False,
                        )
                        fobj.seek(0)
                        await destination.send(
                            embed=snakecore.utils.embed_utils.create_embed(
                                author_name="Embed Data",
                                title=output_name.string
                                if len(msgs) < 2
                                else "(add a title by editing this embed)",
                                color=common.DEFAULT_EMBED_COLOR,
                                fields=[
                                    dict(
                                        name="\u2800",
                                        value=f"**[View Original Message]({msg.jump_url})**",
                                        inline=True,
                                    ),
                                ],
                                footer_text="Structural validity: "
                                + (
                                    "Valid."
                                    if snakecore.utils.embed_utils.validate_embed_dict(
                                        embed_dict
                                    )
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
                    if (
                        corrected_embed_dict
                        and snakecore.utils.embed_utils.validate_embed_dict(
                            corrected_embed_dict
                        )
                    ):
                        if pop and copy_color_with_pop and embed.color:
                            corrected_embed_dict["color"] = embed.color.value
                        await destination.send(
                            embed=discord.Embed.from_dict(corrected_embed_dict)
                        )
                    else:
                        raise BotException(
                            "Invalid embed creation data",
                            "Could not generate a valid embed from the extracted embed attributes.",
                        )

                if pop and corrected_pop_target_embed_dict:
                    await msg.edit(
                        embed=discord.Embed.from_dict(corrected_pop_target_embed_dict)
                    )

            if embed_count > 2:
                await snakecore.utils.embed_utils.edit_embed_field_from_dict(
                    load_embed,
                    1,
                    dict(
                        name="Serialization Completed",
                        value=f"`{embed_count}/{embed_count}` embeds serialized\n"
                        "100% | " + snakecore.utils.progress_bar(1.0, divisions=30),
                    ),
                )

                await response_message.edit(embed=load_embed)

            await asyncio.sleep(0)

        if msg_count > 2:
            await snakecore.utils.embed_utils.edit_embed_field_from_dict(
                load_embed,
                0,
                dict(
                    name="Processing Completed",
                    value=f"`{msg_count}/{msg_count}` inputs processed\n"
                    "100% | " + snakecore.utils.progress_bar(1.0, divisions=30),
                ),
            )

            await response_message.edit(embed=load_embed)

        try:
            await response_message.delete(delay=10.0 if msg_count > 2 else 0.0)
        except discord.NotFound:
            pass

    @emsudo.command(name="get")
    @admin_only_and_custom_parsing(inside_class=True, inject_message_reference=True)
    async def emsudo_get(
        self,
        ctx: commands.Context,
        *msgs: discord.Message,
        a: String = String(""),
        attributes: String = String(""),
        mode: int = 0,
        destination: Optional[Union[discord.TextChannel, discord.Thread]] = None,
        output_name: String = String("(add a title by editing this embed)"),
        system_attributes: bool = False,
        as_json: bool = True,
        as_python: bool = False,
    ):
        """
        ->type emsudo commands
        ->signature pg!emsudo get <*messages> [a|attributes=""] [mode=0] [destination=]
        [output_name=""] [system_attributes=False] [as_json=True] [as_python=False]

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

            `as_python (bool) = False`
            `as_json (bool) = True`
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

        return await self.emsudo_get_func(
            ctx,
            *msgs,
            a=a,
            attributes=attributes,
            mode=mode,
            destination=destination,
            output_name=output_name,
            system_attributes=system_attributes,
            as_json=as_json,
            as_python=as_python,
        )

    @emsudo.command(name="pop")
    @admin_only_and_custom_parsing(inside_class=True, inject_message_reference=True)
    async def emsudo_pop(
        self,
        ctx: commands.Context,
        *msgs: discord.Message,
        a: String = String(""),
        attributes: String = String(""),
        destination: Optional[Union[discord.TextChannel, discord.Thread]] = None,
    ):
        """
        ->type emsudo commands
        ->signature pg!emsudo pop <*messages> [a|attributes=""]

        ->description 'pop' out a part of an embed into a separate one
        ->extended description
        Remove attributes of the embed of a message from the given arguments and send those as
        another embed to a given destination channel. If this is not possible
        a BotException will be raised.

        __Args__:
            `*messages: (Message)`
            > A sequence of discord messages whose embeds should
            > be modified.

            `a|attributes: (String) =`
            > A string containing the attributes to pop out
            > of the target embeds. If those attributes
            > have attributes themselves
            > (e.g. `author`, `fields`, `footer`),
            > then those can be specified using the dot `.`
            > operator inside this string.
            > If omitted or empty, the attributes of
            > all target message embeds will be serialized.
            > Embed data that becomes invalid
            > upon being popped out might not be enough
            > to successfully represent an embed anymore.
            > In some cases, popping embed attributes might
            > not be possible, thereby leading to a BotException.

            `destination (TextChannel) = `
            > A destination channel to send the output to.

        __Raises__:
            > `BotException`: One or more given arguments are invalid.
            > `HTTPException`: An invalid operation was blocked by Discord.
        ->example command
        pg!emsudo pop 98765432198765444321
        pg!emsudo pop 123456789123456789/98765432198765444321 a="description fields.0 fields.(3,7) author"
        pg!emsudo pop 123456789123456789/98765432198765444321 attributes="fields thumbnail"
        -----
        """

        if not (a.string or attributes.string):
            raise BotException(
                "Invalid embed attribute string!", "No embed attributes specified."
            )

        await self.emsudo_get_func(
            ctx,
            *msgs,
            a=a,
            attributes=attributes,
            mode=1,
            destination=destination,
            pop=True,
            copy_color_with_pop=True,
        )

    @emsudo_add.group(name="field", invoke_without_command=True)
    @admin_only_and_custom_parsing(inside_class=True, inject_message_reference=True)
    async def emsudo_add_field(
        self,
        ctx: commands.Context,
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

        response_message = common.recent_response_messages[ctx.message.id]

        if not snakecore.utils.have_permissions_in_channels(
            ctx.author,
            msg.channel,
            "view_channel",
            "send_messages",
        ):
            raise BotException(
                "Not enough permissions",
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
                field_list = snakecore.utils.embed_utils.parse_embed_field_strings(
                    field_str
                )[0]
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
                    field_dict = snakecore.utils.embed_utils.import_embed_data(
                        data.code,
                        input_format="JSON_STRING",
                    )
                except json.JSONDecodeError as j:
                    raise BotException(
                        "Invalid JSON data",
                        f"```\n{j.args[0]}\n```",
                    )
            else:
                try:
                    args = literal_eval(data.code)
                except Exception as e:
                    raise BotException(
                        "Invalid arguments!",
                        snakecore.utils.code_block(
                            snakecore.utils.format_code_exception(e)
                        ),
                    )

                if isinstance(args, dict):
                    field_dict = args

                elif isinstance(args, str):
                    field_str = args

                    try:
                        field_list = (
                            snakecore.utils.embed_utils.parse_embed_field_strings(
                                field_str
                            )[0]
                        )
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

        await msg.edit(
            embed=snakecore.utils.embed_utils.add_embed_fields_from_dicts(
                msg_embed, field_dict, in_place=False
            )
        )
        try:
            await ctx.message.delete()
            await response_message.delete()
        except discord.NotFound:
            pass

    @emsudo_add.group(name="fields", invoke_without_command=True)
    @admin_only_and_custom_parsing(inside_class=True, inject_message_reference=True)
    async def emsudo_add_fields(
        self,
        ctx: commands.Context,
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

        response_message = common.recent_response_messages[ctx.message.id]

        if not snakecore.utils.have_permissions_in_channels(
            ctx.author,
            msg.channel,
            "view_channel",
            "send_messages",
        ):
            raise BotException(
                "Not enough permissions",
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
            attachment_msg = ctx.message

        elif isinstance(data, String):
            if not data.string:
                attachment_msg = ctx.message
            else:
                raise BotException(
                    "Invalid arguments!",
                    'Argument `data` must be omitted or be an empty string `""`,'
                    " a message `[channel_id/]message_id` or a code block containing"
                    ' a list/tuple of embed field strings `"<name|value|inline>"` or embed dictionaries'
                    " `{'name: 'name', 'value': 'value'[, 'inline': True/False]}`.",
                )

        elif isinstance(data, discord.Message):
            if not snakecore.utils.have_permissions_in_channels(
                ctx.author,
                data.channel,
                "view_channel",
            ):
                raise BotException(
                    "Not enough permissions",
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
                embed_dict = snakecore.utils.embed_utils.import_embed_data(
                    embed_data, input_format="JSON_STRING"
                )
            else:
                embed_dict = snakecore.utils.embed_utils.import_embed_data(
                    embed_data, input_format="STRING"
                )

            if "fields" not in embed_dict or not embed_dict["fields"]:
                raise BotException("No embed field data found in attachment message.")

            await msg.edit(
                embed=snakecore.utils.embed_utils.add_embed_fields_from_dicts(
                    msg_embed, *embed_dict["fields"], in_place=False
                )
            )

        else:
            if data.lang == "json":
                try:
                    embed_dict = snakecore.utils.embed_utils.import_embed_data(
                        data.code,
                        input_format="JSON_STRING",
                    )
                except json.JSONDecodeError as j:
                    raise BotException(
                        "Invalid JSON data",
                        f"```\n{j.args[0]}\n```",
                    )

                if "fields" not in embed_dict or not embed_dict["fields"]:
                    raise BotException(
                        "No embed field data found in the given JSON embed data."
                    )

                await msg.edit(
                    embed=snakecore.utils.embed_utils.add_embed_fields_from_dicts(
                        msg_embed, *embed_dict["fields"], in_place=False
                    )
                )
            else:
                try:
                    args = literal_eval(data.code)
                except Exception as e:
                    raise BotException(
                        "Invalid arguments!",
                        snakecore.utils.code_block(
                            snakecore.utils.format_code_exception(e)
                        ),
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
                                data_list = snakecore.utils.embed_utils.parse_embed_field_strings(
                                    data
                                )[
                                    0
                                ]
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

                await msg.edit(
                    embed=snakecore.utils.embed_utils.add_embed_fields_from_dicts(
                        msg_embed, *field_dicts_list, in_place=False
                    )
                )

        try:
            await ctx.message.delete()
            await response_message.delete()
        except discord.NotFound:
            pass

    @emsudo_add_field.command(name="at")
    @admin_only_and_custom_parsing(inside_class=True, inject_message_reference=True)
    async def emsudo_add_field_at(
        self,
        ctx: commands.Context,
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

        response_message = common.recent_response_messages[ctx.message.id]

        if not snakecore.utils.have_permissions_in_channels(
            ctx.author,
            msg.channel,
            "view_channel",
            "send_messages",
        ):
            raise BotException(
                "Not enough permissions",
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
                field_list = snakecore.utils.embed_utils.parse_embed_field_strings(
                    field_str
                )[0]
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
                    field_dict = snakecore.utils.embed_utils.import_embed_data(
                        data.code,
                        input_format="JSON_STRING",
                    )
                except json.JSONDecodeError as j:
                    raise BotException(
                        "Invalid JSON data",
                        f"```\n{j.args[0]}\n```",
                    )
            else:
                try:
                    args = literal_eval(data.code)
                except Exception as e:
                    raise BotException(
                        "Invalid arguments!",
                        snakecore.utils.code_block(
                            snakecore.utils.format_code_exception(e)
                        ),
                    )

                if isinstance(args, dict):
                    field_dict = args

                elif isinstance(args, str):
                    field_str = args

                    try:
                        field_list = (
                            snakecore.utils.embed_utils.parse_embed_field_strings(
                                field_str
                            )[0]
                        )
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

        await msg.edit(
            embed=snakecore.utils.embed_utils.insert_embed_fields_from_dicts(
                msg_embed, index, field_dict, in_place=False
            )
        )
        try:
            await ctx.message.delete()
            await response_message.delete()
        except discord.NotFound:
            pass

    @emsudo_add_fields.command(name="at")
    @admin_only_and_custom_parsing(inside_class=True, inject_message_reference=True)
    async def emsudo_add_fields_at(
        self,
        ctx: commands.Context,
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

        response_message = common.recent_response_messages[ctx.message.id]

        if not snakecore.utils.have_permissions_in_channels(
            ctx.author,
            msg.channel,
            "view_channel",
            "send_messages",
        ):
            raise BotException(
                "Not enough permissions",
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
            attachment_msg = ctx.message

        elif isinstance(data, String):
            if not data.string:
                attachment_msg = ctx.message
            else:
                raise BotException(
                    "Invalid arguments!",
                    'Argument `data` must be omitted or be an empty string `""`,'
                    " a message `[channel_id/]message_id` or a code block containing"
                    ' a list/tuple of embed field strings `"<name|value|inline>"` or embed dictionaries'
                    " `{'name: 'name', 'value': 'value'[, 'inline': True/False]}`.",
                )

        elif isinstance(data, discord.Message):
            if not snakecore.utils.have_permissions_in_channels(
                ctx.author,
                data.channel,
                "view_channel",
            ):
                raise BotException(
                    "Not enough permissions",
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
                embed_dict = snakecore.utils.embed_utils.import_embed_data(
                    embed_data, input_format="JSON_STRING"
                )
            else:
                embed_dict = snakecore.utils.embed_utils.import_embed_data(
                    embed_data, input_format="STRING"
                )

            if "fields" not in embed_dict or not embed_dict["fields"]:
                raise BotException("No embed field data found in attachment message.")

            await msg.edit(
                embed=snakecore.utils.embed_utils.insert_embed_fields_from_dicts(
                    msg_embed, index, *embed_dict["fields"], in_place=False
                )
            )

        else:
            if data.lang == "json":
                try:
                    embed_dict = snakecore.utils.embed_utils.import_embed_data(
                        data.code,
                        input_format="JSON_STRING",
                    )
                except json.JSONDecodeError as j:
                    raise BotException(
                        "Invalid JSON data",
                        f"```\n{j.args[0]}\n```",
                    )

                if "fields" not in embed_dict or not embed_dict["fields"]:
                    raise BotException(
                        "No embed field data found in the given JSON embed data."
                    )

                await msg.edit(
                    embed=snakecore.utils.embed_utils.insert_embed_fields_from_dicts(
                        msg_embed, index, *embed_dict["fields"], in_place=False
                    )
                )
            else:
                try:
                    args = literal_eval(data.code)
                except Exception as e:
                    raise BotException(
                        "Invalid arguments!",
                        snakecore.utils.code_block(
                            snakecore.utils.format_code_exception(e)
                        ),
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
                                data_list = snakecore.utils.embed_utils.parse_embed_field_strings(
                                    data
                                )[
                                    0
                                ]
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

                await msg.edit(
                    embed=snakecore.utils.embed_utils.insert_embed_fields_from_dicts(
                        msg_embed, index, *reversed(field_dicts_list), in_place=False
                    )
                )

        try:
            await ctx.message.delete()
            await response_message.delete()
        except discord.NotFound:
            pass

    @emsudo_edit.command(name="field")
    @admin_only_and_custom_parsing(inside_class=True, inject_message_reference=True)
    async def emsudo_edit_field(
        self,
        ctx: commands.Context,
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

        response_message = common.recent_response_messages[ctx.message.id]

        if not snakecore.utils.have_permissions_in_channels(
            ctx.author,
            msg.channel,
            "view_channel",
            "send_messages",
        ):
            raise BotException(
                "Not enough permissions",
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
                field_list = snakecore.utils.embed_utils.parse_embed_field_strings(
                    field_str
                )[0]
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
                    field_dict = snakecore.utils.embed_utils.import_embed_data(
                        data.code,
                        input_format="JSON_STRING",
                    )
                except json.JSONDecodeError as j:
                    raise BotException(
                        "Invalid JSON data",
                        f"```\n{j.args[0]}\n```",
                    )
            else:
                try:
                    args = literal_eval(data.code)
                except Exception as e:
                    raise BotException(
                        "Invalid arguments!",
                        snakecore.utils.code_block(
                            snakecore.utils.format_code_exception(e)
                        ),
                    )

                if isinstance(args, dict):
                    field_dict = args

                elif isinstance(args, str):
                    field_str = args

                    try:
                        field_list = (
                            snakecore.utils.embed_utils.parse_embed_field_strings(
                                field_str
                            )[0]
                        )
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

        await msg.edit(
            embed=snakecore.utils.embed_utils.edit_embed_field_from_dict(
                msg_embed, index, field_dict, in_place=False
            )
        )

        try:
            await ctx.message.delete()
            await response_message.delete()
        except discord.NotFound:
            pass

    @emsudo_edit.command(name="fields")
    @admin_only_and_custom_parsing(inside_class=True, inject_message_reference=True)
    async def emsudo_edit_fields(
        self,
        ctx: commands.Context,
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

        response_message = common.recent_response_messages[ctx.message.id]

        if not snakecore.utils.have_permissions_in_channels(
            ctx.author,
            msg.channel,
            "view_channel",
            "send_messages",
        ):
            raise BotException(
                "Not enough permissions",
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
            attachment_msg = ctx.message

        elif isinstance(data, String):
            if not data.string:
                attachment_msg = ctx.message
            else:
                raise BotException(
                    "Invalid arguments!",
                    'Argument `data` must be omitted or be an empty string `""`,'
                    " a message `[channel_id/]message_id` or a code block containing"
                    ' a list/tuple of embed field strings `"<name|value|inline>"` or embed dictionaries'
                    " `{'name: 'name', 'value': 'value'[, 'inline': True/False]}`.",
                )

        elif isinstance(data, discord.Message):
            if not snakecore.utils.have_permissions_in_channels(
                ctx.author,
                data.channel,
                "view_channel",
            ):
                raise BotException(
                    "Not enough permissions",
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
                embed_dict = snakecore.utils.embed_utils.import_embed_data(
                    embed_data, input_format="JSON_STRING"
                )
            else:
                embed_dict = snakecore.utils.embed_utils.import_embed_data(
                    embed_data, input_format="STRING"
                )

            if "fields" not in embed_dict or not embed_dict["fields"]:
                raise BotException("No embed field data found in attachment message.")

            await msg.edit(
                embed=snakecore.utils.embed_utils.edit_embed_fields_from_dicts(
                    msg_embed, *embed_dict["fields"], in_place=False
                )
            )

        else:
            if data.lang == "json":
                try:
                    embed_dict = snakecore.utils.embed_utils.import_embed_data(
                        data.code,
                        input_format="JSON_STRING",
                    )
                except json.JSONDecodeError as j:
                    raise BotException(
                        "Invalid JSON data",
                        f"```\n{j.args[0]}\n```",
                    )

                if "fields" not in embed_dict or not embed_dict["fields"]:
                    raise BotException(
                        "No embed field data found in the given JSON embed data."
                    )

                await msg.edit(
                    embed=snakecore.utils.embed_utils.edit_embed_fields_from_dicts(
                        msg_embed, *embed_dict["fields"], in_place=False
                    )
                )
            else:
                try:
                    args = literal_eval(data.code)
                except Exception as e:
                    raise BotException(
                        "Invalid arguments!",
                        snakecore.utils.code_block(
                            snakecore.utils.format_code_exception(e)
                        ),
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
                                data_list = snakecore.utils.embed_utils.parse_embed_field_strings(
                                    data
                                )[
                                    0
                                ]
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

                await msg.edit(
                    embed=snakecore.utils.embed_utils.edit_embed_fields_from_dicts(
                        msg_embed, *field_dicts_list, in_place=False
                    )
                )

        try:
            await ctx.message.delete()
            await response_message.delete()
        except discord.NotFound:
            pass

    @emsudo_replace.command(name="field")
    @admin_only_and_custom_parsing(inside_class=True, inject_message_reference=True)
    async def emsudo_replace_field(
        self,
        ctx: commands.Context,
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

        response_message = common.recent_response_messages[ctx.message.id]

        if not snakecore.utils.have_permissions_in_channels(
            ctx.author,
            msg.channel,
            "view_channel",
            "send_messages",
        ):
            raise BotException(
                "Not enough permissions",
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
                field_list = snakecore.utils.embed_utils.parse_embed_field_strings(
                    field_str
                )[0]
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
                    field_dict = snakecore.utils.embed_utils.import_embed_data(
                        data.code,
                        input_format="JSON_STRING",
                    )
                except json.JSONDecodeError as j:
                    raise BotException(
                        "Invalid JSON data",
                        f"```\n{j.args[0]}\n```",
                    )
            else:
                try:
                    args = literal_eval(data.code)
                except Exception as e:
                    raise BotException(
                        "Invalid arguments!",
                        snakecore.utils.code_block(
                            snakecore.utils.format_code_exception(e)
                        ),
                    )

                if isinstance(args, dict):
                    field_dict = args

                elif isinstance(args, str):
                    field_str = args

                    try:
                        field_list = (
                            snakecore.utils.embed_utils.parse_embed_field_strings(
                                field_str
                            )[0]
                        )
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

        await msg.edit(
            embed=snakecore.utils.embed_utils.edit_embed_field_from_dict(
                msg_embed, index, field_dict, in_place=False
            )
        )

        try:
            await ctx.message.delete()
            await response_message.delete()
        except discord.NotFound:
            pass

    @emsudo_swap.command(name="fields")
    @admin_only_and_custom_parsing(inside_class=True, inject_message_reference=True)
    async def emsudo_swap_fields(
        self, ctx: commands.Context, msg: discord.Message, index_a: int, index_b: int
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

        response_message = common.recent_response_messages[ctx.message.id]

        if not snakecore.utils.have_permissions_in_channels(
            ctx.author,
            msg.channel,
            "view_channel",
            "send_messages",
        ):
            raise BotException(
                "Not enough permissions",
                "You do not have enough permissions to run this command on the specified channel.",
            )

        if not msg.embeds:
            raise BotException(
                "Cannot execute command:",
                "No embed data found in message.",
            )

        msg_embed = msg.embeds[0]

        await msg.edit(
            embed=snakecore.utils.embed_utils.swap_embed_fields(
                msg_embed, index_a, index_b, in_place=False
            )
        )

        try:
            await ctx.message.delete()
            await response_message.delete()
        except discord.NotFound:
            pass

    @emsudo_clone.command(name="fields")
    @admin_only_and_custom_parsing(inside_class=True, inject_message_reference=True)
    async def emsudo_clone_fields(
        self,
        ctx: commands.Context,
        msg: discord.Message,
        *indices: Union[int, range],
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

        response_message = common.recent_response_messages[ctx.message.id]

        if not snakecore.utils.have_permissions_in_channels(
            ctx.author,
            msg.channel,
            "view_channel",
            "send_messages",
        ):
            raise BotException(
                "Not enough permissions",
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
            await msg.edit(
                embed=snakecore.utils.embed_utils.clone_embed_fields(
                    msg_embed, *field_indices, insertion_index=clone_to, in_place=False
                )
            )
        except IndexError:
            raise BotException("Invalid field index/indices!", "")

        try:
            await ctx.message.delete()
            await response_message.delete()
        except discord.NotFound:
            pass

    @emsudo_remove.command(name="fields")
    @admin_only_and_custom_parsing(inside_class=True, inject_message_reference=True)
    async def emsudo_remove_fields(
        self,
        ctx: commands.Context,
        msg: discord.Message,
        *indices: Union[int, range],
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

        response_message = common.recent_response_messages[ctx.message.id]

        if not snakecore.utils.have_permissions_in_channels(
            ctx.author,
            msg.channel,
            "view_channel",
            "send_messages",
        ):
            raise BotException(
                "Not enough permissions",
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
            await msg.edit(
                embed=snakecore.utils.embed_utils.remove_embed_fields(
                    msg_embed, *field_indices, in_place=False
                )
            )
        except IndexError:
            raise BotException("Invalid field index/indices!", "")

        try:
            await ctx.message.delete()
            await response_message.delete()
        except discord.NotFound:
            pass

    @emsudo_remove.command(name="allfields")
    @admin_only_and_custom_parsing(inside_class=True, inject_message_reference=True)
    async def emsudo_remove_all_fields(
        self,
        ctx: commands.Context,
        msg: discord.Message,
    ):
        """
        ->type More emsudo commands
        ->signature pg!emsudo remove allfields <message>
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

        response_message = common.recent_response_messages[ctx.message.id]

        if not snakecore.utils.have_permissions_in_channels(
            ctx.author,
            msg.channel,
            "view_channel",
            "send_messages",
        ):
            raise BotException(
                "Not enough permissions",
                "You do not have enough permissions to run this command on the specified channel.",
            )

        if not msg.embeds:
            raise BotException(
                "Cannot execute command:",
                "No embed data found in message.",
            )

        msg_embed = msg.embeds[0].copy()

        msg_embed.clear_fields()

        await msg.edit(embed=msg_embed)

        try:
            await ctx.message.delete()
            await response_message.delete()
        except discord.NotFound:
            pass
