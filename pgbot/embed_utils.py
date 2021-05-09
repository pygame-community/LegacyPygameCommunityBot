import asyncio
import re
import datetime
from collections.abc import Mapping

import discord
from discord.embeds import EmptyEmbed

from . import common


def recursive_update(old_dict, update_dict):
    """
    Update one embed dictionary with another, similar to dict.update(),
    But recursively update dictionary values that are dictionaries as well.
    based on the answers in
    https://stackoverflow.com/questions/3232943/update-value-of-a-nested-dictionary-of-varying-depth
    """
    for k, v in update_dict.items():
        if isinstance(v, Mapping):
            old_dict[k] = recursive_update(old_dict.get(k, {}), v)
        else:
            old_dict[k] = v
    return old_dict


def get_fields(messages):
    """
    Get a list of fields from messages.
    Syntax of embeds: <title|desc|[inline]>

    Args:
        messages (List[str]): The messages to get the fields from

    Returns:
        List[List[str, str, bool]]: The list of fields
    """
    # syntax: <Title|desc.[|inline=False]>
    field_regex = r"(<.*\|.*(\|True|\|False|)>)"
    field_datas = []

    for message in messages:
        field_list = re.split(field_regex, message)
        for field in field_list:
            if field:
                field = field.strip()[1:-1]  # remove < and >
                field_data = field.split("|")

                if len(field_data) not in (2, 3):
                    continue
                elif len(field_data) == 2:
                    field_data.append("")

                field_data[2] = True if field_data[2] == "True" else False

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
            message (discord.Message): The message to overwrite.

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
            "prev":  ("◀️", "Go to the previous page"),
            "stop":  ("⏹️", "Deactivate the buttons"),
            "info":  ("ℹ️", "Show this information page"),
            "next":  ("▶️", "Go to the next page"),
            "last":  ("", ""),
        }

        if len(self.pages) >= 3:
            self.control_emojis["first"] = ("⏪", "Go to the first page")
            self.control_emojis["last"]  = ("⏩", "Go to the last page")


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
        footer = f"Page {page_num+1} of {len(self.pages)}.{newline}"

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
                if role.id in common.ADMIN_ROLES:
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


async def replace(message, title, description, color=0xFFFFAA, url_image=None, fields=[]):
    """
    Edits the embed of a message with a much more tight function
    """
    embed = discord.Embed(title=title, description=description, color=color)
    if url_image:
        embed.set_image(url=url_image)

    for field in fields:
        embed.add_field(name=field[0], value=field[1], inline=field[2])

    return await message.edit(embed=embed)


async def send(channel, title, description, color=0xFFFFAA, url_image=None, fields=[], do_return=False):
    """
    Sends an embed with a much more tight function
    """
    embed = discord.Embed(title=title, description=description, color=color)
    if url_image:
        embed.set_image(url=url_image)

    for field in fields:
        embed.add_field(name=field[0], value=field[1], inline=field[2])

    if do_return:
        return embed

    return await channel.send(embed=embed)

def create(
    embed_type="rich", author_name=EmptyEmbed, author_url=EmptyEmbed, author_icon_url=EmptyEmbed, title=EmptyEmbed, url=EmptyEmbed, thumbnail_url=EmptyEmbed,
    description=EmptyEmbed, image_url=EmptyEmbed, color=0xFFFFAA, fields=[], footer_text=EmptyEmbed, footer_icon_url=EmptyEmbed, timestamp=EmptyEmbed
):
    """
    Creates an embed with a much more tight function.
    """
    embed = discord.Embed(title=title, type=embed_type,
                          url=url, description=description, color=color)

    if timestamp:
        if isinstance(timestamp, str):
            embed.timestamp = datetime.datetime.fromisoformat(timestamp)
        else:
            embed.timestamp = timestamp

    if author_name:
        embed.set_author(name=author_name, url=author_url,
                         icon_url=author_icon_url)

    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)

    if image_url:
        embed.set_image(url=image_url)

    for field in fields:
        if isinstance(field, dict):
            embed.add_field(name=field.get("name", ""), value=field.get("value", ""), inline=field.get("inline", True))
        else:
            embed.add_field(name=field[0], value=field[1], inline=field[2])

    embed.set_footer(text=footer_text, icon_url=footer_icon_url)

    return embed



