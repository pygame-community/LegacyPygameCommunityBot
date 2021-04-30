from __future__ import annotations

import asyncio
import inspect
import os
import platform
import random
import re
import sys
import time
import traceback
import urllib

import discord
import pygame
from discord.errors import HTTPException

from . import clock, common, docs, emotion, sandbox, utils, embed_utils


class CodeBlock:
    def __init__(self, code):
        code = code.strip().strip("\\")  # because \\ causes problems
        self.code = code


class BaseCommand:
    """
    Base class for all commands. Defines the main utilities like argument
    parsers and command handlers
    """

    def __init__(
        self, invoke_msg: discord.Message, resp_msg: discord.Message,
    ):
        """
        Initialise UserCommand class
        """
        # Create a dictionary of command names and respective handler functions
        self.invoke_msg = invoke_msg
        self.response_msg = resp_msg
        self.is_priv = True

        self.cmds_and_funcs = {}
        for i in dir(self):
            if i.startswith("cmd_"):
                self.cmds_and_funcs[i[len("cmd_"):]] = self.__getattribute__(i)

    async def parse_args(self, argstr):
        """
        Custom parser for handling arguments
        """
        splits = argstr.split("```")
        newargs = []
        for cnt, i in enumerate(splits):
            if cnt % 2:
                # in command block
                if i[:6] == "python":
                    i = i[6:]
                elif i[:2] == "py":
                    i = i[2:]

                newargs.append(CodeBlock(i))
            else:
                newargs.extend(filter(lambda x: x, i.split(" ")))

        if cnt % 2:
            # The last command block was not closed
            await embed_utils.replace(
                self.response_msg,
                "Invalid Code block",
                "Code block was not properly closed in code ticks",
                0xFF0000
            )
            return None, None

        # args empty or starts with code block
        if not newargs or isinstance(newargs[0], CodeBlock):
            await embed_utils.replace(
                self.response_msg,
                "Invalid Command",
                "Proper command name was not entered",
                0xFF0000
            )
            return None, None

        # If user has put an attachment, check whether it's a text file, and
        # handle as code block
        for attach in self.invoke_msg.attachments:
            if (
                attach.content_type is not None
                and attach.content_type.startswith("text")
            ):
                contents = await attach.read()
                newargs.append(CodeBlock(contents.decode()))

        cmd = newargs.pop(0)
        return cmd, newargs

    async def handle_cmd(self):
        """
        Command handler, calls the appropriate sub function to handle commands.
        """
        cmd_str = self.invoke_msg.content[len(common.PREFIX):].lstrip()
        cmd, args = await self.parse_args(cmd_str)
        if cmd is None:
            return

        if cmd not in self.cmds_and_funcs:
            await embed_utils.replace(
                self.response_msg,
                "Unrecognized command!",
                f"Make sure that the command '{cmd}' exists, and you have "
                + "the permission to use it. \nFor help on bot commands, "
                + "do `pg!help`",
                0xFF0000
            )
            return

        func = self.cmds_and_funcs[cmd]
        sig = inspect.signature(func)

        i = -1
        for i, key in enumerate(sig.parameters):
            val = sig.parameters[key]
            if val.annotation == sig.empty:
                # A function argument had no annotations
                await embed_utils.replace(
                    self.response_msg,
                    "Internal Bot error",
                    "This error is due to a bug in the bot, if you are "
                    + "seeing this message, alert a mod or wizard about it",
                    0xFF0000
                )
                return

            if i >= len(args) and val.default == sig.empty:
                # Missed a required positional argument
                await embed_utils.replace(
                    self.response_msg,
                    "Invalid Arguments!",
                    f"{len(args)} were given, but more were expected. \n"
                    + f"For help on this bot command, do `pg!help {cmd}`",
                    0xFF0000
                )
                return

            try:
                if val.annotation == "int":
                    args[i] = int(args[i])
                elif val.annotation == "float":
                    args[i] = float(args[i])
            except ValueError:
                await embed_utils.replace(
                    self.response_msg,
                    "Invalid Arguments!",
                    f"The argument at index {i} must be {val} \n"
                    + f"For help on this bot command, do `pg!help {cmd}`",
                    0xFF0000
                )
                return

            if val.annotation == "CodeBlock" and not isinstance(args[i], CodeBlock):
                await embed_utils.replace(
                    self.response_msg,
                    "Invalid Arguments!",
                    "Please enter code in 'code blocks', that is, surround "
                    + "your code in code backticks '```'",
                    0xFF0000
                )
                return

        i += 1
        # More arguments were given than required
        if i < len(args):
            # If we expected last argument to be a string, join all the
            # remaining arguments into that
            if sig.parameters and val.annotation == "str":
                try:
                    args[i - 1] = " ".join(args[i - 1:])
                    del args[i:]
                except TypeError:
                    # Codeblock found in the remaining arguments
                    await embed_utils.replace(
                        self.response_msg,
                        "Invalid Arguments!",
                        "Got CodeBlock where it is not supposed to be. \n"
                        + f"For help on this bot command, do `pg!help {cmd}`",
                        0xFF0000
                    )
                    return
            else:
                await embed_utils.replace(
                    self.response_msg,
                    "Invalid Arguments!",
                    f"{len(args)} were given, but {i} expected. \n"
                    + f"For help on this bot command, do `pg!help {cmd}`",
                    0xFF0000
                )
                return

        try:
            await func(*args)

        except Exception as exc:
            tbs = traceback.format_exception(type(exc), exc, exc.__traceback__)
            # Pop out the second entry in the traceback, because that's
            # this function call itself
            tbs.pop(1)

            elog = "This error is most likely caused due to a bug in " + \
                "the bot itself. Here is the traceback:\n"
            elog += ''.join(tbs).replace(os.getcwd(), "PgBot")
            if platform.system() == "Windows":
                # Hide path to python on windows
                elog = elog.replace(
                    os.path.dirname(sys.executable), "Python"
                )

            await embed_utils.replace(
                self.response_msg,
                "An exception occured while handling the command!",
                utils.code_block(elog),
                0xFF0000
            )


