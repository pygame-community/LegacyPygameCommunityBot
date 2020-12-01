import sys
from typing import Any

import discord
import threading


# Safe subscripting
from discord import Message


def safeSub(input_list: list, index: int) -> Any:
    try:
        return input_list[index]
    except IndexError:
        return ''


# Formats time with a prefix
def formatTime(seconds: float, decimal_places: int = 4) -> str:
    for fractions, unit in [(1.0, "s"), (1e-03, "ms"), (1e-06, "\u03bcs"), (1e-09, "ns"), (1e-12, "ps")]:
        if seconds >= fractions:
            return f"{seconds * 1 / fractions:.0{decimal_places}f} {unit}"
    raise ValueError(f"Invalid seconds '{seconds}''")


# Formats memory size with a prefix
def formatByte(b: int, decimal_places: int = 3) -> str:
    dec: int = 10 ** decimal_places

    if b < 1e+03:
        return f'{int(b * dec) / dec} B'
    elif b < 1e+06:
        return f'{int(b * 1e-03 * dec) / dec} KB'
    elif b < 1e+09:
        return f'{int(b * 1e-06 * dec) / dec} MB'
    else:
        return f'{int(b * 1e-09 * dec) / dec} GB'


# Filters mention to get ID '<@!6969>' to 6969
def filterID(mention: str) -> str:
    return mention.replace('<', '').replace('@', '').replace('!', '').replace('>', '')


# Sends an embed with a much more tight function
async def sendEmbed(channel: discord.TextChannel, title: str, description: str, color: int = 0xFFFFAA) -> Message:
    return await channel.send(embed=discord.Embed(title=title, description=description, color=color))


# Modified thread with a kill method
class ThreadWithTrace(threading.Thread):
    def __init__(self, *args, **keywords):
        threading.Thread.__init__(self, *args, **keywords)
        self.killed = False
        self.__run_backup: None = None
        self.run = None

    def start(self):
        self.__run_backup = self.run
        self.run = self.__run
        threading.Thread.start(self)

    def __run(self):
        sys.settrace(self.globaltrace)
        self.__run_backup()
        self.run = self.__run_backup

    def globaltrace(self, frame, event, arg):
        if event == 'call':
            return self.localtrace
        else:
            return None

    def localtrace(self, frame, event, arg):
        if self.killed:
            if event == 'line':
                raise SystemExit()
        return self.localtrace

    def kill(self):
        self.killed = True
