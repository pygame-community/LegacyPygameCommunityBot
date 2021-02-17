import asyncio
import math
import os
import random
import sys
import threading
import time
import traceback

import discord
import pygame
from pgbot.constants import INCLUDE_FUNCTIONS, CLOCK_TIMEZONES, ESC_CODE_BLOCK_QUOTE


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
        exec(f"{INCLUDE_FUNCTIONS}{code}", globals_)
        return time.perf_counter() - script_start

    except ImportError:
        raise PgExecBot(
            "Oopsies! The bot's exec function doesn't support importing " + \
            "external modules. Don't worry, many modules are pre-imported " + \
            "for you already! Just re-run your code, without the import statements"
        )

    except SyntaxError as e:
        offsetarrow = " " * e.offset + "^\n"
        lineno = e.lineno - INCLUDE_FUNCTIONS.count("\n")
        raise PgExecBot(f"SyntaxError at line {lineno}\n  " + \
                          e.text + '\n' + offsetarrow + e.msg)

    except Exception as err:
        ename = err.__class__.__name__
        details = err.args[0]
        lineno = (traceback.extract_tb(sys.exc_info()[-1])[-1][1]
                  - INCLUDE_FUNCTIONS.count("\n"))
        raise PgExecBot(f"{ename} at line {lineno}: {details}")


def safe_subscripting(list_: list, index: int):
    """
    Safe subscripting, does not error
    """
    try:
        return list_[index]
    except IndexError:
        return ""


def format_time(seconds: float, decimal_places: int = 4):
    """
    Formats time with a prefix
    """
    for fractions, unit in [
        (1.0, "s"),
        (1e-03, "ms"),
        (1e-06, "\u03bcs"),
        (1e-09, "ns"),
        (1e-12, "ps"),
        (1e-15, "fs"),
        (1e-18, "as"),
        (1e-21, "zs"),
        (1e-24, "ys"),
    ]:
        if seconds >= fractions:
            return f"{seconds / fractions:.0{decimal_places}f} {unit}"
    return f"very fast"


def format_byte(size: int, decimal_places=3):
    """
    Formats memory size with a prefix
    """
    dec = 10 ** decimal_places

    if size < 1e03:
        return f"{int(size * dec) / dec} B"
    if size < 1e06:
        return f"{int(size * 1e-03 * dec) / dec} KB"
    if size < 1e09:
        return f"{int(size * 1e-06 * dec) / dec} MB"

    return f"{int(size * 1e-09 * dec) / dec} GB"


def split_long_message(message: str):
    """
    Splits message string by 2000 characters with safe newline splitting
    """
    split_output = []
    lines = message.split('\n')
    temp = ""

    for line in lines:
        if len(temp) + len(line) + 1 > 2000:
            split_output.append(temp[:-1])
            temp = line + '\n'
        else:
            temp += line + '\n'

    if temp:
        split_output.append(temp)

    return split_output


def filter_id(mention: str):
    """
    Filters mention to get ID "<@!6969>" to "6969"
    Note that this function can error with ValueError on the int call, so the
    caller of this function must take care of this
    """
    for char in ("<", ">", "@", "&", "#", "!", " "):
        mention = mention.replace(char, "")
    return int(mention)


async def edit_embed(message, title, description, color=0xFFFFAA, url_image=None):
    """
    Edits the embed of a message with a much more tight function
    """
    embed = discord.Embed(title=title, description=description, color=color)
    if url_image:
        embed.set_image(url=url_image)

    return await message.edit(
        embed=embed
    )


async def send_embed(channel, title, description, color=0xFFFFAA, url_image=None):
    """
    Sends an embed with a much more tight function
    """
    embed = discord.Embed(title=title, description=description, color=color)
    if url_image:
        embed.set_image(url=url_image)

    return await channel.send(
        embed=embed
    )


