import asyncio
import builtins
import itertools
import json
import math
import os
import pickle
import random
import re
import socket
import string
import sys
import threading
import time
import timeit

import discord
import pkg_resources
import psutil
import pygame
import pygame.gfxdraw
import pygame._sdl2

from sandbox import exec_sandbox
from util import edit_embed, filter_id, format_byte, format_time, safe_subscripting, send_embed, split_long_message, user_clock
from constants import *


# Pet and BONCC command variables
last_pet = time.time() - 3600
pet_anger = 0.1
boncc_rate = 0

doc_modules = {  # Modules to provide documentation for
    "pygame": pygame,
    "discord": discord,
    "asyncio": asyncio,
    "json": json,
    "sys": sys,
    "os": os,
    "socket": socket,
    "random": random,
    "re": re,
    "math": math,
    "pickle": pickle,
    "threading": threading,
    "time": time,
    "timeit": timeit,
    "string": string,
    "itertools": itertools,
    "builtins": builtins,
}

for module in sys.modules:
    doc_modules[module] = sys.modules[module]

pkgs = sorted(
    [i.key for i in pkg_resources.working_set]
)  # pylint: disable=not-an-iterable
process = psutil.Process(os.getpid())

for module in pkgs:
    try:
        doc_modules[module] = __import__(module.replace("-", "_"))
    except BaseException:
        pass


