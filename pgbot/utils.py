"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file defines some important utility functions.
"""

from __future__ import annotations

import asyncio
import datetime
import os
import platform
import re
import sys
import traceback
import typing

import discord
import pygame

from . import common, embed_utils

# regex for doc string
regex = re.compile(
    # If you add a new "section" to this regex dont forget the "|" at the end
    # Does not have to be in the same order in the docs as in here.
    r"(->type|"
    r"->signature|"
    r"->description|"
    r"->example command|"
    r"->extended description\n|"
    r"\Z)|(((?!->).|\n)*)"
)


def clamp(value, min_, max_):
    """
    Returns the value clamped between a maximum and a minumum
    """
    return max(min(value, max_), min_)


def color_to_rgb_int(col: pygame.Color):
    """
    Get integer RGB representation of pygame color object. This does not include
    the alpha component of the color, which int(col) would give you
    """
    return (((col.r << 8) + col.g) << 8) + col.b


def discordify(text: str):
    """
    Converts normal string into "discord" string that includes backspaces to
    cancel out unwanted changes
    """
    return discord.utils.escape_markdown(text)


def format_discord_link(link: str, guild_id: int):
    """
    Format a discord link to a channel or message
    """
    link = link.lstrip("<").rstrip(">").rstrip("/")

    for prefix in (
        f"https://discord.com/channels/{guild_id}/",
        f"https://www.discord.com/channels/{guild_id}/",
    ):
        if link.startswith(prefix):
            link = link[len(prefix) :]

    return link


def progress_bar(pct, full_bar: str = "█", empty_bar: str = "░", divisions: int = 10):
    """
    A simple horizontal progress bar generator.
    """
    pct = 0 if pct < 0 else 1 if pct > 1 else pct
    return full_bar * (int(divisions * pct)) + empty_bar * (
        divisions - int(divisions * pct)
    )


def format_time(
    seconds: float,
    decimal_places: int = 4,
    unit_data=(
        (1.0, "s"),
        (1e-03, "ms"),
        (1e-06, "\u03bcs"),
        (1e-09, "ns"),
        (1e-12, "ps"),
        (1e-15, "fs"),
        (1e-18, "as"),
        (1e-21, "zs"),
        (1e-24, "ys"),
    ),
):
    """
    Formats time with a prefix
    """
    for fractions, unit in unit_data:
        if seconds >= fractions:
            return f"{seconds / fractions:.0{decimal_places}f} {unit}"
    return f"very fast"


def format_long_time(seconds: int):
    """
    Formats time into string, which is of the order of a few days
    """
    result = []

    for name, count in (
        ("weeks", 604800),
        ("days", 86400),
        ("hours", 3600),
        ("minutes", 60),
        ("seconds", 1),
    ):
        value = seconds // count
        if value or (not result and count == 1):
            seconds -= value * count
            if value == 1:
                name = name[:-1]
            result.append(f"{value} {name}")

    preset = ", ".join(result[:-1])
    if preset:
        return f"{preset} and {result[-1]}"
    return result[-1]


def format_timedelta(tdelta: datetime.timedelta):
    """
    Formats timedelta object into human readable time
    """
    return format_long_time(int(tdelta.total_seconds()))


def format_byte(size: int, decimal_places=3):
    """
    Formats a given size and outputs a string equivalent to B, KB, MB, or GB
    """
    if size < 1e03:
        return f"{round(size, decimal_places)} B"
    if size < 1e06:
        return f"{round(size / 1e3, decimal_places)} KB"
    if size < 1e09:
        return f"{round(size / 1e6, decimal_places)} MB"

    return f"{round(size / 1e9, decimal_places)} GB"


def split_long_message(message: str):
    """
    Splits message string by 2000 characters with safe newline splitting
    """
    split_output = []
    lines = message.split("\n")
    temp = ""

    for line in lines:
        if len(temp) + len(line) + 1 > 2000:
            split_output.append(temp[:-1])
            temp = line + "\n"
        else:
            temp += line + "\n"

    if temp:
        split_output.append(temp)

    return split_output


def format_code_exception(e, pops: int = 1):
    """
    Provide a formatted exception for code snippets
    """
    tbs = traceback.format_exception(type(e), e, e.__traceback__)
    # Pop out the first entry in the traceback, because that's
    # this function call itself
    for _ in range(pops):
        tbs.pop(1)

    ret = "".join(tbs).replace(os.getcwd(), "PgBot")
    if platform.system() == "Windows":
        # Hide path to python on windows
        ret = ret.replace(os.path.dirname(sys.executable), "Python")

    return ret


def filter_id(mention: str):
    """
    Filters mention to get ID "<@!6969>" to "6969"
    Note that this function can error with ValueError on the int call, so the
    caller of this function must take care of that.
    """
    for char in ("<", ">", "@", "&", "#", "!", " "):
        mention = mention.replace(char, "")

    return int(mention)


def filter_emoji_id(name: str):
    """
    Filter emoji name to get "837402289709907978" from
    "<:pg_think:837402289709907978>"
    Note that this function can error with ValueError on the int call, in which
    case it returns the input string (no exception is raised)

    Args:
        name (str): The emoji name

    Returns:
        str|int: The emoji id or the input string if it could not convert it to
        an int.
    """
    if name.count(":") >= 2:
        emoji_id = name.split(":")[-1][:-1]
        return int(emoji_id)

    try:
        return int(name)
    except ValueError:
        return name


def get_doc_from_func(func: typing.Callable):
    """
    Get the type, signature, description and other information from docstrings.

    Args:
        func (typing.Callable): The function to get formatted docs for

    Returns:
        Dict[str] or Dict[]: The type, signature and description of
        the string. An empty dict will be returned if the string begins
        with "->skip" or there was no information found
    """
    string = func.__doc__
    if not string:
        return {}

    string = string.strip()
    if string.startswith("->skip"):
        return {}

    finds = regex.findall(string.split("-----")[0])
    current_key = ""
    data = {}
    if finds:
        for find in finds:
            if find[0].startswith("->"):
                current_key = find[0][2:].strip()
                continue

            if not current_key:
                continue

            # remove useless whitespace
            value = re.sub("  +", "", find[1].strip())
            data[current_key] = value
            current_key = ""

    return data


async def send_help_message(
    original_msg: discord.Message,
    invoker: discord.Member,
    commands: tuple[str, ...],
    cmds_and_funcs: dict[str, typing.Callable],
    groups: dict[str, list],
    page: int = 0,
):
    """
    Edit original_msg to a help message. If command is supplied it will
    only show information about that specific command. Otherwise sends
    the general help embed.

    Args:
        original_msg: The message to edit
        invoker: The member who requested the help command
        commands: A tuple of command names passed by user for help.
        cmds_and_funcs: The name-function pairs to get the docstrings from
        groups: The name-list pairs of group commands
        page: The page of the embed, 0 by default
    """

    fields = {}
    embeds = []

    if not commands:
        functions = {}
        for key, func in cmds_and_funcs.items():
            if hasattr(func, "groupname"):
                key = f"{func.groupname} {' '.join(func.subcmds)}"
            functions[key] = func

        for func in functions.values():
            data = get_doc_from_func(func)
            if not data:
                continue

            if not fields.get(data["type"]):
                fields[data["type"]] = ["", "", True]

            fields[data["type"]][0] += f"{data['signature'][2:]}\n"
            fields[data["type"]][1] += (
                f"`{data['signature']}`\n" f"{data['description']}\n\n"
            )

        fields_cpy = fields.copy()

        for field_name in fields:
            value = fields[field_name]
            value[1] = f"```\n{value[0]}\n```\n\n{value[1]}"
            value[0] = f"__**{field_name}**__"

        fields = fields_cpy

        for field in list(fields.values()):
            body = f"{common.BOT_HELP_PROMPT['body']}\n{field[0]}\n\n{field[1]}"
            embeds.append(
                await embed_utils.send_2(
                    None,
                    title=common.BOT_HELP_PROMPT["title"],
                    description=body,
                    color=common.BOT_HELP_PROMPT["color"],
                )
            )

    elif commands[0] in cmds_and_funcs:
        func_name = commands[0]
        funcs = groups[func_name] if func_name in groups else []
        funcs.insert(0, cmds_and_funcs[func_name])

        for func in funcs:
            if commands[1:] and commands[1:] != getattr(func, "subcmds", None):
                continue

            doc = get_doc_from_func(func)
            if not doc:
                # function found, but does not have help.
                return await embed_utils.replace(
                    original_msg,
                    "Could not get docs",
                    f"Command has no documentation",
                    0xFF0000,
                )

            body = f"`{doc['signature']}`\n`Category: {doc['type']}`\n\n"

            desc = doc["description"]

            ext_desc = doc.get("extended description")
            if ext_desc:
                desc = f"> *{desc}*\n\n{ext_desc}"

            desc_list = desc.split(sep="+===+")

            body += f"**Description:**\n{desc_list[0]}"

            embed_fields = []

            example_cmd = doc.get("example command")
            if example_cmd:
                embed_fields.append(["Example command(s):", example_cmd, True])

            if len(desc_list) == 1:
                embeds.append(
                    embed_utils.create(
                        title=f"Help for `{func_name}`",
                        description=body,
                        color=common.BOT_HELP_PROMPT["color"],
                        fields=embed_fields,
                    )
                )
            else:
                embeds.append(
                    embed_utils.create(
                        title=f"Help for `{func_name}`",
                        description=body,
                        color=common.BOT_HELP_PROMPT["color"],
                    )
                )
                desc_list_len = len(desc_list)
                for i in range(1, len(desc_list)):
                    embeds.append(
                        embed_utils.create(
                            title=f"Help for `{func_name}`",
                            description=desc_list[i],
                            color=common.BOT_HELP_PROMPT["color"],
                            fields=embed_fields if i == desc_list_len - 1 else (),
                        )
                    )

    if not embeds:
        return await embed_utils.replace(
            original_msg,
            "Command not found",
            f"No such command exists",
            0xFF0000,
        )

    await embed_utils.PagedEmbed(original_msg, embeds, invoker, "help", page).mainloop()


def format_entries_message(msg: discord.Message, entry_type: str):
    """
    Formats an entries message to be reposted in discussion channel
    """
    title = f"New {entry_type.lower()} in #{common.ZERO_SPACE}{common.entry_channels[entry_type].name}"

    attachments = ""
    if msg.attachments:
        for i, attachment in enumerate(msg.attachments):
            attachments += f" • [Link {i + 1}]({attachment.url})\n"
    else:
        attachments = "No attachments"

    desc = msg.content if msg.content else "No description provided."

    fields = [
        ["**Posted by**", msg.author.mention, True],
        ["**Original msg.**", f"[View]({msg.jump_url})", True],
        ["**Attachments**", attachments, True],
        ["**Description**", desc, True],
    ]
    return title, fields


def code_block(string: str, max_characters=2048):
    """
    Formats text into discord code blocks
    """
    string = string.replace("```", "\u200b`\u200b`\u200b`\u200b")
    max_characters -= 7

    if len(string) > max_characters:
        return f"```\n{string[:max_characters - 7]} ...```"
    else:
        return f"```\n{string[:max_characters]}```"


def check_channel_permissions(
    member: discord.Member,
    channel: discord.TextChannel,
    bool_func: typing.Callable[[typing.Iterable], bool] = all,
    permissions: typing.Iterable[str] = (
        "view_channel",
        "send_messages",
    ),
) -> bool:

    """
    Checks if the given permissions apply to the given member in the given channel.
    """

    channel_perms = channel.permissions_for(member)
    return bool_func(getattr(channel_perms, perm_name) for perm_name in permissions)


def check_channels_permissions(
    member: discord.Member,
    *channels: discord.TextChannel,
    bool_func: typing.Callable[[typing.Iterable], bool] = all,
    skip_invalid_channels: bool = False,
    permissions: typing.Iterable[str] = (
        "view_channel",
        "send_messages",
    ),
) -> typing.Tuple[bool]:

    """
    Checks if the given permissions apply to the given member in the given channels.
    """

    if skip_invalid_channels:
        booleans = tuple(
            bool_func(getattr(channel_perms, perm_name) for perm_name in permissions)
            for channel_perms in (
                channel.permissions_for(member)
                for channel in channels
                if isinstance(channel, discord.TextChannel)
            )
        )
    else:
        booleans = tuple(
            bool_func(getattr(channel_perms, perm_name) for perm_name in permissions)
            for channel_perms in (
                channel.permissions_for(member) for channel in channels
            )
        )
    return booleans


async def coro_check_channels_permissions(
    member: discord.Member,
    *channels: discord.TextChannel,
    bool_func: typing.Callable[[typing.Iterable], bool] = all,
    skip_invalid_channels: bool = False,
    permissions: typing.Iterable[str] = (
        "view_channel",
        "send_messages",
    ),
) -> typing.List[bool]:

    """
    Checks if the given permissions apply to the given member in the given channels.
    """

    booleans = []
    if skip_invalid_channels:
        for i, channel in channels:
            if isinstance(channel, discord.TextChannel):
                channel_perms = channel.permissions_for(member)
                booleans.append(
                    bool_func(getattr(channel_perms, perm) for perm in permissions)
                )

            if not i % 5:
                await asyncio.sleep(0)
    else:
        for i, channel in channels:
            channel_perms = channel.permissions_for(member)
            booleans.append(
                bool_func(getattr(channel_perms, perm) for perm in permissions)
            )

            if not i % 5:
                await asyncio.sleep(0)

    return booleans
