"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file defines some important embed related utility functions.
"""


import asyncio
import datetime
import io
import json
import re
from ast import literal_eval
from collections.abc import Mapping
from typing import Union, Iterable

import black
import discord
from discord.embeds import EmptyEmbed

from . import common

EMBED_TOP_LEVEL_ATTRIBUTES_MASK_DICT = {
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

EMBED_TOP_LEVEL_ATTRIBUTES_SET = {
    "provider",
    "type",
    "title",
    "description",
    "url",
    "color",
    "timestamp",
    "footer",
    "thumbnail",
    "image",
    "author",
    "fields",
}

EMBED_SYSTEM_ATTRIBUTES_MASK_DICT = {
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

EMBED_SYSTEM_ATTRIBUTES_SET = {
    "provider",
    "proxy_url",
    "proxy_icon_url",
    "width",
    "height",
    "type",
}

EMBED_NON_SYSTEM_ATTRIBUTES_SET = {
    "name",
    "value",
    "inline",
    "url",
    "image",
    "thumbnail",
    "title",
    "description",
    "color",
    "timestamp",
    "footer",
    "text",
    "icon_url",
    "author",
    "fields",
}

EMBED_ATTRIBUTES_SET = {
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
}

EMBED_ATTRIBUTES_WITH_SUB_ATTRIBUTES_SET = {
    "author",
    "thumbnail",
    "image",
    "fields",
    "footer",
    "provider",
}  # 'fields' is a special case

DEFAULT_EMBED_COLOR = 0xFFFFAA

CONDENSED_EMBED_SYNTAX_STRUCTURE = """
# Condensed embed data list syntax. String elements that are empty "" will be ignored.
[
    'author.name' or ('author.name', 'author.url') or ('author.name', 'author.url', 'icon.url'),   # embed author

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
"""


def recursive_update(old_dict, update_dict, add_new_keys=True, skip_value="\0"):
    """
    Update one embed dictionary with another, similar to dict.update(),
    But recursively update dictionary values that are dictionaries as well.
    based on the answers in
    https://stackoverflow.com/questions/3232943/update-value-of-a-nested-dictionary-of-varying-depth
    """
    for k, v in update_dict.items():
        if isinstance(v, Mapping):
            new_value = recursive_update(
                old_dict.get(k, {}), v, add_new_keys=add_new_keys, skip_value=skip_value
            )
            if new_value != skip_value:
                if k not in old_dict:
                    if not add_new_keys:
                        continue
                old_dict[k] = new_value
        else:
            if v != skip_value:
                if k not in old_dict:
                    if not add_new_keys:
                        continue
                old_dict[k] = v

    return old_dict


def recursive_delete(old_dict, update_dict, skip_value="\0", inverse=False):
    """
    Delete embed dictionary attributes present in another,
    But recursively do the same dictionary values that are dictionaries as well.
    based on the answers in
    https://stackoverflow.com/questions/3232943/update-value-of-a-nested-dictionary-of-varying-depth
    """
    if inverse:
        for k, v in tuple(old_dict.items()):
            if isinstance(v, Mapping):
                lower_update_dict = None
                if isinstance(update_dict, dict):
                    lower_update_dict = update_dict.get(k, {})

                new_value = recursive_delete(
                    v, lower_update_dict, skip_value=skip_value, inverse=inverse
                )
                if (
                    new_value != skip_value
                    and isinstance(update_dict, dict)
                    and k not in update_dict
                ):
                    old_dict[k] = new_value
                    if not new_value:
                        del old_dict[k]
            else:
                if (
                    v != skip_value
                    and isinstance(update_dict, dict)
                    and k not in update_dict
                ):
                    del old_dict[k]
    else:
        for k, v in update_dict.items():
            if isinstance(v, Mapping):
                new_value = recursive_delete(
                    old_dict.get(k, {}), v, skip_value=skip_value
                )
                if new_value != skip_value and k in old_dict:
                    old_dict[k] = new_value
                    if not new_value:
                        del old_dict[k]
            else:
                if v != skip_value and k in old_dict:
                    del old_dict[k]
    return old_dict


def create_embed_mask_dict(
    attributes="",
    allow_system_attributes=False,
    fields_as_field_dict=False,
):
    embed_top_level_attrib_dict = EMBED_TOP_LEVEL_ATTRIBUTES_MASK_DICT
    embed_top_level_attrib_dict = {
        k: embed_top_level_attrib_dict[k].copy()
        if isinstance(embed_top_level_attrib_dict[k], dict)
        else embed_top_level_attrib_dict[k]
        for k in embed_top_level_attrib_dict
    }

    system_attribs_dict = EMBED_SYSTEM_ATTRIBUTES_MASK_DICT
    system_attribs_dict = {
        k: system_attribs_dict[k].copy()
        if isinstance(system_attribs_dict[k], dict)
        else system_attribs_dict[k]
        for k in system_attribs_dict
    }

    all_system_attribs_set = EMBED_SYSTEM_ATTRIBUTES_SET

    embed_mask_dict = {}

    attribs = attributes

    attribs_tuple = tuple(
        attr_str.split(sep=".") if "." in attr_str else attr_str
        for attr_str in attribs.split()
    )

    all_attribs_set = EMBED_ATTRIBUTES_SET | set(str(i) for i in range(25))

    attribs_with_sub_attribs = EMBED_ATTRIBUTES_WITH_SUB_ATTRIBUTES_SET

    for attr in attribs_tuple:
        if isinstance(attr, list):
            if len(attr) > 3:
                raise ValueError(
                    "Invalid embed attribute filter string!"
                    " Sub-attributes do not propagate beyond 3 levels.",
                )
            bottom_dict = {}
            for i in range(len(attr)):
                if attr[i] not in all_attribs_set:
                    raise ValueError(
                        f"`{attr[i]}` is not a valid embed (sub-)attribute name!",
                    )
                elif attr[i] in all_system_attribs_set and not allow_system_attributes:
                    raise ValueError(
                        f"The given attribute `{attr[i]}` cannot be retrieved when `system_attributes=`"
                        " is set to `False`.",
                    )
                if not i:
                    if attribs_tuple.count(attr[i]):
                        raise ValueError(
                            "Invalid embed attribute filter string!"
                            f" Do not specify upper level embed attributes twice! {attr[i]}",
                        )
                    elif attr[i] not in attribs_with_sub_attribs:
                        raise ValueError(
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
                                raise ValueError(
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

        elif attr in embed_top_level_attrib_dict:
            if attribs_tuple.count(attr) > 1:
                raise ValueError(
                    "Invalid embed attribute filter string!"
                    f" Do not specify upper level embed attributes twice: `{attr}`",
                )
            elif attr in all_system_attribs_set and not allow_system_attributes:
                raise ValueError(
                    f"The given attribute `{attr}` cannot be retrieved when `system_attributes=`"
                    " is set to `False`.",
                )

            if attr not in embed_mask_dict:
                embed_mask_dict[attr] = None
            else:
                raise ValueError(
                    "Invalid embed attribute filter string!"
                    " Do not specify upper level embed attributes twice!",
                )

        else:
            raise ValueError(
                f"Invalid embed attribute name `{attr}`!",
            )

    if not fields_as_field_dict and "fields" in embed_mask_dict:
        embed_mask_dict["fields"] = [
            embed_mask_dict["fields"][i]
            for i in sorted(embed_mask_dict["fields"].keys())
        ]

    return embed_mask_dict


def copy_embed(embed):
    return discord.Embed.from_dict(embed.to_dict())


def copy_embed_dict(embed_dict):
    copied_embed_dict = {
        k: embed_dict[k].copy() if isinstance(embed_dict[k], dict) else embed_dict[k]
        for k in embed_dict
    }

    if "fields" in embed_dict:
        copied_embed_dict["fields"] = [
            field_dict.copy() for field_dict in embed_dict["fields"]
        ]
    return copied_embed_dict


def get_fields(*strings):
    """
    Get a list of fields from messages.
    Syntax of an embed field string: <name|value[|inline]>

    Args:
        *messages (Union[str, List[str]]): The messages to get the fields from

    Returns:
        List[List[str, str, bool]]: The list of fields. if only one message is given as input, then only one field is returned.
    """
    # syntax: <Title|desc.[|inline=False]>
    field_regex = r"(<.*\|.*(\|True|\|False|\|1|\|0|)>)"
    field_datas = []
    true_bool_strings = ("", "True", "1")

    for string in strings:
        field_list = re.split(field_regex, string)
        for field in field_list:
            if field:
                field = field.strip()[1:-1]  # remove < and >
                field_data = field.split("|")

                if len(field_data) not in (2, 3):
                    continue
                elif len(field_data) == 2:
                    field_data.append("")

                field_data[2] = True if field_data[2] in true_bool_strings else False

                field_datas.append(field_data)

    return field_datas


class PagedEmbed:
    def __init__(self, message, pages, caller=None, command=None, start_page=0):
        """
        Create an embed which can be controlled by reactions. The footer of the
        embeds will be overwritten. If the optional "command" argument
        is set the embed page will be refreshable. The pages argument must
        have at least one embed.

        Args:
            message (discord.Message): The message to overwrite. For commands,
            it would be self.response_msg

            pages (list[discord.Embed]): The list of embeds to change
            pages between

            caller (discord.Member, optional): The user that can control
            the embed. Defaults to None (everyone can control it).

            command (str, optional): Optional argument to support pg!refresh.
            Defaults to None.

            start_page (int, optional): The page to start from. Defaults to 0.
        """
        self.pages = pages
        self.current_page = start_page
        self.message = message
        self.parent_command = command
        self.is_on_info = False

        self.control_emojis = {
            "first": ("", ""),
            "prev": ("◀️", "Go to the previous page"),
            "stop": ("⏹️", "Deactivate the buttons"),
            "info": ("ℹ️", "Show this information page"),
            "next": ("▶️", "Go to the next page"),
            "last": ("", ""),
        }

        if len(self.pages) >= 3:
            self.control_emojis["first"] = ("⏪", "Go to the first page")
            self.control_emojis["last"] = ("⏩", "Go to the last page")

        self.killed = False
        self.caller = caller

        newline = "\n"
        self.help_text = ""
        for emoji, desc in self.control_emojis.values():
            if emoji:
                self.help_text += f"{emoji}: {desc}{newline}"

    async def add_control_emojis(self):
        """Add the control reactions to the message."""
        for emoji in self.control_emojis.values():
            if emoji[0]:
                await self.message.add_reaction(emoji[0])

    async def handle_reaction(self, reaction):
        """Handle a reaction."""
        if reaction == self.control_emojis.get("next")[0]:
            await self.set_page(self.current_page + 1)

        if reaction == self.control_emojis.get("prev")[0]:
            await self.set_page(self.current_page - 1)

        if reaction == self.control_emojis.get("first")[0]:
            await self.set_page(0)

        if reaction == self.control_emojis.get("last")[0]:
            await self.set_page(len(self.pages) - 1)

        if reaction == self.control_emojis.get("stop")[0]:
            self.killed = True

        if reaction == self.control_emojis.get("info")[0]:
            await self.show_info_page()

    async def show_info_page(self):
        """Create and show the info page."""
        self.is_on_info = not self.is_on_info
        if self.is_on_info:
            info_page_embed = await send_2(
                None,
                description=self.help_text,
            )
            footer = self.get_footer_text(self.current_page)
            info_page_embed.set_footer(text=footer)
            await self.message.edit(embed=info_page_embed)
        else:
            await self.message.edit(embed=self.pages[self.current_page])

    async def set_page(self, num):
        """Set the current page and display it."""
        self.is_on_info = False
        self.current_page = num % len(self.pages)
        await self.message.edit(embed=self.pages[self.current_page])

    async def setup(self):
        if len(self.pages) == 1:
            await self.message.edit(embed=self.pages[0])
            return False

        for i, page in enumerate(self.pages):
            footer = self.get_footer_text(i)

            page.set_footer(text=footer)

        await self.message.edit(embed=self.pages[self.current_page])
        await self.add_control_emojis()

        return True

    def get_footer_text(self, page_num):
        """Get the information footer text, which contains the current page."""
        newline = "\n"
        footer = f"Page {page_num + 1} of {len(self.pages)}.{newline}"

        if self.parent_command:
            footer += f"Refresh with pg!refresh {self.message.id}{newline}"
            footer += f"Command: {self.parent_command}"

        return footer

    async def check(self, event):
        """Check if the event from "raw_reaction_add" can be passed down to `handle_rection`"""
        if event.member.bot:
            return False

        await self.message.remove_reaction(str(event.emoji), event.member)
        if self.caller and self.caller.id != event.user_id:
            for role in event.member.roles:
                if not common.GENERIC and role.id in common.ServerConstants.ADMIN_ROLES:
                    break
            else:
                return False

        return event.message_id == self.message.id

    async def mainloop(self):
        """Start the mainloop. This checks for reactions and handles them."""
        if not await self.setup():
            return

        while not self.killed:
            try:
                event = await common.bot.wait_for("raw_reaction_add", timeout=60)

                if await self.check(event):
                    await self.handle_reaction(str(event.emoji))

            except asyncio.TimeoutError:
                self.killed = True

        await self.message.clear_reactions()


async def replace(
    message, title="", description="", color=0xFFFFAA, url_image=None, fields=[]
):
    """
    Edits the embed of a message with a much more tight function
    """
    embed = discord.Embed(
        title=title,
        description=description,
        color=color if 0 <= color < 0x1000000 else DEFAULT_EMBED_COLOR,
    )
    if url_image:
        embed.set_image(url=url_image)

    for field in fields:
        embed.add_field(name=field[0], value=field[1], inline=field[2])

    return await message.edit(embed=embed)


async def send(
    channel,
    title="",
    description="",
    color=0xFFFFAA,
    url_image=None,
    fields=[],
    do_return=False,
):
    """
    Sends an embed with a much more tight function
    """
    embed = discord.Embed(
        title=title,
        description=description,
        color=color if 0 <= color < 0x1000000 else DEFAULT_EMBED_COLOR,
    )
    if url_image:
        embed.set_image(url=url_image)

    for field in fields:
        embed.add_field(name=field[0], value=field[1], inline=field[2])

    if do_return or channel == None:
        return embed

    return await channel.send(embed=embed)


def parse_condensed_embed_list(embed_list: Union[list, tuple]):
    """
    Parse the condensed embed list syntax used in some embed creation
    comnands. The syntax is:
    [
        'author.name' or ('author.name', 'author.url') or ('author.name', 'author.url', 'icon.url'),   # embed author

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

    The list must contain at least 1 element.
    """
    arg_count = len(embed_list)

    embed_args = dict(
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

    if arg_count > 0:
        if isinstance(embed_list[0], (tuple, list)):
            if len(embed_list[0]) == 3:
                embed_args.update(
                    author_name=embed_list[0][0] + "",
                    author_url=embed_list[0][0] + "",
                    author_icon_url=embed_list[0][2] + "",
                )
            elif len(embed_list[0]) == 2:
                embed_args.update(
                    author_name=embed_list[0][0] + "",
                    author_url=embed_list[0][1] + "",
                )
            elif len(embed_list[0]) == 1:
                embed_args.update(
                    author_name=embed_list[0][0] + "",
                )

        else:
            embed_args.update(
                author_name=embed_list[0] + "",
            )
    else:
        raise ValueError(
            f"Invalid arguments! The condensed embed syntax is: ```\n{CONDENSED_EMBED_SYNTAX_STRUCTURE}\n```"
        )

    if arg_count > 1:
        if isinstance(embed_list[1], (tuple, list)):
            if len(embed_list[1]) == 3:
                embed_args.update(
                    title=embed_list[1][0] + "",
                    url=embed_list[1][1] + "",
                    thumbnail_url=embed_list[1][2] + "",
                )

            elif len(embed_list[1]) == 2:
                embed_args.update(
                    title=embed_list[1][0] + "",
                    url=embed_list[1][1] + "",
                )

            elif len(embed_list[1]) == 1:
                embed_args.update(
                    title=embed_list[1][0] + "",
                )

        else:
            embed_args.update(
                title=embed_list[1] + "",
            )

    if arg_count > 2:
        if isinstance(embed_list[2], (tuple, list)):
            if len(embed_list[2]) == 2:
                embed_args.update(
                    description=embed_list[2][0] + "",
                    image_url=embed_list[2][1] + "",
                )

            elif len(embed_list[2]) == 1:
                embed_args.update(
                    description=embed_list[2][0] + "",
                )

        else:
            embed_args.update(
                description=embed_list[2] + "",
            )

    if arg_count > 3:
        if embed_list[3] > -1:
            embed_args.update(
                color=embed_list[3] + 0,
            )
        else:
            embed_args.update(
                color=-1,
            )

    if arg_count > 4:
        try:
            fields = get_fields(*embed_list[4])
            embed_args.update(fields=fields)
        except TypeError:
            raise ValueError(
                "Invalid format for field string(s) in the condensed embed syntax!"
                'The format should be `"<name|value|inline>"`'
            )

    if arg_count > 5:
        if isinstance(embed_list[5], (tuple, list)):
            if len(embed_list[5]) == 2:
                embed_args.update(
                    footer_text=embed_list[5][0] + "",
                    footer_icon_url=embed_list[5][1] + "",
                )

            elif len(embed_list[5]) == 1:
                embed_args.update(
                    footer_text=embed_list[5][0] + "",
                )

        else:
            embed_args.update(
                footer_text=embed_list[5] + "",
            )

    if arg_count > 6:
        embed_args.update(timestamp=embed_list[6] + "")

    return embed_args


def create_as_dict(
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
    timestamp=EmptyEmbed,
):
    embed_dict = {}

    if author_name or author_url or author_icon_url:
        embed_dict["author"] = {}
        if author_name:
            embed_dict["author"]["name"] = author_name
        if author_url:
            embed_dict["author"]["url"] = author_url
        if author_icon_url:
            embed_dict["author"]["icon_url"] = author_icon_url

    if footer_text or footer_icon_url:
        embed_dict["footer"] = {}
        if footer_text:
            embed_dict["footer"]["text"] = footer_text
        if footer_icon_url:
            embed_dict["footer"]["icon_url"] = footer_icon_url

    if title:
        embed_dict["title"] = title

    if url:
        embed_dict["url"] = url

    if description:
        embed_dict["description"] = description

    embed_dict["color"] = color if 0 <= color < 0x1000000 else DEFAULT_EMBED_COLOR

    if timestamp:
        if isinstance(timestamp, str):
            embed_dict["timestamp"] = datetime.datetime.fromisoformat(
                timestamp[:-1] if timestamp.endswith("Z") else timestamp
            )
        else:
            embed_dict["timestamp"] = timestamp

    if image_url:
        embed_dict["image"] = {"url": image_url}

    if thumbnail_url:
        embed_dict["thumbnail"] = {"url": thumbnail_url}

    if fields:
        fields_list = []
        embed_dict["fields"] = fields_list
        for field in fields:
            field_dict = {}
            if isinstance(field, dict):
                if field.get("name", ""):
                    field_dict["name"] = field["name"]

                if field.get("value", ""):
                    field_dict["value"] = field["value"]

                if field.get("inline", "") in (False, True):
                    field_dict["name"] = field["name"]

            elif isinstance(field, (list, tuple)):
                name = None
                value = None
                inline = None
                field_len = len(field)
                if field_len == 3:
                    name, value, inline = field
                    if name:
                        field_dict["name"] = name

                    if value:
                        field_dict["value"] = value

                    if inline in (False, True):
                        field_dict["inline"] = field["inline"]

            if field_dict:
                fields_list.append(field_dict)

    return embed_dict


def validate_embed_dict(embed_dict):
    if not embed_dict:
        return False
    
    valid = True
    embed_dict_len = len(embed_dict)
    for k in tuple(embed_dict.keys()):
        if (
            embed_dict_len == 1 and (k == "color" or k == "timestamp")
            or embed_dict_len == 2 and ("color" in embed_dict and "timestamp" in embed_dict)
            ):
            valid = False
        elif (
            not embed_dict[k]
            or k == "footer"
            and "text" not in embed_dict[k]
            or k == "author"
            and "name" not in embed_dict[k]
            or k in ("thumbnail", "image")
            and "url" not in embed_dict[k]
        ):
            valid = False
            break
        elif k == "fields":
            for i in reversed(range(len(embed_dict["fields"]))):
                if (
                    "name" not in embed_dict["fields"][i]
                    or "value" not in embed_dict["fields"][i]
                ):
                    valid = False
                    break
    
    return valid

def correct_embed_dict(embed_dict):
    for k in tuple(embed_dict.keys()):
        if (
            not embed_dict[k]
            or k == "footer"
            and "text" not in embed_dict[k]
            or k == "author"
            and "name" not in embed_dict[k]
            or k in ("thumbnail", "image")
            and "url" not in embed_dict[k]
        ):
            del embed_dict[k]

        elif k == "fields":
            for i in reversed(range(len(embed_dict["fields"]))):
                if (
                    "name" not in embed_dict["fields"][i]
                    or "value" not in embed_dict["fields"][i]
                ):
                    embed_dict["fields"].pop(i)
    
    return embed_dict

def create(
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
    timestamp=EmptyEmbed,
):
    """
    Creates an embed with a much more tight function.
    """
    embed = discord.Embed(
        title=title,
        url=url,
        description=description,
        color=color if 0 <= color < 0x1000000 else DEFAULT_EMBED_COLOR,
    )

    if timestamp:
        if isinstance(timestamp, str):
            embed.timestamp = datetime.datetime.fromisoformat(
                timestamp[:-1] if timestamp.endswith("Z") else timestamp
            )
        else:
            embed.timestamp = timestamp

    if author_name:
        embed.set_author(name=author_name, url=author_url, icon_url=author_icon_url)

    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)

    if image_url:
        embed.set_image(url=image_url)

    for field in fields:
        if isinstance(field, dict):
            embed.add_field(
                name=field.get("name", ""),
                value=field.get("value", ""),
                inline=field.get("inline", True),
            )
        else:
            embed.add_field(name=field[0], value=field[1], inline=field[2])

    if footer_text:
        embed.set_footer(text=footer_text, icon_url=footer_icon_url)

    return embed


async def send_2(
    channel,
    author_name=EmptyEmbed,
    author_url=EmptyEmbed,
    author_icon_url=EmptyEmbed,
    title=EmptyEmbed,
    url=EmptyEmbed,
    thumbnail_url=EmptyEmbed,
    description=EmptyEmbed,
    image_url=EmptyEmbed,
    color=0xFFFFAA,
    fields=[],
    footer_text=EmptyEmbed,
    footer_icon_url=EmptyEmbed,
    timestamp=EmptyEmbed,
):
    """
    Sends an embed with a much more tight function. If the channel is
    None it will return the embed instead of sending it.
    """

    embed = create(
        author_name=author_name,
        author_url=author_url,
        author_icon_url=author_icon_url,
        title=title,
        url=url,
        thumbnail_url=thumbnail_url,
        description=description,
        image_url=image_url,
        color=color,
        fields=fields,
        footer_text=footer_text,
        footer_icon_url=footer_icon_url,
        timestamp=timestamp,
    )

    if channel is None:
        return embed

    return await channel.send(embed=embed)


async def replace_2(
    message,
    author_name=EmptyEmbed,
    author_url=EmptyEmbed,
    author_icon_url=EmptyEmbed,
    title=EmptyEmbed,
    url=EmptyEmbed,
    thumbnail_url=EmptyEmbed,
    description=EmptyEmbed,
    image_url=EmptyEmbed,
    color=0xFFFFAA,
    fields=[],
    footer_text=EmptyEmbed,
    footer_icon_url=EmptyEmbed,
    timestamp=EmptyEmbed,
):
    """
    Replaces the embed of a message with a much more tight function
    """
    embed = create(
        author_name=author_name,
        author_url=author_url,
        author_icon_url=author_icon_url,
        title=title,
        url=url,
        thumbnail_url=thumbnail_url,
        description=description,
        image_url=image_url,
        color=color,
        fields=fields,
        footer_text=footer_text,
        footer_icon_url=footer_icon_url,
        timestamp=timestamp,
    )
    return await message.edit(embed=embed)


async def edit_2(
    message,
    embed,
    author_name=EmptyEmbed,
    author_url=EmptyEmbed,
    author_icon_url=EmptyEmbed,
    title=EmptyEmbed,
    url=EmptyEmbed,
    thumbnail_url=EmptyEmbed,
    description=EmptyEmbed,
    image_url=EmptyEmbed,
    color=0xFFFFAA,
    fields=[],
    footer_text=EmptyEmbed,
    footer_icon_url=EmptyEmbed,
    timestamp=EmptyEmbed,
    add_attributes=False,
    inner_fields: bool = False,
):
    """
    Updates the changed attributes of the embed of a message with a
    much more tight function
    """
    old_embed_dict = embed.to_dict()
    update_embed_dict = create_as_dict(
        author_name=author_name,
        author_url=author_url,
        author_icon_url=author_icon_url,
        title=title,
        url=url,
        thumbnail_url=thumbnail_url,
        description=description,
        image_url=image_url,
        color=color,
        fields=fields,
        footer_text=footer_text,
        footer_icon_url=footer_icon_url,
        timestamp=timestamp,
    )

    if inner_fields:
        if "fields" in old_embed_dict:
            old_embed_dict["fields"] = {
                str(i): old_embed_dict["fields"][i]
                for i in range(len(old_embed_dict["fields"]))
            }
        if "fields" in update_embed_dict:
            update_embed_dict["fields"] = {
                str(i): update_embed_dict["fields"][i]
                for i in range(len(update_embed_dict["fields"]))
            }

    recursive_update(
        old_embed_dict, update_embed_dict, add_new_keys=add_attributes, skip_value=""
    )

    if inner_fields:
        if "fields" in old_embed_dict:
            old_embed_dict["fields"] = [
                old_embed_dict["fields"][i]
                for i in sorted(old_embed_dict["fields"].keys())
            ]
        if "fields" in update_embed_dict:
            update_embed_dict["fields"] = [
                update_embed_dict["fields"][i]
                for i in sorted(update_embed_dict["fields"].keys())
            ]

    if message is None:
        return discord.Embed.from_dict(old_embed_dict)

    return await message.edit(embed=discord.Embed.from_dict(old_embed_dict))


def create_from_dict(data):
    """
    Creates an embed from a dictionary with a much more tight function
    """

    if data.get("timestamp") and data["timestamp"].endswith("Z"):
        data["timestamp"] = data["timestamp"][:-1]

    return discord.Embed.from_dict(data)


async def send_from_dict(channel, data):
    """
    Sends an embed from a dictionary with a much more tight function
    """

    if data.get("timestamp") and data["timestamp"].endswith("Z"):
        data["timestamp"] = data["timestamp"][:-1]

    if channel is None:
        return discord.Embed.from_dict(data)

    return await channel.send(embed=discord.Embed.from_dict(data))


async def replace_from_dict(message, data):
    """
    Replaces the embed of a message from a dictionary with a much more
    tight function
    """
    if data.get("timestamp") and data["timestamp"].endswith("Z"):
        data["timestamp"] = data["timestamp"][:-1]

    if message is None:
        return discord.Embed.from_dict(data)

    return await message.edit(embed=discord.Embed.from_dict(data))


async def edit_from_dict(
    message, embed, update_embed_dict, add_attributes=True, inner_fields=False
):
    """
    Edits the changed attributes of the embed of a message from a
    dictionary with a much more tight function
    """
    old_embed_dict = embed.to_dict()

    if inner_fields:
        if "fields" in old_embed_dict:
            old_embed_dict["fields"] = {
                str(i): old_embed_dict["fields"][i]
                for i in range(len(old_embed_dict["fields"]))
            }
        if "fields" in update_embed_dict:
            update_embed_dict["fields"] = {
                str(i): update_embed_dict["fields"][i]
                for i in range(len(update_embed_dict["fields"]))
            }

    recursive_update(
        old_embed_dict, update_embed_dict, add_new_keys=add_attributes, skip_value=""
    )

    if inner_fields:
        if "fields" in old_embed_dict:
            old_embed_dict["fields"] = [
                old_embed_dict["fields"][i]
                for i in sorted(old_embed_dict["fields"].keys())
            ]
        if "fields" in update_embed_dict:
            update_embed_dict["fields"] = [
                update_embed_dict["fields"][i]
                for i in sorted(update_embed_dict["fields"].keys())
            ]

    if message is None:
        return discord.Embed.from_dict(old_embed_dict)

    return await message.edit(embed=discord.Embed.from_dict(old_embed_dict))


def edit_dict_from_dict(
    old_embed_dict, update_embed_dict, add_attributes=True, inner_fields=False
):
    """
    Edits the changed attributes of an embed dictionary using another
    dictionary
    """
    if inner_fields:
        if "fields" in old_embed_dict:
            old_embed_dict["fields"] = {
                str(i): old_embed_dict["fields"][i]
                for i in range(len(old_embed_dict["fields"]))
            }
        if "fields" in update_embed_dict:
            update_embed_dict["fields"] = {
                str(i): update_embed_dict["fields"][i]
                for i in range(len(update_embed_dict["fields"]))
            }

    recursive_update(
        old_embed_dict, update_embed_dict, add_new_keys=add_attributes, skip_value=""
    )

    if inner_fields:
        if "fields" in old_embed_dict:
            old_embed_dict["fields"] = [
                old_embed_dict["fields"][i]
                for i in sorted(old_embed_dict["fields"].keys())
            ]
        if "fields" in update_embed_dict:
            update_embed_dict["fields"] = [
                update_embed_dict["fields"][i]
                for i in sorted(update_embed_dict["fields"].keys())
            ]

    return old_embed_dict


async def replace_field_from_dict(message, embed, field_dict, index):
    """
    Replaces an embed field of the embed of a message from a dictionary
    """

    fields_count = len(embed.fields)
    index = fields_count + index if index < 0 else index

    embed.set_field_at(
        index,
        name=field_dict.get("name", ""),
        value=field_dict.get("value", ""),
        inline=field_dict.get("inline", True),
    )

    if message is None:
        return embed

    return await message.edit(embed=embed)


async def edit_field_from_dict(message, embed, field_dict, index):
    """
    Edits parts of an embed field of the embed of a message from a
    dictionary
    """

    fields_count = len(embed.fields)
    index = fields_count + index if index < 0 else index
    embed_dict = embed.to_dict()

    old_field_dict = embed_dict["fields"][index]

    for k in field_dict:
        if k in old_field_dict and field_dict[k] != "":
            old_field_dict[k] = field_dict[k]

    embed.set_field_at(
        index,
        name=old_field_dict.get("name", ""),
        value=old_field_dict.get("value", ""),
        inline=old_field_dict.get("inline", True),
    )

    if message is None:
        return embed

    return await message.edit(embed=embed)


async def edit_fields_from_dicts(message, embed: discord.Embed, field_dicts):
    """
    Edits embed fields in the embed of a message from dictionaries
    """

    embed_dict = embed.to_dict()
    old_field_dicts = embed_dict.get("fields", [])
    old_field_dicts_len = len(old_field_dicts)
    field_dicts_len = len(field_dicts)

    for i in range(old_field_dicts_len):
        if i > field_dicts_len - 1:
            break

        old_field_dict = old_field_dicts[i]
        field_dict = field_dicts[i]

        if field_dict:
            for k in field_dict:
                if k in old_field_dict and field_dict[k] != "":
                    old_field_dict[k] = field_dict[k]

            embed.set_field_at(
                i,
                name=old_field_dict.get("name", ""),
                value=old_field_dict.get("value", ""),
                inline=old_field_dict.get("inline", True),
            )
    if message is None:
        return embed

    return await message.edit(embed=embed)


async def add_field_from_dict(message, embed, field_dict):
    """
    Adds an embed field to the embed of a message from a dictionary
    """

    embed.add_field(
        name=field_dict.get("name", ""),
        value=field_dict.get("value", ""),
        inline=field_dict.get("inline", True),
    )
    if message is None:
        return embed

    return await message.edit(embed=embed)


async def add_fields_from_dicts(message, embed: discord.Embed, field_dicts):
    """
    Adds embed fields to the embed of a message from dictionaries
    """

    for field_dict in field_dicts:
        embed.add_field(
            name=field_dict.get("name", ""),
            value=field_dict.get("value", ""),
            inline=field_dict.get("inline", True),
        )
    if message is None:
        return embed

    return await message.edit(embed=embed)


async def insert_field_from_dict(message, embed, field_dict, index):
    """
    Inserts an embed field of the embed of a message from a
    """

    fields_count = len(embed.fields)
    index = fields_count + index if index < 0 else index
    embed.insert_field_at(
        index,
        name=field_dict.get("name", ""),
        value=field_dict.get("value", ""),
        inline=field_dict.get("inline", True),
    )
    if message is None:
        return embed

    return await message.edit(embed=embed)


async def insert_fields_from_dicts(message, embed: discord.Embed, field_dicts, index):
    """
    Inserts embed fields to the embed of a message from dictionaries
    at a specified index
    """
    fields_count = len(embed.fields)
    index = fields_count + index if index < 0 else index
    for field_dict in field_dicts:
        embed.insert_field_at(
            index,
            name=field_dict.get("name", ""),
            value=field_dict.get("value", ""),
            inline=field_dict.get("inline", True),
        )
    if message is None:
        return embed

    return await message.edit(embed=embed)


async def remove_field(message, embed, index):
    """
    Removes an embed field of the embed of a message from a dictionary
    """

    fields_count = len(embed.fields)
    index = fields_count + index if index < 0 else index
    embed.remove_field(index)
    if message is None:
        return embed

    return await message.edit(embed=embed)


async def remove_fields(message, embed, field_indices):
    """
    Removes multiple embed fields of the embed of a message from a
    dictionary
    """

    fields_count = len(embed.fields)

    parsed_field_indices = [
        fields_count + idx if idx < 0 else idx for idx in field_indices
    ]

    parsed_field_indices.sort(reverse=True)

    for index in parsed_field_indices:
        embed.remove_field(index)
    if message is None:
        return embed

    return await message.edit(embed=embed)


async def swap_fields(message, embed, index_a, index_b):
    """
    Swaps two embed fields of the embed of a message from a
    dictionary
    """

    fields_count = len(embed.fields)
    index_a = fields_count + index_a if index_a < 0 else index_a
    index_b = fields_count + index_b if index_b < 0 else index_b

    embed_dict = embed.to_dict()
    fields_list = embed_dict["fields"]
    fields_list[index_a], fields_list[index_b] = (
        fields_list[index_b],
        fields_list[index_a],
    )
    if message is None:
        return discord.Embed.from_dict(embed_dict)

    return await message.edit(embed=discord.Embed.from_dict(embed_dict))


async def clone_field(message, embed, index):
    """
    Duplicates an embed field of the embed of a message from a
    dictionary
    """
    fields_count = len(embed.fields)
    index = fields_count + index if index < 0 else index

    embed_dict = embed.to_dict()
    cloned_field = embed_dict["fields"][index].copy()
    embed_dict["fields"].insert(index, cloned_field)
    if message is None:
        return embed

    return await message.edit(embed=discord.Embed.from_dict(embed_dict))


async def clone_fields(message, embed, field_indices, insertion_index=None):
    """
    Duplicates multiple embed fields of the embed of a message
    from a dictionary
    """

    fields_count = len(embed.fields)

    parsed_field_indices = [
        fields_count + idx if idx < 0 else idx for idx in field_indices
    ]

    parsed_field_indices.sort(reverse=True)

    insertion_index = (
        fields_count + insertion_index if insertion_index < 0 else insertion_index
    )
    embed_dict = embed.to_dict()

    if isinstance(insertion_index, int):
        cloned_fields = tuple(
            embed_dict["fields"][index].copy()
            for index in sorted(field_indices, reverse=True)
        )
        for cloned_field in cloned_fields:
            embed_dict["fields"].insert(insertion_index, cloned_field)
    else:
        for index in parsed_field_indices:
            cloned_field = embed_dict["fields"][index].copy()
            embed_dict["fields"].insert(index, cloned_field)

    if message is None:
        return embed

    return await message.edit(embed=discord.Embed.from_dict(embed_dict))


async def clear_fields(message, embed):
    """
    Removes all embed fields of the embed of a message from a
    dictionary
    """
    embed.clear_fields()
    if message is None:
        return embed
    return await message.edit(embed=embed)


def import_embed_data(
    source: Union[str, io.StringIO],
    from_string=False,
    from_json=False,
    from_json_string=False,
    as_string=False,
    as_dict=True,
):
    """
    Import embed data from a file or a string containing JSON
    or a Python dictionary and return it as a Python dictionary or string.
    """

    if from_json or from_json_string:

        if from_json_string:
            json_data = json.loads(source)

            if not isinstance(json_data, dict) and as_dict:
                raise TypeError(
                    f"The given string must contain a JSON object that"
                    f" can be converted into a Python `dict` object"
                )
            if as_string:
                json_data = json.dumps(json_data)

            return json_data

        else:
            json_data = json.load(source)

            if not isinstance(json_data, dict) and as_dict:
                raise TypeError(
                    f"the file at '{source}' must contain a JSON object that"
                    f" can be converted into a Python `dict` object"
                )
            if as_string:
                json_data = json.dumps(json_data)

            return json_data

    elif from_string:
        try:
            data = literal_eval(source)
        except Exception as e:
            raise TypeError(
                "The contents of the given object must be parsable into literal Python "
                "strings, bytes, numbers, tuples, lists, dicts, sets, booleans, and "
                "None."
            ).with_traceback(e)

        if not isinstance(data, dict) and as_dict:
            raise TypeError(
                f"the file at '{source}' must be of type dict" f", not '{type(data)}'"
            )

        if as_string:
            return repr(data)

        return data

    else:
        data = None
        if isinstance(source, io.StringIO):
            if as_string:
                data = source.getvalue()
            else:
                try:
                    data = literal_eval(source.getvalue())
                except Exception as e:
                    raise TypeError(
                        f", not '{type(data)}'"
                        f"the content of the file at '{source}' must be parsable into a"
                        f"literal Python strings, bytes, numbers, tuples, lists, dicts, sets, booleans, and None."
                    ).with_traceback(e)

                if not isinstance(data, dict) and as_dict:
                    raise TypeError(
                        f"the file at '{source}' must be of type dict"
                        f", not '{type(data)}'"
                    )
        else:
            with open(source, "r", encoding="utf-8") as d:
                if as_string:
                    data = d.read()
                else:
                    try:
                        data = literal_eval(d.read())
                    except Exception as e:
                        raise TypeError(
                            f", not '{type(data)}'"
                            f"the content of the file at '{source}' must be parsable into a"
                            f"literal Python strings, bytes, numbers, tuples, lists, dicts, sets, booleans, and None."
                        ).with_traceback(e)

                    if not isinstance(data, dict) and as_dict:
                        raise TypeError(
                            f"the file at '{source}' must be of type dict"
                            f", not '{type(data)}'"
                        )
        return data


def export_embed_data(
    data: Union[dict, tuple, list],
    fp: Union[str, io.StringIO] = None,
    indent=None,
    as_json=True,
    always_return=False,
):
    """
    Export embed data to serialized JSON or a Python dictionary and store it in a file or a string.
    """

    if as_json:
        return_data = None
        if isinstance(fp, str):
            with open(fp, "w", encoding="utf-8") as fobj:
                json.dump(data, fobj, indent=indent)
            if always_return:
                return_data = json.dumps(data, indent=indent)

        elif isinstance(fp, io.StringIO):
            json.dump(data, fp, indent=indent)
            if always_return:
                return_data = fp.getvalue()
        else:
            return_data = json.dumps(data, indent=indent)

        return return_data

    else:
        return_data = None
        if isinstance(fp, str):
            with open(fp, "w", encoding="utf-8") as fobj:
                if always_return:
                    return_data = black.format_str(
                        repr(data),
                        mode=black.FileMode(),
                    )
                    fobj.write(return_data)
                else:
                    fobj.write(
                        black.format_str(
                            repr(data),
                            mode=black.FileMode(),
                        )
                    )

        elif isinstance(fp, io.StringIO):
            if always_return:
                return_data = black.format_str(
                    repr(data),
                    mode=black.FileMode(),
                )
                fp.write(return_data)
                fp.seek(0)
            else:
                fp.write(
                    black.format_str(
                        repr(data),
                        mode=black.FileMode(),
                    )
                )
                fp.seek(0)
        else:
            return_data = repr(data)

        return return_data


def get_member_info_str(member: Union[discord.Member, discord.User]):
    """
    Get member info in a string, utility function for the embed functions
    """
    datetime_format_str = f"`%a, %d %b %Y`\n> `%H:%M:%S (UTC)  `"
    is_member_obj = isinstance(member, discord.Member)

    member_name_info = f"\u200b\n*Name*: \n> {member.mention} \n> "
    if hasattr(member, "nick") and member.nick:
        member_nick = (
            member.nick.replace("\\", r"\\")
            .replace("*", r"\*")
            .replace("`", r"\`")
            .replace("_", r"\_")
        )
        member_name_info += (
            f"**{member_nick}**\n> (*{member.name}#{member.discriminator}*)\n\n"
        )
    else:
        member_name_info += f"**{member.name}**#{member.discriminator}\n\n"

    member_created_at_fdtime = member.created_at.astimezone(
        tz=datetime.timezone.utc
    ).strftime(datetime_format_str)
    member_created_at_info = (
        f"*Created On*:\n`{member.created_at.isoformat()}`\n"
        + f"> {member_created_at_fdtime}\n\n"
    )

    if is_member_obj and member.joined_at:
        member_joined_at_fdtime = member.joined_at.astimezone(
            tz=datetime.timezone.utc
        ).strftime(datetime_format_str)
        member_joined_at_info = (
            f"*Joined On*:\n`{member.joined_at.isoformat()}`\n"
            + f"> {member_joined_at_fdtime}\n\n"
        )
    else:
        member_joined_at_info = f"*Joined On*: \n> `...`\n\n"

    divider_roles = {} if common.GENERIC else common.ServerConstants.DIVIDER_ROLES

    member_func_role_count = (
        max(
            len(
                tuple(
                    member.roles[i]
                    for i in range(1, len(member.roles))
                    if member.roles[i].id not in divider_roles
                )
            ),
            0,
        )
        if is_member_obj
        else ""
    )

    if is_member_obj and member_func_role_count:
        member_top_role_info = f"*Highest Role*: \n> {member.roles[-1].mention}\n> `<@&{member.roles[-1].id}>`\n\n"
        if member_func_role_count != len(member.roles) - 1:
            member_role_count_info = f"*Role Count*: \n> `{member_func_role_count} ({len(member.roles) - 1})`\n\n"
        else:
            member_role_count_info = f"*Role Count*: \n> `{member_func_role_count}`\n\n"
    else:
        member_top_role_info = member_role_count_info = ""

    member_id_info = f"*Member ID*: \n> <@!`{member.id}`>\n\n"

    if is_member_obj:
        member_stats = (
            f"*Is Pending Screening*: \n> `{member.pending}`\n\n"
            f"*Is Bot Account*: \n> `{member.bot}`\n\n"
            f"*Is System User (Discord Official)*: \n> `{member.system}`\n\n"
        )
    else:
        member_stats = (
            f"*Is Bot Account*: \n> `{member.bot}`\n\n"
            f"*Is System User (Discord Official)*: \n> `{member.system}`\n\n"
        )

    return "".join(
        (
            member_name_info,
            member_created_at_info,
            member_joined_at_info,
            member_top_role_info,
            member_role_count_info,
            member_id_info,
            member_stats,
        )
    )


def get_msg_info_embed(msg: discord.Message, author: bool = True):
    """
    Generate an embed containing info about a message and its author.
    """
    member: Union[discord.Member, discord.User] = msg.author

    datetime_format_str = f"`%a, %d %b %Y`\n> `%H:%M:%S (UTC)  `"
    msg_created_at_fdtime = msg.created_at.astimezone(
        tz=datetime.timezone.utc
    ).strftime(datetime_format_str)

    msg_created_at_info = (
        "\u200b\n"
        if author
        else ""
        + f"*Created On:*\n`{msg.created_at.isoformat()}`\n"
        + f"> {msg_created_at_fdtime}\n\n"
    )

    if msg.edited_at:
        msg_edited_at_fdtime = msg.edited_at.astimezone(
            tz=datetime.timezone.utc
        ).strftime(datetime_format_str)
        msg_edited_at_info = (
            f"*Last Edited On*:\n`{msg.edited_at.isoformat()}`\n"
            + f"> {msg_edited_at_fdtime}\n\n"
        )

    else:
        msg_edited_at_info = f"*Last Edited On*: \n> `...`\n\n"

    msg_id_info = f"*Message ID*: \n> `{msg.id}`\n\n"
    msg_char_count_info = f"*Char. Count*: \n> `{len(msg.content) if isinstance(msg.content, str) else 0}`\n\n"
    msg_attachment_info = (
        f"*Number Of Attachments*: \n> `{len(msg.attachments)} attachment(s)`\n\n"
    )
    msg_embed_info = f"*Number Of Embeds*: \n> `{len(msg.embeds)} embed(s)`\n\n"
    msg_is_pinned = f"*Is Pinned*: \n> `{msg.pinned}`\n\n"

    msg_info = "".join(
        (
            msg_created_at_info,
            msg_edited_at_info,
            msg_char_count_info,
            msg_id_info,
            msg_embed_info,
            msg_attachment_info,
            msg_is_pinned,
        )
    )

    if author:
        return create(
            title="__Message & Author Info__",
            thumbnail_url=str(member.avatar_url),
            description=(
                f"__Text__:\n\n {msg.content}\n\u2800" if msg.content else EmptyEmbed
            ),
            fields=[
                ("__Message Info__", msg_info, True),
                ("__Message Author Info__", get_member_info_str(member), True),
                ("\u2800", f"**[View Original Message]({msg.jump_url})**", False),
            ],
        )

    member_name_info = f"\u200b\n*Name*: \n> {member.mention} \n> "

    if hasattr(member, "nick") and member.nick:
        member_nick = (
            member.nick.replace("\\", r"\\")
            .replace("*", r"\*")
            .replace("`", r"\`")
            .replace("_", r"\_")
        )
        member_name_info += (
            f"**{member_nick}**\n> (*{member.name}#{member.discriminator}*)\n\n"
        )
    else:
        member_name_info += f"**{member.name}**#{member.discriminator}\n\n"

    return create(
        title="__Message Info__",
        author_name=f"{member.name}#{member.discriminator}",
        author_icon_url=str(member.avatar_url),
        description=(
            f"__Text__:\n\n {msg.content}\n\u2800" if msg.content else EmptyEmbed
        ),
        fields=[
            (
                "__" + ("Message " if author else "") + "Info__",
                member_name_info + msg_info,
                True,
            ),
            ("\u2800", f"**[View Original Message]({msg.jump_url})**", False),
        ],
    )


def get_member_info_embed(member: Union[discord.Member, discord.User]):
    """
    Generate an embed containing info about a server member.
    """

    return create(
        title="__"
        + ("Member" if isinstance(member, discord.Member) else "User")
        + " Info__",
        description=get_member_info_str(member),
        thumbnail_url=str(member.avatar_url),
    )
