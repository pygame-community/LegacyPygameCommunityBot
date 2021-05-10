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

ESCAPES = {
    '0': '\0',
    'n': '\n',
    'r': '\r',
    't': '\t',
    'v': '\v',
    'b': '\b',
    'f': '\f',
    '\\': '\\',
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

    def __init__(self, text, no_backticks=False):
        self.lang = None
        self.text = code = text
        md_bacticks = ("```", "`")

        if no_backticks and "\n" in code:
            code = code[code.index("\n") + 1:]
        
        elif code.startswith(md_bacticks) or code.endswith(md_bacticks):
            code = code.strip("`")
            if code[0].isspace():
                code = code[1:]
            elif code[0].isalnum():
                for i in range(len(code)):
                    if code[i].isspace():
                        break
                self.lang = code[:i]
                code = code[i+1:]

        self.code = code.strip().strip("\\")  # because \\ causes problems


class String:
    """
    Base class to represent strings in the argument parser. On the discord end
    it is a string enclosed in quotes
    """

    def __init__(self, string):
        self.string = self.escape(string)

    def escape(self, string):
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

                    var = string[cnt:cnt + n]
                    cnt += n
                    try:
                        newstr += chr(int(var, base=16))
                    except ValueError:
                        raise BotException(
                            "Invalid escape character",
                            "Invalid unicode escape character in string"
                        )
                elif char in ESCAPES:
                    newstr += ESCAPES[char]
                else:
                    raise BotException(
                        "Invalid escape character",
                        "Invalid unicode escape character in string"
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

        # Put a few attributes here for easy access
        self.author = self.invoke_msg.author
        self.channel = self.invoke_msg.channel
        self.guild = self.invoke_msg.guild
        self.is_dm = self.guild is None
        if self.is_dm:
            self.guild = common.bot.get_guild(common.SERVER_ID)

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
            if (
                attach.content_type is not None
                and attach.content_type.startswith("text")
            ):
                contents = await attach.read()
                args.append(CodeBlock(contents.decode()))

        # user entered something like 'pg!', display help message
        if not args:
            if kwargs:
                raise BotException(
                    "Invalid Command name!", "Command name must be str"
                )
            args = ["help"]

        cmd = args.pop(0)
        if not isinstance(cmd, str):
            raise BotException(
                "Invalid Command name!", "Command name must be str"
            )

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
            raise ValueError()

        elif isinstance(arg, str):
            if anno in ["CodeBlock", "String"]:
                raise ValueError()

            elif anno == "HiddenArg":
                raise ArgError(
                    "Hidden arguments cannot be explicitly passed",
                    cmd
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
                try:
                    return await utils.get_mention_from_id(arg, self.invoke_msg)
                except discord.errors.NotFound:
                    raise BotException(
                        f"Member does not exist!",
                        f"The member \"{arg}\" does not exist, please try again."
                    )

            elif anno == "discord.TextChannel":
                chan_id = utils.filter_id(arg)
                chan = self.guild.get_channel(chan_id)
                if chan is None:
                    raise ArgError("Got invalid channel ID", cmd)

                return chan

            elif anno == "discord.Message":
                a, b, c = arg.partition("/")
                if b:
                    msg = int(c)
                    chan_id = utils.filter_id(a)
                    chan = self.guild.get_channel(chan_id)

                    if chan is None:
                        raise ArgError("Got invalid channel ID", cmd)
                else:
                    msg = int(a)
                    chan = self.channel

                try:
                    return await chan.fetch_message(msg)
                except discord.NotFound:
                    raise ArgError("Got invalid message ID", cmd)

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

        if anno.startswith("Optional["):
            anno = anno[9:-1].strip()

        try:
            return await self._cast_arg(anno, arg, cmd)

        except ValueError:
            if anno == "CodeBlock":
                typ = "a codeblock, please surround your code in codeticks"

            elif anno == "String":
                typ = "a string, please surround it in quotes (`\"\"`)"

            elif anno == "discord.Member":
                typ = "an id of a person or a mention to them"

            elif anno == "discord.TextChannel":
                typ = "an id or mention to a text channel"

            elif anno == "discord.Message":
                typ = "a message id, or a 'channel/message' combo"

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

        # command name entered does not exist
        if cmd not in self.cmds_and_funcs:
            raise BotException(
                "Unrecognized command!",
                f"Make sure that the command '{cmd}' exists, and you have "
                + "the permission to use it. \nFor help on bot commands, "
                + "do `pg!help`"
            )

        db_channel = self.guild.get_channel(common.DB_CHANNEL_ID)
        db_message = await db_channel.fetch_message(
            common.DB_BLACKLIST_MSG_IDS[common.TEST_MODE]
        )
        splits = db_message.content.split(":")
        cmds = splits[1].strip().split(" ") if len(splits) == 2 else []

        # command has been blacklisted from running
        if cmd in cmds:
            raise BotException(
                "Cannot execute comamand!",
                f"The command '{cmd}' has been temporarily been blocked from "
                + "running, while wizards are casting their spells on it!\n"
                + "Please try running the command after the maintenance work "
                + "has been finished"
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
                            f"`{key}` cannot be passed as a keyword argument",
                            cmd
                        )
                    args.append(kwargs.pop(key))

                elif param.default == param.empty:
                    raise ArgError(f"Missed required argument `{key}`", cmd)

                else:
                    args.append(param.default)
                    continue

            elif key in kwargs:
                raise ArgError(
                    "Positional cannot be passed again as a keyword argument",
                    cmd
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
                    raise KwargError(
                        f"Received invalid keyword argument `{key}`", cmd
                    )

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
