import sys
import threading

import discord


# Safe subscripting
def safe_subscripting(list_: list, index: int):
    try:
        return list_[index]
    except IndexError:
        return ""


# Formats time with a prefix
def format_time(seconds: float, decimal_places: int = 4):
    for fractions, unit in [
        (1.0, "s"),
        (1e-03, "ms"),
        (1e-06, "\u03bcs"),
    ]:
        if seconds >= fractions:
            return f"{seconds / fractions:.0{decimal_places}f} {unit}"
    return "very fast"


# Formats memory size with a prefix
def format_byte(size: int, decimal_places=3):
    dec = 10 ** decimal_places

    if size < 1e03:
        return f"{int(size * dec) / dec} B"
    if size < 1e06:
        return f"{int(size * 1e-03 * dec) / dec} KB"
    if size < 1e09:
        return f"{int(size * 1e-06 * dec) / dec} MB"

    return f"{int(size * 1e-09 * dec) / dec} GB"


# Filters mention to get ID '<@!6969>' to 6969
def filter_id(mention: str):
    return mention.replace("<", "").replace("@", "").replace("!", "").replace(">", "")


# Sends an embed with a much more tight function
async def send_embed(channel, title, description, color=0xFFFFAA):
    return await channel.send(
        embed=discord.Embed(title=title, description=description, color=color)
    )


# Modified thread with a kill method
class ThreadWithTrace(threading.Thread):
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
