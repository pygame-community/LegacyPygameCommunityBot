from __future__ import annotations

import inspect
import os
import platform
import sys
import traceback

import discord
import pygame

from pgbot import common, embed_utils, utils


class ArgError(Exception):
    """
    Base class for all argument parsing related exceptions
    """
    pass


class CodeBlock:
    """
    Base class to represent code blocks in the argument parser
    """

    def __init__(self, code):
        code = code.strip().strip("\\")  # because \\ causes problems
        self.code = code


class String:
    """
    Base class to represent strings in the argument parser
    """

    def __init__(self, string):
        self.string = string


class MentionableID:
    """
    Base class to a mentionable ID (as an int) in the argument parser
    """

    def __init__(self, string):
        self.id = utils.filter_id(string)


class HiddenArg:
    """
    Base class to represent a "hidden argument", one that cannot be passed via
    discord, but is used internally by other commands
    """
    pass


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
        self.cmd_str = self.invoke_msg.content[len(common.PREFIX):].lstrip()

        self.cmds_and_funcs = {}
        for i in dir(self):
            if i.startswith("cmd_"):
                self.cmds_and_funcs[i[len("cmd_"):]] = self.__getattribute__(i)

    def handle_non_code_args(self, argstr, args, kwargs, kwstart):
        for cnt, i in enumerate(argstr.split('"')):
            if cnt % 2:
                args.append(String(i))
            else:
                for arg in i.split(" "):
                    arg = arg.strip()
                    if not arg:
                        continue

                    a, b, c = arg.partition("=")
                    if not b:
                        if not kwstart:
                            args.append(arg)
                        else:
                            raise ArgError(
                                "Invalid Keyword Arguments!",
                                "Keyword arguments cannot come before "
                                + "positional arguments"
                            )
                    elif a and c:
                        kwstart = True
                        kwargs[a] = c
                    else:
                        raise ArgError(
                            "Invalid Keyword argument",
                            "Keyword seperator '=' was not surrounded by args"
                        )

        if cnt % 2:
            # The last quote was not closed
            raise ArgError(
                "Invalid String",
                "String was not properly closed in quotes"
            )

        return kwstart

    async def parse_args(self):
        """
        Custom parser for handling arguments
        """
        args = []
        kwargs = {}
        kwstart = False
        for cnt, i in enumerate(self.cmd_str.split("```")):
            if cnt % 2:
                # in command block
                if i[:6] == "python":
                    i = i[6:]
                elif i[:2] == "py":
                    i = i[2:]

                args.append(CodeBlock(i))
            else:
                kwstart = self.handle_non_code_args(i, args, kwargs, kwstart)

        if cnt % 2:
            # The last command block was not closed
            raise ArgError(
                "Invalid Code block",
                "Code block was not properly closed in code ticks"
            )

        if not args or not isinstance(args[0], str):
            raise ArgError(
                "Invalid Command",
                "Command name was not entered"
            )

        # If user has put an attachment, check whether it's a text file, and
        # handle as code block
        for attach in self.invoke_msg.attachments:
            if (
                attach.content_type is not None
                and attach.content_type.startswith("text")
            ):
                contents = await attach.read()
                args.append(CodeBlock(contents.decode()))

        cmd = args.pop(0)
        return cmd, args, kwargs

    async def call_cmd(self):
        """
        Command handler, calls the appropriate sub function to handle commands.
        """
        cmd, args, kwargs = await self.parse_args()
        if cmd not in self.cmds_and_funcs:
            raise ArgError(
                "Unrecognized command!",
                f"Make sure that the command '{cmd}' exists, and you have "
                + "the permission to use it. \nFor help on bot commands, "
                + "do `pg!help`"
            )

        func = self.cmds_and_funcs[cmd]
        sig = inspect.signature(func)

        for i in kwargs:
            if i not in sig.parameters:
                raise ArgError(
                    "Invalid Keyword Argument!",
                    f"Recieved invalid keyword argument `{i}`\n"
                    + f"For help on this bot command, do `pg!help {cmd}`"
                )

        i = -1
        newargs = []
        for i, key in enumerate(sig.parameters):
            val = sig.parameters[key]
            if val.annotation == sig.empty:
                # A function argument had no annotations
                raise ArgError(
                    "Internal Bot error",
                    "This error is due to a bug in the bot, if you are "
                    + "seeing this message, alert a mod or wizard about it"
                )

            isdefault = False
            if key in kwargs:
                arg = kwargs[key]
            elif i >= len(args):
                if val.default == sig.empty:
                    raise ArgError(
                        "Invalid Arguments!",
                        f"Missed required argument `{key}`\n For help on "
                        + f"this bot command, do `pg!help {cmd}`"
                    )
                else:
                    isdefault = True
                    arg = val.default
            else:
                arg = args[i]

            if not isdefault:
                try:
                    if val.annotation == "HiddenArg":
                        raise ArgError(
                            "Invalid Arguments!",
                            "Hidden arguments cannot be explicitly passed"
                        )

                    elif val.annotation == "pygame.Color":
                        try:
                            newargs.append(pygame.Color(arg))
                        except ValueError:
                            raise ArgError(
                                "Invalid Arguments!",
                                "Got invalid color argument"
                            )

                    elif val.annotation == "bool":
                        newargs.append(
                            arg == "1" or bool(arg.lower() == "true")
                        )

                    elif val.annotation == "int":
                        newargs.append(int(arg))

                    elif val.annotation == "float":
                        newargs.append(float(arg))

                    elif val.annotation == "discord.Member":
                        try:
                            newargs.append(
                                utils.get_mention_from_id(arg, self.invoke_msg)
                            )
                        except ValueError:
                            raise ArgError(
                                "Invalid Arguments!",
                                f"Expected `{key}` be a member mention.\nFor "
                                + f"help on this bot command, do `pg!help {cmd}`"
                            )

                    elif val.annotation == "MentionableID":
                        if not isinstance(arg, str):
                            raise ArgError(
                                "Invalid Arguments!",
                                f"Expected {key} to be a Mentionable ID argument\n"
                                + f"For help on this bot command, do `pg!help {cmd}`"
                            )
                        newargs.append(MentionableID(arg))

                    elif val.annotation == "CodeBlock":
                        # Expected code block, did not get one
                        if not isinstance(arg, CodeBlock):
                            raise ArgError(
                                "Invalid Arguments!",
                                "Please enter code in 'code blocks', that is, "
                                + "surround your code in code backticks '```'"
                            )
                        newargs.append(arg)

                    elif val.annotation == "String":
                        # Expected String, did not get one
                        if not isinstance(arg, String):
                            raise ArgError(
                                "Invalid Arguments!",
                                "Please enter the string in quotes"
                            )
                        newargs.append(arg)

                    else:
                        newargs.append(arg)

                except ValueError:
                    raise ArgError(
                        "Invalid Arguments!",
                        f"The argument `{key}` must be `{val.annotation}` \n"
                        + f"For help on this bot command, do `pg!help {cmd}`"
                    )
            else:
                newargs.append(arg)

        i += 1
        # More arguments were given than required
        tot = len(args) + len(kwargs)
        if i < tot:
            raise ArgError(
                "Invalid Arguments!",
                f"{tot} were given, but {i} expected. \n"
                + f"For help on this bot command, do `pg!help {cmd}`"
            )

        await func(*newargs)

    async def handle_cmd(self):
        """
        Command handler, calls the appropriate sub function to handle commands.
        """
        try:
            return await self.call_cmd()

        except ArgError as exc:
            title, msg = exc.args

        except Exception as exc:
            title = "An exception occured while handling the command!"
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

            msg = utils.code_block(elog)

        await embed_utils.replace(self.response_msg, title, msg, 0xFF0000)


