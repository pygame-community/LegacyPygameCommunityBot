from __future__ import annotations

import inspect
import os
import platform
import sys
import traceback
from typing import Any, TypeVar

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

    def __init__(self, code, strip_py=False):
        if strip_py:
            if code[:6] == "python":
                code = code[6:]
            elif code[:2] == "py":
                code = code[2:]

        code = code.strip().strip("\\")  # because \\ causes problems
        self.code = code


class String:
    """
    Base class to represent strings in the argument parser. On the discord end
    it is a string enclosed in quotes
    """

    def __init__(self, string):
        self.string = string


# Type hint for an argument that is "hidden", that is, it cannot be passed
# from the discord end
HiddenArg = TypeVar("HiddenArg")

SPLIT_FLAGS = [
    ("```", CodeBlock, (True,)),
    ("`", CodeBlock, ()),
    ('"', String, ()),
]


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
        self.cmd_str = self.invoke_msg.content[len(common.PREFIX):]

        self.cmds_and_funcs = {}
        for i in dir(self):
            if i.startswith(common.CMD_FUNC_PREFIX):
                self.cmds_and_funcs[i[len(common.CMD_FUNC_PREFIX):]] = \
                    self.__getattribute__(i)

    def split_args(self, split_str, split_flags):
        """
        Utility function to do the first parsing step to recursively split
        string based on seperators
        """
        splitchar, splitfunc, exargs = split_flags.pop(0)
        for cnt, substr in enumerate(split_str.split(splitchar)):
            if cnt % 2:
                yield splitfunc(substr, *exargs)
            elif split_flags:
                yield from self.split_args(substr, split_flags.copy())
            else:
                yield substr

        if cnt % 2:
            raise ArgError(
                f"Invalid {splitfunc.__name__}",
                f"{splitfunc.__name__} was not properly closed"
            )

    async def parse_args(self):
        """
        Custom parser for handling arguments. The work of this function is to
        parse the source string of the command into the command name, a list
        of arguments and a dictionary of keyword arguments. The list of
        arguments must only contain strings, 'CodeBlock' objects and 'String'
        objects.
        """
        args = []
        kwargs = {}
        kwstart = False  # used to make sure that keyword args come after args
        prevkey = None  # temporarily store previous key name

        for arg in self.split_args(self.cmd_str, SPLIT_FLAGS.copy()):
            if not isinstance(arg, str):
                if prevkey is not None:
                    kwargs[prevkey] = arg
                    prevkey = None
                else:
                    args.append(arg)
                continue

            arg = arg.replace(" =", "=")
            for substr in arg.split(" "):
                substr = substr.strip()
                if not substr:
                    continue

                a, b, c = substr.partition("=")
                if not b:
                    if prevkey:
                        kwargs[prevkey] = a
                        prevkey = None
                        continue

                    if kwstart:
                        raise ArgError(
                            "Invalid Keyword Arguments!",
                            "Keyword arguments cannot come before positional "
                            + "arguments"
                        )
                    args.append(substr)

                else:
                    kwstart = True
                    if prevkey:
                        raise ArgError(
                            "Invalid Keyword Argument!",
                            "Did not specify argument after '='"
                        )

                    if not a:
                        raise ArgError(
                            "Invalid Keyword Argument!",
                            "Missing keyword before '=' symbol"
                        )

                    if not a[0].isalpha() and not a.startswith("_"):
                        raise ArgError(
                            "Invalid Keyword Argument!",
                            "Keyword argument must begin with an alphabet or "
                            + "underscore"
                        )

                    if c:
                        kwargs[a] = c
                    else:
                        prevkey = a

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
        if not args:
            if kwargs:
                raise ArgError(
                    "Invalid Keyword Argument!",
                    "Keyword argument entered without command!"
                )
            args = ["help"]

        cmd = args.pop(0)
        if not isinstance(cmd, str):
            raise ArgError("Invalid Command name!", "")

        if self.invoke_msg.reference is not None:
            args.insert(
                0,
                str(self.invoke_msg.reference.channel_id) + "/"
                + str(self.invoke_msg.reference.message_id)
            )

        return cmd, args, kwargs

    async def _cast_arg(self, param, arg):
        """
        Helper to cast an argument to the type mentioned by the parameter 
        annotation
        Raises ValueErrors on failure to cast arguments
        """
        if param.annotation in ["Any", param.empty]:
            # no checking/converting, do a direct return
            return arg

        if param.annotation.startswith("Optional["):
            anno = param.annotation[9:-1].strip()
        else:
            anno = param.annotation

        if isinstance(arg, CodeBlock):
            if anno == "CodeBlock":
                return arg
            raise ValueError()

        elif isinstance(arg, String):
            if anno == "String":
                return arg
            raise ValueError()

        elif isinstance(arg, str):
            if anno in ["CodeBlock", "String"]:
                raise ValueError()

            elif anno == "HiddenArg":
                raise ArgError(
                    "Invalid Arguments!",
                    "Hidden arguments cannot be explicitly passed"
                )

            elif anno == "pygame.Color":
                return pygame.Color(arg)

            elif anno == "bool":
                return arg == "1" or arg.lower() == "true"

            elif anno == "int":
                return int(arg)

            elif anno == "float":
                return float(arg)

            elif anno == "discord.Member":
                return await utils.get_mention_from_id(arg, self.invoke_msg)

            elif anno == "discord.TextChannel":
                chan_id = utils.filter_id(arg)
                chan = self.invoke_msg.guild.get_channel(chan_id)
                if chan is None:
                    raise ArgError(
                        "Invalid Arguments!", "Got invalid channel ID"
                    )

                return chan

            elif anno == "discord.Message":
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

            elif anno == "str":
                return arg

            raise ArgError(
                "Internal Bot error", f"Invalid type annotation `{anno}`"
            )

        raise ArgError(
            "Internal Bot error", f"Invalid argument of type `{type(arg)}`"
        )

    async def cast_arg(self, param, arg, cmd, key=None):
        """
        Cast an argument to the type mentioned by the paramenter annotation
        """
        try:
            return await self._cast_arg(param, arg)

        except ValueError:
            # TODO fix anno
            if param.annotation == "CodeBlock":
                typ = "a codeblock, please surround your code in codeticks"

            elif param.annotation == "String":
                typ = "a string, please surround it in quotes (`\"\"`)"

            elif param.annotation == "discord.Member":
                typ = "an id of a person or a mention to them"

            elif param.annotation == "discord.TextChannel":
                typ = "an id or mention to a text channel"

            elif param.annotation == "discord.Message":
                typ = "a message id, or a 'channel/message' combo"

            elif param.annotation == "pygame.Color":
                typ = "a color, represented by the color name or hex rgb"

            else:
                typ = f"of type `{param.annotation}`"

            if key is None:
                msg = "The variable args/kwargs"
            else:
                msg = f"The argument `{key}`"

            raise ArgError(
                "Invalid Arguments!",
                f"{msg} must be {typ} \n"
                + f"For help on this bot command, do `pg!help {cmd}`",
            )

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

        i = -1
        is_var_pos = is_var_key = False
        keyword_only_args = []

        # iterate through function parameters, arrange the given args and
        # kwargs in the order and format the function wants
        for i, key in enumerate(sig.parameters):
            param = sig.parameters[key]
            iskw = False

            if param.kind == param.VAR_POSITIONAL:
                is_var_pos = True
                for j in range(i, len(args)):
                    args[j] = await self.cast_arg(param, args[j], cmd)
                continue

            elif param.kind == param.VAR_KEYWORD:
                is_var_key = True
                for j in kwargs:
                    if j not in keyword_only_args:
                        kwargs[j] = await self.cast_arg(param, kwargs[j], cmd)
                continue

            elif param.kind == param.KEYWORD_ONLY:
                iskw = True
                keyword_only_args.append(key)
                if key not in kwargs:
                    if param.default == param.empty:
                        raise ArgError(
                            "Invalid Keyword Arguments!",
                            f"Missed required keyword argument `{key}` \nFor "
                            + f"help on this bot command, do `pg!help {cmd}`"
                        )
                    kwargs[key] = param.default
                    continue

            elif i == len(args):
                # ran out of args, try to fill it with something
                if key in kwargs:
                    if param.kind == param.POSITIONAL_ONLY:
                        raise ArgError(
                            "Invalid Arguments!",
                            f"`{key}` cannot be passed as a keyword argument \n"
                            + f"Run `pg!help {cmd}` for help on this command"
                        )
                    args.append(kwargs.pop(key))

                elif param.default == param.empty:
                    raise ArgError(
                        "Invalid Arguments!",
                        f"Missed required argument `{key}` \nFor help on "
                        + f"this bot command, do `pg!help {cmd}`"
                    )

                else:
                    args.append(param.default)
                    continue

            elif key in kwargs:
                raise ArgError(
                    "Invalid Arguments!",
                    "Positional cannot be passed again as a keyword argument"
                )

            if iskw:
                kwargs[key] = await self.cast_arg(param, kwargs[key], cmd, key)
            else:
                args[i] = await self.cast_arg(param, args[i], cmd, key)

        i += 1
        # More arguments were given than required
        if not is_var_pos and i < len(args):
            raise ArgError(
                "Invalid Arguments!",
                f"Too many args were given ({len(args)}) \n"
                + f"For help on this bot command, do `pg!help {cmd}`",
            )

        # Iterate through kwargs to check if we received invalid ones
        if not is_var_key:
            for key in kwargs:
                if key not in sig.parameters:
                    raise ArgError(
                        "Invalid Keyword Argument!",
                        f"Received invalid keyword argument `{key}`\n"
                        + f"For help on this bot command, do `pg!help {cmd}`"
                    )

        await func(*args, **kwargs)

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
            # Pop out the second and third entry in the traceback, because that
            # is this function call itself
            tbs.pop(1)
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