async def send_2(
    channel, embed_type="rich", author_name=EmptyEmbed, author_url=EmptyEmbed, author_icon_url=EmptyEmbed, title=EmptyEmbed, url=EmptyEmbed, thumbnail_url=EmptyEmbed,
    description=EmptyEmbed, image_url=EmptyEmbed, color=0xFFFFAA, fields=[], footer_text=EmptyEmbed, footer_icon_url=EmptyEmbed, timestamp=EmptyEmbed
):
    """
    Sends an embed with a much more tight function. If the channel is
    None it will return the embed instead of sending it.
    """

    embed = create(
        embed_type=embed_type,
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
        timestamp=timestamp
    )

    if channel is None:
        return embed

    return await channel.send(embed=embed)


async def replace_2(
    message, embed_type="rich", author_name=EmptyEmbed, author_url=EmptyEmbed, author_icon_url=EmptyEmbed, title=EmptyEmbed, url=EmptyEmbed, thumbnail_url=EmptyEmbed,
    description=EmptyEmbed, image_url=EmptyEmbed, color=0xFFFFAA, fields=[], footer_text=EmptyEmbed, footer_icon_url=EmptyEmbed, timestamp=EmptyEmbed
):
    """
    Replaces the embed of a message with a much more tight function
    """
    embed = create(
        embed_type=embed_type,
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
        timestamp=timestamp
    )

    return await message.edit(embed=embed)


async def edit_2(
    message, embed, embed_type="rich", author_name=EmptyEmbed, author_url=EmptyEmbed, author_icon_url=EmptyEmbed, title=EmptyEmbed, url=EmptyEmbed, thumbnail_url=EmptyEmbed,
    description=EmptyEmbed, image_url=EmptyEmbed, color=0xFFFFAA, fields=[], footer_text=EmptyEmbed, footer_icon_url=EmptyEmbed, timestamp=EmptyEmbed
):
    """
    Updates the changed attributes of the embed of a message with a much more tight function
    """
    update_embed = create(
        embed_type=embed_type,
        author_name=author_name,
        author_url=author_url,
        author_icon_url=author_icon_url,
        title=title,
        url=url,
        thumbnail_url=thumbnail_url,
        description=description,
        image_url=image_url,
        color=(color if color >= 0 else EmptyEmbed),
        fields=fields,
        footer_text=footer_text,
        footer_icon_url=footer_icon_url,
        timestamp=timestamp
    )

    old_embed_dict = embed.to_dict()
    update_embed_dict = update_embed.to_dict()

    recursive_update(old_embed_dict, update_embed_dict)

    return await message.edit(embed=discord.Embed.from_dict(old_embed_dict))


async def send_from_dict(channel, data):
    """
    Sends an embed from a dictionary with a much more tight function
    """
    return await channel.send(embed=discord.Embed.from_dict(data))


async def replace_from_dict(message, data):
    """
    Replaces the embed of a message from a dictionary with a much more tight 
    function
    """
    return await message.edit(embed=discord.Embed.from_dict(data))


async def edit_from_dict(message, embed, update_embed_dict):
    """
    Edits the changed attributes of the embed of a message from a dictionary with a much more tight function
    """
    old_embed_dict = embed.to_dict()
    recursive_update(old_embed_dict, update_embed_dict)
    return await message.edit(embed=discord.Embed.from_dict(old_embed_dict))


async def replace_field_from_dict(message, embed, field_dict, index):
    """
    Replaces an embed field of the embed of a message from a dictionary with a much more tight function
    """

    embed.set_field_at(
        index,
        name=field_dict.get("name", ""),
        value=field_dict.get("value", ""),
        inline=field_dict.get("inline", True),
    )

    return await message.edit(embed=embed)


async def edit_field_from_dict(message, embed, field_dict, index):
    """
    Edits parts of an embed field of the embed of a message from a dictionary with a much more tight function
    """

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

    return await message.edit(embed=embed)


async def edit_fields_from_dicts(message, embed: discord.Embed, field_dicts):
    """
    Edits embed fields in the embed of a message from dictionaries with a much more tight function
    """

    embed_dict = embed.to_dict()
    old_field_dicts = embed_dict.get("fields", [])
    old_field_dicts_len = len(old_field_dicts)
    field_dicts_len = len(field_dicts)

    for i in range(old_field_dicts_len):
        if i > field_dicts_len-1:
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

    return await message.edit(embed=embed)


async def add_field_from_dict(message, embed, field_dict):
    """
    Adds an embed field to the embed of a message from a dictionary with a much more tight function
    """

    embed.add_field(
        name=field_dict.get("name", ""),
        value=field_dict.get("value", ""),
        inline=field_dict.get("inline", True),
    )

    return await message.edit(embed=embed)