# Ankith26 : TODO - SOMEONE PLEASE REFACTOR THIS FUNCTION I TRIED AND GAVE UP
def format_archive_messages(messages):
    """
    Formats a message to be archived
    """
    formatted_msgs = []
    for message in messages:
        triple_block_quote = '```'
        newline = '\n'
        formatted_msgs.append(
            f"**AUTHOR**: {message.author} ({message.author.mention}) [{message.author.id}]\n" +
            (f"**MESSAGE**: \n> {f'{newline}> '.join(message.content.split(newline))}\n" if message.content else "") +
            (f"**ATTACHMENT(S)**: \n> {f'{newline}> '.join(newline.join([f'{i+1}:{newline}    **Name**: {repr(attachment.filename)}{newline}    **URL**: {attachment.url}' for i, attachment in enumerate(message.attachments)]).split(newline))}\n" if message.attachments else "") +
            (f"**EMBED(S)**: \n> {f'{newline}> '.join(newline.join([(f'{i+1}:{newline}    **Title**: {embed.title}{newline}    **Description**: ```{newline}{(embed.description if isinstance(embed.description, str) else newline).replace(triple_block_quote, ESC_CODE_BLOCK_QUOTE)}```{newline}    **Image URL**: {embed.image.url}' if isinstance(embed, discord.Embed) else newline) for i, embed in enumerate(message.embeds)]).split(newline))}\n" if message.embeds else "")
        )
        asyncio.sleep(0.01) # Lets the bot do other things

    return formatted_msgs


def generate_arrow_points(center, arrow_vector, thickness=5.0, size_multiplier=1.0, tip_thickness_mul=0.75, tip_to_base_ratio=2.0/3.0):
    """
    Generates an arrow polygon
    """
    thickness *= size_multiplier

    arrow_vec2d = [arrow_vector[i] * size_multiplier for i in range(2)]
    vec_length = (arrow_vec2d[0] ** 2 + arrow_vec2d[1] ** 2) ** 0.5

    if not vec_length:
        return ((0, 0),) * 7

    mvp_norm = (-arrow_vec2d[1] / vec_length, arrow_vec2d[0] / vec_length)
    thickness_part = thickness * tip_thickness_mul
    mvpstl = (mvp_norm[0] * thickness_part,  mvp_norm[1] * thickness_part)

    points = []

    points.append([mvp_norm[i] * thickness for i in range(2)])
    points.append([
            points[0][i] + arrow_vec2d[i] * tip_to_base_ratio for i in range(2)
        ]
    )
    points.append([points[1][i] + mvpstl[i] for i in range(2)])
    points.append(arrow_vec2d)

    mulp4 = (thickness + thickness_part) * 2.0
    points.append([points[2][i] - mvp_norm[i] * mulp4 for i in range(2)])
    points.append([points[4][i] + mvpstl[i] for i in range(2)])
    points.append([
            points[5][i] - arrow_vec2d[i] * tip_to_base_ratio for i in range(2)
        ]
    )
    for point in points:
        for i in range(2):
            point[i] += center[i]
            point[i] = int(point[i])

    return points


def user_clock(t):
    """
    Generate a 24 hour clock for special server roles
    """
    image = pygame.Surface((1280, 1280)).convert_alpha()
    font = pygame.font.Font(os.path.join("assets", "tahoma.ttf"), 36)
    texts = []

    font.bold = True

    image.fill((0, 0, 0, 0))
    pygame.draw.circle(image, (255, 255, 146), (640, 640), 600,
                       draw_top_left=True, draw_top_right=True)
    pygame.draw.circle(image, (0, 32, 96), (640, 640), 600,
                       draw_bottom_left=True, draw_bottom_right=True)

    pygame.draw.circle(image, (0, 0, 0), (640, 640), 620, 32)

    for offset, name, color in CLOCK_TIMEZONES:
        angle = (t + offset) % 86400 / 86400 * 360 + 180
        s, c = math.sin(math.radians(angle)), math.cos(math.radians(angle))

        pygame.draw.polygon(
            image, color,
            generate_arrow_points(
                (640, 640), (s * 560, -c * 560),
                thickness=5, tip_thickness_mul=2,
                tip_to_base_ratio=0.1
            )
        )
        color = 255 - random.randint(0, 86)
        text = font.render(name, True, (color, 0, 0))
        texts.append(
            (
                text,
                (s * 500 + 640 - text.get_width() // 2,
                -c * 500 + 640 - text.get_height() // 2)
            )
        )
    pygame.draw.circle(image, (0, 0, 0), (640, 640), 64)

    for text, pos in texts:
        image.blit(text, pos)

    return image


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
