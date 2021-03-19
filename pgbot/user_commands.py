import os
import random
import time

import discord
import pygame

from . import (
    common,
    clock,
    docs,
    emotion,
    util,
    sandbox
)


EXPORTED_COMMANDS = {}


def export_command(identifier: str, args: int):
    def decorator_handler(func):
        global EXPORTED_COMMANDS
        EXPORTED_COMMANDS[list(EXPORTED_COMMANDS.keys())[-1]]["function"] = func
        return func

    global EXPORTED_COMMANDS
    EXPORTED_COMMANDS[identifier] = {
        "args": args
    }
    return decorator_handler


@export_command("version", 0)
async def version_cmd(invoke_msg: discord.Message, response_msg: discord.Message, args, string):
    await util.edit_embed(response_msg, "Current bot's version", f"`{common.VERSION}`")


@export_command("clock", 0)
async def clock_cmd(invoke_msg: discord.Message, response_msg: discord.Message, args, string):
    t = time.time()
    pygame.image.save(clock.user_clock(t), f"temp{t}.png")
    common.cmd_logs[invoke_msg.id] = await response_msg.channel.send(file=discord.File(f"temp{t}.png"))
    await response_msg.delete()
    os.remove(f"temp{t}.png")


@export_command("doc", 1)
async def docs_cmd(invoke_msg: discord.Message, response_msg: discord.Message, args, string):
    title, body = docs.get(args[0])
    await util.edit_embed(response_msg, title, body)


@export_command("exec", -1)
async def exec_cmd(invoke_msg: discord.Message, response_msg: discord.Message, args, string, _duration=5):
    code = string.lstrip().rstrip().lstrip('`').rstrip('`')
    if code.startswith("python\n"):
        code = code[7:]
    elif code.startswith("py\n"):
        code = code[3:]

    start = time.perf_counter()
    returned = await sandbox.exec_sandbox(code, _duration)
    duration = returned.duration  # the execution time of the script alone

    if not isinstance(returned.exc, BaseException):
        if isinstance(returned.img, pygame.Surface):
            pygame.image.save(returned.img, f"temp{start}.png")
            if os.path.getsize(f"temp{start}.png") < 2 ** 22:
                await response_msg.channel.send(file=discord.File(f"temp{start}.png"))
            else:
                await util.edit_embed(
                    response_msg,
                    "Image cannot be sent:",
                    "The image file size is above 4MiB",
                )
            os.remove(f"temp{start}.png")

        str_repr = str(returned.text).replace(
            "```", common.ESC_CODE_BLOCK_QUOTE
        )

        # if not str_repr and isinstance(returned.img, pygame.Surface):
        #     return

        if len(str_repr) + 11 > 2048:
            await util.edit_embed(
                response_msg,
                f"Returned text (code executed in {util.format_time(duration)}):",
                "```\n" + str_repr[:2037] + " ...```",
            )
        else:
            await util.edit_embed(
                response_msg,
                f"Returned text (code executed in {util.format_time(duration)}):",
                "```\n" + str_repr + "```",
            )

    else:
        exp = (
                type(returned.exc).__name__.replace(
                    "```", common.ESC_CODE_BLOCK_QUOTE
                )
                + ": "
                + ", ".join(str(t) for t in returned.exc.args).replace(
            "```", common.ESC_CODE_BLOCK_QUOTE
        )
        )

        if len(exp) + 11 > 2048:
            await util.edit_embed(
                response_msg,
                common.EXP_TITLES[1],
                "```\n" + exp[:2037] + " ...```",
            )
        else:
            await util.edit_embed(
                response_msg, common.EXP_TITLES[1], "```\n" + exp + "```"
            )


@export_command("help", 0)
async def help_cmd(invoke_msg: discord.Message, response_msg: discord.Message, args, string):
    await util.edit_embed(
        response_msg,
        common.BOT_HELP_PROMPT["title"][0],
        common.BOT_HELP_PROMPT["message"][0],
        common.BOT_HELP_PROMPT["color"][0]
    )


@export_command("pet", 0)
async def pet_cmd(invoke_msg: discord.Message, response_msg: discord.Message, args, string):
    emotion.pet_anger -= (time.time() - emotion.last_pet - common.PET_INTERVAL) * (
            emotion.pet_anger / common.JUMPSCARE_THRESHOLD
    ) - common.PET_COST

    if emotion.pet_anger < common.PET_COST:
        emotion.pet_anger = common.PET_COST
    emotion.last_pet = time.time()

    fname = "die.gif" if emotion.pet_anger > common.JUMPSCARE_THRESHOLD else "pet.gif"
    await invoke_msg.channel.send(
        "https://raw.githubusercontent.com/PygameCommunityDiscord/"
        f"PygameCommunityBot/main/assets/images/{fname}"
    )

    await response_msg.delete()


@export_command("vibecheck", 0)
async def vibecheck_cmd(invoke_msg: discord.Message, response_msg: discord.Message, args, string):
    await util.edit_embed(
        response_msg,
        "Vibe Check, snek?",
        f"Previous petting anger: {emotion.pet_anger:.2f}/{common.JUMPSCARE_THRESHOLD:.2f}" + \
        f"\nIt was last pet {time.time() - emotion.last_pet:.2f} second(s) ago",
    )


@export_command("sorry", 0)
async def sorry_cmd(invoke_msg: discord.Message, response_msg: discord.Message, args, string):
    if not emotion.boncc_count:
        await util.edit_embed(
            response_msg,
            "Ask forgiveness from snek?",
            "Snek is happy. Awww, don't be sorry."
        )
        return

    if random.random() < common.SORRY_CHANCE:
        emotion.boncc_count -= common.BONCC_PARDON
        if emotion.boncc_count < 0:
            emotion.boncc_count = 0
        await util.edit_embed(
            response_msg,
            "Ask forgiveness from snek?",
            "Your pythonic lord accepts your apology.\n" + \
            f"Now go to code again.\nThe boncc count is {emotion.boncc_count}"
        )
    else:
        await util.edit_embed(
            response_msg,
            "Ask forgiveness from snek?",
            "How did you dare to boncc a snake?\nBold of you to assume " + \
            "I would apologize to you, two-feet-standing being!\nThe " + \
            f"boncc count is {emotion.boncc_count}"
        )


@export_command("bonkcheck", 0)
async def bonkcheck_cmd(invoke_msg: discord.Message, response_msg: discord.Message, args, string):
    if emotion.boncc_count:
        await util.edit_embed(
            response_msg,
            "The snek is hurt and angry:",
            f"The boncc count is {emotion.boncc_count}"
        )
    else:
        await util.edit_embed(
            response_msg,
            "The snek is right",
            "Please, don't hit the snek"
        )
