"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present pygame-community

This file defines some rich embed generation functions.
"""

from __future__ import annotations


from typing import Union

import discord
import snakecore

from pgbot import common


def get_member_info_str(member: Union[discord.Member, discord.User]):
    """
    Get member info in a string, utility function for the embed functions
    """
    member_name_info = f"\u200b\n*Name*: \n> {member.mention} \n> "
    if hasattr(member, "nick") and member.display_name:
        member_nick = (
            member.display_name.replace("\\", r"\\")
            .replace("*", r"\*")
            .replace("`", r"\`")
            .replace("_", r"\_")
        )
        member_name_info += (
            f"**{member_nick}**\n> (*{member.name}#{member.discriminator}*)\n\n"
        )
    else:
        member_name_info += f"**{member.name}**#{member.discriminator}\n\n"

    member_created_at_info = f"*Created On*:\n> {snakecore.utils.create_markdown_timestamp(member.created_at)}\n\n"

    if isinstance(member, discord.Member) and member.joined_at:
        member_joined_at_info = f"*Joined On*:\n> {snakecore.utils.create_markdown_timestamp(member.joined_at)}\n\n"
    else:
        member_joined_at_info = "*Joined On*: \n> `...`\n\n"

    divider_roles = {} if common.GENERIC else common.GuildConstants.DIVIDER_ROLES

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
        if isinstance(member, discord.Member)
        else ""
    )

    if isinstance(member, discord.Member) and member_func_role_count:
        member_top_role_info = f"*Highest Role*: \n> {member.roles[-1].mention}\n> `<@&{member.roles[-1].id}>`\n\n"
        if member_func_role_count != len(member.roles) - 1:
            member_role_count_info = f"*Role Count*: \n> `{member_func_role_count} ({len(member.roles) - 1})`\n\n"
        else:
            member_role_count_info = f"*Role Count*: \n> `{member_func_role_count}`\n\n"
    else:
        member_top_role_info = member_role_count_info = ""

    member_id_info = f"*Member ID*: \n> <@!`{member.id}`>\n\n"

    if isinstance(member, discord.Member):
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

    msg_created_at_info = f"*Created On:*\n> {snakecore.utils.create_markdown_timestamp(msg.created_at)}\n\n"

    if msg.edited_at:
        msg_edited_at_info = f"*Last Edited On*: \n> {snakecore.utils.create_markdown_timestamp(msg.edited_at)}\n\n"

    else:
        msg_edited_at_info = "*Last Edited On*: \n> `...`\n\n"

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
        return snakecore.utils.embeds.create_embed(
            title="__Message & Author Info__",
            description="\n".join(
                (
                    "__Text"
                    + (" (Shortened)" if len(msg.content) > 2000 else "")
                    + "__:",
                    f"\n {msg.content[:2001]}" + "\n\n[...]"
                    if len(msg.content) > 2000
                    else msg.content,
                    "\u200b",
                )
            ),
            color=common.DEFAULT_EMBED_COLOR,
            thumbnail_url=member.display_avatar.url,
            fields=[
                dict(name="__Message Info__", value=msg_info, inline=True),
                dict(
                    name="__Message Author Info__",
                    value=get_member_info_str(member),
                    inline=True,
                ),
                dict(
                    name="\u200b",
                    value=f"**[View Original Message]({msg.jump_url})**",
                    inline=False,
                ),
            ],
        )

    member_name_info = f"\u200b\n*Name*: \n> {member.mention} \n> "

    if isinstance(member, discord.Member) and member.nick:
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

    return snakecore.utils.embeds.create_embed(
        title="__Message Info__",
        author_name=f"{member.name}#{member.discriminator}",
        author_icon_url=member.display_avatar.url,
        description="\n".join(
            (
                "__Text" + (" (Shortened)" if len(msg.content) > 2000 else "") + "__:",
                f"\n {msg.content[:2001]}" + "\n[...]"
                if len(msg.content) > 2000
                else msg.content,
                "\u200b",
            )
        ),
        color=common.DEFAULT_EMBED_COLOR,
        fields=[
            dict(
                name="__" + ("Message " if author else "") + "Info__",
                value=member_name_info + msg_info,
                inline=True,
            ),
            dict(
                name="\u200b",
                value=f"**[View Original Message]({msg.jump_url})**",
                inline=False,
            ),
        ],
    )


def get_member_info_embed(member: Union[discord.Member, discord.User]):
    """
    Generate an embed containing info about a server member.
    """

    return snakecore.utils.embeds.create_embed(
        title="__"
        + ("Member" if isinstance(member, discord.Member) else "User")
        + " Info__",
        thumbnail_url=member.display_avatar.url,
        description=get_member_info_str(member),
        color=common.DEFAULT_EMBED_COLOR,
    )