async def add_fields_from_dicts(message, embed: discord.Embed, field_dicts):
    """
    Adds embed fields to the embed of a message from dictionaries with a much more tight function
    """

    for field_dict in field_dicts:
        embed.add_field(
            name=field_dict.get("name", ""),
            value=field_dict.get("value", ""),
            inline=field_dict.get("inline", True),
        )

    return await message.edit(embed=embed)


async def insert_field_from_dict(message, embed, field_dict, index):
    """
    Inserts an embed field of the embed of a message from a dictionary with a much more tight function
    """

    embed.insert_field_at(
        index,
        name=field_dict.get("name", ""),
        value=field_dict.get("value", ""),
        inline=field_dict.get("inline", True),
    )

    return await message.edit(embed=embed)


async def insert_fields_from_dicts(message, embed: discord.Embed, field_dicts, index):
    """
    Inserts embed fields to the embed of a message from dictionaries at a specified index with a much more tight function
    """

    for field_dict in field_dicts:
        embed.insert_field_at(
        index,
        name=field_dict.get("name", ""),
        value=field_dict.get("value", ""),
        inline=field_dict.get("inline", True),
        )

    return await message.edit(embed=embed)


async def remove_field(message, embed, index):
    """
    Removes an embed field of the embed of a message from a dictionary with a much more tight function
    """
    embed.remove_field(index)
    return await message.edit(embed=embed)


async def remove_fields(message, embed, field_indices):
    """
    Removes multiple embed fields of the embed of a message from a dictionary with a much more tight function
    """
    for index in sorted(field_indices, reverse=True):
        embed.remove_field(index)
    return await message.edit(embed=embed)


async def swap_fields(message, embed, index_a, index_b):
    """
    Swaps two embed fields of the embed of a message from a dictionary with a much more tight function
    """
    embed_dict = embed.to_dict()
    fields_list = embed_dict["fields"]
    fields_list[index_a], fields_list[index_b] = fields_list[index_b], fields_list[index_a]
    return await message.edit(embed=discord.Embed.from_dict(embed_dict))


async def clone_field(message, embed, index):
    """
    Duplicates an embed field of the embed of a message from a dictionary with a much more tight function
    """
    embed_dict = embed.to_dict()
    cloned_field = embed_dict["fields"][index].copy()
    embed_dict["fields"].insert(index, cloned_field)
    return await message.edit(embed=discord.Embed.from_dict(embed_dict))


async def clone_fields(message, embed, field_indices, insertion_index=None):
    """
    Duplicates multiple embed fields of the embed of a message from a dictionary with a much more tight function
    """
    embed_dict = embed.to_dict()

    if isinstance(insertion_index, int):
        cloned_fields = tuple(embed_dict["fields"][index].copy() for index in sorted(field_indices, reverse=True))
        for cloned_field in cloned_fields:
            embed_dict["fields"].insert(insertion_index, cloned_field)
    else:
        for index in sorted(field_indices, reverse=True):
            cloned_field = embed_dict["fields"][index].copy()
            embed_dict["fields"].insert(index, cloned_field)

    return await message.edit(embed=discord.Embed.from_dict(embed_dict))


async def clear_fields(message, embed):
    """
    Removes all embed fields of the embed of a message from a dictionary with a much more tight function
    """
    embed.clear_fields()
    return await message.edit(embed=embed)


