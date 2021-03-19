import asyncio
import builtins
import cmath
import gc
import itertools
import math
import os
import random
import re
import string
import sys
import threading
import time
import traceback

import psutil
import pygame.freetype
import pygame.gfxdraw

from . import common, util


class PgExecBot(Exception):
    """
    Base class for pg!exec exceptions
    """
    pass


def pg_exec(code: str, globals_: dict):
    """
    exec wrapper used for pg!exec, with better error reporting
    """
    try:
        script_start = time.perf_counter()
        exec(f"{common.INCLUDE_FUNCTIONS}{code}", globals_)
        return time.perf_counter() - script_start

    except ImportError:
        raise PgExecBot(
            "Oopsies! The bot's exec function doesn't support importing " + \
            "external modules. Don't worry, many modules are pre-imported " + \
            "for you already! Just re-run your code, without the import statements"
        )

    except SyntaxError as e:
        offsetarrow = " " * e.offset + "^\n"
        lineno = e.lineno - common.INCLUDE_FUNCTIONS.count("\n")
        raise PgExecBot(f"SyntaxError at line {lineno}\n  " + \
                          e.text + '\n' + offsetarrow + e.msg)

    except Exception as err:
        ename = err.__class__.__name__
        details = err.args[0]
        lineno = (traceback.extract_tb(sys.exc_info()[-1])[-1][1]
                  - common.INCLUDE_FUNCTIONS.count("\n"))
        raise PgExecBot(f"{ename} at line {lineno}: {details}")


class ThreadWithTrace(threading.Thread):
    """
    Modified thread with a kill method
    """
    def __init__(self, *args, **keywords):
        threading.Thread.__init__(self, *args, **keywords)
        self.killed = False

    def start(self):
        self.__run_backup = self.run
        self.run = self.__run
        threading.Thread.start(self)

    def __run(self):
        sys.settrace(self.global_trace)
        self.__run_backup()
        self.run = self.__run_backup

    def global_trace(self, frame, event, arg):
        if event == "call":
            return self.local_trace
        return None

    def local_trace(self, frame, event, arg):
        if self.killed:
            if event == "line":
                raise SystemExit()
        return self.local_trace

    def kill(self):
        self.killed = True


process = psutil.Process(os.getpid())

filtered_builtins = {}
disallowed_builtins = (
    "__debug__",
    "__doc__",
    "__import__",
    "__loader__",
    "__package__",
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


class FilteredPygame:
    Surface = pygame.Surface
    Rect = pygame.Rect
    Color = pygame.Color
    PixelArray = pygame.PixelArray
    draw = pygame.draw
    gfxdraw = pygame.gfxdraw
    transform = pygame.transform
    mask = pygame.mask
    math = pygame.math
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

allowed_globals["__builtins__"] = filtered_builtins
allowed_globals["pygame"] = FilteredPygame

for k in filtered_builtins:
    allowed_globals[k] = filtered_builtins[k]


class Output:
    def __init__(self):
        self.text = ""
        self.img = None
        self.exc = None
        self.duration = -1  # The script execution time


async def exec_sandbox(code: str, timeout=5, max_memory=2 ** 28):
    output = Output()
    allowed_globals["output"] = output

    for illegal_patterns in ["__subclasses__", "__loader__", "__bases__", "__code__",
                             "__getattribute__", "__setattr__", "__delattr_", "mro"]:
        if illegal_patterns in code:
            output.exc = PgExecBot("Suspicious Pattern")
            return output

    def exec_thread():
        glob = allowed_globals.copy()
        try:
            output.duration = pg_exec(code, glob)
        except Exception as exc:
            output.exc = exc

        glob.clear()
        gc.collect()

    thread = ThreadWithTrace(target=exec_thread)
    thread.start()

    start = time.time()
    while thread.is_alive():
        if start + timeout < time.time():
            output.exc = PgExecBot(
                f"Sandbox was running for more than the timeout of {timeout} seconds!"
            )
            break
        if process.memory_info().rss > max_memory:
            output.exc = PgExecBot(
                f"The bot's memory has taken up to {max_memory} bytes!"
            )
            break
        await asyncio.sleep(0.05)  # Let the bot do other async things

    thread.kill()
    thread.join()
    return output
