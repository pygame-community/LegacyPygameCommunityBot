"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file defines the base classes for the command handler classes, defines
argument parsing and casting utilities
"""


from __future__ import annotations

import datetime
import inspect
import io
import os
import platform
import random
import sys
import traceback
from typing import TypeVar

import discord
import pygame
from pgbot import common, db, embed_utils, utils, emotion

ESCAPES = {
    "0": "\0",
    "n": "\n",
    "r": "\r",
    "t": "\t",
    "v": "\v",
    "b": "\b",
    "f": "\f",
    "\\": "\\",
    '"': '"',
    "'": "'",
}


class BotException(Exception):
    """
    Base class for all bot related exceptions, that need to be displayed on
    discord
    """


class ArgError(BotException):
    """
    Base class for arguments related exceptions
    """


class KwargError(BotException):
    """
    Base class for keyword arguments related exceptions
    """


class CodeBlock:
    """
    Base class to represent code blocks in the argument parser
    """

    def __init__(self, text: str, no_backticks=False):
        self.lang = None
        self.text = code = text

        md_bacticks = ("```", "`")

        if no_backticks and "\n" in code:
            code = code[code.index("\n") + 1 :]

        elif code.startswith(md_bacticks) or code.endswith(md_bacticks):
            code = code.strip("`")
            if code[0].isspace():
                code = code[1:]
            elif code[0].isalnum():
                i = 0
                for i in range(len(code)):
                    if code[i].isspace():
                        break
                self.lang = code[:i]
                code = code[i + 1 :]

        self.code: str = code.strip().strip("\\")  # because \\ causes problems


class String:
    """
    Base class to represent strings in the argument parser. On the discord end
    it is a string enclosed in quotes
    """

    def __init__(self, string: str):
        self.string = self.escape(string)

    def escape(self, string: str):
        """
        Convert a "raw" string to one where characters are escaped
        """
        cnt = 0
        newstr = ""
        while cnt < len(string):
            char = string[cnt]
            cnt += 1
            if char == "\\":
                char = string[cnt]
                cnt += 1
                if char.lower() in ["x", "u"]:
                    if char.lower() == "x":
                        n = 2
                    else:
                        n = 4 if char == "u" else 8

                    var = string[cnt : cnt + n]
                    cnt += n
                    try:
                        newstr += chr(int(var, base=16))
                    except ValueError:
                        raise BotException(
                            "Invalid escape character",
                            "Invalid unicode escape character in string",
                        )
                elif char in ESCAPES:
                    newstr += ESCAPES[char]
                else:
                    raise BotException(
                        "Invalid escape character",
                        "Invalid unicode escape character in string",
                    )
            else:
                newstr += char

        return newstr


# Type hint for an argument that is "hidden", that is, it cannot be passed
# from the discord end
HiddenArg = TypeVar("HiddenArg")

SPLIT_FLAGS = [
    ("```", CodeBlock, (True,)),
    ("`", CodeBlock, (True,)),
    ('"', String, ()),
    ("'", String, ()),
]


def fun_command(func):
    """
    A decorator to indicate a "fun command", one that the bot skips when it is
    'exhausted'
    """
    func.fun_cmd = True
    return func


def add_group(groupname: str, *subcmds: str):
    """
    Utility to add a function name to a group command
    """

    def inner(func):
        # patch in group name data and sub command data into the function itself
        if subcmds:
            func.groupname = groupname
            func.subcmds = subcmds
        return func

    return inner


class BaseCommand:
    """
    Base class for all commands. Defines the main utilities like argument
    parsers and command handlers
    """

    def __init__(
        self,
        invoke_msg: discord.Message,
        resp_msg: discord.Message,
    ):
        """
        Initialise UserCommand class
        """
        # Create a dictionary of command names and respective handler functions
        self.invoke_msg: discord.Message = invoke_msg
        self.response_msg: discord.Message = resp_msg
        self.is_priv = True
        self.cmd_str: str = self.invoke_msg.content[len(common.PREFIX) :]

        # Put a few attributes here for easy access
        self.author: discord.Member = self.invoke_msg.author
        self.channel: discord.TextChannel = self.invoke_msg.channel
        self.guild: discord.Guild = self.invoke_msg.guild
        self.is_dm = self.guild is None
        if self.is_dm:
            self.guild = common.bot.get_guild(common.SERVER_ID)

        self.cmds_and_funcs = {}
        self.groups = {}
        for i in dir(self):
            if i.startswith(common.CMD_FUNC_PREFIX):
                func = self.__getattribute__(i)
                name = i[len(common.CMD_FUNC_PREFIX) :]
                self.cmds_and_funcs[name] = func

                if hasattr(func, "groupname"):
                    if func.groupname in self.groups:
                        self.groups[func.groupname].append(func)
                    else:
                        self.groups[func.groupname] = [func]

    def split_args(self, split_str, split_flags):
        """
        Utility function to do the first parsing step to recursively split
        string based on seperators
        """
        splitchar, splitfunc, exargs = split_flags.pop(0)

        cnt = 0
        prev = ""
        for substr in split_str.split(splitchar):
            if cnt % 2:
                if substr.endswith("\\"):
                    prev += substr + splitchar
                    continue

                yield splitfunc(prev + substr, *exargs)
                prev = ""

            elif split_flags:
                yield from self.split_args(substr, split_flags.copy())
            else:
                yield substr

            cnt += 1

        if not cnt % 2 or prev:
            raise BotException(
                f"Invalid {splitfunc.__name__}",
                f"{splitfunc.__name__} was not properly closed",
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
            for substr in arg.split():
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
                        raise KwargError(
                            "Keyword arguments cannot come before positional "
                            + "arguments"
                        )
                    args.append(substr)

                else:
                    kwstart = True
                    if prevkey:
                        raise KwargError("Did not specify argument after '='")

                    if not a:
                        raise KwargError("Missing keyword before '=' symbol")

                    if not a[0].isalpha() and not a.startswith("_"):
                        raise KwargError(
                            "Keyword argument must begin with an alphabet or "
                            + "underscore"
                        )

                    if c:
                        kwargs[a] = c
                    else:
                        prevkey = a

        if prevkey:
            raise KwargError("Did not specify argument after '='")

        # If user has put an attachment, check whether it's a text file, and
        # handle as code block
        for attach in self.invoke_msg.attachments:
            if attach.content_type is not None and attach.content_type.startswith(
                "text"
            ):
                contents = await attach.read()
                args.append(CodeBlock(contents.decode()))

        # user entered something like 'pg!', display help message
        if not args:
            if kwargs:
                raise BotException("Invalid Command name!", "Command name must be str")
            args = ["help"]

        cmd = args.pop(0)
        if not isinstance(cmd, str):
            raise BotException("Invalid Command name!", "Command name must be str")

        if self.invoke_msg.reference is not None:
            msg = str(self.invoke_msg.reference.message_id)
            if self.invoke_msg.reference.channel_id != self.channel.id:
                msg = str(self.invoke_msg.reference.channel_id) + "/" + msg

            args.insert(0, msg)

        return cmd, args, kwargs

    async def _cast_arg(self, anno, arg, cmd):
        """
        Helper to cast an argument to the type mentioned by the parameter
        annotation
        Raises ValueErrors on failure to cast arguments
        """

        if isinstance(arg, CodeBlock):
            if anno == "CodeBlock":
                return arg
            raise ValueError()

        elif isinstance(arg, String):
            if anno == "String":
                return arg

            elif anno in ["datetime.datetime", "datetime"]:
                arg2 = arg.string.strip()
                arg2 = arg2[:-1] if arg2.endswith("Z") else arg2
                return datetime.datetime.fromisoformat(arg2)

            raise ValueError()

        elif isinstance(arg, str):
            if anno in ["CodeBlock", "String", "datetime.datetime", "datetime"]:
                raise ValueError()

            elif anno == "HiddenArg":
                raise ArgError("Hidden arguments cannot be explicitly passed", cmd)

            elif anno == "pygame.Color":
                return pygame.Color(arg)

            elif anno == "bool":
                return arg == "1" or arg.lower() == "true"

            elif anno == "int":
                return int(arg)

            elif anno == "float":
                return float(arg)

            elif anno == "range":
                if not arg.startswith("(") or not arg.endswith(")"):
                    raise ValueError()

                splits = [int(i) for i in arg[1:-1].split("-")]
                if splits and len(splits) <= 3:
                    return range(*splits)
                raise ValueError()

            elif anno == "discord.Member":
                try:
                    return await self.guild.fetch_member(utils.filter_id(arg))
                except discord.errors.NotFound:
                    raise ValueError()
            
            elif anno == "discord.User":
                try:
                    return await common.bot.fetch_user(utils.filter_id(arg))
                except discord.errors.NotFound:
                    raise ValueError()

            elif anno == "discord.TextChannel":
                chan = self.guild.get_channel(utils.filter_id(arg))
                if chan is None:
                    raise ValueError()

                return chan

            elif anno == "discord.Message":
                a, b, c = arg.partition("/")
                if b:
                    msg = int(c)
                    chan = self.guild.get_channel(utils.filter_id(a))

                    if chan is None:
                        raise ValueError()
                else:
                    msg = int(a)
                    chan = self.channel

                try:
                    return await chan.fetch_message(msg)
                except discord.NotFound:
                    raise ValueError()

            elif anno == "str":
                return arg

            raise BotException(
                "Internal Bot error", f"Invalid type annotation `{anno}`"
            )

        raise BotException(
            "Internal Bot error", f"Invalid argument of type `{type(arg)}`"
        )

    async def cast_arg(self, param, arg, cmd, key=None):
        """
        Cast an argument to the type mentioned by the paramenter annotation
        """
        anno = param.annotation
        if anno in ["Any", param.empty]:
            # no checking/converting, do a direct return
            return arg

        if anno.startswith("Optional[") and anno.endswith("]"):
            anno = anno[9:-1].strip()

        try:
            if anno.startswith("Union[") and anno.endswith("]"):
                annos = [i.strip() for i in anno[6:-1].split(",")]
                for cnt, anno in enumerate(annos):
                    try:
                        return await self._cast_arg(anno, arg, cmd)
                    except ValueError:
                        if cnt == len(annos) - 1:
                            raise

            return await self._cast_arg(anno, arg, cmd)

        except ValueError:
            if anno == "CodeBlock":
                typ = "a codeblock, please surround your code in codeticks"

            elif anno == "String":
                typ = 'a string, please surround it in quotes (`""`)'

            elif anno in ["datetime.datetime", "datetime"]:
                typ = "a string, that denotes datetime in iso format"

            elif anno == "range":
                typ = (
                    "a range specifier, formatted with hyphens, enclosed in "
                    "parenthesis"
                )

            elif anno == "discord.Member":
                typ = (
                    "an id of a person or a mention to them \nPlease make sure"
                    "that the ID is a valid ID of a member in the server"
                )

            elif anno == "discord.TextChannel":
                typ = (
                    "an id or mention to a text channel\nPlease make sure"
                    "that the ID is a valid ID of a channel in the server"
                )

            elif anno == "discord.Message":
                typ = (
                    "a message id, or a 'channel/message' combo\nPlease make"
                    "sure that the ID(s) is(are) valid ones"
                )

            elif anno == "pygame.Color":
                typ = "a color, represented by the color name or hex rgb"

            else:
                typ = f"of type `{param.annotation}`"

            if key is None:
                raise ArgError(f"The variable args/kwargs must be {typ}", cmd)

            raise ArgError(f"The argument `{key}` must be {typ}", cmd)

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

        # command has been blacklisted from running
        if cmd in db.DiscordDB("blacklist").get([]):
            raise BotException(
                "Cannot execute comamand!",
                f"The command '{cmd}' has been temporarily been blocked from "
                + "running, while wizards are casting their spells on it!\n"
                + "Please try running the command after the maintenance work "
                + "has been finished",
            )

        is_group = False
        if cmd in self.groups:
            for func in self.groups[cmd]:
                n = len(func.subcmds)
                if func.subcmds == tuple(args[:n]):
                    args = args[n:]
                    is_group = True
                    break

        if not is_group:
            if cmd not in self.cmds_and_funcs:
                if cmd in common.admin_commands:
                    raise BotException(
                        "Permissions Error!",
                        f"The command '{cmd}' is an admin command, and you do "
                        "not have access to that",
                    )

                raise BotException(
                    "Unrecognized command!",
                    f"The command '{cmd}' does not exist.\nFor help on bot "
                    "commands, do `pg!help`",
                )
            func = self.cmds_and_funcs[cmd]

        if (
            hasattr(func, "fun_cmd")
            and random.randint(0, 1)
            and emotion.get("bored") < -600
        ):
            raise BotException(
                "I am Exhausted!",
                "I have been running a lot of commands lately, and now I am tired.\n"
                "Give me a bit of a break, and I will be back to normal!",
            )

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
                        raise KwargError(
                            f"Missed required keyword argument `{key}`", cmd
                        )
                    kwargs[key] = param.default
                    continue

            elif i == len(args):
                # ran out of args, try to fill it with something
                if key in kwargs:
                    if param.kind == param.POSITIONAL_ONLY:
                        raise ArgError(
                            f"`{key}` cannot be passed as a keyword argument", cmd
                        )
                    args.append(kwargs.pop(key))

                elif param.default == param.empty:
                    raise ArgError(f"Missed required argument `{key}`", cmd)

                else:
                    args.append(param.default)
                    continue

            elif key in kwargs:
                raise ArgError(
                    "Positional cannot be passed again as a keyword argument", cmd
                )

            if iskw:
                kwargs[key] = await self.cast_arg(param, kwargs[key], cmd, key)
            else:
                args[i] = await self.cast_arg(param, args[i], cmd, key)

        i += 1
        # More arguments were given than required
        if not is_var_pos and i < len(args):
            raise ArgError(f"Too many args were given (`{len(args)}`)", cmd)

        # Iterate through kwargs to check if we received invalid ones
        if not is_var_key:
            for key in kwargs:
                if key not in sig.parameters:
                    raise KwargError(f"Received invalid keyword argument `{key}`", cmd)

        await func(*args, **kwargs)

    async def handle_cmd(self):
        """
        Command handler, calls the appropriate sub function to handle commands.
        """
        try:
            return await self.call_cmd()

        except ArgError as exc:
            title = "Invalid Arguments!"
            msg, cmd = exc.args
            msg += f"\nFor help on this bot command, do `pg!help {cmd}`"

        except KwargError as exc:
            title = "Invalid Keyword Arguments!"
            if len(exc.args) == 2:
                msg, cmd = exc.args
                msg += f"\nFor help on this bot command, do `pg!help {cmd}`"
            else:
                msg = exc.args[0]

        except BotException as exc:
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

            if len(title) > 256 or len(elog) > 2048:
                with io.StringIO() as fobj:
                    fobj.write(f"{title}\n{elog}")
                    fobj.seek(0)
                    await self.response_msg.channel.send(
                        content="Here is the full error log",
                        file=discord.File(fobj, filename="exception.txt"),
                    )

        await embed_utils.replace(self.response_msg, title, msg, 0xFF0000)
