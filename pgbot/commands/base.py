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


class CodeBlock:
    """
    Base class to represent code blocks in the argument parser
    """

    def __init__(self, code):
        code = code.strip().strip("\\")  # because \\ causes problems
        self.code = code


class String:
    """
    Base class to represent strings in the argument parser. On the discord end
    it is a string enclosed in quotes
    """

    def __init__(self, string):
        self.string = string


class HiddenArg:
    """
    Base class to represent a "hidden argument", one that cannot be passed via
    discord, but is used internally by other commands
    """


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
        """
        Helper to handle argument parsing
        """
        for cnt, substr in enumerate(argstr.split('"')):
            if cnt % 2:
                args.append(String(substr))
            else:
                for arg in substr.split(" "):
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
                            + "\nRemember to not put spaces around them!"
                        )

        if cnt % 2:
            # The last quote was not closed
            raise ArgError(
                "Invalid String", "String was not properly closed in quotes"
            )

        return kwstart

    async def parse_args(self):
        """
        Custom parser for handling arguments. The work of this function is to
        parse the source string of the command into the command name, a list
        of arguments and a dictionary of keyword arguments. The list of
        arguments must only contain strings, 'CodeBlock' objects and 'String'
        objects. The keyword arguments dictionary are string-string pairs

        TODO for @Ankith26:
        It is a limitation that 'CodeBlock' and 'String' objects cannot be
        used as keyword arguments, and I am too lazy to fix it as of now. If
        required I will fix it in the future.
        """
        args = []
        kwargs = {}
        kwstart = False  # used to make sure that keyword args come after args

        # first split based on the code block character
        for cnt, substr in enumerate(self.cmd_str.split("```")):
            if cnt % 2:
                # in command block
                if substr[:6] == "python":
                    substr = substr[6:]
                elif substr[:2] == "py":
                    substr = substr[2:]

                args.append(CodeBlock(substr))
            else:
                # Handle non codeblock parts or the command
                kwstart = self.handle_non_code_args(
                    substr, args, kwargs, kwstart
                )

        if cnt % 2:
            # The last command block was not closed
            raise ArgError(
                "Invalid Code block",
                "Code block was not properly closed in code ticks"
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

        # user entered something like 'pg!', display help message
        if not args or not isinstance(args[0], str):
            args = ["help"]
            kwargs.clear()

        cmd = args.pop(0)
        return cmd, args, kwargs

    async def call_cmd(self):
        """
        Command handler, calls the appropriate sub function to handle commands.
        This one takes in the parsed arguments from the parse_args function,
        and handles that according to the function being called, by using
        the inspect module, and verifying that all args and kwargs are accurate
        before calling the actual function. Relies on argument annotations to
        cast args/kwargs to the types required by the function
        """
        cmd, args, kwargs = await self.parse_args()

        # command name entered does not exist
        if cmd not in self.cmds_and_funcs:
            raise ArgError(
                "Unrecognized command!",
                f"Make sure that the command '{cmd}' exists, and you have "
                + "the permission to use it. \nFor help on bot commands, "
                + "do `pg!help`"
            )

        func = self.cmds_and_funcs[cmd]
        sig = inspect.signature(func)

        # Iterate through kwargs to check if we recieved invalid ones
        for key in kwargs:
            if key not in sig.parameters:
                raise ArgError(
                    "Invalid Keyword Argument!",
                    f"Recieved invalid keyword argument `{key}`\n"
                    + f"For help on this bot command, do `pg!help {cmd}`"
                )

        i = -1
        newargs = []

        # iterate through function parameters, arrange the given args and
        # kwargs in the order and format the function wants
        for i, key in enumerate(sig.parameters):
            param = sig.parameters[key]

            # a bool which indicates wheter an argument is at it's default value
            isdefault = False
            if key in kwargs:
                # argument was passed as a keyword argument
                arg = kwargs[key]

            elif i >= len(args):
                if param.default == sig.empty:
                    raise ArgError(
                        "Invalid Arguments!",
                        f"Missed required argument `{key}` \nFor help on "
                        + f"this bot command, do `pg!help {cmd}`"
                    )
                else:
                    # use default argument for the function
                    isdefault = True
                    arg = param.default

            else:
                arg = args[i]

            if not isdefault:
                try:
                    newargs.append(
                        await self.correct_arg(sig, param, arg)
                    )
                except ValueError:
                    if param.annotation == "discord.Member":
                        typ = "an @mention to someone"

                    elif param.annotation == "discord.TextChannel":
                        typ = "an id or mention to a text channel"

                    elif param.annotation == "discord.Messgae":
                        typ = "a message id, or a 'channel/message' combo"

                    elif param.annotation == "pygame.Color":
                        typ = (
                            "a color, represented by"
                            "the color name or hex rgb"
                        )

                    else:
                        typ = f"of type `{param.annotation}`"

                    raise ArgError(
                        "Invalid Arguments!",
                        f"The argument `{key}` must be {typ} \n"
                        + f"For help on this bot command, do `pg!help {cmd}`",
                    )
            else:
                newargs.append(arg)

        i += 1
        # More arguments were given than required
        tot = len(args) + len(kwargs)
        if i < tot:
            raise ArgError(
                "Invalid Arguments!",
                f"{tot} were given, but {i} is the maximum number allowed. \n"
                + f"For help on this bot command, do `pg!help {cmd}`",
            )

        await func(*newargs)

    async def correct_arg(self, sig, param, arg):
        if param.annotation == "HiddenArg":
            raise ArgError(
                "Invalid Arguments!",
                "Hidden arguments cannot be explicitly passed"
            )

        elif param.annotation == "pygame.Color":
            return pygame.Color(arg)

        elif param.annotation == "bool":
            return arg == "1" or bool(arg.lower() == "true")

        elif param.annotation == "int":
            return int(arg)

        elif param.annotation == "float":
            return float(arg)

        elif param.annotation == "discord.Member":
            return utils.get_mention_from_id(arg, self.invoke_msg)

        elif param.annotation == "discord.TextChannel":
            if not isinstance(arg, str):
                raise ValueError()

            chan_id = utils.filter_id(arg)
            chan = self.invoke_msg.guild.get_channel(chan_id)

            if chan is None:
                raise ArgError(
                    "Invalid Arguments!", "Got invalid channel ID"
                )

            return chan

        elif param.annotation == "discord.Message":
            if not isinstance(arg, str):
                raise ValueError()

            a, b, c = arg.partition("/")
            if b:
                msg = int(c)
                chan_id = utils.filter_id(a)
                chan = self.invoke_msg.guild.get_channel(chan_id)

                if chan is None:
                    raise ArgError(
                        "Invalid Arguments!", "Got invalid channel ID"
                    )

            else:
                msg = int(a)
                chan = self.invoke_msg.channel

            try:
                return await chan.fetch_message(msg)
            except discord.NotFound:
                raise ArgError(
                    "Invalid Arguments!", "Got invalid message ID"
                )

        elif param.annotation == "CodeBlock":
            # Expected code block, did not get one
            if not isinstance(arg, CodeBlock):
                raise ArgError(
                    "Invalid Arguments!",
                    "Please enter code in 'code blocks', that is, "
                    + "surround your code in code backticks '```'",
                )

            return arg

        elif param.annotation == "String":
            # Expected String, did not get one
            if not isinstance(arg, String):
                raise ArgError(
                    "Invalid Arguments!",
                    "Please enter the string in quotes"
                )

            return arg

        elif param.annotation in [sig.empty, "str"]:
            return arg

        raise ArgError(
            "Internal Bot error", f"Invalid annotation `{param.annotation}`"
        )

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

            elog = (
                "This error is most likely caused due to a bug in "
                + "the bot itself. Here is the traceback:\n"
            )
            elog += "".join(tbs).replace(os.getcwd(), "PgBot")
            if platform.system() == "Windows":
                # Hide path to python on windows
                elog = elog.replace(os.path.dirname(sys.executable), "Python")

            msg = utils.code_block(elog)

        await embed_utils.replace(self.response_msg, title, msg, 0xFF0000)


class OldBaseCommand:
    """
    Base class to handle commands. This is the older version of BaseCommand,
    kept temporarily while we are switching to the new command handler and new
    command argument system. Right now, this is only useful for the emsudo
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
        self.string = ""
        self.args = []

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
        msg = (
            f"Make sure that the command '{cmd}' exists, and you have "
            + "the permission to use it. \nFor help on bot commands, do `pg!help`"
        )
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

            elog = (
                "This error is most likely caused due to a bug in "
                + "the bot itself. Here is the traceback:\n"
            )
            elog += "".join(tbs).replace(os.getcwd(), "PgBot")
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
        if not minarg <= got <= maxarg:
            raise ArgError(
                f"The number of arguments must be {exp} but {got} were given"
            )
