import sys
import time

import asyncio
import discord

from . import (
    common
)


def format_time(seconds: float, decimal_places: int = 4):
    """
    Formats time with a prefix
    """
    for fractions, unit in [
        (1.0, "s"),
        (1e-03, "ms"),
        (1e-06, "\u03bcs"),
        (1e-09, "ns"),
        (1e-12, "ps"),
        (1e-15, "fs"),
        (1e-18, "as"),
        (1e-21, "zs"),
        (1e-24, "ys"),
    ]:
        if seconds >= fractions:
            return f"{seconds / fractions:.0{decimal_places}f} {unit}"
    return f"very fast"


def format_byte(size: int, decimal_places=3):
    """
    Formats memory size with a prefix
    """
    dec = 10 ** decimal_places

    if size < 1e03:
        return f"{int(size * dec) / dec} B"
    if size < 1e06:
        return f"{int(size * 1e-03 * dec) / dec} KB"
    if size < 1e09:
        return f"{int(size * 1e-06 * dec) / dec} MB"

    return f"{int(size * 1e-09 * dec) / dec} GB"


def split_long_message(message: str):
    """
    Splits message string by 2000 characters with safe newline splitting
    """
    split_output = []
    lines = message.split('\n')
    temp = ""

    for line in lines:
        if len(temp) + len(line) + 1 > 2000:
            split_output.append(temp[:-1])
            temp = line + '\n'
        else:
            temp += line + '\n'

    if temp:
        split_output.append(temp)

    return split_output


def filter_id(mention: str):
    """
    Filters mention to get ID "<@!6969>" to "6969"
    Note that this function can error with ValueError on the int call, so the
    caller of this function must take care of this
    """
    for char in ("<", ">", "@", "&", "#", "!", " "):
        mention = mention.replace(char, "")
    return int(mention)


async def edit_embed(message, title, description, color=0xFFFFAA, url_image=None):
    """
    Edits the embed of a message with a much more tight function
    """
    embed = discord.Embed(title=title, description=description, color=color)
    if url_image:
        embed.set_image(url=url_image)

    return await message.edit(
        embed=embed
    )


async def send_embed(channel, title, description, color=0xFFFFAA, url_image=None):
    """
    Sends an embed with a much more tight function
    """
    embed = discord.Embed(title=title, description=description, color=color)
    if url_image:
        embed.set_image(url=url_image)

    return await channel.send(
        embed=embed
    )


# Ankith26 : TODO - SOMEONE PLEASE REFACTOR THIS FUNCTION I TRIED AND GAVE UP
async def format_archive_messages(messages):
    """
    Formats a message to be archived
    """
    formatted_msgs = []
    for message in messages:
        triple_block_quote = '```'
        newline = '\n'
        formatted_msgs.append(
            f"**AUTHOR**: {message.author} ({message.author.mention}) [{message.author.id}]\n" +
            (f"**MESSAGE**: \n> {f'{newline}> '.join(message.content.split(newline))}\n" if message.content else "") +
            (f"**ATTACHMENT(S)**: \n> {f'{newline}> '.join(newline.join([f'{i+1}:{newline}    **Name**: {repr(attachment.filename)}{newline}    **URL**: {attachment.url}' for i, attachment in enumerate(message.attachments)]).split(newline))}\n" if message.attachments else "") +
            (f"**EMBED(S)**: \n> {f'{newline}> '.join(newline.join([(f'{i+1}:{newline}    **Title**: {embed.title}{newline}    **Description**: ```{newline}{(embed.description if isinstance(embed.description, str) else newline).replace(triple_block_quote, common.ESC_CODE_BLOCK_QUOTE)}```{newline}    **Image URL**: {embed.image.url}' if isinstance(embed, discord.Embed) else newline) for i, embed in enumerate(message.embeds)]).split(newline))}\n" if message.embeds else "")
        )
        await asyncio.sleep(0.01)  # Lets the bot do other things

    return formatted_msgs
