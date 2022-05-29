"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file defines some utility functions for pg!help command
"""

from __future__ import annotations

import re
import typing

import discord
from discord.ext import commands
import snakecore

from pgbot import common

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
    ctx: commands.Context,
    bot: commands.Bot,
    original_msg: discord.Message,
    invoker: discord.Member,
    qualified_name: typing.Optional[str] = None,
    page: int = 1,
):
    """
    Edit original_msg to a help message. If command is supplied it will
    only show information about that specific command. Otherwise sends
    the general help embed.

    Args:
        original_msg: The message to edit
        invoker: The member who requested the help command
        page: The page of the embed, 0 by default
    """

    doc_fields = {}
    embeds = []

    is_admin = any(
        role.id in common.ServerConstants.ADMIN_ROLES
        for role in getattr(invoker, "roles", ())
    )

    if not qualified_name:
        for cmd in sorted(bot.walk_commands(), key=lambda cmd: cmd.qualified_name):
            if cmd.hidden or not is_admin and cmd.extras.get("admin_only", False):
                continue

            data = get_doc_from_func(cmd.callback)
            if not data:
                continue

            if not doc_fields.get(data["type"]):
                doc_fields[data["type"]] = ["", "", True]

            doc_fields[data["type"]][0] += f"{data['signature'][2:]}\n"
            doc_fields[data["type"]][1] += (
                f"`{data['signature']}`\n" f"{data['description']}\n\n"
            )

        doc_fields_cpy = doc_fields.copy()

        for doc_field_name in doc_fields:
            doc_field_list = doc_fields[doc_field_name]
            doc_field_list[1] = f"```\n{doc_field_list[0]}\n```\n\n{doc_field_list[1]}"
            doc_field_list[0] = f"__**{doc_field_name}**__"

        doc_fields = doc_fields_cpy

        embeds.append(
            discord.Embed(
                title=common.BOT_HELP_PROMPT["title"],
                description=common.BOT_HELP_PROMPT["description"],
                color=common.BOT_HELP_PROMPT["color"],
            )
        )
        for doc_field in list(doc_fields.values()):
            body = f"{doc_field[0]}\n\n{doc_field[1]}"
            embeds.append(
                snakecore.utils.embed_utils.create_embed(
                    title=common.BOT_HELP_PROMPT["title"],
                    description=body,
                    color=common.BOT_HELP_PROMPT["color"],
                )
            )

    else:
        cmd = bot.get_command(qualified_name)
        if (
            cmd is not None
            and not cmd.hidden
            and (is_admin or cmd.extras.get("admin_only", False))
        ):
            cmds = [cmd]
            if isinstance(cmd, commands.Group):
                cmds.extend(
                    sorted(
                        (subcmd for subcmd in cmd.walk_commands()),
                        key=lambda cmd: cmd.qualified_name,
                    )
                )

            for cmd in cmds:
                doc = get_doc_from_func(cmd.callback)
                if not doc:
                    # function found, but does not have help.
                    return await snakecore.utils.embed_utils.replace_embed_at(
                        original_msg,
                        title="Could not get docs",
                        description="Command has no documentation",
                        color=0xFF0000,
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
                    embed_fields.append(
                        dict(name="Example command(s):", value=example_cmd, inline=True)
                    )

                cmd_qualified_name = cmd.qualified_name

                if len(desc_list) == 1:
                    embeds.append(
                        snakecore.utils.embed_utils.create_embed(
                            title=f"Help for `{cmd_qualified_name}`",
                            description=body,
                            color=common.BOT_HELP_PROMPT["color"],
                            fields=embed_fields,
                        )
                    )
                else:
                    embeds.append(
                        snakecore.utils.embed_utils.create_embed(
                            title=f"Help for `{cmd_qualified_name}`",
                            description=body,
                            color=common.BOT_HELP_PROMPT["color"],
                        )
                    )
                    desc_list_len = len(desc_list)
                    for i in range(1, desc_list_len):
                        embeds.append(
                            snakecore.utils.embed_utils.create_embed(
                                title=f"Help for `{cmd_qualified_name}`",
                                description=desc_list[i],
                                color=common.BOT_HELP_PROMPT["color"],
                                fields=embed_fields if i == desc_list_len - 1 else None,
                            )
                        )

    if not embeds:
        return await snakecore.utils.embed_utils.replace_embed_at(
            original_msg,
            title="Command not found",
            description="No such command exists",
            color=0xFF0000,
        )

    footer_text = (
        f"Refresh this by replying with `{common.COMMAND_PREFIX}refresh`.\ncmd: help"
    )

    raw_command_input: str = getattr(ctx, "raw_command_input", "")
    # attribute injected by snakecore's custom parser

    if raw_command_input:
        footer_text += f" | args: {raw_command_input}"

    msg_embeds = [
        snakecore.utils.embed_utils.create_embed(
            color=common.BOT_HELP_PROMPT["color"],
            footer_text=footer_text,
        )
    ]

    original_msg = await original_msg.edit(embeds=msg_embeds)

    try:
        await snakecore.utils.pagination.EmbedPaginator(
            original_msg,
            *embeds,
            caller=invoker,
            whitelisted_role_ids=common.ServerConstants.ADMIN_ROLES,
            start_page_number=page,
            inactivity_timeout=60,
            theme_color=common.BOT_HELP_PROMPT["color"],
        ).mainloop()
    except discord.HTTPException:
        pass