def get_msg_info_embed(msg: discord.Message, author: bool = True):
    """
    Generate an embed containing info about a message and its author.
    """
    msg_link = f"https://discord.com/channels/{msg.guild.id}/{msg.channel.id}/{msg.id}"

    member = msg.author
    datetime_format_str = f"`%a. %b %d, %Y`\n> `%I:%M:%S %p (UTC)`"
    msg_created_at_fdtime = msg.created_at.replace(tzinfo=datetime.timezone.utc).strftime(datetime_format_str)

    msg_created_at_info = f"*Created On*: \n> {msg_created_at_fdtime}\n\n"
    
    if msg.edited_at:
        msg_edited_at_fdtime = msg.edited_at.replace(tzinfo=datetime.timezone.utc).strftime(datetime_format_str)
        msg_edited_at_info = f"*Last Edited On*: \n> {msg_edited_at_fdtime}\n\n"
    else:
        msg_edited_at_info = f"*Last Edited On*: \n> `...`\n\n"

    msg_id_info = f"*Message ID*: \n> `{msg.id}`\n\n"
    msg_char_count_info = f"*Char. Count*: \n> `{len(msg.content) if isinstance(msg.content, str) else 0}`\n\n"

    if author:
        member_name_info = "*Name*: \n> "+(
            f"**{member.nick}**\n> (*{member.name}#{member.discriminator}*)\n\n"\
            if member.nick else f"**{member.name}**#{member.discriminator}\n\n"
            )

        member_created_at_fdtime = member.created_at.replace(tzinfo=datetime.timezone.utc).strftime(datetime_format_str)
        member_created_at_info = f"*Created On*: \n> {member_created_at_fdtime}\n\n"
        
        member_joined_at_fdtime = member.joined_at.replace(tzinfo=datetime.timezone.utc).strftime(datetime_format_str)
        member_joined_at_info = f"*Joined On*: \n> {member_joined_at_fdtime}\n\n"

        
        member_func_role_count = max(
            len(tuple(member.roles[i] for i in range(1, len(member.roles))\
                if member.roles[i].id not in common.DIVIDER_ROLES
                )),
            0)

        if member_func_role_count:
            member_top_role_info = f"*Highest Role*: \n> {member.roles[-1].mention}\n> `<@&{member.roles[-1].id}>`\n\n"
            if member_func_role_count != len(member.roles) - 1:
                member_role_count_info =  f"*Role Count*: \n> `{member_func_role_count} ({len(member.roles)-1})`\n\n"
            else:
                member_role_count_info =  f"*Role Count*: \n> `{member_func_role_count}`\n\n"
        else:
            member_top_role_info = member_role_count_info = ""
        
        member_id_info = f"*Author ID*: \n> <@!`{member.id}`>\n\n"

        msg_info = f"{msg_created_at_info}{msg_edited_at_info}{msg_char_count_info}{msg_id_info}"
        member_info = f"{member_name_info}{member_created_at_info}{member_joined_at_info}{member_top_role_info}"+\
                        f"{member_role_count_info}{member_id_info}"

        return create(
            title="__Message & Author Stats__",
            thumbnail_url=str(member.avatar_url),
            description=(f"__Text__:\n\n {msg.content}\n\u2800" if msg.content else discord.embeds.EmptyEmbed),
            fields=(
                (
                    "__Message Info__",
                    msg_info,
                    True
                ),
                (
                    "__Message Author Info__",
                    member_info,
                    True
                ),
                (
                    "\u2800",
                    f"**[View Original Message]({msg_link})**",
                    False
                ),
            ),
        )
    else:
        return create(
            title="__Message Stats__",
            thumbnail_url=str(member.avatar_url),
            description=(f"__Text__:\n\n {msg.content}\n\u2800" if msg.content else discord.embeds.EmptyEmbed),
            fields=(
                (
                    "__Message Info__",
                    msg_info,
                    True
                ),
                (
                    "\u2800",
                    f"**[View Original Message]({msg_link})**",
                    False
                ),
            ),
        )


def get_user_info_embed(member: discord.Member):
    """
    Generate an embed containing info about a server member.
    """
    datetime_format_str = f"`%a. %b %d, %Y`\n> `%I:%M:%S %p (UTC)`"

    member_name_info = "*Name*: \n> "+(
        f"**{member.nick}**\n> (*{member.name}#{member.discriminator}*)\n\n"\
        if member.nick else f"**{member.name}**#{member.discriminator}\n\n"
        )

    member_created_at_fdtime = member.created_at.replace(tzinfo=datetime.timezone.utc).strftime(datetime_format_str)
    member_created_at_info = f"*Created On*: \n> {member_created_at_fdtime}\n\n"
    
    member_joined_at_fdtime = member.joined_at.replace(tzinfo=datetime.timezone.utc).strftime(datetime_format_str)
    member_joined_at_info = f"*Joined On*: \n> {member_joined_at_fdtime}\n\n"

    
    member_func_role_count = max(
        len(tuple(member.roles[i] for i in range(1, len(member.roles))\
            if member.roles[i].id not in common.DIVIDER_ROLES
            )),
        0)

    if member_func_role_count:
        member_top_role_info = f"*Highest Role*: \n> {member.roles[-1].mention}\n> `<@&{member.roles[-1].id}>`\n\n"
        if member_func_role_count != len(member.roles) - 1:
            member_role_count_info =  f"*Role Count*: \n> `{member_func_role_count} ({len(member.roles)-1})`\n\n"
        else:
            member_role_count_info =  f"*Role Count*: \n> `{member_func_role_count}`\n\n"
    else:
        member_top_role_info = member_role_count_info = ""
    
    member_id_info = f"*Member ID*: \n> <@!`{member.id}`>\n\n"

    member_info = f"{member_name_info}{member_created_at_info}{member_joined_at_info}{member_top_role_info}"+\
                    f"{member_role_count_info}{member_id_info}"

    return create(
        title="__Member Info__",
        description=member_info,
        thumbnail_url=str(member.avatar_url)
    )