class OldBaseCommand:
    """
    Base class to handle commands. This is the older version of BaseCommand,
    kept temporarily while we are switching to the new command handler and new
    command argument system. Right now, this is only useful for the Emsudo
    commands
    """

    def __init__(
        self, invoke_msg: discord.Message, resp_msg: discord.Message, is_priv
    ):
        """
        Initialise OldBaseCommand class
        """
        self.invoke_msg = invoke_msg
        self.response_msg = resp_msg
        self.is_priv = is_priv
        self.cmd_str = self.invoke_msg.content[len(common.PREFIX):].lstrip()

        # Create a dictionary of command names and respective handler functions
        self.cmds_and_funcs = {}
        for i in dir(self):
            if i.startswith("cmd_"):
                self.cmds_and_funcs[i[len("cmd_"):]] = self.__getattribute__(i)

    async def handle_cmd(self):
        """
        Calls the appropriate sub function to handle commands.
        Must return True on successful command execution, False otherwise
        """
        self.args = self.cmd_str.split()
        cmd = self.args.pop(0) if self.args else ""
        self.string = self.cmd_str[len(cmd):].strip()

        title = "Unrecognized command!"
        msg = f"Make sure that the command '{cmd}' exists, and you have " + \
            "the permission to use it. \nFor help on bot commands, do `pg!help`"
        try:
            if cmd in self.cmds_and_funcs:
                await self.cmds_and_funcs[cmd]()
                return

        except ArgError as exc:
            title = "Incorrect amount of arguments!"
            msg = exc.args[0]
            msg += f" \nFor help on this bot command, do `pg!help {cmd}`"

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

            msg = utils.code_block(elog)

        await embed_utils.replace(self.response_msg, title, msg, 0xFF0000)

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
