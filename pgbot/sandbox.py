"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file defines exec sandbox utitites, for sandboxing and running user code.
"""


import asyncio
import builtins
import cmath
import itertools
import math
import multiprocessing
import random
import re
import string
import time
from inspect import getframeinfo, stack


import psutil
import pygame.freetype
import pygame.gfxdraw
from PIL import Image

from . import common, utils


class Output:
    """
    Output class for posting relevent data through discord
    """

    def __init__(self):
        self.text = ""
        self.img = None

        # internal
        self.exc = ""
        self.duration = -1  # The script execution time

        # gif related
        self.loops = 0
        self._imgs = []
        self._delays = []

    def add_frame(self, image, delay=200):
        lineno = getframeinfo(stack()[1][0]).lineno

        if isinstance(delay, (int, float)):
            try:
                delay = int(delay)
            except OverflowError:
                delay = 65536

            if 65535 < delay:
                self.exc = (
                    "That would take a lot of time."
                    f" Please choose a number between 0 and 65535. (line {lineno})"
                )
                return
            if 0 > delay:
                self.exc = (
                    "Negative time? That does not make sense..."
                    f" Please choose between 0 and 65535. (line {lineno})"
                )
                return
        else:
            self.exc = (
                f"TypeError at line {lineno}: "
                f"Argument delay must be int not '{delay.__class__.__name__}'"
            )
            return

        if not isinstance(image, pygame.Surface):
            self.exc = (
                f"TypeError at line {lineno}: "
                "Argument image must be type of pygame.Surface"
            )
            return

        self._imgs.append(image.copy())
        self._delays.append(delay)

    def _get_kwargs(self, tstamp, images):
        if len(self._delays) != len(self._imgs):
            return "Length of delays must be the same as the length of imgs"

        try:
            loops = int(getattr(self, "loops", 0))
        except OverflowError:
            loops = 0
        except (ValueError, TypeError):
            return "Please set the loops to an integer value."

        kwargs = {
            "fp": f"temp{tstamp}.gif",
            "format": "GIF",
            "append_images": images[1:],
            "save_all": True,
            "duration": self._delays,
        }

        if loops != 1:
            kwargs["loop"] = utils.clamp(loops - 1, 0, 100)

        return kwargs


class SandboxFunctionsObject:
    """
    Wrap custom functions for use in pg!exec
    """

    public_functions = ("print",)

    def __init__(self):
        self.output = Output()

    def print(self, *values, sep=" ", end="\n"):
        self.output.text = str(self.output.text)
        self.output.text += sep.join(map(str, values)) + end


filtered_builtins = {}
disallowed_builtins = (
    "__debug__",
    "__import__",
    "__loader__",
    "__spec__",
    "copyright",
    "credits",
    "exit",
    "type",
    "help",
    "input",
    "license",
    "print",
    "open",
    "quit",
    "compile",
    "exec",
    "eval",
    "getattr",
    "setattr",
    "delattr",
    "globals",
    "locals",
    "vars",
)

for key in dir(builtins):
    if key not in disallowed_builtins:
        filtered_builtins[key] = getattr(builtins, key)

filtered_builtins["__name__"] = "__main__"
filtered_builtins["__package__"] = ""
filtered_builtins["__file__"] = "<string>"
filtered_builtins["__doc__"] = filtered_builtins["__spec__"] = None


class FilteredPygame:
    """
    pygame module in a sandbox
    """

    time = pygame.time
    sprite = pygame.sprite
    Surface = pygame.Surface
    Rect = pygame.Rect
    Color = pygame.Color
    PixelArray = pygame.PixelArray
    draw = pygame.draw
    gfxdraw = pygame.gfxdraw
    transform = pygame.transform
    mask = pygame.mask
    math = pygame.math
    Vector2 = pygame.math.Vector2
    Vector3 = pygame.math.Vector3
    version = pygame.version

    class freetype:
        get_error = pygame.freetype.get_error
        get_version = pygame.freetype.get_version
        get_cache_size = pygame.freetype.get_cache_size
        get_default_resolution = pygame.freetype.get_default_resolution
        set_default_resolution = pygame.freetype.set_default_resolution
        SysFont = pygame.freetype.SysFont
        get_default_font = pygame.freetype.get_default_font
        Font = pygame.freetype.Font

    class image:
        fromstring = pygame.image.fromstring
        tostring = pygame.image.tostring
        frombuffer = pygame.image.frombuffer

    class font:
        get_default_font = pygame.font.get_default_font
        get_fonts = pygame.font.get_fonts
        match_font = pygame.font.match_font
        SysFont = pygame.font.SysFont
        Font = pygame.font.Font

    class constants:
        pass


del FilteredPygame.mask.__loader__
del FilteredPygame.math.__loader__
del FilteredPygame.transform.__loader__
del FilteredPygame.draw.__loader__
del FilteredPygame.gfxdraw.__loader__
del FilteredPygame.version.__loader__

del FilteredPygame.mask.__spec__
del FilteredPygame.math.__spec__
del FilteredPygame.transform.__spec__
del FilteredPygame.draw.__spec__
del FilteredPygame.gfxdraw.__spec__
del FilteredPygame.version.__spec__

for const in pygame.constants.__all__:
    setattr(FilteredPygame.constants, const, pygame.constants.__dict__[const])
    setattr(FilteredPygame, const, pygame.constants.__dict__[const])


def pg_exec(code: str, tstamp: int, allowed_builtins: dict, q: multiprocessing.Queue):
    """
    exec wrapper used for pg!exec, runs in a seperate process. Since this
    function runs in a seperate Process, keep that in mind if you want to make
    any changes to this function (that is, do not touch this shit if you don't
    know what you are doing)
    """
    sandbox_funcs = SandboxFunctionsObject()
    output = sandbox_funcs.output

    allowed_globals = {
        "math": math,
        "cmath": cmath,
        "random": random,
        "re": re,
        "time": time,
        "string": string,
        "itertools": itertools,
    }

    for module in allowed_globals:
        del allowed_globals[module].__loader__, allowed_globals[module].__spec__

    allowed_globals["__builtins__"] = allowed_builtins
    allowed_globals["pygame"] = FilteredPygame
    allowed_globals["output"] = output

    allowed_globals.update(allowed_builtins)

    for func_name in sandbox_funcs.public_functions:
        allowed_globals[func_name] = getattr(sandbox_funcs, func_name)

    for ill_attr in common.ILLEGAL_ATTRIBUTES:
        if ill_attr in code:
            output.exc = "Suspicious Pattern"
            q.put(output)
            return

    script_start = time.perf_counter()
    try:
        exec(code + "\n", allowed_globals)

    except ImportError:
        output.exc = (
            "Oopsies! The bot's exec function doesn't support importing "
            "external modules. Don't worry, many modules are pre- imported "
            "for you already! Just re-run your code, without the import "
            "statements"
        )

    except Exception as err:
        output.exc = utils.format_code_exception(err)

    finally:
        output.duration = time.perf_counter() - script_start

    # Because output needs to go through queue, we need to sanitize it first
    # Any random data that gets put in the queue will likely crash the entire
    # bot
    sanitized_output = Output()
    if isinstance(getattr(output, "text", None), str):
        sanitized_output.text = output.text

    if isinstance(getattr(output, "duration", None), float):
        sanitized_output.duration = output.duration

    if isinstance(getattr(output, "exc", None), str):
        sanitized_output.exc = output.exc

    if isinstance(getattr(output, "img", None), pygame.Surface):
        # A surface is not picklable, so handle differently
        sanitized_output.img = True
        pygame.image.save(output.img, f"temp{tstamp}.png")

    if getattr(output, "_imgs", None):
        i = 0
        images = []
        if isinstance(output._imgs, list):
            for surf in output._imgs:
                if not isinstance(surf, pygame.Surface):
                    continue
                if i == 0:
                    pygame.image.save(surf, f"temp{tstamp}.png")

                image = Image.frombytes(
                    "RGBA", surf.get_size(), pygame.image.tostring(surf, "RGBA")
                )
                images.append(image)

                i += 1

            if i > 0:
                img = Image.open(f"temp{tstamp}.png")
                kwargs = output._get_kwargs(tstamp, images)
                if isinstance(kwargs, str):
                    sanitized_output.exc = kwargs
                else:
                    img.save(**kwargs)
                    sanitized_output._imgs = True

    q.put(sanitized_output)


async def exec_sandbox(
    code: str, tstamp: int, timeout: int = 5, max_memory: int = 2 ** 28
):
    """
    Helper to run pg!exec code in a sandbox, manages the seperate process that
    runs to execute user code.
    """
    q = multiprocessing.Queue(1)
    proc = multiprocessing.Process(
        target=pg_exec,
        args=(code, tstamp, filtered_builtins, q),
        daemon=True,  # the process must die when the main process dies
    )
    proc.start()
    psproc = psutil.Process(proc.pid)

    # is system-wide and has the highest resolution.
    start = time.perf_counter()
    while proc.is_alive():
        if start + timeout < time.perf_counter():
            output = Output()
            output.exc = f"Hit timeout of {timeout} seconds!"
            output.duration = timeout
            proc.kill()
            return output

        try:
            if psproc.memory_info().rss > max_memory:
                output = Output()
                output.exc = f"The bot's memory has taken up to {max_memory} bytes!"
                proc.kill()
                return output
        except psutil.NoSuchProcess:
            # The process finished but it tried to check it's memory usage
            # at the "wrong time". Get the output from the queue and return it
            return q.get()

        await asyncio.sleep(0.05)  # Let the bot do other async things

    return q.get()