async def admin_command(client: discord.Client, msg: discord.Message, args: list, prefix: str):
    if safe_subscripting(args, 0) == "eval" and len(args) > 1:
        try:
            script = compile(
                msg.content[len(prefix) + 5 :], "<string>", "eval"
            )  # compile script first

            script_start = time.perf_counter()
            eval_output = eval(script)  # pylint: disable = eval-used
            script_duration = time.perf_counter() - script_start

            enhanced_eval_output = repr(eval_output).replace(
                "```", "\u200e`\u200e`\u200e`\u200e"
            )

            if len(enhanced_eval_output) + 11 > 2048:
                await send_embed(
                    msg.channel,
                    f"Return output (code executed in {format_time(script_duration)}):",
                    "```\n" + enhanced_eval_output[:2037] + " ...```",
                )
            else:
                await send_embed(
                    msg.channel,
                    f"Return output (code executed in {format_time(script_duration)}):",
                    "```\n" + enhanced_eval_output + "```",
                )

        except Exception as ex:
            exp = (
                type(ex).__name__.replace("```", "\u200e`\u200e`\u200e`\u200e")
                + ": "
                + ", ".join([str(t) for t in ex.args]).replace(
                    "```", "\u200e`\u200e`\u200e`\u200e"
                )
            )

            if len(exp) + 11 > 2048:
                await send_embed(
                    msg.channel,
                    "An exception occured!",
                    "```\n" + exp[:2037] + " ...```",
                )
            else:
                await send_embed(
                    msg.channel, "An exception occured!", "```\n" + exp + "```"
                )

    elif safe_subscripting(args, 0) == "sudo" and len(args) > 1:
        try:
            await msg.channel.send(msg.content[len(prefix) + 5 :])
            await msg.delete()
        except Exception as ex:
            exp = (
                    type(ex).__name__.replace("```", "\u200e`\u200e`\u200e`\u200e")
                    + ": "
                    + ", ".join([str(t) for t in ex.args]).replace(
                "```", "\u200e`\u200e`\u200e`\u200e"
            )
            )
            await send_embed(msg.channel, 'An exception occurred whilst trying to execute command!', f'```\n{exp}```')

    elif safe_subscripting(args, 0) == "sudo-edit" and len(args) > 2:
        try:
            edit_msg = await msg.channel.fetch_message(int(filter_id(args[1])))
            await edit_msg.edit(content=msg.content[msg.content.find(args[2]):])
            await msg.delete()
        except Exception as ex:
            exp = (
                    type(ex).__name__.replace("```", "\u200e`\u200e`\u200e`\u200e")
                    + ": "
                    + ", ".join([str(t) for t in ex.args]).replace(
                "```", "\u200e`\u200e`\u200e`\u200e"
            )
            )
            await send_embed(msg.channel, 'An exception occurred whilst trying to execute command!', f'```\n{exp}```')

    elif safe_subscripting(args, 0) == "emsudo" and len(args) > 1:
        try:
            argss = eval(msg.content[len(prefix) + 7:])

            if len(argss) == 2:
                await send_embed(msg.channel, argss[0], argss[1])
            elif len(argss) == 3:
                await send_embed(msg.channel, argss[1], argss[2], argss[0])
            elif len(argss) == 4:
                await send_embed(msg.channel, argss[1], argss[2], argss[0], argss[3])

            await msg.delete()
        except Exception as ex:
            exp = (
                    type(ex).__name__.replace("```", "\u200e`\u200e`\u200e`\u200e")
                    + ": "
                    + ", ".join([str(t) for t in ex.args]).replace(
                    "```", "\u200e`\u200e`\u200e`\u200e"
            )
            )
            await send_embed(msg.channel, 'An exception occurred whilst trying to execute command!', f'```\n{exp}```')

    elif safe_subscripting(args, 0) == "emsudo-edit" and len(args) > 1:
        try:
            argss = eval(msg.content[len(prefix) + 12:])
            edit_msg = await msg.channel.fetch_message(argss[0])

            if len(argss) == 3:
                await edit_embed(edit_msg, argss[1], argss[2])
            elif len(argss) == 4:
                await edit_embed(edit_msg, argss[2], argss[3], argss[1])
            elif len(argss) > 4:
                await edit_embed(edit_msg, argss[2], argss[3], argss[1], argss[4])

            await msg.delete()
        except Exception as ex:
            exp = (
                    type(ex).__name__.replace("```", "\u200e`\u200e`\u200e`\u200e")
                    + ": "
                    + ", ".join([str(t) for t in ex.args]).replace(
                    "```", "\u200e`\u200e`\u200e`\u200e"
            )
            )
            await send_embed(msg.channel, 'An exception occurred whilst trying to execute command!', f'```\n{exp}```')

    elif safe_subscripting(args, 0) == "archive" and len(args) == 4:
        try:
            origin_channel_id = int(filter_id(args[1]))
            quantity = int(args[2])
            destination_channel_id = int(filter_id(args[3]))

            origin_channel = None
            destination_channel = None

            for channel in client.get_all_channels():
                if channel.id == origin_channel_id:
                    origin_channel = channel
                if channel.id == destination_channel_id:
                    destination_channel = channel

            if not origin_channel:
                await send_embed(msg.channel, 'Cannot execute command', 'Invalid origin channel!')
                return
            elif not destination_channel:
                await send_embed(msg.channel, 'Cannot execute command', 'Invalid destination channel!')
                return

            messages = await origin_channel.history(limit=quantity).flatten()
            messages.reverse()

            message_list = []
            for message in messages:
                triple_block_quote = '```'
                escaped_code_block_quote = '\u200e`\u200e`\u200e`\u200e'
                newline = '\n'
                message_list.append(
                    f"**AUTHOR**: {message.author} ({message.author.mention}) [{message.author.id}]\n" +
                    (f"**MESSAGE**: \n> {f'{newline}> '.join(message.content.split(newline))}\n" if message.content else "") +
                    (f"**ATTACHMENT(S)**: \n> {f'{newline}> '.join(newline.join([f'{i+1}:{newline}    **Name**: {repr(attachment.filename)}{newline}    **URL**: {attachment.url}' for i, attachment in enumerate(message.attachments)]).split(newline))}\n" if message.attachments else "") +
                    (f"**EMBED(S)**: \n> {f'{newline}> '.join(newline.join([(f'{i+1}:{newline}    **Title**: {embed.title}{newline}    **Description**: ```{newline}{(embed.description if isinstance(embed.description, str) else newline).replace(triple_block_quote, escaped_code_block_quote)}```{newline}    **Image URL**: {embed.image.url}' if isinstance(embed, discord.Embed) else newline) for i, embed in enumerate(message.embeds)]).split(newline))}\n" if message.embeds else "")
                )
                asyncio.sleep(0.01) # Lets the bot do other things

            archive_str = f"+{'='*40}+\n" + f"+{'='*40}+\n".join(message_list) + f"+{'='*40}+\n"
            archive_list = split_long_message(archive_str)

            for message in archive_list:
                await destination_channel.send(message)
        except Exception as ex:
            exp = (
                type(ex).__name__.replace("```", "\u200e`\u200e`\u200e`\u200e")
                + ": "
                + ", ".join([str(t) for t in ex.args]).replace(
                "```", "\u200e`\u200e`\u200e`\u200e"
            )
            )
            await send_embed(msg.channel, 'An exception occurred whilst trying to execute command!', f'```\n{exp}```')

    elif safe_subscripting(args, 0) == "heap" and len(args) == 1:
        mem = process.memory_info().rss
        await send_embed(
            msg.channel, "Total memory used:", f"**{format_byte(mem, 4)}**\n({mem} B)"
        )

    elif safe_subscripting(args, 0) == "stop" and len(args) == 1:
        await send_embed(
            msg.channel,
            "Stopping bot...",
            "Change da world,\nMy final message,\nGoodbye.",
        )
        sys.exit(0)

    else:
        await user_command(client, msg, args, prefix, True, True)


