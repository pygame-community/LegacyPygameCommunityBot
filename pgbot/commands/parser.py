"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file defines the main utility functions for the argument parser
"""

from __future__ import annotations

from typing import Any, Generator, Optional, Union


# mapping of all escape characters to their escaped values
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


# declare a dict of anno names, and the respective messages to give on error
ANNO_AND_ERROR = {
    "str": "a normal argument",
    "CodeBlock": "a codeblock, code surrounded in code ticks",
    "String": 'a string, surrounded in quotes (`""`)',
    "datetime.datetime": "a string, that denotes datetime in iso format",
    "datetime": "a string, that denotes datetime in iso format",
    "range": "a range specifier",
    "pygame.Color": "a color, represented by the color name or the hex RGB value",
    "common.Channel": "an ID or mention of a Discord server text channel",
    "discord.Object": "a generic Discord Object with an ID",
    "discord.Role": "an ID or mention of a Discord server Role",
    "discord.Member": "an ID or mention of a Discord server member",
    "discord.User": "an ID or mention of a Discord user",
    "discord.TextChannel": "an ID or mention of a Discord server text channel",
    "discord.Guild": "an ID of a discord guild (server)",
    "discord.Message": (
        "a message ID, or a 'channel_id/message_id' combo, or a [link](#) to a message"
    ),
    "discord.PartialMessage": (
        "a message ID, or a 'channel_id/message_id' combo, or a [link](#) to a message"
    ),
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

    def __init__(self, text: str, no_backticks: bool = False):
        self.lang = None
        self.text = code = text

        md_bacticks = ("```", "`")

        if no_backticks and "\n" in code:
            newline_idx = code.index("\n")
            self.lang = code[:newline_idx].strip().lower()
            self.lang = self.lang if self.lang else None
            code = code[newline_idx + 1 :]

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
                # got a backslash, handle escapes
                char = string[cnt]
                cnt += 1
                if char.lower() in ["x", "u"]:  # these are unicode escapes
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
                    # general escapes
                    newstr += ESCAPES[char]
                else:
                    raise BotException(
                        "Invalid escape character",
                        "Invalid unicode escape character in string",
                    )
            else:
                newstr += char

        return newstr


SPLIT_FLAGS = [
    ("```", CodeBlock, (True,)),
    ("`", CodeBlock, (True,)),
    ('"', String, ()),
    ("'", String, ()),
]


def split_anno(anno: str):
    """
    Helper to split an anno string based on commas, but does not split commas
    within nested annotations. Returns a generator of strings.
    """
    nest_cnt = 0
    prev = 0
    for cnt, char in enumerate(anno):
        if char == "[":
            nest_cnt += 1
        elif char == "]":
            nest_cnt -= 1
        elif char == "," and not nest_cnt:
            ret = anno[prev:cnt].strip()
            prev = cnt + 1
            if ret:
                yield ret

    ret = anno[prev:].strip()
    if ret and not nest_cnt:
        yield ret


def strip_optional_anno(anno: str):
    """
    Helper to strip "Optional" anno
    """
    anno = anno.strip()
    if anno.startswith("Optional[") and anno.endswith("]"):
        # call recursively to split "Optional" chains
        return strip_optional_anno(anno[9:-1])

    return anno


def split_union_anno(anno: str):
    """
    Helper to split a 'Union' annotation. Returns a generator of strings.
    """
    anno = strip_optional_anno(anno)
    if anno.startswith("Union[") and anno.endswith("]"):
        for anno in split_anno(anno[6:-1]):
            # use recursive splits to "flatten" unions
            yield from split_union_anno(anno)
    else:
        yield anno


def split_tuple_anno(anno: str):
    """
    Helper to split a 'tuple' annotation.
    Returns None if anno is not a valid tuple annotation
    """
    if anno == "tuple":
        anno = "tuple[Any, ...]"

    if anno.startswith("tuple[") and anno.endswith("]"):
        return list(split_anno(anno[6:-1]))


def get_anno_error(anno: str) -> str:
    """
    Get error message to display to user when user has passed invalid arg
    """
    union_errors = []
    for subanno in split_union_anno(anno):
        tupled = split_tuple_anno(subanno)
        if tupled is None:
            union_errors.append(ANNO_AND_ERROR.get(subanno, f"of type `{subanno}`"))
            continue

        # handle tuple
        if len(tupled) == 2 and tupled[1] == "...":
            # variable length tuple
            union_errors.append(
                f"a tuple, where each element is {get_anno_error(tupled[0])}"
            )

        else:
            ret = "a tuple, where "
            for i, j in enumerate(map(get_anno_error, tupled)):
                ret += f"element at index {i} is {j}; "

            union_errors.append(ret[:-2])  # strip last two chars, which is "; "

    msg = ""
    if len(union_errors) != 1:
        # display error messages of all the union-ed annos
        msg += "either "
        msg += ", or ".join(union_errors[:-1])
        msg += ", or atleast, "

    msg += union_errors[-1]
    return msg


def split_args(
    split_str: str, split_flags: list[tuple[str, Any, tuple]]
) -> Generator[Union[str, String, CodeBlock], None, None]:
    """
    Utility function to do the first parsing step to recursively split
    string based on seperators
    """
    if not split_flags:
        # we are done with splitting, and got the node at the final depth
        yield split_str
        return

    splitchar, splitfunc, exargs = split_flags.pop(0)

    cnt = 0
    prev = ""
    for substr in split_str.split(splitchar):
        if cnt % 2:
            if substr.endswith("\\"):
                # last split character escaped, do not split on it
                prev += substr[:-1] + splitchar
                continue

            yield splitfunc(prev + substr, *exargs)
            prev = ""

        else:
            # recursively split the remaining substrings
            yield from split_args(substr, split_flags.copy())

        cnt += 1

    if not cnt % 2 or prev:
        raise BotException(
            f"Invalid {splitfunc.__name__}!",
            f"{splitfunc.__name__} was not properly closed",
        )


def parse_args(cmd_str):
    """
    Custom parser for handling arguments. This function parses the source
    string of the command into the command name, a list of arguments and a
    dictionary of keyword arguments. Arguments must only contain strings,
    'CodeBlock' objects, 'String' objects and tuples.
    """
    args: list[Any] = []
    kwargs: dict[str, Any] = {}
    temp_list: Optional[list[Any]] = None  # used to store the temporary tuple

    kwstart = False  # used to make sure that keyword args come after args
    prevkey = None  # temporarily store previous key name

    def append_arg(arg: Any):
        """
        Internal helper funtion to append a parsed argument into arg/kwarg/tuple
        """
        nonlocal prevkey
        if temp_list is not None:
            # already in a tuple, flush arg into that
            temp = temp_list
            while temp and isinstance(temp[-1], list):
                temp = temp[-1]

            temp.append(arg)
        else:
            if prevkey is not None:
                # had a keyword, flush arg into keyword
                kwargs[prevkey] = arg
                prevkey = None
            else:
                if kwstart:
                    raise KwargError(
                        "Keyword arguments cannot come before positional arguments"
                    )
                args.append(arg)

    for arg in split_args(cmd_str, SPLIT_FLAGS.copy()):
        if not isinstance(arg, str):
            append_arg(arg)
            continue

        # these string replacements are done to make parsing easier
        # ignore any commas in the source string, just treat them as spaces
        for a, b in (
            (" =", "="),
            (",", " "),
            (")(", ") ("),
            ("=(", "= ("),
        ):
            arg = arg.replace(a, b)

        for substr in arg.split():
            if not substr:
                continue

            splits = substr.split("=")
            if len(splits) == 2:
                # got first keyword, mark a flag so that future arguments are
                # all keywords
                kwstart = True
                if temp_list is not None:
                    # we were parsing a tuple, and got keyword arg
                    raise KwargError("Keyword arguments cannot come inside a tuple")

                # underscores not allowed at start of keyword names here
                if not splits[0][0].isalpha():
                    raise KwargError("Keyword argument must begin with an alphabet")

                if prevkey:
                    # we had a prevkey, and also got a new keyword in the
                    # same iteration
                    raise KwargError("Did not specify argument after '='")

                prevkey = splits[0]
                if not prevkey:
                    # we do not have keyword name
                    raise KwargError("Missing keyword before '=' symbol")

                if splits[1]:
                    # flush kwarg
                    kwargs[prevkey] = splits[1]
                    prevkey = None

            elif len(splits) == 1:
                # current substring is not a keyword (does not have =)
                while substr.startswith("("):
                    # start of a tuple
                    if temp_list is not None:
                        temp = temp_list
                        while temp and isinstance(temp[-1], list):
                            temp = temp[-1]

                        temp.append([])
                    else:
                        temp_list = []

                    substr = substr[1:]
                    if not substr:
                        continue

                oldlen = len(substr)
                substr = substr.rstrip(")")
                count = oldlen - len(substr)
                if substr:
                    append_arg(substr)

                for _ in range(count):
                    # end of a tuple
                    if temp_list is None:
                        raise ArgError("Invalid closing tuple bracket")

                    prevtemp = None
                    temp = temp_list
                    while temp and isinstance(temp[-1], list):
                        prevtemp = temp
                        temp = temp[-1]

                    if prevtemp is None:
                        arg = tuple(temp)
                        temp_list = None
                        append_arg(arg)
                    else:
                        prevtemp[-1] = tuple(temp)
            else:
                raise KwargError("Invalid number of '=' in keyword argument expression")

    if temp_list is not None:
        raise ArgError("Tuple was not closed")

    if prevkey:
        raise KwargError("Did not specify argument after '='")

    # user entered something like 'pg!', display help message
    if not args:
        if kwargs:
            raise BotException("Invalid Command name!", "Command name must be str")
        args = ["help"]

    cmd = args.pop(0)
    if not isinstance(cmd, str):
        raise BotException("Invalid Command name!", "Command name must be str")

    return cmd, args, kwargs