class UserCommand(BaseCommand):
    """ Base class to handle user commands. """

    async def cmd_version(self):
        """
        ->type Other commands
        ->signature pg!version
        ->description Get the version of <@&822580851241123860>
        -----
        Implement pg!version, to report bot version
        """
        await embed_utils.replace(
            self.response_msg, "Current bot's version", f"`{common.VERSION}`"
        )

    async def cmd_clock(self):
        """
        ->type Get help
        ->signature pg!clock
        ->description 24 Hour Clock showing <@&778205389942030377> 's who are available to help
        -----
        Implement pg!clock, to display a clock of helpfulies/mods/wizards
        """
        t = time.time()
        pygame.image.save(clock.user_clock(t), f"temp{t}.png")
        common.cmd_logs[self.invoke_msg.id] = \
            await self.response_msg.channel.send(
                file=discord.File(f"temp{t}.png")
        )
        await self.response_msg.delete()
        os.remove(f"temp{t}.png")

    async def _cmd_doc(self, modname, page=0, msg=None):
        """
        Helper function for doc, handle pg!refresh stuff
        """
        if not msg:
            msg = self.response_msg

        await docs.put_doc(modname, msg, self.invoke_msg.author, page)

    async def cmd_doc(self, name: str):
        """
        ->type Get help
        ->signature pg!doc [module.Class.method]
        ->description Look up the docstring of a Python/Pygame object, e.g str or pygame.Rect
        -----
        Implement pg!doc, to view documentation
        """
        await self._cmd_doc(name)

    async def cmd_exec(self, code: CodeBlock):
        """
        ->type Run code
        ->signature pg!exec [python code block]
        ->description Run python code in an isolated environment.
        ->extended description
        Import is not available. Various methods of builtin objects have been disabled for security reasons.
        The available preimported modules are:
        `math, cmath, random, re, time, string, itertools, pygame`
        To show an image, overwrite `output.img` to a surface (see example command).
        To make it easier to read and write code use code blocks (see [HERE](https://discord.com/channels/772505616680878080/774217896971730974/785510505728311306)).
        ->example command pg!exec \\`\\`\\`py ```py
        # Draw a red rectangle on a transparent surface
        output.img = pygame.Surface((200, 200)).convert_alpha()
        output.img.fill((0, 0, 0, 0))
        pygame.draw.rect(output.img, (200, 0, 0), (50, 50, 100, 100))```
        \\`\\`\\`
        -----
        Implement pg!exec, for execution of python code
        """
        tstamp = time.perf_counter_ns()
        returned = await sandbox.exec_sandbox(
            code.code, tstamp, 10 if self.is_priv else 5
        )
        dur = returned.duration  # the execution time of the script alone

        if returned.exc is None:
            if returned.img:
                if os.path.getsize(f"temp{tstamp}.png") < 2 ** 22:
                    await self.response_msg.channel.send(
                        file=discord.File(f"temp{tstamp}.png")
                    )
                else:
                    await embed_utils.replace(
                        self.response_msg,
                        "Image cannot be sent:",
                        "The image file size is above 4MiB",
                    )
                os.remove(f"temp{tstamp}.png")

            await embed_utils.replace(
                self.response_msg,
                f"Returned text (code executed in {utils.format_time(dur)}):",
                utils.code_block(returned.text)
            )

        else:
            await embed_utils.replace(
                self.response_msg,
                common.EXC_TITLES[1],
                utils.code_block(", ".join(map(str, returned.exc.args)))
            )

    async def _cmd_help(self, argname, page=0, msg=None):
        """
        Helper function for pg!help, handle pg!refresh stuff
        """
        if not msg:
            msg = self.response_msg

        if argname is None:
            await utils.send_help_message(
                msg,
                self.invoke_msg.author,
                self.cmds_and_funcs,
                page=page
            )
        else:
            await utils.send_help_message(
                msg,
                self.invoke_msg.author,
                self.cmds_and_funcs,
                argname
            )

    async def cmd_help(self, argname: str = None):
        """
        ->type Get help
        ->signature pg!help [command]
        ->description Ask me for help
        ->example command pg!help help
        -----
        Implement pg!help, to display a help message
        """
        await self._cmd_help(argname)

    async def cmd_pet(self):
        """
        ->type Play With Me :snake: 
        ->signature pg!pet
        ->description Pet me :3 . Don't pet me too much or I will get mad.
        -----
        Implement pg!pet, to pet the bot
        """
        emotion.pet_anger -= (time.time() - emotion.last_pet - common.PET_INTERVAL) * (
            emotion.pet_anger / common.JUMPSCARE_THRESHOLD
        ) - common.PET_COST

        if emotion.pet_anger < common.PET_COST:
            emotion.pet_anger = common.PET_COST
        emotion.last_pet = time.time()

        fname = "die.gif" if emotion.pet_anger > common.JUMPSCARE_THRESHOLD else "pet.gif"
        await embed_utils.replace(
            self.response_msg,
            "",
            "",
            0xFFFFAA,
            "https://raw.githubusercontent.com/PygameCommunityDiscord/"
            + f"PygameCommunityBot/main/assets/images/{fname}"
        )

    async def cmd_vibecheck(self):
        """
        ->type Play With Me :snake:
        ->signature pg!vibecheck
        ->description Check my mood.
        -----
        Implement pg!vibecheck, to check if the bot is angry
        """
        await embed_utils.replace(
            self.response_msg,
            "Vibe Check, snek?",
            f"Previous petting anger: {emotion.pet_anger:.2f}/{common.JUMPSCARE_THRESHOLD:.2f}"
            + f"\nIt was last pet {utils.format_long_time(round(time.time() - emotion.last_pet))} ago",
        )

    async def cmd_sorry(self):
        """
        ->type Play With Me :snake:
        ->signature pg!sorry
        ->description You were hitting me <:pg_bonk:780423317718302781> and you're now trying to apologize?
        Let's see what I'll say :unamused:
        -----
        Implement pg!sorry, to ask forgiveness from the bot after bonccing it
        """
        if not emotion.boncc_count:
            await embed_utils.replace(
                self.response_msg,
                "Ask forgiveness from snek?",
                "Snek is happy. Awww, don't be sorry."
            )
            return

        if random.random() < common.SORRY_CHANCE:
            emotion.boncc_count -= common.BONCC_PARDON
            if emotion.boncc_count < 0:
                emotion.boncc_count = 0
            await embed_utils.replace(
                self.response_msg,
                "Ask forgiveness from snek?",
                "Your pythonic lord accepts your apology.\n"
                + f"Now go to code again.\nThe boncc count is {emotion.boncc_count}"
            )
        else:
            await embed_utils.replace(
                self.response_msg,
                "Ask forgiveness from snek?",
                "How did you dare to boncc a snake?\nBold of you to assume "
                + "I would apologize to you, two-feet-standing being!\nThe "
                + f"boncc count is {emotion.boncc_count}"
            )

    async def cmd_bonkcheck(self):
        """
        ->type Play With Me :snake:
        ->signature pg!bonkcheck
        ->description Check how many times you have done me harm.
        -----
        Implement pg!bonkcheck, to check how much the snek has been boncced
        """
        if emotion.boncc_count:
            await embed_utils.replace(
                self.response_msg,
                "The snek is hurt and angry:",
                f"The boncc count is {emotion.boncc_count}"
            )
        else:
            await embed_utils.replace(
                self.response_msg,
                "The snek is right",
                "Please, don't hit the snek"
            )

    async def cmd_refresh(self, msg_id: int):
        """
        ->type Other commands
        ->signature pg!refresh [message_id]
        ->description Refresh a message which support pages.
        -----
        Implement pg!refresh, to refresh a message which supports pages
        """
        try:
            msg = await self.invoke_msg.channel.fetch_message(msg_id)
        except (discord.errors.NotFound, discord.errors.HTTPException):
            await embed_utils.replace(
                self.response_msg,
                "Message not found",
                "Message was not found. Make sure that the id is correct and that "
                "you are in the same channel as the message."
            )
            return

        if not msg.embeds or not msg.embeds[0].footer or not msg.embeds[0].footer.text:
            await embed_utils.replace(
                self.response_msg,
                "Message does not support pages",
                "The message specified does not support pages. Make sure "
                "the id of the message is correct."
            )
            return

        data = msg.embeds[0].footer.text.split("\n")

        page = re.search(r'\d+', data[0]).group()
        command = data[2].replace("Command: ", "").split()

        if not page or not command or not self.cmds_and_funcs.get(command[0]):
            await embed_utils.replace(
                self.response_msg,
                "Message does not support pages",
                "The message specified does not support pages. Make sure "
                "the id of the message is correct."
            )
            return

        await self.response_msg.delete()
        await self.invoke_msg.delete()

        if command[0] == "help":
            await self._cmd_help(
                *command[1:], page=int(page) - 1, msg=msg
            )
        elif command[0] == "doc":
            await self._cmd_doc(
                *command[1:], page=int(page) - 1, msg=msg
            )