async def user_command(
    client: discord.Client, msg: discord.Message, args: list, prefix: str, is_priv=False, is_admin=False
):
    # TODO: Check possible removal of globals
    global last_pet, pet_anger

    if safe_subscripting(args, 0) == "doc" and len(args) == 2:
        splits = args[1].split(".")

        if safe_subscripting(splits, 0) not in doc_modules:
            await send_embed(
                msg.channel,
                "Unknown module!",
                "No such module is available for its documentation.",
            )
            return
        objects = doc_modules
        obj = None

        for part in splits:
            try:
                obj = objects[part]
                try:
                    objects = vars(obj)
                except BaseException:  # TODO: Figure out proper exception
                    objects = {}
            except KeyError:
                await send_embed(
                    msg.channel,
                    "Class/function/sub-module not found!",
                    f"There's no such thing here named `{args[1]}`",
                )
                return
        messg = str(obj.__doc__).replace("```", "\u200e`\u200e`\u200e`\u200e")

        if len(messg) + 11 > 2048:
            await send_embed(
                msg.channel,
                f"Documentation for {args[1]}",
                "```\n" + messg[:2037] + " ...```",
            )
            return

        messg = "```\n" + messg + "```\n\n"

        if safe_subscripting(splits, 0) == "pygame":
            doclink = "https://www.pygame.org/docs"
            if len(splits) > 1:
                doclink += "/ref/" + safe_subscripting(splits, 1).lower() + ".html"
                doclink += "#"
                doclink += "".join([s + "." for s in splits])[:-1]
            messg = "Online documentation: " + doclink + "\n" + messg

        for obj in objects:
            if obj.startswith("__"):
                continue
            if type(objects[obj]).__name__ not in (
                "module",
                "type",
                "function",
                "method_descriptor",
                "builtin_function_or_method",
            ):
                continue
            messg += "**" + type(objects[obj]).__name__.upper() + "** `" + obj + "`\n"

        if len(messg) > 2048:
            await send_embed(
                msg.channel, f"Documentation for {args[1]}", messg[:2044] + " ..."
            )
        else:
            await send_embed(msg.channel, f"Documentation for {args[1]}", messg)

    elif safe_subscripting(args, 0) == "exec" and len(args) > 1:
        code = msg.content[len(prefix) + 5 :]
        ret = ""

        # Filters code block
        for i in range(len(code)):
            if code[i] in [" ", "`", "\n"]:
                ret = code[i + 1:]
            else:
                break
        code = ret

        for i in reversed(range(len(code))):
            if code[i] in [" ", "`", "\n"]:
                ret = code[:i]
            else:
                break

        if ret.startswith("py\n"):
            ret = ret[3:]

        if ret.startswith("python\n"):
            ret = ret[7:]

        start = time.time()
        returned = await exec_sandbox(ret, 5 if is_priv else 2)
        duration = returned.duration  # the execution time of the script alone

        if not isinstance(returned.exc, BaseException):
            if isinstance(returned.img, pygame.Surface):
                pygame.image.save(returned.img, f"temp{start}.png")
                if os.path.getsize(f"temp{start}.png") < 2 ** 22:
                    await msg.channel.send(file=discord.File(f"temp{start}.png"))
                else:
                    await send_embed(
                        msg.channel,
                        "Image cannot be sent",
                        "The image file size is >4MiB",
                    )
                os.remove(f"temp{start}.png")
            str_repr = str(returned.text).replace(
                "```", "\u200e`\u200e`\u200e`\u200e"
            )
            if not str_repr and isinstance(returned.img, pygame.Surface):
                return

            if len(str_repr) + 11 > 2048:
                await send_embed(
                    msg.channel,
                    f"Returned text (code executed in {format_time(duration)}):",
                    "```\n" + str_repr[:2037] + " ...```",
                )
            else:
                await send_embed(
                    msg.channel,
                    f"Returned text (code executed in {format_time(duration)}):",
                    "```\n" + str_repr + "```",
                )

        else:
            exp = (
                type(returned.exc).__name__.replace(
                    "```", "\u200e`\u200e`\u200e`\u200e"
                )
                + ": "
                + ", ".join([str(t) for t in returned.exc.args]).replace(
                    "```", "\u200e`\u200e`\u200e`\u200e"
                )
            )

            if len(exp) + 11 > 2048:
                await send_embed(
                    msg.channel,
                    "An exception occured!",
                    "```\n" + exp[:2037] + " ...```",
                )
            else:
                await send_embed(
                    msg.channel, "An exception occured!", "```\n" + exp + "```"
                )

    elif safe_subscripting(args, 0) == "reskek" and len(args) == 1:
        try:
            emojis = await msg.guild.fetch_emojis()
            for emoji in emojis:
                if emoji.name == "pg_kekw":
                    await emoji.delete()
        except Exception:
            pass

        try:
            with open("save/pg_kekw.png", "rb") as f:
                await msg.guild.create_custom_emoji(name="pg_kekw", image=f.read())
            await send_embed(msg.channel, "Restored pg_kekw :D", "")
        except Exception:
            await send_embed(msg.channel, "Failed to restore pg_kekw :C", "")

    elif safe_subscripting(args, 0) == "pet" and len(args) == 1:
        pet_anger -= (time.time() - last_pet - PET_INTERVAL) * (
            pet_anger / JUMPSCARE_THRESHOLD
        ) - PET_COST

        if pet_anger < PET_COST:
            pet_anger = PET_COST
        last_pet = time.time()

        if pet_anger > JUMPSCARE_THRESHOLD:
            await msg.channel.send(
                "https://raw.githubusercontent.com/AvaxarXapaxa/PygameCommunityBot/main/save/die.gif"
            )
        else:
            await msg.channel.send(
                "https://raw.githubusercontent.com/AvaxarXapaxa/PygameCommunityBot/main/save/pet.gif"
            )

    elif safe_subscripting(args, 0) == "vibecheck" and len(args) == 1:
        await send_embed(
            msg.channel,
            "Vibe Check, snek?",
            f"Previous petting anger: {pet_anger:.2f}/{JUMPSCARE_THRESHOLD:.2f}\nIt was last pet {time.time() - last_pet:.2f} second(s) ago",
        )
    
    elif safe_subscripting(args, 0) == "sorry" and len(args) == 1:
        if random.random() < SORRY_CHANCE:
            await send_embed(
                msg.channel,
                "Ask forgiveness from snek?",
                f"Your pythonic lord accepts your apologize.\nNow go to code again.\nThe bonccrate is {boncc_rate}"
            )
            boncc_rate -= 10
        else:
            await send_embed(
                msg.channel,
                "Ask forgiveness from snek?",
                f"How did you dare to boncc a snake?\nBold of you to assume I would apologize to you, two-feet-standing being!\nThe boncc rate is {boncc_rate}"
            )
    
    elif safe_subscripting(args, 0) == "bonccrate" and len(args) == 1:
        if boncc_rate:
            await send_embed(
                msg.channel,
                "The snek is right",
                "Please, don't hit the snek"
                )
        else:
            await send_embed(
                msg.channel,
                "The snek is hurted and angry:",
                f"The boncc rate is {boncc_rate}"
                )

    elif safe_subscripting(args, 0) == "clock" and len(args) == 1:
        t = time.time()
        image = user_clock(CLOCK_TIMEZONES, t)
        
        pygame.image.save(image, f"temp{t}.png")
        await msg.channel.send(file=discord.File(f"temp{t}.png"))
        os.remove(f"temp{t}.png")

    elif safe_subscripting(args, 0) == "version" and len(args) == 1:
        await send_embed(msg.channel, 'Current bot\'s version', f'`{VERSION}`')
