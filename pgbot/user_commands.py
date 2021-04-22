import asyncio
import os
import platform
import random
import sys
import time
import traceback

import discord
import pygame

from . import clock, common, docs, emotion, sandbox, util


class ArgError(Exception):
    pass


class UserCommand:
    """
    Base class to handle user commands.
    """

    def __init__(self):
        """
        Initialise UserCommand class
        """
        # Create a dictionary of command names and respective handler functions
        self.cmds_and_funcs = {}
        for i in dir(self):
            if i.startswith("cmd_"):
                self.cmds_and_funcs[i[len("cmd_"):]] = self.__getattribute__(i)

    async def handle_cmd(
        self, invoke_msg: discord.Message, resp_msg: discord.Message, is_priv
    ):
        """
        Calls the appropriate sub function to handle commands.
        Must return True on successful command execution, False otherwise
        """
        self.invoke_msg = invoke_msg
        self.response_msg = resp_msg

        cmd_str = invoke_msg.content[len(common.PREFIX):].lstrip()
        self.args = cmd_str.split()
        cmd = self.args.pop(0) if self.args else ""
        self.string = cmd_str[len(cmd):].strip()
        self.is_priv = is_priv

        title = "Unrecognized command!"
        msg = f"Make sure that the command '{cmd}' exists, " + \
               "and you have the permission to use it"
        try:
            if cmd in self.cmds_and_func:
                await self.cmds_and_funcs[cmd]()
                return
        
        except ArgError:
            title = "Incorrect amount of arguments!"
            msg = exc.args[0]

        except Exception as exc:
            title = "An exception occured while handling the command!"

            error_tuple = (type(exc), exc, exc.__traceback__)
            tbs = traceback.format_exception(*error_tuple)
            # Pop out the first entry in the traceback, because that's
            # this function call itself
            tbs.pop(1)

            elog = "This error is most likely caused due to a bug in " + \
                "the bot itself. Here is the traceback:\n"
            elog += ''.join(tbs).replace(os.getcwd(), "PgBot")
            if platform.system() == "Windows":
                elog = elog.replace(
                    os.path.dirname(sys.executable), "Python"
                )

            msg = util.code_block(elog)

        await util.edit_embed(resp_msg, title, msg, 0xFF0000)

    def check_args(self, minarg, maxarg=None):
        """
        A utility for a function to check that the correct number of args were
        passed
        """
        exp = f"between {minarg} and {maxarg}"
        if maxarg is None:
            exp = maxarg = minarg

        got = len(self.args)
        if not (minarg <= got <= maxarg):
            raise ArgError(
                f"The number of arguments must be {exp} but {got} were given"
            )

    async def cmd_version(self):
        """
        Implement pg!version, to report bot version
        """
        self.check_args(0)
        await util.edit_embed(
            self.response_msg, "Current bot's version", f"`{common.VERSION}`"
        )

    async def cmd_clock(self):
        """
        Implement pg!clock, to display a clock of helpfulies/mods/wizards
        """
        self.check_args(0)

        t = time.time()
        pygame.image.save(clock.user_clock(t), f"temp{t}.png")
        common.cmd_logs[self.invoke_msg.id] = \
            await self.response_msg.channel.send(
                file=discord.File(f"temp{t}.png")
        )
        await self.response_msg.delete()
        os.remove(f"temp{t}.png")

    async def cmd_doc(self):
        """
        Implement pg!doc, to view documentation
        """
        self.check_args(1)

        await docs.put_doc(self.args[0], self.invoke_msg.channel)
        await self.response_msg.delete()

    async def cmd_exec(self):
        """
        Implement pg!exec, for execution of python code
        """
        code = self.string.lstrip('`').rstrip('`')
        if code.startswith("python\n"):
            code = code[7:]
        elif code.startswith("py\n"):
            code = code[3:]

        tstamp = time.perf_counter_ns()
        returned = await sandbox.exec_sandbox(code, tstamp, 10 if self.is_priv else 5)
        dur = returned.duration  # the execution time of the script alone

        if returned.exc is None:
            if returned.img:
                if os.path.getsize(f"temp{tstamp}.png") < 2 ** 22:
                    await self.response_msg.channel.send(
                        file=discord.File(f"temp{tstamp}.png")
                    )
                else:
                    await util.edit_embed(
                        self.response_msg,
                        "Image cannot be sent:",
                        "The image file size is above 4MiB",
                    )
                os.remove(f"temp{tstamp}.png")

            await util.edit_embed(
                self.response_msg,
                f"Returned text (code executed in {util.format_time(dur)}):",
                util.code_block(returned.text)
            )

        else:
            await util.edit_embed(
                self.response_msg,
                common.EXC_TITLES[1],
                util.code_block(", ".join(map(str, returned.exc.args)))
            )

    async def cmd_help(self):
        """
        Implement pg!help, to display a help message
        """
        self.check_args(0)
        await util.edit_embed(
            self.response_msg,
            common.BOT_HELP_PROMPT["title"],
            common.BOT_HELP_PROMPT["body"],
            color=common.BOT_HELP_PROMPT["color"],
            fields=common.BOT_HELP_PROMPT["fields"]
        )

    async def cmd_pet(self):
        """
        Implement pg!pet, to pet the bot
        """
        self.check_args(0)
        emotion.pet_anger -= (time.time() - emotion.last_pet - common.PET_INTERVAL) * (
            emotion.pet_anger / common.JUMPSCARE_THRESHOLD
        ) - common.PET_COST

        if emotion.pet_anger < common.PET_COST:
            emotion.pet_anger = common.PET_COST
        emotion.last_pet = time.time()

        fname = "die.gif" if emotion.pet_anger > common.JUMPSCARE_THRESHOLD else "pet.gif"
        await util.edit_embed(
            self.response_msg,
            "",
            "",
            0xFFFFAA,
            "https://raw.githubusercontent.com/PygameCommunityDiscord/"
            + f"PygameCommunityBot/main/assets/images/{fname}"
        )

    async def cmd_vibecheck(self):
        """
        Implement pg!vibecheck, to check if the bot is angry
        """
        self.check_args(0)
        await util.edit_embed(
            self.response_msg,
            "Vibe Check, snek?",
            f"Previous petting anger: {emotion.pet_anger:.2f}/{common.JUMPSCARE_THRESHOLD:.2f}"
            + f"\nIt was last pet {util.format_long_time(round(time.time() - emotion.last_pet))} ago",
        )

    async def cmd_sorry(self):
        """
        Implement pg!sorry, to ask forgiveness from the bot after bonccing it
        """
        self.check_args(0)
        if not emotion.boncc_count:
            await util.edit_embed(
                self.response_msg,
                "Ask forgiveness from snek?",
                "Snek is happy. Awww, don't be sorry."
            )
            return

        if random.random() < common.SORRY_CHANCE:
            emotion.boncc_count -= common.BONCC_PARDON
            if emotion.boncc_count < 0:
                emotion.boncc_count = 0
            await util.edit_embed(
                self.response_msg,
                "Ask forgiveness from snek?",
                "Your pythonic lord accepts your apology.\n"
                + f"Now go to code again.\nThe boncc count is {emotion.boncc_count}"
            )
        else:
            await util.edit_embed(
                self.response_msg,
                "Ask forgiveness from snek?",
                "How did you dare to boncc a snake?\nBold of you to assume "
                + "I would apologize to you, two-feet-standing being!\nThe "
                + f"boncc count is {emotion.boncc_count}"
            )

    async def cmd_bonkcheck(self):
        """
        Implement pg!bonkcheck, to check how much the snek has been boncced
        """
        self.check_args(0)
        if emotion.boncc_count:
            await util.edit_embed(
                self.response_msg,
                "The snek is hurt and angry:",
                f"The boncc count is {emotion.boncc_count}"
            )
        else:
            await util.edit_embed(
                self.response_msg,
                "The snek is right",
                "Please, don't hit the snek"
            )
