import asyncio
import math
import random
import sys
import time
import threading

import discord
import pygame
from constants import CLOCK_TIMEZONES



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
    return mention.replace("<", "").replace("@", "").replace("!", "").replace(">", "").replace(" ", "")


# Sends an embed with a much more tight function
async def send_embed(channel, title, description, color=0xFFFFAA):
    return await channel.send(
        embed=discord.Embed(title=title, description=description, color=color)
    )



def generate_arrow_points(point, arrow_vector, thickness=5.0, size_multiplier=1.0, tip_thickness_mul=0.75, tip_to_base_ratio=2.0/3.0):
    """
    Generates an arrow polygon
    """
    thickness *= size_multiplier
    
    #vec = Vec2D(point)
    px=point[0]; py=point[1]
    arrow_vec2d = (arrow_vector[0]*size_multiplier, arrow_vector[1]*size_multiplier)

    vec_length = (arrow_vec2d[0]*arrow_vec2d[0] + arrow_vec2d[1]*arrow_vec2d[1])**0.5

    if not (arrow_vec2d[0] and not arrow_vec2d[1]) or not vec_length:
        return ((0,0),)*7

    mvp_norm = (-arrow_vec2d[1]/vec_length, arrow_vec2d[0]/vec_length)

    thickness_part = thickness*tip_thickness_mul
    

    mvpstl = ( mvp_norm[0] * thickness_part,  mvp_norm[1] * thickness_part )

    point0 = ( mvp_norm[0] * thickness,  mvp_norm[1] * thickness )
    
    point1 = ( point0[0] + arrow_vec2d[0]*tip_to_base_ratio, point0[1] + arrow_vec2d[1]*tip_to_base_ratio )
    
    point2 = (point1[0] + mvpstl[0], point1[1] + mvpstl[1])
    
    point3 = arrow_vec2d

    mulp4 = -(thickness*2.0+thickness_part*2.0)

    point4 = (point2[0] + mvp_norm[0] * mulp4, point2[1] + mvp_norm[1] * mulp4)

    point5 = (point4[0] + mvpstl[0], point4[1] + mvpstl[1])

    point6 = (point5[0] + ((-arrow_vec2d[0])*tip_to_base_ratio), point5[1] + ((-arrow_vec2d[1])*tip_to_base_ratio))

    return ((int(point6[0]+px), int(point6[1]+py)), (int(point5[0]+px), int(point5[1]+py)), (int(point4[0]+px), int(point4[1]+py)), (int(point3[0]+px), int(point3[1]+py)), (int(point2[0]+px), int(point2[1]+py)), (int(point1[0]+px), int(point1[1]+py)), (int(point0[0]+px), int(point0[1]+py)))




async def user_clock(CLOCK_TIMEZONES, time):
    image = pygame.Surface((1280, 1280)).convert_alpha()
    font = pygame.font.Font("save/tahoma.ttf", 36)
    texts = []
    
    font.bold = True

    image.fill((0, 0, 0, 0))
    pygame.draw.circle(image, (255, 255, 146), (640, 640), 600, draw_top_left=True, draw_top_right=True)
    pygame.draw.circle(image, (0, 32, 96), (640, 640), 600, draw_bottom_left=True, draw_bottom_right=True)
    pygame.draw.circle(image, (0, 0, 0), (640, 640), 620, 32)

    for offset, name, color in CLOCK_TIMEZONES:
        angle = (time + offset) % 86400 / 86400 * 360 + 180
        s, c = math.sin(math.radians(angle)), math.cos(math.radians(angle))
        pygame.draw.polygon(image, color, generate_arrow_points((640, 640), (s * 560, -c * 560), tip_to_base_ratio=2/3))
        color = 255 - random.randint(0, 86)
        text = font.render(name, True, (color, 0, 0))
        texts.append((text, (s * 500 + 640 - text.get_width() // 2, -c * 500 + 640 - text.get_height() // 2)))
    pygame.draw.circle(image, (0, 0, 0), (640, 640), 64)

    for text, pos in texts:
        image.blit(text, pos)

    return image


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
